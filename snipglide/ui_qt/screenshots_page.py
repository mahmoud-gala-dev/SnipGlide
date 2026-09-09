import os
import subprocess
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import (
    QPixmap, QIcon, QFont, QCursor, QColor, QPainter, QImageReader,
    QPen, QBrush, QImage, QPolygon
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QGridLayout, QFrame, QFileDialog,
    QMessageBox, QDialog, QApplication
)

from snipglide.database.screenshot_repo import (
    get_all_screenshots, delete_screenshot, toggle_favorite_screenshot,
    get_screenshots_count, delete_all_screenshots
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
        sub = QLabel(f"{type_lbl} • {self.screenshot.width} × {self.screenshot.height} px • {size_str} • {self.screenshot.created_at}")
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

        btn_copy = QPushButton("📋 نسخ الصورة")
        btn_copy.setFixedHeight(36)
        btn_copy.setCursor(QCursor(Qt.PointingHandCursor))
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_copy.clicked.connect(self._copy_image)
        header.addWidget(btn_copy)

        btn_save_as = QPushButton("💾 حفظ باسم...")
        btn_save_as.setFixedHeight(36)
        btn_save_as.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save_as.setStyleSheet(self._btn_style())
        btn_save_as.clicked.connect(self._save_as)
        header.addWidget(btn_save_as)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(36, 36)
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #3b4a54;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # ── Image Display Area with Scroll ──
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 12px;
            }
        """)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: transparent;")

        self.original_pixmap = QPixmap(self.screenshot.file_path)
        self.scroll_area.setWidget(self.img_label)
        layout.addWidget(self.scroll_area, stretch=1)

        # Trigger initial fit
        QTimer.singleShot(50, self._fit_to_window)

    def _btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #182229;
                color: #e9edef;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #202c33;
                color: #60a5fa;
                border-color: #3b82f6;
            }
        """

    def _update_pixmap_display(self):
        if self.original_pixmap.isNull():
            self.img_label.setText("تعذر تحميل ملف الصورة!")
            return

        target_w = max(50, int(self.original_pixmap.width() * self.zoom_factor))
        target_h = max(50, int(self.original_pixmap.height() * self.zoom_factor))

        scaled = self.original_pixmap.scaled(
            target_w, target_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.img_label.setPixmap(scaled)

    def _zoom_in(self):
        self.zoom_factor = min(4.0, self.zoom_factor * 1.25)
        self._update_pixmap_display()

    def _zoom_out(self):
        self.zoom_factor = max(0.1, self.zoom_factor / 1.25)
        self._update_pixmap_display()

    def _fit_to_window(self):
        if self.original_pixmap.isNull():
            return
        avail_w = max(100, self.scroll_area.viewport().width() - 30)
        avail_h = max(100, self.scroll_area.viewport().height() - 30)

        factor_w = avail_w / self.original_pixmap.width()
        factor_h = avail_h / self.original_pixmap.height()
        self.zoom_factor = min(factor_w, factor_h, 1.0)
        self._update_pixmap_display()

    def _copy_image(self):
        if not self.original_pixmap.isNull():
            QApplication.clipboard().setPixmap(self.original_pixmap)
            self.toast("تم نسخ الصورة إلى الحافظة بنجاح! 📋", False)

    def _save_as(self):
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


class ScreenshotCardWidget(QFrame):
    """Modern dark card representing a single captured screenshot with thumbnails & actions."""
    copied = Signal(str)
    deleted = Signal(int)
    preview_requested = Signal(Screenshot)
    favorite_toggled = Signal(int)

    def __init__(self, screenshot: Screenshot, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.setObjectName("screenshotCard")
        self.setFixedHeight(300)
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

        # Asynchronously or smoothly load thumbnail
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


class ScreenshotsPageQt(QWidget):
    """
    Main responsive UI section for capturing, viewing, organizing, and managing screenshots and screen recordings.
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

        self.active_filter = "all"  # 'all', 'full', 'area', 'video', 'favorite'
        self.search_text = ""

        self._setup_ui()
        self.refresh_list()

        # Connect live service signals
        if self.screenshot_service:
            self.screenshot_service.screenshot_saved.connect(self._on_external_screenshot_saved)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 22, 28, 22)
        main_layout.setSpacing(16)

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
        title_box.setSpacing(3)
        title = QLabel("📸 لقطات وتسجيلات الشاشة (Screenshots & Video)")
        title.setStyleSheet("font-size: 23px; font-weight: 800; color: #f0f2f5;")
        title_box.addWidget(title)

        subtitle = QLabel("التقاط وتسجيل فوري: شاشة كاملة (Ctrl + Print) • تحديد مساحة (Win + Print) • تصوير فيديو MP4")
        subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)

        header_row.addStretch()

        # Primary Action: Full Screenshot Button
        btn_capture_full = QPushButton("📸 لقطة كاملة")
        btn_capture_full.setToolTip("التقاط الشاشة بالكامل فوراً (Ctrl + Print)")
        btn_capture_full.setCursor(QCursor(Qt.PointingHandCursor))
        btn_capture_full.setFixedHeight(40)
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
        btn_capture_area.setFixedHeight(40)
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
        btn_record_full.setFixedHeight(40)
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
        btn_record_area.setFixedHeight(40)
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
        btn_folder.setFixedHeight(40)
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

        # ── 2. Filter Bar & Search Row ──
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
        self.search_edit.setFixedHeight(38)
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
            btn.setFixedHeight(36)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, fid=f_id: self._set_filter(fid))
            self.filter_buttons[f_id] = btn
            fc_layout.addWidget(btn)

        self._update_filter_styles()

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

        # ── 3. Scroll Area & Gallery Grid ──
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
        self.grid_layout.setSpacing(16)

        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

    def _set_filter(self, filter_id: str):
        self.active_filter = filter_id
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
        self.refresh_list()

    def refresh_list(self):
        # Clear existing items
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

        screenshots = get_all_screenshots(
            search_query=self.search_text,
            capture_type=capture_type,
            favorites_only=favorites_only,
            limit=200
        )

        total_count = get_screenshots_count()
        self.lbl_count.setText(f"{len(screenshots)} من أصل {total_count}")

        if not screenshots:
            self._render_empty_state()
            return

        # Render 3 columns in grid
        columns = 3
        for idx, shot in enumerate(screenshots):
            card = ScreenshotCardWidget(shot, parent=self)
            card.copied.connect(lambda msg: self.toast(msg, False))
            card.deleted.connect(lambda _: self.refresh_list())
            card.preview_requested.connect(self._open_viewer)
            card.favorite_toggled.connect(lambda _: self.refresh_list() if self.active_filter == "favorite" else None)

            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)

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
            "• استخدم أزرار تسجيل الفيديو 🎥 بالأعلى لتصوير الشاشة أو جزء محدد بصيغة MP4."
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
            self.refresh_list()
        else:
            dlg = ScreenshotViewerDialog(screenshot, toast_callback=self.toast, parent=self)
            dlg.exec()
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
        self.refresh_list()

    def _on_external_recording_saved(self, file_path: str, capture_type: str):
        self.refresh_list()
