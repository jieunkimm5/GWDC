from decimal import Decimal, InvalidOperation
from typing import Optional
from pydantic import BaseModel, field_validator


# =========================
# 1. 사용자 -> 우리 Backend
# =========================
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
            raise ValueError("budget_usd must be a valid decimal number.")

        if not budget.is_finite():
            raise ValueError("budget_usd must be finite.")

        if budget < 0:
            raise ValueError("budget_usd cannot be negative.")

        return value

# =========================
# 2. A -> C
# Kiln Router 결과
# =========================
class RouterResult(BaseModel):
    recommended_route: str
    selected_model: str
    reason: str
    estimated_cost_usd: str
    max_output_tokens: int

# =========================
# 3. B -> C
# Blockchain / Payment 결과
# =========================
class PaymentResult(BaseModel):
    approved: bool
    amount_usd: str
    tx_hash: Optional[str] = None


# =========================
# 4. 최종 응답 내부 - decision
# =========================
class DecisionResult(BaseModel):
    recommended_route: str
    actual_route: str
    selected_model: str
    reason: str
    fallback_reason: Optional[str] = None


# =========================
# 5. 최종 응답 내부 - cost
# =========================
class CostResult(BaseModel):
    budget_usd: str
    estimated_cost_usd: str
    actual_cost_usd: str


# =========================
# 6. 최종 응답 내부 - payment
# =========================
class PaymentResponse(BaseModel):
    approved: bool
    tx_hash: Optional[str] = None


# =========================
# 7. 최종 응답 내부 - usage
# =========================
class UsageResult(BaseModel):
    input_tokens: int
    output_tokens: int


# =========================
# 8. 최종 API 응답
# =========================
class RunResponse(BaseModel):
    run_id: str
    status: str
    decision: DecisionResult
    cost: CostResult
    payment: PaymentResponse
    usage: UsageResult
    result: str
    