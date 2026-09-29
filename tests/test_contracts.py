"""Contract boundaries that must remain stable for integration with C."""

import json
import unittest

from pydantic import ValidationError

from kiln_router.models import MODELS
from kiln_router.schemas import (
    KilnEvaluationResponse,
    RoutingDecision,
    RoutingRequest,
)


class ContractTests(unittest.TestCase):
    def decision(self, **changes):
        return {
            "recommended_route": "PAID",
            "selected_model": "claude-sonnet-5",
            "reason": "Suitable candidate with the lowest estimated cost.",
            "estimated_cost_usd": "0.014000",
            "max_output_tokens": 2048,
            **changes,
        }

    def evaluations(self):
        return [
            {"model_id": model_id, "suitable": True, "reason": "Suitable."}
            for model_id in MODELS
        ]

    def test_task_preserves_code_whitespace(self):
        task = "  def example():\n      return 1\n"
        self.assertEqual(RoutingRequest(task=task).task, task)

    def test_invalid_requests_rejected(self):
        for payload in [{"task": " \n"}, {"task": 123}, {},
                        {"task": "Summarize", "budget_usd": "0.050000"}]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                RoutingRequest.model_validate(payload)

    def test_output_json_preserves_exact_contract(self):
        payload = self.decision()
        decision = RoutingDecision.model_validate_json(json.dumps(payload))
        self.assertEqual(json.loads(decision.model_dump_json()), payload)

    def test_invalid_money_rejected(self):
        for value in [0.014, "-0.014000", "0.014", "NaN", "Infinity",
                      "1e-6", "0.014000\n", " 0.014000", "01.014000"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RoutingDecision.model_validate(self.decision(estimated_cost_usd=value))

    def test_invalid_decisions_rejected(self):
        for changes in [
            {"recommended_route": "LOCAL"},
            {"selected_model": "unknown-model"},
            {"recommended_route": "PREMIUM"},
            {"reason": " "},
            {"approved": True},
            {"max_output_tokens": 0},
            {"max_output_tokens": True},
            {"max_output_tokens": "2048"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                RoutingDecision.model_validate(self.decision(**changes))

    def test_local_cost_must_be_zero(self):
        payload = self.decision(recommended_route="LOCAL", selected_model="qwen3:8b")
        with self.assertRaises(ValidationError):
            RoutingDecision.model_validate(payload)
        payload["estimated_cost_usd"] = "0.000000"
        self.assertEqual(RoutingDecision(**payload).recommended_route, "LOCAL")

    def test_all_candidates_can_be_unsuitable(self):
        items = self.evaluations()
        for item in items:
            item["suitable"] = False
        result = KilnEvaluationResponse.model_validate_json(json.dumps({"expected_output_length": "short", "evaluations": items}))
        self.assertTrue(all(not item.suitable for item in result.evaluations))

    def test_output_length_tier_required(self):
        for payload in [{"evaluations": self.evaluations()},
                        {"expected_output_length": "huge", "evaluations": self.evaluations()}]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                KilnEvaluationResponse.model_validate(payload)

    def test_missing_duplicate_and_unknown_candidates_rejected(self):
        items = self.evaluations()
        for invalid in [items[:-1], items + [items[0]], [items[0]] * 4,
                        [{**items[0], "model_id": "unknown"}] + items[1:]]:
            with self.subTest(items=invalid), self.assertRaises(ValidationError):
                KilnEvaluationResponse.model_validate(
                    {"expected_output_length": "short", "evaluations": invalid})

    def test_boolean_coercion_and_blank_reason_rejected(self):
        for change in [{"suitable": "false"}, {"suitable": 1}, {"reason": "\n"}]:
            items = self.evaluations()
            items[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                KilnEvaluationResponse.model_validate_json(json.dumps({"expected_output_length": "short", "evaluations": items}))


if __name__ == "__main__":
    unittest.main()
