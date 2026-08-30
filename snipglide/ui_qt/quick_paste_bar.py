from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QFrame, QApplication
)

from snipglide.database.snippet_repo import get_all_snippets
from snipglide.database.clipboard_repo import get_clipboard_history

class QuickPasteBarQt(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(580, 360)

        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 2px solid #3b82f6;
                border-radius: 16px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(10)

        # Header
        h_row = QHBoxLayout()
        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 18px; border: none;")
        h_row.addWidget(icon_lbl)

        title = QLabel("شريط اللصق السريع (Quick Paste Bar)")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f2f5; border: none;")
        h_row.addWidget(title)
        h_row.addStretch()

        hint = QLabel("Enter للصق • Esc للإغلاق")
        hint.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        h_row.addWidget(hint)
        c_layout.addLayout(h_row)

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("ابحث للصق أي نص، كود، أو اختصار فوراً...")
        self.search_edit.setFixedHeight(44)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #202c33;
                color: #f0f2f5;
                font-size: 15px;
                border: 2px solid #3b4a54;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_items)
        c_layout.addWidget(self.search_edit)

        # Results List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 1px solid #202c33;
                border-radius: 10px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 10px 12px;
                border-radius: 8px;
                margin-bottom: 3px;
                font-size: 13px;
                border: 1px solid #2a3942;
            }
            QListWidget::item:hover {
                background-color: #202c33;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._paste_selected)
        c_layout.addWidget(self.list_widget, stretch=1)

        layout.addWidget(card)

    def show_centered(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 3
        self.move(x, y)
        self._load_items()
        self.search_edit.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_edit.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._paste_selected()
        elif event.key() == Qt.Key_Down:
            row = self.list_widget.currentRow()
            if row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(row + 1)
        elif event.key() == Qt.Key_Up:
            row = self.list_widget.currentRow()
            if row > 0:
                self.list_widget.setCurrentRow(row - 1)
        else:
            super().keyPressEvent(event)

    def _load_items(self):
        self._items = []
        # Snippets
        for s in get_all_snippets():
            self._items.append((s.replacement, f"✂️ [{s.shortcut}] {s.description or s.replacement[:40]}"))
        # Clipboard
        for text in get_clipboard_history(limit=15):
            self._items.append((text, f"📋 {text.replace(chr(10), ' ')[:50]}"))

        self._filter_items("")

    def _filter_items(self, query: str):
        self.list_widget.clear()
        q = query.strip().lower()
        for content, label in self._items:
            if not q or q in label.lower() or q in content.lower():
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, content)
                self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _paste_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        content = item.data(Qt.UserRole)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(content)
        self.close()
