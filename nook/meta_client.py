"""Client for Meta Model API's OpenAI-compatible chat-completions endpoint."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable

import httpx


class MetaAPIError(Exception):
    """Meta Model API request failed."""


@dataclass
class MetaResponse:
    content: str
    model: str


class MetaModelClient:
    def __init__(
        self,
        base_url: str = "https://api.meta.ai/v1",
        model: str = "muse-spark-1.3",
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        if api_key is None:
            api_key = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY") or ""
        self.api_key = api_key.strip()
        self._timeout = httpx.Timeout(connect=2.0, read=timeout, write=10.0, pool=3.0)
        self._client = http_client or httpx.Client(timeout=self._timeout)

    def configure(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Met à jour les identifiants sans recréer le client (utilisé par l'UI)."""
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        if model is not None:
            self.model = model.strip()
        if api_key is not None:
            self.api_key = api_key.strip()

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        self._client.close()

    def is_reachable(self) -> bool:
        """True si l'hôte répond (même avec 401/403/404 : le réseau est OK)."""
        try:
            self._client.get(self.base_url, timeout=2.0)
            return True
        except httpx.HTTPError:
            return False

    @staticmethod
    def _http_error(response: httpx.Response) -> str:
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    detail = str(error.get("message") or error.get("code") or "")
                elif error:
                    detail = str(error)
                detail = detail or str(payload.get("message") or "")
        except (ValueError, json.JSONDecodeError):
            detail = response.text.strip()[:200]
        if response.status_code == 401:
            return "Meta API rejected the key (401). Check META_API_KEY in .env."
        if response.status_code == 403:
            return "Meta API access denied (403). Check your key permissions."
        if response.status_code == 404:
            return (
                "Meta API endpoint not found (404). Check META_API_BASE_URL "
                f"({response.request.url})."
            )
        suffix = f" — {detail}" if detail else ""
        return f"Meta API returned HTTP {response.status_code}{suffix}"

    def check_credentials(self) -> tuple[bool, str]:
        """Teste la clé et l'endpoint avec une requête minimale."""
        if not self.api_key:
            return False, "Meta API key is missing (META_API_KEY)."
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        headers = {"Authorization": "Bearer " + self.api_key}
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return False, f"Meta API unreachable: {exc}"
        if response.status_code < 400:
            return True, f"Meta API OK · {self.model}"
        return False, self._http_error(response)

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        on_token: Callable[[str], None] | None = None,
    ) -> MetaResponse:
        if not self.api_key:
            raise MetaAPIError("Meta API key is missing (set META_API_KEY).")

        body = {"model": self.model, "messages": messages, "stream": stream}
        headers = {"Authorization": "Bearer " + self.api_key}
        if stream:
            return self._stream(body, headers, on_token)
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            )
            if response.status_code >= 400:
                raise MetaAPIError(self._http_error(response))
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return MetaResponse(str(content).strip(), data.get("model", self.model))
        except MetaAPIError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise MetaAPIError(f"Meta Model API request failed: {exc}") from exc

    def _stream(
        self,
        body: dict[str, object],
        headers: dict[str, str],
        on_token: Callable[[str], None] | None,
    ) -> MetaResponse:
        content: list[str] = []
        model = self.model
        try:
            with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    raise MetaAPIError(self._http_error(response))
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    data = json.loads(payload)
                    model = data.get("model", model)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    chunk = delta.get("content") or ""
                    if chunk:
                        content.append(chunk)
                        if on_token:
                            on_token(chunk)
        except MetaAPIError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise MetaAPIError(f"Meta Model API streaming request failed: {exc}") from exc
        return MetaResponse("".join(content).strip(), model)
