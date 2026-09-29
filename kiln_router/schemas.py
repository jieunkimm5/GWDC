"""Strict contracts for C -> A, Kiln -> A, and A -> C."""

import re

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import MODELS, ModelId, OutputLength, Route


class ContractModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class RoutingRequest(ContractModel):
    """C passes only task; preserve whitespace inside source code."""

    task: str

    @field_validator("task")
    @classmethod
    def require_task(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task must not be blank")
        return value


class CandidateEvaluation(ContractModel):
    model_id: ModelId
    suitable: bool
    reason: str

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


class KilnEvaluationResponse(ContractModel):
    """Internal response, not the response returned to C."""

    expected_output_length: OutputLength
    evaluations: list[CandidateEvaluation]

    @model_validator(mode="after")
    def require_all_candidates(self) -> "KilnEvaluationResponse":
        ids = [item.model_id for item in self.evaluations]
        if len(ids) != len(MODELS) or set(ids) != set(MODELS):
            raise ValueError("each registered candidate must appear exactly once")
        return self


class RoutingDecision(ContractModel):
    """Exactly the agreed output fields. No execution or budget decision.

    C must call selected_model with max_output_tokens as its output limit;
    estimated_cost_usd reserves exactly that many output tokens.
    """

    recommended_route: Route
    selected_model: ModelId
    reason: str
    estimated_cost_usd: str
    max_output_tokens: int

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value

    @field_validator("estimated_cost_usd")
    @classmethod
    def require_usd_string(cls, value: str) -> str:
        if re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{6}", value) is None:
            raise ValueError("cost must be a nonnegative USD string with six decimals")
        return value

    @field_validator("max_output_tokens")
    @classmethod
    def require_positive_tokens(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_output_tokens must be positive")
        return value

    @model_validator(mode="after")
    def require_consistent_route(self) -> "RoutingDecision":
        if MODELS[self.selected_model].route != self.recommended_route:
            raise ValueError("selected_model must match recommended_route")
        if self.recommended_route == "LOCAL" and self.estimated_cost_usd != "0.000000":
            raise ValueError("LOCAL must have zero paid inference cost")
        return self
