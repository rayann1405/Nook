#!/usr/bin/env python3
"""
Point d'entrée de Nook.

Application de bureau : lancement via le menu Ubuntu ou ~/.local/bin/nook.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from nook.agent import ReActAgent
from nook.config import load_config
from nook.hotkey import GlobalHotkeyManager
from nook.meta_client import MetaModelClient
from nook.ollama_client import OllamaClient
from nook.router import ModelRouter
from nook.tools import build_tools
from nook.ui.main_window import NookWindow


def main() -> int:
    config = load_config()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Nook")
    app.setApplicationDisplayName("Nook")
    app.setQuitOnLastWindowClosed(True)
    app.setDesktopFileName("nook")
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "nook.svg"
    app.setWindowIcon(QIcon(str(icon_path)))

    ollama = OllamaClient(
        base_url=config.ollama.base_url,
        temperature=config.ollama.temperature,
    )
    meta = MetaModelClient(config.meta.base_url, config.meta.model)
    router = ModelRouter(
        ollama,
        meta,
        mode=config.router.mode,
        cloud_enabled=config.router.cloud_enabled,
        max_cloud_calls=config.router.max_cloud_calls,
        preferred_model=config.ollama.model,
        num_ctx=config.ollama.num_ctx,
        low_memory_threshold_gb=config.router.low_memory_threshold_gb,
    )
    tools = build_tools(config.agent.default_cwd, config.agent.max_file_bytes)
    agent = ReActAgent(
        router=router,
        tools=tools,
        max_iterations=config.ollama.max_iterations,
    )

    window = NookWindow(
        config,
        agent,
        model_name="",
        ollama_online=False,
        model_error="Checking local Ollama…",
    )
    window.show()
    window.refresh_local_model()
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        window.show_notice(
            "Wayland may limit global shortcuts and always-on-top behavior. "
            "Use the Nook app menu if the shortcut does not work."
        )

    # Re-détection périodique (Ollama démarré après l'app, nouveau modèle pullé)
    refresh_timer = QTimer()
    refresh_timer.setInterval(15000)
    refresh_timer.timeout.connect(window.refresh_local_model)
    refresh_timer.start()

    def on_hotkey() -> None:
        window.toggle_visibility_requested.emit()

    hotkey_manager = GlobalHotkeyManager(config.ui.hotkey, on_hotkey)
    try:
        hotkey_manager.start()
    except Exception as e:
        window.show_notice(
            f"Global shortcut unavailable ({e}). You can still open Nook from the app menu."
        )

    exit_code = app.exec()

    refresh_timer.stop()
    hotkey_manager.stop()
    window.shutdown()
    ollama.close()
    meta.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
