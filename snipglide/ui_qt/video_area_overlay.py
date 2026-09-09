from typing import Callable, Optional
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QGuiApplication, QPixmap, QPainter, QColor, QPen, QBrush, QFont, QCursor
)
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QLabel, QFrame

from snipglide.services.screenshot_service import ScreenshotService

class VideoAreaOverlayWidget(QWidget):
    """
    Interactive fullscreen overlay allowing user to select a custom desktop area
    specifically for video recording, with dimension hints and confirm/cancel controls.
    """

    def __init__(self, on_area_selected: Callable[[Optional[QRect]], None], parent=None):
        super().__init__(parent)
        self.on_area_selected = on_area_selected

        # Grab frozen desktop
        self.full_pixmap = ScreenshotService.grab_virtual_desktop()

        self.start_pos: Optional[QPoint] = None
        self.current_pos: Optional[QPoint] = None
        self.is_selecting: bool = False
        self.selected_rect: Optional[QRect] = None

        # Topmost frameless overlay
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        screens = QGuiApplication.screens()
        if screens:
            min_x = min(s.geometry().x() for s in screens)
            min_y = min(s.geometry().y() for s in screens)
            max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
            max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
            self.setGeometry(min_x, min_y, max_x - min_x, max_y - min_y)
        else:
            self.showFullScreen()

        self._setup_floating_controls()

    def _setup_floating_controls(self):
        # Action bar that appears once a rectangle is selected
        self.action_card = QFrame(self)
        self.action_card.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 1.5px solid #3b82f6;
                border-radius: 12px;
                padding: 6px 12px;
            }
        """)
        hlayout = QHBoxLayout(self.action_card)
        hlayout.setContentsMargins(6, 4, 6, 4)
        hlayout.setSpacing(10)

        self.lbl_dims = QLabel("0 × 0 px", self.action_card)
        self.lbl_dims.setStyleSheet("color: #60a5fa; font-weight: bold; font-size: 13px;")
        hlayout.addWidget(self.lbl_dims)

        self.btn_confirm = QPushButton("🎬 بدء تسجيل المساحة", self.action_card)
        self.btn_confirm.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                padding: 6px 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_confirm.clicked.connect(self._confirm_selection)
        hlayout.addWidget(self.btn_confirm)

        self.btn_cancel = QPushButton("❌ إلغاء", self.action_card)
        self.btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #ef4444;
                border: 1px solid #3b4a54;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        self.btn_cancel.clicked.connect(self._cancel_selection)
        hlayout.addWidget(self.btn_cancel)

        self.action_card.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.action_card.hide()
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.is_selecting = True
            self.selected_rect = None
            self.update()
        elif event.button() == Qt.RightButton:
            self._cancel_selection()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            if self.start_pos and self.current_pos:
                rect = QRect(self.start_pos, self.current_pos).normalized()
                if rect.width() >= 60 and rect.height() >= 60:
                    self.selected_rect = rect

                    # Map rect to screen coordinates
                    scale_x = self.full_pixmap.width() / max(1, self.width())
                    scale_y = self.full_pixmap.height() / max(1, self.height())
                    actual_w = int(rect.width() * scale_x)
                    actual_h = int(rect.height() * scale_y)

                    self.lbl_dims.setText(f"📐 {actual_w} × {actual_h} px")

                    # Position action card centered below or above rect
                    card_w = 340
                    card_h = 50
                    card_x = max(10, min(self.width() - card_w - 10, rect.center().x() - card_w // 2))
                    card_y = rect.bottom() + 15
                    if card_y + card_h > self.height() - 15:
                        card_y = max(15, rect.top() - card_h - 15)

                    self.action_card.setGeometry(card_x, card_y, card_w, card_h)
                    self.action_card.show()
                    self.action_card.raise_()
                else:
                    self.selected_rect = None
            self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.selected_rect:
                self._confirm_selection()
        elif event.key() in (Qt.Key_Escape, Qt.Key_Back):
            self._cancel_selection()
        else:
            super().keyPressEvent(event)

    def _confirm_selection(self):
        if not self.selected_rect:
            self._cancel_selection()
            return

        scale_x = self.full_pixmap.width() / max(1, self.width())
        scale_y = self.full_pixmap.height() / max(1, self.height())

        crop_x = int(self.selected_rect.x() * scale_x)
        crop_y = int(self.selected_rect.y() * scale_y)
        crop_w = int(self.selected_rect.width() * scale_x)
        crop_h = int(self.selected_rect.height() * scale_y)

        final_rect = QRect(crop_x, crop_y, crop_w, crop_h)
        self.close()
        if self.on_area_selected:
            self.on_area_selected(final_rect)

    def _cancel_selection(self):
        self.close()
        if self.on_area_selected:
            self.on_area_selected(None)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 1. Frozen desktop background
        if not self.full_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.full_pixmap)

        active_rect = None
        if self.is_selecting and self.start_pos and self.current_pos:
            active_rect = QRect(self.start_pos, self.current_pos).normalized()
        elif self.selected_rect:
            active_rect = self.selected_rect

        if active_rect and active_rect.isValid():
            # Dim outside
            dim_color = QColor(0, 0, 0, 150)
            painter.fillRect(0, 0, self.width(), active_rect.top(), dim_color)
            painter.fillRect(0, active_rect.top(), active_rect.left(), active_rect.height(), dim_color)
            painter.fillRect(active_rect.right() + 1, active_rect.top(), self.width() - active_rect.right() - 1, active_rect.height(), dim_color)
            painter.fillRect(0, active_rect.bottom() + 1, self.width(), self.height() - active_rect.bottom() - 1, dim_color)

            # Red/violet glowing border for recording area
            pen = QPen(QColor("#ef4444"), 2.5)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(active_rect)

            # Corner markers
            corner_pen = QPen(QColor("#f87171"), 4)
            painter.setPen(corner_pen)
            l = 14
            # Top-left
            painter.drawLine(active_rect.left(), active_rect.top(), active_rect.left() + l, active_rect.top())
            painter.drawLine(active_rect.left(), active_rect.top(), active_rect.left(), active_rect.top() + l)
            # Top-right
            painter.drawLine(active_rect.right(), active_rect.top(), active_rect.right() - l, active_rect.top())
            painter.drawLine(active_rect.right(), active_rect.top(), active_rect.right(), active_rect.top() + l)
            # Bottom-left
            painter.drawLine(active_rect.left(), active_rect.bottom(), active_rect.left() + l, active_rect.bottom())
            painter.drawLine(active_rect.left(), active_rect.bottom(), active_rect.left(), active_rect.bottom() - l)
            # Bottom-right
            painter.drawLine(active_rect.right(), active_rect.bottom(), active_rect.right() - l, active_rect.bottom())
            painter.drawLine(active_rect.right(), active_rect.bottom(), active_rect.right(), active_rect.bottom() - l)

            # Badge inside
            badge_text = f"🎥 منطقة تسجيل الفيديو ({active_rect.width()}×{active_rect.height()})"
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(17, 24, 39, 210))
            badge_rect = QRect(active_rect.left() + 10, active_rect.top() + 10, 230, 26)
            painter.drawRoundedRect(badge_rect, 6, 6)
            painter.setPen(QColor("#fca5a5"))
            painter.drawText(badge_rect, Qt.AlignCenter, badge_text)
        else:
            # Dim whole screen slightly and draw instructions hint
            painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

            hint_w = 460
            hint_h = 75
            hint_x = (self.width() - hint_w) // 2
            hint_y = 60
            hint_rect = QRect(hint_x, hint_y, hint_w, hint_h)

            painter.setPen(QPen(QColor("#3b82f6"), 1.5))
            painter.setBrush(QColor(17, 27, 33, 230))
            painter.drawRoundedRect(hint_rect, 14, 14)

            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setPen(QColor("#f0f2f5"))
            painter.drawText(QRect(hint_x, hint_y + 12, hint_w, 24), Qt.AlignCenter, "🎬 حدد المساحة التي تريد تسجيلها فيديو بالماوس")

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(QRect(hint_x, hint_y + 38, hint_w, 20), Qt.AlignCenter, "اضغط مع السحب لتحديد الإطار • اضغط Esc للإلغاء")
