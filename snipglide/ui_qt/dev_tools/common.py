from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QPlainTextEdit, QLabel, QApplication
)

def create_tool_button(text: str, bg_color: str, callback: Callable[[], None]) -> QPushButton:
    """Creates a styled action button matching SnipGlide aesthetics."""
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.PointingHandCursor))
    btn.setFixedHeight(36)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg_color};
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 13px;
            border: none;
        }}
        QPushButton:hover {{
            opacity: 0.9;
            border: 1px solid rgba(255, 255, 255, 0.4);
        }}
    """)
    btn.clicked.connect(callback)
    return btn


def create_code_editor(placeholder: str = "", readonly: bool = False) -> QPlainTextEdit:
    """Creates a Monospace code editor matching SnipGlide dark theme."""
    editor = QPlainTextEdit()
    editor.setPlaceholderText(placeholder)
    editor.setReadOnly(readonly)
    editor.setStyleSheet("""
        QPlainTextEdit {
            background-color: #0b141a;
            color: #38bdf8;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
            border: 1.5px solid #202c33;
            border-radius: 10px;
            padding: 10px;
        }
        QPlainTextEdit:focus {
            border-color: #3b82f6;
        }
    """)
    return editor


def wrap_in_labeled_box(label_text: str, widget: QWidget) -> QWidget:
    """Wraps a widget in a titled container layout."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    lbl = QLabel(label_text)
    lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #94a3b8;")
    layout.addWidget(lbl)
    layout.addWidget(widget, stretch=1)
    return container


def create_section_card(title: str, widget: QWidget) -> QWidget:
    """Wraps a widget in a styled section card with header title."""
    card = QWidget()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    card.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px;")

    lbl = QLabel(title)
    lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #89b4fa; border: none;")
    layout.addWidget(lbl)
    layout.addWidget(widget, stretch=1)
    return card



def show_status_badge(label: QLabel, text: str, is_error: bool = False) -> None:
    """Updates and displays a status feedback badge."""
    bg = "#450a0a" if is_error else "#052e16"
    color = "#f87171" if is_error else "#4ade80"
    border = "#dc2626" if is_error else "#16a34a"
    label.setStyleSheet(f"background-color: {bg}; color: {color}; border: 1px solid {border}; font-size: 13px; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
    label.setText(text)
    label.show()


def copy_text_to_clipboard(text: str, toast_callback: Optional[Callable[[str, bool], None]] = None) -> bool:
    """Copies text safely to system clipboard and triggers user feedback."""
    if not text:
        if toast_callback:
            toast_callback("لا يوجد محتوى لنسخه!", True)
        return False
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)
        if toast_callback:
            toast_callback("تم نسخ المحتوى إلى الحافظة! 📋", False)
        return True
    return False

copy_to_clipboard = copy_text_to_clipboard

