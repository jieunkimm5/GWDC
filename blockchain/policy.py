from decimal import Decimal


def check_budget(budget_usd: str, estimated_cost_usd: str) -> dict:
    budget = Decimal(budget_usd)
    cost = Decimal(estimated_cost_usd)

    if cost <= budget:
        return {
            "approved": True,
            "amount_usd": estimated_cost_usd,
            "reason": "WITHIN_BUDGET",
        }

    return {
        "approved": False,
        "amount_usd": estimated_cost_usd,
        "reason": "BUDGET_EXCEEDED",
    }