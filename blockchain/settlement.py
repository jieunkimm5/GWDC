from decimal import Decimal


def settle_cost(
    estimated_cost_usd: str,
    actual_cost_usd: str,
) -> dict:
    """
    실제 유료 모델 실행 후 비용을 정산한다.

    정책:
    - 사용자는 사전에 고지된 estimated_cost_usd를 초과해서 부담하지 않는다.
    - 실제 비용이 예상 비용보다 크면 초과분은 플랫폼이 부담한다.
    - 실제 비용이 예상 비용보다 작으면 사용자는 실제 비용만 부담한다.
    """

    estimated_cost = Decimal(estimated_cost_usd)
    actual_cost = Decimal(actual_cost_usd)

    if estimated_cost < 0:
        raise ValueError("estimated_cost_usd cannot be negative")

    if actual_cost < 0:
        raise ValueError("actual_cost_usd cannot be negative")

    # 사용자가 부담하는 금액:
    # 실제 비용과 사전 고지 금액 중 더 작은 금액
    user_charge = min(
        actual_cost,
        estimated_cost,
    )

    # 예상 금액을 초과한 부분은 플랫폼이 부담
    platform_charge = max(
        actual_cost - estimated_cost,
        Decimal("0"),
    )

    return {
        "estimated_cost_usd": format(estimated_cost, ".6f"),
        "actual_cost_usd": format(actual_cost, ".6f"),
        "user_charge_usd": format(user_charge, ".6f"),
        "platform_charge_usd": format(platform_charge, ".6f"),
    }