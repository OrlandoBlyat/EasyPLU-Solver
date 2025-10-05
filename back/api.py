from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from solver import run_session

app = FastAPI(title="PLU Solver API")

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

@app.post("/run-session")
def run_plu_session(req: SessionRequest):
    try:
        result = run_session(req.email, req.password, req.target_score)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
