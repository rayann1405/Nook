"""Styles QSS de l'interface sombre Nook."""

DARK_THEME = """
QWidget#NookRoot {
    background-color: transparent;
}

/* ---------- Bulle discrète ---------- */
QPushButton#BubbleButton {
    background-color: rgba(16, 16, 22, 170);
    color: rgba(225, 228, 240, 235);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#BubbleButton:hover {
    background-color: rgba(44, 52, 78, 220);
    border: 1px solid rgba(120, 150, 230, 160);
}
QPushButton#BubbleButton:pressed {
    background-color: rgba(60, 78, 120, 230);
}

/* ---------- Panneau ---------- */
QFrame#PanelFrame {
    background-color: rgba(16, 17, 23, 246);
    border: 1px solid rgba(255, 255, 255, 34);
    border-radius: 14px;
}

QLabel#TitleLabel {
    color: #eceef6;
    font-size: 13px;
    font-weight: 700;
}

QLabel#StatusDot {
    border-radius: 4px;
}

QLabel#StatusLabel {
    color: #9aa3b8;
    font-size: 10px;
}

QLabel#SectionLabel {
    color: #7f8aa3;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#HintLabel {
    color: #6f7890;
    font-size: 9px;
}

QLabel#ActivityLabel {
    color: #8f9ab3;
    font-size: 10px;
}

QFrame#Divider {
    background-color: rgba(255, 255, 255, 18);
    max-height: 1px;
}

/* ---------- Messages ---------- */
QFrame#UserMessageCard {
    background-color: rgba(64, 92, 156, 120);
    border: 1px solid rgba(110, 145, 220, 70);
    border-radius: 11px;
}
QFrame#AssistantMessageCard {
    background-color: rgba(38, 41, 53, 200);
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 11px;
}
QLabel#UserMessageText {
    color: #eef3ff;
    font-size: 11px;
}
QLabel#AssistantMessageText {
    color: #e4e7ef;
    font-size: 11px;
}
QLabel#RoleLabel {
    color: #78829a;
    font-size: 9px;
    font-weight: 700;
}
QLabel#SystemMessageLabel {
    color: #8aa3c8;
    background-color: rgba(70, 100, 160, 40);
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 10px;
}
QLabel#EmptyStateLabel {
    color: #7c869e;
    font-size: 11px;
}

/* ---------- Réglages ---------- */
QFrame#SettingsCard {
    background-color: rgba(28, 30, 39, 220);
    border: 1px solid rgba(255, 255, 255, 22);
    border-radius: 10px;
}

QLineEdit#ChatInput, QPlainTextEdit#ChatInput, QLineEdit#SettingsInput {
    background-color: rgba(24, 26, 34, 235);
    color: #e7e9f2;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 9px;
    padding: 6px 9px;
    font-size: 11px;
    selection-background-color: #4a6aa8;
}
QLineEdit#ChatInput:focus, QPlainTextEdit#ChatInput:focus, QLineEdit#SettingsInput:focus {
    border: 1px solid rgba(110, 145, 225, 180);
}

QPushButton#SendButton {
    background-color: #4a6aa8;
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 7px 12px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#SendButton:hover {
    background-color: #5a7cbe;
}
QPushButton#SendButton:pressed {
    background-color: #3d578b;
}
QPushButton#SendButton:disabled {
    background-color: rgba(70, 76, 94, 140);
    color: rgba(190, 195, 210, 120);
}

QPushButton#PrimaryButton {
    background-color: #4a6aa8;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 10px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: #5a7cbe;
}

QPushButton#GhostButton {
    background-color: transparent;
    color: #a8b2c8;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 3px 7px;
    font-size: 10px;
}
QPushButton#GhostButton:hover {
    color: #e6e9f2;
    background-color: rgba(255, 255, 255, 16);
    border: 1px solid rgba(255, 255, 255, 24);
}

QPushButton#CloseButton {
    background-color: transparent;
    color: #a8b2c8;
    border: none;
    border-radius: 7px;
    font-size: 15px;
    padding: 0 6px;
}
QPushButton#CloseButton:hover {
    color: #ffffff;
    background-color: rgba(220, 90, 90, 120);
}

QComboBox, QCheckBox {
    color: #dfe3ee;
    font-size: 10px;
    spacing: 5px;
}
QComboBox {
    background-color: rgba(24, 26, 34, 235);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 7px;
    padding: 4px 7px;
    min-height: 16px;
}
QComboBox:hover {
    border: 1px solid rgba(110, 145, 225, 140);
}
QComboBox::drop-down {
    border: none;
    width: 16px;
}
QComboBox QAbstractItemView {
    background-color: #1c1e27;
    color: #e6e8f1;
    border: 1px solid rgba(255, 255, 255, 28);
    selection-background-color: #3d578b;
    outline: none;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 50);
    background-color: rgba(24, 26, 34, 225);
}
QCheckBox::indicator:checked {
    background-color: #4a6aa8;
    border: 1px solid #6e8fd0;
}

QToolButton {
    color: #a7b3cc;
    background: transparent;
    border: none;
    text-align: left;
    font-size: 10px;
    padding: 2px 0;
}
QToolButton:hover {
    color: #e6e9f2;
}

QLabel#AgentStepLabel {
    color: #8d97ae;
    font-size: 9px;
}

/* ---------- Barres de défilement ---------- */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 1px;
}
QScrollBar::handle:vertical {
    background: rgba(120, 130, 155, 120);
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(140, 152, 180, 170);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""
