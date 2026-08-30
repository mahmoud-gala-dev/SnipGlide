from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QCheckBox, QMessageBox,
    QListWidget, QListWidgetItem, QSplitter
)

from snipglide.database.snippet_repo import (
    get_all_snippets, get_snippets_for_list, get_snippet_by_id, add_snippet, update_snippet,
    delete_snippet
)
from snipglide.database.group_repo import get_all_groups, add_group
from snipglide.models.snippet import Snippet

class SnippetEditorViewQt(QWidget):
    toast_signal = Signal(str, bool)
    snippets_changed_signal = Signal()

    def __init__(self, toast_callback=None, snippets_changed_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)
        if snippets_changed_callback:
            self.snippets_changed_signal.connect(snippets_changed_callback)

        self.selected_snippet_id = None
        self._groups = []
        self._setup_ui()
        self.update_group_dropdowns()
        self.refresh_list()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left List Pane ──
        left_pane = QFrame()
        left_pane.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 8px;")
        l_layout = QVBoxLayout(left_pane)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(8)

        # Search & Group filter
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في الاختصارات...")
        self.search_edit.setFixedHeight(34)
        self.search_edit.textChanged.connect(self.refresh_list)
        l_layout.addWidget(self.search_edit)

        self.group_filter = QComboBox()
        self.group_filter.setFixedHeight(34)
        self.group_filter.currentTextChanged.connect(self.refresh_list)
        l_layout.addWidget(self.group_filter)

        new_btn = QPushButton("➕ اختصار جديد")
        new_btn.setFixedHeight(36)
        new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_btn.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; border-radius: 8px;")
        new_btn.clicked.connect(self.new_snippet)
        l_layout.addWidget(new_btn)

        self.snippet_list = QListWidget()
        self.snippet_list.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 1px solid #1f2c34;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
                color: #e9edef;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #1f2c34;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #60a5fa;
                font-weight: bold;
            }
        """)
        self.snippet_list.itemClicked.connect(self._on_item_clicked)
        l_layout.addWidget(self.snippet_list, stretch=1)
        splitter.addWidget(left_pane)

        # ── Right Form Pane ──
        right_pane = QFrame()
        right_pane.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 12px;")
        r_layout = QVBoxLayout(right_pane)
        r_layout.setContentsMargins(15, 12, 15, 12)
        r_layout.setSpacing(10)

        # Shortcut & Group row
        row1 = QHBoxLayout()
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setPlaceholderText("نص الاختصار (مثال: :mail)")
        self.shortcut_edit.setFixedHeight(36)
        row1.addWidget(self.shortcut_edit)

        self.group_combo = QComboBox()
        self.group_combo.setFixedHeight(36)
        row1.addWidget(self.group_combo)
        r_layout.addLayout(row1)

        # Description
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("الوصف (اختياري)")
        self.desc_edit.setFixedHeight(36)
        r_layout.addWidget(self.desc_edit)

        # Content Text
        r_layout.addWidget(QLabel("نص التوسيع الكامل:"))
        self.content_edit = QPlainTextEdit()
        self.content_edit.setStyleSheet("background-color: #0b141a; color: #e9edef; font-size: 14px; border-radius: 8px; padding: 10px;")
        r_layout.addWidget(self.content_edit, stretch=1)

        # Bottom Options
        bot_row = QHBoxLayout()
        self.case_check = QCheckBox("حساس لحالة الأحرف (Case Sensitive)")
        self.case_check.setChecked(True)
        bot_row.addWidget(self.case_check)

        bot_row.addStretch()

        self.del_btn = QPushButton("🗑️ حذف")
        self.del_btn.setFixedHeight(36)
        self.del_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 8px; padding: 4px 14px;")
        self.del_btn.clicked.connect(self._delete_current)
        bot_row.addWidget(self.del_btn)

        save_btn = QPushButton("💾 حفظ الاختصار")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 8px; padding: 4px 18px;")
        save_btn.clicked.connect(self._save_current)
        bot_row.addWidget(save_btn)

        r_layout.addLayout(bot_row)
        splitter.addWidget(right_pane)

        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter)

    def update_group_dropdowns(self):
        groups = get_all_groups()
        self._groups = groups
        self.group_filter.clear()
        self.group_filter.addItem("جميع المجموعات (All Groups)", None)
        self.group_combo.clear()

        for g in groups:
            self.group_filter.addItem(f"{g.icon} {g.name}", g.id)
            self.group_combo.addItem(f"{g.icon} {g.name}", g.id)

    def refresh_list(self):
        self.snippet_list.clear()
        query = self.search_edit.text().strip()
        gid = self.group_filter.currentData()
        snippets = get_snippets_for_list(query=query, group_id=gid)

        for s in snippets:
            item = QListWidgetItem(f"{s.shortcut}  —  {s.description or s.replacement[:30]}")
            item.setData(Qt.UserRole, s.id)
            self.snippet_list.addItem(item)

    def _on_item_clicked(self, item):
        sid = item.data(Qt.UserRole)
        snippet = get_snippet_by_id(sid)
        if snippet:
            self.selected_snippet_id = snippet.id
            self.shortcut_edit.setText(snippet.shortcut)
            self.desc_edit.setText(snippet.description or "")
            self.content_edit.setPlainText(snippet.replacement)
            self.case_check.setChecked(bool(snippet.regex_enabled))
            if snippet.group_id:
                idx = self.group_combo.findData(snippet.group_id)
                if idx >= 0:
                    self.group_combo.setCurrentIndex(idx)

    def new_snippet(self, initial_content: str = ""):
        self.selected_snippet_id = None
        self.shortcut_edit.clear()
        self.desc_edit.clear()
        self.content_edit.setPlainText(initial_content)
        self.shortcut_edit.setFocus()

    def _save_current(self):
        sc = self.shortcut_edit.text().strip()
        content = self.content_edit.toPlainText()
        if not sc:
            self.toast_signal.emit("الاختصار مطلوب.", True)
            return
        if not content:
            self.toast_signal.emit("محتوى الاختصار لا يمكن أن يكون فارغاً.", True)
            return

        gid = self.group_combo.currentData()
        desc = self.desc_edit.text().strip()

        snippet = Snippet(
            id=self.selected_snippet_id,
            shortcut=sc,
            replacement=content,
            description=desc,
            group_id=gid,
        )

        try:
            if self.selected_snippet_id is None:
                self.selected_snippet_id = add_snippet(snippet)
            else:
                update_snippet(snippet)
            self.refresh_list()
            self.snippets_changed_signal.emit()
            self.toast_signal.emit("تم حفظ الاختصار بنجاح! 💾", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def _delete_current(self):
        if not self.selected_snippet_id:
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذا الاختصار؟")
        if reply == QMessageBox.Yes:
            delete_snippet(self.selected_snippet_id)
            self.new_snippet()
            self.refresh_list()
            self.snippets_changed_signal.emit()
            self.toast_signal.emit("تم حذف الاختصار 🗑️", False)
