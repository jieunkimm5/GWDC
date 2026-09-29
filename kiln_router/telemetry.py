"""Append one JSON event per A invocation; independent of C's run_id."""

import json
import os
from pathlib import Path
from threading import Lock

from .errors import RoutingError


class JsonlTelemetry:
    def __init__(self, path: str | Path = "logs/routing.jsonl"):
        self.path = Path(path)
        self._lock = Lock()

    def write(self, event: dict) -> None:
        try:
            line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as handle:
                    handle.write(line)
        except (OSError, TypeError, ValueError):
            raise RoutingError("TELEMETRY_ERROR") from None
