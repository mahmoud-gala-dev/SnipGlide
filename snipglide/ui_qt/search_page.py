from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QApplication
)

from snipglide.database.search_repo import search_all, get_search_result_body

class SearchPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        title = QLabel("البحث الموحد (Unified Search)")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e9edef;")
        layout.addWidget(title)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("ابحث عبر الاختصارات، الملاحظات، والشات، والحافظة...")
        self.search_edit.setFixedHeight(40)
        self.search_edit.textChanged.connect(self._run_search)
        layout.addWidget(self.search_edit)

        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 1px solid #1f2c34;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #1f2c34;
                color: #e9edef;
                padding: 12px 14px;
                border-radius: 8px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #2a3942;
            }
        """)
        self.results_list.itemDoubleClicked.connect(self._copy_result)
        layout.addWidget(self.results_list, stretch=1)

    def _run_search(self, text: str):
        self.results_list.clear()
        query = text.strip().lower()
        if not query:
            return

        results = search_all(query, limit=50)
        for r in results:
            kind_tag = f"[{r['kind']}]"
            item = QListWidgetItem(f"{kind_tag} {r['title']}\n{r['body'][:100]}")
            item.setData(Qt.UserRole, (r["kind"], r["ref"]))
            self.results_list.addItem(item)

    def _copy_result(self, item):
        kind, ref = item.data(Qt.UserRole)
        body = get_search_result_body(kind, ref)
        if body:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(body)
                self.toast_signal.emit("تم نسخ النتيجة إلى الحافظة! 📋", False)
