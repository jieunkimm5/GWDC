from blockchain.policy import check_budget
from blockchain.record import record_decision
from blockchain.settlement import settle_cost


def authorize(
    run_id: str,
    decision: str,
    provider: str,
    budget_usd: str,
    estimated_cost_usd: str,
) -> dict:
    """
    유료 모델 실행 전 사전 승인 단계.

    1. 예상 비용이 사용자 budget 안에 있는지 검사
    2. budget 부족 → 거절
    3. budget 충분 → blockchain 승인 기록 생성
    4. blockchain transaction 성공(status == 1) 시에만 승인
    """

    # 1. 사용자 budget 검사
    policy_result = check_budget(
        budget_usd=budget_usd,
        estimated_cost_usd=estimated_cost_usd,
    )

    # 2. Budget 부족
    if not policy_result["approved"]:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BUDGET_EXCEEDED",
        }

    # 3. Budget 통과 → Blockchain에 사전 승인 기록
    try:
        blockchain_result = record_decision(
            run_id=run_id,
            decision=decision,
            approved=True,
            amount=estimated_cost_usd,
            provider=provider,
        )

    except Exception:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 4. Transaction 성공 여부 확인
    if blockchain_result["status"] != 1:
        return {
            "approved": False,
            "amount_usd": estimated_cost_usd,
            "tx_hash": None,
            "reason": "BLOCKCHAIN_FAILED",
        }

    # 5. 사전 승인 성공
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
    유료 모델 실행이 끝난 뒤 실제 비용을 기준으로 정산한다.

    사용자는 사전에 고지된 예상 금액 이상을 부담하지 않는다.
    예상 비용을 초과한 금액은 플랫폼이 부담한다.
    """

    return settle_cost(
        estimated_cost_usd=estimated_cost_usd,
        actual_cost_usd=actual_cost_usd,
    )