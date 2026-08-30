from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QFrame, QApplication
)

from snipglide.database.snippet_repo import get_all_snippets
from snipglide.database.note_repo import get_all_notes
from snipglide.database.chat_note_repo import get_all_chat_notes

class CommandPaletteQt(QDialog):
    action_triggered = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(650, 480)

        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Background Container Card
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 2px solid #25D366;
                border-radius: 16px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(12)

        # Top Header Bar
        top_row = QHBoxLayout()
        icon_lbl = QLabel("⚡")
        icon_lbl.setStyleSheet("font-size: 20px; border: none;")
        top_row.addWidget(icon_lbl)

        title_lbl = QLabel("لوحة الأوامر السريعة (Command Palette)")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #f0f2f5; border: none;")
        top_row.addWidget(title_lbl)

        top_row.addStretch()

        esc_badge = QLabel("Esc للإغلاق")
        esc_badge.setStyleSheet("background-color: #202c33; color: #94a3b8; font-size: 11px; padding: 3px 8px; border-radius: 6px; border: 1px solid #3b4a54;")
        top_row.addWidget(esc_badge)
        c_layout.addLayout(top_row)

        # Search Input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("ابحث عن أي أمر، اختصار، أو ملاحظة...")
        self.search_edit.setFixedHeight(46)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #202c33;
                color: #f0f2f5;
                font-size: 16px;
                border: 2px solid #3b4a54;
                border-radius: 10px;
                padding: 10px 14px;
            }
            QLineEdit:focus {
                border: 2px solid #25D366;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_items)
        c_layout.addWidget(self.search_edit)

        # List
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
                padding: 10px 14px;
                border-radius: 8px;
                margin-bottom: 4px;
                font-size: 14px;
                border: 1px solid #2a3942;
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
        self.list_widget.itemDoubleClicked.connect(self._execute_selected)
        c_layout.addWidget(self.list_widget, stretch=1)

        main_layout.addWidget(container)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected()
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
        self._all_items = [
            ("nav", "Dashboard", "📊 الانتقال إلى: لوحة التحكم (Dashboard)"),
            ("nav", "Snippets", "✂️ الانتقال إلى: محرر الاختصارات (Snippets)"),
            ("nav", "Notes", "📝 الانتقال إلى: الملاحظات العادية (Notes)"),
            ("nav", "ChatNotes", "💬 الانتقال إلى: شات نوت (Chat Notes)"),
            ("nav", "Search", "🔍 الانتقال إلى: البحث الموحد (Search)"),
            ("nav", "Clipboard", "📋 الانتقال إلى: سجل الحافظة (Clipboard)"),
            ("action", "new_snippet", "➕ إنشاء اختصار جديد"),
            ("action", "new_note", "📝 كتابة ملاحظة جديدة"),
            ("action", "email_templates", "📧 فتح قوالب البريد الإلكتروني الذكية"),
            ("action", "toggle_chat_head", "💬 إظهار / إخفاء فقاعة شات نوت العائمة على الشاشة"),
            ("action", "export_data", "💾 تصدير كافة البيانات إلى ملف JSON"),
            ("action", "import_data", "📥 استيراد البيانات من ملف JSON"),
            ("action", "seed_demo", "🌱 توليد عينات وبيانات تجريبية"),
        ]

        # Add top snippets
        for s in get_all_snippets()[:15]:
            self._all_items.append(("copy_snippet", s.replacement, f"✂️ اختصار [{s.shortcut}]: {s.description or s.replacement[:40]}"))

        # Add top chat notes
        for c in get_all_chat_notes()[:15]:
            self._all_items.append(("copy_chat", c.content, f"💬 شات: {c.content.replace(chr(10), ' ')[:50]}"))

        self._filter_items("")

    def _filter_items(self, query: str):
        self.list_widget.clear()
        q = query.strip().lower()

        for kind, data, label in self._all_items:
            if not q or q in label.lower() or (isinstance(data, str) and q in data.lower()):
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, (kind, data))
                self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _execute_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        kind, data = item.data(Qt.UserRole)
        self.action_triggered.emit(kind, data)
        self.close()
