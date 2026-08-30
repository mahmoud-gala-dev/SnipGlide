from datetime import datetime
import re
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QMenu, QMessageBox,
    QSizePolicy, QApplication
)

from snipglide.database.chat_note_repo import (
    add_chat_note, add_chat_section, clear_all_chat_notes, delete_chat_note,
    delete_chat_section, get_all_chat_notes, get_all_chat_sections,
    get_chat_notes_count, seed_demo_chat_notes, toggle_star_chat_note
)
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting
from snipglide.models.chat_note import ChatNote, ChatNoteSection
from snipglide.utils.helpers import download_and_load_arabic_font
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family


class ChatNotesPageQt(QWidget):
    toast_signal = Signal(str, bool)
    navigate_to_snippet_signal = Signal(str)

    def __init__(self, toast_callback=None, navigate_to_snippet_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)
        if navigate_to_snippet_callback:
            self.navigate_to_snippet_signal.connect(navigate_to_snippet_callback)

        self.selected_section_id = None
        self.starred_filter_active = False
        self._sections_cache = []
        self._notes_cache = []
        self._is_dirty = True

        # Load font settings
        self.chat_font_size = self._get_saved_font_size()
        self.chat_font_family = self._get_saved_font_family()

        self._setup_ui()

        if get_chat_notes_count() == 0:
            try:
                seed_demo_chat_notes()
            except Exception:
                pass

        QTimer.singleShot(50, self.refresh_sections)
        QTimer.singleShot(80, self.refresh_chat)

    def _get_saved_font_size(self) -> int:
        try:
            val = int(get_note_setting("chat_font_size", "22"))
            if val < 18:
                val = 22
                set_note_setting("chat_font_size", "22")
            return min(max(val, 12), 36)
        except Exception:
            return 22

    def _get_saved_font_family(self) -> str:
        saved = get_note_setting("chat_font_family", "Tajawal")
        return saved if saved else get_arabic_font_family()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(8)

        # ── 1. Header ──
        header = QFrame()
        header.setObjectName("headerFrame")
        header.setProperty("class", "cardFrame")
        header.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 6, 12, 6)

        # Title & Avatar
        avatar_lbl = QLabel("💬")
        avatar_lbl.setStyleSheet("font-size: 22px; background-color: #25D366; color: white; border-radius: 19px; padding: 4px 8px;")
        h_layout.addWidget(avatar_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_lbl = QLabel("شات الملاحظات السريعة (Quick Chat Notes)")
        self.title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; font-family: '{self.chat_font_family}'; color: #e9edef;")
        self.count_badge = QLabel("سجل ملاحظاتك وأفكارك بأسلوب محادثات الواتساب الأنيق")
        self.count_badge.setStyleSheet(f"font-size: 12px; font-family: '{self.chat_font_family}'; color: #8696a0;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.count_badge)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Font controls: [A-] [22px] [A+]
        font_box = QFrame()
        font_box.setStyleSheet("background-color: #1f2c34; border-radius: 8px; padding: 2px;")
        fb_layout = QHBoxLayout(font_box)
        fb_layout.setContentsMargins(4, 2, 4, 2)
        fb_layout.setSpacing(4)

        down_btn = QPushButton("A-")
        down_btn.setFixedSize(28, 28)
        down_btn.setCursor(QCursor(Qt.PointingHandCursor))
        down_btn.setStyleSheet("background-color: transparent; font-weight: bold; border: none; color: white;")
        down_btn.clicked.connect(lambda: self._change_font_size(-1))
        fb_layout.addWidget(down_btn)

        self.font_size_lbl = QLabel(f"{self.chat_font_size}px")
        self.font_size_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #25D366;")
        fb_layout.addWidget(self.font_size_lbl)

        up_btn = QPushButton("A+")
        up_btn.setFixedSize(28, 28)
        up_btn.setCursor(QCursor(Qt.PointingHandCursor))
        up_btn.setStyleSheet("background-color: transparent; font-weight: bold; border: none; color: white;")
        up_btn.clicked.connect(lambda: self._change_font_size(1))
        fb_layout.addWidget(up_btn)
        h_layout.addWidget(font_box)

        # Font family selector
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"])
        self.font_combo.setCurrentText(self.chat_font_family if self.chat_font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_combo.setFixedHeight(32)
        self.font_combo.currentTextChanged.connect(self._on_font_family_change)
        h_layout.addWidget(self.font_combo)

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في الملاحظات...")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setFixedWidth(160)
        self.search_edit.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self.search_edit)

        # Star Filter Button
        self.star_filter_btn = QPushButton("⭐ المفضلة")
        self.star_filter_btn.setFixedHeight(32)
        self.star_filter_btn.setCheckable(True)
        self.star_filter_btn.setStyleSheet("background-color: #1f2c34; color: white; border-radius: 8px; padding: 4px 12px;")
        self.star_filter_btn.clicked.connect(self._toggle_star_filter)
        h_layout.addWidget(self.star_filter_btn)

        # Seed Demo Button
        demo_btn = QPushButton("🌱 عينات")
        demo_btn.setFixedHeight(32)
        demo_btn.setStyleSheet("background-color: #1f2c34; color: white; border-radius: 8px; padding: 4px 10px;")
        demo_btn.clicked.connect(self._seed_demo_data)
        h_layout.addWidget(demo_btn)

        # Clear All Button
        clear_btn = QPushButton("🗑️ مسح")
        clear_btn.setFixedHeight(32)
        clear_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 8px; padding: 4px 10px;")
        clear_btn.clicked.connect(self._confirm_clear_all)
        h_layout.addWidget(clear_btn)

        main_layout.addWidget(header)

        # ── 2. Sections Bar ──
        self.sections_scroll = QScrollArea()
        self.sections_scroll.setFixedHeight(46)
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setStyleSheet("background: transparent; border: none;")

        self.sections_container = QWidget()
        self.sections_layout = QHBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 4, 0, 4)
        self.sections_layout.setSpacing(6)
        self.sections_layout.setAlignment(Qt.AlignLeft)
        self.sections_scroll.setWidget(self.sections_container)
        main_layout.addWidget(self.sections_scroll)

        # ── 3. Chat Feed Area ──
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("background-color: #0b141a; border-radius: 12px; border: 1px solid #1f2c34;")

        self.chat_feed_container = QWidget()
        self.chat_feed_container.setStyleSheet("background-color: transparent;")
        self.chat_feed_layout = QVBoxLayout(self.chat_feed_container)
        self.chat_feed_layout.setContentsMargins(15, 15, 15, 15)
        self.chat_feed_layout.setSpacing(8)
        self.chat_feed_layout.setAlignment(Qt.AlignTop)
        self.chat_scroll.setWidget(self.chat_feed_container)
        main_layout.addWidget(self.chat_scroll, stretch=1)

        # ── 4. Compose Bar ──
        compose_frame = QFrame()
        compose_frame.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 6px;")
        comp_layout = QHBoxLayout(compose_frame)
        comp_layout.setContentsMargins(10, 6, 10, 6)
        comp_layout.setSpacing(8)

        self.compose_sec_combo = QComboBox()
        self.compose_sec_combo.setFixedHeight(40)
        self.compose_sec_combo.setMinimumWidth(110)
        comp_layout.addWidget(self.compose_sec_combo)

        time_btn = QPushButton("🕒")
        time_btn.setFixedSize(40, 40)
        time_btn.setStyleSheet("background-color: #1f2c34; border-radius: 8px; font-size: 16px;")
        time_btn.clicked.connect(self._insert_timestamp)
        comp_layout.addWidget(time_btn)

        self.star_new_btn = QPushButton("⭐")
        self.star_new_btn.setFixedSize(40, 40)
        self.star_new_btn.setCheckable(True)
        self.star_new_btn.setStyleSheet("background-color: #1f2c34; border-radius: 8px; font-size: 16px;")
        comp_layout.addWidget(self.star_new_btn)

        self.message_input = QPlainTextEdit()
        self.message_input.setFixedHeight(54)
        self.message_input.setPlaceholderText("اكتب ملاحظتك هنا... (Enter للإرسال، Shift+Enter لسطر جديد)")
        self.message_input.setStyleSheet(f"font-size: {self.chat_font_size}px; font-family: '{self.chat_font_family}'; background-color: #2a3942; border-radius: 8px; padding: 8px; color: white;")
        self.message_input.installEventFilter(self)
        comp_layout.addWidget(self.message_input, stretch=1)

        send_btn = QPushButton("➤ إرسال")
        send_btn.setFixedHeight(44)
        send_btn.setFixedWidth(90)
        send_btn.setCursor(QCursor(Qt.PointingHandCursor))
        send_btn.setStyleSheet(f"background-color: #25D366; color: white; font-weight: bold; font-size: 14px; font-family: '{self.chat_font_family}'; border-radius: 8px;")
        send_btn.clicked.connect(self._send_message)
        comp_layout.addWidget(send_btn)

        main_layout.addWidget(compose_frame)

    def eventFilter(self, obj, event):
        if obj is self.message_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    def _change_font_size(self, delta: int):
        new_size = min(max(self.chat_font_size + delta, 12), 36)
        if new_size != self.chat_font_size:
            self.chat_font_size = new_size
            set_note_setting("chat_font_size", str(new_size))
            self.font_size_lbl.setText(f"{new_size}px")
            self.message_input.setStyleSheet(f"font-size: {new_size}px; font-family: '{self.chat_font_family}'; background-color: #2a3942; border-radius: 8px; padding: 8px; color: white;")
            self.refresh_chat(scroll_to_bottom=False)

    def _on_font_family_change(self, family: str):
        download_and_load_arabic_font(family)
        self.chat_font_family = family
        set_arabic_font_family(family)
        set_note_setting("chat_font_family", family)
        self.title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; font-family: '{family}'; color: #e9edef;")
        self.count_badge.setStyleSheet(f"font-size: 12px; font-family: '{family}'; color: #8696a0;")
        self.message_input.setStyleSheet(f"font-size: {self.chat_font_size}px; font-family: '{family}'; background-color: #2a3942; border-radius: 8px; padding: 8px; color: white;")
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=False)

    def refresh_sections(self):
        # Clear existing section buttons
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = get_all_chat_sections()
        self._sections_cache = sections

        self.compose_sec_combo.clear()
        for s in sections:
            self.compose_sec_combo.addItem(f"{s.icon} {s.name}", s.id)

        # All button
        all_count = get_chat_notes_count()
        all_btn = QPushButton(f"💬 الكل ({all_count})")
        all_btn.setFixedHeight(32)
        all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        is_all = self.selected_section_id is None
        all_style = "background-color: #25D366; color: white; font-weight: bold;" if is_all else "background-color: #1f2c34; color: #e9edef;"
        all_btn.setStyleSheet(f"{all_style} border-radius: 16px; padding: 4px 16px; font-size: 12px; font-family: '{self.chat_font_family}';")
        all_btn.clicked.connect(lambda: self._select_section(None))
        self.sections_layout.addWidget(all_btn)

        # Dynamic Section Pills
        for sec in sections:
            count = get_chat_notes_count(section_id=sec.id)
            btn = QPushButton(f"{sec.icon} {sec.name} ({count})")
            btn.setFixedHeight(32)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            is_active = self.selected_section_id == sec.id
            btn_style = f"background-color: {sec.color}; color: white; font-weight: bold;" if is_active else "background-color: #1f2c34; color: #e9edef;"
            btn.setStyleSheet(f"{btn_style} border-radius: 16px; padding: 4px 14px; font-size: 12px; font-family: '{self.chat_font_family}';")
            btn.clicked.connect(lambda _, s=sec: self._select_section(s.id))
            if sec.id != 1:
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda pos, s=sec, b=btn: self._show_section_menu(b, pos, s))
            self.sections_layout.addWidget(btn)

        # Add section button
        add_btn = QPushButton("➕ قسم جديد")
        add_btn.setFixedHeight(32)
        add_btn.setStyleSheet(f"background-color: #2a3942; color: #e9edef; border-radius: 16px; padding: 4px 14px; font-size: 12px; font-family: '{self.chat_font_family}';")
        add_btn.clicked.connect(self._prompt_add_section)
        self.sections_layout.addWidget(add_btn)

    def _select_section(self, section_id: int | None):
        self.selected_section_id = section_id
        if section_id:
            idx = self.compose_sec_combo.findData(section_id)
            if idx >= 0:
                self.compose_sec_combo.setCurrentIndex(idx)
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=True)

    def _show_section_menu(self, btn, pos, section: ChatNoteSection):
        menu = QMenu(self)
        del_action = menu.addAction(f"🗑️ حذف قسم '{section.name}'")
        action = menu.exec(btn.mapToGlobal(pos))
        if action == del_action:
            delete_chat_section(section.id)
            if self.selected_section_id == section.id:
                self.selected_section_id = None
            self.refresh_sections()
            self.refresh_chat()
            self.toast_signal.emit(f"تم حذف قسم '{section.name}'", False)

    def _prompt_add_section(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "إضافة قسم جديد", "اسم القسم:")
        if ok and name.strip():
            try:
                new_sec = add_chat_section(name=name.strip(), icon="💬", color="#25D366")
                self.selected_section_id = new_sec.id
                self.refresh_sections()
                self.refresh_chat()
                self.toast_signal.emit(f"تم إنشاء قسم '{name}' بنجاح! 🎉", False)
            except Exception as e:
                self.toast_signal.emit(f"فشل إنشاء القسم: {e}", True)

    def _seed_demo_data(self):
        try:
            seed_demo_chat_notes()
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
            self.toast_signal.emit("تمت إضافة الملاحظات التجريبية بنجاح! 💬", False)
        except Exception as e:
            self.toast_signal.emit(f"خطأ: {e}", True)

    def _insert_timestamp(self):
        now_str = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
        self.message_input.insertPlainText(now_str)
        self.message_input.setFocus()

    def _on_search_changed(self, text: str):
        self.refresh_chat()

    def _toggle_star_filter(self):
        self.starred_filter_active = self.star_filter_btn.isChecked()
        if self.starred_filter_active:
            self.star_filter_btn.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; border-radius: 8px; padding: 4px 12px;")
        else:
            self.star_filter_btn.setStyleSheet("background-color: #1f2c34; color: white; border-radius: 8px; padding: 4px 12px;")
        self.refresh_chat()

    def _send_message(self):
        content = self.message_input.toPlainText().strip()
        if not content:
            return

        is_starred = self.star_new_btn.isChecked()
        target_sec_id = self.compose_sec_combo.currentData() or 1

        try:
            add_chat_note(content=content, is_starred=is_starred, section_id=target_sec_id)
            self.message_input.clear()
            self.star_new_btn.setChecked(False)
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
            self.toast_signal.emit("تم حفظ الملاحظة بنجاح 💬", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def refresh_chat(self, scroll_to_bottom: bool = True):
        # Clear chat feed
        while self.chat_feed_layout.count():
            item = self.chat_feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.search_edit.text().strip()
        notes = get_all_chat_notes(
            query=query,
            starred_only=self.starred_filter_active,
            section_id=self.selected_section_id,
        )
        self._notes_cache = notes
        self._is_dirty = False

        total_count = get_chat_notes_count(section_id=self.selected_section_id)
        current_count = len(notes)
        sec_name = "الكل"
        if self.selected_section_id:
            s_obj = next((s for s in self._sections_cache if s.id == self.selected_section_id), None)
            if s_obj:
                sec_name = s_obj.name

        self.count_badge.setText(f"القسم: [{sec_name}] • الإجمالي: {total_count} • المعروض: {current_count}")

        if not notes:
            empty_lbl = QLabel("صندوق الملاحظات فارغ.\nاكتب فكرتك أو ملاحظتك في صندوق الكتابة بالأسفل واضغط Enter لحفظها فوراً!")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(f"color: #8696a0; font-size: 15px; font-family: '{self.chat_font_family}'; padding: 40px;")
            self.chat_feed_layout.addWidget(empty_lbl)
            return

        last_date_str = None
        for note in notes:
            # Date divider
            note_date_str = self._format_date_header(note.created_at)
            if note_date_str != last_date_str:
                div = QLabel(f"  {note_date_str}  ")
                div.setAlignment(Qt.AlignCenter)
                div.setStyleSheet(f"background-color: #182229; color: #8696a0; font-size: 12px; font-weight: bold; border-radius: 10px; padding: 4px 12px; font-family: '{self.chat_font_family}';")
                self.chat_feed_layout.addWidget(div, alignment=Qt.AlignCenter)
                last_date_str = note_date_str

            bubble = self._create_bubble_widget(note)
            self.chat_feed_layout.addWidget(bubble, alignment=Qt.AlignRight)

        if scroll_to_bottom:
            QTimer.singleShot(30, self._scroll_to_bottom)

    def _create_bubble_widget(self, note: ChatNote) -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        align = Qt.AlignRight if has_arabic else Qt.AlignLeft

        bubble = QFrame()
        bg_color = "#005c4b" if not note.is_starred else "#064e3b"
        border = "border: 1px solid #f59e0b;" if note.is_starred else "border: none;"
        bubble.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 14px; {border} }}")
        bubble.setMaximumWidth(700)

        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(14, 8, 14, 8)
        b_layout.setSpacing(6)

        # Top tag if starred or section
        sec_name = None
        if note.section_id and self.selected_section_id is None:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = f"{s_obj.icon} {s_obj.name}"

        if note.is_starred or sec_name:
            top_layout = QHBoxLayout()
            top_layout.setSpacing(8)
            if note.is_starred:
                star_tag = QLabel("⭐ مميزة")
                star_tag.setStyleSheet("color: #fde047; font-size: 12px; font-weight: bold; border: none;")
                top_layout.addWidget(star_tag)
            if sec_name:
                sec_tag = QLabel(sec_name)
                sec_tag.setStyleSheet("color: #a7f3d0; font-size: 12px; font-weight: bold; border: none;")
                top_layout.addWidget(sec_tag)
            top_layout.addStretch()
            b_layout.addLayout(top_layout)

        # Note text (22px Large Default font)
        content_lbl = QLabel(note.content)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_lbl.setAlignment(align)
        content_lbl.setStyleSheet(f"font-size: {self.chat_font_size}px; font-family: '{font_family}'; color: #e9edef; line-height: 1.4; border: none; background: transparent;")
        b_layout.addWidget(content_lbl)

        # Bottom Bar: Actions + Time + Checkmarks
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(4)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(56, 24)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 11px; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        bottom_layout.addWidget(copy_btn)

        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(28, 24)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_color = "#fde047" if note.is_starred else "white"
        star_btn.setStyleSheet(f"background-color: #128c7e; color: {star_color}; font-size: 12px; border-radius: 6px; border: none;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        bottom_layout.addWidget(star_btn)

        snip_btn = QPushButton("✂️ اختصار")
        snip_btn.setFixedSize(65, 24)
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 11px; border-radius: 6px; border: none;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        bottom_layout.addWidget(snip_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(28, 24)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #128c7e; color: #f87171; font-size: 11px; border-radius: 6px; border: none;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        bottom_layout.addWidget(del_btn)

        bottom_layout.addStretch()

        time_str = self._format_note_time(note.created_at)
        time_lbl = QLabel(f"{time_str} ✓✓")
        time_lbl.setStyleSheet("color: #8696a0; font-size: 11px; border: none;")
        bottom_layout.addWidget(time_lbl)

        b_layout.addLayout(bottom_layout)

        # Context Menu
        bubble.setContextMenuPolicy(Qt.CustomContextMenu)
        bubble.customContextMenuRequested.connect(lambda pos, n=note, b=bubble: self._show_bubble_menu(b, pos, n))

        return bubble

    def _show_bubble_menu(self, widget, pos, note: ChatNote):
        menu = QMenu(self)
        copy_act = menu.addAction("📋 نسخ النص")
        star_act = menu.addAction("⭐ تمييز بنجمة" if not note.is_starred else "⭐ إزالة النجمة")
        snip_act = menu.addAction("✂️ تحويل إلى اختصار (Snippet)")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ حذف الملاحظة")

        action = menu.exec(widget.mapToGlobal(pos))
        if action == copy_act:
            self._copy_note(note)
        elif action == star_act:
            self._toggle_star_note(note)
        elif action == snip_act:
            self._convert_to_snippet(note)
        elif action == del_act:
            self._delete_note_instant(note)

    def _format_note_time(self, created_at_str: str) -> str:
        try:
            dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return created_at_str[-8:]

    def _format_date_header(self, created_at_str: str) -> str:
        try:
            dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if dt.date() == now.date():
                return "اليوم - Today"
            elif (now.date() - dt.date()).days == 1:
                return "أمس - Yesterday"
            else:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            return "ملاحظات"

    def _scroll_to_bottom(self):
        bar = self.chat_scroll.verticalScrollBar()
        if bar:
            bar.setValue(bar.maximum())

    def _copy_note(self, note: ChatNote):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(note.content)
            self.toast_signal.emit("تم نسخ الملاحظة إلى الحافظة! 📋", False)

    def _toggle_star_note(self, note: ChatNote):
        new_state = toggle_star_chat_note(note.id)
        note.is_starred = new_state
        self.refresh_chat(scroll_to_bottom=False)

    def _delete_note_instant(self, note: ChatNote):
        delete_chat_note(note.id)
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=False)
        self.toast_signal.emit("تم حذف الملاحظة 🗑️", False)

    def _convert_to_snippet(self, note: ChatNote):
        self.navigate_to_snippet_signal.emit(note.content)
        self.toast_signal.emit("تم نقل الملاحظة إلى محرر الاختصارات ✂️", False)

    def _confirm_clear_all(self):
        reply = QMessageBox.question(
            self,
            "تأكيد المسح",
            "هل أنت متأكد من مسح جميع الملاحظات في هذا القسم؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            clear_all_chat_notes(section_id=self.selected_section_id)
            self.refresh_sections()
            self.refresh_chat()
            self.toast_signal.emit("تم مسح الملاحظات بنجاح 🗑️", False)
