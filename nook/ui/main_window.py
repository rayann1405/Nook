"""
Fenêtre principale Nook — widget discret ancré en bas à droite.

Deux états : une bulle compacte et un panneau de chat complet avec réglages
intégrés (mode de routage, modèle local, clé Meta, langue).
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QSignalBlocker, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nook.agent import AgentResult, AgentStep, ReActAgent
from nook.config import AppConfig, save_config
from nook.i18n import LANGUAGE_LABELS, normalize_language, tr
from nook.router import ModelRouter
from nook.ui.styles import DARK_THEME

_STATUS_COLORS = {
    "ok": "#57c785",
    "warn": "#e3b341",
    "error": "#e05a5a",
    "idle": "#7c869e",
}


class ModelRefreshWorker(QThread):
    model_ready = pyqtSignal(str, str)

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self._router = router

    def run(self) -> None:
        try:
            model = self._router.refresh_local_model()
            error = self._router.last_error
        except Exception as exc:  # pragma: no cover - defensive
            model = ""
            error = f"Impossible de contacter Ollama : {exc}"
        self.model_ready.emit(model, error)


class MetaCheckWorker(QThread):
    """Vérifie la clé Meta hors du thread Qt pour ne pas figer l'interface."""

    checked = pyqtSignal(bool, str)

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self._router = router

    def run(self) -> None:
        try:
            ok, message = self._router.meta.check_credentials()
        except Exception as exc:  # pragma: no cover - defensive
            ok, message = False, str(exc)
        self.checked.emit(ok, message)


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
    """Bulle de message (utilisateur, assistant ou système)."""

    def __init__(
        self,
        role: str,
        text: str,
        max_width: int,
        language: str = "fr",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.role = role
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 1, 0, 1)
        outer.setSpacing(0)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        if role == "system":
            self.role_label = None
            self.label.setObjectName("SystemMessageLabel")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(self.label)
            return

        card = QFrame()
        card.setObjectName(
            "UserMessageCard" if role == "user" else "AssistantMessageCard"
        )
        card.setMaximumWidth(max_width)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(9, 6, 9, 7)
        card_layout.setSpacing(2)

        self.role_label = QLabel()
        self.role_label.setObjectName("RoleLabel")
        self.label.setObjectName(
            "UserMessageText" if role == "user" else "AssistantMessageText"
        )
        self.set_language(language)

        card_layout.addWidget(self.role_label)
        card_layout.addWidget(self.label)

        if role == "user":
            outer.addStretch(1)
            outer.addWidget(card)
        else:
            outer.addWidget(card)
            outer.addStretch(1)

    def set_language(self, language: str) -> None:
        if self.role_label is None:
            return
        key = "role_user" if self.role == "user" else "role_assistant"
        self.role_label.setText(tr(language, key))

    def set_text(self, text: str) -> None:
        self.label.setText(text)


