from decimal import Decimal

from app.schemas import PaymentResult


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str
) -> PaymentResult:

    budget = Decimal(budget_usd)
    estimated_cost = Decimal(estimated_cost_usd)

    if estimated_cost <= budget:
        return PaymentResult(
            approved=True,
            amount_usd=estimated_cost_usd,
            tx_hash=f"0xMOCK_{run_id}"
        )

    return PaymentResult(
        approved=False,
        amount_usd="0.000000",
        tx_hash=None
    )