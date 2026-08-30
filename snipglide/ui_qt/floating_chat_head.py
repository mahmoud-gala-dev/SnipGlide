from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QCursor, QColor, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QPlainTextEdit, QComboBox, QApplication
)

from snipglide.database.chat_note_repo import add_chat_note, get_all_chat_notes, get_all_chat_sections

class FloatingChatDrawer(QFrame):
    note_saved_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(360, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 2px solid #25D366;
                border-radius: 16px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        # Header
        h_row = QHBoxLayout()
        icon = QLabel("💬")
        icon.setStyleSheet("font-size: 18px; border: none;")
        h_row.addWidget(icon)

        title = QLabel("شات نوت السريع (Quick Chat Note)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #f0f2f5; border: none;")
        h_row.addWidget(title)
        h_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("background: transparent; color: #94a3b8; font-weight: bold; border: none; font-size: 14px;")
        close_btn.clicked.connect(self.close)
        h_row.addWidget(close_btn)
        c_layout.addLayout(h_row)

        # Section Selector
        self.sec_combo = QComboBox()
        self.sec_combo.setFixedHeight(36)
        self.sec_combo.setStyleSheet("background-color: #202c33; color: white; border: 1px solid #3b4a54; border-radius: 8px; padding: 4px;")
        try:
            for s in get_all_chat_sections():
                self.sec_combo.addItem(f"{s.icon} {s.name}", s.id)
        except Exception:
            pass
        c_layout.addWidget(self.sec_combo)

        # Note Input
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("اكتب ملاحظتك السريعة هنا... (Enter للحفظ فوراً)")
        self.input_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: 14px;
                border: 1.5px solid #3b4a54;
                border-radius: 10px;
                padding: 10px;
            }
            QPlainTextEdit:focus {
                border: 1.5px solid #25D366;
            }
        """)
        c_layout.addWidget(self.input_edit, stretch=1)

        # Bottom Save Button
        save_btn = QPushButton("💾 حفظ في شات نوت")
        save_btn.setFixedHeight(40)
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 10px; font-size: 14px; border: none;")
        save_btn.clicked.connect(self._save_note)
        c_layout.addWidget(save_btn)

        layout.addWidget(card)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self._save_note()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _save_note(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        sec_id = self.sec_combo.currentData() or 1
        try:
            add_chat_note(content=text, is_starred=False, section_id=sec_id)
            self.note_saved_signal.emit("تم حفظ الملاحظة في شات نوت فوراً! 💬")
            self.input_edit.clear()
            self.close()
        except Exception:
            pass


class FloatingChatHead(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(60, 60)

        self._drag_pos = QPoint()
        self.drawer = FloatingChatDrawer()

        # Position at bottom-right of screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 80, screen.height() - 200)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw green gradient circular bubble
        painter.setBrush(QBrush(QColor("#25D366")))
        painter.setPen(QPen(QColor("#1da851"), 2))
        painter.drawEllipse(4, 4, 52, 52)

        # Draw icon
        painter.setPen(QPen(QColor("white")))
        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.drawText(self.rect(), Qt.AlignCenter, "💬")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if it was a click or a drag
            cur_pos = event.globalPosition().toPoint() - self._drag_pos
            if (cur_pos - self.pos()).manhattanLength() < 5:
                self._toggle_drawer()

    def _toggle_drawer(self):
        if self.drawer.isVisible():
            self.drawer.hide()
        else:
            # Position drawer to the left of the chat head
            pos = self.pos()
            self.drawer.move(pos.x() - self.drawer.width() - 10, max(50, pos.y() - 150))
            self.drawer.show()
            self.drawer.input_edit.setFocus()
