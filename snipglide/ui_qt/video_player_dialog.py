import os
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import Qt, QUrl, QTime
from PySide6.QtGui import QCursor, QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QMessageBox, QWidget
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from snipglide.models.screenshot import Screenshot
from snipglide.database.screenshot_repo import delete_screenshot, toggle_favorite_screenshot
from snipglide.utils.logger import logger

class VideoPlayerDialog(QDialog):
    """
    Modern in-app media player modal dialog for viewing and interacting
    with recorded screen videos, featuring playback controls, seek slider, and file actions.
    """

    def __init__(self, screenshot: Screenshot, toast_callback: Optional[Callable[[str, bool], None]] = None, parent=None):
        super().__init__(parent)
        self.screenshot = screenshot
        self.toast = toast_callback or (lambda msg, err=False: None)

        self.setWindowTitle(f"مشغل الفيديو - {screenshot.filename}")
        self.resize(880, 620)
        self.setMinimumSize(640, 480)

        self.setStyleSheet("""
            QDialog {
                background-color: #0b141a;
                color: #e9edef;
            }
        """)

        # Initialize Qt Multimedia Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self._setup_ui()
        self._init_playback()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # ── 1. Header Row ──
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel(f"🎬 {self.screenshot.filename}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f0f2f5;")
        title_box.addWidget(title)

        size_mb = self.screenshot.file_size / (1024 * 1024)
        type_str = "تسجيل شاشة كاملة 🖥️" if self.screenshot.capture_type == "video_full" else "تسجيل مساحة مقتطعة ✂️"
        sub = QLabel(f"{type_str} • {self.screenshot.width} × {self.screenshot.height} px • {size_mb:.2f} MB • {self.screenshot.created_at}")
        sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(sub)

        header_row.addLayout(title_box)
        header_row.addStretch()

        # Favorite Star Button
        self.btn_fav = QPushButton("⭐" if self.screenshot.is_favorite else "☆")
        self.btn_fav.setToolTip("إضافة إلى المفضلة" if not self.screenshot.is_favorite else "إزالة من المفضلة")
        self.btn_fav.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_fav.setFixedSize(38, 38)
        self.btn_fav.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #eab308;
                border: 1px solid #2a3942;
                border-radius: 9px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #eab308;
            }
        """)
        self.btn_fav.clicked.connect(self._toggle_favorite)
        header_row.addWidget(self.btn_fav)

        # Open in Windows Default Player
        btn_sys_play = QPushButton("▶ فتح بالمشغل الخارجي")
        btn_sys_play.setToolTip("فتح مقطع الفيديو بالمشغل الافتراضي لنظام ويندوز")
        btn_sys_play.setCursor(QCursor(Qt.PointingHandCursor))
        btn_sys_play.setFixedHeight(38)
        btn_sys_play.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #93c5fd;
                border: 1px solid #2a3942;
                border-radius: 9px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #172554;
                border-color: #3b82f6;
            }
        """)
        btn_sys_play.clicked.connect(self._open_in_external_player)
        header_row.addWidget(btn_sys_play)

        # Open Directory Button
        btn_folder = QPushButton("📁 المجلد")
        btn_folder.setToolTip("فتح مكان حفظ الفيديو في مستكشف ويندوز")
        btn_folder.setCursor(QCursor(Qt.PointingHandCursor))
        btn_folder.setFixedHeight(38)
        btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 9px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #3b82f6;
            }
        """)
        btn_folder.clicked.connect(self._open_folder)
        header_row.addWidget(btn_folder)

        # Delete Button
        btn_del = QPushButton("🗑️ حذف")
        btn_del.setToolTip("حذف هذا التسجيل نهائياً من القرص")
        btn_del.setCursor(QCursor(Qt.PointingHandCursor))
        btn_del.setFixedHeight(38)
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #ef4444;
                border: 1px solid #2a3942;
                border-radius: 9px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #450a0a;
                border-color: #ef4444;
            }
        """)
        btn_del.clicked.connect(self._delete_video)
        header_row.addWidget(btn_del)

        main_layout.addLayout(header_row)

        # ── 2. Video Display Area ──
        video_frame = QFrame()
        video_frame.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 1.5px solid #2a3942;
                border-radius: 12px;
            }
        """)
        vf_layout = QVBoxLayout(video_frame)
        vf_layout.setContentsMargins(4, 4, 4, 4)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.player.setVideoOutput(self.video_widget)
        vf_layout.addWidget(self.video_widget)

        main_layout.addWidget(video_frame, stretch=1)

        # ── 3. Media Controls Bar ──
        controls_card = QFrame()
        controls_card.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 1px solid #2a3942;
                border-radius: 12px;
                padding: 6px 14px;
            }
        """)
        cc_layout = QVBoxLayout(controls_card)
        cc_layout.setContentsMargins(10, 8, 10, 8)
        cc_layout.setSpacing(8)

        # Timeline Slider Row
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        self.lbl_current_time = QLabel("00:00")
        self.lbl_current_time.setStyleSheet("color: #60a5fa; font-family: monospace; font-size: 13px; font-weight: bold;")
        slider_row.addWidget(self.lbl_current_time)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setCursor(QCursor(Qt.PointingHandCursor))
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #2a3942;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #60a5fa;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #93c5fd;
            }
        """)
        self.seek_slider.sliderMoved.connect(self._set_position)
        slider_row.addWidget(self.seek_slider, stretch=1)

        self.lbl_total_time = QLabel("00:00")
        self.lbl_total_time.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 13px;")
        slider_row.addWidget(self.lbl_total_time)

        cc_layout.addLayout(slider_row)

        # Buttons Control Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        # Play / Pause Toggle Button
        self.btn_play = QPushButton("⏸️ إيقاف مؤقت")
        self.btn_play.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_play.setFixedHeight(36)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                padding: 0 18px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_play.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.btn_play)

        # Replay from Start Button
        btn_replay = QPushButton("🔄 إعادة")
        btn_replay.setCursor(QCursor(Qt.PointingHandCursor))
        btn_replay.setFixedHeight(36)
        btn_replay.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #202c33;
                border-color: #3b82f6;
            }
        """)
        btn_replay.clicked.connect(self._replay)
        btn_row.addWidget(btn_replay)

        btn_row.addStretch()

        # Volume / Mute Toggle
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_mute.setFixedSize(36, 36)
        self.btn_mute.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #202c33;
            }
        """)
        self.btn_mute.clicked.connect(self._toggle_mute)
        btn_row.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setCursor(QCursor(Qt.PointingHandCursor))
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #2a3942;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #93c5fd;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
        """)
        self.volume_slider.valueChanged.connect(self._set_volume)
        btn_row.addWidget(self.volume_slider)

        cc_layout.addLayout(btn_row)
        main_layout.addWidget(controls_card)

    def _init_playback(self):
        file_path = self.screenshot.file_path
        if not os.path.exists(file_path):
            self.toast("ملف الفيديو غير موجود على القرص!", True)
            return

        # Connect signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Set source and start playback automatically
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _replay(self):
        self.player.setPosition(0)
        self.player.play()

    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.btn_mute.setText("🔇" if not is_muted else "🔊")

    def _set_volume(self, value: int):
        vol = value / 100.0
        self.audio_output.setVolume(vol)
        if vol == 0:
            self.btn_mute.setText("🔇")
        else:
            self.btn_mute.setText("🔊")

    def _set_position(self, position: int):
        self.player.setPosition(position)

    def _on_position_changed(self, position: int):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self.lbl_current_time.setText(self._format_time(position))

    def _on_duration_changed(self, duration: int):
        self.seek_slider.setRange(0, duration)
        self.lbl_total_time.setText(self._format_time(duration))

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸️ إيقاف مؤقت")
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    border-radius: 8px;
                    padding: 0 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
        else:
            self.btn_play.setText("▶ تشغيل")
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #16a34a;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    border-radius: 8px;
                    padding: 0 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #15803d;
                }
            """)

    @staticmethod
    def _format_time(ms: int) -> str:
        total_seconds = ms // 1000
        seconds = total_seconds % 60
        minutes = (total_seconds // 60) % 60
        hours = total_seconds // 3600
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _toggle_favorite(self):
        new_fav = toggle_favorite_screenshot(self.screenshot.id)
        self.screenshot.is_favorite = new_fav
        self.btn_fav.setText("⭐" if new_fav else "☆")
        msg = "تمت إضافة التسجيل للمفضلة ⭐" if new_fav else "تمت الإزالة من المفضلة"
        self.toast(msg, False)

    def _open_folder(self):
        try:
            fp = Path(self.screenshot.file_path)
            if fp.exists():
                os.system(f'explorer /select,"{fp}"')
            else:
                self.toast("ملف الفيديو غير موجود!", True)
        except Exception as e:
            self.toast(f"تعذر فتح المجلد: {e}", True)

    def _open_in_external_player(self):
        try:
            fp = self.screenshot.file_path
            if os.path.exists(fp):
                os.startfile(fp)
            else:
                self.toast("الملف غير موجود على القرص!", True)
        except Exception as e:
            self.toast(f"تعذر تشغيل الملف خارجياً: {e}", True)

    def _delete_video(self):
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من رغبتك في حذف مقطع الفيديو '{self.screenshot.filename}' نهائياً؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.player.stop()
            self.player.setSource(QUrl())
            delete_screenshot(self.screenshot.id, delete_file=True)
            self.toast("تم حذف مقطع الفيديو بنجاح.", False)
            self.accept()

    def closeEvent(self, event):
        self.player.stop()
        self.player.setSource(QUrl())
        super().closeEvent(event)
