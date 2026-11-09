from fastapi import APIRouter
from backend.tests_runner.service import submit_otp, run_plu_session, run_plu_session_stream

router = APIRouter()
router.add_api_route("/submit-otp", submit_otp, methods=["POST"])
router.add_api_route("/run-session", run_plu_session, methods=["POST"])
router.add_api_route("/run-session-stream", run_plu_session_stream, methods=["POST"])
