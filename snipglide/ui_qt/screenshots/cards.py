import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List

from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect, QPoint, QMimeData
from PySide6.QtGui import (
    QPixmap, QIcon, QFont, QCursor, QColor, QPainter, QImageReader,
    QPen, QBrush, QImage, QDrag
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QMenu, QApplication
)

from snipglide.database.screenshot_repo import (
    delete_screenshot, toggle_favorite_screenshot, move_screenshot_to_folder
)
from snipglide.models.screenshot import Screenshot
from snipglide.ui_qt.screenshots.viewer_dialog import ScreenshotViewerDialog
from snipglide.ui_qt.video_player_dialog import VideoPlayerDialog
from snipglide.utils.logger import logger

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


