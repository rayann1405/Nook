"""Local-first model routing with bounded Meta API fallback."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

import httpx

from nook.meta_client import MetaModelClient
from nook.ollama_client import OllamaClient, OllamaModelInfo, is_chat_model

TokenCallback = Callable[[str], None]
ResetCallback = Callable[[], None]
ProviderCallback = Callable[[str, str], None]


class RouterError(Exception):
    """No configured model provider could complete the request."""


@dataclass
class Generation:
    content: str
    provider: str
    model: str


def available_memory_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="ascii") as meminfo:
            for line in meminfo:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 / 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return pages * page_size / 1024**3
    except (OSError, ValueError, AttributeError):
        return 0.0


def _match_model(query: str, models: list[OllamaModelInfo]) -> str | None:
    query = query.strip().lower()
    for model in models:
        name = model.name.lower()
        if name == query or name.split(":")[0] == query:
            return model.name
    for model in models:
        if model.name.lower().startswith(f"{query}:"):
            return model.name
    return None


class ModelRouter:
    def __init__(
        self,
        ollama: OllamaClient,
        meta: MetaModelClient,
        *,
        mode: str = "auto",
        cloud_enabled: bool = True,
        max_cloud_calls: int = 5,
        preferred_model: str = "auto",
        num_ctx: int = 2048,
        low_memory_threshold_gb: float = 3.0,
        memory_provider: Callable[[], float] = available_memory_gb,
        connectivity_check: Callable[[], bool] | None = None,
    ) -> None:
        self.ollama = ollama
        self.meta = meta
        self.mode = self._validate_mode(mode)
        self.cloud_enabled = cloud_enabled
        self.max_cloud_calls = max(0, max_cloud_calls)
        self.preferred_model = preferred_model or "auto"
        self.num_ctx = max(2048, min(4096, num_ctx))
        self.low_memory_threshold_gb = low_memory_threshold_gb
        self.available_ram_gb = memory_provider()
        self._connectivity_check = connectivity_check or meta.is_reachable
        self._cloud_calls = 0
        self._lock = threading.Lock()
        self._local_lock = threading.Lock()
        self.local_model = ""
        self.local_models: list[str] = []
        self.last_error = ""

    @staticmethod
    def _validate_mode(mode: str) -> str:
        if mode not in {"auto", "local", "cloud"}:
            raise ValueError(f"Unsupported router mode: {mode}")
        return mode

    @property
    def cloud_calls(self) -> int:
        with self._lock:
            return self._cloud_calls

    def available_local_models(self) -> list[str]:
        try:
            self.local_models = [
                model.name
                for model in self.ollama.list_models_detailed()
                if is_chat_model(model.name)
            ]
            return self.local_models
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self.local_models = []
            self.last_error = f"Ollama unavailable: {exc}"
            return []

    def _select_local_model(self) -> str:
        try:
            models = [
                model for model in self.ollama.list_models_detailed()
                if is_chat_model(model.name)
            ]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self.local_models = []
            raise RouterError(f"Local Ollama is unavailable: {exc}") from exc
        self.local_models = [model.name for model in models]
        if not models:
            raise RouterError(
                "No local chat model is installed. Install llama3.2:3b or llama3.2:1b."
            )

        if self.preferred_model.lower() not in {"", "auto", "detect", "automatic"}:
            match = _match_model(self.preferred_model, models)
            if not match:
                raise RouterError(f"Configured local model '{self.preferred_model}' is not installed.")
            return match

        preferred = (
            ("llama3.2:1b", "llama3.2:3b")
            if self.available_ram_gb < self.low_memory_threshold_gb
            else ("llama3.2:3b", "llama3.2:1b")
        )
        for candidate in preferred:
            if match := _match_model(candidate, models):
                return match
        models.sort(key=lambda model: model.modified_at, reverse=True)
        return models[0].name

    def refresh_local_model(self) -> str:
        with self._local_lock:
            try:
                self.local_model = self._select_local_model()
                self.ollama.set_model(self.local_model)
                self.last_error = ""
            except RouterError as exc:
                self.local_model = ""
                self.last_error = str(exc)
        return self.local_model

    def set_local_model(self, model: str) -> None:
        self.preferred_model = model or "auto"
        self.refresh_local_model()

    def _cloud_allowed(self) -> bool:
        if not self.cloud_enabled or not self.meta.configured:
            self.last_error = "Cloud mode needs META_API_KEY and must be enabled."
            return False
        if self.cloud_calls >= self.max_cloud_calls:
            self.last_error = f"Cloud session limit reached ({self.max_cloud_calls} calls)."
            return False
        if not self._connectivity_check():
            self.last_error = "Meta Model API is unreachable; check your internet connection."
            return False
        return True

    def _generate_cloud(
        self,
        messages: list[dict[str, str]],
        stream: bool,
        on_token: TokenCallback | None,
        on_provider: ProviderCallback | None,
    ) -> Generation:
        if not self._cloud_allowed():
            raise RouterError(self.last_error)
        with self._lock:
            if self._cloud_calls >= self.max_cloud_calls:
                raise RouterError(f"Cloud session limit reached ({self.max_cloud_calls} calls).")
            self._cloud_calls += 1
        if on_provider:
            on_provider("cloud", self.meta.model)
        response = self.meta.generate(messages, stream=stream, on_token=on_token)
        return Generation(response.content, "cloud", response.model)

    def _generate_local(
        self,
        messages: list[dict[str, str]],
        stream: bool,
        on_token: TokenCallback | None,
        on_provider: ProviderCallback | None,
    ) -> Generation:
        with self._local_lock:
            model = self._select_local_model()
            self.local_model = model
            self.ollama.set_model(model)
            if on_provider:
                on_provider("local", model)
            try:
                response = self.ollama.chat(
                    messages,
                    stream=stream,
                    on_token=on_token,
                    num_ctx=self.num_ctx,
                )
            except Exception as exc:
                raise RouterError(f"Local model request failed: {exc}") from exc
        return Generation(response.content, "local", response.model)

    def generate(
        self,
        messages: list[dict[str, str]] | str,
        *,
        mode: str | None = None,
        hard: bool = False,
        stream: bool = False,
        on_token: TokenCallback | None = None,
        on_reset: ResetCallback | None = None,
        on_provider: ProviderCallback | None = None,
    ) -> Generation:
        selected_mode = self._validate_mode(mode or self.mode)
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        if selected_mode == "local":
            return self._generate_local(messages, stream, on_token, on_provider)

        if selected_mode == "cloud":
            return self._try_cloud_then_local(
                messages, stream, on_token, on_reset, on_provider
            )

        if hard:
            try:
                return self._generate_cloud(messages, stream, on_token, on_provider)
            except Exception as exc:
                if on_reset:
                    on_reset()
                cloud_error = str(exc)
                try:
                    result = self._generate_local(messages, stream, on_token, on_provider)
                    self.last_error = f"Cloud fallback to local: {cloud_error}"
                    return result
                except Exception as local_exc:
                    raise RouterError(
                        f"Cloud failed ({cloud_error}); local fallback failed ({local_exc})."
                    ) from local_exc

        try:
            return self._generate_local(messages, stream, on_token, on_provider)
        except Exception as local_exc:
            if on_reset:
                on_reset()
            local_error = str(local_exc)
            try:
                result = self._generate_cloud(messages, stream, on_token, on_provider)
                self.last_error = f"Local fallback to cloud: {local_error}"
                return result
            except Exception as cloud_exc:
                raise RouterError(
                    f"Local failed ({local_error}); cloud fallback failed ({cloud_exc})."
                ) from cloud_exc

    def _try_cloud_then_local(
        self,
        messages: list[dict[str, str]],
        stream: bool,
        on_token: TokenCallback | None,
        on_reset: ResetCallback | None,
        on_provider: ProviderCallback | None,
    ) -> Generation:
        try:
            return self._generate_cloud(messages, stream, on_token, on_provider)
        except Exception as cloud_exc:
            if on_reset:
                on_reset()
            try:
                result = self._generate_local(messages, stream, on_token, on_provider)
                self.last_error = f"Cloud fallback to local: {cloud_exc}"
                return result
            except Exception as local_exc:
                raise RouterError(
                    f"Cloud failed ({cloud_exc}); local fallback failed ({local_exc})."
                ) from local_exc
