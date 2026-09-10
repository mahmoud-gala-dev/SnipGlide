import datetime
from typing import Optional, Any
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QLineEdit, QComboBox, QMenu, QApplication
)

from snipglide.database.clipboard_repo import (
    get_clipboard_entries, get_clipboard_history_count,
    clear_clipboard_history, delete_clipboard_entry, search_clipboard_entries
)
from snipglide.services.clipboard_content_detector import (
    ClipboardContentDetector, TYPE_PLAIN_TEXT, TYPE_URL, TYPE_JSON,
    TYPE_XML, TYPE_SQL, TYPE_CODE, TYPE_STACK_TRACE, TYPE_UUID,
    TYPE_JWT, TYPE_EMAIL
)
from snipglide.services.dev_tools_service import (
    JsonTools, JwtTools, UrlTools, UuidTools
)

# Badge styling metadata per content type
TYPE_META = {
    TYPE_JSON: {"label": "{ } JSON", "color": "#f59e0b", "bg": "#451a03", "border": "#d97706", "quick": "✨ تنسيق JSON"},
    TYPE_JWT: {"label": "🎫 JWT", "color": "#ec4899", "bg": "#500724", "border": "#db2777", "quick": "🎫 فك التوكن"},
    TYPE_URL: {"label": "🌐 URL", "color": "#60a5fa", "bg": "#172554", "border": "#3b82f6", "quick": "🌐 فتح الرابط"},
    TYPE_SQL: {"label": "🗄️ SQL", "color": "#c084fc", "bg": "#3b0764", "border": "#a855f7", "quick": "✂️ كاختصار"},
    TYPE_CODE: {"label": "💻 CODE", "color": "#34d399", "bg": "#064e3b", "border": "#059669", "quick": "✂️ كاختصار"},
    TYPE_STACK_TRACE: {"label": "⚠️ STACK TRACE", "color": "#f87171", "bg": "#450a0a", "border": "#dc2626", "quick": "📝 كملاحظة"},
    TYPE_UUID: {"label": "🆔 UUID", "color": "#38bdf8", "bg": "#083344", "border": "#0284c7", "quick": "📋 نسخ"},
    TYPE_EMAIL: {"label": "📧 EMAIL", "color": "#2dd4bf", "bg": "#042f2e", "border": "#0d9488", "quick": "📧 إرسال بريد"},
    TYPE_XML: {"label": "📑 XML", "color": "#fb923c", "bg": "#431407", "border": "#ea580c", "quick": "📝 كملاحظة"},
    TYPE_PLAIN_TEXT: {"label": "📄 TEXT", "color": "#94a3b8", "bg": "#1e293b", "border": "#475569", "quick": "📋 نسخ"},
}


