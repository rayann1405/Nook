"""Styles QSS pour l'interface ultra-discrète de Nook."""

DARK_THEME = """
QWidget#NookRoot {
    background-color: transparent;
}

QFrame#BubbleFrame {
    background-color: rgba(16, 16, 20, 95);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 5px;
}

QFrame#BubbleDot {
    background-color: rgba(120, 120, 130, 140);
    border-radius: 2px;
}

QFrame#PanelFrame {
    background-color: rgba(14, 14, 18, 238);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 10px;
}

QLabel#TitleLabel {
    color: rgba(200, 200, 210, 200);
    font-size: 11px;
    font-weight: 500;
}

QLabel#StatusLabel {
    color: rgba(130, 130, 145, 180);
    font-size: 10px;
}

QLabel#MessageUser {
    color: rgba(190, 210, 245, 230);
    font-size: 11px;
    padding: 5px 7px;
    background-color: rgba(50, 70, 110, 70);
    border-radius: 6px;
}

QLabel#MessageAssistant {
    color: rgba(220, 220, 228, 235);
    font-size: 11px;
    padding: 5px 7px;
    background-color: rgba(32, 32, 40, 100);
    border-radius: 6px;
}

QLabel#MessageSystem {
    color: rgba(120, 150, 120, 170);
    font-size: 10px;
    font-style: italic;
}

QLineEdit#ChatInput {
    background-color: rgba(24, 24, 30, 210);
    color: rgba(230, 230, 235, 230);
    border: 1px solid rgba(255, 255, 255, 22);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}

QLineEdit#ChatInput:focus {
    border: 1px solid rgba(90, 120, 200, 150);
}

QPushButton#SendButton {
    background-color: rgba(55, 85, 150, 180);
    color: rgba(240, 240, 245, 230);
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}

QPushButton#SendButton:hover {
    background-color: rgba(70, 100, 170, 200);
}

QPushButton#SendButton:disabled {
    background-color: rgba(40, 40, 48, 120);
    color: rgba(150, 150, 160, 120);
}

QPushButton#IconButton {
    background-color: transparent;
    color: rgba(170, 170, 180, 180);
    border: none;
    font-size: 13px;
    padding: 0 4px;
}

QPushButton#IconButton:hover {
    color: rgba(220, 220, 228, 220);
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 1px;
}

QScrollBar::handle:vertical {
    background: rgba(100, 100, 115, 100);
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
