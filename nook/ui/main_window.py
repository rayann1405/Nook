"""
Fenêtre principale Nook — widget ultra-discret ancré en bas à droite.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nook.agent import AgentResult, AgentStep, ReActAgent
from nook.config import AppConfig
from nook.ui.styles import DARK_THEME


class AgentWorker(QThread):
    """Exécute la boucle ReAct dans un thread séparé pour ne pas bloquer l'UI."""

    step_ready = pyqtSignal(str, str)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, agent: ReActAgent, message: str) -> None:
        super().__init__()
        self._agent = agent
        self._message = message

    def run(self) -> None:
        def on_step(step: AgentStep) -> None:
            self.step_ready.emit(step.kind, step.content)

        self._agent.on_step = on_step
        try:
            result = self._agent.run(self._message)
            if result.error and not result.answer:
                self.failed.emit(result.error)
            else:
                self.finished_with_result.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self._agent.on_step = None


class MessageBubble(QWidget):
    """Bulle de message dans l'historique du chat."""

    def __init__(self, role: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if role == "user":
            label.setObjectName("MessageUser")
        elif role == "assistant":
            label.setObjectName("MessageAssistant")
        else:
            label.setObjectName("MessageSystem")

        layout.addWidget(label)


class NookWindow(QWidget):
    """
    Fenêtre frameless toujours au-dessus, verrouillée en bas à droite.

    États :
    - bubble : carré sombre 22×22 px quasi invisible
    - expanded : panneau de chat compact
    """

    toggle_visibility_requested = pyqtSignal()
    model_refresh_requested = pyqtSignal()

    def __init__(
        self,
        config: AppConfig,
        agent: ReActAgent,
        model_name: str = "",
        ollama_online: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.agent = agent
        self._model_name = model_name
        self._ollama_online = ollama_online
        self._expanded = False
        self._visible = True
        self._worker: AgentWorker | None = None
        self._pending_steps: list[tuple[str, str]] = []

        self._bubble_size = config.ui.bubble_size
        self._expanded_width = config.ui.expanded_width
        self._expanded_height = config.ui.expanded_height
        self._margin = config.ui.screen_margin

        self.setObjectName("NookRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(DARK_THEME)

        self._build_ui()
        self._show_expanded()
        self._anchor_bottom_right()

        self.toggle_visibility_requested.connect(self.toggle_visibility)

        # Réancrage si résolution / barre des tâches change
        reposition = QTimer(self)
        reposition.setInterval(2000)
        reposition.timeout.connect(self._anchor_bottom_right)
        reposition.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        # --- Mode bulle : petit carré sombre ---
        self.bubble_frame = QFrame()
        self.bubble_frame.setObjectName("BubbleFrame")
        self.bubble_frame.setFixedSize(self._bubble_size, self._bubble_size)
        self.bubble_frame.setToolTip("Nook — clic pour ouvrir")

        bubble_layout = QVBoxLayout(self.bubble_frame)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dot = QFrame()
        dot.setObjectName("BubbleDot")
        dot.setFixedSize(4, 4)
        bubble_layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Mode déplié ---
        self.panel_frame = QFrame()
        self.panel_frame.setObjectName("PanelFrame")
        self.panel_frame.setFixedSize(self._expanded_width, self._expanded_height)

        panel_layout = QVBoxLayout(self.panel_frame)
        panel_layout.setContentsMargins(10, 8, 10, 10)
        panel_layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("nook")
        title.setObjectName("TitleLabel")
        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        collapse_btn = QPushButton("×")
        collapse_btn.setObjectName("IconButton")
        collapse_btn.setToolTip("Réduire")
        collapse_btn.clicked.connect(self._show_bubble)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status_label)
        header.addWidget(collapse_btn)
        panel_layout.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(2, 2, 2, 2)
        self.chat_layout.setSpacing(3)
        self.chat_layout.addStretch()
        self.scroll_area.setWidget(self.chat_container)
        panel_layout.addWidget(self.scroll_area, stretch=1)

        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setObjectName("ChatInput")
        self.input_field.setPlaceholderText("Message…")
        self.input_field.returnPressed.connect(self._send_message)

        self.send_button = QPushButton("→")
        self.send_button.setObjectName("SendButton")
        self.send_button.setFixedWidth(36)
        self.send_button.clicked.connect(self._send_message)

        input_row.addWidget(self.input_field)
        input_row.addWidget(self.send_button)
        panel_layout.addLayout(input_row)

        self.stack.addWidget(self.bubble_frame)
        self.stack.addWidget(self.panel_frame)
        root.addWidget(self.stack)

        self._apply_bubble_opacity()
        self._update_status_label()

    def _apply_bubble_opacity(self) -> None:
        opacity = max(0.15, min(0.85, self.config.ui.bubble_opacity))
        alpha = int(opacity * 255)
        self.bubble_frame.setStyleSheet(
            f"QFrame#BubbleFrame {{ background-color: rgba(12, 12, 16, {alpha}); "
            f"border: 1px solid rgba(255, 255, 255, 14); border-radius: 5px; }}"
        )

    def _screen_geometry(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    def _anchor_bottom_right(self) -> None:
        """Positionne la fenêtre collée au coin bas-droit (au-dessus de la barre des tâches)."""
        if self._expanded:
            w, h = self._expanded_width, self._expanded_height
        else:
            w, h = self._bubble_size, self._bubble_size

        self.setFixedSize(w, h)

        geo = self._screen_geometry()
        if geo is None:
            return

        x = geo.x() + geo.width() - w - self._margin
        y = geo.y() + geo.height() - h - self._margin
        self.move(x, y)

    def _show_bubble(self) -> None:
        self._expanded = False
        self.stack.setCurrentWidget(self.bubble_frame)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.show()
        self._anchor_bottom_right()

    def _show_expanded(self) -> None:
        self._expanded = True
        self.stack.setCurrentWidget(self.panel_frame)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
        self.show()
        self._anchor_bottom_right()
        self.activateWindow()
        self.input_field.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._anchor_bottom_right()

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
            self._visible = False
        else:
            self.show()
            self.raise_()
            self._anchor_bottom_right()
            self._visible = True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._expanded:
            self._show_expanded()
            event.accept()
            return
        super().mousePressEvent(event)

    def _append_message(self, role: str, text: str) -> None:
        stretch_index = self.chat_layout.count() - 1
        bubble = MessageBubble(role, text)
        self.chat_layout.insertWidget(stretch_index, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_status_label(self) -> None:
        if not self._ollama_online:
            self.status_label.setText("hors ligne")
            self.bubble_frame.setToolTip("Nook — Ollama hors ligne")
            return
        if self._model_name:
            short = self._model_name.split(":")[0]
            if len(short) > 14:
                short = short[:12] + "…"
            self.status_label.setText(short)
            self.bubble_frame.setToolTip(f"Nook — {self._model_name}")
        else:
            self.status_label.setText("")
            self.bubble_frame.setToolTip("Nook")

    def set_model_info(self, model: str, online: bool) -> None:
        self._model_name = model
        self._ollama_online = online
        self._update_status_label()

    def _send_message(self) -> None:
        text = self.input_field.text().strip()
        if not text or (self._worker and self._worker.isRunning()):
            return

        if not self._ollama_online or not self._model_name:
            self._append_message("system", "Ollama indisponible ou aucun modèle détecté.")
            return

        self.input_field.clear()
        self._append_message("user", text)
        self._pending_steps.clear()
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.status_label.setText("…")

        self._worker = AgentWorker(self.agent, text)
        self._worker.step_ready.connect(self._on_agent_step)
        self._worker.finished_with_result.connect(self._on_agent_finished)
        self._worker.failed.connect(self._on_agent_failed)
        self._worker.start()

    def _on_agent_step(self, kind: str, content: str) -> None:
        if kind == "thought":
            self._append_message("system", content)
        elif kind == "action":
            self._append_message("system", f"→ {content}")
        elif kind == "observation":
            preview = content[:240] + ("…" if len(content) > 240 else "")
            self._append_message("system", preview)

    def _on_agent_finished(self, result: AgentResult) -> None:
        self._append_message("assistant", result.answer)
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self._update_status_label()
        self.input_field.setFocus()

    def _on_agent_failed(self, error: str) -> None:
        self._append_message("system", f"Erreur : {error}")
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        self.status_label.setText("erreur")
        self.input_field.setFocus()

    def shutdown(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
