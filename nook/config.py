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

from nook.i18n import normalize_language

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def install_root() -> Path:
    """Répertoire d'installation (~/.local/share/nook ou sources en dev)."""
    if home := os.environ.get("NOOK_HOME"):
        return Path(home).expanduser().resolve()
    return PACKAGE_ROOT


USER_CONFIG_DIR = Path.home() / ".config" / "nook"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"
USER_ENV_PATH = USER_CONFIG_DIR / ".env"
BUNDLED_EXAMPLE = install_root() / "config.example.yaml"


def _expand_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def _dotenv_paths() -> list[Path]:
    """Fichiers .env consultés, du plus prioritaire au moins prioritaire."""
    paths: list[Path] = []
    if explicit := os.environ.get("NOOK_ENV_FILE"):
        paths.append(Path(explicit).expanduser())
    paths.extend([install_root() / ".env", Path.cwd() / ".env", USER_ENV_PATH])
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def load_dotenv() -> None:
    """
    Charge les fichiers .env dans os.environ.

    Les variables déjà définies (shell, système, tests) gardent la priorité :
    .env ne sert qu'à compléter l'environnement. C'est ce qui permet à
    ``META_API_KEY`` placé dans .env d'être réellement pris en compte.
    """
    for path in _dotenv_paths():
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            key, separator, value = line.partition("=")
            if not separator:
                continue
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "auto"
    temperature: float = 0.3
    max_iterations: int = 8
    num_ctx: int = 2048


@dataclass
class RouterConfig:
    mode: str = "auto"
    cloud_enabled: bool = True
    max_cloud_calls: int = 5
    low_memory_threshold_gb: float = 3.0


@dataclass
class MetaConfig:
    base_url: str = "https://api.meta.ai/v1"
    model: str = "muse-spark-1.3"
    api_key: str = ""


@dataclass
class UIConfig:
    language: str = "fr"
    hotkey: str = "ctrl+alt+space"
    bubble_opacity: float = 0.85
    expanded_width: int = 420
    expanded_height: int = 600
    bubble_size: int = 44
    screen_margin: int = 8


@dataclass
class AgentConfig:
    default_cwd: str = field(default_factory=lambda: str(Path.home()))
    max_file_bytes: int = 65536


@dataclass
class AppConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    meta: MetaConfig = field(default_factory=MetaConfig)
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
    router_data = data.get("router", {})
    meta_data = data.get("meta", {})
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
            num_ctx=max(2048, min(4096, int(ollama_data.get("num_ctx", 2048)))),
        ),
        router=RouterConfig(
            mode=str(router_data.get("mode", "auto")).lower().strip(),
            cloud_enabled=bool(router_data.get("cloud_enabled", True)),
            max_cloud_calls=max(0, int(router_data.get("max_cloud_calls", 5))),
            low_memory_threshold_gb=float(
                router_data.get("low_memory_threshold_gb", 3.0)
            ),
        ),
        meta=MetaConfig(
            base_url=str(meta_data.get("base_url", "https://api.meta.ai/v1")).rstrip("/"),
            model=str(meta_data.get("model", "muse-spark-1.3")).strip(),
            api_key=str(meta_data.get("api_key", "") or "").strip(),
        ),
        ui=UIConfig(
            language=normalize_language(
                str(ui_data.get("language", "fr") or "fr")
            ),
            hotkey=str(ui_data.get("hotkey", "ctrl+alt+space")).lower().strip(),
            bubble_opacity=max(
                0.6, min(1.0, float(ui_data.get("bubble_opacity", 0.85)))
            ),
            expanded_width=max(
                400, min(760, int(ui_data.get("expanded_width", 420)))
            ),
            expanded_height=max(
                560, min(1000, int(ui_data.get("expanded_height", 600)))
            ),
            bubble_size=max(40, min(72, int(ui_data.get("bubble_size", 44)))),
            screen_margin=max(0, min(64, int(ui_data.get("screen_margin", 8)))),
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
    if num_ctx := os.environ.get("NOOK_NUM_CTX"):
        config.ollama.num_ctx = max(2048, min(4096, int(num_ctx)))
    if mode := os.environ.get("NOOK_MODE"):
        config.router.mode = mode.lower().strip()
    if cloud_enabled := os.environ.get("NOOK_CLOUD_ENABLED"):
        config.router.cloud_enabled = cloud_enabled.lower().strip() in {"1", "true", "yes", "on"}
    if max_cloud_calls := os.environ.get("NOOK_MAX_CLOUD_CALLS"):
        config.router.max_cloud_calls = max(0, int(max_cloud_calls))
    if base_url := os.environ.get("META_API_BASE_URL"):
        config.meta.base_url = base_url.rstrip("/")
    if model := os.environ.get("META_MODEL"):
        config.meta.model = model.strip()
    if api_key := (os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        config.meta.api_key = api_key.strip()
    if hotkey := os.environ.get("NOOK_HOTKEY"):
        config.ui.hotkey = hotkey.lower().strip()
    if language := os.environ.get("NOOK_LANGUAGE"):
        config.ui.language = normalize_language(language)
    if cwd := os.environ.get("NOOK_DEFAULT_CWD"):
        config.agent.default_cwd = _expand_path(cwd)
    if max_bytes := os.environ.get("NOOK_MAX_FILE_BYTES"):
        config.agent.max_file_bytes = int(max_bytes)
    return config


def load_config(config_path: Path | None = None) -> AppConfig:
    load_dotenv()
    path = config_path or ensure_user_config()
    config = _build_from_dict(_load_yaml(path))
    return _apply_env(config)


def save_config(config: AppConfig, config_path: Path | None = None) -> Path:
    """Écrit la configuration utilisateur (dont la clé Meta) et la protège."""
    path = config_path or USER_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ollama": {
            "base_url": config.ollama.base_url,
            "model": config.ollama.model or "auto",
            "temperature": config.ollama.temperature,
            "max_iterations": config.ollama.max_iterations,
            "num_ctx": config.ollama.num_ctx,
        },
        "router": {
            "mode": config.router.mode,
            "cloud_enabled": config.router.cloud_enabled,
            "max_cloud_calls": config.router.max_cloud_calls,
            "low_memory_threshold_gb": config.router.low_memory_threshold_gb,
        },
        "meta": {
            "base_url": config.meta.base_url,
            "model": config.meta.model,
            "api_key": config.meta.api_key,
        },
        "ui": {
            "language": config.ui.language,
            "hotkey": config.ui.hotkey,
            "bubble_opacity": config.ui.bubble_opacity,
            "expanded_width": config.ui.expanded_width,
            "expanded_height": config.ui.expanded_height,
            "bubble_size": config.ui.bubble_size,
            "screen_margin": config.ui.screen_margin,
        },
        "agent": {
            "default_cwd": config.agent.default_cwd,
            "max_file_bytes": config.agent.max_file_bytes,
        },
    }
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
