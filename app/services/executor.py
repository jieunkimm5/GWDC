def run_local(task: str) -> dict:
    return {
        "result": f"[LOCAL MOCK RESULT] {task}",
        "actual_cost_usd": "0.000000",
        "input_tokens": 100,
        "output_tokens": 50
    }


def run_paid(task: str, model: str) -> dict:
    return {
        "result": f"[PAID MOCK RESULT with {model}] {task}",
        "actual_cost_usd": "0.030800",
        "input_tokens": 2200,
        "output_tokens": 900
    }