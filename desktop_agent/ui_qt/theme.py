from __future__ import annotations


APP_STYLESHEET = """
QMainWindow,
QDialog,
QWidget#AppRoot {
    background: #edf2f7;
}

QWidget {
    color: #0f172a;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 13px;
}

QFrame[card="true"] {
    background: #ffffff;
    border: 1px solid #dbe3ec;
    border-radius: 18px;
}

QLabel[role="title"] {
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
    padding: 4px 0 6px 0;
    min-height: 48px;
}

QLabel[role="subtitle"] {
    color: #475569;
    font-size: 13px;
    padding: 1px 0 2px 0;
}

QLabel[role="section"] {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    padding: 2px 0 4px 0;
    min-height: 28px;
}

QLabel[role="meta"] {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
}

QLabel[role="value"] {
    color: #0f172a;
    font-size: 13px;
}

QLabel[role="hint"] {
    color: #475569;
    font-size: 12px;
    padding: 1px 0;
}

QPushButton {
    border-radius: 12px;
    padding: 0 16px;
    border: 1px solid #d6deea;
    background: #ffffff;
    color: #0f172a;
    font-weight: 600;
    min-height: 40px;
}

QPushButton:hover {
    border-color: #94a3b8;
}

QPushButton:disabled {
    color: #94a3b8;
    background: #f8fafc;
    border-color: #e2e8f0;
}

QPushButton[variant="primary"] {
    background: #2563eb;
    color: #ffffff;
    border-color: #2563eb;
}

QPushButton[variant="primary"]:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

QLineEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #d6deea;
    border-radius: 12px;
    padding: 0 12px;
    min-height: 40px;
}

QLineEdit:focus, QComboBox:focus {
    border-color: #2563eb;
}

QToolButton {
    border: none;
    color: #2563eb;
    font-weight: 600;
    padding: 0;
}

QCheckBox {
    spacing: 8px;
    min-height: 24px;
    padding: 2px 0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
"""


BADGE_COLORS = {
    "unconfigured": "#94a3b8",
    "stopped": "#0f766e",
    "running": "#16a34a",
    "starting": "#d97706",
    "error": "#dc2626",
}
