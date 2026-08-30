import os
import time
import re
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame
)

from snipglide.services.audio_service import global_player

class VoiceWaveformWidget(QWidget):
    """WhatsApp-style dynamic audio waveform bars."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setMinimumWidth(160)
        self.progress_pct = 0.0  # 0.0 to 1.0
        self.bar_heights = [6, 12, 18, 10, 24, 16, 28, 22, 14, 26, 18, 12, 8, 15, 20, 10, 14, 6]

    def set_progress(self, pct: float):
        self.progress_pct = max(0.0, min(1.0, pct))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        num_bars = len(self.bar_heights)
        total_w = self.width()
        spacing = 4
        bar_w = max(3, (total_w - (num_bars * spacing)) // num_bars)
        mid_y = self.height() // 2

        for i, h in enumerate(self.bar_heights):
            x = i * (bar_w + spacing) + 4
            bar_pct = (i + 1) / num_bars

            # Played bars are bright teal/emerald, unplayed are dark slate
            if bar_pct <= self.progress_pct:
                color = QColor("#38bdf8")  # Active neon cyan/blue
            else:
                color = QColor("#334155")  # Inactive dark slate

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, mid_y - (h // 2), bar_w, h, 2, 2)

class VoiceNotePlayerWidget(QFrame):
    """Interactive WhatsApp Voice Note Player Card with real microphone audio playback & animated waveform."""
    
    # Internal Qt signal to safely update UI from background audio thread
    progress_signal = Signal(float, float)
    finished_signal = Signal()

    def __init__(self, raw_content: str, parent=None):
        super().__init__(parent)
        self.raw_content = raw_content
        self.audio_file_path = self._extract_audio_file(raw_content)
        self.duration_seconds = self._extract_duration(raw_content)
        self.current_seconds = 0.0
        self.is_playing = False

        self.progress_signal.connect(self._on_progress_received)
        self.finished_signal.connect(self._on_audio_finished)

        self._setup_ui()

    def _extract_audio_file(self, text: str) -> str:
        # Match pattern like [audio:C:\path\to\voice.wav]
        match = re.search(r"\[audio:([^\]]+)\]", text)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_duration(self, text: str) -> float:
        # Match pattern like (00:05) or (5 ثانية) or (5.2s)
        match_min_sec = re.search(r"\((\d{1,2}):(\d{2})\)", text)
        if match_min_sec:
            mins = int(match_min_sec.group(1))
            secs = int(match_min_sec.group(2))
            return max(1.0, float(mins * 60 + secs))

        match_sec = re.search(r"\((\d+(?:\.\d+)?)\s*(?:ثانية|s|sec)\)", text)
        if match_sec:
            return max(1.0, float(match_sec.group(1)))

        return 3.0

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #0b141a;
                border: 1.5px solid #202c33;
                border-radius: 14px;
            }
        """)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)

        # 1. Circular Play/Pause Button
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(42, 42)
        self.play_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
                border: none;
                padding-left: 2px;
            }
            QPushButton:hover {
                background-color: #22c55e;
            }
        """)
        self.play_btn.clicked.connect(self.toggle_play)
        main_layout.addWidget(self.play_btn)

        # 2. Center Waveform & Progress
        center_box = QVBoxLayout()
        center_box.setSpacing(4)

        self.waveform = VoiceWaveformWidget(self)
        center_box.addWidget(self.waveform)

        # Duration label & Mic Tag
        dur_row = QHBoxLayout()
        dur_row.setSpacing(6)

        mins = int(self.duration_seconds) // 60
        secs = int(self.duration_seconds) % 60
        self.time_lbl = QLabel(f"00:00 / {mins:02d}:{secs:02d}")
        self.time_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        dur_row.addWidget(self.time_lbl)
        dur_row.addStretch()

        voice_tag = QLabel("🎙️ تسجيل صوتي")
        voice_tag.setStyleSheet("color: #25D366; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        dur_row.addWidget(voice_tag)

        center_box.addLayout(dur_row)
        main_layout.addLayout(center_box, stretch=1)

        # 3. Avatar Badge
        avatar_lbl = QLabel("🎧")
        avatar_lbl.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        main_layout.addWidget(avatar_lbl)

    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        self.is_playing = True
        self.play_btn.setText("❚❚")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #38bdf8;
                color: #0f172a;
                font-size: 14px;
                font-weight: 800;
                border-radius: 21px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
        """)

        if self.audio_file_path and os.path.exists(self.audio_file_path):
            global_player.play(
                self.audio_file_path,
                progress_callback=lambda el, tot: self.progress_signal.emit(el, tot),
                finished_callback=lambda: self.finished_signal.emit()
            )
        else:
            # Fallback simulated progress timer if no physical wav file attached
            self._sim_timer = QTimer(self)
            self._sim_timer.setInterval(50)
            self.current_seconds = 0.0
            def _sim_tick():
                self.current_seconds += 0.05
                if self.current_seconds >= self.duration_seconds:
                    self._sim_timer.stop()
                    self.finished_signal.emit()
                else:
                    self.progress_signal.emit(self.current_seconds, self.duration_seconds)
            self._sim_timer.timeout.connect(_sim_tick)
            self._sim_timer.start()

    def pause(self):
        self.is_playing = False
        self.play_btn.setText("▶")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
                border: none;
                padding-left: 2px;
            }
            QPushButton:hover {
                background-color: #22c55e;
            }
        """)
        global_player.stop()
        if hasattr(self, "_sim_timer") and self._sim_timer:
            self._sim_timer.stop()

    def _on_progress_received(self, elapsed: float, total: float):
        if total <= 0:
            return
        pct = min(1.0, elapsed / total)
        self.waveform.set_progress(pct)

        cur_m = int(elapsed) // 60
        cur_s = int(elapsed) % 60
        tot_m = int(total) // 60
        tot_s = int(total) % 60
        self.time_lbl.setText(f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}")

    def _on_audio_finished(self):
        self.is_playing = False
        self.play_btn.setText("▶")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
                border: none;
                padding-left: 2px;
            }
            QPushButton:hover {
                background-color: #22c55e;
            }
        """)
        self.waveform.set_progress(0.0)
        mins = int(self.duration_seconds) // 60
        secs = int(self.duration_seconds) % 60
        self.time_lbl.setText(f"00:00 / {mins:02d}:{secs:02d}")
