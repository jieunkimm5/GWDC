from blockchain.policy import check_budget
from blockchain.record import record_decision


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str,
) -> dict:
    """
    Paid inference 요청에 대해:

    1. 사용자 budget 검사
    2. budget 부족 → 거절
    3. budget 충분 → on-chain record 생성
    4. blockchain transaction 성공(status == 1)한 경우에만 승인
    """

    # 1. Budget policy 확인
    policy_result = check_budget(
        budget_usd=budget_usd,
        estimated_cost_usd=estimated_cost_usd,
    )

    # 2. Budget 부족
    # Blockchain transaction 자체를 만들지 않음
    if not policy_result["approved"]:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BUDGET_EXCEEDED",
        }

    # 3. Budget 통과 → Blockchain 기록 시도
    try:
        blockchain_result = record_decision(
            run_id=run_id,
            decision=decision,
            approved=True,
            amount=estimated_cost_usd,
            provider=provider,
        )

    # 4. Blockchain 자체가 실패한 경우
    except Exception as e:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 5. 혹시 모를 추가 방어
    if blockchain_result["status"] != 1:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 6. Budget 통과 + Blockchain transaction 성공
    return {
        "approved": True,
        "amount_usd": estimated_cost_usd,
        "tx_hash": blockchain_result["tx_hash"],
    }