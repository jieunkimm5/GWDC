"""Explicit, billable connectivity check: python -m kiln_router.smoke."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from .client import KilnClient, KilnSettings
from .errors import RoutingError


async def check() -> int:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "flow": "kiln_smoke"}
    try:
        async with KilnClient(KilnSettings.from_env()) as client:
            result = await client.complete(
                system_prompt="Answer briefly.", task="Reply with the word OK."
            )
        record.update(result.log_metadata())
        record.update(flow="kiln_smoke", status="SUCCESS")
        print("Kiln API call succeeded.")
        exit_code = 0
    except RoutingError as error:
        record.update(error.metadata)
        record.update(flow="kiln_smoke", status="ERROR", error_code=error.code,
                      http_status=error.status_code)
        print(f"Kiln check failed: {error.code}")
        exit_code = 1
    Path("logs").mkdir(exist_ok=True)
    with Path("logs/kiln_smoke.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print("Metadata saved to logs/kiln_smoke.jsonl (no key or response text).")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
