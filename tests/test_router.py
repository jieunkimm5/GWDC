import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import httpx

from kiln_router.client import KilnClient, KilnSettings
from kiln_router.errors import RoutingError
from kiln_router.models import MODELS, KILN_MODEL_ID
from kiln_router.pricing import InputTokenEstimate
from kiln_router.router import KilnRouter
from kiln_router.telemetry import JsonlTelemetry


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "routing.jsonl"
        self.calls = 0

    def models(self):
        return {key: replace(value, execution_context_tokens=8192,
                             execution_max_output_tokens=1000) for key, value in MODELS.items()}

    def handler(self, suitable, malformed=False, status=200, truncated=False, output_length="short"):
        def respond(request):
            self.calls += 1
            self.assertEqual(json.loads(request.content)["model"], KILN_MODEL_ID)
            content = json.dumps({"expected_output_length": output_length, "evaluations": [
                {"model_id": key, "suitable": key in suitable, "reason": "Test assessment"}
                for key in MODELS
            ]})
            return httpx.Response(status, json={
                "id": "test", "model": KILN_MODEL_ID,
                "choices": [{"message": {"content": "oops" if malformed else content},
                             "finish_reason": "length" if truncated else "stop"}],
                "usage": {"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
            })
        return respond

    async def run_route(self, suitable=None, *, task="Explain print(1)", models=None,
                        malformed=False, status=200, truncated=False, counter=None, telemetry=None,
                        output_length="short"):
        suitable = set(MODELS) if suitable is None else suitable
        async with KilnClient(KilnSettings(api_key="test-secret"),
            transport=httpx.MockTransport(self.handler(suitable, malformed, status, truncated, output_length))) as client:
            router = KilnRouter(client,
                execution_prompts={key: "Explain the supplied task" for key in MODELS},
                models=self.models() if models is None else models,
                telemetry=JsonlTelemetry(self.path) if telemetry is None else telemetry,
                token_counter=counter or (lambda key, req: InputTokenEstimate(2000, "fixture")))
            return await router.recommend_route(task)

    def event(self):
        return json.loads(self.path.read_text().splitlines()[-1])

    async def test_local_returns_exact_contract(self):
        result = await self.run_route(task="private-task-text")
        self.assertEqual(result.recommended_route, "LOCAL")
        self.assertEqual(result.estimated_cost_usd, "0.000000")
        self.assertEqual(set(result.model_dump()),
            {"recommended_route", "selected_model", "reason", "estimated_cost_usd",
             "max_output_tokens"})
        self.assertEqual(result.max_output_tokens, 512)
        self.assertEqual(self.calls, 1)
        event = self.event()
        self.assertEqual(event["status"], "SUCCESS")
        self.assertEqual(event["kiln_usage"]["total_tokens"], 700)
        self.assertNotIn("private-task-text", self.path.read_text())
        self.assertNotIn("test-secret", self.path.read_text())

    async def test_paid_cheapest_suitable(self):
        result = await self.run_route({"claude-sonnet-5", "claude-opus-5-5"})
        self.assertEqual(result.selected_model, "claude-sonnet-5")
        self.assertEqual(result.estimated_cost_usd, "0.009120")
        self.assertEqual(len(self.event()["cost_estimates"]), 2)
        self.assertEqual(self.event()["expected_output_length"], "short")

    async def test_capacity_rejects_ai_local(self):
        result = await self.run_route(counter=lambda key, req:
            InputTokenEstimate(8000 if key == "qwen3:8b" else 2000, "fixture"))
        self.assertEqual(result.selected_model, "claude-haiku-4-5-20251001")

    async def test_long_answer_excludes_local_output_cap(self):
        result = await self.run_route(models=MODELS, output_length="long")
        self.assertEqual(result.selected_model, "claude-haiku-4-5-20251001")
        self.assertEqual(result.estimated_cost_usd, "0.022480")
        self.assertEqual(result.max_output_tokens, 4096)
        self.assertFalse(self.event()["checked_assessment"]["evaluations"][0]["suitable"])

    async def test_no_suitable_model_is_not_local(self):
        with self.assertRaises(RoutingError) as caught:
            await self.run_route(set())
        self.assertEqual(caught.exception.code, "NO_SUITABLE_MODEL")
        self.assertNotIn("decision", self.event())
        self.assertEqual(self.event()["kiln_usage"]["total_tokens"], 700)

    async def test_invalid_json_preserves_usage(self):
        with self.assertRaises(RoutingError) as caught:
            await self.run_route(malformed=True)
        self.assertEqual(caught.exception.code, "INVALID_MODEL_RESPONSE")
        self.assertEqual(self.event()["kiln_usage"]["total_tokens"], 700)

    async def test_api_error_has_unknown_usage(self):
        with self.assertRaises(RoutingError) as caught:
            await self.run_route(status=404)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertIsNone(self.event()["kiln_usage"])
        self.assertEqual(self.calls, 1)

    async def test_truncated_usage_preserved(self):
        with self.assertRaises(RoutingError):
            await self.run_route(truncated=True)
        self.assertEqual(self.event()["kiln_usage"]["total_tokens"], 700)

    async def test_preflight_failures_do_not_call_api(self):
        for options, code in [({"task": " "}, "INVALID_INPUT"),
                              ({"models": {key: replace(value, execution_max_output_tokens=None)
                                           for key, value in MODELS.items()}},
                               "MODEL_CONFIG_ERROR"),
                              ({"counter": lambda key, req: InputTokenEstimate(140000, "fixture")},
                               "INPUT_TOO_LARGE")]:
            with self.subTest(code=code), self.assertRaises(RoutingError) as caught:
                await self.run_route(**options)
            self.assertEqual(caught.exception.code, code)
            self.assertFalse(self.event()["api_attempted"])
        self.assertEqual(self.calls, 0)

    async def test_default_settings_send_task_without_system_prompt(self):
        async with KilnClient(KilnSettings(api_key="test-secret"),
            transport=httpx.MockTransport(self.handler({"claude-sonnet-5"}, output_length="long"))) as client:
            router = KilnRouter(client, telemetry=JsonlTelemetry(self.path),
                token_counter=lambda key, req: InputTokenEstimate(
                    2000 if req.system_prompt == "" else 1, "fixture"))
            result = await router.recommend_route("Explain print(1)")
        self.assertEqual(result.selected_model, "claude-sonnet-5")
        self.assertEqual(result.estimated_cost_usd, "0.044960")
        self.assertEqual(result.max_output_tokens, 4096)

    async def test_separate_concurrent_events(self):
        await asyncio.gather(self.run_route(), self.run_route())
        events = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]["analysis_id"], events[1]["analysis_id"])

    async def test_log_failure_is_explicit(self):
        class BrokenLog:
            def write(self, event):
                raise OSError("private-path")
        with self.assertRaises(RoutingError) as caught:
            await self.run_route(telemetry=BrokenLog())
        self.assertEqual(caught.exception.code, "TELEMETRY_ERROR")
        with self.assertWarns(RuntimeWarning), self.assertRaises(RoutingError) as caught:
            await self.run_route(status=404, telemetry=BrokenLog())
        self.assertEqual(caught.exception.code, "KILN_API_ERROR")


if __name__ == "__main__":
    unittest.main()
