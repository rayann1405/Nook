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

_MODIFIER_ALIASES: dict[keyboard.Key, keyboard.Key] = {
    keyboard.Key.ctrl_l: keyboard.Key.ctrl,
    keyboard.Key.ctrl_r: keyboard.Key.ctrl,
    keyboard.Key.alt_l: keyboard.Key.alt,
    keyboard.Key.alt_r: keyboard.Key.alt,
    keyboard.Key.shift_l: keyboard.Key.shift,
    keyboard.Key.shift_r: keyboard.Key.shift,
    keyboard.Key.cmd_l: keyboard.Key.cmd,
    keyboard.Key.cmd_r: keyboard.Key.cmd,
}


def parse_hotkey(hotkey: str) -> set[keyboard.Key | keyboard.KeyCode]:
    """
    Convertit une chaîne du type 'ctrl+alt+space' en ensemble de touches pynput.
    """
    parts = [part.strip().lower() for part in hotkey.split("+") if part.strip()]
    if not parts:
        raise ValueError("Le raccourci ne peut pas être vide.")

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
        self._triggered = False

    def _normalize(self, key: keyboard.Key | keyboard.KeyCode) -> keyboard.Key | keyboard.KeyCode:
        if key in _MODIFIER_ALIASES:
            return _MODIFIER_ALIASES[key]
        if isinstance(key, keyboard.KeyCode) and key.char:
            return keyboard.KeyCode.from_char(key.char.lower())
        return key

    def _target_is_pressed(self) -> bool:
        normalized_pressed = {self._normalize(key) for key in self._pressed}
        return self._target_keys.issubset(normalized_pressed)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        should_trigger = False
        with self._lock:
            self._pressed.add(key)
            if self._target_is_pressed() and not self._triggered:
                self._triggered = True
                should_trigger = True
        if should_trigger:
            self._callback()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            self._pressed.discard(key)
            if not self._target_is_pressed():
                self._triggered = False

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
