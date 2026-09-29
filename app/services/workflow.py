import uuid 


from app.schemas import (
    RunResponse,
    DecisionResult,
    CostResult,
    PaymentResponse,
    UsageResult,
    PaymentResult,
)

from app.router.mock_router import analyze
from blockchain.payment import authorize
from app.services.executor import run_local, run_paid
from app.services.history import save_run


def run_workflow(task: str, budget_usd: str) -> RunResponse:
    # 1. 실행마다 고유한 run_id 생성
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # 2. A에게는 task만 전달
    # budget은 A에게 전달하지 않음
    router_result = analyze(task)

    recommended_route = router_result.recommended_route

    payment_approved = False
    tx_hash = None
    fallback_reason = None

    # 3. A가 LOCAL을 추천한 경우
    if recommended_route == "LOCAL":
        execution = run_local(task)

        actual_route = "LOCAL"
        final_selected_model = router_result.selected_model

    # 4. A가 PAID를 추천한 경우
    elif recommended_route == "PAID":

        # C가 가지고 있던 budget과
        # A가 계산한 예상 비용을 B에게 전달
        raw_payment_result = authorize(
            run_id=run_id,
            decision=router_result.recommended_route,
            provider=router_result.selected_model,
            budget_usd=budget_usd,
            estimated_cost_usd=router_result.estimated_cost_usd,
        )

        payment_result = PaymentResult(**raw_payment_result)

        payment_approved = payment_result.approved
        tx_hash = payment_result.tx_hash

        # 5. B가 승인했을 때만 PAID 실행
        if payment_result.approved:
            execution = run_paid(
                task,
                router_result.selected_model,
            )

            actual_route = "PAID"
            final_selected_model = router_result.selected_model

        # 6. B가 거부하면 LOCAL fallback
        else:
            execution = run_local(task)

            actual_route = "LOCAL"
            final_selected_model = "local-model-1"
            fallback_reason = "BUDGET_EXCEEDED"

    else:
        raise ValueError(
            f"Unknown recommended_route: {recommended_route}"
        )

    # 7. 최종 응답 생성
    response = RunResponse(
        run_id=run_id,
        status="SUCCESS",

        decision=DecisionResult(
            recommended_route=recommended_route,
            actual_route=actual_route,
            selected_model=final_selected_model,
            reason=router_result.reason,
            fallback_reason=fallback_reason,
        ),

        cost=CostResult(
            budget_usd=budget_usd,
            estimated_cost_usd=router_result.estimated_cost_usd,
            actual_cost_usd=execution["actual_cost_usd"],
        ),

        payment=PaymentResponse(
            approved=payment_approved,
            tx_hash=tx_hash,
        ),

        usage=UsageResult(
            input_tokens=execution["input_tokens"],
            output_tokens=execution["output_tokens"],
        ),

        result=execution["result"],
    )
    save_run(response)
    return response