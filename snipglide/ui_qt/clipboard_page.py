from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QApplication
)

from snipglide.database.clipboard_repo import (
    get_clipboard_history, get_clipboard_history_count, clear_clipboard_history
)

class ClipboardPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self.current_page = 1
        self.page_size = 30
        self._setup_ui()
        self.refresh_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        # Header Row
        h_row = QHBoxLayout()
        title = QLabel("سجل الحافظة (Clipboard History)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e9edef;")
        h_row.addWidget(title)

        h_row.addStretch()

        clear_btn = QPushButton("🗑️ مسح السجل")
        clear_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 8px; padding: 6px 14px;")
        clear_btn.clicked.connect(self._clear_all)
        h_row.addWidget(clear_btn)
        layout.addLayout(h_row)

        # List
        self.clip_list = QListWidget()
        self.clip_list.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 1px solid #1f2c34;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #1f2c34;
                color: #e9edef;
                padding: 10px 14px;
                border-radius: 8px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #2a3942;
            }
        """)
        self.clip_list.itemDoubleClicked.connect(self._copy_item)
        layout.addWidget(self.clip_list, stretch=1)

        # Footer Pagination
        f_row = QHBoxLayout()
        prev_btn = QPushButton("السابق")
        prev_btn.clicked.connect(self._prev_page)
        f_row.addWidget(prev_btn)

        self.page_lbl = QLabel("صفحة 1")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        f_row.addWidget(self.page_lbl, stretch=1)

        next_btn = QPushButton("التالي")
        next_btn.clicked.connect(self._next_page)
        f_row.addWidget(next_btn)
        layout.addLayout(f_row)

    def refresh_history(self):
        self.clip_list.clear()
        total = get_clipboard_history_count()
        offset = (self.current_page - 1) * self.page_size
        items = get_clipboard_history(limit=self.page_size, offset=offset)

        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.page_lbl.setText(f"صفحة {self.current_page} من {total_pages}")

        for text in items:
            preview = text.replace("\n", " ")[:120]
            item = QListWidgetItem(f"📋 {preview}")
            item.setData(Qt.UserRole, text)
            self.clip_list.addItem(item)

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_history()

    def _next_page(self):
        total = get_clipboard_history_count()
        if self.current_page * self.page_size < total:
            self.current_page += 1
            self.refresh_history()

    def _copy_item(self, item):
        content = item.data(Qt.UserRole)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(content)
            self.toast_signal.emit("تم نسخ العنصر إلى الحافظة! 📋", False)

    def _clear_all(self):
        clear_clipboard_history()
        self.refresh_history()
        self.toast_signal.emit("تم مسح سجل الحافظة 🗑️", False)
