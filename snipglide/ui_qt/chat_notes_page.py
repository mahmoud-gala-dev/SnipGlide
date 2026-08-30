import html
import re
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QMenu, QMessageBox,
    QApplication
)

from snipglide.database.chat_note_repo import (
    add_chat_note, add_chat_section, clear_all_chat_notes, delete_chat_note,
    delete_chat_section, get_all_chat_notes, get_all_chat_sections,
    get_chat_notes_count, seed_demo_chat_notes, toggle_star_chat_note
)
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting
from snipglide.models.chat_note import ChatNote, ChatNoteSection
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family
from snipglide.ui_qt.voice_player_widget import VoiceNotePlayerWidget
from snipglide.services.audio_service import global_recorder


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
        self._expanded_note_ids = set()

        # Load font settings
        self.chat_font_size = self._get_saved_font_size()
        self.chat_font_family = self._get_saved_font_family()

        self._setup_ui()

        if get_chat_notes_count() == 0:
            try:
                seed_demo_chat_notes()
            except Exception:
                pass

        QTimer.singleShot(30, self.refresh_sections)
        QTimer.singleShot(60, self.refresh_chat)

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
        main_layout.setContentsMargins(18, 12, 18, 18)
        main_layout.setSpacing(10)

        # ── 1. Top Header ──
        header = QFrame()
        header.setObjectName("headerFrame")
        header.setStyleSheet("""
            QFrame#headerFrame {
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 14px;
                padding: 6px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 8, 14, 8)
        h_layout.setSpacing(10)

        # Avatar
        avatar_lbl = QLabel("💬")
        avatar_lbl.setStyleSheet("font-size: 24px; background-color: #25D366; color: white; border-radius: 20px; padding: 4px 10px;")
        h_layout.addWidget(avatar_lbl)

        # Title and Count Badge
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_lbl = QLabel("شات الملاحظات السريعة (Quick Chat Notes)")
        self.title_lbl.setStyleSheet(f"font-size: 17px; font-weight: bold; font-family: '{self.chat_font_family}'; color: #f0f2f5;")
        self.count_badge = QLabel("سجل أفكارك وملاحظاتك بأسلوب محادثات الواتساب الأنيق")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{self.chat_font_family}'; color: #94a3b8;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.count_badge)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Font Controls: [A-] [22px] [A+]
        font_box = QFrame()
        font_box.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; padding: 2px;")
        fb_layout = QHBoxLayout(font_box)
        fb_layout.setContentsMargins(6, 3, 6, 3)
        fb_layout.setSpacing(6)

        down_btn = QPushButton("A-")
        down_btn.setFixedSize(32, 32)
        down_btn.setCursor(QCursor(Qt.PointingHandCursor))
        down_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 14px; border: none; color: #f0f2f5;")
        down_btn.clicked.connect(lambda: self._change_font_size(-1))
        fb_layout.addWidget(down_btn)

        self.font_size_lbl = QLabel(f"{self.chat_font_size}px")
        self.font_size_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #25D366;")
        fb_layout.addWidget(self.font_size_lbl)

        up_btn = QPushButton("A+")
        up_btn.setFixedSize(32, 32)
        up_btn.setCursor(QCursor(Qt.PointingHandCursor))
        up_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 14px; border: none; color: #f0f2f5;")
        up_btn.clicked.connect(lambda: self._change_font_size(1))
        fb_layout.addWidget(up_btn)
        h_layout.addWidget(font_box)

        # Font Selector Dropdown
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"])
        self.font_combo.setCurrentText(self.chat_font_family if self.chat_font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_combo.setFixedHeight(38)
        self.font_combo.setMinimumWidth(120)
        self.font_combo.currentTextChanged.connect(self._on_font_family_change)
        h_layout.addWidget(self.font_combo)

        # Visible Search Box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث وتمييز في الرسائل...")
        self.search_edit.setFixedHeight(38)
        self.search_edit.setFixedWidth(200)
        self.search_edit.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self.search_edit)

        # Star Filter
        self.star_filter_btn = QPushButton("⭐ المفضلة")
        self.star_filter_btn.setFixedHeight(38)
        self.star_filter_btn.setCheckable(True)
        self.star_filter_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 14px; font-weight: bold;")
        self.star_filter_btn.clicked.connect(self._toggle_star_filter)
        h_layout.addWidget(self.star_filter_btn)

        # Seed Demo Button
        demo_btn = QPushButton("🌱 عينات")
        demo_btn.setFixedHeight(38)
        demo_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 12px; font-weight: bold;")
        demo_btn.clicked.connect(self._seed_demo_data)
        h_layout.addWidget(demo_btn)

        # Scroll to Top / Bottom Buttons
        scroll_btn_box = QFrame()
        scroll_btn_box.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px;")
        sb_layout = QHBoxLayout(scroll_btn_box)
        sb_layout.setContentsMargins(4, 2, 4, 2)
        sb_layout.setSpacing(4)

        top_btn = QPushButton("🔼 للأعلى")
        top_btn.setFixedHeight(34)
        top_btn.setCursor(QCursor(Qt.PointingHandCursor))
        top_btn.setToolTip("الانتقال إلى بداية الرسائل الأولى")
        top_btn.setStyleSheet("background: transparent; color: #f0f2f5; font-weight: bold; font-size: 12px; border: none; padding: 2px 8px;")
        top_btn.clicked.connect(self._scroll_to_top)
        sb_layout.addWidget(top_btn)

        sep = QLabel("|")
        sep.setStyleSheet("color: #3b4a54; border: none;")
        sb_layout.addWidget(sep)

        bot_btn = QPushButton("🔽 للأسفل")
        bot_btn.setFixedHeight(34)
        bot_btn.setCursor(QCursor(Qt.PointingHandCursor))
        bot_btn.setToolTip("الانتقال إلى أحدث الرسائل بالأسفل")
        bot_btn.setStyleSheet("background: transparent; color: #25D366; font-weight: bold; font-size: 12px; border: none; padding: 2px 8px;")
        bot_btn.clicked.connect(self._scroll_to_bottom)
        sb_layout.addWidget(bot_btn)
        h_layout.addWidget(scroll_btn_box)

        # Clear Button
        clear_btn = QPushButton("🗑️ مسح")
        clear_btn.setFixedHeight(38)
        clear_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 10px; padding: 4px 14px; border: none;")
        clear_btn.clicked.connect(self._confirm_clear_all)
        h_layout.addWidget(clear_btn)

        main_layout.addWidget(header)

        # ── 2. Sections Bar ──
        self.sections_scroll = QScrollArea()
        self.sections_scroll.setFixedHeight(50)
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setStyleSheet("background: transparent; border: none;")

        self.sections_container = QWidget()
        self.sections_layout = QHBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 4, 0, 4)
        self.sections_layout.setSpacing(8)
        self.sections_layout.setAlignment(Qt.AlignLeft)
        self.sections_scroll.setWidget(self.sections_container)
        main_layout.addWidget(self.sections_scroll)

        # ── 3. Chat Feed Area ──
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("background-color: #0b141a; border-radius: 14px; border: 2px solid #202c33;")

        self.chat_feed_container = QWidget()
        self.chat_feed_container.setStyleSheet("background-color: transparent;")
        self.chat_feed_layout = QVBoxLayout(self.chat_feed_container)
        self.chat_feed_layout.setContentsMargins(18, 18, 18, 18)
        self.chat_feed_layout.setSpacing(10)
        self.chat_feed_layout.setAlignment(Qt.AlignTop)
        self.chat_scroll.setWidget(self.chat_feed_container)
        main_layout.addWidget(self.chat_scroll, stretch=1)

        # ── 4. Prominent Input Compose Bar ──
        compose_frame = QFrame()
        compose_frame.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 2px solid #2a3942;
                border-radius: 14px;
                padding: 8px;
            }
        """)
        comp_layout = QHBoxLayout(compose_frame)
        comp_layout.setContentsMargins(12, 8, 12, 8)
        comp_layout.setSpacing(10)

        # Section Selector
        self.compose_sec_combo = QComboBox()
        self.compose_sec_combo.setFixedHeight(48)
        self.compose_sec_combo.setMinimumWidth(130)
        comp_layout.addWidget(self.compose_sec_combo)

        # Timestamp button
        time_btn = QPushButton("🕒")
        time_btn.setFixedSize(48, 48)
        time_btn.setToolTip("إدراج التاريخ والوقت الحالي")
        time_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 18px; color: white;")
        time_btn.clicked.connect(self._insert_timestamp)
        comp_layout.addWidget(time_btn)

        # Star toggle button
        self.star_new_btn = QPushButton("⭐")
        self.star_new_btn.setFixedSize(48, 48)
        self.star_new_btn.setCheckable(True)
        # Voice Note Record button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(48, 48)
        self.mic_btn.setToolTip("تسجيل ملاحظة صوتية (Voice Note)")
        self.mic_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 20px; color: white;")
        self.mic_btn.clicked.connect(self._toggle_voice_record)
        comp_layout.addWidget(self.mic_btn)

        # Message Input (Prominent Border)
        self.message_input = QPlainTextEdit()
        self.message_input.setFixedHeight(62)
        self.message_input.setPlaceholderText("اكتب ملاحظتك هنا... (Enter للإرسال، Shift+Enter لسطر جديد)")
        self.message_input.setStyleSheet(f"""
            QPlainTextEdit {{
                font-size: {self.chat_font_size}px;
                font-family: '{self.chat_font_family}';
                background-color: #202c33;
                border: 2px solid #3b4a54;
                border-radius: 10px;
                padding: 10px 14px;
                color: #f0f2f5;
            }}
            QPlainTextEdit:focus {{
                background-color: #2a3942;
                border: 2px solid #25D366;
            }}
        """)
        self.message_input.installEventFilter(self)
        comp_layout.addWidget(self.message_input, stretch=1)

        # Send Button
        send_btn = QPushButton("➤ إرسال")
        send_btn.setFixedHeight(50)
        send_btn.setFixedWidth(110)
        send_btn.setCursor(QCursor(Qt.PointingHandCursor))
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #25D366;
                color: white;
                font-weight: bold;
                font-size: 16px;
                font-family: '{self.chat_font_family}';
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #1da851;
            }}
        """)
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
            self.message_input.setStyleSheet(f"""
                QPlainTextEdit {{
                    font-size: {new_size}px;
                    font-family: '{self.chat_font_family}';
                    background-color: #202c33;
                    border: 2px solid #3b4a54;
                    border-radius: 10px;
                    padding: 10px 14px;
                    color: #f0f2f5;
                }}
                QPlainTextEdit:focus {{
                    background-color: #2a3942;
                    border: 2px solid #25D366;
                }}
            """)
            self.refresh_chat(scroll_to_bottom=False)

    def _on_font_family_change(self, family: str):
        download_and_load_arabic_font(family)
        self.chat_font_family = family
        set_arabic_font_family(family)
        set_note_setting("chat_font_family", family)
        self.title_lbl.setStyleSheet(f"font-size: 17px; font-weight: bold; font-family: '{family}'; color: #f0f2f5;")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{family}'; color: #94a3b8;")
        self.message_input.setStyleSheet(f"""
            QPlainTextEdit {{
                font-size: {self.chat_font_size}px;
                font-family: '{family}';
                background-color: #202c33;
                border: 2px solid #3b4a54;
                border-radius: 10px;
                padding: 10px 14px;
                color: #f0f2f5;
            }}
            QPlainTextEdit:focus {{
                background-color: #2a3942;
                border: 2px solid #25D366;
            }}
        """)
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=False)

    def refresh_sections(self):
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = get_all_chat_sections()
        self._sections_cache = sections

        self.compose_sec_combo.clear()
        for s in sections:
            self.compose_sec_combo.addItem(f"{s.icon} {s.name}", s.id)

        all_count = get_chat_notes_count()
        all_btn = QPushButton(f"💬 الكل ({all_count})")
        all_btn.setFixedHeight(36)
        all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        is_all = self.selected_section_id is None
        all_style = "background-color: #25D366; color: white; font-weight: bold; border: none;" if is_all else "background-color: #182229; color: #f0f2f5; border: 1.5px solid #2a3942;"
        all_btn.setStyleSheet(f"{all_style} border-radius: 18px; padding: 4px 18px; font-size: 13px; font-family: '{self.chat_font_family}';")
        all_btn.clicked.connect(lambda: self._select_section(None))
        self.sections_layout.addWidget(all_btn)

        for sec in sections:
            count = get_chat_notes_count(section_id=sec.id)
            btn = QPushButton(f"{sec.icon} {sec.name} ({count})")
            btn.setFixedHeight(36)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            is_active = self.selected_section_id == sec.id
            btn_style = f"background-color: {sec.color}; color: white; font-weight: bold; border: none;" if is_active else "background-color: #182229; color: #f0f2f5; border: 1.5px solid #2a3942;"
            btn.setStyleSheet(f"{btn_style} border-radius: 18px; padding: 4px 16px; font-size: 13px; font-family: '{self.chat_font_family}';")
            btn.clicked.connect(lambda _, s=sec: self._select_section(s.id))
            if sec.id != 1:
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda pos, s=sec, b=btn: self._show_section_menu(b, pos, s))
            self.sections_layout.addWidget(btn)

        add_btn = QPushButton("➕ قسم جديد")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(f"background-color: #202c33; border: 1.5px dashed #3b4a54; color: #f0f2f5; border-radius: 18px; padding: 4px 16px; font-size: 13px; font-family: '{self.chat_font_family}'; font-weight: bold;")
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
        self.refresh_chat(scroll_to_bottom=False)

    def _toggle_star_filter(self):
        self.starred_filter_active = self.star_filter_btn.isChecked()
        if self.starred_filter_active:
            self.star_filter_btn.setStyleSheet("background-color: #f59e0b; border: 1.5px solid #d97706; color: white; font-weight: bold; border-radius: 10px; padding: 4px 14px;")
        else:
            self.star_filter_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 14px; font-weight: bold;")
        self.refresh_chat()

    def _toggle_voice_record(self):
        if not getattr(self, "_is_recording", False):
            self._is_recording = True
            self._record_seconds = 0
            self.mic_btn.setText("⏹️")
            self.mic_btn.setStyleSheet("background-color: #dc2626; color: white; border-radius: 10px; font-size: 20px; font-weight: bold;")
            self.message_input.setPlaceholderText("🔴 جارِ تسجيل صوتك الحقيقي من المايكروفون... (اضغط ⏹️ للحفظ والإرسال)")
            
            # Start real microphone audio recording
            global_recorder.start()

            self._record_timer = QTimer(self)
            self._record_timer.timeout.connect(self._update_record_ticker)
            self._record_timer.start(1000)
            self.toast_signal.emit("بدأ تسجيل صوتك من المايكروفون 🎙️", False)
        else:
            self._stop_and_save_voice_record()

    def _update_record_ticker(self):
        self._record_seconds += 1
        mins = self._record_seconds // 60
        secs = self._record_seconds % 60
        self.message_input.setPlaceholderText(f"🔴 تسجيل صوتي حي ({mins:02d}:{secs:02d}) • اضغط ⏹️ للحفظ والإرسال...")

    def _stop_and_save_voice_record(self):
        self._is_recording = False
        if hasattr(self, "_record_timer") and self._record_timer:
            self._record_timer.stop()
            self._record_timer = None

        self.mic_btn.setText("🎙️")
        self.mic_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 20px; color: white;")
        self.message_input.setPlaceholderText("اكتب ملاحظتك هنا... (Enter للإرسال، Shift+Enter لسطر جديد)")

        # Stop real microphone recording and get saved WAV file info
        rec_data = global_recorder.stop()

        dur = max(self._record_seconds, 1)
        audio_tag = ""
        if rec_data:
            dur = max(1, int(round(rec_data.get("duration", dur))))
            file_path = rec_data.get("file_path", "")
            audio_tag = f"\n[audio:{file_path}]"

        mins = dur // 60
        secs = dur % 60
        voice_content = f"🎙️ [ملاحظة صوتية - Voice Note ({mins:02d}:{secs:02d})]{audio_tag}"

        target_sec_id = self.compose_sec_combo.currentData() or 1
        try:
            add_chat_note(content=voice_content, is_starred=False, section_id=target_sec_id)
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
            self.toast_signal.emit("تم حفظ الملاحظة الصوتية الحقيقية بنجاح! 🎙️", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def _send_message(self):
        if getattr(self, "_is_recording", False):
            self._stop_and_save_voice_record()
            return

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
            empty_lbl.setStyleSheet(f"color: #94a3b8; font-size: 16px; font-family: '{self.chat_font_family}'; padding: 50px;")
            self.chat_feed_layout.addWidget(empty_lbl)
            return

        last_date_str = None
        for note in notes:
            note_date_str = self._format_date_header(note.created_at)
            if note_date_str != last_date_str:
                div = QLabel(f"  {note_date_str}  ")
                div.setAlignment(Qt.AlignCenter)
                div.setStyleSheet(f"background-color: #182229; color: #94a3b8; font-size: 13px; font-weight: bold; border-radius: 12px; padding: 6px 16px; font-family: '{self.chat_font_family}'; border: 1px solid #2a3942;")
                self.chat_feed_layout.addWidget(div, alignment=Qt.AlignCenter)
                last_date_str = note_date_str

            bubble = self._create_bubble_widget(note, search_query=query)
            self.chat_feed_layout.addWidget(bubble, alignment=Qt.AlignRight)

        if scroll_to_bottom:
            QTimer.singleShot(30, self._scroll_to_bottom)

    def _create_bubble_widget(self, note: ChatNote, search_query: str = "") -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        align = Qt.AlignRight if has_arabic else Qt.AlignLeft

        bubble = QFrame()
        bg_color = "#005c4b" if not note.is_starred else "#064e3b"
        border = "border: 2px solid #f59e0b;" if note.is_starred else "border: 1px solid #004d3e;"
        bubble.setCursor(QCursor(Qt.PointingHandCursor))
        bubble.setToolTip("انقر هنا لنسخ الملاحظة فوراً إلى الحافظة 📋")

        def _on_bubble_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note(n)
            QFrame.mousePressEvent(bubble, event)
        bubble.mousePressEvent = _on_bubble_clicked

        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(16, 10, 16, 10)
        b_layout.setSpacing(6)

        # Top tag
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
                star_tag.setStyleSheet("color: #fde047; font-size: 13px; font-weight: bold; border: none;")
                top_layout.addWidget(star_tag)
            if sec_name:
                sec_tag = QLabel(sec_name)
                sec_tag.setStyleSheet("color: #a7f3d0; font-size: 13px; font-weight: bold; border: none;")
                top_layout.addWidget(sec_tag)
            top_layout.addStretch()
            b_layout.addLayout(top_layout)

        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content

        if is_voice_note:
            voice_player = VoiceNotePlayerWidget(note.content, bubble)
            b_layout.addWidget(voice_player)
        else:
            # Truncation logic (Read more / Read less)
            is_long = len(note.content) > 220 or note.content.count("\n") >= 4
            is_expanded = note.id in self._expanded_note_ids

            display_text = note.content
            if is_long and not is_expanded and not search_query:
                display_text = note.content[:200] + "..."

            # Highlight Search Query with vivid highlight
            formatted_html = self._format_highlighted_text(display_text, search_query)

            content_lbl = QLabel()
            content_lbl.setTextFormat(Qt.RichText)
            content_lbl.setText(formatted_html)
            content_lbl.setWordWrap(True)
            content_lbl.setCursor(QCursor(Qt.PointingHandCursor))
            content_lbl.setAlignment(align)
            content_lbl.setStyleSheet(f"font-size: {self.chat_font_size}px; font-family: '{font_family}'; color: #f0f2f5; line-height: 1.4; border: none; background: transparent;")
            
            def _on_lbl_clicked(event, n=note):
                if event.button() == Qt.LeftButton:
                    self._copy_note(n)
                QLabel.mousePressEvent(content_lbl, event)
            content_lbl.mousePressEvent = _on_lbl_clicked
            b_layout.addWidget(content_lbl)

            # "Read more / Read less" Button
            if is_long and not search_query:
                more_btn = QPushButton("عرض أقل ▴" if is_expanded else "عرض المزيد ▾")
                more_btn.setCursor(QCursor(Qt.PointingHandCursor))
                more_btn.setStyleSheet("color: #6ee7b7; font-size: 13px; font-weight: bold; border: none; background: transparent; text-align: right; padding: 2px;")
                more_btn.clicked.connect(lambda _, nid=note.id: self._toggle_expand_note(nid))
                b_layout.addWidget(more_btn)

        # Bottom Bar: Actions + Time
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(6)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(62, 26)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        bottom_layout.addWidget(copy_btn)

        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(32, 26)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_color = "#fde047" if note.is_starred else "white"
        star_btn.setStyleSheet(f"background-color: #128c7e; color: {star_color}; font-size: 13px; border-radius: 6px; border: none;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        bottom_layout.addWidget(star_btn)

        snip_btn = QPushButton("✂️ اختصار")
        snip_btn.setFixedSize(74, 26)
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        bottom_layout.addWidget(snip_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(32, 26)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #128c7e; color: #fca5a5; font-size: 12px; border-radius: 6px; border: none;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        bottom_layout.addWidget(del_btn)

        bottom_layout.addStretch()

        time_str = self._format_note_time(note.created_at)
        # Double blue ticks for delivered feel
        time_lbl = QLabel(f"{time_str} <span style='color: #53bdeb; font-weight: 800;'>✓✓</span>")
        time_lbl.setTextFormat(Qt.RichText)
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold; border: none;")
        bottom_layout.addWidget(time_lbl)

        b_layout.addLayout(bottom_layout)

        # Context Menu
        bubble.setContextMenuPolicy(Qt.CustomContextMenu)
        bubble.customContextMenuRequested.connect(lambda pos, n=note, b=bubble: self._show_bubble_menu(b, pos, n))

        return bubble

    def _format_highlighted_text(self, text: str, query: str) -> str:
        escaped = html.escape(text).replace("\n", "<br>")
        if not query:
            return escaped

        pattern = re.compile(re.escape(html.escape(query)), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f'<span style="background-color: #facc15; color: #0f172a; font-weight: 800; border-radius: 4px; padding: 1px 5px;">{m.group(0)}</span>',
            escaped
        )
        return highlighted

    def _toggle_expand_note(self, note_id: int):
        if note_id in self._expanded_note_ids:
            self._expanded_note_ids.remove(note_id)
        else:
            self._expanded_note_ids.add(note_id)
        self.refresh_chat(scroll_to_bottom=False)

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

    def _scroll_to_top(self):
        bar = self.chat_scroll.verticalScrollBar()
        if bar:
            bar.setValue(bar.minimum())

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
