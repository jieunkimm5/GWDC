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
from blockchain.payment import authorize, settle_payment
from app.services.executor import run_local, run_paid
from app.services.history import save_run


# =========================================================
# Allowed execution models
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
    # 1. Generate unique run ID
    # -----------------------------------------------------

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # -----------------------------------------------------
    # 2. Ask A for routing decision
    # -----------------------------------------------------

    router_result = analyze(task)

    recommended_route = router_result.recommended_route
    recommended_model = router_result.selected_model
    estimated_cost_usd = router_result.estimated_cost_usd
    max_output_tokens = router_result.max_output_tokens

    # -----------------------------------------------------
    # 3. Security: model allowlist
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
    # Default values
    # -----------------------------------------------------

    payment_approved = False
    tx_hash = None
    fallback_reason = None

    user_charge_usd = "0.000000"
    platform_charge_usd = "0.000000"


    # =====================================================
    # CASE 1
    # A recommends LOCAL
    # =====================================================

    if recommended_route == "LOCAL":

        execution = run_local(
            task=task,
            max_output_tokens=max_output_tokens,
        )

        actual_route = "LOCAL"
        final_selected_model = recommended_model

        # Local execution costs the user/platform $0
        user_charge_usd = "0.000000"
        platform_charge_usd = "0.000000"


    # =====================================================
    # CASE 2
    # A recommends PAID
    # =====================================================

    else:

        # -------------------------------------------------
        # 4. Pre-execution authorization
        #
        # estimated_cost <= user budget ?
        # -------------------------------------------------

        raw_payment_result = authorize(
            run_id=run_id,
            decision=recommended_route,
            provider=recommended_model,
            budget_usd=budget_usd,
            estimated_cost_usd=estimated_cost_usd,
        )

        payment_result = PaymentResult(**raw_payment_result)

        payment_approved = payment_result.approved
        tx_hash = payment_result.tx_hash
        payment_reason = payment_result.reason


        # =================================================
        # CASE 2-A
        # Budget sufficient + blockchain authorization OK
        # =================================================

        if payment_result.approved:

            try:
                # -----------------------------------------
                # 5. Execute the paid model
                # -----------------------------------------

                execution = run_paid(
                    task=task,
                    model=recommended_model,
                    max_output_tokens=max_output_tokens,
                )

                actual_route = "PAID"
                final_selected_model = recommended_model


                # -----------------------------------------
                # 6. Post-execution settlement
                #
                # User never pays more than estimated cost.
                # Excess actual cost is paid by platform.
                # -----------------------------------------

                settlement = settle_payment(
                    estimated_cost_usd=estimated_cost_usd,
                    actual_cost_usd=execution["actual_cost_usd"],
                )

                user_charge_usd = settlement[
                    "user_charge_usd"
                ]

                platform_charge_usd = settlement[
                    "platform_charge_usd"
                ]


            # =============================================
            # Paid API failed after authorization
            # -> LOCAL fallback
            # =============================================

            except Exception:

                local_execution = run_local(
                    task=task,
                    max_output_tokens=max_output_tokens,
                )

                actual_route = "LOCAL"
                final_selected_model = FALLBACK_LOCAL_MODEL
                fallback_reason = "PAID_API_FAILED"

                # 실제 paid-model 비용을 확정할 수 없으므로
                # 현재 응답에서는 사용자/플랫폼 charge를 0으로 둔다.
                user_charge_usd = "0.000000"
                platform_charge_usd = "0.000000"

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
        # Authorization rejected
        # =================================================

        else:

            actual_route = "LOCAL"
            final_selected_model = FALLBACK_LOCAL_MODEL

            local_execution = run_local(
                task=task,
                max_output_tokens=max_output_tokens,
            )

            # No paid model was executed
            user_charge_usd = "0.000000"
            platform_charge_usd = "0.000000"


            # ---------------------------------------------
            # Insufficient budget
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
            # Blockchain authorization failed
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
            # Unknown rejection
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
    # 7. Build final response
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
            user_charge_usd=user_charge_usd,
            platform_charge_usd=platform_charge_usd,
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