"""Interactive test orchestration, cancellation, OTP, and progress streaming."""
import asyncio
import json
import secrets
import time
import uuid
from queue import Queue, Empty, Full
from threading import Event, Thread, Lock
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request
from backend.tests_runner.solver import run_session
from backend.infrastructure.jobs import job_scope, check_cancelled, JobCancelled, MAX_JOB_SECONDS
from backend.infrastructure.limits import client_ip, sms_limiter
from backend.infrastructure.test_queue import test_queue, rate_key, MAX_QUEUE_SECONDS
from backend.infrastructure.errors import client_error
from backend.infrastructure.logging import log
from backend.api.schemas import SessionRequest, OtpRequest
from backend.api.identity import run_owner

otp_waiters: dict[str, dict] = {}
otp_lock = Lock()

def make_otp_callback(run_id: str, owner: str, progress_queue: Queue | None = None, timeout: int = 150):
    def otp_callback():
        waiter = {"event": Event(), "code": None, "owner": owner}
        with otp_lock:
            otp_waiters[run_id] = waiter
        if progress_queue is not None:
            progress_queue.put({
                "stage": "otp_required",
                "progress": 15,
                "message": "Vnesite SMS kodo iz Lidl prijave.",
                "run_id": run_id,
            })
        try:
            deadline = time.monotonic() + timeout
            while not waiter["event"].wait(timeout=0.2):
                check_cancelled()
                if time.monotonic() >= deadline:
                    raise TimeoutError("Čas za vnos SMS kode je potekel")
            check_cancelled()
            if not waiter["code"]:
                raise RuntimeError("SMS koda ni bila poslana")
            return waiter["code"]
        finally:
            with otp_lock:
                if otp_waiters.get(run_id) is waiter:
                    otp_waiters.pop(run_id, None)

    return otp_callback


def submit_otp(req: OtpRequest, request: Request):
    sms_limiter.check(client_ip(request))
    owner = run_owner(request)
    with otp_lock:
        waiter = otp_waiters.get(req.run_id)
        if waiter is None or not secrets.compare_digest(waiter["owner"], owner):
            raise HTTPException(status_code=404, detail="SSO prijava ne čaka na SMS kodo")
        otp_waiters.pop(req.run_id)
        waiter["code"] = req.otp
        waiter["event"].set()
    return {"status": "ok"}


async def run_plu_session(req: SessionRequest, request: Request):
    owner = run_owner(request)
    ticket = test_queue.enqueue(owner, rate_key(request, owner))
    release = ticket.release
    try:
        while not ticket.try_start():
            if time.monotonic() - ticket.created >= MAX_QUEUE_SECONDS:
                raise HTTPException(408, "Čas čakanja v vrsti je potekel. Poskusite znova.")
            if await request.is_disconnected():
                raise HTTPException(499, "Povezava je bila prekinjena.")
            await asyncio.sleep(0.2)
    except BaseException:
        ticket.cancel()
        ticket.release()
        raise
    cancel = Event()
    deadline = time.monotonic() + MAX_JOB_SECONDS

    def work():
        try:
            with job_scope(cancel, deadline):
                run_id = str(uuid.uuid4())
                otp_callback = make_otp_callback(run_id, owner) if req.login_method == "sso" else None
                result = run_session(req.email, req.password, req.target_score,
                                   login_method=req.login_method, otp_callback=otp_callback, mode=req.mode)
                from backend.scheduling.service import verified_test
                verified_test(owner, result.get("user_id"), req.email, req.password, req.login_method)
                return result
        finally:
            release()

    try:
        task = asyncio.create_task(asyncio.to_thread(work))
    except BaseException:
        release()
        raise
    try:
        while not task.done():
            if time.monotonic() >= deadline:
                raise HTTPException(408, "Čas izvajanja testa je potekel. Poskusite znova.")
            if await request.is_disconnected():
                cancel.set()
                raise JobCancelled("Client disconnected")
            await asyncio.sleep(0.2)
        return {"status": "success", "data": await task}
    except HTTPException:
        raise
    except JobCancelled:
        raise HTTPException(status_code=499, detail="Povezava je bila prekinjena.") from None
    except Exception as e:
        log("solver", "Session request failed:", e)
        raise HTTPException(status_code=500, detail=client_error(e)) from None
    finally:
        cancel.set()
        if not task.done():
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)


