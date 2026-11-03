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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = (
            os.environ.get("META_API_KEY")
            or os.environ.get("MODEL_API_KEY")
            or ""
        )
        self._timeout = httpx.Timeout(connect=2.0, read=timeout, write=10.0, pool=3.0)
        self._client = http_client or httpx.Client(timeout=self._timeout)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        self._client.close()

    def is_reachable(self) -> bool:
        try:
            self._client.get(self.base_url, timeout=2.0)
            return True
        except httpx.HTTPError:
            return False

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
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return MetaResponse(str(content).strip(), data.get("model", self.model))
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
                response.raise_for_status()
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
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise MetaAPIError(f"Meta Model API streaming request failed: {exc}") from exc
        return MetaResponse("".join(content).strip(), model)
