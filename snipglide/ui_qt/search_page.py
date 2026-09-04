from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
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
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        btn_drawer = QPushButton("☰ القائمة")
        btn_drawer.setToolTip("إظهار / إخفاء القائمة الجانبية (Drawer) - Ctrl+B")
        btn_drawer.setCursor(QCursor(Qt.PointingHandCursor))
        btn_drawer.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #60a5fa;
                border: 1.5px solid #2a3942;
                border-radius: 9px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #172554;
                color: #93c5fd;
                border-color: #3b82f6;
            }
        """)
        btn_drawer.clicked.connect(lambda: self.window().toggle_sidebar() if hasattr(self.window(), "toggle_sidebar") else None)
        top_row.addWidget(btn_drawer)

        title = QLabel("البحث الموحد الشامل (Unified Global Search)")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #f0f2f5;")
        top_row.addWidget(title)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 ابحث فوراً عبر الاختصارات، الملاحظات، الشات، والحافظة...")
        self.search_edit.setFixedHeight(48)
        self.search_edit.textChanged.connect(self._run_search)
        layout.addWidget(self.search_edit)

        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 2px solid #202c33;
                border-radius: 12px;
                padding: 8px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 14px 18px;
                border-radius: 10px;
                margin-bottom: 6px;
                border: 1px solid #2a3942;
                font-size: 15px;
            }
            QListWidget::item:hover {
                background-color: #202c33;
                border-color: #3b4a54;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
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
