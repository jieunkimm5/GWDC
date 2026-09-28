from fastapi import FastAPI, HTTPException

from app.schemas import RunRequest, RunResponse
from app.services.workflow import run_workflow
from app.services.history import get_run


app = FastAPI(
    title="Agent Finance API",
    version="0.1.0"
)


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/api/run", response_model=RunResponse)
def run_agent(request: RunRequest) -> RunResponse:
    return run_workflow(
        task=request.task,
        budget_usd=request.budget_usd
    )


@app.get("/api/runs/{run_id}", response_model=RunResponse)
def get_run_history(run_id: str) -> RunResponse:
    run = get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found"
        )

    return run