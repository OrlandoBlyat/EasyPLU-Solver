from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from .identity import run_owner
from .schemas import ScheduleRequest

router = APIRouter()

@router.get("/schedule")
def get_schedule(request: Request):
    from backend.scheduling.service import status
    return status(run_owner(request))


@router.post("/schedule")
def set_schedule(req: ScheduleRequest, request: Request):
    from backend.scheduling.service import update
    try:
        return update(run_owner(request), req.enabled, req.consent)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None


