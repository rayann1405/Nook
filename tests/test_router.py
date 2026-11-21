import unittest
from datetime import datetime

from nook.ollama_client import OllamaModelInfo, OllamaResponse
from nook.router import ModelRouter, RouterError


class FakeOllama:
    def __init__(self, models, content="local reply", error=None, discovery_error=None):
        self.models = [
            OllamaModelInfo(name, datetime.now(), 1)
            for name in models
        ]
        self.content = content
        self.error = error
        self.discovery_error = discovery_error
        self.model = ""
        self.calls = 0

    def list_models_detailed(self):
        if self.discovery_error:
            raise self.discovery_error
        return self.models

    def set_model(self, model):
        self.model = model

    def chat(self, messages, *, stream=False, on_token=None, num_ctx=2048):
        self.calls += 1
        if self.error:
            raise self.error
        if stream and on_token:
            on_token(self.content)
        return OllamaResponse(self.content, self.model, True)


class FakeMeta:
    def __init__(self, content="cloud reply", configured=True, error=None):
        self.content = content
        self.configured = configured
        self.error = error
        self.calls = 0

    @property
    def configured(self):
        return self._configured

    @configured.setter
    def configured(self, value):
        self._configured = value

    def is_reachable(self):
        return True

    def generate(self, messages, *, stream=False, on_token=None):
        self.calls += 1
        if self.error:
            raise self.error
        if stream and on_token:
            on_token(self.content)
        return type("Response", (), {"content": self.content, "model": "muse-spark-1.3"})()


class ModelRouterTests(unittest.TestCase):
    def make_router(
        self,
        *,
        local_models=("llama3.2:1b", "llama3.2:3b"),
        local_error=None,
        meta_error=None,
        mode="auto",
        hard=False,
        memory=8.0,
        max_cloud_calls=5,
        reachable=True,
        discovery_error=None,
    ):
        local = FakeOllama(
            local_models,
            error=local_error,
            discovery_error=discovery_error,
        )
        meta = FakeMeta(error=meta_error)
        router = ModelRouter(
            local,
            meta,
            mode=mode,
            max_cloud_calls=max_cloud_calls,
            memory_provider=lambda: memory,
            connectivity_check=lambda: reachable,
        )
        return router, local, meta

    def test_auto_uses_local_three_b_model_by_default(self):
        router, local, meta = self.make_router()

        result = router.generate("hello")

        self.assertEqual((result.provider, result.model), ("local", "llama3.2:3b"))
        self.assertEqual(local.calls, 1)
        self.assertEqual(meta.calls, 0)

    def test_provider_callback_reports_selected_provider_and_model(self):
        router, _, _ = self.make_router()
        providers = []

        router.generate("hello", on_provider=lambda provider, model: providers.append((provider, model)))

        self.assertEqual(providers, [("local", "llama3.2:3b")])

    def test_low_available_memory_selects_one_b_model(self):
        router, _, _ = self.make_router(memory=2.0)

        result = router.generate("hello")

        self.assertEqual(result.model, "llama3.2:1b")

    def test_refresh_reports_missing_preferred_model(self):
        router, _, _ = self.make_router(local_models=("llama3.2:3b",))

        router.set_local_model("missing-model")

        self.assertEqual(router.local_model, "")
        self.assertIn("missing-model", router.last_error)

    def test_refresh_reports_when_ollama_is_offline(self):
        import httpx

        router, _, _ = self.make_router(
            discovery_error=httpx.ConnectError("connection refused")
        )

        self.assertEqual(router.refresh_local_model(), "")
        self.assertIn("Ollama is unavailable", router.last_error)

    def test_local_failure_falls_back_to_cloud_once(self):
        router, local, meta = self.make_router(local_error=TimeoutError("local timeout"))

        result = router.generate("hello")

        self.assertEqual(result.provider, "cloud")
        self.assertEqual(local.calls, 1)
        self.assertEqual(meta.calls, 1)
        self.assertEqual(router.cloud_calls, 1)

    def test_hard_auto_task_tries_cloud_first(self):
        router, local, meta = self.make_router()

        result = router.generate("complex task", hard=True)

        self.assertEqual(result.provider, "cloud")
        self.assertEqual(local.calls, 0)
        self.assertEqual(meta.calls, 1)

    def test_cloud_failure_falls_back_to_local(self):
        router, local, meta = self.make_router(mode="cloud", meta_error=TimeoutError("cloud timeout"))

        result = router.generate("hello")

        self.assertEqual(result.provider, "local")
        self.assertEqual(meta.calls, 1)
        self.assertEqual(local.calls, 1)

    def test_cloud_call_cap_blocks_later_cloud_calls(self):
        router, _, meta = self.make_router(
            local_error=TimeoutError("local timeout"),
            max_cloud_calls=1,
        )

        router.generate("first")
        with self.assertRaisesRegex(RouterError, "session limit reached"):
            router.generate("second")

        self.assertEqual(meta.calls, 1)
        self.assertEqual(router.cloud_calls, 1)

    def test_local_mode_never_uses_cloud_fallback(self):
        router, _, meta = self.make_router(mode="local", local_error=TimeoutError("local timeout"))

        with self.assertRaisesRegex(RouterError, "Local model request failed"):
            router.generate("hello")

        self.assertEqual(meta.calls, 0)

    def test_hard_auto_requires_connectivity_before_cloud(self):
        router, local, meta = self.make_router(reachable=False)

        result = router.generate("complex task", hard=True)

        self.assertEqual(result.provider, "local")
        self.assertEqual(local.calls, 1)
        self.assertEqual(meta.calls, 0)

    def test_cloud_fallback_failure_includes_both_errors(self):
        router, _, _ = self.make_router(
            mode="cloud",
            local_error=TimeoutError("local timeout"),
            meta_error=TimeoutError("cloud timeout"),
        )

        with self.assertRaisesRegex(RouterError, "Cloud failed.*local fallback failed"):
            router.generate("hello")


if __name__ == "__main__":
    unittest.main()
