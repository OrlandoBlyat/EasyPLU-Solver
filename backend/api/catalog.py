from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.requests import Request
from threading import Event
import time
from backend.infrastructure.limits import pdf_limiter, client_ip
from backend.infrastructure.jobs import job_scope, MAX_JOB_SECONDS

router = APIRouter()

@router.get("/catalog-pdf")
def download_catalog(request: Request):
    release = pdf_limiter.acquire(client_ip(request))
    try:
        from backend.catalog.service import export_catalog
        with job_scope(Event(), time.monotonic() + MAX_JOB_SECONDS):
            content = export_catalog()
        return Response(content, media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="plu-catalog.pdf"',
            "Cache-Control": "no-store",
        })
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    finally:
        release()


