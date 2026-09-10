import math
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List

from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect, QPoint, QMimeData
from PySide6.QtGui import (
    QPixmap, QIcon, QFont, QCursor, QColor, QPainter, QImageReader,
    QPen, QBrush, QImage, QPolygon, QDrag
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QGridLayout, QFrame, QFileDialog,
    QMessageBox, QDialog, QApplication, QMenu, QComboBox, QInputDialog
)

from snipglide.database.screenshot_repo import (
    get_all_screenshots, delete_screenshot, toggle_favorite_screenshot,
    get_screenshots_count, get_screenshots_count_filtered, delete_all_screenshots,
    get_screenshot_folders, add_screenshot_folder, rename_screenshot_folder,
    delete_screenshot_folder, move_screenshot_to_folder
)
from snipglide.models.screenshot import Screenshot
from snipglide.services.screenshot_service import ScreenshotService
from snipglide.services.video_recording_service import ScreenRecordingService
from snipglide.ui_qt.recording_floating_widget import ScreenRecorderFloatingWidget
from snipglide.ui_qt.video_player_dialog import VideoPlayerDialog
from snipglide.utils.logger import logger


from snipglide.ui_qt.screenshots import (
    ScreenshotViewerDialog,
    FolderDropButton,
    ScreenshotCardWidget,
    ScreenshotCompactCardWidget,
    ScreenshotListRowWidget,
)

__all__ = [
    "ScreenshotViewerDialog",
    "FolderDropButton",
    "ScreenshotCardWidget",
    "ScreenshotCompactCardWidget",
    "ScreenshotListRowWidget",
    "ScreenshotsPageQt",
]