class ClipboardItemWidget(QFrame):
    """Custom card widget for displaying a single clipboard item with badges and actions."""
    action_requested = Signal(str, dict)  # action_id, entry_dict

    def __init__(self, entry: dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.content = entry.get("content", "")
        self.c_type = entry.get("content_type") or TYPE_PLAIN_TEXT
        self.is_sensitive = ClipboardContentDetector.is_sensitive(self.content)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            ClipboardItemWidget {
                background-color: #182229;
                border: 1px solid #2a3942;
                border-radius: 10px;
                padding: 10px 14px;
            }
            ClipboardItemWidget:hover {
                background-color: #202c33;
                border-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # ── Top Row: Type Badge + Sensitive Badge + Meta + Action Buttons ──
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Content Type Badge
        meta = TYPE_META.get(self.c_type, TYPE_META[TYPE_PLAIN_TEXT])
        badge_lbl = QLabel(meta["label"])
        badge_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {meta['bg']};
                color: {meta['color']};
                border: 1px solid {meta['border']};
                border-radius: 6px;
                padding: 3px 9px;
                font-weight: 800;
                font-size: 11px;
            }}
        """)
        top_row.addWidget(badge_lbl)

        # Sensitive Indicator Badge
        if self.is_sensitive:
            sens_badge = QLabel("🔒 محتوى حساس (Sensitive)")
            sens_badge.setStyleSheet("""
                QLabel {{
                    background-color: #7f1d1d;
                    color: #fca5a5;
                    border: 1px solid #dc2626;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-weight: bold;
                    font-size: 11px;
                }}
            """)
            top_row.addWidget(sens_badge)

        # Copied Time / Length info
        copied_at = self.entry.get("copied_at") or ""
        length_str = f"{len(self.content):,} حرف"
        info_text = f"{length_str}"
        if copied_at:
            try:
                # Format ISO string nicely if possible
                info_text += f" • {copied_at[:16].replace('T', ' ')}"
            except Exception:
                pass

        info_lbl = QLabel(info_text)
        info_lbl.setStyleSheet("color: #8696a0; font-size: 11px;")
        top_row.addWidget(info_lbl)

        top_row.addStretch()

        # Quick Action Button (Tailored to type)
        quick_btn = QPushButton(meta["quick"])
        quick_btn.setCursor(QCursor(Qt.PointingHandCursor))
        quick_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #60a5fa;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #172554;
                color: #93c5fd;
            }
        """)
        quick_btn.clicked.connect(self._trigger_quick_action)
        top_row.addWidget(quick_btn)

        # Copy Button
        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setToolTip("نسخ هذا العنصر مباشرة إلى الحافظة")
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a3942;
                color: #25D366;
                border-color: #25D366;
            }
        """)
        copy_btn.clicked.connect(lambda: self.action_requested.emit("copy", self.entry))
        top_row.addWidget(copy_btn)

        # Context Menu Button
        more_btn = QPushButton("⋮")
        more_btn.setToolTip("المزيد من الخيارات والإجراءات")
        more_btn.setCursor(QCursor(Qt.PointingHandCursor))
        more_btn.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #8696a0;
                border: 1px solid #2a3942;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a3942;
                color: #f0f2f5;
            }
        """)
        more_btn.clicked.connect(lambda: self.action_requested.emit("menu", self.entry))
        top_row.addWidget(more_btn)

        # Delete Button
        del_btn = QPushButton("🗑️")
        del_btn.setToolTip("حذف هذا العنصر من سجل الحافظة")
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ef4444;
                border: none;
                padding: 4px 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #450a0a;
                border-radius: 6px;
            }
        """)
        del_btn.clicked.connect(lambda: self.action_requested.emit("delete", self.entry))
        top_row.addWidget(del_btn)

        layout.addLayout(top_row)

        # ── Bottom Row: Preview Text ──
        if self.is_sensitive:
            preview_text = "•••••••••••••••••••••••••••••••• (محتوى حساس مشفر ومخفي)"
        else:
            clean_lines = [line.strip() for line in self.content.splitlines() if line.strip()]
            preview_text = "  ".join(clean_lines[:3])[:220]
            if len(self.content) > len(preview_text):
                preview_text += " …"

        preview_lbl = QLabel(preview_text)
        if self.c_type in (TYPE_JSON, TYPE_JWT, TYPE_CODE, TYPE_SQL, TYPE_UUID, TYPE_STACK_TRACE):
            font = QFont("Consolas", 10)
            font.setStyleHint(QFont.Monospace)
            preview_lbl.setFont(font)
            preview_lbl.setStyleSheet("color: #e2e8f0; background: transparent; padding-top: 2px;")
        else:
            preview_lbl.setStyleSheet("color: #d1d5db; background: transparent; font-size: 13px; padding-top: 2px;")
        preview_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(preview_lbl)

    def _trigger_quick_action(self):
        """Dispatches primary quick action based on detected content type."""
        c_type = self.c_type
        if c_type == TYPE_JSON:
            self.action_requested.emit("json_format", self.entry)
        elif c_type == TYPE_JWT:
            self.action_requested.emit("jwt_decode", self.entry)
        elif c_type == TYPE_URL:
            self.action_requested.emit("url_open", self.entry)
        elif c_type == TYPE_UUID:
            self.action_requested.emit("copy", self.entry)
        elif c_type == TYPE_EMAIL:
            self.action_requested.emit("email_open", self.entry)
        elif c_type in (TYPE_SQL, TYPE_CODE):
            self.action_requested.emit("save_snippet", self.entry)
        elif c_type == TYPE_STACK_TRACE:
            self.action_requested.emit("create_note", self.entry)
        else:
            self.action_requested.emit("copy", self.entry)


class ClipboardPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self.current_page = 1
        self.page_size = 25
        self.search_query = ""
        self.filter_type: Optional[str] = None

        self._setup_ui()
        self.refresh_history()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(14)

        # ── Header Bar ──
        h_row = QHBoxLayout()

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
        h_row.addWidget(btn_drawer)

        title = QLabel("📋 سجل الحافظة الذكي (Developer Clipboard)")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f0f2f5;")
        h_row.addWidget(title)

        h_row.addStretch()

        badge = QLabel("⚡ تصنيف محلي ذكي للبيانات البرمجية")
        badge.setStyleSheet("background-color: #172554; color: #93c5fd; padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: bold; border: 1px solid #1e3a8a;")
        h_row.addWidget(badge)

        clear_btn = QPushButton("🗑️ مسح السجل")
        clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        clear_btn.clicked.connect(self._clear_all)
        h_row.addWidget(clear_btn)

        main_layout.addLayout(h_row)

        # ── Search & Filter Controls ──
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 تصفية وبحث مباشر في عناصر الحافظة...")
        self.search_edit.setFixedHeight(40)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #182229;
                color: #f0f2f5;
                font-size: 13px;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        ctrl_row.addWidget(self.search_edit, stretch=3)

        self.type_filter_combo = QComboBox()
        self.type_filter_combo.setFixedHeight(40)
        self.type_filter_combo.setStyleSheet("""
            QComboBox {
                background-color: #182229;
                color: #f0f2f5;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #3b82f6;
            }
            QComboBox QAbstractItemView {
                background-color: #111b21;
                color: #f0f2f5;
                selection-background-color: #172554;
                border: 1px solid #2a3942;
            }
        """)
        self.type_filter_combo.addItem("📂 جميع الأنواع (All Types)", None)
        for t in [
            (TYPE_JSON, "{ } JSON"),
            (TYPE_JWT, "🎫 JWT"),
            (TYPE_URL, "🌐 URL"),
            (TYPE_SQL, "🗄️ SQL"),
            (TYPE_CODE, "💻 Code"),
            (TYPE_STACK_TRACE, "⚠️ Stack Trace"),
            (TYPE_UUID, "🆔 UUID"),
            (TYPE_EMAIL, "📧 Email"),
            (TYPE_XML, "📑 XML"),
            (TYPE_PLAIN_TEXT, "📄 Plain Text"),
        ]:
            self.type_filter_combo.addItem(t[1], t[0])
        self.type_filter_combo.currentIndexChanged.connect(self._on_type_filter_changed)
        ctrl_row.addWidget(self.type_filter_combo, stretch=1)

        main_layout.addLayout(ctrl_row)

        # ── Clipboard List ──
        self.clip_list = QListWidget()
        self.clip_list.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 1.5px solid #1f2c34;
                border-radius: 12px;
                padding: 8px;
            }
            QListWidget::item {
                background: transparent;
                padding: 2px 0px;
                border: none;
            }
        """)
        self.clip_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.clip_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clip_list.customContextMenuRequested.connect(self._show_clip_menu_at_pos)
        main_layout.addWidget(self.clip_list, stretch=1)

        # ── Footer Pagination ──
        f_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀ السابق")
        self.prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #f0f2f5;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #3b82f6;
            }
            QPushButton:disabled {
                color: #475569;
                border-color: #1f2c34;
            }
        """)
        self.prev_btn.clicked.connect(self._prev_page)
        f_row.addWidget(self.prev_btn)

        self.page_lbl = QLabel("صفحة 1")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        self.page_lbl.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 13px;")
        f_row.addWidget(self.page_lbl, stretch=1)

        self.next_btn = QPushButton("التالي ▶")
        self.next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #f0f2f5;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #3b82f6;
            }
            QPushButton:disabled {
                color: #475569;
                border-color: #1f2c34;
            }
        """)
        self.next_btn.clicked.connect(self._next_page)
        f_row.addWidget(self.next_btn)

        main_layout.addLayout(f_row)

    def _on_search_changed(self, text: str):
        self.search_query = text.strip()
        self.current_page = 1
        self.refresh_history()

    def _on_type_filter_changed(self, index: int):
        self.filter_type = self.type_filter_combo.currentData()
        self.current_page = 1
        self.refresh_history()

    def refresh_history(self):
        self.clip_list.clear()
        offset = (self.current_page - 1) * self.page_size

        if self.search_query:
            entries, total = search_clipboard_entries(self.search_query, limit=self.page_size, offset=offset)
        else:
            total = get_clipboard_history_count()
            entries = get_clipboard_entries(limit=self.page_size, offset=offset)

        # Filter by type if selected
        if self.filter_type:
            entries = [e for e in entries if (e.get("content_type") or ClipboardContentDetector.detect_type(e.get("content", ""))) == self.filter_type]

        total_pages = max(1, (total + self.page_size - 1) // self.page_size) if total > 0 else 1
        self.page_lbl.setText(f"صفحة {self.current_page} من {total_pages} (إجمالي: {total} عنصر)")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

        if not entries:
            empty_item = QListWidgetItem("لا توجد عناصر في سجل الحافظة حالياً.")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setFlags(Qt.NoItemFlags)
            self.clip_list.addItem(empty_item)
            return

        for entry in entries:
            # Lazy detection fallback if content_type is missing or plain text
            c_type = entry.get("content_type")
            if not c_type or c_type == TYPE_PLAIN_TEXT:
                detected = ClipboardContentDetector.detect_type(entry.get("content", ""))
                if detected != TYPE_PLAIN_TEXT:
                    entry["content_type"] = detected

            card = ClipboardItemWidget(entry, parent=self.clip_list)
            card.action_requested.connect(self._handle_item_action)

            item = QListWidgetItem(self.clip_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.UserRole, entry)
            self.clip_list.addItem(item)
            self.clip_list.setItemWidget(item, card)

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_history()

    def _next_page(self):
        total = get_clipboard_history_count()
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_history()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        entry = item.data(Qt.UserRole)
        if entry and "content" in entry:
            self._copy_text(entry["content"])

    def _handle_item_action(self, action_id: str, entry: dict[str, Any]):
        content = entry.get("content", "")

        if action_id == "copy":
            self._copy_text(content)
        elif action_id == "delete":
            delete_clipboard_entry(content)
            self.refresh_history()
            self.toast_signal.emit("تم حذف العنصر من سجل الحافظة 🗑️", False)
        elif action_id == "menu":
            self._show_context_menu_for_entry(entry, QCursor.pos())
        elif action_id == "json_format":
            self._action_json_format(content)
        elif action_id == "jwt_decode":
            self._action_jwt_decode(content)
        elif action_id == "url_open":
            self._action_url_open(content)
        elif action_id == "email_open":
            self._action_email_open(content)
        elif action_id == "save_snippet":
            self._action_save_snippet(content)
        elif action_id == "create_note":
            self._action_create_note(content, entry.get("content_type", "Clipboard Note"))

    def _show_clip_menu_at_pos(self, pos):
        item = self.clip_list.itemAt(pos)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        global_pos = self.clip_list.mapToGlobal(pos)
        self._show_context_menu_for_entry(entry, global_pos)

    def _show_context_menu_for_entry(self, entry: dict[str, Any], global_pos):
        content = entry.get("content", "")
        c_type = entry.get("content_type") or ClipboardContentDetector.detect_type(content)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #111b21;
                color: #f0f2f5;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #172554;
                color: #93c5fd;
            }
            QMenu::separator {
                height: 1px;
                background: #202c33;
                margin: 4px 0px;
            }
        """)

        # Always available: Copy
        copy_act = menu.addAction("📋 نسخ إلى الحافظة (Copy)")
        menu.addSeparator()

        # Contextual Actions per type
        custom_actions = {}
        if c_type == TYPE_JSON:
            custom_actions["json_fmt"] = menu.addAction("✨ تنسيق ونسخ (Format & Copy)")
            custom_actions["json_min"] = menu.addAction("🗜️ ضغط ونسخ (Minify & Copy)")
            custom_actions["json_val"] = menu.addAction("✅ التحقق من الصحة (Validate)")
            custom_actions["json_dev"] = menu.addAction("🛠️ فتح في معالج JSON بالـ Toolbox")
        elif c_type == TYPE_JWT:
            custom_actions["jwt_dec"] = menu.addAction("🎫 فك التوكن ونسخ الـ Payload")
            custom_actions["jwt_dev"] = menu.addAction("🛠️ فتح في JWT Decoder بالـ Toolbox")
        elif c_type == TYPE_URL:
            custom_actions["url_open"] = menu.addAction("🌐 فتح الرابط في المتصفح")
            custom_actions["url_enc"] = menu.addAction("🔒 ترميز الرابط (URL Encode)")
            custom_actions["url_dec"] = menu.addAction("🔓 فك ترميز الرابط (URL Decode)")
            custom_actions["url_qry"] = menu.addAction("🔍 استخراج معلمات الاستعلام (Query Params)")
        elif c_type == TYPE_UUID:
            custom_actions["uuid_new"] = menu.addAction("🆔 توليد UUID جديد والنسخ للحافظة")
        elif c_type == TYPE_EMAIL:
            custom_actions["mail_open"] = menu.addAction("📧 فتح تطبيق البريد (Send Email)")
        elif c_type == TYPE_SQL:
            custom_actions["save_snip"] = menu.addAction("✂️ حفظ استعلام SQL كاختصار (Snippet)")
            custom_actions["save_note"] = menu.addAction("📝 حفظ في الملاحظات (Create Note)")
        elif c_type == TYPE_CODE:
            custom_actions["save_snip"] = menu.addAction("✂️ حفظ الكود كاختصار (Snippet)")
            custom_actions["save_note"] = menu.addAction("📝 حفظ الكود في الملاحظات")
            custom_actions["code_dev"] = menu.addAction("🛠️ فتح في معالج النصوص (Text Utils)")
        elif c_type == TYPE_STACK_TRACE:
            custom_actions["save_note"] = menu.addAction("📝 حفظ تقرير الخطأ كملاحظة للمتابعة")
        else:
            custom_actions["save_snip"] = menu.addAction("✂️ حفظ كاختصار (Save as Snippet)")
            custom_actions["save_note"] = menu.addAction("📝 حفظ في الملاحظات (Create Note)")
            custom_actions["text_dev"] = menu.addAction("🛠️ فتح في معالج النصوص (Text Utils)")

        menu.addSeparator()
        del_act = menu.addAction("🗑️ حذف هذا العنصر من السجل")
        clear_act = menu.addAction("🗑️ مسح كامل سجل الحافظة")

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen == copy_act:
            self._copy_text(content)
        elif chosen == del_act:
            delete_clipboard_entry(content)
            self.refresh_history()
            self.toast_signal.emit("تم حذف العنصر 🗑️", False)
        elif chosen == clear_act:
            self._clear_all()
        elif "json_fmt" in custom_actions and chosen == custom_actions["json_fmt"]:
            self._action_json_format(content)
        elif "json_min" in custom_actions and chosen == custom_actions["json_min"]:
            res = JsonTools.minify(content)
            self._copy_text(res)
            self.toast_signal.emit("تم ضغط JSON ونسخه للحافظة! 🗜️", False)
        elif "json_val" in custom_actions and chosen == custom_actions["json_val"]:
            is_valid, msg = JsonTools.validate(content)
            self.toast_signal.emit(msg, not is_valid)
        elif "json_dev" in custom_actions and chosen == custom_actions["json_dev"]:
            self._open_dev_toolbox_tab(0, content)
        elif "jwt_dec" in custom_actions and chosen == custom_actions["jwt_dec"]:
            self._action_jwt_decode(content)
        elif "jwt_dev" in custom_actions and chosen == custom_actions["jwt_dev"]:
            self._open_dev_toolbox_tab(3, content)
        elif "url_open" in custom_actions and chosen == custom_actions["url_open"]:
            self._action_url_open(content)
        elif "url_enc" in custom_actions and chosen == custom_actions["url_enc"]:
            enc = UrlTools.url_encode(content)
            self._copy_text(enc)
            self.toast_signal.emit("تم ترميز الرابط ونسخه للحافظة! 🌐", False)
        elif "url_dec" in custom_actions and chosen == custom_actions["url_dec"]:
            dec = UrlTools.url_decode(content)
            self._copy_text(dec)
            self.toast_signal.emit("تم فك ترميز الرابط ونسخه للحافظة! 🌐", False)
        elif "url_qry" in custom_actions and chosen == custom_actions["url_qry"]:
            parsed = UrlTools.parse_query_params(content)
            import json as py_json
            formatted = py_json.dumps(parsed, indent=2, ensure_ascii=False)
            self._copy_text(formatted)
            self.toast_signal.emit("تم استخراج معلمات الاستعلام ونسخها كـ JSON! 🔍", False)
        elif "uuid_new" in custom_actions and chosen == custom_actions["uuid_new"]:
            new_id = UuidTools.generate_uuid_v4()
            self._copy_text(new_id)
            self.toast_signal.emit("تم توليد UUID جديد ونسخه! 🆔", False)
        elif "mail_open" in custom_actions and chosen == custom_actions["mail_open"]:
            self._action_email_open(content)
        elif "save_snip" in custom_actions and chosen == custom_actions["save_snip"]:
            self._action_save_snippet(content)
        elif "save_note" in custom_actions and chosen == custom_actions["save_note"]:
            self._action_create_note(content, f"{c_type} Note")
        elif "code_dev" in custom_actions and chosen == custom_actions["code_dev"]:
            self._open_dev_toolbox_tab(7, content)
        elif "text_dev" in custom_actions and chosen == custom_actions["text_dev"]:
            self._open_dev_toolbox_tab(7, content)

    # ── Action Implementations ──

    def _copy_text(self, text: str):
        clip = QApplication.clipboard()
        if clip:
            clip.setText(text)
            self.toast_signal.emit("تم نسخ العنصر إلى الحافظة! 📋", False)

    def _action_json_format(self, content: str):
        res = JsonTools.beautify(content)
        self._copy_text(res)
        self.toast_signal.emit("تم تنسيق JSON ونسخه بنجاح! ✨", False)

    def _action_jwt_decode(self, content: str):
        res = JwtTools.decode_jwt(content)
        if res.get("is_valid"):
            import json as py_json
            payload_str = py_json.dumps(res.get("payload", {}), indent=2, ensure_ascii=False)
            self._copy_text(payload_str)
            self.toast_signal.emit("تم فك تشفير JWT ونسخ الـ Payload إلى الحافظة! 🎫", False)
        else:
            self.toast_signal.emit(f"تعذر فك التوكن: {res.get('error', 'Invalid JWT')}", True)

    def _action_url_open(self, content: str):
        raw = content.strip()
        if not raw.startswith(("http://", "https://", "ftp://")):
            raw = "https://" + raw
        QDesktopServices.openUrl(QUrl(raw))
        self.toast_signal.emit("جاري فتح الرابط في المتصفح... 🌐", False)

    def _action_email_open(self, content: str):
        raw = content.strip()
        QDesktopServices.openUrl(QUrl(f"mailto:{raw}"))
        self.toast_signal.emit("جاري فتح تطبيق البريد... 📧", False)

    def _action_save_snippet(self, content: str):
        win = self.window()
        if hasattr(win, "sidebar") and hasattr(win, "snippets_page"):
            win.sidebar.select_page("Snippets")
            win.snippets_page.new_snippet(initial_content=content)
            self.toast_signal.emit("جاهز لحفظ الكود كاختصار جديد! ✂️", False)
        else:
            self._copy_text(content)

    def _action_create_note(self, content: str, title: str = "Clipboard Note"):
        win = self.window()
        if hasattr(win, "sidebar") and hasattr(win, "notes_page"):
            win.sidebar.select_page("Notes")
            win.notes_page.new_note(initial_content=content, initial_title=title)
            self.toast_signal.emit("تم فتح الملاحظة في المحرر! 📝", False)
        else:
            self._copy_text(content)

    def _open_dev_toolbox_tab(self, tab_idx: int, content: str):
        win = self.window()
        if hasattr(win, "sidebar") and hasattr(win, "dev_toolbox_page"):
            win.sidebar.select_page("DevToolbox")
            win.dev_toolbox_page.tabs.setCurrentIndex(tab_idx)
            # Inject content into relevant sub-widget editor
            if tab_idx == 0 and hasattr(win.dev_toolbox_page, "json_widget"):
                win.dev_toolbox_page.json_widget.editor_input.setPlainText(content)
            elif tab_idx == 3 and hasattr(win.dev_toolbox_page, "jwt_widget"):
                win.dev_toolbox_page.jwt_widget.editor_input.setPlainText(content)
                win.dev_toolbox_page.jwt_widget.decode_jwt()
            elif tab_idx == 7 and hasattr(win.dev_toolbox_page, "text_widget"):
                win.dev_toolbox_page.text_widget.editor.setPlainText(content)
            self.toast_signal.emit("تم فتح المحتوى في أدوات المطورين! 🛠️", False)

    def _clear_all(self):
        clear_clipboard_history()
        self.refresh_history()
        self.toast_signal.emit("تم مسح كامل سجل الحافظة 🗑️", False)
