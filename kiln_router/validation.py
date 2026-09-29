"""Parse assessments and enforce capacity independently of model opinions."""

import json
import re
from typing import Mapping

from pydantic import ValidationError

from .errors import RoutingError
from .models import MODELS, KILN_CONTEXT_TOKENS, OUTPUT_LENGTH_TOKENS, ModelConfig
from .schemas import CandidateEvaluation, KilnEvaluationResponse


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonstandard JSON constant")


def parse_evaluations(content: str) -> KilnEvaluationResponse:
    """Unwrap one complete JSON fence, then strictly validate unchanged data."""
    if not isinstance(content, str) or not content.strip():
        raise RoutingError("INVALID_MODEL_RESPONSE")
    wrapped = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", content.strip(), re.DOTALL)
    if wrapped:
        content = wrapped.group(1)
    try:
        data = json.loads(content, object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        return KilnEvaluationResponse.model_validate(data)
    except (ValueError, TypeError, RecursionError, ValidationError):
        # Pydantic errors can include task/model text, so expose only a safe code.
        raise RoutingError("INVALID_MODEL_RESPONSE") from None


def fits_context(*, input_tokens: int, reserved_output_tokens: int,
                 context_tokens: int) -> bool:
    """Counts must include the full execution request, not just raw task text."""
    for value in (input_tokens, reserved_output_tokens, context_tokens):
        if type(value) is not int:
            raise RoutingError("INVALID_TOKEN_COUNT")
    if input_tokens < 0 or reserved_output_tokens <= 0 or context_tokens <= 0:
        raise RoutingError("INVALID_TOKEN_COUNT")
    return input_tokens + reserved_output_tokens <= context_tokens


def check_kiln_capacity(*, input_tokens: int, max_tokens: int) -> None:
    """Use before the API call, once a full-prompt token count is available."""
    if not fits_context(input_tokens=input_tokens, reserved_output_tokens=max_tokens,
                        context_tokens=KILN_CONTEXT_TOKENS):
        raise RoutingError("INPUT_TOO_LARGE")


def _execution_limits(model: ModelConfig) -> tuple[int, int]:
    context = model.execution_context_tokens
    output = model.execution_max_output_tokens
    if (type(context) is not int or type(output) is not int
            or context <= 0 or output <= 0 or output > context):
        raise RoutingError("MODEL_CONFIG_ERROR")
    if (model.published_context_tokens is not None
            and context > model.published_context_tokens):
        raise RoutingError("MODEL_CONFIG_ERROR")
    if (model.published_max_output_tokens is not None
            and output > model.published_max_output_tokens):
        raise RoutingError("MODEL_CONFIG_ERROR")
    return context, output


def apply_capacity_checks(
    assessment: KilnEvaluationResponse,
    *,
    input_tokens_by_model: Mapping[str, int],
    models: Mapping[str, ModelConfig] = MODELS,
) -> KilnEvaluationResponse:
    """Return a new assessment; never promote an AI-rejected candidate.

    Reserve the output tokens for Kiln's expected answer length. A model whose
    output cap is below that reserve, or whose context cannot hold input plus
    reserve, becomes unsuitable. Missing counts/settings are errors, not zero
    tokens or unlimited capacity.
    """
    if set(models) != set(MODELS):
        raise RoutingError("MODEL_CONFIG_ERROR")
    if set(input_tokens_by_model) != set(MODELS):
        raise RoutingError("INVALID_TOKEN_COUNT")
    # Revalidate at the boundary in case a nested list was changed after construction.
    try:
        assessment = KilnEvaluationResponse.model_validate(assessment.model_dump())
    except ValidationError:
        raise RoutingError("INVALID_MODEL_RESPONSE") from None
    reserved = OUTPUT_LENGTH_TOKENS[assessment.expected_output_length]
    checked = []
    for item in assessment.evaluations:
        model = models[item.model_id]
        if model.model_id != item.model_id:
            raise RoutingError("MODEL_CONFIG_ERROR")
        context, output = _execution_limits(model)
        fits = fits_context(input_tokens=input_tokens_by_model[item.model_id],
                            reserved_output_tokens=reserved, context_tokens=context)
        if reserved > output:
            note = "예상 답변 길이가 이 모델의 실행 출력 한도를 초과합니다. "
        elif not fits:
            note = "입력과 예상 출력 토큰 합계가 설정된 실행 컨텍스트 한도를 초과합니다. "
        else:
            note = ""
        checked.append(CandidateEvaluation(
            model_id=item.model_id,
            suitable=item.suitable and not note,
            reason=note + item.reason,
        ))
    return KilnEvaluationResponse(
        expected_output_length=assessment.expected_output_length, evaluations=checked,
    )
