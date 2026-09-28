from typing import Optional

from app.schemas import RunResponse


RUN_HISTORY: dict[str, RunResponse] = {}


def save_run(run: RunResponse) -> None:
    RUN_HISTORY[run.run_id] = run


def get_run(run_id: str) -> Optional[RunResponse]:
    return RUN_HISTORY.get(run_id)