class ChatInput(QPlainTextEdit):
    """Zone de saisie : Entrée envoie, Maj+Entrée insère un retour à la ligne."""

    submitted = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatInput")
        self.setFixedHeight(54)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class NookWindow(QWidget):
    """Fenêtre frameless toujours au-dessus, verrouillée en bas à droite."""

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
        self._language = normalize_language(config.ui.language)
        config.ui.language = self._language
        self.agent.set_language(self._language)
        self._model_name = model_name
        self._ollama_online = ollama_online
        self._model_error = model_error
        self._expanded = False
        self._visible = True
        self._worker: AgentWorker | None = None
        self._model_refresh_worker: ModelRefreshWorker | None = None
        self._meta_check_worker: MetaCheckWorker | None = None
        self._stream_bubble: MessageBubble | None = None
        self._stream_text = ""
        self._active_provider = ""
        self._active_model = model_name
        self._busy = False
        self._activity_key: str | None = None
        self._activity_params: dict[str, object] = {}
        self._activity_level = "idle"
        self._activity_text = ""
        self._meta_hint_default = True

        self._bubble_size = config.ui.bubble_size
        self._expanded_width = config.ui.expanded_width
        self._expanded_height = config.ui.expanded_height
        self._margin = config.ui.screen_margin
        self._message_max_width = max(180, int(self._expanded_width * 0.8))

        self.setObjectName("NookRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DARK_THEME)

        self._build_ui()
        self._populate_model_combo()
        self._apply_language()
        self._show_expanded()
        self._anchor_bottom_right()

        self.toggle_visibility_requested.connect(self.toggle_visibility)

        reposition = QTimer(self)
        reposition.setInterval(2000)
        reposition.timeout.connect(self._anchor_bottom_right)
        reposition.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        # --- Bulle compacte ---
        self.bubble_button = QPushButton("N")
        self.bubble_button.setObjectName("BubbleButton")
        self.bubble_button.setFixedSize(self._bubble_size, self._bubble_size)
        self.bubble_button.setToolTip(tr(self._language, "bubble_tooltip"))
        self.bubble_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bubble_button.clicked.connect(self._show_expanded)
        self._apply_bubble_opacity()

        # --- Panneau ---
        self.panel_frame = QFrame()
        self.panel_frame.setObjectName("PanelFrame")
        self.panel_frame.setFixedSize(self._expanded_width, self._expanded_height)

        panel = QVBoxLayout(self.panel_frame)
        panel.setContentsMargins(12, 10, 12, 11)
        panel.setSpacing(7)

        panel.addLayout(self._build_header())
        self.settings_card = self._build_settings_card()
        self.settings_card.setVisible(False)
        panel.addWidget(self.settings_card)

        panel.addWidget(self._build_chat_area(), stretch=1)
        panel.addLayout(self._build_steps_area())
        panel.addLayout(self._build_activity_row())
        panel.addLayout(self._build_input_area())
        panel.addWidget(self._hint_label())

        self.stack.addWidget(self.bubble_button)
        self.stack.addWidget(self.panel_frame)
        root.addWidget(self.stack)

        self._update_status_label()

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(8, 8)

        title = QLabel("Nook")
        title.setObjectName("TitleLabel")

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setMaximumWidth(170)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )

        self.new_chat_button = QPushButton(tr(self._language, "new"))
        self.new_chat_button.setObjectName("GhostButton")
        self.new_chat_button.setToolTip(tr(self._language, "new_tooltip"))
        self.new_chat_button.clicked.connect(self._new_conversation)

        self.settings_button = QPushButton(tr(self._language, "settings"))
        self.settings_button.setObjectName("GhostButton")
        self.settings_button.setCheckable(True)
        self.settings_button.setToolTip(tr(self._language, "settings_tooltip"))
        self.settings_button.toggled.connect(self._on_settings_toggled)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("CloseButton")
        self.close_button.setToolTip(tr(self._language, "collapse"))
        self.close_button.clicked.connect(self._show_bubble)

        header.addWidget(self.status_dot)
        header.addWidget(title)
        header.addWidget(self.status_label)
        header.addStretch(1)
        header.addWidget(self.new_chat_button)
        header.addWidget(self.settings_button)
        header.addWidget(self.close_button)
        return header

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("SettingsCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 9)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.connection_label = QLabel(tr(self._language, "connection"))
        self.connection_label.setObjectName("SectionLabel")
        grid.addWidget(self.connection_label, 0, 0, 1, 4)

        self.mode_label = QLabel(tr(self._language, "mode"))
        grid.addWidget(self.mode_label, 1, 0)
        self.mode_combo = QComboBox()
        for key, value in (("auto", "auto"), ("local", "local"), ("cloud", "cloud")):
            self.mode_combo.addItem(tr(self._language, key), value)
        self.mode_combo.setCurrentIndex(
            max(0, self.mode_combo.findData(self.agent.router.mode))
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        grid.addWidget(self.mode_combo, 1, 1)

        self.model_label = QLabel(tr(self._language, "model"))
        grid.addWidget(self.model_label, 1, 2)
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        grid.addWidget(self.model_combo, 1, 3)

        self.cloud_checkbox = QCheckBox(tr(self._language, "cloud_enabled"))
        self.cloud_checkbox.setChecked(self.agent.router.cloud_enabled)
        self.cloud_checkbox.toggled.connect(self._on_cloud_toggled)

        self.hard_checkbox = QCheckBox(tr(self._language, "hard_task"))
        self.hard_checkbox.setToolTip(tr(self._language, "hard_task_tip"))

        options_row = QHBoxLayout()
        options_row.setSpacing(8)
        options_row.addWidget(self.cloud_checkbox)
        options_row.addWidget(self.hard_checkbox)
        options_row.addStretch(1)
        grid.addLayout(options_row, 2, 0, 1, 2)

        language_row = QHBoxLayout()
        language_row.setSpacing(6)
        self.language_label = QLabel(tr(self._language, "language"))
        language_row.addWidget(self.language_label)
        self.language_combo = QComboBox()
        for code, label in LANGUAGE_LABELS.items():
            self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(self._language))
        )
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_row.addWidget(self.language_combo, stretch=1)
        grid.addLayout(language_row, 2, 2, 1, 2)

        divider = QFrame()
        divider.setObjectName("Divider")
        grid.addWidget(divider, 3, 0, 1, 4)

        self.meta_title = QLabel(tr(self._language, "meta_section"))
        self.meta_title.setObjectName("SectionLabel")
        grid.addWidget(self.meta_title, 4, 0, 1, 4)

        self.api_key_input = QLineEdit()
        self.api_key_input.setObjectName("SettingsInput")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(
            tr(self._language, "api_key_placeholder")
        )
        self.api_key_input.setText(self.config.meta.api_key)
        self.api_key_input.returnPressed.connect(self._on_save_meta)
        grid.addWidget(self.api_key_input, 5, 0, 1, 3)

        self.save_meta_button = QPushButton(tr(self._language, "save"))
        self.save_meta_button.setObjectName("PrimaryButton")
        self.save_meta_button.clicked.connect(self._on_save_meta)
        grid.addWidget(self.save_meta_button, 5, 3)

        self.meta_url_input = QLineEdit(self.config.meta.base_url)
        self.meta_url_input.setObjectName("SettingsInput")
        self.meta_url_input.setPlaceholderText("https://api.meta.ai/v1")
        grid.addWidget(self.meta_url_input, 6, 0, 1, 2)

        self.meta_model_input = QLineEdit(self.config.meta.model)
        self.meta_model_input.setObjectName("SettingsInput")
        self.meta_model_input.setPlaceholderText("muse-spark-1.3")
        grid.addWidget(self.meta_model_input, 6, 2, 1, 2)

        self.meta_hint = QLabel(tr(self._language, "meta_hint"))
        self.meta_hint.setObjectName("HintLabel")
        self.meta_hint.setWordWrap(True)
        grid.addWidget(self.meta_hint, 7, 0, 1, 4)

        return card

    def _build_chat_area(self) -> QScrollArea:
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(1, 1, 1, 1)
        self.chat_layout.setSpacing(5)
        self.chat_layout.addStretch(1)

        self.empty_label = QLabel(tr(self._language, "empty_state"))
        self.empty_label.setObjectName("EmptyStateLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.chat_layout.insertWidget(0, self.empty_label)

        self.scroll_area.setWidget(self.chat_container)
        return self.scroll_area

    def _build_steps_area(self) -> QVBoxLayout:
        area = QVBoxLayout()
        area.setSpacing(2)

        self.steps_toggle = QToolButton()
        self.steps_toggle.setText(tr(self._language, "steps", count=0))
        self.steps_toggle.setCheckable(True)
        self.steps_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        area.addWidget(self.steps_toggle)

        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.steps_scroll.setMaximumHeight(96)
        self.steps_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.steps_scroll.setVisible(False)

        steps_container = QWidget()
        self.steps_layout = QVBoxLayout(steps_container)
        self.steps_layout.setContentsMargins(6, 2, 6, 2)
        self.steps_layout.setSpacing(2)
        self.steps_scroll.setWidget(steps_container)
        self.steps_toggle.toggled.connect(self.steps_scroll.setVisible)
        area.addWidget(self.steps_scroll)
        return area

    def _build_activity_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        self.activity_label = QLabel(tr(self._language, "ready"))
        self.activity_label.setObjectName("ActivityLabel")
        row.addWidget(self.activity_label)
        row.addStretch(1)
        self.clear_button = QPushButton(tr(self._language, "clear"))
        self.clear_button.setObjectName("GhostButton")
        self.clear_button.setToolTip(tr(self._language, "clear_tooltip"))
        self.clear_button.clicked.connect(self._new_conversation)
        row.addWidget(self.clear_button)
        return row

    def _build_input_area(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        self.input_field = ChatInput()
        self.input_field.setPlaceholderText(
            tr(self._language, "input_placeholder")
        )
        self.input_field.submitted.connect(self._send_message)

        self.send_button = QPushButton(tr(self._language, "send"))
        self.send_button.setObjectName("SendButton")
        self.send_button.setFixedWidth(74)
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.clicked.connect(self._send_message)

        row.addWidget(self.input_field, stretch=1)
        row.addWidget(self.send_button)
        return row

    def _hint_label(self) -> QLabel:
        self.hint_label = QLabel(tr(self._language, "hint"))
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setWordWrap(True)
        return self.hint_label

    # ------------------------------------------------------------- settings
    def _populate_model_combo(self) -> None:
        if not hasattr(self, "model_combo"):
            return
        blocker = QSignalBlocker(self.model_combo)
        current = self.agent.router.preferred_model or "auto"
        self.model_combo.clear()
        self.model_combo.addItem(tr(self._language, "auto_model"), "auto")

        models: list[str] = []
        for model in (
            *self.agent.router.local_models,
            self._model_name,
            "" if current == "auto" else current,
        ):
            if model and model not in models:
                models.append(model)
        for model in models:
            self.model_combo.addItem(model, model)

        index = self.model_combo.findData(current)
        self.model_combo.setCurrentIndex(max(0, index))
        del blocker

    def _on_settings_toggled(self, visible: bool) -> None:
        self.settings_card.setVisible(visible)
        if visible:
            self.api_key_input.setFocus()

    def _on_mode_changed(self) -> None:
        self.agent.router.mode = str(self.mode_combo.currentData())
        self._persist_settings()
        self._update_status_label()

    def _on_model_changed(self) -> None:
        selected = str(self.model_combo.currentData() or "auto")
        self.agent.router.preferred_model = selected or "auto"
        if selected not in {"", "auto"}:
            self.agent.router.local_model = selected
            self.agent.router.ollama.set_model(selected)
            self._model_name = selected
        self.config.ollama.model = "" if selected == "auto" else selected
        self._model_error = None
        self._persist_settings()
        self._update_status_label()
        self.refresh_local_model()

    def _on_cloud_toggled(self, enabled: bool) -> None:
        self.agent.router.cloud_enabled = enabled
        self.config.router.cloud_enabled = enabled
        self._persist_settings()
        self._update_status_label()

    def _on_language_changed(self) -> None:
        language = normalize_language(str(self.language_combo.currentData()))
        self._language = language
        self.config.ui.language = language
        self.agent.set_language(language)
        self._apply_language()
        self._persist_settings()

    def _apply_language(self) -> None:
        lang = self._language
        self.bubble_button.setToolTip(tr(lang, "bubble_tooltip"))
        self.new_chat_button.setText(tr(lang, "new"))
        self.new_chat_button.setToolTip(tr(lang, "new_tooltip"))
        self.settings_button.setText(tr(lang, "settings"))
        self.settings_button.setToolTip(tr(lang, "settings_tooltip"))
        self.close_button.setToolTip(tr(lang, "collapse"))
        self.connection_label.setText(tr(lang, "connection"))
        self.mode_label.setText(tr(lang, "mode"))
        self.mode_combo.setItemText(0, tr(lang, "auto"))
        self.mode_combo.setItemText(1, tr(lang, "local"))
        self.mode_combo.setItemText(2, tr(lang, "cloud"))
        self.model_label.setText(tr(lang, "model"))
        self.cloud_checkbox.setText(tr(lang, "cloud_enabled"))
        self.hard_checkbox.setText(tr(lang, "hard_task"))
        self.hard_checkbox.setToolTip(tr(lang, "hard_task_tip"))
        self.language_label.setText(tr(lang, "language"))
        self.meta_title.setText(tr(lang, "meta_section"))
        self.api_key_input.setPlaceholderText(tr(lang, "api_key_placeholder"))
        self.save_meta_button.setText(tr(lang, "save"))
        if self._meta_hint_default:
            self.meta_hint.setText(tr(lang, "meta_hint"))
        self.empty_label.setText(tr(lang, "empty_state"))
        self.input_field.setPlaceholderText(tr(lang, "input_placeholder"))
        self.send_button.setText(tr(lang, "send"))
        self.clear_button.setText(tr(lang, "clear"))
        self.clear_button.setToolTip(tr(lang, "clear_tooltip"))
        self.hint_label.setText(tr(lang, "hint"))
        self._update_steps_label()
        self._retranslate_activity()
        for index in range(self.chat_layout.count()):
            bubble = self.chat_layout.itemAt(index).widget()
            if isinstance(bubble, MessageBubble):
                bubble.set_language(lang)
        self._populate_model_combo()
        self._update_status_label()

    def _retranslate_activity(self) -> None:
        if self._activity_key:
            self._set_activity(
                tr(self._language, self._activity_key, **self._activity_params),
                self._activity_level,
                key=self._activity_key,
                **self._activity_params,
            )
        elif self._activity_text:
            self._set_activity(self._activity_text, self._activity_level)

    def _update_steps_label(self) -> None:
        self.steps_toggle.setText(
            tr(self._language, "steps", count=self.steps_layout.count())
        )

    def _on_save_meta(self) -> None:
        key = self.api_key_input.text().strip()
        base_url = self.meta_url_input.text().strip().rstrip("/")
        model = self.meta_model_input.text().strip()

        if not key:
            self._set_activity(
                tr(self._language, "key_missing"), "error", key="key_missing"
            )
            self.api_key_input.setFocus()
            return
        if not base_url.startswith(("http://", "https://")):
            self._set_activity(
                tr(self._language, "invalid_url"), "error", key="invalid_url"
            )
            self.meta_url_input.setFocus()
            return
        if not model:
            self._set_activity(
                tr(self._language, "meta_model_missing"),
                "error",
                key="meta_model_missing",
            )
            self.meta_model_input.setFocus()
            return

        self.config.meta.api_key = key
        self.config.meta.base_url = base_url
        self.config.meta.model = model
        self.agent.router.meta.configure(
            base_url=base_url, model=model, api_key=key
        )
        self.agent.router.last_error = ""
        try:
            save_config(self.config)
        except OSError as exc:
            self._append_message(
                "system",
                tr(self._language, "settings_not_saved", error=exc),
            )
        self._meta_hint_default = False
        self.meta_hint.setText(tr(self._language, "restart_needed"))
        self._update_status_label()
        self._check_meta_credentials()

    def _check_meta_credentials(self) -> None:
        if self._meta_check_worker and self._meta_check_worker.isRunning():
            return
        worker = MetaCheckWorker(self.agent.router)
        self._meta_check_worker = worker
        worker.checked.connect(self._on_meta_checked)
        worker.finished.connect(self._on_meta_check_finished)
        worker.start()

    def _on_meta_checked(self, ok: bool, message: str) -> None:
        self._meta_hint_default = False
        if ok:
            self.meta_hint.setText(
                tr(
                    self._language,
                    "key_validated",
                )
                + f" · {self.agent.router.meta.model}"
            )
            self._set_activity(
                tr(self._language, "key_validated"), "ok", key="key_validated"
            )
        else:
            self.meta_hint.setText(message)
            self._set_activity(message, "error")

    def _on_meta_check_finished(self) -> None:
        worker = self._meta_check_worker
        self._meta_check_worker = None
        if worker:
            worker.deleteLater()

    def _persist_settings(self) -> None:
        self.config.router.mode = self.agent.router.mode
        try:
            save_config(self.config)
        except OSError as exc:
            self._set_activity(
                tr(self._language, "settings_not_saved", error=exc),
                "error",
            )

    # --------------------------------------------------------------- display
    def _apply_bubble_opacity(self) -> None:
        opacity = max(0.6, min(1.0, self.config.ui.bubble_opacity))
        alpha = int(opacity * 255)
        border = max(60, alpha // 3)
        background = f"rgba(24, 32, 52, {alpha})"
        hover = "rgba(74, 106, 168, 245)"
        self.bubble_button.setStyleSheet(
            f"QPushButton#BubbleButton {{ background-color: {background}; "
            f"border: 1px solid rgba(255, 255, 255, {border}); border-radius: 12px; }}"
            f"QPushButton#BubbleButton:hover {{ background-color: {hover}; }}"
        )

    def _screen_geometry(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    def _anchor_bottom_right(self) -> None:
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

    def _set_accept_focus(self, accept: bool) -> None:
        flags = self.windowFlags()
        if accept:
            flags &= ~Qt.WindowType.WindowDoesNotAcceptFocus
        else:
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)

    def _show_bubble(self) -> None:
        self._expanded = False
        self.stack.setCurrentWidget(self.bubble_button)
        self._set_accept_focus(False)
        self.show()
        self._anchor_bottom_right()

    def _show_expanded(self) -> None:
        self._expanded = True
        self.stack.setCurrentWidget(self.panel_frame)
        self._set_accept_focus(True)
        self.show()
        self.raise_()
        self._anchor_bottom_right()
        self.activateWindow()
        self.input_field.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._anchor_bottom_right()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self._expanded:
            self._show_bubble()
            event.accept()
            return
        super().keyPressEvent(event)

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
            self._visible = False
        else:
            self.show()
            self.raise_()
            self._anchor_bottom_right()
            self._visible = True

    def _new_conversation(self) -> None:
        self.agent.reset()
        while self.chat_layout.count() > 2:
            item = self.chat_layout.takeAt(1)
            widget = item.widget()
            if widget is not None and widget is not self.empty_label:
                widget.deleteLater()
        self.empty_label.setVisible(True)
        self._stream_bubble = None
        self._stream_text = ""
        self._active_provider = ""
        self._active_model = self._model_name
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._update_steps_label()
        self.steps_toggle.setChecked(False)
        self._set_activity(tr(self._language, "ready"), "idle", key="ready")
        self._update_status_label()
        self.input_field.setFocus()

    def _append_message(self, role: str, text: str) -> None:
        if role != "system":
            self.empty_label.setVisible(False)
        stretch_index = self.chat_layout.count() - 1
        bubble = MessageBubble(role, text, self._message_max_width, self._language)
        self.chat_layout.insertWidget(stretch_index, bubble)
        QTimer.singleShot(40, self._scroll_to_bottom)
        return bubble

    def _append_agent_step(self, kind: str, content: str) -> None:
        if kind == "thought":
            summary = tr(self._language, "step_thought")
        elif kind == "action":
            summary = tr(self._language, "step_action", name=content)
        elif kind == "observation":
            summary = tr(self._language, "step_observation", text=content[:240])
        elif kind == "confirmation":
            summary = tr(self._language, "step_confirmation", text=content[:200])
        else:
            return

        label = QLabel(summary)
        label.setWordWrap(True)
        label.setObjectName("AgentStepLabel")
        self.steps_layout.addWidget(label)
        self._update_steps_label()

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_activity(
        self,
        text: str,
        level: str = "idle",
        key: str | None = None,
        **params: object,
    ) -> None:
        self._activity_key = key
        self._activity_params = params
        self._activity_level = level
        self._activity_text = text
        self.activity_label.setText(text)
        self._set_dot(level)
        self.bubble_button.setToolTip(f"Nook — {text}")

    def _set_dot(self, level: str) -> None:
        color = _STATUS_COLORS.get(level, _STATUS_COLORS["idle"])
        self.status_dot.setStyleSheet(
            f"QLabel#StatusDot {{ background-color: {color}; border-radius: 4px; }}"
        )

    def _update_status_label(self) -> None:
        router = self.agent.router
        mode = router.mode
        provider = self._active_provider
        lang = self._language

        if provider == "cloud":
            model = self._active_model or router.meta.model
            text = (
                f"{tr(lang, 'cloud')} · {model} · "
                f"{router.cloud_calls}/{router.max_cloud_calls}"
            )
            level = "ok"
        elif provider == "local":
            text = (
                f"{tr(lang, 'local')} · "
                f"{self._active_model or self._model_name or '?'}"
            )
            level = "ok"
        elif mode == "cloud":
            if not router.cloud_enabled:
                text, level = tr(lang, "cloud_off"), "warn"
            elif not router.meta.configured:
                text, level = tr(lang, "cloud_key_required"), "error"
            else:
                text, level = f"{tr(lang, 'cloud')} · {router.meta.model}", "ok"
        elif mode == "local":
            if self._model_name:
                text, level = f"{tr(lang, 'local')} · {self._model_name}", "ok"
            else:
                text, level = tr(lang, "local_unavailable"), "error"
        else:  # auto
            if self._model_name:
                text, level = f"{tr(lang, 'auto')} · {self._model_name}", "ok"
            elif router.meta.configured and router.cloud_enabled:
                text, level = (
                    f"{tr(lang, 'auto')} · {tr(lang, 'cloud')} {router.meta.model}",
                    "ok",
                )
            else:
                text, level = tr(lang, "auto_offline"), "error"

        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self._set_dot(level)
        detail = self._model_error or router.last_error
        if mode == "cloud" and not router.meta.configured:
            detail = tr(lang, "add_key_hint")
        elif mode == "cloud" and not router.cloud_enabled:
            detail = tr(lang, "enable_cloud_hint")
        self.status_label.setToolTip(detail or text)
        self.bubble_button.setToolTip(f"Nook — {detail}" if detail else f"Nook — {text}")

    def set_model_info(self, model: str, online: bool, error: str | None = None) -> None:
        self._model_name = model
        self._ollama_online = online
        self._model_error = error
        self._populate_model_combo()
        self._update_status_label()

    def show_notice(self, message: str) -> None:
        self._append_message("system", message)
        self._set_activity(
            tr(self._language, "information"), "warn", key="information"
        )

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

    # ----------------------------------------------------------------- chat
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.send_button.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.mode_combo.setEnabled(not busy)
        self.model_combo.setEnabled(not busy)
        self.language_combo.setEnabled(not busy)
        self.cloud_checkbox.setEnabled(not busy)
        self.hard_checkbox.setEnabled(not busy)
        self.new_chat_button.setEnabled(not busy)
        self.save_meta_button.setEnabled(not busy)
        if not busy:
            self.input_field.setFocus()

    def _send_message(self) -> None:
        text = self.input_field.toPlainText().strip()
        if not text or self._busy:
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
        self._update_steps_label()
        self.steps_toggle.setChecked(False)
        self._set_busy(True)
        self._set_activity(
            tr(self._language, "thinking"), "warn", key="thinking"
        )

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
        worker = self._worker
        worker.finished.connect(lambda: self._on_agent_worker_finished(worker))
        worker.start()

    def _on_agent_worker_finished(self, worker: AgentWorker) -> None:
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _on_stream_token(self, token: str) -> None:
        if self._stream_bubble is None:
            self.empty_label.setVisible(False)
            self._stream_bubble = MessageBubble(
                "assistant", "", self._message_max_width, self._language
            )
            self.chat_layout.insertWidget(
                self.chat_layout.count() - 1, self._stream_bubble
            )
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
        dialog.setWindowTitle(tr(self._language, "confirm_title"))
        dialog.setText(tr(self._language, "confirm_text"))
        dialog.setInformativeText(prompt)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dialog.button(QMessageBox.StandardButton.Yes).setText(
            tr(self._language, "yes")
        )
        dialog.button(QMessageBox.StandardButton.No).setText(
            tr(self._language, "no")
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        response["confirmed"] = dialog.exec() == QMessageBox.StandardButton.Yes
        ready.set()

    def _on_agent_step(self, kind: str, content: str) -> None:
        self._append_agent_step(kind, content)

    def _on_agent_finished(self, result: AgentResult) -> None:
        if self._stream_bubble:
            self._stream_bubble.set_text(result.answer)
        else:
            self._append_message("assistant", result.answer)
        self._active_provider = result.provider
        self._active_model = result.model
        self._set_activity(tr(self._language, "ready"), "ok", key="ready")
        self._set_busy(False)
        self._update_status_label()

    def _on_agent_failed(self, error: str) -> None:
        self._append_message(
            "system", tr(self._language, "error_prefix", error=error)
        )
        self._set_activity(
            tr(self._language, "request_failed"),
            "error",
            key="request_failed",
        )
        self._set_busy(False)
        self._update_status_label()

    # -------------------------------------------------------------- shutdown
    def shutdown(self) -> None:
        for worker in (
            self._worker,
            self._model_refresh_worker,
            self._meta_check_worker,
        ):
            if worker and worker.isRunning():
                worker.wait()
