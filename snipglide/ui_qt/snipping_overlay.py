from typing import Callable, Optional
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QGuiApplication, QPixmap, QPainter, QColor, QPen, QBrush, QFont, QCursor
)
from PySide6.QtWidgets import QWidget

class SnippingOverlayWidget(QWidget):
    """
    High-performance interactive fullscreen overlay for selecting and snipping
    a custom rectangular portion of the desktop.
    """

    def __init__(self, full_pixmap: QPixmap, on_captured: Callable[[QPixmap], None], parent=None):
        super().__init__(parent)
        self.full_pixmap = full_pixmap
        self.on_captured = on_captured

        self.start_pos: Optional[QPoint] = None
        self.current_pos: Optional[QPoint] = None
        self.is_selecting: bool = False

        # Configure window to be seamless, topmost, borderless
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Set geometry to cover all connected screens (virtual desktop)
        screens = QGuiApplication.screens()
        if screens:
            min_x = min(s.geometry().x() for s in screens)
            min_y = min(s.geometry().y() for s in screens)
            max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
            max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
            self.setGeometry(min_x, min_y, max_x - min_x, max_y - min_y)
        else:
            self.showFullScreen()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            if self.start_pos and self.current_pos:
                rect = QRect(self.start_pos, self.current_pos).normalized()
                if rect.width() >= 10 and rect.height() >= 10:
                    scale_x = self.full_pixmap.width() / max(1, self.width())
                    scale_y = self.full_pixmap.height() / max(1, self.height())

                    crop_x = int(rect.x() * scale_x)
                    crop_y = int(rect.y() * scale_y)
                    crop_w = int(rect.width() * scale_x)
                    crop_h = int(rect.height() * scale_y)

                    cropped = self.full_pixmap.copy(crop_x, crop_y, crop_w, crop_h)
                    self.close()
                    if self.on_captured:
                        self.on_captured(cropped)
                    return

            self.close()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Back):
            self.close()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 1. Draw frozen desktop
        painter.drawPixmap(self.rect(), self.full_pixmap)

        scale_x = self.full_pixmap.width() / max(1, self.width())
        scale_y = self.full_pixmap.height() / max(1, self.height())

        # 2. If selecting, clear cutout and dim surrounding area
        if self.is_selecting and self.start_pos and self.current_pos:
            rect = QRect(self.start_pos, self.current_pos).normalized()

            # Dim top, bottom, left, right around rect
            dim_color = QColor(0, 0, 0, 140)
            painter.fillRect(0, 0, self.width(), rect.top(), dim_color)
            painter.fillRect(0, rect.top(), rect.left(), rect.height(), dim_color)
            painter.fillRect(rect.right() + 1, rect.top(), self.width() - rect.right() - 1, rect.height(), dim_color)
            painter.fillRect(0, rect.bottom() + 1, self.width(), self.height() - rect.bottom() - 1, dim_color)

            # Draw glowing selection border
            pen = QPen(QColor("#3b82f6"), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            # Draw corner handles
            corner_pen = QPen(QColor("#60a5fa"), 3)
            painter.setPen(corner_pen)
            h_len = 10
            # Top-left
            painter.drawLine(rect.left(), rect.top(), rect.left() + h_len, rect.top())
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + h_len)
            # Top-right
            painter.drawLine(rect.right() - h_len, rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + h_len)
            # Bottom-left
            painter.drawLine(rect.left(), rect.bottom(), rect.left() + h_len, rect.bottom())
            painter.drawLine(rect.left(), rect.bottom() - h_len, rect.left(), rect.bottom())
            # Bottom-right
            painter.drawLine(rect.right() - h_len, rect.bottom(), rect.right(), rect.bottom())
            painter.drawLine(rect.right(), rect.bottom() - h_len, rect.right(), rect.bottom())

            # Dimension badge
            phys_w = int(rect.width() * scale_x)
            phys_h = int(rect.height() * scale_y)
            dim_text = f"{phys_w} × {phys_h} px"

            badge_font = QFont("Segoe UI", 10, QFont.Bold)
            painter.setFont(badge_font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(dim_text) + 16
            th = fm.height() + 8

            # Position badge below selection or above if near screen bottom
            bx = rect.left() + 6
            by = rect.bottom() + 10
            if by + th > self.height():
                by = rect.top() - th - 10

            painter.setPen(QPen(QColor("#3b82f6"), 1))
            painter.setBrush(QBrush(QColor("#0f172a")))
            painter.drawRoundedRect(bx, by, tw, th, 6, 6)

            painter.setPen(QColor("#60a5fa"))
            painter.drawText(bx + 8, by + fm.ascent() + 4, dim_text)

        else:
            # Whole screen dimmed
            painter.fillRect(self.rect(), QColor(0, 0, 0, 130))

            # Top instructions banner
            tip_text = "✂️ انقر واسحب بالفأرة لتحديد جزء من الشاشة • اضغط Esc أو زر الفأرة الأيمن للإلغاء"
            tip_font = QFont("Tajawal", 13, QFont.Bold)
            painter.setFont(tip_font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(tip_text) + 36
            th = fm.height() + 18

            bx = (self.width() - tw) // 2
            by = 40

            # Banner background
            painter.setPen(QPen(QColor("#3b82f6"), 1.5))
            painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
            painter.drawRoundedRect(bx, by, tw, th, 12, 12)

            painter.setPen(QColor("#f8fafc"))
            painter.drawText(bx + 18, by + fm.ascent() + 9, tip_text)

        painter.end()