class ScreenshotsPageQt(QWidget):
    """
    Main responsive UI section for capturing, viewing, organizing, and managing screenshots and screen recordings.
    Supports:
    - 3 switchable View Modes: Large Cards (⊞), Compact Grid (▦), and Detailed List (☰).
    - Full Pagination with customizable page size (12, 24, 48, 96, All).
    - Folders organization with Drag-and-Drop item transfer.
    - Screenshot and Video recording actions.
    """

    def __init__(
        self,
        screenshot_service: Optional[ScreenshotService] = None,
        recording_service: Optional[ScreenRecordingService] = None,
        toast_callback: Optional[Callable[[str, bool], None]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.screenshot_service = screenshot_service
        self.recording_service = recording_service
        self.toast = toast_callback or (lambda msg, err=False: None)

        self.floating_recorder = None
        if self.recording_service:
            self.floating_recorder = ScreenRecorderFloatingWidget(self.recording_service)
            self.recording_service.recording_saved.connect(self._on_external_recording_saved)

        # State
        self.active_filter = "all"  # 'all', 'full', 'area', 'video', 'favorite'
        self.active_folder = "كافة الملفات"
        self.active_view_mode = "cards"  # 'cards', 'compact', 'list'
        self.search_text = ""
        self.current_page = 1
        self.page_size = 24  # 12, 24, 48, 96, -1 (all)
        self.total_pages = 1
        self.folder_buttons = {}

        self._setup_ui()
        self._refresh_folders_bar()
        self.refresh_list()

        # Connect live service signals
        if self.screenshot_service:
            self.screenshot_service.screenshot_saved.connect(self._on_external_screenshot_saved)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(14)

        # ── 1. Header Row ──
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        # Drawer toggle
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
        header_row.addWidget(btn_drawer)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("📸 لقطات وتسجيلات الشاشة (Screenshots & Video)")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #f0f2f5;")
        title_box.addWidget(title)

        subtitle = QLabel("التقاط وتسجيل فوري: شاشة كاملة (Ctrl + Print) • تحديد مساحة (Win + Print) • تصوير فيديو MP4 • ترتيب بمجلدات بالسحب والإفلات")
        subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)

        header_row.addStretch()

        # Primary Action: Full Screenshot Button
        btn_capture_full = QPushButton("📸 لقطة كاملة")
        btn_capture_full.setToolTip("التقاط الشاشة بالكامل فوراً (Ctrl + Print)")
        btn_capture_full.setCursor(QCursor(Qt.PointingHandCursor))
        btn_capture_full.setFixedHeight(38)
        btn_capture_full.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 9px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_capture_full.clicked.connect(self._trigger_full_capture)
        header_row.addWidget(btn_capture_full)

        # Primary Action: Area Snipping Button
        btn_capture_area = QPushButton("✂️ قص جزء")
        btn_capture_area.setToolTip("فتح أداة تحديد واقتصاص جزء من الشاشة (Win + Print)")
        btn_capture_area.setCursor(QCursor(Qt.PointingHandCursor))
        btn_capture_area.setFixedHeight(38)
        btn_capture_area.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 9px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        btn_capture_area.clicked.connect(self._trigger_area_capture)
        header_row.addWidget(btn_capture_area)

        # Video Action: Full Screen Video Record
        btn_record_full = QPushButton("🎥 تسجيل فيديو كامل")
        btn_record_full.setToolTip("بدء تسجيل فيديو للشاشة بالكامل بصيغة MP4 عالية الدقة")
        btn_record_full.setCursor(QCursor(Qt.PointingHandCursor))
        btn_record_full.setFixedHeight(38)
        btn_record_full.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 9px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        btn_record_full.clicked.connect(self._trigger_full_video_record)
        header_row.addWidget(btn_record_full)

        # Video Action: Area Video Record
        btn_record_area = QPushButton("🎬 تسجيل مساحة محددة")
        btn_record_area.setToolTip("تحديد مساحة مخصصة من الشاشة وبدء تسجيلها فيديو")
        btn_record_area.setCursor(QCursor(Qt.PointingHandCursor))
        btn_record_area.setFixedHeight(38)
        btn_record_area.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 9px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c2410c;
            }
        """)
        btn_record_area.clicked.connect(self._trigger_area_video_record)
        header_row.addWidget(btn_record_area)

        # Open Folder Button
        btn_folder = QPushButton("📁 المجلد")
        btn_folder.setToolTip("فتح مجلد حفظ اللقطات والتسجيلات في مستكشف ويندوز")
        btn_folder.setCursor(QCursor(Qt.PointingHandCursor))
        btn_folder.setFixedHeight(38)
        btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #e9edef;
                border: 1.5px solid #2a3942;
                border-radius: 9px;
                padding: 0 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #3b82f6;
                color: #60a5fa;
            }
        """)
        btn_folder.clicked.connect(self._open_screenshots_folder)
        header_row.addWidget(btn_folder)

        main_layout.addLayout(header_row)

        # ── 2. Modern Folder Bar (With Drag & Drop Support) ──
        self.folder_bar_frame = QFrame()
        self.folder_bar_frame.setStyleSheet("""
            QFrame {
                background-color: #111a21;
                border: 1.5px solid #202c33;
                border-radius: 12px;
            }
        """)
        fb_layout = QHBoxLayout(self.folder_bar_frame)
        fb_layout.setContentsMargins(12, 8, 12, 8)
        fb_layout.setSpacing(8)

        lbl_fld_title = QLabel("📁 المجلدات:")
        lbl_fld_title.setStyleSheet("color: #e9edef; font-weight: bold; font-size: 13px;")
        fb_layout.addWidget(lbl_fld_title)

        # Scrollable container for folder tabs
        self.folder_buttons_layout = QHBoxLayout()
        self.folder_buttons_layout.setSpacing(8)
        fb_layout.addLayout(self.folder_buttons_layout)

        fb_layout.addStretch()

        # Add new folder button
        btn_add_fld = QPushButton("➕ مجلد جديد")
        btn_add_fld.setToolTip("إنشاء مجلد جديد لترتيب الصور والفيديوهات")
        btn_add_fld.setCursor(QCursor(Qt.PointingHandCursor))
        btn_add_fld.setFixedHeight(34)
        btn_add_fld.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1.5px dashed #0284c7;
                border-radius: 9px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: white;
                border-style: solid;
            }
        """)
        btn_add_fld.clicked.connect(self._create_folder_dialog)
        fb_layout.addWidget(btn_add_fld)

        main_layout.addWidget(self.folder_bar_frame)

        # ── 3. Filter Bar & View Mode Switcher ──
        filter_card = QFrame()
        filter_card.setStyleSheet("""
            QFrame {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 12px;
            }
        """)
        fc_layout = QHBoxLayout(filter_card)
        fc_layout.setContentsMargins(12, 8, 12, 8)
        fc_layout.setSpacing(10)

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 ابحث عن لقطة بالاسم أو التاريخ...")
        self.search_edit.setFixedHeight(36)
        self.search_edit.textChanged.connect(self._on_search_changed)
        fc_layout.addWidget(self.search_edit, stretch=1)

        # Filter buttons
        self.filter_buttons = {}
        filters = [
            ("all", "الكل 📁"),
            ("full", "شاشة كاملة 🖥️"),
            ("area", "أجزاء مقتطعة ✂️"),
            ("video", "تسجيلات الفيديو 🎥"),
            ("favorite", "المفضلة ⭐"),
        ]
        for f_id, f_text in filters:
            btn = QPushButton(f_text)
            btn.setFixedHeight(34)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, fid=f_id: self._set_filter(fid))
            self.filter_buttons[f_id] = btn
            fc_layout.addWidget(btn)

        self._update_filter_styles()

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #2a3942; max-width: 1px;")
        fc_layout.addWidget(sep)

        # View Mode Buttons: Cards (⊞), Compact (▦), List (☰)
        self.view_buttons = {}
        view_modes = [
            ("cards", "⊞ بطاقات", "عرض بطاقات كبيرة"),
            ("compact", "▦ مصغرات", "عرض شبكي مصغر متعدد الأعمدة"),
            ("list", "☰ قائمة", "عرض جدول وتفاصيل"),
        ]
        for v_mode, v_text, v_tip in view_modes:
            btn_v = QPushButton(v_text)
            btn_v.setToolTip(v_tip)
            btn_v.setFixedHeight(34)
            btn_v.setCursor(QCursor(Qt.PointingHandCursor))
            btn_v.clicked.connect(lambda _, m=v_mode: self._set_view_mode(m))
            self.view_buttons[v_mode] = btn_v
            fc_layout.addWidget(btn_v)

        self._update_view_mode_styles()

        # Count badge
        self.lbl_count = QLabel("0 لقطة")
        self.lbl_count.setStyleSheet("""
            background-color: #202c33;
            color: #60a5fa;
            font-weight: bold;
            font-size: 12px;
            padding: 5px 12px;
            border-radius: 8px;
            border: 1px solid #3b4a54;
        """)
        fc_layout.addWidget(self.lbl_count)

        main_layout.addWidget(filter_card)

        # ── 4. Scroll Area & Gallery Grid ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 4, 0, 10)
        self.grid_layout.setSpacing(14)

        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # ── 5. Pagination Bar (Bottom) ──
        self.pagination_frame = QFrame()
        self.pagination_frame.setStyleSheet("""
            QFrame {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
            }
        """)
        p_layout = QHBoxLayout(self.pagination_frame)
        p_layout.setContentsMargins(14, 6, 14, 6)
        p_layout.setSpacing(10)

        self.lbl_page_info = QLabel("عرض 0 - 0 من أصل 0")
        self.lbl_page_info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        p_layout.addWidget(self.lbl_page_info)

        p_layout.addStretch()

        # Page navigation controls
        self.btn_first_page = QPushButton("⏮ الأولى")
        self.btn_first_page.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_first_page.setFixedHeight(30)
        self.btn_first_page.setStyleSheet(self._pagination_btn_style())
        self.btn_first_page.clicked.connect(lambda: self._go_to_page(1))
        p_layout.addWidget(self.btn_first_page)

        self.btn_prev_page = QPushButton("◀ السابق")
        self.btn_prev_page.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_prev_page.setFixedHeight(30)
        self.btn_prev_page.setStyleSheet(self._pagination_btn_style())
        self.btn_prev_page.clicked.connect(lambda: self._go_to_page(self.current_page - 1))
        p_layout.addWidget(self.btn_prev_page)

        self.lbl_current_page = QLabel("صفحة 1 من 1")
        self.lbl_current_page.setStyleSheet("""
            color: #f0f2f5;
            font-weight: bold;
            font-size: 12px;
            padding: 4px 10px;
            background-color: #202c33;
            border-radius: 6px;
        """)
        p_layout.addWidget(self.lbl_current_page)

        self.btn_next_page = QPushButton("التالي ▶")
        self.btn_next_page.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_next_page.setFixedHeight(30)
        self.btn_next_page.setStyleSheet(self._pagination_btn_style())
        self.btn_next_page.clicked.connect(lambda: self._go_to_page(self.current_page + 1))
        p_layout.addWidget(self.btn_next_page)

        self.btn_last_page = QPushButton("الأخيرة ⏭")
        self.btn_last_page.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_last_page.setFixedHeight(30)
        self.btn_last_page.setStyleSheet(self._pagination_btn_style())
        self.btn_last_page.clicked.connect(lambda: self._go_to_page(self.total_pages))
        p_layout.addWidget(self.btn_last_page)

        # Page Size selector
        lbl_size_title = QLabel("العناصر في الصفحة:")
        lbl_size_title.setStyleSheet("color: #8696a0; font-size: 12px; margin-right: 6px;")
        p_layout.addWidget(lbl_size_title)

        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["12", "24", "48", "96", "الكل"])
        self.combo_page_size.setCurrentText(str(self.page_size))
        self.combo_page_size.setFixedHeight(30)
        self.combo_page_size.setStyleSheet("""
            QComboBox {
                background-color: #202c33;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #182229;
                color: #e9edef;
                selection-background-color: #2563eb;
            }
        """)
        self.combo_page_size.currentTextChanged.connect(self._on_page_size_changed)
        p_layout.addWidget(self.combo_page_size)

        main_layout.addWidget(self.pagination_frame)

    def _pagination_btn_style(self):
        return """
            QPushButton {
                background-color: #202c33;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 6px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
                border-color: #3b82f6;
                color: white;
            }
            QPushButton:disabled {
                background-color: #131b20;
                color: #4b5563;
                border-color: #1e293b;
            }
        """

    def _set_view_mode(self, mode: str):
        if mode != self.active_view_mode:
            self.active_view_mode = mode
            self._update_view_mode_styles()
            self.refresh_list()

    def _update_view_mode_styles(self):
        for mode, btn in self.view_buttons.items():
            is_active = (mode == self.active_view_mode)
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: white;
                        border: 1.5px solid #60a5fa;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: bold;
                        padding: 0 12px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #202c33;
                        color: #94a3b8;
                        border: 1px solid #2a3942;
                        border-radius: 8px;
                        font-size: 12px;
                        padding: 0 10px;
                    }
                    QPushButton:hover {
                        background-color: #26333c;
                        color: #e9edef;
                    }
                """)

    def _set_filter(self, filter_id: str):
        self.active_filter = filter_id
        self.current_page = 1
        self._update_filter_styles()
        self.refresh_list()

    def _update_filter_styles(self):
        for fid, btn in self.filter_buttons.items():
            is_active = (fid == self.active_filter)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #172554;
                        color: #60a5fa;
                        border: 1.5px solid #3b82f6;
                        border-radius: 8px;
                        font-size: 13px;
                        font-weight: bold;
                        padding: 0 14px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #202c33;
                        color: #94a3b8;
                        border: 1px solid #2a3942;
                        border-radius: 8px;
                        font-size: 13px;
                        padding: 0 12px;
                    }
                    QPushButton:hover {
                        background-color: #26333c;
                        color: #e9edef;
                    }
                """)

    def _on_search_changed(self, text: str):
        self.search_text = text.strip()
        self.current_page = 1
        self.refresh_list()

    def _on_page_size_changed(self, val: str):
        if val == "الكل":
            self.page_size = -1
        else:
            try:
                self.page_size = int(val)
            except ValueError:
                self.page_size = 24
        self.current_page = 1
        self.refresh_list()

    def _go_to_page(self, page_num: int):
        new_page = max(1, min(page_num, self.total_pages))
        if new_page != self.current_page:
            self.current_page = new_page
            self.refresh_list()

    # ── Folder Operations ──
    def _refresh_folders_bar(self):
        # Clear existing folder buttons
        while self.folder_buttons_layout.count():
            item = self.folder_buttons_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.folder_buttons.clear()

        # 1. Add "كافة الملفات" tab
        total_all = get_screenshots_count()
        btn_all = FolderDropButton(
            folder_name="كافة الملفات",
            count=total_all,
            is_active=(self.active_folder == "كافة الملفات"),
            is_all=True,
            parent=self
        )
        btn_all.folder_selected.connect(self._on_folder_selected)
        self.folder_buttons["كافة الملفات"] = btn_all
        self.folder_buttons_layout.addWidget(btn_all)

        # 2. Add each folder from database
        folders = get_screenshot_folders()
        for f in folders:
            fname = f["name"]
            fcnt = f["count"]
            fcol = f.get("color", "#3b82f6")
            fbtn = FolderDropButton(
                folder_name=fname,
                count=fcnt,
                color=fcol,
                is_active=(self.active_folder == fname),
                is_all=False,
                parent=self
            )
            fbtn.folder_selected.connect(self._on_folder_selected)
            fbtn.screenshot_dropped.connect(self._on_screenshot_dropped)
            fbtn.rename_requested.connect(self._rename_folder_dialog)
            fbtn.delete_requested.connect(self._delete_folder_dialog)
            self.folder_buttons[fname] = fbtn
            self.folder_buttons_layout.addWidget(fbtn)

    def _on_folder_selected(self, folder_name: str):
        self.active_folder = folder_name
        self.current_page = 1
        for fname, btn in self.folder_buttons.items():
            btn.set_active(fname == folder_name)
        self.refresh_list()

    def _on_screenshot_dropped(self, screenshot_id: int, target_folder: str):
        success = move_screenshot_to_folder(screenshot_id, target_folder)
        if success:
            self.toast(f"تم نقل العنصر إلى مجلد '{target_folder}' بنجاح! 📁", False)
            self._refresh_folders_bar()
            self.refresh_list()
        else:
            self.toast("فشل نقل العنصر إلى المجلد!", True)

    def _on_move_requested(self, screenshot_id: int, target_folder: str):
        success = move_screenshot_to_folder(screenshot_id, target_folder)
        if success:
            self.toast(f"تم نقل العنصر إلى مجلد '{target_folder}' بنجاح! 📁", False)
            self._refresh_folders_bar()
            self.refresh_list()
        else:
            self.toast("فشل نقل العنصر إلى المجلد!", True)

    def _create_folder_dialog(self):
        name, ok = QInputDialog.getText(
            self,
            "إنشاء مجلد جديد",
            "أدخل اسم المجلد الجديد لتنظيم اللقطات والتسجيلات:"
        )
        if ok and name and name.strip():
            folder_name = name.strip()
            if folder_name in ("كافة الملفات", "الكل"):
                self.toast("اسم المجلد محجوز للنظام!", True)
                return
            success = add_screenshot_folder(folder_name)
            if success:
                self.toast(f"تم إنشاء المجلد '{folder_name}' بنجاح! 📁", False)
                self.active_folder = folder_name
                self._refresh_folders_bar()
                self.refresh_list()
            else:
                self.toast("المجلد موجود بالفعل مسبقاً!", True)

    def _rename_folder_dialog(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self,
            "إعادة تسمية المجلد",
            f"أدخل الاسم الجديد للمجلد '{old_name}':",
            text=old_name
        )
        if ok and new_name and new_name.strip() and new_name.strip() != old_name:
            target = new_name.strip()
            if target in ("كافة الملفات", "الكل"):
                self.toast("اسم المجلد محجوز للنظام!", True)
                return
            success = rename_screenshot_folder(old_name, target)
            if success:
                self.toast(f"تم تعديل اسم المجلد إلى '{target}' بنجاح! ✏️", False)
                if self.active_folder == old_name:
                    self.active_folder = target
                self._refresh_folders_bar()
                self.refresh_list()
            else:
                self.toast("فشل إعادة تسمية المجلد أو الاسم مستخدم بالفعل!", True)

    def _delete_folder_dialog(self, folder_name: str):
        reply = QMessageBox.question(
            self,
            "تأكيد حذف المجلد",
            f"هل أنت متأكد من رغبتك في حذف المجلد '{folder_name}'؟\n\n"
            "ملاحظة: سيتم الاحتفاظ بكافة الصور والفيديوهات ونقلها تلقائياً إلى مجلد 'العامة'.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = delete_screenshot_folder(folder_name)
            if success:
                self.toast(f"تم حذف المجلد '{folder_name}' ونقل محتوياته إلى 'العامة'.", False)
                if self.active_folder == folder_name:
                    self.active_folder = "كافة الملفات"
                self._refresh_folders_bar()
                self.refresh_list()
            else:
                self.toast("تعذر حذف المجلد!", True)

    def refresh_list(self):
        # Clear existing items from grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        capture_type = None
        favorites_only = False
        if self.active_filter == "full":
            capture_type = "full"
        elif self.active_filter == "area":
            capture_type = "area"
        elif self.active_filter == "video":
            capture_type = "video"
        elif self.active_filter == "favorite":
            favorites_only = True

        target_folder = None if self.active_folder == "كافة الملفات" else self.active_folder

        # Compute total matching count for pagination
        total_filtered = get_screenshots_count_filtered(
            search_query=self.search_text,
            capture_type=capture_type,
            favorites_only=favorites_only,
            folder=target_folder
        )

        total_all = get_screenshots_count()

        # Calculate pages
        if self.page_size > 0:
            self.total_pages = max(1, math.ceil(total_filtered / self.page_size))
        else:
            self.total_pages = 1

        self.current_page = max(1, min(self.current_page, self.total_pages))

        # Query items with limit and offset
        if self.page_size > 0:
            limit = self.page_size
            offset = (self.current_page - 1) * self.page_size
        else:
            limit = 10000
            offset = 0

        screenshots = get_all_screenshots(
            search_query=self.search_text,
            capture_type=capture_type,
            favorites_only=favorites_only,
            folder=target_folder,
            limit=limit,
            offset=offset
        )

        # Update labels & pagination controls
        if total_filtered > 0:
            start_num = offset + 1
            end_num = offset + len(screenshots)
            self.lbl_page_info.setText(f"عرض {start_num} - {end_num} من أصل {total_filtered} عنصر")
            self.lbl_count.setText(f"{total_filtered} من أصل {total_all}")
        else:
            self.lbl_page_info.setText("عرض 0 - 0 من أصل 0")
            self.lbl_count.setText(f"0 من أصل {total_all}")

        self.lbl_current_page.setText(f"صفحة {self.current_page} من {self.total_pages}")
        self.btn_first_page.setEnabled(self.current_page > 1)
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < self.total_pages)
        self.btn_last_page.setEnabled(self.current_page < self.total_pages)

        if not screenshots:
            self._render_empty_state()
            return

        # Render active view mode
        if self.active_view_mode == "compact":
            columns = 6
            for idx, shot in enumerate(screenshots):
                card = ScreenshotCompactCardWidget(shot, parent=self)
                card.copied.connect(lambda msg: self.toast(msg, False))
                card.deleted.connect(lambda _: self._on_item_deleted())
                card.preview_requested.connect(self._open_viewer)
                card.favorite_toggled.connect(lambda _: self.refresh_list() if self.active_filter == "favorite" else None)
                card.move_requested.connect(self._on_move_requested)

                row = idx // columns
                col = idx % columns
                self.grid_layout.addWidget(card, row, col)

        elif self.active_view_mode == "list":
            for idx, shot in enumerate(screenshots):
                row_card = ScreenshotListRowWidget(shot, parent=self)
                row_card.copied.connect(lambda msg: self.toast(msg, False))
                row_card.deleted.connect(lambda _: self._on_item_deleted())
                row_card.preview_requested.connect(self._open_viewer)
                row_card.favorite_toggled.connect(lambda _: self.refresh_list() if self.active_filter == "favorite" else None)
                row_card.move_requested.connect(self._on_move_requested)

                self.grid_layout.addWidget(row_card, idx, 0)

        else:  # 'cards' (Large Cards Grid - 3 columns)
            columns = 3
            for idx, shot in enumerate(screenshots):
                card = ScreenshotCardWidget(shot, parent=self)
                card.copied.connect(lambda msg: self.toast(msg, False))
                card.deleted.connect(lambda _: self._on_item_deleted())
                card.preview_requested.connect(self._open_viewer)
                card.favorite_toggled.connect(lambda _: self.refresh_list() if self.active_filter == "favorite" else None)
                card.move_requested.connect(self._on_move_requested)

                row = idx // columns
                col = idx % columns
                self.grid_layout.addWidget(card, row, col)

    def _on_item_deleted(self):
        self._refresh_folders_bar()
        self.refresh_list()

    def _render_empty_state(self):
        empty_box = QFrame()
        empty_box.setStyleSheet("""
            QFrame {
                background-color: #182229;
                border: 2px dashed #2a3942;
                border-radius: 16px;
                padding: 40px;
            }
        """)
        vbox = QVBoxLayout(empty_box)
        vbox.setAlignment(Qt.AlignCenter)
        vbox.setSpacing(14)

        icon_lbl = QLabel("📸 🎬")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 50px; border: none;")
        vbox.addWidget(icon_lbl)

        title = QLabel("لا توجد لقطات أو تسجيلات بعد!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f0f2f5; border: none;")
        vbox.addWidget(title)

        desc = QLabel(
            "يمكنك التقاط الشاشة أو تسجيل فيديو في أي وقت حتى أثناء تصغير البرنامج في الخلفية:\n"
            "• اضغط Ctrl + PrintScreen لالتقاط وحفظ الشاشة بالكامل فوراً.\n"
            "• اضغط Win + PrintScreen لتحديد واقتصاص أي جزء تريده بدقة.\n"
            "• استخدم أزرار تسجيل الفيديو 🎥 بالأعلى لتصوير الشاشة أو جزء محدد بصيغة MP4.\n"
            "• رتّب عناصرك في مجلدات بالسحب والإفلات مباشرة أو باستخدام زر 'نقل'."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.6; border: none;")
        vbox.addWidget(desc)

        # Quick action row in empty state
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setAlignment(Qt.AlignCenter)

        b1 = QPushButton("📸 التقاط الشاشة الآن")
        b1.setFixedHeight(38)
        b1.setCursor(QCursor(Qt.PointingHandCursor))
        b1.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border-radius: 9px;
                padding: 0 16px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        b1.clicked.connect(self._trigger_full_capture)
        btn_row.addWidget(b1)

        b2 = QPushButton("✂️ قص جزء محدد")
        b2.setFixedHeight(38)
        b2.setCursor(QCursor(Qt.PointingHandCursor))
        b2.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-weight: bold;
                border-radius: 9px;
                padding: 0 16px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        b2.clicked.connect(self._trigger_area_capture)
        btn_row.addWidget(b2)

        b3 = QPushButton("🎥 تسجيل فيديو كامل")
        b3.setFixedHeight(38)
        b3.setCursor(QCursor(Qt.PointingHandCursor))
        b3.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                border-radius: 9px;
                padding: 0 16px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        b3.clicked.connect(self._trigger_full_video_record)
        btn_row.addWidget(b3)

        vbox.addLayout(btn_row)
        self.grid_layout.addWidget(empty_box, 0, 0, 1, 3)

    def _open_viewer(self, screenshot: Screenshot):
        if screenshot.is_video:
            dlg = VideoPlayerDialog(screenshot, toast_callback=self.toast, parent=self)
            dlg.exec()
            self._refresh_folders_bar()
            self.refresh_list()
        else:
            dlg = ScreenshotViewerDialog(screenshot, toast_callback=self.toast, parent=self)
            dlg.exec()
            self._refresh_folders_bar()
            self.refresh_list()

    def _trigger_full_capture(self):
        if self.screenshot_service:
            self.screenshot_service.capture_full_screen()
        else:
            self.toast("خدمة لقطات الشاشة غير متصلة!", True)

    def _trigger_area_capture(self):
        if self.screenshot_service:
            self.screenshot_service.start_area_capture()
        else:
            self.toast("خدمة لقطات الشاشة غير متصلة!", True)

    def _trigger_full_video_record(self):
        if self.recording_service:
            self.recording_service.start_full_screen_recording()
        else:
            self.toast("خدمة تسجيل الفيديو غير متصلة!", True)

    def _trigger_area_video_record(self):
        if self.recording_service:
            self.recording_service.start_area_recording()
        else:
            self.toast("خدمة تسجيل الفيديو غير متصلة!", True)

    def _open_screenshots_folder(self):
        if self.screenshot_service:
            p = self.screenshot_service.get_save_dir()
            try:
                os.startfile(str(p))
            except Exception as e:
                self.toast(f"تعذر فتح المجلد: {e}", True)

    def _on_external_screenshot_saved(self, file_path: str, capture_type: str):
        self._refresh_folders_bar()
        self.refresh_list()

    def _on_external_recording_saved(self, file_path: str, capture_type: str):
        self._refresh_folders_bar()
        self.refresh_list()
