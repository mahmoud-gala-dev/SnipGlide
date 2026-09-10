import math
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List

from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import (
    QPixmap, QIcon, QFont, QCursor, QColor, QPainter, QImageReader,
    QPen, QBrush, QImage, QPolygon
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog, QApplication
)

from snipglide.models.screenshot import Screenshot
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


