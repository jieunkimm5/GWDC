from policy import check_budget
from record import record_decision


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str,
):

    policy_result = check_budget(
        budget_usd=budget_usd,
        estimated_cost_usd=estimated_cost_usd,
    )


    # Budget 초과
    if not policy_result["approved"]:

        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
        }


    # Budget 통과 → on-chain 기록
    blockchain_result = record_decision(
        run_id=run_id,
        decision=decision,
        approved=True,
        amount=estimated_cost_usd,
        provider=provider,
    )


    return {
        "approved": True,
        "amount_usd": estimated_cost_usd,
        "tx_hash": blockchain_result["tx_hash"],
    }