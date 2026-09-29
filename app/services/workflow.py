import uuid

from app.schemas import (
    RunResponse,
    DecisionResult,
    CostResult,
    PaymentResponse,
    UsageResult,
    PaymentResult,
)

from app.router.kiln_router import analyze
from blockchain.payment import authorize
from app.services.executor import run_local, run_paid
from app.services.history import save_run


# =========================================================
# 허용된 실제 실행 모델
# =========================================================

ALLOWED_PAID_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-5-5",
}

ALLOWED_LOCAL_MODELS = {
    "qwen3:8b",
}

FALLBACK_LOCAL_MODEL = "qwen3:8b"


# =========================================================
# Main Workflow
# =========================================================

def run_workflow(task: str, budget_usd: str) -> RunResponse:

    # -----------------------------------------------------
    # 1. 실행 ID 생성
    # -----------------------------------------------------

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # -----------------------------------------------------
    # 2. A에게 task 전달
    #
    # A는 예산을 보지 않고
    # task에 적절한 모델과 예상 비용만 결정한다.
    # -----------------------------------------------------

    router_result = analyze(task)

    recommended_route = router_result.recommended_route
    recommended_model = router_result.selected_model
    estimated_cost_usd = router_result.estimated_cost_usd
    max_output_tokens = router_result.max_output_tokens

    # -----------------------------------------------------
    # 3. 보안: A가 반환한 모델 검증
    # -----------------------------------------------------

    if recommended_route == "PAID":

        if recommended_model not in ALLOWED_PAID_MODELS:
            raise ValueError(
                f"Unauthorized paid model: {recommended_model}"
            )

    elif recommended_route == "LOCAL":

        if recommended_model not in ALLOWED_LOCAL_MODELS:
            raise ValueError(
                f"Unauthorized local model: {recommended_model}"
            )

    else:
        raise ValueError(
            f"Unknown recommended_route: {recommended_route}"
        )

    # -----------------------------------------------------
    # 기본 payment 상태
    # -----------------------------------------------------

    payment_approved = False
    tx_hash = None
    fallback_reason = None


    # =====================================================
    # CASE 1
    # A가 처음부터 LOCAL을 추천
    # =====================================================

    if recommended_route == "LOCAL":

        execution = run_local(task, max_output_tokens=max_output_tokens,)

        actual_route = "LOCAL"
        final_selected_model = recommended_model


    # =====================================================
    # CASE 2
    # A가 PAID 모델을 추천
    # =====================================================

    else:

        # -------------------------------------------------
        # 4. B에게 예산 검증 + blockchain 승인 요청
        # -------------------------------------------------

        raw_payment_result = authorize(
            run_id=run_id,
            decision=router_result.recommended_route,
            provider=recommended_model,
            budget_usd=budget_usd,
            estimated_cost_usd=estimated_cost_usd,
        )

        # B가 추가로 reason을 반환하므로 따로 보관
        payment_reason = raw_payment_result.get("reason")

        # 우리가 정한 PaymentResult 형식만 추출
        payment_result = PaymentResult(
            approved=raw_payment_result["approved"],
            amount_usd=raw_payment_result["amount_usd"],
            tx_hash=raw_payment_result.get("tx_hash"),
        )

        payment_approved = payment_result.approved
        tx_hash = payment_result.tx_hash


        # =================================================
        # CASE 2-A
        # 예산 충분 + blockchain 성공
        # → 추천된 PAID 모델 실제 실행
        # =================================================

        if payment_result.approved:

            try:
                execution = run_paid(
                    task=task,
                    model=recommended_model,
                    max_output_tokens=max_output_tokens,
                )

                actual_route = "PAID"
                final_selected_model = recommended_model

            # ---------------------------------------------
            # PAID API 자체가 실패한 경우
            # LOCAL fallback
            # ---------------------------------------------

            except Exception as e:

                local_execution = run_local(task, max_output_tokens=max_output_tokens,)

                actual_route = "LOCAL"
                final_selected_model = FALLBACK_LOCAL_MODEL
                fallback_reason = "PAID_API_FAILED"

                execution = {
                    "result": (
                        "The paid model was authorized, but the model API "
                        "failed during execution.\n\n"
                        f"Requested paid model: {recommended_model}\n\n"
                        "The request was therefore executed with the local "
                        f"model ({FALLBACK_LOCAL_MODEL}).\n\n"
                        "Local model result:\n"
                        f"{local_execution['result']}"
                    ),
                    "actual_cost_usd": local_execution[
                        "actual_cost_usd"
                    ],
                    "input_tokens": local_execution[
                        "input_tokens"
                    ],
                    "output_tokens": local_execution[
                        "output_tokens"
                    ],
                }


        # =================================================
        # CASE 2-B
        # B가 거부
        # =================================================

        else:

            actual_route = "LOCAL"
            final_selected_model = FALLBACK_LOCAL_MODEL

            local_execution = run_local(task, max_output_tokens=max_output_tokens,)

            # ---------------------------------------------
            # 예산 부족
            # ---------------------------------------------

            if payment_reason == "BUDGET_EXCEEDED":

                fallback_reason = "BUDGET_EXCEEDED"

                result_message = (
                    "The paid model could not be executed because "
                    "your budget was insufficient.\n\n"
                    f"Recommended paid model: {recommended_model}\n"
                    f"Your budget: ${budget_usd}\n"
                    f"Required estimated budget: "
                    f"${estimated_cost_usd}\n\n"
                    f"The task was executed with the local model "
                    f"({FALLBACK_LOCAL_MODEL}) instead.\n\n"
                    "Local model result:\n"
                    f"{local_execution['result']}"
                )

            # ---------------------------------------------
            # Blockchain 실패
            # ---------------------------------------------

            elif payment_reason == "BLOCKCHAIN_FAILED":

                fallback_reason = "BLOCKCHAIN_FAILED"

                result_message = (
                    "The paid model could not be executed because "
                    "blockchain authorization failed.\n\n"
                    f"Recommended paid model: {recommended_model}\n"
                    f"Estimated cost: ${estimated_cost_usd}\n\n"
                    f"The task was executed with the local model "
                    f"({FALLBACK_LOCAL_MODEL}) instead.\n\n"
                    "Local model result:\n"
                    f"{local_execution['result']}"
                )

            # ---------------------------------------------
            # 알 수 없는 승인 실패
            # ---------------------------------------------

            else:

                fallback_reason = (
                    payment_reason
                    or "PAYMENT_REJECTED"
                )

                result_message = (
                    "Paid execution was not authorized.\n\n"
                    f"Recommended paid model: {recommended_model}\n"
                    f"Estimated cost: ${estimated_cost_usd}\n\n"
                    f"The task was executed with the local model "
                    f"({FALLBACK_LOCAL_MODEL}) instead.\n\n"
                    "Local model result:\n"
                    f"{local_execution['result']}"
                )

            execution = {
                "result": result_message,
                "actual_cost_usd": local_execution[
                    "actual_cost_usd"
                ],
                "input_tokens": local_execution[
                    "input_tokens"
                ],
                "output_tokens": local_execution[
                    "output_tokens"
                ],
            }


    # =====================================================
    # 5. 최종 API 응답
    # =====================================================

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
            estimated_cost_usd=estimated_cost_usd,
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