from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import re
from typing import Literal
from back.security.body_limit import BodyLimitMiddleware
from back.plu.solver import run_session
from back.runtime.jobs import job_scope, check_cancelled, JobCancelled, MAX_JOB_SECONDS
from back.security.limits import limiter, client_ip, sms_limiter
from back.runtime.single_worker import lifespan
from back.core.errors import client_error
from back.core.debug import log
from fastapi.exceptions import RequestValidationError
import json
import asyncio
import uuid
import time
import secrets
from pathlib import Path
from starlette.requests import Request
from queue import Queue, Empty, Full
from threading import Event, Thread, Lock

app = FastAPI(title="PLU Solver API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Neveljavni podatki zahteve."})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log("solver", "API request failed:", exc)
    return JSONResponse(status_code=500, content={"detail": client_error(exc)})

_key_file = Path(__file__).resolve().parent.parent / ".api-key"
_internal_key = _key_file.read_text().strip() if _key_file.exists() else ""


@app.middleware("http")
async def require_internal_key(request: Request, call_next):
    if not _internal_key:
        return JSONResponse(status_code=503, content={"detail": "API access is not configured"})
    supplied = request.headers.get("x-internal-key", "")
    if not secrets.compare_digest(supplied.encode(), _internal_key.encode()):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)

otp_waiters: dict[str, dict] = {}
otp_lock = Lock()


def run_owner(request):
    owner = request.headers.get("x-run-owner", "")
    if len(owner) != 64 or any(char not in "0123456789abcdef" for char in owner):
        raise HTTPException(403, "Prijavna seja ni veljavna.")
    return owner


origins = [
    "http://localhost:3000",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       
    allow_credentials=True,
    allow_methods=["*"],         
    allow_headers=["*"],        
)

class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=1024)
    target_score: int | None = Field(default=None, ge=0, le=99, strict=True)
    full_knowledge: bool = False
    login_method: Literal["easyplu", "easy-plu", "sso"] = "easyplu"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if not value.strip():
            raise ValueError("Empty username")
        return value.strip()

    @model_validator(mode="after")
    def validate_login_identity(self):
        pattern = r"[0-9]{8}" if self.login_method == "sso" else r"[^\s@]+@[^\s@]+\.[^\s@]+"
        if not re.fullmatch(pattern, self.email):
            raise ValueError("Invalid login identity")
        return self


class OtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


app.add_middleware(BodyLimitMiddleware)

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


@app.post("/submit-otp")
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


@app.post("/run-session")
async def run_plu_session(req: SessionRequest, request: Request):
    owner = run_owner(request)
    release = limiter.acquire(client_ip(request))
    cancel = Event()
    deadline = time.monotonic() + MAX_JOB_SECONDS

    def work():
        try:
            with job_scope(cancel, deadline):
                run_id = str(uuid.uuid4())
                otp_callback = make_otp_callback(run_id, owner) if req.login_method == "sso" else None
                return run_session(req.email, req.password, req.target_score,
                                   login_method=req.login_method, otp_callback=otp_callback)
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

@app.post("/run-session-stream")
async def run_plu_session_stream(req: SessionRequest, request: Request):
    """Stream solver progress using Server-Sent Events"""
    owner = run_owner(request)
    release = limiter.acquire(client_ip(request))
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
                )
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
                
                if req.full_knowledge:
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
    
    solver_thread = Thread(target=run_solver, daemon=True)
    try:
        solver_thread.start()
    except BaseException:
        release()
        raise
    
    async def event_generator():
        try:
            yield ": connected\n\n"
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

@app.get("/health", tags=["Health"])
async def health():
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "api",
        }
    )
