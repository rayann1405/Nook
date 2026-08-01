"""Outils système exposés à l'agent ReAct."""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: str


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    def schema_line(self) -> str:
        return f"- {self.name}: {self.description}"


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Exécute une commande shell et retourne la sortie (bloquant, max 15s) ou lance en tâche de fond. "
        'Paramètres JSON: {"command": "ls -l", "cwd": "/chemin/optionnel", "background": false}'
    )

    def __init__(self, default_cwd: str) -> None:
        self.default_cwd = default_cwd

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command", "").strip()
        if not command:
            return ToolResult(False, "Erreur: le paramètre 'command' est requis.")

        cwd_raw = arguments.get("cwd") or self.default_cwd
        cwd = str(Path(str(cwd_raw)).expanduser().resolve())

        if not Path(cwd).is_dir():
            return ToolResult(False, f"Erreur: répertoire introuvable: {cwd}")

        background = arguments.get("background", False)
        env = os.environ.copy()

        try:
            if background:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return ToolResult(
                    True,
                    f"Commande lancée en arrière-plan (PID {process.pid}) dans {cwd}: {command}",
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                output = result.stdout + result.stderr
                if not output.strip():
                    output = "Commande exécutée avec succès sans sortie visible."
                return ToolResult(
                    result.returncode == 0,
                    f"Code retour: {result.returncode}\nSortie:\n{output.strip()}"
                )
        except subprocess.TimeoutExpired as exc:
            partial_out = ""
            if exc.stdout:
                partial_out = exc.stdout.decode('utf-8', 'replace') if isinstance(exc.stdout, bytes) else str(exc.stdout)
            return ToolResult(False, f"Erreur: Délai dépassé (15s). Sortie partielle:\n{partial_out}")
        except OSError as exc:
            return ToolResult(False, f"Erreur d'exécution: {exc}")


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Lit le contenu textuel d'un fichier local. "
        'Paramètres JSON: {"path": "/chemin/vers/fichier"}'
    )

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", "").strip()
        if not raw_path:
            return ToolResult(False, "Erreur: le paramètre 'path' est requis.")

        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            return ToolResult(False, f"Erreur: fichier introuvable: {path}")

        size = path.stat().st_size
        if size > self.max_bytes:
            return ToolResult(
                False,
                f"Erreur: fichier trop volumineux ({size} octets, max {self.max_bytes}).",
            )

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(False, f"Erreur de lecture: {exc}")

        header = f"--- {path} ({size} octets) ---\n"
        return ToolResult(True, header + content)


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = (
        "Liste les fichiers et dossiers d'un répertoire. "
        'Paramètres JSON: {"path": "/chemin/vers/dossier"}'
    )

    def __init__(self, default_cwd: str) -> None:
        self.default_cwd = default_cwd

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path", self.default_cwd)
        path = Path(str(raw_path)).expanduser().resolve()

        if not path.is_dir():
            return ToolResult(False, f"Erreur: répertoire introuvable: {path}")

        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            return ToolResult(False, f"Erreur de listage: {exc}")

        lines: list[str] = [f"Contenu de {path}:"]
        for entry in entries[:200]:
            kind = "d" if entry.is_dir() else "f"
            lines.append(f"  [{kind}] {entry.name}")
        if len(entries) > 200:
            lines.append(f"  ... ({len(entries) - 200} entrées supplémentaires)")
        return ToolResult(True, "\n".join(lines))


def build_tools(default_cwd: str, max_file_bytes: int) -> dict[str, Tool]:
    tools: list[Tool] = [
        RunCommandTool(default_cwd),
        ReadFileTool(max_file_bytes),
        ListDirectoryTool(default_cwd),
    ]
    return {tool.name: tool for tool in tools}


def parse_action_input(raw: str) -> dict[str, Any]:
    """Parse l'entrée JSON d'une action ReAct, tolérant aux petits modèles."""
    raw = raw.strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: chaîne simple interprétée comme commande ou chemin
    if raw.startswith("{") and raw.endswith("}"):
        try:
            fixed = raw.replace("'", '"')
            parsed = json.loads(fixed)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {"command": raw} if " " in raw or raw.startswith("/") else {"path": raw}
