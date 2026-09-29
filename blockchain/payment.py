from .policy import check_budget
from .record import record_decision


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str,
) -> dict:
    """
    Paid inference authorization.

    1. Check user budget.
    2. Reject if budget is insufficient.
    3. If budget is sufficient, record the decision on-chain.
    4. Approve only when the blockchain transaction succeeds.
    """

    # 1. Check budget
    policy_result = check_budget(
        budget_usd=budget_usd,
        estimated_cost_usd=estimated_cost_usd,
    )

    # 2. Insufficient budget -> no blockchain transaction
    if not policy_result["approved"]:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BUDGET_EXCEEDED",
        }

    # 3. Attempt blockchain transaction
    try:
        blockchain_result = record_decision(
            run_id=run_id,
            decision=decision,
            approved=True,
            amount=estimated_cost_usd,
            provider=provider,
        )

    # 4. Blockchain error -> reject paid execution
    except Exception:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 5. Transaction was mined but failed
    if blockchain_result["status"] != 1:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 6. Budget passed + blockchain transaction succeeded
    return {
        "approved": True,
        "amount_usd": estimated_cost_usd,
        "tx_hash": blockchain_result["tx_hash"],
    }