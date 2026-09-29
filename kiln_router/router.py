"""Task-only routing entry point; no budget approval, payment or execution."""

import asyncio
import warnings
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable, Mapping
from uuid import uuid4

from .client import KilnClient
from .errors import RoutingError
from .models import MODELS, KILN_MODEL_ID, ModelConfig
from .pricing import (
    ExecutionInput, InputTokenEstimate, estimate_input_tokens,
    estimate_candidate_costs, _validate_rates,
)
from .prompts import PROMPT_VERSION, build_analysis_prompt
from .schemas import RoutingDecision
from .telemetry import JsonlTelemetry
from .validation import _execution_limits, check_kiln_capacity, parse_evaluations


class KilnRouter:
    """Configure once in C; each request supplies only task.

    C owns the client's async context/lifetime. By default C sends the task alone
    (no system prompt) with the limits in MODELS; pass overrides only if C does not.
    """

    def __init__(
        self, client: KilnClient, *, execution_prompts: Mapping[str, str] | None = None,
        models: Mapping[str, ModelConfig] = MODELS,
        telemetry: JsonlTelemetry | None = None,
        token_counter: Callable[[str, ExecutionInput], InputTokenEstimate] = estimate_input_tokens,
    ):
        self.client = client
        self.models = dict(models)
        self.execution_prompts = (dict(execution_prompts) if execution_prompts is not None
                                  else {key: "" for key in MODELS})
        self.telemetry = telemetry if telemetry is not None else JsonlTelemetry()
        self.token_counter = token_counter

    def _check_settings(self):
        if set(self.models) != set(MODELS) or set(self.execution_prompts) != set(MODELS):
            raise RoutingError("MODEL_CONFIG_ERROR")
        for key, model in self.models.items():
            if (model.model_id != key or model.route != MODELS[key].route
                    or model.provider != MODELS[key].provider
                    or not isinstance(self.execution_prompts[key], str)):
                raise RoutingError("MODEL_CONFIG_ERROR")
            _execution_limits(model)
            _validate_rates(model)

    def _count(self, model_id: str, request: ExecutionInput) -> InputTokenEstimate:
        estimate = self.token_counter(model_id, request)
        if not isinstance(estimate, InputTokenEstimate):
            raise RoutingError("INVALID_TOKEN_COUNT")
        return estimate

    async def recommend_route(self, task: str) -> RoutingDecision:
        started = perf_counter()
        event = {
            "analysis_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "flow": "kiln_analysis",
            "prompt_version": PROMPT_VERSION,
            "analysis_model": KILN_MODEL_ID,
            "stage": "input_validation",
            "api_attempted": False,
            "kiln_usage": None,
            "retry_count": 0,
        }
        result = None
        error = None
        cancelled = False
        try:
            prompt = build_analysis_prompt(task)
            event["stage"] = "configuration"
            self._check_settings()
            event["stage"] = "token_estimation"
            analysis_count = self._count(
                KILN_MODEL_ID, ExecutionInput(prompt.system_prompt, prompt.task),
            )
            event["analysis_input_estimate"] = {
                "tokens": analysis_count.tokens, "method": analysis_count.method,
            }
            check_kiln_capacity(input_tokens=analysis_count.tokens,
                                max_tokens=self.client.settings.max_tokens)
            requests = {key: ExecutionInput(self.execution_prompts[key], task) for key in self.models}
            counts = {key: self._count(key, request) for key, request in requests.items()}
            event["execution_settings"] = {
                key: {"context_tokens": model.execution_context_tokens,
                      "max_output_tokens": model.execution_max_output_tokens,
                      "estimated_input_tokens": counts[key].tokens,
                      "input_method": counts[key].method}
                for key, model in self.models.items()
            }

            event["stage"] = "kiln_call"
            event["api_attempted"] = True
            response = await self.client.complete(system_prompt=prompt.system_prompt, task=prompt.task)
            event["kiln_usage"] = response.log_metadata()
            event["stage"] = "response_validation"
            assessment = parse_evaluations(response.content)
            event["raw_assessment"] = assessment.model_dump()
            event["expected_output_length"] = assessment.expected_output_length
            event["stage"] = "cost_comparison"
            costs = estimate_candidate_costs(
                assessment, requests_by_model=requests, models=self.models,
                token_counter=lambda key, request: counts[key],
            )
            event["checked_assessment"] = costs.assessment.model_dump()
            event["cost_estimates"] = [item.log_metadata() for item in costs.ranked_estimates]
            if not costs.ranked_estimates:
                raise RoutingError("NO_SUITABLE_MODEL")
            best = costs.ranked_estimates[0]
            selected = next(item for item in costs.assessment.evaluations if item.model_id == best.model_id)
            route = self.models[best.model_id].route
            reason = selected.reason + (
                " 로컬 후보가 적합하여 유료 추론 비용 없이 처리하도록 추천합니다."
                if route == "LOCAL" else
                " 적합한 후보 중 예상 유료 추론 비용이 가장 낮아 선택했습니다."
            )
            result = RoutingDecision(
                recommended_route=route, selected_model=best.model_id,
                reason=reason, estimated_cost_usd=best.estimated_cost_usd,
                max_output_tokens=best.billable_output_tokens,
            )
            event.update(status="SUCCESS", stage="complete", decision=result.model_dump())
        except RoutingError as exc:
            error = exc
            event.update(status="ERROR", error_code=exc.code, http_status=exc.status_code)
            if exc.code == "KILN_INCOMPLETE_RESPONSE":
                event["kiln_usage"] = exc.metadata
        except asyncio.CancelledError:
            cancelled = True
            event.update(status="CANCELLED", error_code="ROUTING_CANCELLED")
        except Exception:
            # Avoid surfacing raw provider responses or request text through exceptions.
            error = RoutingError("ROUTING_INTERNAL_ERROR")
            event.update(status="ERROR", error_code=error.code)

        event["total_latency_ms"] = round((perf_counter() - started) * 1000, 3)
        # Model-generated reasons may quote task data. Redact the configured key
        # defensively; no request or raw response body is added to events.
        def redact(value):
            if isinstance(value, str):
                return value.replace(self.client.settings.api_key, "[REDACTED]")
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            return value
        try:
            self.telemetry.write(redact(event))
        except Exception:
            if error is None and not cancelled:
                raise RoutingError("TELEMETRY_ERROR") from None
            warnings.warn("Routing log write failed; original routing error preserved.", RuntimeWarning)
        if cancelled:
            raise asyncio.CancelledError()
        if error is not None:
            raise error from None
        return result
