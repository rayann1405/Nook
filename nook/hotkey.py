"""Gestionnaire de raccourci clavier global (Linux/X11/Wayland via pynput)."""

from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard


# Mapping des noms de touches vers pynput Key
SPECIAL_KEYS: dict[str, keyboard.Key] = {
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc,
    "escape": keyboard.Key.esc,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "page_up": keyboard.Key.page_up,
    "page_down": keyboard.Key.page_down,
    "insert": keyboard.Key.insert,
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
}


def parse_hotkey(hotkey: str) -> set[keyboard.Key | keyboard.KeyCode]:
    """
    Convertit une chaîne du type 'ctrl+alt+space' en ensemble de touches pynput.
    """
    parts = [part.strip().lower() for part in hotkey.split("+") if part.strip()]
    keys: set[keyboard.Key | keyboard.KeyCode] = set()

    for part in parts:
        if part in ("ctrl", "control"):
            keys.add(keyboard.Key.ctrl)
        elif part in ("alt", "option"):
            keys.add(keyboard.Key.alt)
        elif part in ("shift",):
            keys.add(keyboard.Key.shift)
        elif part in ("super", "meta", "win", "cmd"):
            keys.add(keyboard.Key.cmd)
        elif part in SPECIAL_KEYS:
            keys.add(SPECIAL_KEYS[part])
        elif len(part) == 1:
            keys.add(keyboard.KeyCode.from_char(part))
        else:
            raise ValueError(f"Touche non reconnue dans le raccourci: {part}")

    return keys


class GlobalHotkeyManager:
    """Écoute un raccourci global et invoque un callback sur le thread principal Qt."""

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self._target_keys = parse_hotkey(hotkey)
        self._callback = callback
        self._pressed: set[keyboard.Key | keyboard.KeyCode] = set()
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()

    def _normalize(self, key: keyboard.Key | keyboard.KeyCode) -> keyboard.Key | keyboard.KeyCode:
        if isinstance(key, keyboard.KeyCode) and key.char:
            return keyboard.KeyCode.from_char(key.char.lower())
        return key

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            self._pressed.add(self._normalize(key))
            if self._target_keys.issubset(self._pressed):
                self._callback()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            normalized = self._normalize(key)
            self._pressed.discard(normalized)
            # Nettoyage des modificateurs équivalents
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._pressed.discard(keyboard.Key.ctrl)
            if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._pressed.discard(keyboard.Key.alt)
            if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._pressed.discard(keyboard.Key.shift)

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
