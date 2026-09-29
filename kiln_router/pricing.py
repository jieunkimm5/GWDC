"""Offline estimates for paid execution only; no budget approval or API calls."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, localcontext
from typing import Callable, Mapping

from .errors import RoutingError
from .models import MODELS, KILN_MODEL_ID, OUTPUT_LENGTH_TOKENS, ModelConfig
from .schemas import KilnEvaluationResponse
from .validation import apply_capacity_checks, _execution_limits

MILLION = Decimal("1000000")
USD_UNIT = Decimal("0.000001")
ESTIMATION_VERSION = "utf8-envelope-v1"
# Tie only on unrounded totals; never use Kiln array order as a tiebreaker.
TIE_ORDER = (
    "qwen3:8b", "claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-5-5",
)


@dataclass(frozen=True)
class ExecutionInput:
    """The full text-only request C will send, not the Kiln routing prompt.

    The MVP has a system message and one user task. Tools, images and conversation
    history are unsupported here; adding them requires extending the estimator.
    """

    system_prompt: str
    task: str

    def __post_init__(self):
        if not isinstance(self.system_prompt, str) or not isinstance(self.task, str) or not self.task.strip():
            raise RoutingError("INVALID_INPUT")


@dataclass(frozen=True)
class InputTokenEstimate:
    tokens: int
    method: str

    def __post_init__(self):
        if type(self.tokens) is not int or self.tokens <= 0:
            raise RoutingError("INVALID_TOKEN_COUNT")
        if not isinstance(self.method, str) or not self.method.strip():
            raise RoutingError("INVALID_TOKEN_COUNT")


def estimate_input_tokens(model_id: str, request: ExecutionInput) -> InputTokenEstimate:
    """Conservative heuristic, NOT a model tokenizer or guaranteed upper bound.

    Count UTF-8 bytes plus an explicit assumed chat-envelope allowance (32 for
    the request, 16 per message). Avoid chars/4 undercounting Korean and code.
    Replace via token_counter with model-specific full-request counts when ready.
    """
    if model_id not in MODELS and model_id != KILN_MODEL_ID:
        raise RoutingError("MODEL_CONFIG_ERROR")
    texts = [request.task]
    if request.system_prompt:
        texts.insert(0, request.system_prompt)
    tokens = sum(len(text.encode("utf-8")) for text in texts) + 32 + 16 * len(texts)
    return InputTokenEstimate(tokens=tokens, method=ESTIMATION_VERSION)


def format_usd(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise RoutingError("INVALID_COST")
    with localcontext() as context:
        context.prec = max(50, len(value.as_tuple().digits) + max(value.adjusted(), 0) + 10)
        return format(value.quantize(USD_UNIT, rounding=ROUND_CEILING), ".6f")


def _validate_rates(model: ModelConfig) -> None:
    for rate in (model.input_usd_per_million, model.output_usd_per_million):
        if not isinstance(rate, Decimal) or not rate.is_finite() or rate < 0:
            raise RoutingError("MODEL_CONFIG_ERROR")
        if model.route == "PAID" and rate == 0:
            raise RoutingError("MODEL_CONFIG_ERROR")
        if model.route == "LOCAL" and rate != 0:
            raise RoutingError("MODEL_CONFIG_ERROR")


@dataclass(frozen=True)
class CostEstimate:
    model_id: str
    input_tokens: int
    billable_output_tokens: int
    input_method: str
    output_method: str
    input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    input_rate: Decimal
    output_rate: Decimal
    pricing_verified_on: str

    @property
    def estimated_cost_usd(self) -> str:
        return format_usd(self.total_cost_usd)

    def log_metadata(self) -> dict:
        return {
            "model_id": self.model_id,
            "estimated_input_tokens": self.input_tokens,
            "estimated_billable_output_tokens": self.billable_output_tokens,
            "input_estimation_method": self.input_method,
            "output_estimation_method": self.output_method,
            "input_usd_per_million": str(self.input_rate),
            "output_usd_per_million": str(self.output_rate),
            "input_cost_usd": str(self.input_cost_usd),
            "output_cost_usd": str(self.output_cost_usd),
            "unrounded_cost_usd": str(self.total_cost_usd),
            "estimated_cost_usd": self.estimated_cost_usd,
            "pricing_verified_on": self.pricing_verified_on,
            "scope": "paid_inference_only",
        }


def estimate_model_cost(model: ModelConfig, input_estimate: InputTokenEstimate,
                        output_tokens: int | None = None) -> CostEstimate:
    """Price output_tokens (default: the model's cap), including billable reasoning.

    This is a reserve, not expected average usage or an invoice. C must send
    the same number as the output limit; input estimates still need calibration.
    """
    context_tokens, cap = _execution_limits(model)
    method = "configured_output_cap" if output_tokens is None else "expected_output_length"
    output_tokens = cap if output_tokens is None else output_tokens
    if type(output_tokens) is not int or not 0 < output_tokens <= cap:
        raise RoutingError("INVALID_TOKEN_COUNT")
    if input_estimate.tokens + output_tokens > context_tokens:
        raise RoutingError("INPUT_TOO_LARGE")
    _validate_rates(model)
    with localcontext() as context:
        context.prec = 50
        input_cost = Decimal(input_estimate.tokens) * model.input_usd_per_million / MILLION
        output_cost = Decimal(output_tokens) * model.output_usd_per_million / MILLION
        total = input_cost + output_cost
    return CostEstimate(
        model_id=model.model_id, input_tokens=input_estimate.tokens,
        billable_output_tokens=output_tokens, input_method=input_estimate.method,
        output_method=method,
        input_cost_usd=input_cost, output_cost_usd=output_cost, total_cost_usd=total,
        input_rate=model.input_usd_per_million, output_rate=model.output_usd_per_million,
        pricing_verified_on=model.verified_on,
    )


@dataclass(frozen=True)
class CandidateCosts:
    assessment: KilnEvaluationResponse
    # Cheapest first. Empty means no suitable candidate, never implicit LOCAL.
    ranked_estimates: tuple[CostEstimate, ...]


def estimate_candidate_costs(
    assessment: KilnEvaluationResponse,
    *,
    requests_by_model: Mapping[str, ExecutionInput],
    models: Mapping[str, ModelConfig] = MODELS,
    token_counter: Callable[[str, ExecutionInput], InputTokenEstimate] = estimate_input_tokens,
) -> CandidateCosts:
    """Count each full request, enforce capacity, and price suitable candidates.

    C can use different execution prompts per model. No API calls are made by
    the default estimator; a model tokenizer/count result can be injected.
    """
    if set(models) != set(MODELS) or set(requests_by_model) != set(MODELS):
        raise RoutingError("MODEL_CONFIG_ERROR")
    inputs = {key: token_counter(key, requests_by_model[key]) for key in MODELS}
    if any(not isinstance(item, InputTokenEstimate) for item in inputs.values()):
        raise RoutingError("INVALID_TOKEN_COUNT")
    checked = apply_capacity_checks(
        assessment, input_tokens_by_model={key: value.tokens for key, value in inputs.items()},
        models=models,
    )
    output_tokens = OUTPUT_LENGTH_TOKENS[checked.expected_output_length]
    estimates = [
        estimate_model_cost(models[item.model_id], inputs[item.model_id], output_tokens)
        for item in checked.evaluations if item.suitable
    ]
    estimates.sort(key=lambda item: (item.total_cost_usd, TIE_ORDER.index(item.model_id)))
    return CandidateCosts(assessment=checked, ranked_estimates=tuple(estimates))
