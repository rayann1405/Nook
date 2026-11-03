"""
Fenêtre principale Nook — widget ultra-discret ancré en bas à droite.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QSignalBlocker, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nook.agent import AgentResult, AgentStep, ReActAgent
from nook.config import AppConfig
from nook.router import ModelRouter
from nook.ui.styles import DARK_THEME, LIGHT_THEME


class ModelRefreshWorker(QThread):
    model_ready = pyqtSignal(str, str)

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self._router = router

    def run(self) -> None:
        try:
            model = self._router.refresh_local_model()
            error = self._router.last_error
        except Exception as exc:
            model = ""
            error = f"Could not check Ollama: {exc}"
        self.model_ready.emit(model, error)


class AgentWorker(QThread):
    """Exécute la boucle ReAct dans un thread séparé pour ne pas bloquer l'UI."""

    step_ready = pyqtSignal(str, str)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)
    token_ready = pyqtSignal(str)
    provider_ready = pyqtSignal(str, str)
    stream_reset = pyqtSignal()
    confirmation_requested = pyqtSignal(str, object)

    def __init__(self, agent: ReActAgent, message: str, mode: str, hard: bool) -> None:
        super().__init__()
        self._agent = agent
        self._message = message
        self._mode = mode
        self._hard = hard

    def _confirm(self, prompt: str) -> bool:
        response = {"confirmed": False}
        ready = threading.Event()
        self.confirmation_requested.emit(prompt, (ready, response))
        ready.wait()
        return response["confirmed"]

    def run(self) -> None:
        def on_step(step: AgentStep) -> None:
            self.step_ready.emit(step.kind, step.content)

        self._agent.on_step = on_step
        try:
            result = self._agent.run(
                self._message,
                mode=self._mode,
                hard=self._hard,
                on_token=self.token_ready.emit,
                on_reset=self.stream_reset.emit,
                on_provider=self.provider_ready.emit,
                confirm_action=self._confirm,
            )
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

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if role == "user":
            self.label.setObjectName("MessageUser")
        elif role == "assistant":
            self.label.setObjectName("MessageAssistant")
        else:
            self.label.setObjectName("MessageSystem")

        layout.addWidget(self.label)

    def set_text(self, text: str) -> None:
        self.label.setText(text)


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
        model_error: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.agent = agent
        self._model_name = model_name
        self._ollama_online = ollama_online
        self._model_error = model_error
        self._expanded = False
        self._visible = True
        self._worker: AgentWorker | None = None
        self._model_refresh_worker: ModelRefreshWorker | None = None
        self._stream_bubble: MessageBubble | None = None
        self._stream_text = ""
        self._active_provider = ""
        self._active_model = model_name

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
        self.setStyleSheet(LIGHT_THEME if config.ui.theme == "light" else DARK_THEME)

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
        title = QLabel("Nook")
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

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Mode"))
        self.mode_combo = QComboBox()
        for label, value in (("Auto", "auto"), ("Local", "local"), ("Cloud", "cloud")):
            self.mode_combo.addItem(label, value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.agent.router.mode)))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        model_row.addWidget(self.mode_combo, stretch=1)
        model_row.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self._populate_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_combo, stretch=1)
        panel_layout.addLayout(model_row)

        options_row = QHBoxLayout()
        self.cloud_checkbox = QCheckBox("Cloud enabled")
        self.cloud_checkbox.setChecked(self.agent.router.cloud_enabled)
        self.cloud_checkbox.toggled.connect(self._on_cloud_toggled)
        self.hard_checkbox = QCheckBox("Hard task")
        options_row.addWidget(self.cloud_checkbox)
        options_row.addWidget(self.hard_checkbox)
        panel_layout.addLayout(options_row)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setCurrentIndex(
            max(0, self.theme_combo.findData(self.config.ui.theme))
        )
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        panel_layout.addLayout(theme_row)

        self.activity_label = QLabel("Ready")
        self.activity_label.setObjectName("ActivityLabel")
        panel_layout.addWidget(self.activity_label)

        self.steps_toggle = QToolButton()
        self.steps_toggle.setText("Agent steps (0)")
        self.steps_toggle.setCheckable(True)
        self.steps_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        panel_layout.addWidget(self.steps_toggle)
        self.steps_panel = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_panel)
        self.steps_layout.setContentsMargins(6, 2, 6, 2)
        self.steps_panel.setMaximumHeight(100)
        self.steps_panel.setVisible(False)
        self.steps_toggle.toggled.connect(self.steps_panel.setVisible)
        panel_layout.addWidget(self.steps_panel)

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

    def _populate_model_combo(self) -> None:
        blocker = QSignalBlocker(self.model_combo)
        models = self.agent.router.local_models
        for model in ("llama3.2:3b", "llama3.2:1b", *models):
            if self.model_combo.findText(model) == -1:
                self.model_combo.addItem(model)
        self.model_combo.insertItem(0, "Automatic", "auto")
        selected = self.agent.router.preferred_model
        index = 0 if selected.lower() in {"", "auto", "detect", "automatic"} else self.model_combo.findText(selected)
        self.model_combo.setCurrentIndex(max(0, index))
        del blocker

    def _on_mode_changed(self) -> None:
        self.agent.router.mode = str(self.mode_combo.currentData())
        self._update_status_label()

    def _on_model_changed(self) -> None:
        self.agent.router.set_local_model(
            str(self.model_combo.currentData() or self.model_combo.currentText())
        )
        self._model_name = self.agent.router.local_model
        self._model_error = self.agent.router.last_error or None
        self._update_status_label()

    def _on_cloud_toggled(self, enabled: bool) -> None:
        self.agent.router.cloud_enabled = enabled
        self._update_status_label()

    def _on_theme_changed(self) -> None:
        theme = str(self.theme_combo.currentData())
        self.config.ui.theme = theme
        self.setStyleSheet(LIGHT_THEME if theme == "light" else DARK_THEME)

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

    def _append_agent_step(self, kind: str, content: str) -> None:
        if kind == "thought":
            summary = content
            self.activity_label.setText("Thinking…")
        elif kind == "action":
            summary = f"Running tool: {content}"
            self.activity_label.setText(summary)
        elif kind == "observation":
            summary = f"Result: {content[:240]}"
            self.activity_label.setText("Thinking…")
        elif kind == "confirmation":
            summary = f"Waiting for confirmation: {content[:200]}"
        else:
            return

        label = QLabel(summary)
        label.setWordWrap(True)
        label.setObjectName("AgentStepLabel")
        self.steps_layout.addWidget(label)
        count = self.steps_layout.count()
        self.steps_toggle.setText(f"Agent steps ({count})")

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _update_status_label(self) -> None:
        if self._active_provider:
            model = self._active_model or self._model_name
            provider = "Cloud" if self._active_provider == "cloud" else "Local"
            suffix = (
                f" · {self.agent.router.cloud_calls}/{self.agent.router.max_cloud_calls}"
                if provider == "Cloud"
                else ""
            )
            self.status_label.setText(f"{provider} · {model}{suffix}")
        elif (
            self.agent.router.mode == "cloud"
            and not self.agent.router.meta.configured
        ):
            self.status_label.setText("Cloud · API key missing")
        elif self.agent.router.mode == "cloud" or (
            self.agent.router.cloud_enabled and self.agent.router.meta.configured and not self._model_name
        ):
            self.status_label.setText(f"Cloud · {self.agent.router.meta.model}")
        elif self._model_name:
            self.status_label.setText(f"Local · {self._model_name}")
        else:
            self.status_label.setText("Local indisponible")
        detail = self._model_error or self.agent.router.last_error
        if (
            self.agent.router.mode == "cloud"
            and self.agent.router.cloud_enabled
            and not self.agent.router.meta.configured
        ):
            detail = "Set META_API_KEY to enable Meta Model API."
        self.bubble_frame.setToolTip(f"Nook — {detail}" if detail else "Nook")

    def set_model_info(self, model: str, online: bool, error: str | None = None) -> None:
        self._model_name = model
        self._ollama_online = online
        self._model_error = error
        for available_model in self.agent.router.local_models:
            if self.model_combo.findText(available_model) < 0:
                self.model_combo.addItem(available_model)
        self._update_status_label()

    def show_notice(self, message: str) -> None:
        self._append_message("system", message)
        self.activity_label.setText("Notice")

    def refresh_local_model(self) -> None:
        if self._model_refresh_worker and self._model_refresh_worker.isRunning():
            return
        if self._worker and self._worker.isRunning():
            return

        worker = ModelRefreshWorker(self.agent.router)
        self._model_refresh_worker = worker
        worker.model_ready.connect(self._on_model_refresh_ready)
        worker.finished.connect(self._on_model_refresh_finished)
        worker.start()

    def _on_model_refresh_ready(self, model: str, error: str) -> None:
        self.set_model_info(model, bool(model), error or None)

    def _on_model_refresh_finished(self) -> None:
        worker = self._model_refresh_worker
        self._model_refresh_worker = None
        if worker:
            worker.deleteLater()

    def _send_message(self) -> None:
        text = self.input_field.text().strip()
        if not text or (self._worker and self._worker.isRunning()):
            return

        self.input_field.clear()
        self._append_message("user", text)
        self._stream_bubble = None
        self._stream_text = ""
        self._active_provider = ""
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.steps_toggle.setText("Agent steps (0)")
        self.steps_toggle.setChecked(False)
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.mode_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.cloud_checkbox.setEnabled(False)
        self.hard_checkbox.setEnabled(False)
        self.activity_label.setText("Thinking…")

        self._worker = AgentWorker(
            self.agent,
            text,
            str(self.mode_combo.currentData()),
            self.hard_checkbox.isChecked(),
        )
        self._worker.step_ready.connect(self._on_agent_step)
        self._worker.finished_with_result.connect(self._on_agent_finished)
        self._worker.failed.connect(self._on_agent_failed)
        self._worker.token_ready.connect(self._on_stream_token)
        self._worker.provider_ready.connect(self._on_provider_ready)
        self._worker.stream_reset.connect(self._on_stream_reset)
        self._worker.confirmation_requested.connect(self._on_confirmation_requested)
        self._worker.start()

    def _on_stream_token(self, token: str) -> None:
        if self._stream_bubble is None:
            self._stream_bubble = MessageBubble("assistant", "")
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._stream_bubble)
        self._stream_text += token
        self._stream_bubble.set_text(self._stream_text)
        self._scroll_to_bottom()

    def _on_provider_ready(self, provider: str, model: str) -> None:
        self._active_provider = provider
        self._active_model = model
        self._update_status_label()

    def _on_stream_reset(self) -> None:
        self._stream_text = ""
        if self._stream_bubble:
            self._stream_bubble.set_text("")

    def _on_confirmation_requested(self, prompt: str, payload: object) -> None:
        ready, response = payload
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Confirm action")
        dialog.setText("Nook requests permission to perform this action:")
        dialog.setInformativeText(prompt)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        response["confirmed"] = dialog.exec() == QMessageBox.StandardButton.Yes
        ready.set()

    def _on_agent_step(self, kind: str, content: str) -> None:
        self._append_agent_step(kind, content)

    def _set_worker_controls_enabled(self, enabled: bool) -> None:
        self.send_button.setEnabled(enabled)
        self.input_field.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.cloud_checkbox.setEnabled(enabled)
        self.hard_checkbox.setEnabled(enabled)

    def _on_agent_finished(self, result: AgentResult) -> None:
        if self._stream_bubble:
            self._stream_bubble.set_text(result.answer)
        else:
            self._append_message("assistant", result.answer)
        self._active_provider = result.provider
        self._active_model = result.model
        self.activity_label.setText("Ready")
        self._set_worker_controls_enabled(True)
        self._update_status_label()
        self.input_field.setFocus()

    def _on_agent_failed(self, error: str) -> None:
        self._append_message("system", f"Erreur : {error}")
        self.activity_label.setText("Request failed")
        self._set_worker_controls_enabled(True)
        self._update_status_label()
        self.input_field.setFocus()

    def shutdown(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        if self._model_refresh_worker and self._model_refresh_worker.isRunning():
            self._model_refresh_worker.wait()
