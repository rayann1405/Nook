"""
Chargement de la configuration Nook.

Priorité : variables d'environnement > ~/.config/nook/config.yaml > défauts.
Le modèle Ollama est détecté automatiquement sauf surcharge explicite.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def install_root() -> Path:
    """Répertoire d'installation (~/.local/share/nook ou sources en dev)."""
    if home := os.environ.get("NOOK_HOME"):
        return Path(home).expanduser().resolve()
    return PACKAGE_ROOT


USER_CONFIG_DIR = Path.home() / ".config" / "nook"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"
BUNDLED_EXAMPLE = install_root() / "config.example.yaml"


def _expand_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = ""  # vide = détection automatique
    temperature: float = 0.3
    max_iterations: int = 8


@dataclass
class UIConfig:
    hotkey: str = "ctrl+alt+space"
    bubble_opacity: float = 0.42
    expanded_width: int = 320
    expanded_height: int = 420
    bubble_size: int = 22
    screen_margin: int = 6


@dataclass
class AgentConfig:
    default_cwd: str = field(default_factory=lambda: str(Path.home()))
    max_file_bytes: int = 65536


@dataclass
class AppConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def ensure_user_config() -> Path:
    """Crée ~/.config/nook/config.yaml à partir de l'exemple si absent."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Mode développement ou environnement restreint
        if BUNDLED_EXAMPLE.is_file():
            return BUNDLED_EXAMPLE
        return PACKAGE_ROOT / "config.yaml"

    if not USER_CONFIG_PATH.is_file():
        if BUNDLED_EXAMPLE.is_file():
            shutil.copy(BUNDLED_EXAMPLE, USER_CONFIG_PATH)
        else:
            USER_CONFIG_PATH.write_text(
                "ollama:\n  base_url: http://localhost:11434\n  model: auto\n",
                encoding="utf-8",
            )
    return USER_CONFIG_PATH


def _build_from_dict(data: dict[str, Any]) -> AppConfig:
    ollama_data = data.get("ollama", {})
    ui_data = data.get("ui", {})
    agent_data = data.get("agent", {})

    raw_model = str(ollama_data.get("model", "") or "").strip()
    if raw_model.lower() in ("", "auto", "detect", "automatic"):
        raw_model = ""

    default_cwd = agent_data.get("default_cwd", str(Path.home()))
    if isinstance(default_cwd, str):
        default_cwd = _expand_path(default_cwd)

    return AppConfig(
        ollama=OllamaConfig(
            base_url=str(ollama_data.get("base_url", "http://localhost:11434")).rstrip("/"),
            model=raw_model,
            temperature=float(ollama_data.get("temperature", 0.3)),
            max_iterations=int(ollama_data.get("max_iterations", 8)),
        ),
        ui=UIConfig(
            hotkey=str(ui_data.get("hotkey", "ctrl+alt+space")).lower().strip(),
            bubble_opacity=float(ui_data.get("bubble_opacity", 0.42)),
            expanded_width=int(ui_data.get("expanded_width", 320)),
            expanded_height=int(ui_data.get("expanded_height", 420)),
            bubble_size=int(ui_data.get("bubble_size", 22)),
            screen_margin=int(ui_data.get("screen_margin", 6)),
        ),
        agent=AgentConfig(
            default_cwd=default_cwd,
            max_file_bytes=int(agent_data.get("max_file_bytes", 65536)),
        ),
    )


def _apply_env(config: AppConfig) -> AppConfig:
    if url := os.environ.get("NOOK_OLLAMA_URL"):
        config.ollama.base_url = url.rstrip("/")
    if model := os.environ.get("NOOK_MODEL"):
        config.ollama.model = model.strip()
    if temp := os.environ.get("NOOK_TEMPERATURE"):
        config.ollama.temperature = float(temp)
    if max_iter := os.environ.get("NOOK_MAX_ITERATIONS"):
        config.ollama.max_iterations = int(max_iter)
    if hotkey := os.environ.get("NOOK_HOTKEY"):
        config.ui.hotkey = hotkey.lower().strip()
    if cwd := os.environ.get("NOOK_DEFAULT_CWD"):
        config.agent.default_cwd = _expand_path(cwd)
    if max_bytes := os.environ.get("NOOK_MAX_FILE_BYTES"):
        config.agent.max_file_bytes = int(max_bytes)
    return config


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or ensure_user_config()
    config = _build_from_dict(_load_yaml(path))
    return _apply_env(config)
