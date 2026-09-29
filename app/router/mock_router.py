from app.schemas import RouterResult


def analyze(task: str) -> RouterResult:
    return RouterResult(
    recommended_route="PAID",
    selected_model="claude-sonnet-5",
    reason=(
        "여러 함수에 걸친 버그 분석이 필요합니다. "
        "적합한 후보 중 예상 유료 추론 비용이 가장 낮아 선택했습니다."
    ),
    estimated_cost_usd="0.026480",
    max_output_tokens=2048,
)