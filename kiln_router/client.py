"""Async Kiln transport. Candidate evaluation belongs to the next stage."""

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import dotenv_values

from .errors import RoutingError
from .models import KILN_MODEL_ID


@dataclass(frozen=True)
class KilnSettings:
    api_key: str = field(repr=False)
    api_url: str = "https://api.bricksum.com/v1"
    timeout_seconds: float = 60.0
    max_tokens: int = 2048

    def __post_init__(self):
        if not self.api_key.strip():
            raise RoutingError("KILN_CONFIG_ERROR")
        url = httpx.URL(self.api_url)
        if (url.scheme != "https" or not url.host or url.userinfo
                or url.query or url.fragment):
            raise RoutingError("KILN_CONFIG_ERROR")
        if not 0 < self.timeout_seconds <= 90 or type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise RoutingError("KILN_CONFIG_ERROR")

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "KilnSettings":
        values = {**dotenv_values(env_file), **os.environ}
        return cls(
            api_key=values.get("KILN_API_KEY") or "",
            api_url=values.get("KILN_API_URL") or "https://api.bricksum.com/v1",
        )


@dataclass(frozen=True)
class KilnResponse:
    content: str = field(repr=False)
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    completion_id: str
    generation_id: str | None
    finish_reason: str
    kiln_cost_usd: str | None
    retry_count: int = 0

    def log_metadata(self) -> dict:
        """Only allowlisted metadata; no prompt, answer, or key."""
        data = asdict(self)
        data.pop("content")
        return {"flow": "kiln_analysis", **data}


class KilnClient:
    """Use with async with. No automatic retries of billable requests."""

    def __init__(self, settings: KilnSettings, *, transport=None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._http.aclose()

    async def complete(self, *, system_prompt: str, task: str) -> KilnResponse:
        if not isinstance(task, str) or not task.strip():
            raise RoutingError("INVALID_INPUT")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise RoutingError("INVALID_INPUT")
        payload = {
            "model": KILN_MODEL_ID,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ],
            "max_tokens": self.settings.max_tokens,
            # Minimize sampling variance so the same task gets the same routing.
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }
        started = perf_counter()
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                response = await self._http.post(
                    self.settings.api_url.rstrip("/") + "/chat/completions",
                    json=payload,
                )
        except (TimeoutError, httpx.TimeoutException):
            raise RoutingError("KILN_TIMEOUT") from None
        except httpx.RequestError:
            raise RoutingError("KILN_NETWORK_ERROR") from None

        latency = round((perf_counter() - started) * 1000, 3)
        if response.status_code != 200:
            code = {
                401: "KILN_AUTH_ERROR", 403: "KILN_AUTH_ERROR",
                402: "KILN_CREDIT_ERROR", 429: "KILN_RATE_LIMIT",
            }.get(response.status_code, "KILN_API_ERROR")
            raise RoutingError(code, status_code=response.status_code)

        try:
            data = json.loads(response.text, parse_float=Decimal)
            choice = data["choices"][0]
            usage = data["usage"]
            counts = [usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")]
            if any(type(count) is not int or count < 0 for count in counts):
                raise ValueError()
            if counts[0] + counts[1] != counts[2]:
                raise ValueError()
            content = choice["message"]["content"]
            finish = choice["finish_reason"]
            if content is not None and not isinstance(content, str):
                raise ValueError()
            if not isinstance(finish, str) or data["model"] != KILN_MODEL_ID:
                raise ValueError()
            if not isinstance(data["id"], str):
                raise ValueError()
            cost = usage.get("cost")
            if cost is not None:
                if type(cost) not in (int, Decimal):
                    raise ValueError()
                cost = Decimal(cost)
                if not cost.is_finite() or cost < 0:
                    raise ValueError()
            result = KilnResponse(
                content=content or "", model=data["model"],
                input_tokens=counts[0], output_tokens=counts[1], total_tokens=counts[2],
                latency_ms=latency, completion_id=data["id"],
                generation_id=response.headers.get("X-Neocloud-Generation-Id"),
                finish_reason=finish,
                kiln_cost_usd=format(cost, "f") if cost is not None else None,
            )
        except (ValueError, KeyError, IndexError, TypeError):
            raise RoutingError("KILN_INVALID_RESPONSE") from None

        if result.finish_reason != "stop" or not result.content.strip():
            raise RoutingError("KILN_INCOMPLETE_RESPONSE", metadata=result.log_metadata())
        return result
