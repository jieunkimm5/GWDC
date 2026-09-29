import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from kiln_router.client import KilnClient, KilnSettings
from kiln_router.errors import RoutingError


def body():
    return {
        "id": "chatcmpl-test", "model": "qwen3-32b",
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 9, "completion_tokens": 12,
                  "total_tokens": 21, "cost": 0.000001155},
    }


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, handler):
        async with KilnClient(KilnSettings(api_key="test-secret"),
                              transport=httpx.MockTransport(handler)) as client:
            return await client.complete(system_prompt="Be brief.", task="Hello")

    async def test_request_and_usage(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://api.bricksum.com/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer test-secret")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "qwen3-32b")
            self.assertNotIn("reasoning_effort", payload)
            self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
            self.assertEqual(payload["messages"][1]["content"], "Hello")
            self.assertNotIn("response_format", payload)
            return httpx.Response(200, json=body(), headers={"X-Neocloud-Generation-Id": "gen-test"})
        result = await self.call(handler)
        self.assertEqual(result.content, "OK")
        self.assertEqual(result.total_tokens, 21)
        self.assertEqual(result.kiln_cost_usd, "0.000001155")
        self.assertEqual(result.generation_id, "gen-test")
        self.assertNotIn("content", result.log_metadata())

    async def test_http_errors_not_retried_or_leaked(self):
        for status, code in [(401, "KILN_AUTH_ERROR"), (403, "KILN_AUTH_ERROR"),
                             (402, "KILN_CREDIT_ERROR"), (429, "KILN_RATE_LIMIT"),
                             (500, "KILN_API_ERROR"), (302, "KILN_API_ERROR")]:
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, text="test-secret", headers={"Location": "https://example.com"})
            with self.subTest(status=status), self.assertRaises(RoutingError) as caught:
                await self.call(handler)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.status_code, status)
            self.assertNotIn("test-secret", str(caught.exception))
            self.assertEqual(len(calls), 1)

    async def test_timeout_and_network_error(self):
        for error, code in [(httpx.ReadTimeout, "KILN_TIMEOUT"),
                            (httpx.ConnectError, "KILN_NETWORK_ERROR")]:
            def handler(request):
                raise error("test-secret", request=request)
            with self.subTest(code=code), self.assertRaises(RoutingError) as caught:
                await self.call(handler)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("test-secret", str(caught.exception))

    async def test_invalid_responses(self):
        missing = body()
        missing.pop("usage")
        wrong_count = body()
        wrong_count["usage"]["prompt_tokens"] = True
        for data in [{}, missing, wrong_count, {**body(), "choices": []}]:
            with self.subTest(data=data), self.assertRaises(RoutingError) as caught:
                await self.call(lambda request: httpx.Response(200, json=data))
            self.assertEqual(caught.exception.code, "KILN_INVALID_RESPONSE")
        with self.assertRaises(RoutingError):
            await self.call(lambda request: httpx.Response(200, text="not json"))

    async def test_truncation_preserves_usage(self):
        data = body()
        data["choices"][0] = {"message": {"content": ""}, "finish_reason": "length"}
        with self.assertRaises(RoutingError) as caught:
            await self.call(lambda request: httpx.Response(200, json=data))
        self.assertEqual(caught.exception.code, "KILN_INCOMPLETE_RESPONSE")
        self.assertEqual(caught.exception.metadata["total_tokens"], 21)

    async def test_optional_cost_is_unknown_not_zero(self):
        data = body()
        data["usage"].pop("cost")
        result = await self.call(lambda request: httpx.Response(200, json=data))
        self.assertIsNone(result.kiln_cost_usd)

    def test_settings_and_secret_repr(self):
        self.assertNotIn("test-secret", repr(KilnSettings(api_key="test-secret")))
        for key, url in [("", "https://api.bricksum.com/v1"),
                         ("test-secret", "http://api.bricksum.com/v1")]:
            with self.assertRaises(RoutingError):
                KilnSettings(api_key=key, api_url=url)

    def test_environment_overrides_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("KILN_API_KEY=file-secret\n")
            with patch.dict("os.environ", {"KILN_API_KEY": "env-secret"}, clear=True):
                self.assertEqual(KilnSettings.from_env(path).api_key, "env-secret")


if __name__ == "__main__":
    unittest.main()
