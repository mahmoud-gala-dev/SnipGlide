import html
import re
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QMenu, QMessageBox,
    QApplication, QDialog, QTextEdit
)

from snipglide.database.chat_note_repo import (
    add_chat_note, add_chat_section, clear_all_chat_notes, delete_chat_note,
    delete_chat_section, get_all_chat_notes, get_all_chat_sections,
    get_chat_notes_count, seed_demo_chat_notes, toggle_star_chat_note
)
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting
from snipglide.models.chat_note import ChatNote, ChatNoteSection
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family
from snipglide.utils.helpers import download_and_load_arabic_font
from snipglide.ui_qt.voice_player_widget import VoiceNotePlayerWidget
from snipglide.services.audio_service import global_recorder


STICKY_PALETTES = [
    {
        "name": "yellow",
        "bg": "#fef08a",
        "border": "#eab308",
        "text": "#713f12",
        "pin": "📌",
        "header_bg": "#fde047",
        "badge_bg": "#ca8a04",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#713f12",
    },
    {
        "name": "mint",
        "bg": "#bbf7d0",
        "border": "#22c55e",
        "text": "#14532d",
        "pin": "📌",
        "header_bg": "#86efac",
        "badge_bg": "#16a34a",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#14532d",
    },
    {
        "name": "cyan",
        "bg": "#bae6fd",
        "border": "#0ea5e9",
        "text": "#0c4a6e",
        "pin": "📌",
        "header_bg": "#7dd3fc",
        "badge_bg": "#0284c7",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#0c4a6e",
    },
    {
        "name": "lavender",
        "bg": "#e9d5ff",
        "border": "#a855f7",
        "text": "#581c87",
        "pin": "📌",
        "header_bg": "#d8b4fe",
        "badge_bg": "#9333ea",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#581c87",
    },
    {
        "name": "coral",
        "bg": "#fecdd3",
        "border": "#f43f5e",
        "text": "#881337",
        "pin": "📌",
        "header_bg": "#fda4af",
        "badge_bg": "#e11d48",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#881337",
    },
    {
        "name": "amber",
        "bg": "#fed7aa",
        "border": "#f97316",
        "text": "#7c2d12",
        "pin": "📌",
        "header_bg": "#fdba74",
        "badge_bg": "#ea580c",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_hover": "rgba(0, 0, 0, 0.16)",
        "action_text": "#7c2d12",
    },
]


class ZoomablePlainTextEdit(QPlainTextEdit):
    """QPlainTextEdit with support for Ctrl + Mouse Wheel zooming."""
    zoom_changed = Signal(int)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = 1 if event.angleDelta().y() > 0 else -1
            self.zoom_changed.emit(delta)
            event.accept()
        else:
            super().wheelEvent(event)