async def run_plu_session_stream(req: SessionRequest, request: Request):
    """Stream solver progress using Server-Sent Events"""
    owner = run_owner(request)
    ticket = test_queue.enqueue(owner, rate_key(request, owner))
    release = ticket.release
    progress_queue = Queue(maxsize=64)
    cancel = Event()
    deadline = time.monotonic() + MAX_JOB_SECONDS
    result_container = {"result": None, "error": None}
    
    def emit_progress(data):
        while not cancel.is_set():
            try:
                progress_queue.put(data, timeout=0.2)
                return
            except Full:
                continue
        raise JobCancelled("Client disconnected")

    def run_solver():
        try:
            with job_scope(cancel, deadline):
                run_worker()
        except JobCancelled:
            log("solver", "Job cancelled after client disconnect")
        finally:
            release()

    def run_worker():
        try:
            attempt = 0
            max_attempts = 50
            run_id = str(uuid.uuid4())
            otp_callback = make_otp_callback(run_id, owner, progress_queue) if req.login_method == "sso" else None
            authenticated_user_id = None
            
            while attempt < max_attempts:
                check_cancelled()
                attempt += 1
                emit_progress({
                    "stage": "attempt_start",
                    "progress": 0,
                    "message": "Pripravljam test...",
                    "attempt": attempt,
                    "user_knowledge": None
                })
                
                result = run_session(
                    req.email, 
                    req.password, 
                    req.target_score, 
                    progress_callback=lambda data: emit_progress({
                        **data,
                        "attempt": attempt
                    }),
                    login_method=req.login_method,
                    otp_callback=otp_callback,
                    user_id=authenticated_user_id,
                    mode=req.mode,
                )
                from backend.scheduling.service import verified_test
                verified_test(owner, result.get("user_id"), req.email, req.password, req.login_method)
                authenticated_user_id = authenticated_user_id or result.get("user_id")
                
                user_knowledge = result.get("user_knowledge", 0)
                
                emit_progress({
                    "stage": "attempt_complete",
                    "progress": 90,
                    "message": "Preverjam doseženo znanje...",
                    "attempt": attempt,
                    "user_knowledge": user_knowledge,
                    "result": result
                })
                
                if req.full_knowledge and req.mode != "tasks":
                    if user_knowledge >= 100.0:
                        emit_progress({
                            "stage": "final",
                            "progress": 100,
                            "message": "Končano! Doseženo 100 % znanje.",
                            "attempt": attempt,
                            "user_knowledge": user_knowledge,
                            "result": result
                        })
                        result_container["result"] = result
                        break
                    else:
                        emit_progress({
                            "stage": "retrying",
                            "progress": 95,
                            "message": "Test se samodejno nadaljuje do 100 % znanja.",
                            "attempt": attempt,
                            "user_knowledge": user_knowledge
                        })
                        continue
                else:
                    emit_progress({
                        "stage": "final",
                        "progress": 100,
                        "message": "Končano",
                        "attempt": attempt,
                        "user_knowledge": user_knowledge,
                        "result": result
                    })
                    result_container["result"] = result
                    break
            
            if attempt >= max_attempts:
                emit_progress({
                    "stage": "error",
                    "progress": 0,
                    "message": f"Dosežena največja števila poskusov ({max_attempts}). Znanje: {result.get('user_knowledge', 0):.2f}%",
                    "error": "Max attempts reached"
                })
        except JobCancelled:
            raise
        except Exception as e:
            message = client_error(e)
            log("solver", "Stream worker failed:", e)
            result_container["error"] = message
            emit_progress({"stage": "error", "progress": 0, "message": message, "error": message})
        finally:
            if not cancel.is_set():
                emit_progress(None)
    
    async def event_generator():
        nonlocal deadline
        worker_started = False
        try:
            yield ": connected\n\n"
            last_notice = 0
            while not ticket.try_start():
                now = time.monotonic()
                if now - ticket.created >= MAX_QUEUE_SECONDS:
                    yield f"data: {json.dumps({'stage': 'error', 'message': 'Čas čakanja v vrsti je potekel. Poskusite znova.'})}\n\n"
                    return
                if await request.is_disconnected():
                    return
                if now - last_notice >= 10:
                    notice = {"stage": "queued", "progress": 0, "message": "Ste v čakalni vrsti. Test se bo samodejno začel, ko bo na voljo prosto mesto."}
                    yield f"data: {json.dumps(notice)}\n\n"
                    last_notice = now
                await asyncio.sleep(0.2)
            deadline = time.monotonic() + MAX_JOB_SECONDS
            solver_thread = Thread(target=run_solver, daemon=True)
            solver_thread.start()
            worker_started = True
            last_sent = time.monotonic()
            while True:
                if time.monotonic() >= deadline:
                    yield f"data: {json.dumps({'stage': 'error', 'message': 'Čas izvajanja testa je potekel. Poskusite znova.'})}\n\n"
                    break
                try:
                    data = progress_queue.get(timeout=0.1)
                except Empty:
                    if time.monotonic() - last_sent >= 10:
                        yield ": keep-alive\n\n"
                        last_sent = time.monotonic()
                    await asyncio.sleep(0.1)
                    continue
                
                if data is None:
                    break
                
                # Send SSE formatted data
                yield f"data: {json.dumps(data)}\n\n"
                last_sent = time.monotonic()
                
                # If we got final result or error, break
                if data.get("stage") in ["final", "error"]:
                    break
        except Exception as e:
            log("solver", "Progress stream failed:", e)
            yield f"data: {json.dumps({'stage': 'error', 'message': client_error(e)})}\n\n"
        finally:
            cancel.set()
            ticket.cancel()
            if not worker_started:
                ticket.release()
    
    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    return response


