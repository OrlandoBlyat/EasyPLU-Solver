from pathlib import Path
import secrets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from backend.infrastructure.lifecycle import lifespan
from backend.infrastructure.body_limit import BodyLimitMiddleware
from backend.infrastructure.logging import log
from backend.infrastructure.errors import client_error
from backend.api import tests, catalog, schedules, health

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

app.add_middleware(BodyLimitMiddleware)

for router in (tests.router, catalog.router, schedules.router, health.router):
    app.include_router(router)
