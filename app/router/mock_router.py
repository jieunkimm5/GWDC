from app.schemas import RouterResult


def analyze(task: str) -> RouterResult:
    return RouterResult(
        recommended_route="PAID",
        selected_model="paid-model-1",
        reason="Complex reasoning is required.",
        estimated_cost_usd="0.032000"
    )