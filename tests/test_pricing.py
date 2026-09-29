import unittest
from dataclasses import replace
from decimal import Decimal

from kiln_router.errors import RoutingError
from kiln_router.models import MODELS
from kiln_router.pricing import (
    ExecutionInput, InputTokenEstimate, estimate_input_tokens,
    estimate_model_cost, estimate_candidate_costs, format_usd,
)
from kiln_router.schemas import CandidateEvaluation, KilnEvaluationResponse


class PricingTests(unittest.TestCase):
    def models(self):
        return {key: replace(value, execution_context_tokens=8192,
                             execution_max_output_tokens=1000)
                for key, value in MODELS.items()}

    def assessment(self, suitable=None, length="short"):
        suitable = set(MODELS) if suitable is None else suitable
        return KilnEvaluationResponse(expected_output_length=length, evaluations=[
            CandidateEvaluation(model_id=key, suitable=key in suitable, reason="Test assessment")
            for key in MODELS
        ])

    def requests(self):
        return {key: ExecutionInput(system_prompt="Explain the code.", task="print(1)")
                for key in MODELS}

    def test_three_model_costs(self):
        expected = {"claude-haiku-4-5-20251001": "0.007000",
                    "claude-sonnet-5": "0.014000", "claude-opus-5-5": "0.028000"}
        for key, usd in expected.items():
            with self.subTest(key=key):
                quote = estimate_model_cost(self.models()[key], InputTokenEstimate(2000, "fixture"))
                self.assertEqual(quote.estimated_cost_usd, usd)
                self.assertEqual(quote.log_metadata()["output_estimation_method"], "configured_output_cap")

    def test_output_length_tier_sets_billable_output(self):
        model = self.models()["claude-sonnet-5"]
        quote = estimate_model_cost(model, InputTokenEstimate(2000, "fixture"), 512)
        self.assertEqual(quote.estimated_cost_usd, "0.009120")
        self.assertEqual(quote.log_metadata()["output_estimation_method"], "expected_output_length")
        for tokens in [0, 1001, True]:
            with self.subTest(tokens=tokens), self.assertRaises(RoutingError) as caught:
                estimate_model_cost(model, InputTokenEstimate(2000, "fixture"), tokens)
            self.assertEqual(caught.exception.code, "INVALID_TOKEN_COUNT")
        result = estimate_candidate_costs(self.assessment({"claude-sonnet-5"}, "medium"),
            requests_by_model=self.requests(),
            models={**self.models(), "claude-sonnet-5": replace(model, execution_max_output_tokens=4096)},
            token_counter=lambda key, req: InputTokenEstimate(2000, "fixture"))
        self.assertEqual(result.ranked_estimates[0].billable_output_tokens, 2048)
        self.assertEqual(result.ranked_estimates[0].estimated_cost_usd, "0.024480")

    def test_local_cost_zero(self):
        quote = estimate_model_cost(self.models()["qwen3:8b"], InputTokenEstimate(2000, "fixture"))
        self.assertEqual(quote.estimated_cost_usd, "0.000000")

    def test_round_total_once_upward(self):
        model = replace(self.models()["claude-sonnet-5"],
                        input_usd_per_million=Decimal("0.1"),
                        output_usd_per_million=Decimal("0.1"),
                        execution_max_output_tokens=1)
        quote = estimate_model_cost(model, InputTokenEstimate(1, "fixture"))
        self.assertEqual(quote.total_cost_usd, Decimal("0.0000002"))
        self.assertEqual(quote.estimated_cost_usd, "0.000001")

    def test_utf8_estimator_includes_system_prompt(self):
        request = ExecutionInput(system_prompt="코드를 설명해", task="  print('안녕')\n")
        estimate = estimate_input_tokens("qwen3:8b", request)
        self.assertEqual(estimate.tokens,
                         len(request.system_prompt.encode()) + len(request.task.encode()) + 64)
        self.assertEqual(estimate.method, "utf8-envelope-v1")
        self.assertGreater(estimate.tokens,
                           estimate_input_tokens("qwen3:8b", ExecutionInput("", request.task)).tokens)

    def test_invalid_inputs_and_rates(self):
        for tokens in [True, -1, 0, "10", 1.5]:
            with self.subTest(tokens=tokens), self.assertRaises(RoutingError):
                InputTokenEstimate(tokens, "fixture")
        for rate in [1.0, Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("0")]:
            model = replace(self.models()["claude-sonnet-5"], input_usd_per_million=rate)
            with self.subTest(rate=rate), self.assertRaises(RoutingError):
                estimate_model_cost(model, InputTokenEstimate(1, "fixture"))
        for amount in [0.1, Decimal("NaN"), Decimal("Infinity"), Decimal("-1")]:
            with self.subTest(amount=amount), self.assertRaises(RoutingError):
                format_usd(amount)

    def test_missing_limits_and_context_overflow(self):
        with self.assertRaises(RoutingError):
            estimate_model_cost(replace(MODELS["qwen3:8b"], execution_max_output_tokens=None),
                                InputTokenEstimate(10, "fixture"))
        model = self.models()["qwen3:8b"]
        estimate_model_cost(model, InputTokenEstimate(7192, "fixture"))
        with self.assertRaises(RoutingError) as caught:
            estimate_model_cost(model, InputTokenEstimate(7193, "fixture"))
        self.assertEqual(caught.exception.code, "INPUT_TOO_LARGE")

    def test_only_suitable_candidates_priced(self):
        result = estimate_candidate_costs(
            self.assessment({"claude-sonnet-5", "claude-opus-5-5"}),
            requests_by_model=self.requests(), models=self.models(),
            token_counter=lambda key, req: InputTokenEstimate(2000, "fixture"),
        )
        self.assertEqual([x.model_id for x in result.ranked_estimates],
                         ["claude-sonnet-5", "claude-opus-5-5"])

    def test_local_first_and_all_unsuitable_empty(self):
        for suitable, expected_count in [(set(MODELS), 4), (set(), 0)]:
            result = estimate_candidate_costs(self.assessment(suitable),
                requests_by_model=self.requests(), models=self.models())
            self.assertEqual(len(result.ranked_estimates), expected_count)
            if expected_count:
                self.assertEqual(result.ranked_estimates[0].model_id, "qwen3:8b")

    def test_model_specific_counts_can_change_cost_order(self):
        key = "claude-sonnet-5"
        result = estimate_candidate_costs(
            self.assessment({"claude-haiku-4-5-20251001", key}),
            requests_by_model=self.requests(), models=self.models(),
            token_counter=lambda mid, req: InputTokenEstimate(10 if mid == key else 5000, "model-specific"),
        )
        self.assertEqual(result.ranked_estimates[0].model_id, key)

    def test_context_overflow_excludes_even_suitable_local(self):
        result = estimate_candidate_costs(self.assessment(), requests_by_model=self.requests(),
            models=self.models(), token_counter=lambda key, req:
                InputTokenEstimate(8000 if key == "qwen3:8b" else 100, "fixture"))
        self.assertNotIn("qwen3:8b", [x.model_id for x in result.ranked_estimates])

    def test_tie_break_is_stable_and_uses_unrounded_cost(self):
        models = self.models()
        paid = set(MODELS) - {"qwen3:8b"}
        for key in paid:
            models[key] = replace(models[key], input_usd_per_million=Decimal("0.1"),
                                  output_usd_per_million=Decimal("0.1"), execution_max_output_tokens=512)
        assessment = self.assessment(paid)
        assessment.evaluations.reverse()
        result = estimate_candidate_costs(assessment, requests_by_model=self.requests(), models=models,
            token_counter=lambda key, req: InputTokenEstimate(1, "fixture"))
        self.assertEqual(result.ranked_estimates[0].model_id, "claude-haiku-4-5-20251001")
        models["claude-opus-5-5"] = replace(models["claude-opus-5-5"],
                                            input_usd_per_million=Decimal("0.01"))
        result = estimate_candidate_costs(assessment, requests_by_model=self.requests(), models=models,
            token_counter=lambda key, req: InputTokenEstimate(1, "fixture"))
        self.assertEqual(len({x.estimated_cost_usd for x in result.ranked_estimates}), 1)
        self.assertEqual(result.ranked_estimates[0].model_id, "claude-opus-5-5")

    def test_default_execution_limits_are_configured(self):
        result = estimate_candidate_costs(self.assessment(set(MODELS) - {"qwen3:8b"}, "long"),
            requests_by_model={key: ExecutionInput("", "print(1)") for key in MODELS},
            token_counter=lambda key, req: InputTokenEstimate(2000, "fixture"))
        self.assertEqual([x.estimated_cost_usd for x in result.ranked_estimates],
                         ["0.022480", "0.044960", "0.089920"])

    def test_missing_request_is_error(self):
        with self.assertRaises(RoutingError):
            estimate_candidate_costs(self.assessment(), requests_by_model={}, models=self.models())


if __name__ == "__main__":
    unittest.main()
