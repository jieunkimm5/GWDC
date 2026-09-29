"""Offline checks for local fallback limits, failure handling, and tx locking.

All model, Kiln, and blockchain calls are mocked; no credits or gas are used.
"""

import threading
import time
import unittest
from unittest.mock import patch

import httpx

from app.schemas import RouterResult
from app.services import executor, workflow
from blockchain import record


def paid_recommendation(max_output_tokens=4096):
    return RouterResult(
        recommended_route="PAID", selected_model="claude-sonnet-5",
        reason="Complex task.", estimated_cost_usd="0.041634",
        max_output_tokens=max_output_tokens,
    )


REJECTED = {"approved": False, "amount_usd": "0.041634", "tx_hash": None,
            "reason": "BUDGET_EXCEEDED"}
LOCAL_OK = {"result": "local answer", "actual_cost_usd": "0.000000",
            "input_tokens": 10, "output_tokens": 20}


class ExecutorTests(unittest.TestCase):
    def test_local_run_caps_paid_output_and_sets_context(self):
        sent = {}

        def fake_post(url, json, timeout):
            sent.update(json=json, timeout=timeout)
            return httpx.Response(200, request=httpx.Request("POST", url), json={
                "message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1})

        with patch.object(executor.httpx, "post", fake_post):
            executor.run_local("task", max_output_tokens=4096)
        self.assertEqual(sent["json"]["options"]["num_predict"], 2048)
        self.assertEqual(sent["json"]["options"]["num_ctx"], 16384)
        self.assertEqual(sent["timeout"], 300.0)


class WorkflowFallbackTests(unittest.TestCase):
    def run_rejected(self, run_local):
        with patch.object(workflow, "analyze", return_value=paid_recommendation()), \
             patch.object(workflow, "authorize", return_value=REJECTED), \
             patch.object(workflow, "run_local", run_local):
            return workflow.run_workflow(task="Build a backend", budget_usd="0")

    def test_budget_rejection_runs_local(self):
        response = self.run_rejected(lambda task, max_output_tokens: LOCAL_OK)
        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(response.decision.recommended_route, "PAID")
        self.assertEqual(response.decision.actual_route, "LOCAL")
        self.assertEqual(response.decision.fallback_reason, "BUDGET_EXCEEDED")

    def test_local_failure_returns_failed_response_not_exception(self):
        def failing_local(task, max_output_tokens):
            raise RuntimeError("Ollama request failed: timed out")

        response = self.run_rejected(failing_local)
        self.assertEqual(response.status, "FAILED")
        self.assertEqual(response.decision.fallback_reason, "BUDGET_EXCEEDED")
        self.assertIn("Local model execution failed", response.result)
        self.assertEqual(response.usage.output_tokens, 0)


class RecordLockTests(unittest.TestCase):
    def test_concurrent_records_are_sent_one_at_a_time(self):
        active, peak = 0, 0
        guard = threading.Lock()

        def fake_send(**kwargs):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with guard:
                active -= 1
            return {"tx_hash": "0x1", "status": 1, "block_number": 1}

        with patch.object(record, "_record_decision_unlocked", fake_send):
            threads = [threading.Thread(target=record.record_decision, kwargs=dict(
                run_id=f"run_{i}", decision="PAID", approved=True,
                amount="0.01", provider="claude-sonnet-5")) for i in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(peak, 1)


if __name__ == "__main__":
    unittest.main()
