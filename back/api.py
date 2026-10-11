from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from solver import run_session
import json
import asyncio
import uuid
import time
from queue import Queue, Empty
from threading import Event, Thread

app = FastAPI(title="PLU Solver API")

otp_waiters: dict[str, dict] = {}

# Allow frontend to access backend
origins = [
    "http://localhost:3000",  # your frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # allow your frontend origin
    allow_credentials=True,
    allow_methods=["*"],         # allow all HTTP methods
    allow_headers=["*"],         # allow all headers
)

class SessionRequest(BaseModel):
    email: str
    password: str
    target_score: int | None = None
    full_knowledge: bool = False
    login_method: str = "easyplu"
    run_id: str | None = None


class OtpRequest(BaseModel):
    run_id: str
    otp: str

def make_otp_callback(run_id: str, progress_queue: Queue | None = None, timeout: int = 150):
    def otp_callback():
        waiter = {"event": Event(), "code": None}
        otp_waiters[run_id] = waiter
        if progress_queue is not None:
            progress_queue.put({
                "stage": "otp_required",
                "progress": 15,
                "message": "Vnesite SMS kodo iz Lidl prijave.",
                "run_id": run_id,
            })
        if not waiter["event"].wait(timeout=timeout):
            otp_waiters.pop(run_id, None)
            raise TimeoutError("Čas za vnos SMS kode je potekel")
        code = waiter["code"]
        otp_waiters.pop(run_id, None)
        if not code:
            raise RuntimeError("SMS koda ni bila poslana")
        return code

    return otp_callback


@app.post("/submit-otp")
def submit_otp(req: OtpRequest):
    waiter = otp_waiters.get(req.run_id)
    if waiter is None:
        raise HTTPException(status_code=404, detail="SSO prijava ne čaka na SMS kodo")
    waiter["code"] = req.otp.strip()
    waiter["event"].set()
    return {"status": "ok"}


@app.post("/run-session")
def run_plu_session(req: SessionRequest):
    try:
        run_id = req.run_id or str(uuid.uuid4())
        otp_callback = make_otp_callback(run_id) if req.login_method == "sso" else None
        result = run_session(
            req.email,
            req.password,
            req.target_score,
            login_method=req.login_method,
            otp_callback=otp_callback,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-session-stream")
async def run_plu_session_stream(req: SessionRequest):
    """Stream solver progress using Server-Sent Events"""
    progress_queue = Queue()
    result_container = {"result": None, "error": None}
    
    def emit_progress(data):
        progress_queue.put(data)
    
    def run_solver():
        try:
            attempt = 0
            max_attempts = 50  # Safety limit to prevent infinite loops
            run_id = req.run_id or str(uuid.uuid4())
            otp_callback = make_otp_callback(run_id, progress_queue) if req.login_method == "sso" else None
            authenticated_user_id = None
            
            while attempt < max_attempts:
                attempt += 1
                progress_queue.put({
                    "stage": "attempt_start",
                    "progress": 0,
                    "message": f"Poskus {attempt}...",
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
                
                progress_queue.put({
                    "stage": "attempt_complete",
                    "progress": 90,
                    "message": f"Poskus {attempt} končan. Znanje: {user_knowledge:.2f}%",
                    "attempt": attempt,
                    "user_knowledge": user_knowledge,
                    "result": result
                })
                
                # If full_knowledge is enabled, check if we need to continue
                if req.full_knowledge:
                    if user_knowledge >= 100.0:
                        progress_queue.put({
                            "stage": "final",
                            "progress": 100,
                            "message": f"Končano! Doseženo 100% znanje po {attempt} poskusih.",
                            "attempt": attempt,
                            "user_knowledge": user_knowledge,
                            "result": result
                        })
                        result_container["result"] = result
                        break
                    else:
                        # Continue to next attempt
                        progress_queue.put({
                            "stage": "retrying",
                            "progress": 95,
                            "message": f"Znanje: {user_knowledge:.2f}% < 100%. Nadaljujem s poskusom {attempt + 1}...",
                            "attempt": attempt,
                            "user_knowledge": user_knowledge
                        })
                        continue
                else:
                    # Not requiring full knowledge, return after first attempt
                    progress_queue.put({
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
                progress_queue.put({
                    "stage": "error",
                    "progress": 0,
                    "message": f"Dosežena največja števila poskusov ({max_attempts}). Znanje: {result.get('user_knowledge', 0):.2f}%",
                    "error": "Max attempts reached"
                })
        except Exception as e:
            result_container["error"] = str(e)
            progress_queue.put({"stage": "error", "progress": 0, "message": str(e), "error": str(e)})
        finally:
            progress_queue.put(None)  # Signal end of stream
    
    # Start solver in background thread
    solver_thread = Thread(target=run_solver, daemon=True)
    solver_thread.start()
    
    async def event_generator():
        try:
            yield ": connected\n\n"
            last_sent = time.monotonic()
            while True:
                try:
                    # Wait for progress update with timeout
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
            yield f"data: {json.dumps({'stage': 'error', 'message': f'Stream error: {str(e)}'})}\n\n"
        finally:
            # Ensure we send a final message to close the stream
            yield f"data: {json.dumps({'stage': 'closed'})}\n\n"
    
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
