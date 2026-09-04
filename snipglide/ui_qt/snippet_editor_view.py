from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont, QTextOption
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QFrame, QComboBox, QCheckBox, QMessageBox,
    QListWidget, QListWidgetItem, QSplitter, QMenu, QApplication
)

from snipglide.database.snippet_repo import (
    get_all_snippets, get_snippets_for_list, get_snippet_by_id, add_snippet, update_snippet,
    delete_snippet
)
from snipglide.database.group_repo import get_all_groups, add_group
from snipglide.models.snippet import Snippet
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family
from snipglide.utils.helpers import download_and_load_arabic_font

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
        self.font_family = get_arabic_font_family() or "Tajawal"
        self.editor_font_size = 14
        self.is_rtl = True
        
        # Ensure Google font is loaded
        download_and_load_arabic_font(self.font_family)
        self.setFont(QFont(self.font_family, 13))
        
        self._setup_ui()
        self.update_group_dropdowns()
        self.refresh_list()

    def _setup_ui(self):
        # Main container with Vertical Layout for top header + bottom content
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 18, 22, 18)
        main_layout.setSpacing(14)

        # ── Top Header Bar ──
        header_card = QFrame()
        header_card.setObjectName("snippetHeaderCard")
        header_card.setStyleSheet(f"""
            QFrame#snippetHeaderCard {{
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 16px;
                padding: 8px 14px;
                font-family: '{self.font_family}', 'Tajawal', 'Cairo', sans-serif;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(8, 6, 8, 6)
        h_layout.setSpacing(12)

        # Unified Drawer Toggle Button
        btn_drawer = QPushButton("☰ القائمة")
        btn_drawer.setToolTip("إظهار / إخفاء القائمة الجانبية (Drawer) - Ctrl+B")
        btn_drawer.setCursor(QCursor(Qt.PointingHandCursor))
        btn_drawer.setFont(QFont(self.font_family, 12, QFont.Bold))
        btn_drawer.setStyleSheet(f"""
            QPushButton {{
                background-color: #182229;
                color: #60a5fa;
                border: 1.5px solid #2a3942;
                border-radius: 9px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QPushButton:hover {{
                background-color: #172554;
                color: #93c5fd;
                border-color: #3b82f6;
            }}
        """)
        btn_drawer.clicked.connect(lambda: self.window().toggle_sidebar() if hasattr(self.window(), "toggle_sidebar") else None)
        h_layout.addWidget(btn_drawer)

        # Title Icon Badge
        icon_badge = QLabel("✂️")
        icon_badge.setStyleSheet("font-size: 22px; background-color: #16a34a; color: white; border-radius: 18px; padding: 4px 10px;")
        h_layout.addWidget(icon_badge)

        # Title and Subtitle Box
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("إدارة الاختصارات والقوالب السريعة (Snippets Manager)")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; font-family: '{self.font_family}', 'Tajawal', sans-serif; color: #f0f2f5;")
        subtitle_lbl = QLabel("أنشئ وخصص اختصاراتك النصية، القوالب الجاهزة، والمتغيرات الديناميكية بسهولة مع الدعم العربي الكامل.")
        subtitle_lbl.setStyleSheet(f"font-size: 13px; font-family: '{self.font_family}', 'Tajawal', sans-serif; color: #94a3b8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Google Font Family Dropdown
        font_box = QHBoxLayout()
        font_box.setSpacing(6)
        lbl_f = QLabel("🔤 الخط:")
        lbl_f.setStyleSheet(f"color: #94a3b8; font-size: 13px; font-weight: bold; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        font_box.addWidget(lbl_f)

        self.font_combo = QComboBox()
        self.font_combo.addItems(["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"])
        self.font_combo.setCurrentText(self.font_family if self.font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_combo.setFixedHeight(34)
        self.font_combo.setMinimumWidth(110)
        self.font_combo.setFont(QFont(self.font_family, 12))
        self.font_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #182229;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px 10px;
                color: #60a5fa;
                font-weight: bold;
                font-size: 12px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QComboBox:hover {{
                border-color: #3b82f6;
            }}
        """)
        self.font_combo.currentTextChanged.connect(self._on_font_family_changed)
        font_box.addWidget(self.font_combo)
        h_layout.addLayout(font_box)

        # Font Zoom Controls (A- / A+)
        zoom_box = QFrame()
        zoom_box.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 8px; padding: 2px 4px;")
        zb_layout = QHBoxLayout(zoom_box)
        zb_layout.setContentsMargins(4, 2, 4, 2)
        zb_layout.setSpacing(4)

        down_btn = QPushButton("A-")
        down_btn.setFixedSize(28, 28)
        down_btn.setCursor(QCursor(Qt.PointingHandCursor))
        down_btn.setToolTip("تصغير الخط")
        down_btn.setStyleSheet("background: transparent; color: #94a3b8; font-weight: bold; border: none;")
        down_btn.clicked.connect(lambda: self._adjust_font_size(-1))
        zb_layout.addWidget(down_btn)

        self.lbl_size = QLabel(f"{self.editor_font_size}px")
        self.lbl_size.setStyleSheet("color: #f0f2f5; font-size: 12px; font-weight: bold; border: none;")
        zb_layout.addWidget(self.lbl_size)

        up_btn = QPushButton("A+")
        up_btn.setFixedSize(28, 28)
        up_btn.setCursor(QCursor(Qt.PointingHandCursor))
        up_btn.setToolTip("تكبير الخط")
        up_btn.setStyleSheet("background: transparent; color: #94a3b8; font-weight: bold; border: none;")
        up_btn.clicked.connect(lambda: self._adjust_font_size(1))
        zb_layout.addWidget(up_btn)
        h_layout.addWidget(zoom_box)

        # RTL / LTR Direction Toggle Button
        self.btn_dir = QPushButton("🌐 RTL")
        self.btn_dir.setToolTip("تبديل اتجاه الكتابة بين اليمين واليسار (RTL / LTR)")
        self.btn_dir.setFixedHeight(34)
        self.btn_dir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_dir.setFont(QFont(self.font_family, 11, QFont.Bold))
        self.btn_dir.setStyleSheet(f"""
            QPushButton {{
                background-color: #182229;
                color: #38bdf8;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 12px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QPushButton:hover {{
                background-color: #202c33;
                border-color: #38bdf8;
            }}
        """)
        self.btn_dir.clicked.connect(self._toggle_direction)
        h_layout.addWidget(self.btn_dir)

        # Count Badge
        self.count_badge = QLabel("✂️ 0 اختصار")
        self.count_badge.setStyleSheet(f"""
            background-color: #182229;
            color: #25D366;
            font-size: 13px;
            font-weight: bold;
            border: 1px solid #2a3942;
            border-radius: 8px;
            padding: 6px 14px;
            font-family: '{self.font_family}', 'Tajawal', sans-serif;
        """)
        h_layout.addWidget(self.count_badge)

        main_layout.addWidget(header_card)

        # ── Main Content Splitter ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1f2c34;
                width: 4px;
                border-radius: 2px;
            }
        """)

        # ── Left List Pane ──
        left_pane = QFrame()
        left_pane.setStyleSheet(f"""
            QFrame {{
                background-color: #111b21;
                border-radius: 14px;
                border: 1.5px solid #2a3942;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
        """)
        l_layout = QVBoxLayout(left_pane)
        l_layout.setContentsMargins(14, 14, 14, 14)
        l_layout.setSpacing(10)

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 بحث في الاختصارات والكلمات المفتاحية...")
        self.search_edit.setFixedHeight(40)
        self.search_edit.setFont(QFont(self.font_family, 13))
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QLineEdit:focus {{
                border-color: #25D366;
                background-color: #182229;
            }}
        """)
        self.search_edit.textChanged.connect(self.refresh_list)
        l_layout.addWidget(self.search_edit)

        # Group Filter
        self.group_filter = QComboBox()
        self.group_filter.setFixedHeight(38)
        self.group_filter.setFont(QFont(self.font_family, 13))
        self.group_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QComboBox:hover {{
                border-color: #60a5fa;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
        """)
        self.group_filter.currentTextChanged.connect(self.refresh_list)
        l_layout.addWidget(self.group_filter)

        # New Snippet Button
        new_btn = QPushButton("➕ إضافة اختصار جديد")
        new_btn.setFixedHeight(42)
        new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_btn.setFont(QFont(self.font_family, 13, QFont.Bold))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                border-radius: 10px;
                font-size: 14px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #15803d;
            }}
        """)
        new_btn.clicked.connect(self.new_snippet)
        l_layout.addWidget(new_btn)

        # Snippets List
        self.snippet_list = QListWidget()
        self.snippet_list.setFont(QFont(self.font_family, 13))
        self.snippet_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #0b141a;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 6px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 8px;
                color: #f0f2f5;
                margin-bottom: 5px;
                background-color: #111b21;
                border: 1px solid #1f2c34;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QListWidget::item:hover {{
                background-color: #1f2c34;
                border-color: #3b4a54;
            }}
            QListWidget::item:selected {{
                background-color: #172554;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
            }}
        """)
        self.snippet_list.itemClicked.connect(self._on_item_clicked)
        self.snippet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_list.customContextMenuRequested.connect(self._show_snippet_menu)
        l_layout.addWidget(self.snippet_list, stretch=1)

        splitter.addWidget(left_pane)

        # ── Right Form Pane ──
        right_pane = QFrame()
        right_pane.setStyleSheet(f"""
            QFrame {{
                background-color: #111b21;
                border-radius: 14px;
                border: 1.5px solid #2a3942;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
        """)
        r_layout = QVBoxLayout(right_pane)
        r_layout.setContentsMargins(18, 16, 18, 16)
        r_layout.setSpacing(12)

        # Field Row 1: Shortcut Trigger & Group
        r1_box = QHBoxLayout()
        r1_box.setSpacing(12)

        # Shortcut Box
        sc_col = QVBoxLayout()
        sc_col.setSpacing(4)
        lbl_sc = QLabel("رمز الاختصار (Trigger Shortcut):")
        lbl_sc.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setPlaceholderText("مثال: :mail أو #hi أو @sign أو !مرحبا")
        self.shortcut_edit.setFixedHeight(42)
        self.shortcut_edit.setFont(QFont(self.font_family, 13, QFont.Bold))
        self.shortcut_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 14px;
                font-weight: bold;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QLineEdit:focus {{
                border-color: #25D366;
                background-color: #182229;
            }}
        """)
        sc_col.addWidget(lbl_sc)
        sc_col.addWidget(self.shortcut_edit)
        r1_box.addLayout(sc_col, stretch=1)

        # Group Box
        grp_col = QVBoxLayout()
        grp_col.setSpacing(4)
        lbl_grp = QLabel("المجموعة والتصنيف (Category):")
        lbl_grp.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        self.group_combo = QComboBox()
        self.group_combo.setFixedHeight(42)
        self.group_combo.setFont(QFont(self.font_family, 13))
        self.group_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QComboBox:hover {{
                border-color: #60a5fa;
            }}
        """)
        grp_col.addWidget(lbl_grp)
        grp_col.addWidget(self.group_combo)
        r1_box.addLayout(grp_col, stretch=1)

        r_layout.addLayout(r1_box)

        # Field Row 2: Description & App Filter
        r2_box = QHBoxLayout()
        r2_box.setSpacing(12)

        # Description Box
        desc_col = QVBoxLayout()
        desc_col.setSpacing(4)
        lbl_desc = QLabel("الوصف التوضيحي (Description):")
        lbl_desc.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("وصف سريع للتعرف على الاختصار (اختياري)...")
        self.desc_edit.setFixedHeight(42)
        self.desc_edit.setFont(QFont(self.font_family, 13))
        self.desc_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QLineEdit:focus {{
                border-color: #60a5fa;
                background-color: #182229;
            }}
        """)
        desc_col.addWidget(lbl_desc)
        desc_col.addWidget(self.desc_edit)
        r2_box.addLayout(desc_col, stretch=2)

        # App Filter Box
        app_col = QVBoxLayout()
        app_col.setSpacing(4)
        lbl_app = QLabel("تطبيق محدد (Target App):")
        lbl_app.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        self.app_combo = QComboBox()
        self.app_combo.setFixedHeight(42)
        self.app_combo.setFont(QFont(self.font_family, 13))
        self.app_combo.addItem("🌐 يعمل في كافة البرامج (All Apps)", "")
        self.app_combo.addItem("💻 Visual Studio Code", "code")
        self.app_combo.addItem("💬 WhatsApp", "whatsapp")
        self.app_combo.addItem("🌐 Google Chrome / Edge", "chrome")
        self.app_combo.addItem("📄 Microsoft Word", "winword")
        self.app_combo.addItem("⚡ Terminal / PowerShell", "powershell")
        self.app_combo.addItem("📝 Notepad", "notepad")
        self.app_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 9px;
                padding: 4px 12px;
                color: #f0f2f5;
                font-size: 13px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QComboBox:hover {{
                border-color: #60a5fa;
            }}
        """)
        app_col.addWidget(lbl_app)
        app_col.addWidget(self.app_combo)
        r2_box.addLayout(app_col, stretch=1)

        r_layout.addLayout(r2_box)

        # Variable Insert Toolbar
        var_header_row = QHBoxLayout()
        lbl_content = QLabel("نص التوسيع الكامل (Expanded Content):")
        lbl_content.setStyleSheet(f"font-weight: bold; font-size: 13px; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        var_header_row.addWidget(lbl_content)
        var_header_row.addStretch()

        # Variable Quick Pills
        for v_tag, v_label in [
            ("{date}", "📅 {date}"),
            ("{time}", "⏰ {time}"),
            ("{clipboard}", "📋 {clipboard}"),
            ("{uuid}", "🔑 {uuid}"),
            ("{random}", "🎲 {random}"),
            ("{cursor}", "🎯 {cursor}")
        ]:
            btn_v = QPushButton(v_label)
            btn_v.setFixedHeight(28)
            btn_v.setCursor(QCursor(Qt.PointingHandCursor))
            btn_v.setToolTip(f"إدراج المتغير {v_tag} في موضع المؤشر")
            btn_v.setFont(QFont(self.font_family, 11, QFont.Bold))
            btn_v.setStyleSheet(f"""
                QPushButton {{
                    background-color: #182229;
                    border: 1px solid #2a3942;
                    color: #38bdf8;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 7px;
                    padding: 2px 10px;
                    font-family: '{self.font_family}', 'Tajawal', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: #202c33;
                    border-color: #38bdf8;
                    color: #7dd3fc;
                }}
            """)
            btn_v.clicked.connect(lambda _, tag=v_tag: self._insert_variable(tag))
            var_header_row.addWidget(btn_v)

        r_layout.addLayout(var_header_row)

        # Content Editor with Arabic Document Direction support
        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("اكتب النص الذي ترغب في استبداله وتوسيعه عند كتابة رمز الاختصار...")
        self.content_edit.setFont(QFont(self.font_family, self.editor_font_size))
        self._apply_editor_direction()
        self.content_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: {self.editor_font_size}px;
                border-radius: 10px;
                padding: 12px;
                border: 1.5px solid #2a3942;
                font-family: '{self.font_family}', 'Tajawal', 'Cairo', 'Segoe UI', sans-serif;
                line-height: 1.5;
            }}
            QPlainTextEdit:focus {{
                border: 1.5px solid #25D366;
            }}
        """)
        self.content_edit.textChanged.connect(self._update_live_preview)
        r_layout.addWidget(self.content_edit, stretch=1)

        # Real-time Live Expansion Preview Box
        prev_frame = QFrame()
        prev_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0b141a;
                border: 1.5px dashed #202c33;
                border-radius: 10px;
                padding: 6px 12px;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
        """)
        pv_layout = QHBoxLayout(prev_frame)
        pv_layout.setContentsMargins(8, 4, 8, 4)
        pv_tag = QLabel("معاينة حية فورية للتوسيع ⚡:")
        pv_tag.setStyleSheet(f"color: #64748b; font-size: 12px; font-weight: bold; border: none; background: transparent; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        pv_layout.addWidget(pv_tag)

        self.live_prev_lbl = QLabel("(اكتب نصاً لمعاينة التوسيع المباشر)")
        self.live_prev_lbl.setStyleSheet(f"color: #25D366; font-size: 13px; font-weight: bold; border: none; background: transparent; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        pv_layout.addWidget(self.live_prev_lbl, stretch=1)
        r_layout.addWidget(prev_frame)

        # Bottom Options and Action Buttons
        bot_row = QHBoxLayout()
        self.case_check = QCheckBox("حساس لحالة الأحرف (Case Sensitive)")
        self.case_check.setChecked(True)
        self.case_check.setFont(QFont(self.font_family, 13))
        self.case_check.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #94a3b8; font-family: '{self.font_family}', 'Tajawal', sans-serif;")
        bot_row.addWidget(self.case_check)

        bot_row.addStretch()

        self.del_btn = QPushButton("🗑️ حذف")
        self.del_btn.setFixedHeight(42)
        self.del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.del_btn.setFont(QFont(self.font_family, 13, QFont.Bold))
        self.del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #7f1d1d;
                color: #fca5a5;
                font-weight: bold;
                border-radius: 9px;
                padding: 4px 20px;
                font-size: 14px;
                border: 1px solid #991b1b;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
                color: white;
            }}
        """)
        self.del_btn.clicked.connect(self._delete_current)
        bot_row.addWidget(self.del_btn)

        save_btn = QPushButton("💾 حفظ الاختصار")
        save_btn.setFixedHeight(42)
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.setFont(QFont(self.font_family, 14, QFont.Bold))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                border-radius: 9px;
                padding: 4px 26px;
                font-size: 14px;
                border: none;
                font-family: '{self.font_family}', 'Tajawal', sans-serif;
            }}
            QPushButton:hover {{
                background-color: #15803d;
            }}
        """)
        save_btn.clicked.connect(self._save_current)
        bot_row.addWidget(save_btn)

        r_layout.addLayout(bot_row)
        splitter.addWidget(right_pane)

        splitter.setSizes([340, 660])
        main_layout.addWidget(splitter, stretch=1)

    def _on_font_family_changed(self, font_name: str):
        """Handle Google Arabic font family change from dropdown."""
        download_and_load_arabic_font(font_name)
        self.font_family = font_name
        set_arabic_font_family(font_name)
        self.setFont(QFont(self.font_family, 13))
        self.content_edit.setFont(QFont(self.font_family, self.editor_font_size))
        self.refresh_list()
        self.toast_signal.emit(f"تم تطبيق خط {font_name} بنجاح! 🔤", False)

    def _adjust_font_size(self, delta: int):
        """Zoom editor font size up or down."""
        self.editor_font_size = max(11, min(28, self.editor_font_size + delta))
        self.lbl_size.setText(f"{self.editor_font_size}px")
        self.content_edit.setFont(QFont(self.font_family, self.editor_font_size))

    def _toggle_direction(self):
        """Toggle text direction between RTL and LTR."""
        self.is_rtl = not self.is_rtl
        self.btn_dir.setText("🌐 RTL" if self.is_rtl else "🌐 LTR")
        self._apply_editor_direction()
        self.toast_signal.emit("تم تبديل اتجاه الكتابة إلى " + ("RTL (يمين لليسار)" if self.is_rtl else "LTR (يسار لليمين)"), False)

    def _apply_editor_direction(self):
        """Apply direction to the plain text edit document."""
        opt = self.content_edit.document().defaultTextOption()
        opt.setTextDirection(Qt.RightToLeft if self.is_rtl else Qt.LeftToRight)
        self.content_edit.document().setDefaultTextOption(opt)

    def set_font_family(self, font_name: str):
        """Update Arabic Google font dynamically from external callers."""
        self.font_combo.setCurrentText(font_name)

    def update_group_dropdowns(self):
        groups = get_all_groups()
        self._groups = groups
        self.group_filter.clear()
        self.group_filter.addItem("📁 جميع المجموعات (All Groups)", None)
        self.group_combo.clear()

        for g in groups:
            self.group_filter.addItem(f"{g.icon} {g.name}", g.id)
            self.group_combo.addItem(f"{g.icon} {g.name}", g.id)

    def refresh_list(self):
        self.snippet_list.clear()
        query = self.search_edit.text().strip()
        gid = self.group_filter.currentData()
        snippets = get_snippets_for_list(query=query, group_id=gid)

        total_count = len(get_all_snippets())
        filtered_count = len(snippets)
        if query or gid:
            self.count_badge.setText(f"✂️ المعروض: {filtered_count} من {total_count}")
        else:
            self.count_badge.setText(f"✂️ {total_count} اختصار مسجل")

        for s in snippets:
            desc = s.description if s.description else (s.replacement[:32].replace("\n", " ") + "..." if len(s.replacement) > 32 else s.replacement.replace("\n", " "))
            item = QListWidgetItem(f"⚡ {s.shortcut}   |   {desc}")
            item.setFont(QFont(self.font_family, 13))
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

    def _insert_variable(self, tag: str):
        self.content_edit.insertPlainText(tag)
        self.content_edit.setFocus()
        self._update_live_preview()

    def _update_live_preview(self):
        text = self.content_edit.toPlainText()
        if not text:
            self.live_prev_lbl.setText("(اكتب نصاً لمعاينة التوسيع المباشر)")
            return
        from snipglide.engine.parser import parse_variables
        rendered = parse_variables(text)
        preview_clean = rendered.replace("\n", " ⏎ ")
        if len(preview_clean) > 80:
            preview_clean = preview_clean[:80] + "..."
        self.live_prev_lbl.setText(f"» {preview_clean}")

    def new_snippet(self, initial_content: str = ""):
        self.selected_snippet_id = None
        self.shortcut_edit.clear()
        self.desc_edit.clear()
        self.content_edit.setPlainText(initial_content)
        self.app_combo.setCurrentIndex(0)
        self._update_live_preview()
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
        menu.setFont(QFont(self.font_family, 12))
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
