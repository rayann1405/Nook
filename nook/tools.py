"""Outils système exposés à l'agent ReAct."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: str
    requires_confirmation: bool = False


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        raise NotImplementedError

    def schema_line(self) -> str:
        return f"- {self.name}: {self.description}"


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Exécute une commande shell. Les opérations potentiellement destructives nécessitent une confirmation explicite. "
        'Paramètres JSON: {"command": "ls -l", "cwd": "/chemin/optionnel", "background": false}'
    )

    def __init__(self, default_cwd: str) -> None:
        self.default_cwd = default_cwd

    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        raw_command = arguments.get("command", "")
        command = raw_command.strip() if isinstance(raw_command, str) else ""
        if not command:
            return ToolResult(False, "Erreur: le paramètre 'command' est requis.")

        if _is_destructive_command(command) and not confirmed:
            return ToolResult(
                False,
                f"Commande potentiellement destructive :\n{command}",
                requires_confirmation=True,
            )

        cwd_raw = arguments.get("cwd") or self.default_cwd
        cwd = str(Path(str(cwd_raw)).expanduser().resolve())

        if not Path(cwd).is_dir():
            return ToolResult(False, f"Erreur: répertoire introuvable: {cwd}")

        background = arguments.get("background", False)
        if not isinstance(background, bool):
            return ToolResult(False, "Erreur: 'background' doit être true ou false.")
        env = os.environ.copy()
        env.pop("META_API_KEY", None)
        env.pop("MODEL_API_KEY", None)

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
                    check=False,
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

    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        raw_path = arguments.get("path", "")
        raw_path = raw_path.strip() if isinstance(raw_path, str) else ""
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

    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        raw_path = arguments.get("path", self.default_cwd)
        if not isinstance(raw_path, str):
            return ToolResult(False, "Erreur: 'path' doit être une chaîne.")
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


def _is_destructive_command(command: str) -> bool:
    destructive = re.compile(
        r"(?<![\w.-])(?:rm|mv|chmod|chown|dd|mkfs(?:\.\w+)?|wipefs|shred|truncate|"
        r"rmdir|unlink|fdisk|sfdisk|parted|mkswap|wipe|reboot|shutdown)(?![\w.-])|"
        r"\bfind\b[^;\n]*\s-delete\b|\bgit\s+clean\b|\bgit\s+reset\s+--hard\b|"
        r"\bapt(?:-get)?\s+(?:purge|remove)\b|\bdpkg\s+-r\b|"
        r"\bsystemctl\s+(?:stop|disable|mask)\b|\bservice\s+\S+\s+stop\b|"
        r"\bdocker\s+(?:rm|rmi|system\s+prune)\b",
        re.IGNORECASE,
    )
    return bool(destructive.search(command))


class ExplainErrorTool(Tool):
    name = "explain_error"
    description = (
        "Explains a terminal error or traceback in plain language and suggests a likely fix. "
        'Input: {"error": "ModuleNotFoundError: No module named ..."}'
    )

    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        error = arguments.get("error", "")
        if not isinstance(error, str) or not error.strip():
            return ToolResult(False, "Erreur: le champ 'error' est requis.")
        text = error.strip()[:12000]
        lower = text.lower()

        if "modulenotfounderror" in lower or "no module named" in lower:
            module = re.search(r"No module named ['\"]?([^'\"\s]+)", text, re.IGNORECASE)
            package = module.group(1).split(".")[0] if module else "the missing package"
            explanation = (
                f"Python cannot find the '{package}' module in the active environment. "
                f"Install it in that environment with: python -m pip install {package}"
            )
        elif "permissionerror" in lower or "permission denied" in lower:
            explanation = (
                "The process does not have permission to access this file or directory. "
                "Check ownership and permissions first; avoid running broad commands with sudo."
            )
        elif "filenotfounderror" in lower or "no such file or directory" in lower:
            explanation = (
                "A referenced path does not exist. Check the spelling, current working directory, "
                "and whether the file was created."
            )
        elif "connectionrefusederror" in lower or "connection refused" in lower:
            explanation = (
                "The target host refused the connection, usually because its service is stopped "
                "or listening on another address or port."
            )
        elif "syntaxerror" in lower or "indentationerror" in lower:
            explanation = (
                "Python could not parse the source. Check the line reported in the traceback, "
                "including indentation, quotes, and matching brackets."
            )
        elif "timeouterror" in lower or "timed out" in lower:
            explanation = (
                "The operation exceeded its time limit. Check whether the service is responsive "
                "and whether the timeout is appropriate."
            )
        else:
            final_line = text.splitlines()[-1]
            explanation = (
                f"The error indicates: {final_line}. Review the final traceback lines and the "
                "first frame that points to your code; the trace alone does not identify a safe fix."
            )
        return ToolResult(True, explanation)


class OrganizeFilesTool(Tool):
    name = "organize_files"
    description = (
        "Plans a non-recursive file organization by extension. First returns a dry-run plan; "
        "files move only after the user confirms the displayed plan. "
        'Input: {"path": "/folder"}'
    )

    _EXTENSIONS = {
        "Documents": {".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md"},
        "Images": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"},
        "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
        "Audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a"},
        "Archives": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
        "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".sh"},
    }

    def __init__(self, default_cwd: str) -> None:
        self.default_cwd = default_cwd

    def _plan(self, folder: Path) -> list[tuple[Path, Path]]:
        plan = []
        for item in sorted(folder.iterdir(), key=lambda entry: entry.name.lower()):
            if not item.is_file() or item.is_symlink() or item.name.startswith("."):
                continue
            category = next(
                (name for name, extensions in self._EXTENSIONS.items() if item.suffix.lower() in extensions),
                "Other",
            )
            target = folder / category / item.name
            if target.parent == item.parent:
                continue
            plan.append((item, target))
            if len(plan) >= 100:
                break
        return plan

    def run(self, arguments: dict[str, Any], *, confirmed: bool = False) -> ToolResult:
        raw_path = arguments.get("path", self.default_cwd)
        if not isinstance(raw_path, str):
            return ToolResult(False, "Erreur: 'path' doit être une chaîne.")
        folder = Path(raw_path).expanduser().resolve()
        if not folder.is_dir():
            return ToolResult(False, f"Erreur: répertoire introuvable: {folder}")
        try:
            plan = self._plan(folder)
        except OSError as exc:
            return ToolResult(False, f"Erreur de lecture du répertoire: {exc}")
        if not plan:
            return ToolResult(True, f"Aucun fichier à organiser dans {folder}.")

        summary = "\n".join(f"{source.name} -> {target.parent.name}/{target.name}" for source, target in plan)
        if not confirmed:
            return ToolResult(
                True,
                f"Aperçu (aucun fichier déplacé):\n{summary}",
                requires_confirmation=True,
            )

        moved = []
        failures = []
        for source, target in plan:
            try:
                target.parent.mkdir(exist_ok=True)
                if target.exists():
                    failures.append(f"{source.name}: destination déjà présente")
                    continue
                shutil.move(str(source), str(target))
                moved.append(source.name)
            except OSError as exc:
                failures.append(f"{source.name}: {exc}")
        output = f"{len(moved)} fichier(s) déplacé(s): {', '.join(moved)}"
        if failures:
            output += "\nNon déplacés: " + "; ".join(failures)
        return ToolResult(not failures, output)


def build_tools(default_cwd: str, max_file_bytes: int) -> dict[str, Tool]:
    tools: list[Tool] = [
        RunCommandTool(default_cwd),
        ReadFileTool(max_file_bytes),
        ListDirectoryTool(default_cwd),
        ExplainErrorTool(),
        OrganizeFilesTool(default_cwd),
    ]
    return {tool.name: tool for tool in tools}


def parse_action_input(raw: str) -> dict[str, Any]:
    """Parse an action object, tolerating fenced and Python-literal dictionaries."""
    raw = raw.strip()
    if not raw:
        return {}

    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        import ast

        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass
    raise ValueError("Action Input must be a valid JSON object.")
