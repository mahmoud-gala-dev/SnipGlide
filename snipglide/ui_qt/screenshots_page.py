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


class ScreenshotViewerDialog(QDialog):
    """Full-featured modal dialog for inspecting screenshots with zoom and quick actions."""

    def __init__(self, screenshot: Screenshot, toast_callback: Optional[Callable[[str, bool], None]] = None, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.toast = toast_callback or (lambda msg, err=False: None)
        self.zoom_factor = 1.0

        self.setWindowTitle(f"معاينة لقطة الشاشة - {screenshot.filename}")
        self.resize(1100, 780)
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c1317;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ── Header bar ──
        header = QHBoxLayout()
        header.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(f"📸 {self.screenshot.filename}")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #f0f2f5;")
        title_box.addWidget(title)

        size_kb = self.screenshot.file_size / 1024
        size_str = f"{size_kb / 1024:.2f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"
        type_lbl = "شاشة كاملة 🖥️" if self.screenshot.capture_type == "full" else "مساحة مقتطعة ✂️"
        sub = QLabel(f"{type_lbl} • {self.screenshot.width} × {self.screenshot.height} px • {size_str} • {self.screenshot.created_at} • 📁 {self.screenshot.folder}")
        sub.setStyleSheet("font-size: 13px; color: #94a3b8;")
        title_box.addWidget(sub)
        header.addLayout(title_box)

        header.addStretch()

        # Zoom Controls
        btn_zoom_in = QPushButton("➕")
        btn_zoom_in.setToolTip("تكبير")
        btn_zoom_in.setFixedSize(36, 36)
        btn_zoom_in.setCursor(QCursor(Qt.PointingHandCursor))
        btn_zoom_in.setStyleSheet(self._btn_style())
        btn_zoom_in.clicked.connect(self._zoom_in)
        header.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("➖")
        btn_zoom_out.setToolTip("تصغير")
        btn_zoom_out.setFixedSize(36, 36)
        btn_zoom_out.setCursor(QCursor(Qt.PointingHandCursor))
        btn_zoom_out.setStyleSheet(self._btn_style())
        btn_zoom_out.clicked.connect(self._zoom_out)
        header.addWidget(btn_zoom_out)

        btn_fit = QPushButton("↔️ ملائمة")
        btn_fit.setToolTip("ملائمة لحجم النافذة")
        btn_fit.setFixedHeight(36)
        btn_fit.setCursor(QCursor(Qt.PointingHandCursor))
        btn_fit.setStyleSheet(self._btn_style())
        btn_fit.clicked.connect(self._fit_to_window)
        header.addWidget(btn_fit)

        btn_100 = QPushButton("1:1")
        btn_100.setToolTip("الحجم الأصلي 100%")
        btn_100.setFixedHeight(36)
        btn_100.setCursor(QCursor(Qt.PointingHandCursor))
        btn_100.setStyleSheet(self._btn_style())
        btn_100.clicked.connect(self._reset_zoom)
        header.addWidget(btn_100)

        # Quick Actions
        btn_copy = QPushButton("📋 نسخ")
        btn_copy.setFixedHeight(36)
        btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_copy.clicked.connect(self._copy_to_clipboard)
        header.addWidget(btn_copy)

        btn_save = QPushButton("💾 حفظ باسم")
        btn_save.setFixedHeight(36)
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save.setStyleSheet(self._btn_style())
        btn_save.clicked.connect(self._save_as)
        header.addWidget(btn_save)

        btn_folder = QPushButton("📁 المجلد")
        btn_folder.setFixedHeight(36)
        btn_folder.setCursor(QCursor(Qt.PointingHandCursor))
        btn_folder.setStyleSheet(self._btn_style())
        btn_folder.clicked.connect(self._open_in_folder)
        header.addWidget(btn_folder)

        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("حذف لقطة الشاشة")
        btn_del.setFixedSize(36, 36)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border: 1px solid #2a3942;
                border-radius: 8px;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_del.clicked.connect(self._delete_current)
        header.addWidget(btn_del)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(36, 36)
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #8696a0;
                border: 1px solid #2a3942;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b91c1c;
                color: white;
            }
        """)
        btn_close.clicked.connect(self.close)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # ── Image Display Viewport ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0b141a;
                border: 1px solid #202c33;
                border-radius: 12px;
            }
        """)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.img_label)
        layout.addWidget(self.scroll_area)

        # Load image
        if os.path.exists(self.screenshot.file_path):
            self.original_pixmap = QPixmap(self.screenshot.file_path)
            self._fit_to_window()
        else:
            self.img_label.setText("تعذر العثور على ملف الصورة على القرص!")
            self.img_label.setStyleSheet("color: #ef4444; font-size: 16px; font-weight: bold;")

    def _btn_style(self):
        return """
            QPushButton {
                background-color: #202c33;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2a3942;
                border-color: #3b82f6;
            }
        """

    def _update_image_display(self):
        if not hasattr(self, "original_pixmap") or self.original_pixmap.isNull():
            return
        w = int(self.original_pixmap.width() * self.zoom_factor)
        h = int(self.original_pixmap.height() * self.zoom_factor)
        scaled = self.original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(scaled)
        self.img_label.resize(scaled.size())

    def _zoom_in(self):
        if self.zoom_factor < 5.0:
            self.zoom_factor *= 1.25
            self._update_image_display()

    def _zoom_out(self):
        if self.zoom_factor > 0.1:
            self.zoom_factor /= 1.25
            self._update_image_display()

    def _reset_zoom(self):
        self.zoom_factor = 1.0
        self._update_image_display()

    def _fit_to_window(self):
        if not hasattr(self, "original_pixmap") or self.original_pixmap.isNull():
            return
        viewport_w = self.scroll_area.viewport().width() - 20
        viewport_h = self.scroll_area.viewport().height() - 20
        if viewport_w <= 0 or viewport_h <= 0:
            viewport_w, viewport_h = 1000, 600

        scale_w = viewport_w / self.original_pixmap.width()
        scale_h = viewport_h / self.original_pixmap.height()
        self.zoom_factor = min(scale_w, scale_h, 1.0)
        self._update_image_display()

    def _copy_to_clipboard(self):
        if hasattr(self, "original_pixmap") and not self.original_pixmap.isNull():
            QApplication.clipboard().setPixmap(self.original_pixmap)
            self.toast("تم نسخ الصورة إلى الحافظة بنجاح! 📋", False)

    def _open_in_folder(self):
        fp = self.screenshot.file_path
        if os.path.exists(fp):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(fp)}"')
            except Exception:
                pass

    def _delete_current(self):
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من رغبتك في حذف لقطة الشاشة '{self.screenshot.filename}' نهائياً؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_screenshot(self.screenshot.id, delete_file=True)
            self.toast("تم حذف لقطة الشاشة بنجاح.", False)
            self.close()

    def _save_as(self):
        if not hasattr(self, "original_pixmap") or self.original_pixmap.isNull():
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ لقطة الشاشة باسم",
            self.screenshot.filename,
            "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)"
        )
        if save_path:
            try:
                self.original_pixmap.save(save_path)
                self.toast("تم حفظ الصورة بنجاح! 💾", False)
            except Exception as e:
                self.toast(f"فشل حفظ الصورة: {e}", True)


