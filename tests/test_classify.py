import json
import tempfile
import unittest
from pathlib import Path

import httpx

from kiln_router.classify import CapturingTelemetry, classify_task, format_report
from kiln_router.client import KilnClient, KilnSettings
from kiln_router.errors import RoutingError
from kiln_router.models import MODELS


class ClassifyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "classification.jsonl"

    def handler(self, task, length="short", suitable=None):
        suitable = set(MODELS) if suitable is None else suitable
        def respond(request):
            self.assertEqual(json.loads(request.content)["messages"][1]["content"], task)
            evaluations = [{"model_id": key, "suitable": key in suitable, "reason": "간단한 요약"}
                           for key in MODELS]
            return httpx.Response(200, json={
                "id": "test", "model": "qwen3-32b",
                "choices": [{"message": {"content": json.dumps(
                    {"expected_output_length": length, "evaluations": evaluations})},
                    "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            })
        return respond

    async def classify(self, task, **options):
        telemetry = CapturingTelemetry(self.path)
        async with KilnClient(KilnSettings(api_key="test"),
                              transport=httpx.MockTransport(self.handler(task, **options))) as client:
            decision = await classify_task(task, client, telemetry)
        return decision, telemetry.event

    async def test_runs_router_with_default_settings(self):
        decision, event = await self.classify("이 문장을 요약해줘: 오늘은 비가 와서 산책을 취소했다.")
        self.assertEqual(decision.selected_model, "qwen3:8b")
        self.assertEqual(decision.max_output_tokens, 512)
        self.assertEqual(len(event["cost_estimates"]), 4)
        logged = json.loads(self.path.read_text().splitlines()[-1])
        self.assertEqual(logged["flow"], "classification_check")

    async def test_report_shows_costs_limits_and_decision(self):
        _, event = await self.classify("Write a long report", length="long")
        report = format_report(event)
        self.assertIn("long (4096 토큰 예약)", report)
        self.assertIn("qwen3:8b: 부적합 (실행 한도 초과)", report)
        self.assertIn("claude-haiku-4-5-20251001: 적합 · $0.0", report)
        self.assertIn('"max_output_tokens": 4096', report)
        self.assertIn("Kiln 토큰: 입력 10, 출력 20", report)

    async def test_no_suitable_model_still_reports_candidates(self):
        telemetry = CapturingTelemetry(self.path)
        task = "Find the bug"
        async with KilnClient(KilnSettings(api_key="test"),
                              transport=httpx.MockTransport(self.handler(task, suitable=set()))) as client:
            with self.assertRaises(RoutingError) as caught:
                await classify_task(task, client, telemetry)
        self.assertEqual(caught.exception.code, "NO_SUITABLE_MODEL")
        report = format_report(telemetry.event)
        self.assertIn("claude-opus-5-5: 부적합", report)
        self.assertNotIn("최종 추천", report)

    async def test_404_does_not_fabricate_classification(self):
        telemetry = CapturingTelemetry(self.path)
        async with KilnClient(KilnSettings(api_key="test"),
            transport=httpx.MockTransport(lambda request: httpx.Response(404))) as client:
            with self.assertRaises(RoutingError) as caught:
                await classify_task("Summarize: hello world", client, telemetry)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertNotIn("후보별", format_report(telemetry.event))


if __name__ == "__main__":
    unittest.main()
