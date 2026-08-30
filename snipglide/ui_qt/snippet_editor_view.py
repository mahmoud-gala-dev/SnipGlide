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
        left_pane.setStyleSheet("background-color: #111b21; border-radius: 14px; padding: 10px; border: 1.5px solid #2a3942;")
        l_layout = QVBoxLayout(left_pane)
        l_layout.setContentsMargins(10, 10, 10, 10)
        l_layout.setSpacing(10)

        # Search & Group filter
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في الاختصارات...")
        self.search_edit.setFixedHeight(42)
        self.search_edit.textChanged.connect(self.refresh_list)
        l_layout.addWidget(self.search_edit)

        self.group_filter = QComboBox()
        self.group_filter.setFixedHeight(42)
        self.group_filter.currentTextChanged.connect(self.refresh_list)
        l_layout.addWidget(self.group_filter)

        new_btn = QPushButton("➕ إضافة اختصار جديد")
        new_btn.setFixedHeight(44)
        new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_btn.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; border-radius: 10px; font-size: 14px;")
        new_btn.clicked.connect(self.new_snippet)
        l_layout.addWidget(new_btn)

        self.snippet_list = QListWidget()
        self.snippet_list.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 2px solid #202c33;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-radius: 8px;
                color: #f0f2f5;
                margin-bottom: 4px;
                border: 1px solid #182229;
            }
            QListWidget::item:hover {
                background-color: #1f2c34;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
            }
        """)
        self.snippet_list.itemClicked.connect(self._on_item_clicked)
        self.snippet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_list.customContextMenuRequested.connect(self._show_snippet_menu)
        l_layout.addWidget(self.snippet_list, stretch=1)
        splitter.addWidget(left_pane)

        # ── Right Form Pane ──
        right_pane = QFrame()
        right_pane.setStyleSheet("background-color: #111b21; border-radius: 14px; padding: 14px; border: 1.5px solid #2a3942;")
        r_layout = QVBoxLayout(right_pane)
        r_layout.setContentsMargins(18, 14, 18, 14)
        r_layout.setSpacing(12)

        # Shortcut & Group row
        row1 = QHBoxLayout()
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setPlaceholderText("نص الاختصار (مثال: :mail أو #hi)")
        self.shortcut_edit.setFixedHeight(44)
        row1.addWidget(self.shortcut_edit)

        self.group_combo = QComboBox()
        self.group_combo.setFixedHeight(44)
        row1.addWidget(self.group_combo)
        r_layout.addLayout(row1)

        # Description & App Filter Row
        row2 = QHBoxLayout()
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("الوصف التوضيحي (اختياري)")
        self.desc_edit.setFixedHeight(44)
        row2.addWidget(self.desc_edit, stretch=2)

        self.app_combo = QComboBox()
        self.app_combo.setFixedHeight(44)
        self.app_combo.addItem("🌐 يعمل في كافة البرامج (All Apps)", "")
        self.app_combo.addItem("💻 Visual Studio Code", "code")
        self.app_combo.addItem("💬 WhatsApp", "whatsapp")
        self.app_combo.addItem("🌐 Google Chrome / Edge", "chrome")
        self.app_combo.addItem("📄 Microsoft Word", "winword")
        self.app_combo.addItem("⚡ Terminal / PowerShell", "powershell")
        self.app_combo.addItem("📝 Notepad", "notepad")
        row2.addWidget(self.app_combo, stretch=1)
        r_layout.addLayout(row2)

        # Content Text
        lbl_content = QLabel("نص التوسيع الكامل:")
        lbl_content.setStyleSheet("font-weight: bold; font-size: 14px; color: #94a3b8;")
        r_layout.addWidget(lbl_content)

        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("اكتب النص الذي ترغب في توسيعه عند كتابة الاختصار...")
        self.content_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: 15px;
                border-radius: 10px;
                padding: 12px;
                border: 2px solid #3b4a54;
            }
            QPlainTextEdit:focus {
                border: 2px solid #25D366;
            }
        """)
        r_layout.addWidget(self.content_edit, stretch=1)

        # Bottom Options
        bot_row = QHBoxLayout()
        self.case_check = QCheckBox("حساس لحالة الأحرف (Case Sensitive)")
        self.case_check.setChecked(True)
        self.case_check.setStyleSheet("font-size: 14px; font-weight: bold; color: #94a3b8;")
        bot_row.addWidget(self.case_check)

        bot_row.addStretch()

        self.del_btn = QPushButton("🗑️ حذف")
        self.del_btn.setFixedHeight(44)
        self.del_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 10px; padding: 4px 18px; font-size: 14px;")
        self.del_btn.clicked.connect(self._delete_current)
        bot_row.addWidget(self.del_btn)

        save_btn = QPushButton("💾 حفظ الاختصار")
        save_btn.setFixedHeight(44)
        save_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 10px; padding: 4px 24px; font-size: 15px;")
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
            if snippet.app_filter:
                idx = self.app_combo.findData(snippet.app_filter)
                if idx >= 0:
                    self.app_combo.setCurrentIndex(idx)
                else:
                    self.app_combo.setCurrentIndex(0)
            else:
                self.app_combo.setCurrentIndex(0)

    def new_snippet(self, initial_content: str = ""):
        self.selected_snippet_id = None
        self.shortcut_edit.clear()
        self.desc_edit.clear()
        self.content_edit.setPlainText(initial_content)
        self.app_combo.setCurrentIndex(0)
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
        app_f = self.app_combo.currentData() or ""

        snippet = Snippet(
            id=self.selected_snippet_id,
            shortcut=sc,
            replacement=content,
            description=desc,
            group_id=gid,
            app_filter=app_f,
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

    def _show_snippet_menu(self, pos):
        item = self.snippet_list.itemAt(pos)
        if not item:
            return
        sid = item.data(Qt.UserRole)
        snippet = get_snippet_by_id(sid)
        if not snippet:
            return

        menu = QMenu(self)
        copy_sc = menu.addAction(f"📋 نسخ الاختصار: {snippet.shortcut}")
        copy_rep = menu.addAction("📄 نسخ نص التوسيع")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ حذف الاختصار")

        action = menu.exec(self.snippet_list.mapToGlobal(pos))
        clipboard = QApplication.clipboard()
        if action == copy_sc:
            if clipboard:
                clipboard.setText(snippet.shortcut)
                self.toast_signal.emit("تم نسخ رمز الاختصار! 📋", False)
        elif action == copy_rep:
            if clipboard:
                clipboard.setText(snippet.replacement)
                self.toast_signal.emit("تم نسخ نص التوسيع! 📄", False)
        elif action == del_act:
            delete_snippet(snippet.id)
            self.new_snippet()
            self.refresh_list()
            self.snippets_changed_signal.emit()
            self.toast_signal.emit("تم حذف الاختصار 🗑️", False)

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