class FolderDropButton(QPushButton):
    """
    Interactive Folder button in the top folder bar.
    - Accepts drag-and-drop of screenshots/videos to move them into this folder.
    - Provides a glow feedback animation on drag hover.
    - Right-click context menu allows renaming or deleting custom folders.
    """
    screenshot_dropped = Signal(int, str)  # (screenshot_id, target_folder_name)
    folder_selected = Signal(str)
    rename_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, folder_name: str, count: int = 0, color: str = "#3b82f6", is_active: bool = False, is_all: bool = False, parent=None):
        super().__init__(parent)
        self.folder_name = folder_name
        self.count = count
        self.folder_color = color or "#3b82f6"
        self.is_active = is_active
        self.is_all = is_all
        self._is_glowing = False

        self.setAcceptDrops(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(34)
        self._update_text_and_style()
        self.clicked.connect(lambda: self.folder_selected.emit(self.folder_name))

    def set_active(self, active: bool):
        self.is_active = active
        self._update_text_and_style()

    def set_count(self, count: int):
        self.count = count
        self._update_text_and_style()

    def _update_text_and_style(self):
        icon = "📂" if self.is_all else "📁"
        count_str = f" ({self.count})" if self.count >= 0 else ""
        self.setText(f"{icon} {self.folder_name}{count_str}")

        if self._is_glowing:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a8a;
                    color: #ffffff;
                    border: 2px dashed #60a5fa;
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0 14px;
                }
            """)
        elif self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #172554;
                    color: #93c5fd;
                    border: 1.5px solid #3b82f6;
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0 14px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #182229;
                    color: #94a3b8;
                    border: 1px solid #2a3942;
                    border-radius: 9px;
                    font-size: 12px;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background-color: #202c33;
                    color: #f0f2f5;
                    border-color: #3b82f6;
                }
            """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-snipglide-screenshot-id"):
            if not self.is_all:
                event.acceptProposedAction()
                self._is_glowing = True
                self._update_text_and_style()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_glowing = False
        self._update_text_and_style()
        event.accept()

    def dropEvent(self, event):
        self._is_glowing = False
        self._update_text_and_style()
        if event.mimeData().hasFormat("application/x-snipglide-screenshot-id"):
            if not self.is_all:
                try:
                    data = bytes(event.mimeData().data("application/x-snipglide-screenshot-id")).decode("utf-8")
                    screenshot_id = int(data)
                    self.screenshot_dropped.emit(screenshot_id, self.folder_name)
                    event.acceptProposedAction()
                    return
                except Exception as e:
                    logger.error(f"Failed parsing drop mime data: {e}")
        event.ignore()

    def contextMenuEvent(self, event):
        if self.folder_name in ("كافة الملفات", "العامة"):
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: white;
            }
        """)
        rename_act = menu.addAction("✏️ إعادة تسمية المجلد")
        delete_act = menu.addAction("🗑️ حذف المجلد")
        action = menu.exec(event.globalPos())
        if action == rename_act:
            self.rename_requested.emit(self.folder_name)
        elif action == delete_act:
            self.delete_requested.emit(self.folder_name)


class ScreenshotCardWidget(QFrame):
    """Modern dark card representing a single captured screenshot/video (Large Grid View - 3 Columns)."""
    copied = Signal(str)
    deleted = Signal(int)
    preview_requested = Signal(Screenshot)
    favorite_toggled = Signal(int)
    move_requested = Signal(int, str)

    def __init__(self, screenshot: Screenshot, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.setObjectName("screenshotCard")
        self.setFixedHeight(305)
        self.setStyleSheet("""
            QFrame#screenshotCard {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 14px;
            }
            QFrame#screenshotCard:hover {
                border-color: #3b82f6;
                background-color: #1a2630;
            }
        """)

        self._setup_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_start_pos"):
            if (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
                return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-snipglide-screenshot-id", str(self.screenshot.id).encode("utf-8"))
        drag.setMimeData(mime)

        pix = QPixmap(140, 65)
        pix.fill(QColor("#182229"))
        p = QPainter(pix)
        p.setPen(QColor("#3b82f6"))
        p.drawRoundedRect(0, 0, 139, 64, 8, 8)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        icon_str = "🎥" if self.screenshot.is_video else "📸"
        p.drawText(pix.rect().adjusted(4, 4, -4, -4), Qt.AlignCenter, f"{icon_str} اسحب للمجلد\n📁 {self.screenshot.folder}")
        p.end()

        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(70, 32))
        drag.exec(Qt.MoveAction)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── 1. Thumbnail Container ──
        thumb_container = QFrame(self)
        thumb_container.setFixedHeight(160)
        thumb_container.setStyleSheet("""
            background-color: #0b141a;
            border-radius: 10px;
            border: 1px solid #243440;
        """)
        thumb_layout = QVBoxLayout(thumb_container)
        thumb_layout.setContentsMargins(4, 4, 4, 4)

        self.thumb_label = QLabel(thumb_container)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.thumb_label.mousePressEvent = lambda e: self.preview_requested.emit(self.screenshot)

        self._load_thumbnail()
        thumb_layout.addWidget(self.thumb_label)
        layout.addWidget(thumb_container)

        # ── 2. Badges & Info Row ──
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        # Type Pill
        if self.screenshot.capture_type == "video_full":
            type_text = "فيديو كامل 🎥"
            type_color = "#f87171"
            type_bg = "#450a0a"
        elif self.screenshot.capture_type == "video_area":
            type_text = "فيديو مقتطع 🎬"
            type_color = "#fb923c"
            type_bg = "#431407"
        elif self.screenshot.capture_type == "full":
            type_text = "كامل الشاشة 🖥️"
            type_color = "#60a5fa"
            type_bg = "#1e3a8a"
        else:
            type_text = "قص مقتطع ✂️"
            type_color = "#c084fc"
            type_bg = "#4c1d95"

        type_badge = QLabel(type_text)
        type_badge.setStyleSheet(f"""
            background-color: {type_bg};
            color: {type_color};
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        info_row.addWidget(type_badge)

        # Folder Badge
        folder_badge = QLabel(f"📁 {self.screenshot.folder}")
        folder_badge.setToolTip(f"المجلد: {self.screenshot.folder}")
        folder_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #0284c7;
        """)
        info_row.addWidget(folder_badge)

        # Video Duration Badge if available
        if self.screenshot.is_video and self.screenshot.duration > 0:
            dur_badge = QLabel(f"⏱️ {self.screenshot.formatted_duration}")
            dur_badge.setStyleSheet("""
                background-color: #0f172a;
                color: #38bdf8;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 6px;
                border: 1px solid #1e293b;
            """)
            info_row.addWidget(dur_badge)

        # Dimensions badge
        dim_badge = QLabel(f"{self.screenshot.width}×{self.screenshot.height}")
        dim_badge.setStyleSheet("""
            background-color: #202c33;
            color: #94a3b8;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        info_row.addWidget(dim_badge)

        info_row.addStretch()

        # Favorite Button
        self.btn_fav = QPushButton("⭐" if self.screenshot.is_favorite else "☆")
        self.btn_fav.setToolTip("إضافة إلى المفضلة" if not self.screenshot.is_favorite else "إزالة من المفضلة")
        self.btn_fav.setFixedSize(28, 28)
        self.btn_fav.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_fav.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                color: #f59e0b;
            }
            QPushButton:hover {
                font-size: 18px;
            }
        """)
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        info_row.addWidget(self.btn_fav)

        layout.addLayout(info_row)

        # ── 3. Date & Size row ──
        meta_row = QHBoxLayout()
        size_kb = self.screenshot.file_size / 1024
        size_str = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"

        lbl_date = QLabel(f"📅 {self.screenshot.created_at}")
        lbl_date.setStyleSheet("font-size: 11px; color: #8696a0;")
        meta_row.addWidget(lbl_date)

        meta_row.addStretch()

        lbl_size = QLabel(size_str)
        lbl_size.setStyleSheet("font-size: 11px; color: #8696a0; font-weight: bold;")
        meta_row.addWidget(lbl_size)
        layout.addLayout(meta_row)

        # ── 4. Action Buttons ──
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        if self.screenshot.is_video:
            btn_play = QPushButton("▶ تشغيل")
            btn_play.setToolTip("مشاهدة وتشغيل مقطع الفيديو")
            btn_play.setFixedHeight(30)
            btn_play.setCursor(QCursor(Qt.PointingHandCursor))
            btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 7px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            btn_play.clicked.connect(lambda: self.preview_requested.emit(self.screenshot))
            action_row.addWidget(btn_play)

            btn_copy = QPushButton("📋 المسار")
            btn_copy.setToolTip("نسخ مسار ملف الفيديو إلى الحافظة")
            btn_copy.setFixedHeight(30)
            btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
            btn_copy.setStyleSheet("""
                QPushButton {
                    background-color: #202c33;
                    color: #94a3b8;
                    border: 1px solid #2a3942;
                    border-radius: 7px;
                    font-size: 12px;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: #2a3942;
                    color: #e9edef;
                }
            """)
            btn_copy.clicked.connect(self._copy_image)
            action_row.addWidget(btn_copy)
        else:
            btn_copy = QPushButton("📋 نسخ")
            btn_copy.setToolTip("نسخ الصورة إلى الحافظة (Ctrl+V)")
            btn_copy.setFixedHeight(30)
            btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
            btn_copy.setStyleSheet("""
                QPushButton {
                    background-color: #202c33;
                    color: #60a5fa;
                    border: 1px solid #3b82f6;
                    border-radius: 7px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: #172554;
                    color: #93c5fd;
                }
            """)
            btn_copy.clicked.connect(self._copy_image)
            action_row.addWidget(btn_copy)

            btn_view = QPushButton("🔍 معاينة")
            btn_view.setToolTip("عرض وتكبير الصورة بالكامل")
            btn_view.setFixedHeight(30)
            btn_view.setCursor(QCursor(Qt.PointingHandCursor))
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #202c33;
                    color: #e9edef;
                    border: 1px solid #2a3942;
                    border-radius: 7px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0 8px;
                }
                QPushButton:hover {
                    background-color: #2a3942;
                    color: #f0f2f5;
                }
            """)
            btn_view.clicked.connect(lambda: self.preview_requested.emit(self.screenshot))
            action_row.addWidget(btn_view)

        # Move to folder quick menu button
        btn_move = QPushButton("📂 نقل")
        btn_move.setToolTip("نقل العنصر إلى مجلد آخر (أو اسحب البطاقة مباشرة إلى المجلد بالأعلى)")
        btn_move.setFixedHeight(30)
        btn_move.setCursor(QCursor(Qt.PointingHandCursor))
        btn_move.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #38bdf8;
                border: 1px solid #2a3942;
                border-radius: 7px;
                font-size: 12px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: white;
            }
        """)
        btn_move.clicked.connect(lambda: self._show_move_menu(btn_move))
        action_row.addWidget(btn_move)

        btn_folder = QPushButton("📁")
        btn_folder.setToolTip("إظهار الملف في المجلد")
        btn_folder.setFixedSize(30, 30)
        btn_folder.setCursor(QCursor(Qt.PointingHandCursor))
        btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #f59e0b;
                border: 1px solid #2a3942;
                border-radius: 7px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2a3942;
            }
        """)
        btn_folder.clicked.connect(self._open_in_folder)
        action_row.addWidget(btn_folder)

        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("حذف لقطة الشاشة أو التسجيل")
        btn_del.setFixedSize(30, 30)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border: 1px solid #2a3942;
                border-radius: 7px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_del.clicked.connect(self._on_delete_clicked)
        action_row.addWidget(btn_del)

        layout.addLayout(action_row)

    def _show_move_menu(self, btn: QPushButton):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: white;
            }
        """)
        folders = get_screenshot_folders()
        for f in folders:
            fname = f["name"]
            if fname == self.screenshot.folder:
                act = menu.addAction(f"✓ 📁 {fname} (الحالي)")
                act.setEnabled(False)
            else:
                act = menu.addAction(f"📁 {fname}")
                act.triggered.connect(lambda _, target=fname: self.move_requested.emit(self.screenshot.id, target))

        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _load_thumbnail(self):
        if not os.path.exists(self.screenshot.file_path):
            self.thumb_label.setText("الملف غير متوفر")
            return

        if self.screenshot.is_video:
            pix = None
            thumb_path = self.screenshot.thumbnail_path
            if thumb_path and os.path.exists(thumb_path):
                pix = QPixmap(thumb_path)
            else:
                try:
                    import cv2
                    cap = cv2.VideoCapture(self.screenshot.file_path)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        h, w, ch = frame.shape
                        qimg = QImage(frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
                        pix = QPixmap.fromImage(qimg)
                except Exception:
                    pass

            if pix and not pix.isNull():
                scaled = pix.scaled(280, 150, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                final_pix = scaled.copy(max(0, (scaled.width() - 280) // 2), max(0, (scaled.height() - 150) // 2), 280, 150)

                # Draw Play Button & Duration Overlay
                painter = QPainter(final_pix)
                painter.setRenderHint(QPainter.Antialiasing, True)

                # Play button circle in center
                center = final_pix.rect().center()
                painter.setBrush(QColor(0, 0, 0, 150))
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawEllipse(center, 22, 22)

                # Play triangle
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(Qt.NoPen)
                poly = QPolygon([
                    QPoint(center.x() - 5, center.y() - 9),
                    QPoint(center.x() + 9, center.y()),
                    QPoint(center.x() - 5, center.y() + 9),
                ])
                painter.drawPolygon(poly)

                # Duration pill in bottom right
                if self.screenshot.duration > 0:
                    dur_text = f"🎥 {self.screenshot.formatted_duration}"
                    painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    dur_rect = QRect(final_pix.width() - 80, final_pix.height() - 26, 72, 20)
                    painter.setBrush(QColor(0, 0, 0, 190))
                    painter.drawRoundedRect(dur_rect, 6, 6)
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(dur_rect, Qt.AlignCenter, dur_text)

                painter.end()
                self.thumb_label.setPixmap(final_pix)
            else:
                self.thumb_label.setText("🎬 مقطع فيديو\n(انقر للتشغيل)")
                self.thumb_label.setStyleSheet("color: #60a5fa; font-size: 13px; font-weight: bold;")
            return

        reader = QImageReader(self.screenshot.file_path)
        reader.setScaledSize(QSize(280, 150))
        img = reader.read()
        if not img.isNull():
            pix = QPixmap.fromImage(img)
            self.thumb_label.setPixmap(pix)
        else:
            self.thumb_label.setText("خطأ في قراءة الصورة")

    def _copy_image(self):
        if self.screenshot.is_video:
            QApplication.clipboard().setText(self.screenshot.file_path)
            self.copied.emit("تم نسخ مسار ملف الفيديو إلى الحافظة بنجاح! 📋")
            return

        if os.path.exists(self.screenshot.file_path):
            pix = QPixmap(self.screenshot.file_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.copied.emit("تم نسخ الصورة إلى الحافظة بنجاح! 📋")

    def _open_in_folder(self):
        fp = self.screenshot.file_path
        if os.path.exists(fp):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(fp)}"')
            except Exception:
                pass

    def _on_fav_clicked(self):
        new_fav = toggle_favorite_screenshot(self.screenshot.id)
        self.screenshot.is_favorite = new_fav
        self.btn_fav.setText("⭐" if new_fav else "☆")
        self.favorite_toggled.emit(self.screenshot.id)

    def _on_delete_clicked(self):
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من رغبتك في حذف لقطة الشاشة '{self.screenshot.filename}' نهائياً؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_screenshot(self.screenshot.id, delete_file=True)
            self.deleted.emit(self.screenshot.id)


class ScreenshotCompactCardWidget(QFrame):
    """
    Compact 170x190px card widget for high-density 5-6 column grid view.
    Includes thumbnail, type/folder badge, favorite star, quick actions, and drag-and-drop support.
    """
    copied = Signal(str)
    deleted = Signal(int)
    preview_requested = Signal(Screenshot)
    favorite_toggled = Signal(int)
    move_requested = Signal(int, str)

    def __init__(self, screenshot: Screenshot, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.setObjectName("compactCard")
        self.setFixedSize(170, 190)
        self.setStyleSheet("""
            QFrame#compactCard {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
            }
            QFrame#compactCard:hover {
                border-color: #3b82f6;
                background-color: #1a2630;
            }
        """)
        self._setup_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_start_pos"):
            if (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
                return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-snipglide-screenshot-id", str(self.screenshot.id).encode("utf-8"))
        drag.setMimeData(mime)

        pix = QPixmap(130, 60)
        pix.fill(QColor("#182229"))
        p = QPainter(pix)
        p.setPen(QColor("#3b82f6"))
        p.drawRoundedRect(0, 0, 129, 59, 8, 8)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        icon_str = "🎥" if self.screenshot.is_video else "📸"
        p.drawText(pix.rect().adjusted(4, 4, -4, -4), Qt.AlignCenter, f"{icon_str} اسحب للمجلد\n📁 {self.screenshot.folder}")
        p.end()

        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(65, 30))
        drag.exec(Qt.MoveAction)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── 1. Thumbnail ──
        thumb_frame = QFrame(self)
        thumb_frame.setFixedHeight(95)
        thumb_frame.setStyleSheet("background-color: #0b141a; border-radius: 6px;")
        t_layout = QVBoxLayout(thumb_frame)
        t_layout.setContentsMargins(0, 0, 0, 0)

        self.thumb_label = QLabel(thumb_frame)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.thumb_label.mousePressEvent = lambda e: self.preview_requested.emit(self.screenshot)

        self._load_thumbnail()
        t_layout.addWidget(self.thumb_label)
        layout.addWidget(thumb_frame)

        # ── 2. Middle Row: Folder + Type + Star ──
        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)

        fld_lbl = QLabel(f"📁 {self.screenshot.folder}")
        fld_lbl.setToolTip(f"المجلد: {self.screenshot.folder}")
        fld_lbl.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 5px;
            border-radius: 4px;
        """)
        mid_row.addWidget(fld_lbl)

        mid_row.addStretch()

        btn_fav = QPushButton("⭐" if self.screenshot.is_favorite else "☆")
        btn_fav.setFixedSize(20, 20)
        btn_fav.setCursor(QCursor(Qt.PointingHandCursor))
        btn_fav.setStyleSheet("background: transparent; border: none; font-size: 13px; color: #f59e0b;")
        btn_fav.clicked.connect(self._on_fav_clicked)
        mid_row.addWidget(btn_fav)
        layout.addLayout(mid_row)

        # ── 3. Bottom Action Row ──
        act_row = QHBoxLayout()
        act_row.setSpacing(4)

        btn_view = QPushButton("▶" if self.screenshot.is_video else "🔍")
        btn_view.setToolTip("تشغيل الفيديو" if self.screenshot.is_video else "معاينة الصورة")
        btn_view.setFixedHeight(24)
        btn_view.setCursor(QCursor(Qt.PointingHandCursor))
        btn_view.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_view.clicked.connect(lambda: self.preview_requested.emit(self.screenshot))
        act_row.addWidget(btn_view, stretch=1)

        btn_copy = QPushButton("📋")
        btn_copy.setToolTip("نسخ الصورة أو مسار الفيديو")
        btn_copy.setFixedSize(24, 24)
        btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #60a5fa;
                border: 1px solid #2a3942;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2a3942;
            }
        """)
        btn_copy.clicked.connect(self._copy_image)
        act_row.addWidget(btn_copy)

        btn_move = QPushButton("📂")
        btn_move.setToolTip("نقل إلى مجلد")
        btn_move.setFixedSize(24, 24)
        btn_move.setCursor(QCursor(Qt.PointingHandCursor))
        btn_move.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #38bdf8;
                border: 1px solid #2a3942;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: white;
            }
        """)
        btn_move.clicked.connect(lambda: self._show_move_menu(btn_move))
        act_row.addWidget(btn_move)

        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("حذف")
        btn_del.setFixedSize(24, 24)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border: 1px solid #2a3942;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_del.clicked.connect(self._on_delete_clicked)
        act_row.addWidget(btn_del)

        layout.addLayout(act_row)

    def _show_move_menu(self, btn: QPushButton):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 16px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: white;
            }
        """)
        folders = get_screenshot_folders()
        for f in folders:
            fname = f["name"]
            if fname == self.screenshot.folder:
                act = menu.addAction(f"✓ 📁 {fname} (الحالي)")
                act.setEnabled(False)
            else:
                act = menu.addAction(f"📁 {fname}")
                act.triggered.connect(lambda _, target=fname: self.move_requested.emit(self.screenshot.id, target))
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _load_thumbnail(self):
        if not os.path.exists(self.screenshot.file_path):
            self.thumb_label.setText("غير متوفر")
            return

        if self.screenshot.is_video:
            pix = None
            thumb_path = self.screenshot.thumbnail_path
            if thumb_path and os.path.exists(thumb_path):
                pix = QPixmap(thumb_path)
            else:
                try:
                    import cv2
                    cap = cv2.VideoCapture(self.screenshot.file_path)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        h, w, ch = frame.shape
                        qimg = QImage(frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
                        pix = QPixmap.fromImage(qimg)
                except Exception:
                    pass

            if pix and not pix.isNull():
                scaled = pix.scaled(154, 95, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                final_pix = scaled.copy(max(0, (scaled.width() - 154) // 2), max(0, (scaled.height() - 95) // 2), 154, 95)

                p = QPainter(final_pix)
                p.setRenderHint(QPainter.Antialiasing, True)
                c = final_pix.rect().center()
                p.setBrush(QColor(0, 0, 0, 150))
                p.setPen(QPen(QColor("#ffffff"), 1.5))
                p.drawEllipse(c, 15, 15)

                p.setBrush(QColor("#ffffff"))
                p.setPen(Qt.NoPen)
                poly = QPolygon([
                    QPoint(c.x() - 4, c.y() - 6),
                    QPoint(c.x() + 6, c.y()),
                    QPoint(c.x() - 4, c.y() + 6),
                ])
                p.drawPolygon(poly)
                p.end()
                self.thumb_label.setPixmap(final_pix)
            else:
                self.thumb_label.setText("🎥 فيديو")
            return

        reader = QImageReader(self.screenshot.file_path)
        reader.setScaledSize(QSize(154, 95))
        img = reader.read()
        if not img.isNull():
            self.thumb_label.setPixmap(QPixmap.fromImage(img))
        else:
            self.thumb_label.setText("خطأ")

    def _copy_image(self):
        if self.screenshot.is_video:
            QApplication.clipboard().setText(self.screenshot.file_path)
            self.copied.emit("تم نسخ مسار ملف الفيديو! 📋")
            return
        if os.path.exists(self.screenshot.file_path):
            pix = QPixmap(self.screenshot.file_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.copied.emit("تم نسخ الصورة إلى الحافظة! 📋")

    def _on_fav_clicked(self):
        new_fav = toggle_favorite_screenshot(self.screenshot.id)
        self.screenshot.is_favorite = new_fav
        self.favorite_toggled.emit(self.screenshot.id)

    def _on_delete_clicked(self):
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف '{self.screenshot.filename}'؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_screenshot(self.screenshot.id, delete_file=True)
            self.deleted.emit(self.screenshot.id)


class ScreenshotListRowWidget(QFrame):
    """
    Horizontal detailed row widget for table-like list view (Height 54px).
    Includes mini-thumbnail, filename, type, folder badge, dimensions/duration, size, date, star, and actions.
    Supports drag and drop to move between folders.
    """
    copied = Signal(str)
    deleted = Signal(int)
    preview_requested = Signal(Screenshot)
    favorite_toggled = Signal(int)
    move_requested = Signal(int, str)

    def __init__(self, screenshot: Screenshot, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.setObjectName("listRow")
        self.setFixedHeight(54)
        self.setStyleSheet("""
            QFrame#listRow {
                background-color: #182229;
                border: 1px solid #2a3942;
                border-radius: 8px;
            }
            QFrame#listRow:hover {
                background-color: #1e2a34;
                border-color: #3b82f6;
            }
        """)
        self._setup_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_start_pos"):
            if (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
                return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-snipglide-screenshot-id", str(self.screenshot.id).encode("utf-8"))
        drag.setMimeData(mime)

        pix = QPixmap(130, 50)
        pix.fill(QColor("#182229"))
        p = QPainter(pix)
        p.setPen(QColor("#3b82f6"))
        p.drawRoundedRect(0, 0, 129, 49, 8, 8)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        icon_str = "🎥" if self.screenshot.is_video else "📸"
        p.drawText(pix.rect().adjusted(4, 4, -4, -4), Qt.AlignCenter, f"{icon_str} اسحب للمجلد\n📁 {self.screenshot.folder}")
        p.end()

        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(65, 25))
        drag.exec(Qt.MoveAction)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # 1. Mini Thumbnail (50x38)
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(50, 38)
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        self.thumb_lbl.setStyleSheet("background-color: #0b141a; border-radius: 5px; border: 1px solid #243440;")
        self.thumb_lbl.setCursor(QCursor(Qt.PointingHandCursor))
        self.thumb_lbl.mousePressEvent = lambda e: self.preview_requested.emit(self.screenshot)
        self._load_mini_thumb()
        layout.addWidget(self.thumb_lbl)

        # 2. Filename
        name_lbl = QLabel(self.screenshot.filename)
        name_lbl.setStyleSheet("color: #f0f2f5; font-weight: bold; font-size: 12px;")
        name_lbl.setToolTip(self.screenshot.filename)
        name_lbl.setFixedWidth(200)
        layout.addWidget(name_lbl)

        # 3. Type Badge
        if self.screenshot.capture_type == "video_full":
            type_text, type_color, type_bg = "فيديو كامل 🎥", "#f87171", "#450a0a"
        elif self.screenshot.capture_type == "video_area":
            type_text, type_color, type_bg = "فيديو مقتطع 🎬", "#fb923c", "#431407"
        elif self.screenshot.capture_type == "full":
            type_text, type_color, type_bg = "شاشة كاملة 🖥️", "#60a5fa", "#1e3a8a"
        else:
            type_text, type_color, type_bg = "قص مقتطع ✂️", "#c084fc", "#4c1d95"

        type_badge = QLabel(type_text)
        type_badge.setStyleSheet(f"""
            background-color: {type_bg};
            color: {type_color};
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        layout.addWidget(type_badge)

        # 4. Folder Badge
        folder_badge = QLabel(f"📁 {self.screenshot.folder}")
        folder_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #0284c7;
        """)
        layout.addWidget(folder_badge)

        # 5. Dimensions or Duration
        if self.screenshot.is_video and self.screenshot.duration > 0:
            dim_text = f"⏱️ {self.screenshot.formatted_duration}"
        else:
            dim_text = f"📐 {self.screenshot.width}×{self.screenshot.height}"
        dim_lbl = QLabel(dim_text)
        dim_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        dim_lbl.setFixedWidth(100)
        layout.addWidget(dim_lbl)

        # 6. File size
        size_kb = self.screenshot.file_size / 1024
        size_str = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
        size_lbl = QLabel(size_str)
        size_lbl.setStyleSheet("color: #8696a0; font-size: 11px; font-weight: bold;")
        size_lbl.setFixedWidth(65)
        layout.addWidget(size_lbl)

        # 7. Date
        date_lbl = QLabel(self.screenshot.created_at)
        date_lbl.setStyleSheet("color: #8696a0; font-size: 11px;")
        date_lbl.setFixedWidth(120)
        layout.addWidget(date_lbl)

        layout.addStretch()

        # 8. Favorite Star
        btn_fav = QPushButton("⭐" if self.screenshot.is_favorite else "☆")
        btn_fav.setFixedSize(28, 28)
        btn_fav.setCursor(QCursor(Qt.PointingHandCursor))
        btn_fav.setStyleSheet("background: transparent; border: none; font-size: 15px; color: #f59e0b;")
        btn_fav.clicked.connect(self._on_fav_clicked)
        layout.addWidget(btn_fav)

        # 9. Actions
        btn_view = QPushButton("▶ تشغيل" if self.screenshot.is_video else "🔍 معاينة")
        btn_view.setFixedHeight(28)
        btn_view.setCursor(QCursor(Qt.PointingHandCursor))
        btn_view.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_view.clicked.connect(lambda: self.preview_requested.emit(self.screenshot))
        layout.addWidget(btn_view)

        btn_copy = QPushButton("📋")
        btn_copy.setToolTip("نسخ الصورة أو مسار الفيديو")
        btn_copy.setFixedSize(28, 28)
        btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #60a5fa;
                border: 1px solid #2a3942;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a3942;
            }
        """)
        btn_copy.clicked.connect(self._copy_image)
        layout.addWidget(btn_copy)

        btn_move = QPushButton("📂")
        btn_move.setToolTip("نقل إلى مجلد...")
        btn_move.setFixedSize(28, 28)
        btn_move.setCursor(QCursor(Qt.PointingHandCursor))
        btn_move.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #38bdf8;
                border: 1px solid #2a3942;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: white;
            }
        """)
        btn_move.clicked.connect(lambda: self._show_move_menu(btn_move))
        layout.addWidget(btn_move)

        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("حذف")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border: 1px solid #2a3942;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_del.clicked.connect(self._on_delete_clicked)
        layout.addWidget(btn_del)

    def _show_move_menu(self, btn: QPushButton):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: white;
            }
        """)
        folders = get_screenshot_folders()
        for f in folders:
            fname = f["name"]
            if fname == self.screenshot.folder:
                act = menu.addAction(f"✓ 📁 {fname} (الحالي)")
                act.setEnabled(False)
            else:
                act = menu.addAction(f"📁 {fname}")
                act.triggered.connect(lambda _, target=fname: self.move_requested.emit(self.screenshot.id, target))
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _load_mini_thumb(self):
        if not os.path.exists(self.screenshot.file_path):
            self.thumb_lbl.setText("؟")
            return
        if self.screenshot.is_video:
            self.thumb_lbl.setText("▶")
            self.thumb_lbl.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-weight: bold; border-radius: 5px;")
            return
        reader = QImageReader(self.screenshot.file_path)
        reader.setScaledSize(QSize(50, 38))
        img = reader.read()
        if not img.isNull():
            self.thumb_lbl.setPixmap(QPixmap.fromImage(img))

    def _copy_image(self):
        if self.screenshot.is_video:
            QApplication.clipboard().setText(self.screenshot.file_path)
            self.copied.emit("تم نسخ مسار ملف الفيديو! 📋")
            return
        if os.path.exists(self.screenshot.file_path):
            pix = QPixmap(self.screenshot.file_path)
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.copied.emit("تم نسخ الصورة إلى الحافظة! 📋")

    def _on_fav_clicked(self):
        new_fav = toggle_favorite_screenshot(self.screenshot.id)
        self.screenshot.is_favorite = new_fav
        self.favorite_toggled.emit(self.screenshot.id)

    def _on_delete_clicked(self):
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف '{self.screenshot.filename}'؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_screenshot(self.screenshot.id, delete_file=True)
            self.deleted.emit(self.screenshot.id)


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
