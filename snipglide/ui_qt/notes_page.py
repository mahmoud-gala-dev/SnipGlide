import html
import re
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QScrollArea, QFrame, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QSplitter, QMenu, QApplication
)

from snipglide.database.note_repo import (
    get_all_notes, get_notes_for_list, get_note_by_id, add_note, update_note, delete_note,
    toggle_pin
)
from snipglide.database.note_category_repo import get_all_categories
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting
from snipglide.models.note import Note
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family
from snipglide.utils.helpers import download_and_load_arabic_font


STICKY_NOTE_PALETTES = [
    {
        "name": "yellow",
        "bg": "#fef08a",
        "border": "#eab308",
        "title": "#713f12",
        "text": "#854d0e",
        "pin": "📌",
        "badge_bg": "#ca8a04",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#713f12",
    },
    {
        "name": "mint",
        "bg": "#bbf7d0",
        "border": "#22c55e",
        "title": "#14532d",
        "text": "#166534",
        "pin": "📌",
        "badge_bg": "#16a34a",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#14532d",
    },
    {
        "name": "cyan",
        "bg": "#bae6fd",
        "border": "#0ea5e9",
        "title": "#0c4a6e",
        "text": "#075985",
        "pin": "📌",
        "badge_bg": "#0284c7",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#0c4a6e",
    },
    {
        "name": "lavender",
        "bg": "#e9d5ff",
        "border": "#a855f7",
        "title": "#581c87",
        "text": "#6b21a8",
        "pin": "📌",
        "badge_bg": "#9333ea",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#581c87",
    },
    {
        "name": "coral",
        "bg": "#fecdd3",
        "border": "#f43f5e",
        "title": "#881337",
        "text": "#9f1239",
        "pin": "📌",
        "badge_bg": "#e11d48",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#881337",
    },
    {
        "name": "amber",
        "bg": "#fed7aa",
        "border": "#f97316",
        "title": "#7c2d12",
        "text": "#9a3412",
        "pin": "📌",
        "badge_bg": "#ea580c",
        "badge_text": "#ffffff",
        "action_bg": "rgba(0, 0, 0, 0.08)",
        "action_text": "#7c2d12",
    },
]


class ZoomableNoteEdit(QPlainTextEdit):
    """QPlainTextEdit with support for Ctrl + Mouse Wheel zooming."""
    zoom_changed = Signal(int)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = 1 if event.angleDelta().y() > 0 else -1
            self.zoom_changed.emit(delta)
            event.accept()
        else:
            super().wheelEvent(event)


class NotesPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self.selected_note_id = None
        self._categories = []
        self._notes_cache = []

        # Load font & view settings
        self.note_font_size = self._get_saved_font_size()
        self.note_font_family = self._get_saved_font_family()
        self.view_mode = self._get_saved_view_mode()
        self.mode_buttons = {}

        self._setup_ui()
        self.update_category_dropdowns()
        self.refresh_notes_view()

    def _get_saved_font_size(self) -> int:
        try:
            val = int(get_note_setting("notes_page_font_size", "18"))
            return min(max(val, 12), 38)
        except Exception:
            return 18

    def _get_saved_font_family(self) -> str:
        saved = get_note_setting("notes_page_font_family", "Tajawal")
        return saved if saved else get_arabic_font_family()

    def _get_saved_view_mode(self) -> str:
        saved = get_note_setting("notes_page_view_mode", "grid")
        if saved in ("grid", "split", "list", "sticky"):
            return saved
        return "grid"

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 14, 20, 20)
        main_layout.setSpacing(12)

        # ═════════════════════════════════════════════════════════════════════
        # ── 1. Top Integrated Header ──
        # ═════════════════════════════════════════════════════════════════════
        header = QFrame()
        header.setObjectName("notesHeaderFrame")
        header.setStyleSheet("""
            QFrame#notesHeaderFrame {
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 16px;
                padding: 10px 14px;
            }
        """)
        h_main_layout = QVBoxLayout(header)
        h_main_layout.setContentsMargins(4, 4, 4, 4)
        h_main_layout.setSpacing(10)

        # ── Tier 1: Title, Search, Category Filter & New Note ──
        t1_layout = QHBoxLayout()
        t1_layout.setSpacing(12)

        icon_lbl = QLabel("📝")
        icon_lbl.setStyleSheet("font-size: 24px; background-color: #f59e0b; color: white; border-radius: 20px; padding: 4px 10px;")
        t1_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_lbl = QLabel("الملاحظات والمستندات (Notes & Documents)")
        self.title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; font-family: '{self.note_font_family}'; color: #f0f2f5;")
        self.count_badge = QLabel("انقر على أي ملاحظة لنسخ محتواها فوراً 📋 أو اضغط تعديل لتعديلها")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{self.note_font_family}'; color: #94a3b8;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.count_badge)
        t1_layout.addLayout(title_box)

        t1_layout.addStretch()

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
                font-family: '{self.note_font_family}';
            }}
            QLineEdit:focus {{
                border: 1.5px solid #f59e0b;
                background-color: #2a3942;
            }}
        """)
        self.search_edit.textChanged.connect(self.refresh_notes_view)
        t1_layout.addWidget(self.search_edit)

        # Category Filter Dropdown
        self.cat_filter = QComboBox()
        self.cat_filter.setFixedHeight(38)
        self.cat_filter.setMinimumWidth(160)
        self.cat_filter.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: #f0f2f5; border-radius: 10px; padding: 4px 10px; font-weight: bold;")
        self.cat_filter.currentTextChanged.connect(self.refresh_notes_view)
        t1_layout.addWidget(self.cat_filter)

        # New Note Button
        new_btn = QPushButton("➕ إضافة ملاحظة جديدة")
        new_btn.setFixedHeight(38)
        new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #f59e0b;
                color: white;
                font-weight: bold;
                font-size: 14px;
                font-family: '{self.note_font_family}';
                border-radius: 10px;
                border: none;
                padding: 4px 16px;
            }}
            QPushButton:hover {{
                background-color: #d97706;
            }}
        """)
        new_btn.clicked.connect(self.new_note)
        t1_layout.addWidget(new_btn)

        h_main_layout.addLayout(t1_layout)

        # ── Tier 2: View Modes Toolbar & Font Controls ──
        t2_layout = QHBoxLayout()
        t2_layout.setSpacing(12)

        # View Modes Switcher
        view_box = QFrame()
        view_box.setStyleSheet("background-color: #182229; border: 1.5px solid #2a3942; border-radius: 10px; padding: 2px;")
        vb_layout = QHBoxLayout(view_box)
        vb_layout.setContentsMargins(4, 2, 4, 2)
        vb_layout.setSpacing(4)

        modes = [
            ("grid", "🗂️ بطاقات وشبكة", "عرض الملاحظات على شكل بطاقات شبكية (Cards Grid)"),
            ("split", "📋 محرر وتقسيم", "عرض القائمة الجانبية والمحرر الكامل (Split Editor)"),
            ("list", "📑 قائمة مدمجة", "عرض الملاحظات على شكل قائمة أفقية مدمجة وسريعة (Compact List)"),
            ("sticky", "📌 ملصقات ملونة", "عرض الملاحظات على شكل لوحة ملصقات ملونة (Sticky Board)"),
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
        t2_layout.addWidget(view_box)

        t2_layout.addStretch()

        # Font Zoom Controls: [A-] [18px] [A+]
        font_box = QFrame()
        font_box.setStyleSheet("background-color: #182229; border: 1.5px solid #2a3942; border-radius: 10px; padding: 2px;")
        fb_layout = QHBoxLayout(font_box)
        fb_layout.setContentsMargins(6, 2, 6, 2)
        fb_layout.setSpacing(6)

        down_btn = QPushButton("A-")
        down_btn.setFixedSize(30, 30)
        down_btn.setCursor(QCursor(Qt.PointingHandCursor))
        down_btn.setToolTip("تصغير حجم الخط (Ctrl+-)")
        down_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; border: none; color: #f0f2f5;")
        down_btn.clicked.connect(lambda: self._change_font_size(-1))
        fb_layout.addWidget(down_btn)

        self.font_size_lbl = QLabel(f"{self.note_font_size}px")
        self.font_size_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
        fb_layout.addWidget(self.font_size_lbl)

        up_btn = QPushButton("A+")
        up_btn.setFixedSize(30, 30)
        up_btn.setCursor(QCursor(Qt.PointingHandCursor))
        up_btn.setToolTip("تكبير حجم الخط (Ctrl++)")
        up_btn.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; border: none; color: #f0f2f5;")
        up_btn.clicked.connect(lambda: self._change_font_size(1))
        fb_layout.addWidget(up_btn)
        t2_layout.addWidget(font_box)

        # Font Family Dropdown
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"])
        self.font_combo.setCurrentText(self.note_font_family if self.note_font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_combo.setFixedHeight(36)
        self.font_combo.setMinimumWidth(110)
        self.font_combo.currentTextChanged.connect(self._on_font_family_change)
        t2_layout.addWidget(self.font_combo)

        h_main_layout.addLayout(t2_layout)
        main_layout.addWidget(header)

        # ═════════════════════════════════════════════════════════════════════
        # ── 2. Dynamic Content Area ──
        # ═════════════════════════════════════════════════════════════════════
        self.content_stack = QWidget()
        self.content_stack_layout = QVBoxLayout(self.content_stack)
        self.content_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack_layout.setSpacing(0)

        # ── View Mode 1: Split Pane (List + Editor) ──
        self.split_view_widget = QWidget()
        sv_layout = QHBoxLayout(self.split_view_widget)
        sv_layout.setContentsMargins(0, 0, 0, 0)
        sv_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)

        # Left List Pane
        left_pane = QFrame()
        left_pane.setStyleSheet("background-color: #111b21; border-radius: 14px; padding: 10px; border: 1.5px solid #2a3942;")
        l_layout = QVBoxLayout(left_pane)
        l_layout.setContentsMargins(10, 10, 10, 10)
        l_layout.setSpacing(8)

        left_title = QLabel("قائمة الملاحظات")
        left_title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: #f0f2f5; font-family: '{self.note_font_family}';")
        l_layout.addWidget(left_title)

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #0b141a;
                border: 2px solid #202c33;
                border-radius: 10px;
                padding: 6px;
                font-family: '{self.note_font_family}';
                font-size: 14px;
            }}
            QListWidget::item {{
                padding: 12px 14px;
                border-radius: 8px;
                color: #f0f2f5;
                margin-bottom: 4px;
                border: 1px solid #182229;
            }}
            QListWidget::item:hover {{
                background-color: #1f2c34;
            }}
            QListWidget::item:selected {{
                background-color: #1e3a5f;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
            }}
        """)
        self.notes_list.itemClicked.connect(self._on_item_clicked)
        self.notes_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.notes_list.customContextMenuRequested.connect(self._show_notes_menu)
        l_layout.addWidget(self.notes_list, stretch=1)
        self.splitter.addWidget(left_pane)

        # Right Editor Pane
        right_pane = QFrame()
        right_pane.setStyleSheet("background-color: #111b21; border-radius: 14px; padding: 14px; border: 1.5px solid #2a3942;")
        r_layout = QVBoxLayout(right_pane)
        r_layout.setContentsMargins(18, 14, 18, 14)
        r_layout.setSpacing(12)

        # Title + Category + Pin
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("عنوان الملاحظة...")
        self.title_edit.setFixedHeight(44)
        self.title_edit.setStyleSheet(f"font-size: 16px; font-weight: bold; font-family: '{self.note_font_family}'; background-color: #0b141a; border: 1.5px solid #3b4a54; border-radius: 10px; padding: 6px 12px; color: #f0f2f5;")
        row1.addWidget(self.title_edit, stretch=1)

        self.cat_combo = QComboBox()
        self.cat_combo.setFixedHeight(44)
        self.cat_combo.setMinimumWidth(140)
        self.cat_combo.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; border-radius: 10px; color: #f0f2f5; padding: 4px 10px; font-weight: bold;")
        row1.addWidget(self.cat_combo)

        self.pin_btn = QPushButton("📌 تثبيت")
        self.pin_btn.setFixedHeight(44)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pin_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: white; border-radius: 10px; padding: 4px 16px; font-weight: bold;")
        self.pin_btn.clicked.connect(self._toggle_pin)
        row1.addWidget(self.pin_btn)
        r_layout.addLayout(row1)

        # Content Text Editor (Zoomable)
        self.content_edit = ZoomableNoteEdit()
        self.content_edit.setPlaceholderText("اكتب محتوى الملاحظة هنا... (يمكنك تكبير/تصغير الخط بـ Ctrl + عجلة الفأرة أو اختصارات Ctrl++/Ctrl+-)")
        self.content_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: {self.note_font_size}px;
                font-family: '{self.note_font_family}';
                border-radius: 10px;
                padding: 14px;
                border: 2px solid #3b4a54;
                line-height: 1.5;
            }}
            QPlainTextEdit:focus {{
                border: 2px solid #f59e0b;
            }}
        """)
        self.content_edit.zoom_changed.connect(self._change_font_size)
        self.content_edit.installEventFilter(self)
        r_layout.addWidget(self.content_edit, stretch=1)

        # Bottom Actions Bar
        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)

        copy_content_btn = QPushButton("📋 نسخ المحتوى للحافظة")
        copy_content_btn.setFixedHeight(44)
        copy_content_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_content_btn.setStyleSheet("background-color: #202c33; border: 1.5px solid #3b4a54; color: #f0f2f5; font-weight: bold; border-radius: 10px; padding: 4px 18px; font-size: 14px;")
        copy_content_btn.clicked.connect(self._copy_current_editor_content)
        bot_row.addWidget(copy_content_btn)

        bot_row.addStretch()

        self.del_btn = QPushButton("🗑️ حذف")
        self.del_btn.setFixedHeight(44)
        self.del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.del_btn.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 10px; padding: 4px 18px; font-size: 14px;")
        self.del_btn.clicked.connect(self._delete_current)
        bot_row.addWidget(self.del_btn)

        save_btn = QPushButton("💾 حفظ الملاحظة")
        save_btn.setFixedHeight(44)
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; border-radius: 10px; padding: 4px 26px; font-size: 15px;")
        save_btn.clicked.connect(self._save_current)
        bot_row.addWidget(save_btn)

        r_layout.addLayout(bot_row)
        self.splitter.addWidget(right_pane)
        self.splitter.setSizes([340, 760])
        sv_layout.addWidget(self.splitter)
        self.content_stack_layout.addWidget(self.split_view_widget)

        # ── View Mode 2: Grid / List / Sticky Scroll View ──
        self.scroll_view_area = QScrollArea()
        self.scroll_view_area.setWidgetResizable(True)
        self.scroll_view_area.setStyleSheet("""
            QScrollArea {
                background-color: #0b141a;
                border-radius: 16px;
                border: 2px solid #202c33;
            }
        """)

        self.scroll_feed_container = QWidget()
        self.scroll_feed_container.setStyleSheet("background-color: transparent;")
        self.scroll_feed_layout = QVBoxLayout(self.scroll_feed_container)
        self.scroll_feed_layout.setContentsMargins(18, 18, 18, 18)
        self.scroll_feed_layout.setSpacing(12)
        self.scroll_feed_layout.setAlignment(Qt.AlignTop)
        self.scroll_view_area.setWidget(self.scroll_feed_container)
        self.content_stack_layout.addWidget(self.scroll_view_area)

        main_layout.addWidget(self.content_stack, stretch=1)

    def eventFilter(self, obj, event):
        if obj is self.content_edit and event.type() == event.Type.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self._change_font_size(1)
                return True
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Minus:
                self._change_font_size(-1)
                return True
        return super().eventFilter(obj, event)

    def _set_view_mode(self, mode: str):
        if self.view_mode == mode:
            return
        self.view_mode = mode
        set_note_setting("notes_page_view_mode", mode)
        self._update_mode_buttons_style()
        self.refresh_notes_view()
        mode_names = {
            "grid": "بطاقات وشبكة",
            "split": "محرر وتقسيم",
            "list": "قائمة مدمجة",
            "sticky": "ملصقات ملونة",
        }
        self.toast_signal.emit(f"تم التحويل إلى نمط: {mode_names.get(mode, mode)} ✨", False)

    def _update_mode_buttons_style(self):
        for mode_key, btn in self.mode_buttons.items():
            if mode_key == self.view_mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #f59e0b;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 13px;
                        font-family: '{self.note_font_family}';
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
                        font-family: '{self.note_font_family}';
                        border-radius: 8px;
                        border: none;
                        padding: 3px 12px;
                    }}
                    QPushButton:hover {{
                        background-color: #2a3942;
                        color: #f0f2f5;
                    }}
                """)

    def _change_font_size(self, delta: int):
        new_size = min(max(self.note_font_size + delta, 12), 38)
        if new_size != self.note_font_size:
            self.note_font_size = new_size
            set_note_setting("notes_page_font_size", str(new_size))
            self.font_size_lbl.setText(f"{new_size}px")
            self.content_edit.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: #0b141a;
                    color: #f0f2f5;
                    font-size: {new_size}px;
                    font-family: '{self.note_font_family}';
                    border-radius: 10px;
                    padding: 14px;
                    border: 2px solid #3b4a54;
                    line-height: 1.5;
                }}
                QPlainTextEdit:focus {{
                    border: 2px solid #f59e0b;
                }}
            """)
            if self.view_mode != "split":
                self.refresh_notes_view()

    def _on_font_family_change(self, family: str):
        download_and_load_arabic_font(family)
        self.note_font_family = family
        set_arabic_font_family(family)
        set_note_setting("notes_page_font_family", family)
        self.title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; font-family: '{family}'; color: #f0f2f5;")
        self.count_badge.setStyleSheet(f"font-size: 13px; font-family: '{family}'; color: #94a3b8;")
        self._update_mode_buttons_style()
        self.content_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: {self.note_font_size}px;
                font-family: '{family}';
                border-radius: 10px;
                padding: 14px;
                border: 2px solid #3b4a54;
                line-height: 1.5;
            }}
            QPlainTextEdit:focus {{
                border: 2px solid #f59e0b;
            }}
        """)
        self.refresh_notes_view()

    def update_category_dropdowns(self):
        categories = get_all_categories()
        self._categories = categories
        self.cat_filter.clear()
        self.cat_filter.addItem("📂 جميع الأقسام (All Categories)", None)
        self.cat_combo.clear()

        for c in categories:
            self.cat_filter.addItem(f"📁 {c.name}", c.id)
            self.cat_combo.addItem(f"📁 {c.name}", c.id)

    def refresh_notes_view(self):
        query = self.search_edit.text().strip()
        cid = self.cat_filter.currentData()
        notes = get_notes_for_list(query=query, category_id=cid)
        self._notes_cache = notes

        total_count = len(get_all_notes())
        current_count = len(notes)
        self.count_badge.setText(f"الإجمالي: {total_count} ملاحظة • المعروض: {current_count} • انقر على أي ملاحظة لنسخ محتواها فوراً 📋")

        if self.view_mode == "split":
            self.split_view_widget.setVisible(True)
            self.scroll_view_area.setVisible(False)
            self._render_split_list(notes)
        else:
            self.split_view_widget.setVisible(False)
            self.scroll_view_area.setVisible(True)

            while self.scroll_feed_layout.count():
                item = self.scroll_feed_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not notes:
                empty_lbl = QLabel("لا توجد ملاحظات مطابقة.\nاضغط '➕ إضافة ملاحظة جديدة' بالأعلى لإضافة فكرتك أو ملاحظتك!")
                empty_lbl.setAlignment(Qt.AlignCenter)
                empty_lbl.setStyleSheet(f"color: #94a3b8; font-size: 16px; font-family: '{self.note_font_family}'; padding: 50px;")
                self.scroll_feed_layout.addWidget(empty_lbl)
                return

            if self.view_mode == "grid":
                self._render_cards_grid(notes, query)
            elif self.view_mode == "list":
                self._render_compact_list(notes, query)
            elif self.view_mode == "sticky":
                self._render_sticky_board(notes, query)

    # ── Render: Split List Mode ──
    def _render_split_list(self, notes):
        self.notes_list.clear()
        for n in notes:
            prefix = "📌 " if n.pinned else "📝 "
            item = QListWidgetItem(f"{prefix}{n.title}")
            item.setData(Qt.UserRole, n.id)
            self.notes_list.addItem(item)

        if self.selected_note_id:
            for i in range(self.notes_list.count()):
                it = self.notes_list.item(i)
                if it.data(Qt.UserRole) == self.selected_note_id:
                    self.notes_list.setCurrentItem(it)
                    break

    # ── Render: Cards Grid Mode ──
    def _render_cards_grid(self, notes, query: str):
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        cols = 3
        for idx, note in enumerate(notes):
            card = self._create_note_card_widget(note, query)
            grid.addWidget(card, idx // cols, idx % cols)

        self.scroll_feed_layout.addWidget(grid_widget)

    # ── Render: Compact List Mode ──
    def _render_compact_list(self, notes, query: str):
        for note in notes:
            row = self._create_compact_note_row(note, query)
            self.scroll_feed_layout.addWidget(row)

    # ── Render: Sticky Board Mode ──
    def _render_sticky_board(self, notes, query: str):
        sticky_widget = QWidget()
        sticky_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(sticky_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        cols = 3
        for idx, note in enumerate(notes):
            card = self._create_sticky_note_card(note, idx, query)
            grid.addWidget(card, idx // cols, idx % cols)

        self.scroll_feed_layout.addWidget(sticky_widget)

    # ── Widget: Modern Note Card (Grid View) ──
    def _create_note_card_widget(self, note: Note, query: str) -> QWidget:
        card = QFrame()
        card_border = "border: 2px solid #f59e0b;" if note.pinned else "border: 1.5px solid #2a3942;"
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #182229;
                {card_border}
                border-radius: 14px;
            }}
            QFrame:hover {{
                border-color: #f59e0b;
                background-color: #1e2c34;
            }}
        """)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setToolTip("انقر هنا لنسخ محتوى الملاحظة فوراً إلى الحافظة 📋 (أو اضغط تعديل لتعديلها)")

        # 1-Click to Copy & Double Click to edit
        def _on_card_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note_content(n)
            QFrame.mousePressEvent(card, event)
        card.mousePressEvent = _on_card_clicked

        def _on_card_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_in_editor(n.id)
            QFrame.mouseDoubleClickEvent(card, event)
        card.mouseDoubleClickEvent = _on_card_dbl_clicked

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(8)

        # Header: Pin badge + Category Badge + Date
        h_row = QHBoxLayout()
        h_row.setSpacing(6)

        if note.pinned:
            pin_lbl = QLabel("📌 مثبتة")
            pin_lbl.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; font-size: 11px; border-radius: 6px; padding: 2px 7px; border: none;")
            h_row.addWidget(pin_lbl)

        sec_name = self._get_category_name(note.category_id)
        sec_badge = QLabel(f"📁 {sec_name}")
        sec_badge.setStyleSheet("background-color: #202c33; color: #94a3b8; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 2px 8px; border: 1px solid #3b4a54;")
        h_row.addWidget(sec_badge)

        h_row.addStretch()

        time_str = self._format_date_short(note.modified_date)
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        h_row.addWidget(time_lbl)
        c_layout.addLayout(h_row)

        # Title
        title_html = self._format_highlighted_text(note.title, query)
        title_lbl = QLabel()
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setText(title_html)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: #f0f2f5; font-family: '{self.note_font_family}'; border: none; background: transparent;")
        title_lbl.setWordWrap(True)
        c_layout.addWidget(title_lbl)

        # Content Preview
        clean_content = note.content.strip()
        if len(clean_content) > 160:
            clean_content = clean_content[:155] + "..."
        content_html = self._format_highlighted_text(clean_content, query)
        content_lbl = QLabel()
        content_lbl.setTextFormat(Qt.RichText)
        content_lbl.setText(content_html)
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet(f"font-size: {max(self.note_font_size - 2, 13)}px; color: #cbd5e1; font-family: '{self.note_font_family}'; line-height: 1.4; border: none; background: transparent;")
        c_layout.addWidget(content_lbl, stretch=1)

        # Action Buttons Row
        actions = QHBoxLayout()
        actions.setSpacing(6)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(60, 28)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setToolTip("نسخ محتوى الملاحظة")
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note_content(n))
        actions.addWidget(copy_btn)

        edit_btn = QPushButton("✏️ تعديل")
        edit_btn.setFixedSize(64, 28)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setToolTip("تعديل الملاحظة في المحرر الكامل")
        edit_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #38bdf8; font-size: 12px; font-weight: bold; border-radius: 6px;")
        edit_btn.clicked.connect(lambda _, nid=note.id: self._open_note_in_editor(nid))
        actions.addWidget(edit_btn)

        pin_toggle_btn = QPushButton("📌" if note.pinned else "📍")
        pin_toggle_btn.setFixedSize(30, 28)
        pin_toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        pin_toggle_btn.setToolTip("تثبيت / إلغاء التثبيت")
        pin_toggle_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #f59e0b; font-size: 13px; border-radius: 6px;")
        pin_toggle_btn.clicked.connect(lambda _, nid=note.id: self._toggle_pin_for_id(nid))
        actions.addWidget(pin_toggle_btn)

        actions.addStretch()

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(30, 28)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setToolTip("حذف الملاحظة")
        del_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #fca5a5; font-size: 12px; border-radius: 6px;")
        del_btn.clicked.connect(lambda _, nid=note.id: self._delete_note_by_id(nid))
        actions.addWidget(del_btn)

        c_layout.addLayout(actions)
        return card

    # ── Widget: Compact Row ──
    def _create_compact_note_row(self, note: Note, query: str) -> QWidget:
        row = QFrame()
        row_border = "border: 1.5px solid #f59e0b;" if note.pinned else "border: 1px solid #2a3942;"
        row.setStyleSheet(f"""
            QFrame {{
                background-color: #182229;
                {row_border}
                border-radius: 10px;
            }}
            QFrame:hover {{
                background-color: #1e2c34;
                border-color: #f59e0b;
            }}
        """)
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row.setToolTip("انقر هنا لنسخ محتوى الملاحظة فوراً 📋 (أو انقر نقراً مزدوجاً للتعديل)")

        def _on_row_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note_content(n)
            QFrame.mousePressEvent(row, event)
        row.mousePressEvent = _on_row_clicked

        def _on_row_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_in_editor(n.id)
            QFrame.mouseDoubleClickEvent(row, event)
        row.mouseDoubleClickEvent = _on_row_dbl_clicked

        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(14, 10, 14, 10)
        r_layout.setSpacing(10)

        # Pin
        pin_btn = QPushButton("📌" if note.pinned else "📍")
        pin_btn.setFixedSize(28, 28)
        pin_btn.setCursor(QCursor(Qt.PointingHandCursor))
        pin_btn.setStyleSheet("background: transparent; color: #f59e0b; font-size: 14px; border: none;")
        pin_btn.clicked.connect(lambda _, nid=note.id: self._toggle_pin_for_id(nid))
        r_layout.addWidget(pin_btn)

        # Category pill
        sec_name = self._get_category_name(note.category_id)
        sec_lbl = QLabel(f"📁 {sec_name}")
        sec_lbl.setStyleSheet("background-color: #202c33; color: #94a3b8; font-size: 11px; font-weight: bold; border-radius: 5px; padding: 3px 8px; border: 1px solid #3b4a54;")
        r_layout.addWidget(sec_lbl)

        # Title
        title_html = self._format_highlighted_text(note.title, query)
        title_lbl = QLabel()
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setText(title_html)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: #f0f2f5; font-family: '{self.note_font_family}'; border: none; background: transparent;")
        r_layout.addWidget(title_lbl)

        # Content snippet
        clean_text = note.content.replace("\n", " ").strip()
        if len(clean_text) > 90:
            clean_text = clean_text[:85] + "..."
        content_html = self._format_highlighted_text(clean_text, query)
        content_lbl = QLabel()
        content_lbl.setTextFormat(Qt.RichText)
        content_lbl.setText(f"— {content_html}")
        content_lbl.setStyleSheet(f"font-size: 13px; color: #94a3b8; font-family: '{self.note_font_family}'; border: none; background: transparent;")
        r_layout.addWidget(content_lbl, stretch=1)

        # Date
        time_str = self._format_date_short(note.modified_date)
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #64748b; font-size: 12px; border: none; background: transparent;")
        r_layout.addWidget(time_lbl)

        # Actions
        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(58, 26)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-size: 12px; font-weight: bold; border-radius: 6px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note_content(n))
        r_layout.addWidget(copy_btn)

        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(28, 26)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setToolTip("تعديل في المحرر")
        edit_btn.setStyleSheet("background-color: #202c33; border: 1px solid #3b4a54; color: #38bdf8; font-size: 12px; border-radius: 6px;")
        edit_btn.clicked.connect(lambda _, nid=note.id: self._open_note_in_editor(nid))
        r_layout.addWidget(edit_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(28, 26)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet("background-color: #202c33; color: #fca5a5; font-size: 11px; border-radius: 6px; border: 1px solid #3b4a54;")
        del_btn.clicked.connect(lambda _, nid=note.id: self._delete_note_by_id(nid))
        r_layout.addWidget(del_btn)

        return row

    # ── Widget: Sticky Note (Sticky Board View) ──
    def _create_sticky_note_card(self, note: Note, index: int, query: str) -> QWidget:
        pal = STICKY_NOTE_PALETTES[(note.id or index) % len(STICKY_NOTE_PALETTES)]

        sticky = QFrame()
        sticky.setStyleSheet(f"""
            QFrame {{
                background-color: {pal['bg']};
                border: 2px solid {pal['border']};
                border-radius: 14px;
            }}
        """)
        sticky.setCursor(QCursor(Qt.PointingHandCursor))
        sticky.setToolTip("انقر هنا لنسخ محتوى الملاحظة فوراً 📋 (أو انقر نقراً مزدوجاً للتعديل)")

        def _on_sticky_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._copy_note_content(n)
            QFrame.mousePressEvent(sticky, event)
        sticky.mousePressEvent = _on_sticky_clicked

        def _on_sticky_dbl_clicked(event, n=note):
            if event.button() == Qt.LeftButton:
                self._open_note_in_editor(n.id)
            QFrame.mouseDoubleClickEvent(sticky, event)
        sticky.mouseDoubleClickEvent = _on_sticky_dbl_clicked

        s_layout = QVBoxLayout(sticky)
        s_layout.setContentsMargins(16, 12, 16, 14)
        s_layout.setSpacing(8)

        # Header Pin
        h_row = QHBoxLayout()
        h_row.setSpacing(6)

        pin_lbl = QLabel(pal["pin"])
        pin_lbl.setStyleSheet("font-size: 18px; border: none; background: transparent;")
        h_row.addWidget(pin_lbl)

        sec_name = self._get_category_name(note.category_id)
        sec_badge = QLabel(sec_name)
        sec_badge.setStyleSheet(f"background-color: {pal['badge_bg']}; color: {pal['badge_text']}; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 2px 7px; border: none;")
        h_row.addWidget(sec_badge)

        if note.pinned:
            p_tag = QLabel("📌 مثبتة")
            p_tag.setStyleSheet(f"color: {pal['title']}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            h_row.addWidget(p_tag)

        h_row.addStretch()

        time_str = self._format_date_short(note.modified_date)
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(f"color: {pal['text']}; font-size: 11px; font-weight: bold; opacity: 0.8; border: none; background: transparent;")
        h_row.addWidget(time_lbl)
        s_layout.addLayout(h_row)

        # Title
        title_html = self._format_highlighted_text(note.title, query)
        title_lbl = QLabel()
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setText(title_html)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {pal['title']}; font-family: '{self.note_font_family}'; border: none; background: transparent;")
        title_lbl.setWordWrap(True)
        s_layout.addWidget(title_lbl)

        # Content
        clean_text = note.content.strip()
        if len(clean_text) > 150:
            clean_text = clean_text[:145] + "..."
        content_html = self._format_highlighted_text(clean_text, query)
        content_lbl = QLabel()
        content_lbl.setTextFormat(Qt.RichText)
        content_lbl.setText(content_html)
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet(f"font-size: {max(self.note_font_size - 3, 13)}px; color: {pal['text']}; font-family: '{self.note_font_family}'; font-weight: 500; line-height: 1.4; border: none; background: transparent;")
        s_layout.addWidget(content_lbl, stretch=1)

        # Actions
        footer = QHBoxLayout()
        footer.setSpacing(6)

        copy_btn = QPushButton("📋 نسخ")
        copy_btn.setFixedSize(56, 26)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 11px; font-weight: bold; border-radius: 5px; border: none;")
        copy_btn.clicked.connect(lambda _, n=note: self._copy_note_content(n))
        footer.addWidget(copy_btn)

        edit_btn = QPushButton("✏️ تعديل")
        edit_btn.setFixedSize(58, 26)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: {pal['action_text']}; font-size: 11px; font-weight: bold; border-radius: 5px; border: none;")
        edit_btn.clicked.connect(lambda _, nid=note.id: self._open_note_in_editor(nid))
        footer.addWidget(edit_btn)

        footer.addStretch()

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(26, 26)
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet(f"background-color: {pal['action_bg']}; color: #dc2626; font-size: 11px; border-radius: 5px; border: none;")
        del_btn.clicked.connect(lambda _, nid=note.id: self._delete_note_by_id(nid))
        footer.addWidget(del_btn)

        s_layout.addLayout(footer)
        return sticky

    def _get_category_name(self, cat_id: int | None) -> str:
        if not cat_id:
            return "عام"
        cat = next((c for c in self._categories if c.id == cat_id), None)
        return cat.name if cat else "عام"

    def _format_date_short(self, date_str: str) -> str:
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%Y-%m-%d %I:%M %p").lstrip("0")
        except Exception:
            return date_str[:16] if date_str else ""

    def _format_highlighted_text(self, text: str, query: str) -> str:
        escaped = html.escape(text).replace("\n", "<br>")
        if not query:
            return escaped
        pattern = re.compile(re.escape(html.escape(query)), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f'<span style="background-color: #facc15; color: #0f172a; font-weight: 800; border-radius: 4px; padding: 1px 4px;">{m.group(0)}</span>',
            escaped
        )
        return highlighted

    def _copy_note_content(self, note: Note):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(note.content)
            self.toast_signal.emit(f"تم نسخ ملاحظة '{note.title}' إلى الحافظة! 📋", False)

    def _copy_current_editor_content(self):
        text = self.content_edit.toPlainText()
        if not text:
            self.toast_signal.emit("لا يوجد محتوى لنسخه.", True)
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.toast_signal.emit("تم نسخ محتوى الملاحظة إلى الحافظة! 📋", False)

    def _open_note_in_editor(self, note_id: int):
        self._set_view_mode("split")
        note = get_note_by_id(note_id)
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
            self.title_edit.setFocus()
            self._copy_note_content(note)

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
            self._copy_note_content(note)

    def new_note(self):
        self._set_view_mode("split")
        self.selected_note_id = None
        self.title_edit.clear()
        self.content_edit.clear()
        self.pin_btn.setChecked(False)
        self.pin_btn.setText("📌 تثبيت")
        self.title_edit.setFocus()
        self.toast_signal.emit("جاهز لكتابة ملاحظة جديدة ✍️", False)

    def _toggle_pin(self):
        if self.selected_note_id:
            toggle_pin(self.selected_note_id)
            note = get_note_by_id(self.selected_note_id)
            new_val = bool(note.pinned) if note else False
            self.pin_btn.setChecked(new_val)
            self.pin_btn.setText("📌 مثبتة" if new_val else "📌 تثبيت")
            self.refresh_notes_view()

    def _toggle_pin_for_id(self, note_id: int):
        toggle_pin(note_id)
        self.refresh_notes_view()
        self.toast_signal.emit("تم تحديث حالة التثبيت 📌", False)

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
            self.refresh_notes_view()
            self.toast_signal.emit("تم حفظ الملاحظة بنجاح! 💾", False)
        except Exception as e:
            self.toast_signal.emit(f"فشل الحفظ: {e}", True)

    def _show_notes_menu(self, pos):
        item = self.notes_list.itemAt(pos)
        if not item:
            return
        nid = item.data(Qt.UserRole)
        note = get_note_by_id(nid)
        if not note:
            return

        menu = QMenu(self)
        copy_act = menu.addAction("📋 نسخ محتوى الملاحظة")
        pin_act = menu.addAction("📌 إلغاء التثبيت" if note.pinned else "📌 تثبيت في الأعلى")
        menu.addSeparator()
        del_act = menu.addAction("🗑️ حذف الملاحظة")

        action = menu.exec(self.notes_list.mapToGlobal(pos))
        if action == copy_act:
            self._copy_note_content(note)
        elif action == pin_act:
            self._toggle_pin_for_id(note.id)
        elif action == del_act:
            self._delete_note_by_id(note.id)

    def _delete_current(self):
        if not self.selected_note_id:
            return
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذه الملاحظة؟")
        if reply == QMessageBox.Yes:
            delete_note(self.selected_note_id)
            self.new_note()
            self.refresh_notes_view()
            self.toast_signal.emit("تم حذف الملاحظة 🗑️", False)

    def _delete_note_by_id(self, note_id: int):
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذه الملاحظة؟")
        if reply == QMessageBox.Yes:
            delete_note(note_id)
            if self.selected_note_id == note_id:
                self.new_note()
            self.refresh_notes_view()
            self.toast_signal.emit("تم حذف الملاحظة 🗑️", False)