class NoteDetailDialogQt(QDialog):
    """Clean modal dialog to view and inspect a note in detail."""
    def __init__(self, note: ChatNote, font_family: str, font_size: int, section_name: str, parent=None, on_copy=None, on_star=None, on_snip=None, on_delete=None):
        super().__init__(parent)
        self.note = note
        self.on_copy = on_copy
        self.on_star = on_star
        self.on_snip = on_snip
        self.on_delete = on_delete
        
        self.setWindowTitle("تفاصيل الملاحظة (Note Details)")
        self.resize(620, 500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #111b21;
                border: 2px solid #25D366;
                border-radius: 14px;
            }}
            QLabel {{
                color: #f0f2f5;
                font-family: '{font_family}';
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)
        
        # Header Info
        h_row = QHBoxLayout()
        icon = QLabel("💬")
        icon.setStyleSheet("font-size: 20px;")
        h_row.addWidget(icon)
        
        sec_lbl = QLabel(f"القسم: {section_name}")
        sec_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #25D366;")
        h_row.addWidget(sec_lbl)
        
        if note.is_starred:
            star_badge = QLabel("⭐ مميزة")
            star_badge.setStyleSheet("color: #fde047; font-weight: bold; font-size: 13px;")
            h_row.addWidget(star_badge)
            
        h_row.addStretch()
        
        time_lbl = QLabel(f"التاريخ: {note.created_at}")
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        h_row.addWidget(time_lbl)
        layout.addLayout(h_row)
        
        # Body
        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content
        if is_voice_note:
            player = VoiceNotePlayerWidget(note.content, self)
            layout.addWidget(player)
            
        text_view = QTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(note.content)
        text_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: #182229;
                color: #f0f2f5;
                font-size: {font_size}px;
                font-family: '{font_family}';
                border: 1.5px solid #2a3942;
                border-radius: 10px;
                padding: 14px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(text_view, stretch=1)
        
        # Actions Toolbar
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        
        copy_btn = QPushButton("📋 نسخ إلى الحافظة")
        copy_btn.setFixedHeight(40)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; font-size: 14px; border-radius: 8px; border: none; padding: 4px 16px;")
        copy_btn.clicked.connect(self._copy_and_close)
        actions_row.addWidget(copy_btn)
        
        snip_btn = QPushButton("✂️ تحويل إلى اختصار")
        snip_btn.setFixedHeight(40)
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: #38bdf8; font-weight: bold; font-size: 13px; border-radius: 8px; padding: 4px 14px;")
        snip_btn.clicked.connect(self._snip_and_close)
        actions_row.addWidget(snip_btn)
        
        actions_row.addStretch()
        
        del_btn = QPushButton("🗑️ حذف")
        del_btn.setFixedHeight(40)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; font-size: 13px; border-radius: 8px; border: none; padding: 4px 14px;")
        del_btn.clicked.connect(self._delete_and_close)
        actions_row.addWidget(del_btn)
        
        close_btn = QPushButton("✕ إغلاق")
        close_btn.setFixedHeight(40)
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #94a3b8; font-weight: bold; font-size: 13px; border-radius: 8px; padding: 4px 14px;")
        close_btn.clicked.connect(self.accept)
        actions_row.addWidget(close_btn)
        
        layout.addLayout(actions_row)

    def _copy_and_close(self):
        if self.on_copy:
            self.on_copy(self.note)
        self.accept()

    def _snip_and_close(self):
        if self.on_snip:
            self.on_snip(self.note)
        self.accept()

    def _delete_and_close(self):
        if self.on_delete:
            self.on_delete(self.note)
        self.accept()


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

        # Load font & view settings
        self.chat_font_size = self._get_saved_font_size()
        self.chat_font_family = self._get_saved_font_family()
        self.view_mode = self._get_saved_view_mode()
        self.mode_buttons = {}

        self._setup_ui()

        if get_chat_notes_count() == 0:
            try:
                seed_demo_chat_notes()
            except Exception:
                pass

        QTimer.singleShot(30, self.refresh_sections)
        QTimer.singleShot(60, lambda: self.refresh_chat(scroll_to_bottom=(self.view_mode == "chat")))

    def _get_saved_font_size(self) -> int:
        try:
            val = int(get_note_setting("chat_font_size", "20"))
            if val < 14:
                val = 20
                set_note_setting("chat_font_size", "20")
            return min(max(val, 12), 40)
        except Exception:
            return 20

    def _get_saved_font_family(self) -> str:
        saved = get_note_setting("chat_font_family", "Tajawal")
        return saved if saved else get_arabic_font_family()

    def _get_saved_view_mode(self) -> str:
        saved = get_note_setting("chat_view_mode", "chat")
        if saved in ("chat", "grid", "list", "sticky"):
            return saved
        return "chat"

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 14, 20, 20)
        main_layout.setSpacing(12)

        # ═════════════════════════════════════════════════════════════════════
        # ── 1. Top Integrated Header (Clean 2-Tier Organization) ──
        # ═════════════════════════════════════════════════════════════════════
        header = QFrame()
        header.setObjectName("headerFrame")
        header.setStyleSheet("""
            QFrame#headerFrame {
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 16px;
                padding: 10px 14px;
            }
        """)
        h_main_layout = QVBoxLayout(header)
        h_main_layout.setContentsMargins(4, 4, 4, 4)
        h_main_layout.setSpacing(10)

        # ── Tier 1: Title & Main Actions ──
        tier1_row = QHBoxLayout()
        tier1_row.setSpacing(12)

        avatar_lbl = QLabel("💬")
        avatar_lbl.setStyleSheet("font-size: 24px; background-color: #25D366; color: white; border-radius: 20px; padding: 4px 10px;")
        tier1_row.addWidget(avatar_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_lbl = QLabel("شات الملاحظات السريعة (Quick Chat Notes)")
        self.title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; font-family: '{self.chat_font_family}'; color: #f0f2f5;")
        self.count_badge = QLabel("سجل أفكارك وملاحظاتك بأسلوب محادثات الواتساب الأنيق • انقر على أي ملاحظة لنسخها فوراً")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{self.chat_font_family}'; color: #94a3b8;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.count_badge)
        tier1_row.addLayout(title_box)

        tier1_row.addStretch()

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في جميع الملاحظات...")
        self.search_edit.setFixedHeight(38)
        self.search_edit.setMinimumWidth(220)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 10px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 14px;
                font-family: '{self.chat_font_family}';
            }}
            QLineEdit:focus {{
                border: 1.5px solid #25D366;
                background-color: #2a3942;
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        tier1_row.addWidget(self.search_edit)

        # Star Filter Button
        self.star_filter_btn = QPushButton("⭐ المفضلة")
        self.star_filter_btn.setFixedHeight(38)
        self.star_filter_btn.setCheckable(True)
        self.star_filter_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.star_filter_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 14px; font-weight: bold; font-size: 13px;")
        self.star_filter_btn.clicked.connect(self._toggle_star_filter)
        tier1_row.addWidget(self.star_filter_btn)

        # Demo Seed Button
        demo_btn = QPushButton("🌱 عينات")
        demo_btn.setFixedHeight(38)
        demo_btn.setCursor(QCursor(Qt.PointingHandCursor))
        demo_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: #f0f2f5; border-radius: 10px; padding: 4px 12px; font-weight: bold; font-size: 13px;")
        demo_btn.clicked.connect(self._seed_demo_data)
        tier1_row.addWidget(demo_btn)

        # Clear Notes Button
        clear_btn = QPushButton("🗑️ مسح الكل")
        clear_btn.setFixedHeight(38)
        clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        clear_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 10px; padding: 4px 14px; border: none; font-size: 13px;")
        clear_btn.clicked.connect(self._confirm_clear_all)
        tier1_row.addWidget(clear_btn)

        h_main_layout.addLayout(tier1_row)

        # ── Tier 2: View Modes Toolbar & Formatting Controls ──
        tier2_row = QHBoxLayout()
        tier2_row.setSpacing(12)

        # View Mode Switcher
        view_box = QFrame()
        view_box.setStyleSheet("background-color: #182229; border: 1.5px solid #2a3942; border-radius: 10px; padding: 2px;")
        vb_layout = QHBoxLayout(view_box)
        vb_layout.setContentsMargins(4, 2, 4, 2)
        vb_layout.setSpacing(4)

        modes = [
            ("chat", "💬 محادثة", "طريقة عرض المحادثات وفقاعات الدردشة (WhatsApp Style)"),
            ("grid", "🗂️ بطاقات وشبكة", "طريقة عرض شبكة البطاقات المنظمة (Cards Grid)"),
            ("list", "📋 قائمة مدمجة", "طريقة عرض القائمة السريعة المضغوطة (Compact List)"),
            ("sticky", "📌 ملصقات ملونة", "طريقة عرض لوحة الملاحظات اللاصقة الملونة (Sticky Board)"),
        ]

        self.mode_buttons = {}
        for mode_key, mode_label, mode_tip in modes:
            btn = QPushButton(mode_label)
            btn.setFixedHeight(34)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setToolTip(mode_tip)
            btn.clicked.connect(lambda _, m=mode_key: self._set_view_mode(m))
            self.mode_buttons[mode_key] = btn
            vb_layout.addWidget(btn)

        self._update_mode_buttons_style()
        tier2_row.addWidget(view_box)

        tier2_row.addStretch()

        # Font Controls: [A-] [20px] [A+]
        font_box = QFrame()
        font_box.setStyleSheet("background-color: #182229; border: 1.5px solid #2a3942; border-radius: 10px; padding: 2px;")
        fb_layout = QHBoxLayout(font_box)
        fb_layout.setContentsMargins(6, 2, 6, 2)
        fb_layout.setSpacing(6)

        down_btn = QPushButton("A-")
        down_btn.setFixedSize(30, 30)
        down_btn.setCursor(QCursor(Qt.PointingHandCursor))
        down_btn.setToolTip("تصغير الخط (Ctrl+-)")
        down_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; border: none; color: #f0f2f5;")
        down_btn.clicked.connect(lambda: self._change_font_size(-1))
        fb_layout.addWidget(down_btn)

        self.font_size_lbl = QLabel(f"{self.chat_font_size}px")
        self.font_size_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #25D366;")
        fb_layout.addWidget(self.font_size_lbl)

        up_btn = QPushButton("A+")
        up_btn.setFixedSize(30, 30)
        up_btn.setCursor(QCursor(Qt.PointingHandCursor))
        up_btn.setToolTip("تكبير الخط (Ctrl++)")
        up_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; border: none; color: #f0f2f5;")
        up_btn.clicked.connect(lambda: self._change_font_size(1))
        fb_layout.addWidget(up_btn)
        tier2_row.addWidget(font_box)

        # Font Selector Dropdown
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"])
        self.font_combo.setCurrentText(self.chat_font_family if self.chat_font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_combo.setFixedHeight(36)
        self.font_combo.setMinimumWidth(110)
        self.font_combo.currentTextChanged.connect(self._on_font_family_change)
        tier2_row.addWidget(self.font_combo)

        # Scroll to Top / Bottom Buttons
        scroll_btn_box = QFrame()
        scroll_btn_box.setStyleSheet("background-color: #182229; border: 1.5px solid #2a3942; border-radius: 10px;")
        sb_layout = QHBoxLayout(scroll_btn_box)
        sb_layout.setContentsMargins(4, 2, 4, 2)
        sb_layout.setSpacing(4)

        top_btn = QPushButton("🔼 للأعلى")
        top_btn.setFixedHeight(32)
        top_btn.setCursor(QCursor(Qt.PointingHandCursor))
        top_btn.setToolTip("الانتقال إلى بداية الملاحظات الأولى")
        top_btn.setStyleSheet("background: transparent; color: #f0f2f5; font-weight: bold; font-size: 12px; border: none; padding: 2px 8px;")
        top_btn.clicked.connect(self._scroll_to_top)
        sb_layout.addWidget(top_btn)

        sep = QLabel("|")
        sep.setStyleSheet("color: #3b4a54; border: none;")
        sb_layout.addWidget(sep)

        bot_btn = QPushButton("🔽 للأسفل")
        bot_btn.setFixedHeight(32)
        bot_btn.setCursor(QCursor(Qt.PointingHandCursor))
        bot_btn.setToolTip("الانتقال إلى أحدث الملاحظات")
        bot_btn.setStyleSheet("background: transparent; color: #25D366; font-weight: bold; font-size: 12px; border: none; padding: 2px 8px;")
        bot_btn.clicked.connect(self._scroll_to_bottom)
        sb_layout.addWidget(bot_btn)
        tier2_row.addWidget(scroll_btn_box)

        h_main_layout.addLayout(tier2_row)
        main_layout.addWidget(header)

        # ═════════════════════════════════════════════════════════════════════
        # ── 2. Sections Category Bar ──
        # ═════════════════════════════════════════════════════════════════════
        self.sections_scroll = QScrollArea()
        self.sections_scroll.setFixedHeight(50)
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sections_scroll.setStyleSheet("background: transparent; border: none;")

        self.sections_container = QWidget()
        self.sections_layout = QHBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 2, 0, 2)
        self.sections_layout.setSpacing(8)
        self.sections_layout.setAlignment(Qt.AlignLeft)
        self.sections_scroll.setWidget(self.sections_container)
        main_layout.addWidget(self.sections_scroll)

        # ═════════════════════════════════════════════════════════════════════
        # ── 3. Spacious Content Feed Area (Chat, Cards, List, Stickies) ──
        # ═════════════════════════════════════════════════════════════════════
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0b141a;
                border-radius: 16px;
                border: 2px solid #202c33;
            }
        """)

        self.chat_feed_container = QWidget()
        self.chat_feed_container.setStyleSheet("background-color: transparent;")
        self.chat_feed_layout = QVBoxLayout(self.chat_feed_container)
        self.chat_feed_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_feed_layout.setSpacing(12)
        self.chat_feed_layout.setAlignment(Qt.AlignTop)
        self.chat_scroll.setWidget(self.chat_feed_container)
        main_layout.addWidget(self.chat_scroll, stretch=1)

        # ═════════════════════════════════════════════════════════════════════
        # ── 4. Prominent Input Compose Bar ──
        # ═════════════════════════════════════════════════════════════════════
        compose_frame = QFrame()
        compose_frame.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 2px solid #2a3942;
                border-radius: 16px;
                padding: 8px 12px;
            }
        """)
        comp_layout = QHBoxLayout(compose_frame)
        comp_layout.setContentsMargins(10, 8, 10, 8)
        comp_layout.setSpacing(10)

        # Section Selector
        self.compose_sec_combo = QComboBox()
        self.compose_sec_combo.setFixedHeight(48)
        self.compose_sec_combo.setMinimumWidth(130)
        comp_layout.addWidget(self.compose_sec_combo)

        # Timestamp button
        time_btn = QPushButton("🕒")
        time_btn.setFixedSize(48, 48)
        time_btn.setCursor(QCursor(Qt.PointingHandCursor))
        time_btn.setToolTip("إدراج التاريخ والوقت الحالي في النص")
        time_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 18px; color: white;")
        time_btn.clicked.connect(self._insert_timestamp)
        comp_layout.addWidget(time_btn)

        # Star toggle button
        self.star_new_btn = QPushButton("⭐")
        self.star_new_btn.setFixedSize(48, 48)
        self.star_new_btn.setCheckable(True)
        self.star_new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.star_new_btn.setToolTip("تمييز الملاحظة الجديدة بنجمة مفضلة")
        self.star_new_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 18px; color: white;")
        comp_layout.addWidget(self.star_new_btn)

        # Voice Note Record button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(48, 48)
        self.mic_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.mic_btn.setToolTip("تسجيل ملاحظة صوتية حقيقية (Voice Note)")
        self.mic_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; font-size: 20px; color: white;")
        self.mic_btn.clicked.connect(self._toggle_voice_record)
        comp_layout.addWidget(self.mic_btn)

        # Message Input (Zoomable with Ctrl+Wheel & Ctrl++)
        self.message_input = ZoomablePlainTextEdit()
        self.message_input.setFixedHeight(68)
        self.message_input.setPlaceholderText("اكتب ملاحظتك هنا... (Enter للإرسال، Shift+Enter لسطر جديد • تكبير الخط بـ Ctrl + عجلة الفأرة)")
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
        self.message_input.zoom_changed.connect(self._change_font_size)
        self.message_input.installEventFilter(self)
        comp_layout.addWidget(self.message_input, stretch=1)

        # Send Button
        send_btn = QPushButton("➤ حفظ وإرسال")
        send_btn.setFixedHeight(50)
        send_btn.setFixedWidth(130)
        send_btn.setCursor(QCursor(Qt.PointingHandCursor))
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #25D366;
                color: white;
                font-weight: bold;
                font-size: 15px;
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

    def _set_view_mode(self, mode: str):
        if self.view_mode == mode:
            return
        self.view_mode = mode
        set_note_setting("chat_view_mode", mode)
        self._update_mode_buttons_style()
        self.refresh_chat(scroll_to_bottom=(mode == "chat"))
        mode_names = {
            "chat": "محادثة",
            "grid": "بطاقات وشبكة",
            "list": "قائمة مدمجة",
            "sticky": "ملصقات ملونة",
        }
        self.toast_signal.emit(f"تم التحويل إلى نمط: {mode_names.get(mode, mode)} ✨", False)

    def _update_mode_buttons_style(self):
        for mode_key, btn in self.mode_buttons.items():
            if mode_key == self.view_mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #25D366;
                        color: #0b141a;
                        font-weight: bold;
                        font-size: 13px;
                        font-family: '{self.chat_font_family}';
                        border-radius: 8px;
                        border: none;
                        padding: 3px 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #94a3b8;
                        font-weight: bold;
                        font-size: 13px;
                        font-family: '{self.chat_font_family}';
                        border-radius: 8px;
                        border: none;
                        padding: 3px 12px;
                    }}
                    QPushButton:hover {{
                        background-color: #2a3942;
                        color: #f0f2f5;
                    }}
                """)

    def eventFilter(self, obj, event):
        if obj is self.message_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self._send_message()
                return True
            if (event.modifiers() & Qt.ControlModifier) and event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self._change_font_size(1)
                return True
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Minus:
                self._change_font_size(-1)
                return True
        return super().eventFilter(obj, event)

    def _change_font_size(self, delta: int):
        new_size = min(max(self.chat_font_size + delta, 12), 40)
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
        self.title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; font-family: '{family}'; color: #f0f2f5;")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{family}'; color: #94a3b8;")
        self._update_mode_buttons_style()
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
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
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
        self.refresh_chat(scroll_to_bottom=(self.view_mode == "chat"))

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
            self.refresh_chat(scroll_to_bottom=(self.view_mode == "chat"))
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
            self.star_filter_btn.setStyleSheet("background-color: #f59e0b; border: 1.5px solid #d97706; color: white; font-weight: bold; border-radius: 10px; padding: 4px 14px; font-size: 13px;")
        else:
            self.star_filter_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 14px; font-weight: bold; font-size: 13px;")
        self.refresh_chat(scroll_to_bottom=False)

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
            self.refresh_chat(scroll_to_bottom=(self.view_mode == "chat"))
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
            self.refresh_chat(scroll_to_bottom=(self.view_mode == "chat"))
            self.toast_signal.emit("تم حفظ الملاحظة بنجاح 💬", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def refresh_chat(self, scroll_to_bottom: bool = False):
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

        self.count_badge.setText(f"القسم: [{sec_name}] • الإجمالي: {total_count} • المعروض: {current_count} • انقر على أي ملاحظة لنسخها فوراً 📋")

        if not notes:
            empty_lbl = QLabel("صندوق الملاحظات فارغ.\nاكتب فكرتك أو ملاحظتك في صندوق الكتابة بالأسفل واضغط Enter لحفظها فوراً!")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(f"color: #94a3b8; font-size: 16px; font-family: '{self.chat_font_family}'; padding: 50px;")
            self.chat_feed_layout.addWidget(empty_lbl)
            return

        # Dispatch to active view mode
        if self.view_mode == "grid":
            self._render_cards_grid(notes, query)
        elif self.view_mode == "list":
            self._render_compact_list(notes, query)
        elif self.view_mode == "sticky":
            self._render_sticky_notes(notes, query)
        else:  # "chat" mode
            self._render_chat_feed(notes, query)

        if scroll_to_bottom and self.view_mode == "chat":
            QTimer.singleShot(30, self._scroll_to_bottom)

    # ── 1. Render Mode: Chat Feed ──
    def _render_chat_feed(self, notes, query: str):
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

    # ── 2. Render Mode: Cards Grid ──
    def _render_cards_grid(self, notes, query: str):
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)

        cols = 2
        for idx, note in enumerate(notes):
            card = self._create_card_widget(note, search_query=query)
            grid.addWidget(card, idx // cols, idx % cols)

        self.chat_feed_layout.addWidget(grid_widget)

    # ── 3. Render Mode: Compact List ──
    def _render_compact_list(self, notes, query: str):
        for note in notes:
            row = self._create_compact_row_widget(note, search_query=query)
            self.chat_feed_layout.addWidget(row)

    # ── 4. Render Mode: Sticky Notes Board ──
    def _render_sticky_notes(self, notes, query: str):
        sticky_widget = QWidget()
        sticky_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(sticky_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        cols = 3
        for idx, note in enumerate(notes):
            sticky_card = self._create_sticky_note_widget(note, idx, search_query=query)
            grid.addWidget(sticky_card, idx // cols, idx % cols)

        self.chat_feed_layout.addWidget(sticky_widget)

    # ── Widget: Chat Bubble ──
    def _create_bubble_widget(self, note: ChatNote, search_query: str = "") -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        align = Qt.AlignRight if has_arabic else Qt.AlignLeft

        bubble = QFrame()
        bg_color = "#005c4b" if not note.is_starred else "#064e3b"
        border = "border: 2px solid #f59e0b;" if note.is_starred else "border: 1px solid #004d3e;"
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                {border}
                border-radius: 14px;
            }}
            QFrame:hover {{
                border-color: #25D366;
            }}
        """)
        bubble.setCursor(QCursor(Qt.PointingHandCursor))
        bubble.setToolTip("انقر هنا لنسخ الملاحظة فوراً إلى الحافظة 📋 (أو انقر نقراً مزدوجاً لعرض التفاصيل)")

        # 1-Click to Copy & Double Click to view details
        def _on_bubble_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note(n)
            QFrame.mousePressEvent(bubble, event)
        bubble.mousePressEvent = _on_bubble_clicked

        def _on_bubble_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_details_dialog(n)
            QFrame.mouseDoubleClickEvent(bubble, event)
        bubble.mouseDoubleClickEvent = _on_bubble_dbl_clicked

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
                star_tag.setStyleSheet("color: #fde047; font-size: 13px; font-weight: bold; border: none; background: transparent;")
                top_layout.addWidget(star_tag)
            if sec_name:
                sec_tag = QLabel(sec_name)
                sec_tag.setStyleSheet("color: #a7f3d0; font-size: 13px; font-weight: bold; border: none; background: transparent;")
                top_layout.addWidget(sec_tag)
            top_layout.addStretch()
            b_layout.addLayout(top_layout)

        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content

        if is_voice_note:
            voice_player = VoiceNotePlayerWidget(note.content, bubble)
            b_layout.addWidget(voice_player)
        else:
            is_long = len(note.content) > 220 or note.content.count("\n") >= 4
            is_expanded = note.id in self._expanded_note_ids

            display_text = note.content
            if is_long and not is_expanded and not search_query:
                display_text = note.content[:200] + "..."

            formatted_html = self._format_highlighted_text(display_text, search_query)

            content_lbl = QLabel()
            content_lbl.setTextFormat(Qt.RichText)
            content_lbl.setText(formatted_html)
            content_lbl.setWordWrap(True)
            content_lbl.setAlignment(align)
            content_lbl.setCursor(QCursor(Qt.PointingHandCursor))
            content_lbl.setStyleSheet(f"font-size: {self.chat_font_size}px; font-family: '{font_family}'; color: #f0f2f5; line-height: 1.4; border: none; background: transparent;")
            
            def _on_lbl_clicked(event, n=note):
                if event.button() == Qt.LeftButton:
                    self._copy_note(n)
                QLabel.mousePressEvent(content_lbl, event)
            content_lbl.mousePressEvent = _on_lbl_clicked
            b_layout.addWidget(content_lbl)

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
        copy_btn.setFixedSize(64, 28)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setToolTip("نسخ نص الملاحظة إلى الحافظة")
        copy_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        bottom_layout.addWidget(copy_btn)

        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(32, 28)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_btn.setToolTip("تمييز بنجمة")
        star_color = "#fde047" if note.is_starred else "white"
        star_btn.setStyleSheet(f"background-color: #128c7e; color: {star_color}; font-size: 13px; border-radius: 6px; border: none;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        bottom_layout.addWidget(star_btn)

        snip_btn = QPushButton("✂️ اختصار")
        snip_btn.setFixedSize(76, 28)
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setToolTip("تحويل الملاحظة إلى اختصار جاهز للتوسيع")
        snip_btn.setStyleSheet("background-color: #128c7e; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        bottom_layout.addWidget(snip_btn)

        view_btn = QPushButton("🔍 تفاصيل")
        view_btn.setFixedSize(72, 28)
        view_btn.setCursor(QCursor(Qt.PointingHandCursor))
        view_btn.setToolTip("عرض الملاحظة بالكامل في نافذة مريحة")
        view_btn.setStyleSheet("background-color: #128c7e; color: #a7f3d0; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        view_btn.clicked.connect(lambda _, n=note: self._open_note_details_dialog(n))
        bottom_layout.addWidget(view_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(32, 28)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setToolTip("حذف الملاحظة")
        del_btn.setStyleSheet("background-color: #128c7e; color: #fca5a5; font-size: 12px; border-radius: 6px; border: none;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        bottom_layout.addWidget(del_btn)

        bottom_layout.addStretch()

        time_str = self._format_note_time(note.created_at)
        time_lbl = QLabel(f"{time_str} <span style='color: #53bdeb; font-weight: 800;'>✓✓</span>")
        time_lbl.setTextFormat(Qt.RichText)
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        bottom_layout.addWidget(time_lbl)

        b_layout.addLayout(bottom_layout)

        bubble.setContextMenuPolicy(Qt.CustomContextMenu)
        bubble.customContextMenuRequested.connect(lambda pos, n=note, b=bubble: self._show_bubble_menu(b, pos, n))

        return bubble

    # ── Widget: Card View (Grid Mode) ──
    def _create_card_widget(self, note: ChatNote, search_query: str = "") -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        align = Qt.AlignRight if has_arabic else Qt.AlignLeft

        card = QFrame()
        card_border = "border: 1.5px solid #f59e0b;" if note.is_starred else "border: 1.5px solid #2a3942;"
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #182229;
                {card_border}
                border-radius: 14px;
            }}
            QFrame:hover {{
                border-color: #25D366;
            }}
        """)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setToolTip("انقر هنا لنسخ الملاحظة فوراً إلى الحافظة 📋 (أو انقر نقراً مزدوجاً للتفاصيل)")

        def _on_card_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note(n)
            QFrame.mousePressEvent(card, event)
        card.mousePressEvent = _on_card_clicked

        def _on_card_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_details_dialog(n)
            QFrame.mouseDoubleClickEvent(card, event)
        card.mouseDoubleClickEvent = _on_card_dbl_clicked

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(10)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        # Section info
        sec_name = "💬 ملاحظات"
        sec_color = "#25D366"
        if note.section_id:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = f"{s_obj.icon} {s_obj.name}"
                sec_color = s_obj.color

        sec_badge = QLabel(sec_name)
        sec_badge.setStyleSheet(f"background-color: {sec_color}; color: white; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 2px 8px; border: none;")
        header_row.addWidget(sec_badge)

        if note.is_starred:
            star_lbl = QLabel("⭐ مميزة")
            star_lbl.setStyleSheet("color: #fde047; font-size: 12px; font-weight: bold; border: none; background: transparent;")
            header_row.addWidget(star_lbl)

        header_row.addStretch()

        time_str = self._format_note_time(note.created_at)
        time_lbl = QLabel(f"🕒 {time_str}")
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        header_row.addWidget(time_lbl)
        c_layout.addLayout(header_row)

        # Body: Audio or Text
        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content
        if is_voice_note:
            voice_player = VoiceNotePlayerWidget(note.content, card)
            c_layout.addWidget(voice_player)
        else:
            is_long = len(note.content) > 180 or note.content.count("\n") >= 3
            is_expanded = note.id in self._expanded_note_ids

            display_text = note.content
            if is_long and not is_expanded and not search_query:
                display_text = note.content[:160] + "..."

            formatted_html = self._format_highlighted_text(display_text, search_query)

            content_lbl = QLabel()
            content_lbl.setTextFormat(Qt.RichText)
            content_lbl.setText(formatted_html)
            content_lbl.setWordWrap(True)
            content_lbl.setAlignment(align)
            content_lbl.setCursor(QCursor(Qt.PointingHandCursor))
            content_lbl.setStyleSheet(f"font-size: {max(self.chat_font_size - 2, 14)}px; font-family: '{font_family}'; color: #f0f2f5; line-height: 1.4; border: none; background: transparent;")
            
            def _on_clbl_clicked(event, n=note):
                if event.button() == Qt.LeftButton:
                    self._copy_note(n)
                QLabel.mousePressEvent(content_lbl, event)
            content_lbl.mousePressEvent = _on_clbl_clicked
            c_layout.addWidget(content_lbl)

            if is_long and not search_query:
                more_btn = QPushButton("عرض أقل ▴" if is_expanded else "عرض المزيد ▾")
                more_btn.setCursor(QCursor(Qt.PointingHandCursor))
                more_btn.setStyleSheet("color: #25D366; font-size: 12px; font-weight: bold; border: none; background: transparent; text-align: right; padding: 2px;")
                more_btn.clicked.connect(lambda _, nid=note.id: self._toggle_expand_note(nid))
                c_layout.addWidget(more_btn)

        # Footer Actions Toolbar
        footer = QHBoxLayout()
        footer.setSpacing(6)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(62, 28)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #f0f2f5; font-size: 12px; font-weight: bold; border-radius: 6px;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        footer.addWidget(copy_btn)

        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(32, 28)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_color = "#fde047" if note.is_starred else "#94a3b8"
        star_btn.setStyleSheet(f"background-color: #202c33; border: 1px solid #3b4a54; color: {star_color}; font-size: 13px; border-radius: 6px;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        footer.addWidget(star_btn)

        snip_btn = QPushButton("✂️")
        snip_btn.setFixedSize(34, 28)
        snip_btn.setToolTip("تحويل إلى اختصار Snippet")
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #38bdf8; font-size: 13px; border-radius: 6px;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        footer.addWidget(snip_btn)

        view_btn = QPushButton("🔍")
        view_btn.setFixedSize(34, 28)
        view_btn.setToolTip("عرض التفاصيل كاملة")
        view_btn.setCursor(QCursor(Qt.PointingHandCursor))
        view_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #a7f3d0; font-size: 13px; border-radius: 6px;")
        view_btn.clicked.connect(lambda _, n=note: self._open_note_details_dialog(n))
        footer.addWidget(view_btn)

        footer.addStretch()

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(32, 28)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #fca5a5; font-size: 12px; border-radius: 6px;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        footer.addWidget(del_btn)

        c_layout.addLayout(footer)

        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, n=note, b=card: self._show_bubble_menu(b, pos, n))

        return card

    # ── Widget: Compact Row (List Mode) ──
    def _create_compact_row_widget(self, note: ChatNote, search_query: str = "") -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"

        row = QFrame()
        row_border = "border: 1px solid #f59e0b;" if note.is_starred else "border: 1px solid #2a3942;"
        row.setStyleSheet(f"""
            QFrame {{
                background-color: #182229;
                {row_border}
                border-radius: 10px;
            }}
            QFrame:hover {{
                border-color: #25D366;
            }}
        """)
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row.setToolTip("انقر هنا لنسخ الملاحظة فوراً 📋 (أو انقر نقراً مزدوجاً للتفاصيل)")

        def _on_row_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note(n)
            QFrame.mousePressEvent(row, event)
        row.mousePressEvent = _on_row_clicked

        def _on_row_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_details_dialog(n)
            QFrame.mouseDoubleClickEvent(row, event)
        row.mouseDoubleClickEvent = _on_row_dbl_clicked

        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(14, 10, 14, 10)
        r_layout.setSpacing(10)

        # Star toggle
        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(28, 28)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_color = "#fde047" if note.is_starred else "#64748b"
        star_btn.setStyleSheet(f"background: transparent; color: {star_color}; font-size: 14px; border: none;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        r_layout.addWidget(star_btn)

        # Section pill
        sec_name = "ملاحظات"
        sec_color = "#25D366"
        if note.section_id:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = s_obj.name
                sec_color = s_obj.color

        sec_lbl = QLabel(sec_name)
        sec_lbl.setStyleSheet(f"background-color: {sec_color}; color: white; font-size: 11px; font-weight: bold; border-radius: 5px; padding: 3px 8px; border: none;")
        r_layout.addWidget(sec_lbl)

        # Content Summary
        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content
        if is_voice_note:
            text_summary = "🎙️ ملاحظة صوتية (انقر للنسخ أو اضغط تفاصيل)"
            content_lbl = QLabel(text_summary)
            content_lbl.setStyleSheet(f"font-size: 13px; font-family: '{font_family}'; color: #38bdf8; font-weight: bold; border: none; background: transparent;")
        else:
            clean_text = note.content.replace("\n", " ")
            if len(clean_text) > 120:
                clean_text = clean_text[:115] + "..."
            formatted_html = self._format_highlighted_text(clean_text, search_query)
            content_lbl = QLabel()
            content_lbl.setTextFormat(Qt.RichText)
            content_lbl.setText(formatted_html)
            content_lbl.setStyleSheet(f"font-size: 14px; font-family: '{font_family}'; color: #f0f2f5; border: none; background: transparent;")

        r_layout.addWidget(content_lbl, stretch=1)

        # Time
        time_str = self._format_note_time(note.created_at)
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; background: transparent;")
        r_layout.addWidget(time_lbl)

        # Action Buttons
        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(58, 26)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        r_layout.addWidget(copy_btn)

        view_btn = QPushButton("🔍")
        view_btn.setFixedSize(28, 26)
        view_btn.setToolTip("عرض التفاصيل")
        view_btn.setCursor(QCursor(Qt.PointingHandCursor))
        view_btn.setStyleSheet("background-color: #202c33; color: #a7f3d0; font-size: 12px; border-radius: 6px; border: 1px solid #3b4a54;")
        view_btn.clicked.connect(lambda _, n=note: self._open_note_details_dialog(n))
        r_layout.addWidget(view_btn)

        snip_btn = QPushButton("✂️")
        snip_btn.setFixedSize(28, 26)
        snip_btn.setToolTip("تحويل إلى اختصار")
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet("background-color: #202c33; color: #38bdf8; font-size: 12px; border-radius: 6px; border: 1px solid #3b4a54;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        r_layout.addWidget(snip_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(28, 26)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #202c33; color: #fca5a5; font-size: 11px; border-radius: 6px; border: 1px solid #3b4a54;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        r_layout.addWidget(del_btn)

        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(lambda pos, n=note, b=row: self._show_bubble_menu(b, pos, n))

        return row

    # ── Widget: Sticky Memo Note (Sticky Board Mode) ──
    def _create_sticky_note_widget(self, note: ChatNote, index: int, search_query: str = "") -> QWidget:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        align = Qt.AlignRight if has_arabic else Qt.AlignLeft

        pal = STICKY_PALETTES[(note.id or index) % len(STICKY_PALETTES)]

        sticky = QFrame()
        sticky.setStyleSheet(f"""
            QFrame {{
                background-color: {pal['bg']};
                border: 2px solid {pal['border']};
                border-radius: 14px;
            }}
        """)
        sticky.setCursor(QCursor(Qt.PointingHandCursor))
        sticky.setToolTip("انقر هنا لنسخ الملاحظة فوراً 📋 (أو انقر نقراً مزدوجاً للتفاصيل)")

        def _on_sticky_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note(n)
            QFrame.mousePressEvent(sticky, event)
        sticky.mousePressEvent = _on_sticky_clicked

        def _on_sticky_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_details_dialog(n)
            QFrame.mouseDoubleClickEvent(sticky, event)
        sticky.mouseDoubleClickEvent = _on_sticky_dbl_clicked

        s_layout = QVBoxLayout(sticky)
        s_layout.setContentsMargins(16, 12, 16, 14)
        s_layout.setSpacing(10)

        # Pin & Header
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        pin_lbl = QLabel(pal["pin"])
        pin_lbl.setStyleSheet("font-size: 18px; border: none; background: transparent;")
        header_row.addWidget(pin_lbl)

        sec_name = "ملاحظات"
        if note.section_id:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = s_obj.name

        sec_badge = QLabel(sec_name)
        sec_badge.setStyleSheet(f"background-color: {pal['badge_bg']}; color: {pal['badge_text']}; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 2px 8px; border: none;")
        header_row.addWidget(sec_badge)

        if note.is_starred:
            star_icon = QLabel("⭐")
            star_icon.setStyleSheet("font-size: 14px; border: none; background: transparent;")
            header_row.addWidget(star_icon)

        header_row.addStretch()

        time_str = self._format_note_time(note.created_at)
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(f"color: {pal['text']}; font-size: 12px; font-weight: bold; opacity: 0.85; border: none; background: transparent;")
        header_row.addWidget(time_lbl)
        s_layout.addLayout(header_row)

        # Content
        is_voice_note = "🎙️ [ملاحظة صوتية" in note.content or "Voice Note" in note.content
        if is_voice_note:
            voice_player = VoiceNotePlayerWidget(note.content, sticky)
            s_layout.addWidget(voice_player)
        else:
            is_long = len(note.content) > 160 or note.content.count("\n") >= 3
            is_expanded = note.id in self._expanded_note_ids

            display_text = note.content
            if is_long and not is_expanded and not search_query:
                display_text = note.content[:140] + "..."

            formatted_html = self._format_highlighted_text(display_text, search_query)

            content_lbl = QLabel()
            content_lbl.setTextFormat(Qt.RichText)
            content_lbl.setText(formatted_html)
            content_lbl.setWordWrap(True)
            content_lbl.setAlignment(align)
            content_lbl.setCursor(QCursor(Qt.PointingHandCursor))
            content_lbl.setStyleSheet(f"font-size: {max(self.chat_font_size - 3, 14)}px; font-family: '{font_family}'; color: {pal['text']}; font-weight: 500; line-height: 1.4; border: none; background: transparent;")
            
            def _on_slbl_clicked(event, n=note):
                if event.button() == Qt.LeftButton:
                    self._copy_note(n)
                QLabel.mousePressEvent(content_lbl, event)
            content_lbl.mousePressEvent = _on_slbl_clicked
            s_layout.addWidget(content_lbl)

            if is_long and not search_query:
                more_btn = QPushButton("عرض أقل ▴" if is_expanded else "عرض المزيد ▾")
                more_btn.setCursor(QCursor(Qt.PointingHandCursor))
                more_btn.setStyleSheet(f"color: {pal['badge_bg']}; font-size: 12px; font-weight: bold; border: none; background: transparent; text-align: right; padding: 2px;")
                more_btn.clicked.connect(lambda _, nid=note.id: self._toggle_expand_note(nid))
                s_layout.addWidget(more_btn)

        # Footer Action Strip
        footer = QHBoxLayout()
        footer.setSpacing(6)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(56, 26)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 11px; font-weight: bold; border-radius: 5px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note(n))
        footer.addWidget(copy_btn)

        star_btn = QPushButton("⭐" if note.is_starred else "☆")
        star_btn.setFixedSize(28, 26)
        star_btn.setCursor(QCursor(Qt.PointingHandCursor))
        star_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 12px; border-radius: 5px; border: none;")
        star_btn.clicked.connect(lambda _, n=note: self._toggle_star_note(n))
        footer.addWidget(star_btn)

        snip_btn = QPushButton("✂️")
        snip_btn.setFixedSize(28, 26)
        snip_btn.setToolTip("تحويل إلى اختصار Snippet")
        snip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        snip_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 12px; border-radius: 5px; border: none;")
        snip_btn.clicked.connect(lambda _, n=note: self._convert_to_snippet(n))
        footer.addWidget(snip_btn)

        view_btn = QPushButton("🔍")
        view_btn.setFixedSize(28, 26)
        view_btn.setToolTip("عرض التفاصيل كاملة")
        view_btn.setCursor(QCursor(Qt.PointingHandCursor))
        view_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 12px; border-radius: 5px; border: none;")
        view_btn.clicked.connect(lambda _, n=note: self._open_note_details_dialog(n))
        footer.addWidget(view_btn)

        footer.addStretch()

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(28, 26)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: #dc2626; font-size: 11px; border-radius: 5px; border: none;")
        del_btn.clicked.connect(lambda _, n=note: self._delete_note_instant(n))
        footer.addWidget(del_btn)

        s_layout.addLayout(footer)

        sticky.setContextMenuPolicy(Qt.CustomContextMenu)
        sticky.customContextMenuRequested.connect(lambda pos, n=note, b=sticky: self._show_bubble_menu(b, pos, n))

        return sticky

    def _open_note_details_dialog(self, note: ChatNote):
        sec_name = "الكل"
        if note.section_id:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = f"{s_obj.icon} {s_obj.name}"

        dlg = NoteDetailDialogQt(
            note=note,
            font_family=self.chat_font_family,
            font_size=self.chat_font_size,
            section_name=sec_name,
            parent=self,
            on_copy=self._copy_note,
            on_star=self._toggle_star_note,
            on_snip=self._convert_to_snippet,
            on_delete=self._delete_note_instant,
        )
        dlg.exec()

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
        copy_act = menu.addAction("📋 نسخ النص فوراً")
        view_act = menu.addAction("🔍 عرض التفاصيل كاملة")
        star_act = menu.addAction("⭐ تمييز بنجمة" if not note.is_starred else "⭐ إزالة النجمة")
        snip_act = menu.addAction("✂️ تحويل إلى اختصار (Snippet)")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ حذف الملاحظة")

        action = menu.exec(widget.mapToGlobal(pos))
        if action == copy_act:
            self._copy_note(note)
        elif action == view_act:
            self._open_note_details_dialog(note)
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
