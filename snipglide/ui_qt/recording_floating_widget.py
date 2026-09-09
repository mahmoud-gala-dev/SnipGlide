from typing import Optional
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QFrame

from snipglide.services.video_recording_service import ScreenRecordingService

class AreaBorderOverlayWidget(QWidget):
    """
    Non-clickable transparent frame that draws a bright border around the area
    currently being recorded, reminding the user where the capture bounds are.
    """
    def __init__(self, region: QRect, parent=None):
        super().__init__(parent)
        self.region = region

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.TransparentForMouseEvents |  # Clicks pass through to applications underneath!
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Expand geometry slightly to fit border lines
        margin = 3
        self.setGeometry(
            region.x() - margin,
            region.y() - margin,
            region.width() + margin * 2,
            region.height() + margin * 2
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#ef4444"), 2.5, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(2, 2, self.width() - 4, self.height() - 4)

class ScreenRecorderFloatingWidget(QWidget):
    """
    Sleek, draggable floating toolbar that stays on top during screen video recording,
    displaying elapsed time, blinking REC indicator, pause/resume, and stop/cancel actions.
    """

    def __init__(self, recording_service: ScreenRecordingService, parent=None):
        super().__init__(parent)
        self.service = recording_service
        self._drag_pos: Optional[QPoint] = None

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._toggle_blink)

        self.border_overlay: Optional[AreaBorderOverlayWidget] = None

        self._setup_ui()
        self._connect_service()

    def _setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # Main dark pill container
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #0b141a;
                border: 1.5px solid #ef4444;
                border-radius: 22px;
                padding: 4px 12px;
            }
        """)
        hlayout = QHBoxLayout(self.card)
        hlayout.setContentsMargins(8, 6, 8, 6)
        hlayout.setSpacing(12)

        # Drag handle indicator
        lbl_drag = QLabel("⠿", self.card)
        lbl_drag.setToolTip("اسحب لتحريك شريط التسجيل")
        lbl_drag.setCursor(QCursor(Qt.SizeAllCursor))
        lbl_drag.setStyleSheet("color: #64748b; font-size: 16px; font-weight: bold; border: none;")
        hlayout.addWidget(lbl_drag)

        # Blinking REC dot + text
        self.lbl_rec = QLabel("🔴 REC", self.card)
        self.lbl_rec.setStyleSheet("color: #ef4444; font-weight: 800; font-size: 12px; border: none;")
        hlayout.addWidget(self.lbl_rec)

        # Time counter
        self.lbl_time = QLabel("00:00", self.card)
        self.lbl_time.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 15px; font-family: monospace; border: none;")
        hlayout.addWidget(self.lbl_time)

        # Divider
        div = QLabel("|", self.card)
        div.setStyleSheet("color: #334155; font-size: 16px; border: none;")
        hlayout.addWidget(div)

        # Pause / Resume Button
        self.btn_pause = QPushButton("⏸️", self.card)
        self.btn_pause.setToolTip("إيقاف مؤقت / استئناف (Pause)")
        self.btn_pause.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_pause.setFixedSize(32, 32)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #60a5fa;
            }
        """)
        self.btn_pause.clicked.connect(self._toggle_pause)
        hlayout.addWidget(self.btn_pause)

        # Stop and Save Button
        self.btn_stop = QPushButton("⏹️ إنهاء وحفظ", self.card)
        self.btn_stop.setToolTip("إيقاف التسجيل وحفظ الفيديو في المعرض")
        self.btn_stop.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_stop.setFixedHeight(32)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 16px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.btn_stop.clicked.connect(self._stop_recording)
        hlayout.addWidget(self.btn_stop)

        # Cancel Button
        self.btn_cancel = QPushButton("❌", self.card)
        self.btn_cancel.setToolTip("إلغاء التسجيل وحذف الملف")
        self.btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_cancel.setFixedSize(32, 32)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.btn_cancel.clicked.connect(self._cancel_recording)
        hlayout.addWidget(self.btn_cancel)

        root_layout.addWidget(self.card)

        # Default position: bottom-center of primary screen
        self._position_on_screen()

    def _position_on_screen(self):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            w = 360
            h = 56
            self.setGeometry(
                geom.x() + (geom.width() - w) // 2,
                geom.y() + geom.height() - h - 60,
                w,
                h
            )

    def _connect_service(self):
        self.service.recording_started.connect(self._on_started)
        self.service.recording_tick.connect(self._on_tick)
        self.service.recording_paused.connect(self._on_paused)
        self.service.recording_saved.connect(self._on_finished)
        self.service.recording_cancelled.connect(self._on_finished)

    def _on_started(self, capture_type: str, region: QRect):
        self.lbl_time.setText("00:00")
        self.btn_pause.setText("⏸️")
        self.btn_pause.setToolTip("إيقاف مؤقت")
        self.card.setStyleSheet("""
            QFrame {
                background-color: #0b141a;
                border: 1.5px solid #ef4444;
                border-radius: 22px;
                padding: 4px 12px;
            }
        """)

        # If region recording, show non-intrusive border around region
        if capture_type == "video_area" and region and region.isValid():
            self._close_border_overlay()
            self.border_overlay = AreaBorderOverlayWidget(region)
            self.border_overlay.show()

        self._blink_timer.start()
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tick(self, elapsed_seconds: float):
        total_sec = int(elapsed_seconds)
        mins = total_sec // 60
        secs = total_sec % 60
        self.lbl_time.setText(f"{mins:02d}:{secs:02d}")

    def _on_paused(self, is_paused: bool):
        if is_paused:
            self.btn_pause.setText("▶️")
            self.btn_pause.setToolTip("استئناف التسجيل")
            self.lbl_rec.setText("⏸️ PAUSE")
            self.lbl_rec.setStyleSheet("color: #f59e0b; font-weight: 800; font-size: 12px; border: none;")
            self.card.setStyleSheet("""
                QFrame {
                    background-color: #0b141a;
                    border: 1.5px solid #f59e0b;
                    border-radius: 22px;
                    padding: 4px 12px;
                }
            """)
        else:
            self.btn_pause.setText("⏸️")
            self.btn_pause.setToolTip("إيقاف مؤقت")
            self.lbl_rec.setText("🔴 REC")
            self.lbl_rec.setStyleSheet("color: #ef4444; font-weight: 800; font-size: 12px; border: none;")
            self.card.setStyleSheet("""
                QFrame {
                    background-color: #0b141a;
                    border: 1.5px solid #ef4444;
                    border-radius: 22px;
                    padding: 4px 12px;
                }
            """)

    def _on_finished(self, *args):
        self._blink_timer.stop()
        self._close_border_overlay()
        self.hide()

    def _close_border_overlay(self):
        if self.border_overlay:
            try:
                self.border_overlay.close()
            except Exception:
                pass
            self.border_overlay = None

    def _toggle_blink(self):
        if not self.service.is_paused():
            self._blink_state = not self._blink_state
            if self._blink_state:
                self.lbl_rec.setText("🔴 REC")
            else:
                self.lbl_rec.setText("⭕ REC")

    def _toggle_pause(self):
        self.service.toggle_pause()

    def _stop_recording(self):
        self.service.stop_recording()

    def _cancel_recording(self):
        self.service.cancel_recording()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
