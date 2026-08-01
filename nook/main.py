#!/usr/bin/env python3
"""
Point d'entrée de Nook.

Application de bureau : lancement via le menu Ubuntu ou ~/.local/bin/nook.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from nook.agent import ReActAgent
from nook.config import load_config
from nook.hotkey import GlobalHotkeyManager
from nook.ollama_client import (
    NoChatModelError,
    OllamaClient,
    OllamaUnavailableError,
)
from nook.tools import build_tools
from nook.ui.main_window import NookWindow


def _resolve_model(client: OllamaClient, preferred: str) -> tuple[str, bool]:
    """
    Détecte le modèle Ollama disponible.

    Retourne (nom_modèle, en_ligne).
    """
    try:
        model = client.detect_model(preferred or None)
        return model, True
    except OllamaUnavailableError:
        return "", False
    except NoChatModelError:
        return "", True


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

    client = OllamaClient(
        base_url=config.ollama.base_url,
        temperature=config.ollama.temperature,
    )

    model_name, online = _resolve_model(client, config.ollama.model)
    if model_name:
        client.set_model(model_name)

    tools = build_tools(config.agent.default_cwd, config.agent.max_file_bytes)
    agent = ReActAgent(
        client=client,
        tools=tools,
        max_iterations=config.ollama.max_iterations,
    )

    window = NookWindow(
        config,
        agent,
        model_name=model_name,
        ollama_online=online,
    )
    window.show()

    def refresh_model() -> None:
        nonlocal model_name, online
        model_name, online = _resolve_model(client, config.ollama.model)
        if model_name:
            client.set_model(model_name)
        window.set_model_info(model_name, online)

    # Re-détection périodique (Ollama démarré après l'app, nouveau modèle pullé)
    refresh_timer = QTimer()
    refresh_timer.setInterval(15000)
    refresh_timer.timeout.connect(refresh_model)
    refresh_timer.start()

    def on_hotkey() -> None:
        window.toggle_visibility_requested.emit()

    hotkey_manager = GlobalHotkeyManager(config.ui.hotkey, on_hotkey)
    try:
        hotkey_manager.start()
    except Exception as e:
        print(f"Warning: Global hotkey disabled ({e})")

    exit_code = app.exec()

    refresh_timer.stop()
    hotkey_manager.stop()
    window.shutdown()
    client.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
