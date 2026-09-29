from .policy import check_budget
from .record import record_decision
from .settlement import settle_cost


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str,
) -> dict:
    """
    Paid inference authorization.

    1. Check whether the estimated cost fits within the user's budget.
    2. Reject if the budget is insufficient.
    3. If sufficient, record authorization on-chain.
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

    # 3. Record authorization on blockchain
    try:
        blockchain_result = record_decision(
            run_id=run_id,
            decision=decision,
            approved=True,
            amount=estimated_cost_usd,
            provider=provider,
        )

    except Exception as e:
        print("BLOCKCHAIN ERROR:", repr(e))

        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
    }

    # 4. Transaction was mined but failed
    if blockchain_result["status"] != 1:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 5. Authorization succeeded
    return {
        "approved": True,
        "amount_usd": estimated_cost_usd,
        "tx_hash": blockchain_result["tx_hash"],
    }


def settle_payment(
    estimated_cost_usd: str,
    actual_cost_usd: str,
) -> dict:
    """
    Settle the actual cost after paid-model execution.

    The user never pays more than the estimated cost.
    Any amount above the estimated cost is covered by the platform.
    """

    return settle_cost(
        estimated_cost_usd=estimated_cost_usd,
        actual_cost_usd=actual_cost_usd,
    )