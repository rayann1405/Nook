"""Client HTTP minimal pour l'API chat d'Ollama."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

# Modèles d'embedding exclus de la sélection automatique
_EMBED_HINTS = ("embed", "bge", "nomic-embed", "mxbai-embed", "snowflake-arctic-embed")


class OllamaError(Exception):
    """Erreur générique liée à Ollama."""


class OllamaUnavailableError(OllamaError):
    """Ollama n'est pas joignable sur localhost."""


class NoChatModelError(OllamaError):
    """Aucun modèle de chat utilisable n'est installé."""


@dataclass
class OllamaModelInfo:
    name: str
    modified_at: datetime
    size: int


@dataclass
class OllamaResponse:
    content: str
    model: str
    done: bool


def is_chat_model(name: str) -> bool:
    """Exclut les modèles d'embedding de la sélection automatique."""
    lower = name.lower()
    return not any(hint in lower for hint in _EMBED_HINTS)


class OllamaClient:
    """Encapsule les appels à l'API REST d'Ollama (compatible tout modèle)."""

    def __init__(self, base_url: str, model: str = "", temperature: float = 0.3) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self._client = httpx.Client(timeout=300.0)

    def close(self) -> None:
        self._client.close()

    def set_model(self, model: str) -> None:
        self.model = model

    def health_check(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models_detailed(self) -> list[OllamaModelInfo]:
        response = self._client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        payload = response.json()
        models: list[OllamaModelInfo] = []
        for item in payload.get("models", []):
            name = item.get("name", "")
            if not name:
                continue
            raw_date = item.get("modified_at", "")
            try:
                modified = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                modified = datetime.min
            models.append(
                OllamaModelInfo(
                    name=name,
                    modified_at=modified,
                    size=int(item.get("size", 0)),
                )
            )
        return models

    def list_running_models(self) -> list[str]:
        try:
            response = self._client.get(f"{self.base_url}/api/ps")
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        payload = response.json()
        return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]

    def _match_model(self, query: str, available: list[OllamaModelInfo]) -> str | None:
        query = query.strip()
        names = [m.name for m in available]
        if query in names:
            return query
        for name in names:
            if name.split(":")[0] == query or name.startswith(f"{query}:"):
                return name
        return None

    def detect_model(self, preferred: str | None = None) -> str:
        """
        Détecte automatiquement le modèle Ollama à utiliser.

        Priorité :
        1. Modèle explicitement demandé (config / env) s'il est installé
        2. Modèle actuellement chargé en mémoire (api/ps)
        3. Modèle chat le plus récemment modifié (api/tags)
        """
        if not self.health_check():
            raise OllamaUnavailableError(
                f"Ollama injoignable sur {self.base_url}. "
                "Vérifiez qu'Ollama est démarré (service ollama ou `ollama serve`)."
            )

        all_models = self.list_models_detailed()
        chat_models = [m for m in all_models if is_chat_model(m.name)]

        if preferred:
            matched = self._match_model(preferred, chat_models)
            if matched:
                return matched
            raise NoChatModelError(
                f"Modèle « {preferred} » introuvable. "
                f"Modèles disponibles : {', '.join(m.name for m in chat_models) or 'aucun'}"
            )

        running = self.list_running_models()
        for name in running:
            if is_chat_model(name) and any(m.name == name for m in chat_models):
                return name

        if not chat_models:
            raise NoChatModelError(
                "Aucun modèle de chat installé. Installez-en un : ollama pull llama3.2"
            )

        chat_models.sort(key=lambda m: m.modified_at, reverse=True)
        return chat_models[0].name

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
    ) -> OllamaResponse:
        if not self.model:
            raise OllamaError("Aucun modèle sélectionné.")

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": self.temperature},
        }
        response = self._client.post(f"{self.base_url}/api/chat", json=body)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        return OllamaResponse(
            content=content.strip(),
            model=data.get("model", self.model),
            done=bool(data.get("done", True)),
        )
