from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


# =========================================================
# User → C
# =========================================================

class RunRequest(BaseModel):
    task: str
    budget_usd: str

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Task cannot be empty.")

        if len(value) > 10000:
            raise ValueError("Task is too long.")

        return value

    @field_validator("budget_usd")
    @classmethod
    def validate_budget(cls, value: str) -> str:
        try:
            budget = Decimal(value)
        except InvalidOperation:
            raise ValueError(
                "budget_usd must be a valid decimal number."
            )

        if not budget.is_finite():
            raise ValueError(
                "budget_usd must be finite."
            )

        if budget < 0:
            raise ValueError(
                "budget_usd cannot be negative."
            )

        return value


# =========================================================
# A → C
# =========================================================

class RouterResult(BaseModel):
    recommended_route: Literal["LOCAL", "PAID"]
    selected_model: str
    reason: str
    estimated_cost_usd: str

    # A가 예상 비용을 계산할 때 사용한
    # 실제 최대 출력 token 수
    max_output_tokens: int

    @field_validator("max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(
                "max_output_tokens must be greater than 0."
            )

        return value


# =========================================================
# B → C
# Authorization result
# =========================================================

class PaymentResult(BaseModel):
    approved: bool
    amount_usd: str
    tx_hash: Optional[str] = None
    reason: Optional[str] = None


# =========================================================
# Final decision
# =========================================================

class DecisionResult(BaseModel):
    recommended_route: Literal["LOCAL", "PAID"]
    actual_route: Literal["LOCAL", "PAID"]

    selected_model: str
    reason: str

    fallback_reason: Optional[str] = None


# =========================================================
# Final cost information
# =========================================================

class CostResult(BaseModel):
    # 사용자가 허용한 최대 예산
    budget_usd: str

    # A가 실행 전에 예상한 비용
    estimated_cost_usd: str

    # 실제 모델 실행 후 발생한 비용
    actual_cost_usd: str

    # 실제로 사용자에게 부담시키는 금액
    #
    # 새 정책:
    # 사용자는 estimated_cost_usd를 초과해서
    # 부담하지 않는다.
    user_charge_usd: str

    # actual cost가 estimated cost를 초과했을 경우
    # 서비스가 대신 부담하는 금액
    platform_charge_usd: str


# =========================================================
# Final payment information
# =========================================================

class PaymentResponse(BaseModel):
    approved: bool
    tx_hash: Optional[str] = None


# =========================================================
# Model token usage
# =========================================================

class UsageResult(BaseModel):
    input_tokens: int
    output_tokens: int


# =========================================================
# Final API Response
# =========================================================

class RunResponse(BaseModel):
    run_id: str
    status: str

    decision: DecisionResult
    cost: CostResult
    payment: PaymentResponse
    usage: UsageResult

    result: str