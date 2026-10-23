import unittest

from nook.main import _resolve_model
from nook.ollama_client import NoChatModelError, OllamaUnavailableError


class StubOllamaClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.preferred = None

    def detect_model(self, preferred=None):
        self.preferred = preferred
        if self.error:
            raise self.error
        return self.result


class ResolveModelTests(unittest.TestCase):
    def test_returns_detected_model(self):
        client = StubOllamaClient(result="llama3.2:latest")

        self.assertEqual(
            _resolve_model(client, ""),
            ("llama3.2:latest", True, None),
        )
        self.assertIsNone(client.preferred)

    def test_reports_offline_ollama_error(self):
        error = OllamaUnavailableError("Ollama unavailable")

        self.assertEqual(
            _resolve_model(StubOllamaClient(error=error), ""),
            ("", False, "Ollama unavailable"),
        )

    def test_reports_missing_preferred_model(self):
        error = NoChatModelError("Model llama3.2 not installed")
        client = StubOllamaClient(error=error)

        self.assertEqual(
            _resolve_model(client, "llama3.2"),
            ("", True, "Model llama3.2 not installed"),
        )
        self.assertEqual(client.preferred, "llama3.2")


if __name__ == "__main__":
    unittest.main()
