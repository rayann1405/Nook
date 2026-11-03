import json
import os
import unittest
from unittest.mock import patch

import httpx

from nook.meta_client import MetaAPIError, MetaModelClient


class MetaModelClientTests(unittest.TestCase):
    def make_client(self, handler, *, api_key="test-key"):
        http = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(
            os.environ,
            {"META_API_KEY": api_key, "MODEL_API_KEY": ""},
        ):
            return MetaModelClient(http_client=http)

    def test_chat_completion_uses_documented_endpoint_and_bearer_auth(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "model": "muse-spark-1.3",
                    "choices": [{"message": {"content": "Hello."}}],
                },
            )

        client = self.make_client(handler)
        try:
            response = client.generate([{"role": "user", "content": "Hi"}])
        finally:
            client.close()

        self.assertEqual(str(requests[0].url), "https://api.meta.ai/v1/chat/completions")
        self.assertEqual(requests[0].headers["Authorization"], "Bearer test-key")
        self.assertEqual(json.loads(requests[0].content)["model"], "muse-spark-1.3")
        self.assertEqual(response.content, "Hello.")

    def test_streaming_emits_sse_content_deltas(self):
        chunks = [
            'data: {"model":"muse-spark-1.3","choices":[{"delta":{"content":"Hello"}}]}\n\n',
            'data: {"model":"muse-spark-1.3","choices":[{"delta":{"content":" world"}}]}\n\n',
            "data: [DONE]\n\n",
        ]

        def handler(request):
            return httpx.Response(200, text="".join(chunks))

        client = self.make_client(handler)
        received = []
        try:
            response = client.generate(
                [{"role": "user", "content": "Hi"}],
                stream=True,
                on_token=received.append,
            )
        finally:
            client.close()

        self.assertEqual(received, ["Hello", " world"])
        self.assertEqual(response.content, "Hello world")

    def test_missing_key_fails_before_network_request(self):
        client = self.make_client(lambda request: self.fail("unexpected request"), api_key="")
        try:
            with self.assertRaisesRegex(MetaAPIError, "META_API_KEY"):
                client.generate([{"role": "user", "content": "Hi"}])
        finally:
            client.close()

    def test_meta_environment_key_takes_precedence_over_legacy_alias(self):
        with patch.dict(
            os.environ,
            {"META_API_KEY": "environment-key", "MODEL_API_KEY": "legacy-key"},
        ):
            client = MetaModelClient()
        try:
            self.assertEqual(client.api_key, "environment-key")
        finally:
            client.close()

    def test_check_credentials_reports_success_and_auth_failure(self):
        def ok_handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

        def forbidden_handler(request):
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        client = self.make_client(ok_handler)
        try:
            ok, message = client.check_credentials()
        finally:
            client.close()
        self.assertTrue(ok)
        self.assertIn("OK", message)

        client = self.make_client(forbidden_handler)
        try:
            ok, message = client.check_credentials()
        finally:
            client.close()
        self.assertFalse(ok)
        self.assertIn("401", message)

    def test_api_key_can_be_updated_without_recreating_the_client(self):
        client = self.make_client(lambda request: httpx.Response(200, json={}))
        try:
            self.assertTrue(client.configured)
            client.set_api_key("")
            self.assertFalse(client.configured)
            client.set_api_key("new-key")
            self.assertEqual(client.api_key, "new-key")
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
