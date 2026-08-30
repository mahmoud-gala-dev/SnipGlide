from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QSplitter
)

from snipglide.database.note_repo import (
    get_all_notes, get_notes_for_list, get_note_by_id, add_note, update_note, delete_note,
    toggle_pin
)
from snipglide.database.note_category_repo import get_all_categories
from snipglide.models.note import Note

class NotesPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self.selected_note_id = None
        self._categories = []
        self._setup_ui()
        self.update_category_dropdowns()
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

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في الملاحظات...")
        self.search_edit.setFixedHeight(34)
        self.search_edit.textChanged.connect(self.refresh_list)
        l_layout.addWidget(self.search_edit)

        self.cat_filter = QComboBox()
        self.cat_filter.setFixedHeight(34)
        self.cat_filter.currentTextChanged.connect(self.refresh_list)
        l_layout.addWidget(self.cat_filter)

        new_btn = QPushButton("➕ ملاحظة جديدة")
        new_btn.setFixedHeight(36)
        new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_btn.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; border-radius: 8px;")
        new_btn.clicked.connect(self.new_note)
        l_layout.addWidget(new_btn)

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 1px solid #1f2c34;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px 12px;
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
        self.notes_list.itemClicked.connect(self._on_item_clicked)
        l_layout.addWidget(self.notes_list, stretch=1)
        splitter.addWidget(left_pane)

        # ── Right Editor Pane ──
        right_pane = QFrame()
        right_pane.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 12px;")
        r_layout = QVBoxLayout(right_pane)
        r_layout.setContentsMargins(15, 12, 15, 12)
        r_layout.setSpacing(10)

        # Title + Category + Pin
        row1 = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("عنوان الملاحظة...")
        self.title_edit.setFixedHeight(36)
        row1.addWidget(self.title_edit, stretch=1)

        self.cat_combo = QComboBox()
        self.cat_combo.setFixedHeight(36)
        row1.addWidget(self.cat_combo)

        self.pin_btn = QPushButton("📌 تثبيت")
        self.pin_btn.setFixedHeight(36)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setStyleSheet("background-color: #1f2c34; color: white; border-radius: 8px; padding: 4px 12px;")
        self.pin_btn.clicked.connect(self._toggle_pin)
        row1.addWidget(self.pin_btn)
        r_layout.addLayout(row1)

        # Content Text
        self.content_edit = QPlainTextEdit()
        self.content_edit.setStyleSheet("background-color: #0b141a; color: #e9edef; font-size: 15px; border-radius: 8px; padding: 12px;")
        r_layout.addWidget(self.content_edit, stretch=1)

        # Bottom Actions
        bot_row = QHBoxLayout()
        bot_row.addStretch()

        self.del_btn = QPushButton("🗑️ حذف")
        self.del_btn.setFixedHeight(36)
        self.del_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 8px; padding: 4px 14px;")
        self.del_btn.clicked.connect(self._delete_current)
        bot_row.addWidget(self.del_btn)

        save_btn = QPushButton("💾 حفظ الملاحظة")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 8px; padding: 4px 18px;")
        save_btn.clicked.connect(self._save_current)
        bot_row.addWidget(save_btn)

        r_layout.addLayout(bot_row)
        splitter.addWidget(right_pane)

        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter)

    def update_category_dropdowns(self):
        categories = get_all_categories()
        self._categories = categories
        self.cat_filter.clear()
        self.cat_filter.addItem("جميع الأقسام (All Categories)", None)
        self.cat_combo.clear()

        for c in categories:
            self.cat_filter.addItem(c.name, c.id)
            self.cat_combo.addItem(c.name, c.id)

    def refresh_list(self):
        self.notes_list.clear()
        query = self.search_edit.text().strip()
        cid = self.cat_filter.currentData()
        notes = get_notes_for_list(query=query, category_id=cid)

        for n in notes:
            prefix = "📌 " if n.pinned else ""
            item = QListWidgetItem(f"{prefix}{n.title}")
            item.setData(Qt.UserRole, n.id)
            self.notes_list.addItem(item)

    def _on_item_clicked(self, item):
        nid = item.data(Qt.UserRole)
        note = get_note_by_id(nid)
        if note:
            self.selected_note_id = note.id
            self.title_edit.setText(note.title)
            self.content_edit.setPlainText(note.content)
            self.pin_btn.setChecked(bool(note.pinned))
            self.pin_btn.setText("📌 مثبتة" if note.pinned else "📌 تثبيت")
            if note.category_id:
                idx = self.cat_combo.findData(note.category_id)
                if idx >= 0:
                    self.cat_combo.setCurrentIndex(idx)

    def new_note(self):
        self.selected_note_id = None
        self.title_edit.clear()
        self.content_edit.clear()
        self.pin_btn.setChecked(False)
        self.pin_btn.setText("📌 تثبيت")
        self.title_edit.setFocus()

    def _toggle_pin(self):
        if self.selected_note_id:
            toggle_pin(self.selected_note_id)
            note = get_note_by_id(self.selected_note_id)
            new_val = bool(note.pinned) if note else False
            self.pin_btn.setChecked(new_val)
            self.pin_btn.setText("📌 مثبتة" if new_val else "📌 تثبيت")
            self.refresh_list()

    def _save_current(self):
        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText()
        if not title:
            self.toast_signal.emit("عنوان الملاحظة مطلوب.", True)
            return

        cid = self.cat_combo.currentData()
        pinned = self.pin_btn.isChecked()

        note = Note(
            id=self.selected_note_id,
            title=title,
            content=content,
            category_id=cid,
            pinned=pinned,
        )

        try:
            if self.selected_note_id is None:
                self.selected_note_id = add_note(note)
            else:
                update_note(note)
            self.refresh_list()
            self.toast_signal.emit("تم حفظ الملاحظة بنجاح! 💾", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def _delete_current(self):
        if not self.selected_note_id:
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذه الملاحظة؟")
        if reply == QMessageBox.Yes:
            delete_note(self.selected_note_id)
            self.new_note()
            self.refresh_list()
            self.toast_signal.emit("تم حذف الملاحظة 🗑️", False)
