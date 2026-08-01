"""
Boucle ReAct (Reasoning and Acting) pour Nook.

Compatible avec tous les modèles Ollama, y compris les petits SLM qui ne
supportent pas le tool calling natif.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from nook.ollama_client import OllamaClient
from nook.tools import Tool, parse_action_input

# Prompt système structuré pour guider les modèles vers le format ReAct
SYSTEM_PROMPT_TEMPLATE = """Tu es Nook, un assistant personnel local pour un développeur Ubuntu.
Tu réponds en français sauf si l'utilisateur écrit dans une autre langue.
Tu as accès aux outils suivants pour interagir avec le PC :

{tool_descriptions}

Pour utiliser un outil, réponds EXACTEMENT avec ce format (une action à la fois) :
Thought: <ta réflexion courte>
Action: <nom_outil>
Action Input: {{"clé": "valeur"}}

Après réception du résultat (Observation), continue ou conclus.

Quand tu as la réponse finale pour l'utilisateur, utilise :
Thought: <ta réflexion>
Final Answer: <réponse claire et concise>

Règles :
- Une seule Action par message.
- Action Input doit être du JSON valide sur une seule ligne.
- N'invente jamais le résultat d'un outil ; attends l'Observation.
- Pour exécuter une commande terminal et lire son résultat : run_command avec {{"command": "ta commande", "background": false}}.
- Pour ouvrir une app : run_command avec {{"command": "firefox", "background": true}}.
- Pour lire un fichier : read_file avec {{"path": "/chemin/complet"}}.
- Pour lister un dossier : list_directory avec {{"path": "/chemin"}}.
"""


@dataclass
class AgentStep:
    """Une étape visible dans l'interface (pensée, action ou réponse)."""

    kind: str
    content: str


@dataclass
class AgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    error: str | None = None


# Expressions régulières pour parser la sortie du modèle
RE_THOUGHT = re.compile(r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:)|\Z)", re.DOTALL | re.IGNORECASE)
RE_ACTION = re.compile(r"Action:\s*(\w+)", re.IGNORECASE)
RE_ACTION_INPUT = re.compile(r"Action Input:\s*(.+?)(?=\n(?:Thought:|Action:|Final Answer:)|\Z)", re.DOTALL | re.IGNORECASE)
RE_FINAL = re.compile(r"Final Answer:\s*(.+)", re.DOTALL | re.IGNORECASE)


class ReActAgent:
    """Agent conversationnel avec boucle Thought → Action → Observation."""

    def __init__(
        self,
        client: OllamaClient,
        tools: dict[str, Tool],
        max_iterations: int = 8,
        on_step: Callable[[AgentStep], None] | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_iterations = max_iterations
        self.on_step = on_step
        self._history: list[dict[str, str]] = []
        tool_lines = "\n".join(tool.schema_line() for tool in tools.values())
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_descriptions=tool_lines)

    def reset(self) -> None:
        self._history.clear()

    def _emit(self, kind: str, content: str, steps: list[AgentStep]) -> None:
        step = AgentStep(kind, content.strip())
        steps.append(step)
        if self.on_step:
            self.on_step(step)

    def _parse_response(self, text: str) -> tuple[str | None, str | None, dict | None, str | None]:
        """
        Retourne (thought, action_name, action_input_dict, final_answer).
        """
        final_match = RE_FINAL.search(text)
        if final_match:
            thought_match = RE_THOUGHT.search(text)
            thought = thought_match.group(1).strip() if thought_match else None
            return thought, None, None, final_match.group(1).strip()

        action_match = RE_ACTION.search(text)
        if not action_match:
            return None, None, None, text.strip()

        action_name = action_match.group(1).strip().lower()
        thought_match = RE_THOUGHT.search(text)
        thought = thought_match.group(1).strip() if thought_match else None

        input_match = RE_ACTION_INPUT.search(text)
        action_input: dict = {}
        if input_match:
            action_input = parse_action_input(input_match.group(1))

        return thought, action_name, action_input, None

    def run(self, user_message: str) -> AgentResult:
        steps: list[AgentStep] = []
        self._history.append({"role": "user", "content": user_message})

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
            *self._history,
        ]

        for iteration in range(self.max_iterations):
            try:
                response = self.client.chat(messages)
            except Exception as exc:
                return AgentResult("", steps, error=f"Erreur Ollama: {exc}")

            assistant_text = response.content
            self._history.append({"role": "assistant", "content": assistant_text})
            messages.append({"role": "assistant", "content": assistant_text})

            thought, action_name, action_input, final_answer = self._parse_response(assistant_text)

            if thought:
                self._emit("thought", thought, steps)

            if final_answer is not None:
                self._emit("answer", final_answer, steps)
                return AgentResult(final_answer, steps)

            if action_name is None:
                # Le modèle n'a pas suivi le format — renvoyer tel quel
                self._emit("answer", assistant_text, steps)
                return AgentResult(assistant_text, steps)

            if action_name not in self.tools:
                observation = (
                    f"Erreur: outil inconnu '{action_name}'. "
                    f"Outils disponibles: {', '.join(self.tools.keys())}"
                )
            else:
                tool = self.tools[action_name]
                self._emit("action", f"{action_name}({action_input})", steps)
                result = tool.run(action_input or {})
                observation = result.output if result.success else result.output

            self._emit("observation", observation, steps)

            observation_msg = f"Observation: {observation}"
            messages.append({"role": "user", "content": observation_msg})
            self._history.append({"role": "user", "content": observation_msg})

        return AgentResult(
            "J'ai atteint la limite d'itérations sans conclusion. Reformulez votre demande.",
            steps,
            error="max_iterations",
        )
