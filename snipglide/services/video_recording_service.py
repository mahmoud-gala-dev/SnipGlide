import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Qt, QRect, QPoint, QThread, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap, QImage, QPainter, QCursor, QColor, QPen, QBrush

from snipglide.core.config import RECORDINGS_DIR, load_settings
from snipglide.database.screenshot_repo import add_screenshot
from snipglide.utils.logger import logger

class VideoRecorderWorker(QThread):
    """
    Dedicated high-performance background thread that continuously grabs screen frames,
    renders cursor highlight if requested, and streams them into an MP4 container.
    """
    tick_signal = Signal(float)  # Elapsed seconds
    finished_signal = Signal(str, float, int, int, str)  # (file_path, duration, width, height, thumb_path)
    error_signal = Signal(str)

    def __init__(
        self,
        output_file: Path,
        thumb_file: Path,
        region: Optional[QRect] = None,
        fps: int = 24,
        show_cursor: bool = True,
        record_audio: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.output_file = output_file
        self.thumb_file = thumb_file
        self.region = region
        self.fps = max(10, min(60, fps))
        self.show_cursor = show_cursor
        self.record_audio = record_audio
        if self.record_audio:
            logger.info("Video audio capture is reserved for v1.1. Capturing HD screen video.")

        self._running = True
        self._paused = False
        self._cancelled = False
        self._lock = threading.Lock()

        self._start_time = 0.0
        self._elapsed_time = 0.0
        self._last_tick_emit = 0.0

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def toggle_pause(self) -> bool:
        with self._lock:
            self._paused = not self._paused
            return self._paused

    def stop(self):
        with self._lock:
            self._running = False

    def cancel(self):
        with self._lock:
            self._cancelled = True
            self._running = False

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def is_recording(self) -> bool:
        with self._lock:
            return self._running

    def run(self):
        writer = None
        width = 0
        height = 0
        frame_interval = 1.0 / self.fps
        first_frame = True
        frames_recorded = 0

        logger.info(f"Starting video recording thread: FPS={self.fps}, Region={self.region}, File={self.output_file}")

        try:
            import mss

            self._start_time = time.time()
            self._last_tick_emit = self._start_time

            with mss.mss() as sct:
                # Determine monitor capture box
                if self.region and self.region.isValid():
                    capture_box = {
                        "left": int(self.region.x()),
                        "top": int(self.region.y()),
                        "width": int(self.region.width()),
                        "height": int(self.region.height()),
                    }
                else:
                    # Primary screen monitor
                    capture_box = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]

                while True:
                    with self._lock:
                        if not self._running:
                            break
                        paused = self._paused
                        cancelled = self._cancelled

                    if cancelled:
                        break

                    loop_start = time.time()

                    if not paused:
                        # 1. Thread-safe screen grab via mss (direct OS memory buffer)
                        sct_img = sct.grab(capture_box)
                        frame_raw = np.array(sct_img)  # BGRA 4-channel array
                        frame_arr = frame_raw[:, :, :3].copy()  # Convert to BGR for OpenCV

                        h, w = frame_arr.shape[:2]

                        # OpenCV requires dimensions to be divisible by 2
                        if w % 2 != 0:
                            w -= 1
                        if h % 2 != 0:
                            h -= 1

                        if w <= 0 or h <= 0:
                            time.sleep(0.02)
                            continue

                        if frame_arr.shape[1] != w or frame_arr.shape[0] != h:
                            frame_arr = frame_arr[:h, :w]

                        # 2. Draw smooth cursor highlight if enabled (using thread-safe cv2 operations)
                        if self.show_cursor:
                            try:
                                cur_pos = QCursor.pos()
                                rel_x = cur_pos.x() - capture_box["left"]
                                rel_y = cur_pos.y() - capture_box["top"]

                                if 0 <= rel_x < w and 0 <= rel_y < h:
                                    # Amber translucent outer glow (BGR: 11, 158, 245)
                                    overlay = frame_arr.copy()
                                    cv2.circle(overlay, (rel_x, rel_y), 18, (11, 158, 245), -1)
                                    cv2.addWeighted(overlay, 0.35, frame_arr, 0.65, 0, frame_arr)

                                    # Crisp inner pointer dot (BGR red: 68, 68, 239) with white border
                                    cv2.circle(frame_arr, (rel_x, rel_y), 6, (255, 255, 255), 2)
                                    cv2.circle(frame_arr, (rel_x, rel_y), 5, (68, 68, 239), -1)
                            except Exception as e:
                                logger.debug(f"Cursor rendering skipped: {e}")

                        # 3. Initialize VideoWriter and save thumbnail on first frame
                        if first_frame:
                            width = w
                            height = h

                            try:
                                cv2.imwrite(str(self.thumb_file), frame_arr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            except Exception as e:
                                logger.warning(f"Could not save video thumbnail: {e}")

                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            writer = cv2.VideoWriter(
                                str(self.output_file),
                                fourcc,
                                float(self.fps),
                                (width, height)
                            )

                            if not writer.isOpened():
                                logger.warning("mp4v codec failed, trying XVID fallback...")
                                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                                writer = cv2.VideoWriter(
                                    str(self.output_file),
                                    fourcc,
                                    float(self.fps),
                                    (width, height)
                                )

                            if not writer.isOpened():
                                self.error_signal.emit("تعذر تهيئة مشفر الفيديو (VideoWriter). تأكد من توفر مشغلات الوسائط.")
                                return

                            first_frame = False

                        # 4. Write frame to MP4 stream
                        writer.write(frame_arr)
                        frames_recorded += 1

                        self._elapsed_time += frame_interval

                        now = time.time()
                        if now - self._last_tick_emit >= 0.4:
                            self.tick_signal.emit(self._elapsed_time)
                            self._last_tick_emit = now

                    elapsed_loop = time.time() - loop_start
                    sleep_needed = max(0.002, frame_interval - elapsed_loop)
                    time.sleep(sleep_needed)

        except Exception as e:
            logger.error(f"Error during video recording: {e}", exc_info=True)
            self.error_signal.emit(f"خطأ أثناء تسجيل الفيديو: {e}")
        finally:
            if writer:
                writer.release()
                logger.info(f"VideoWriter released. Total frames: {frames_recorded}")

            with self._lock:
                cancelled = self._cancelled

            if cancelled:
                try:
                    if self.output_file.exists():
                        self.output_file.unlink()
                    if self.thumb_file.exists():
                        self.thumb_file.unlink()
                except Exception:
                    pass
                logger.info("Video recording was cancelled and cleaned up.")
            else:
                if self.output_file.exists() and self.output_file.stat().st_size > 0:
                    final_dur = max(0.1, self._elapsed_time)
                    self.finished_signal.emit(
                        str(self.output_file),
                        final_dur,
                        width,
                        height,
                        str(self.thumb_file) if self.thumb_file.exists() else ""
                    )
                else:
                    self.error_signal.emit("لم يتم تسجيل أي إطارات صالحة.")

class ScreenRecordingService(QObject):
    """
    Central manager for screen video recording (full screen or cropped area).
    Coordinates background worker thread, UI notifications, floating widget, and database records.
    """
    recording_started = Signal(str, QRect)  # (capture_type: 'video_full' or 'video_area', region)
    recording_tick = Signal(float)         # Elapsed seconds
    recording_paused = Signal(bool)        # is_paused
    recording_saved = Signal(str, str)     # (file_path, capture_type)
    recording_cancelled = Signal()
    notification_requested = Signal(str, bool)

    def __init__(self, settings_provider: Optional[Callable[[], dict]] = None, parent=None):
        super().__init__(parent)
        self.settings_provider = settings_provider or load_settings
        self.worker: Optional[VideoRecorderWorker] = None
        self.current_capture_type = "video_full"
        self.current_region: Optional[QRect] = None
        self._active_overlay = None

    def get_save_dir(self) -> Path:
        settings = self.settings_provider()
        dir_str = settings.get("recordings_dir", "")
        if dir_str:
            p = Path(dir_str)
        else:
            p = RECORDINGS_DIR
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            return RECORDINGS_DIR

    def is_recording(self) -> bool:
        return self.worker is not None and self.worker.isRunning() and self.worker.is_recording()

    def is_paused(self) -> bool:
        return self.worker is not None and self.worker.is_paused()

    def start_full_screen_recording(self):
        """Start full screen recording immediately."""
        if self.is_recording():
            self.notification_requested.emit("يوجد تسجيل فيديو قيد التشغيل بالفعل!", True)
            return
        self._start_recording(region=None, capture_type="video_full")

    def start_area_recording(self):
        """Launch interactive area selector overlay to choose region for video recording."""
        if self.is_recording():
            self.notification_requested.emit("يوجد تسجيل فيديو قيد التشغيل بالفعل!", True)
            return

        try:
            self._launch_area_selector()
        except Exception as e:
            logger.error(f"Error launching area recording selector: {e}")
            self.notification_requested.emit(f"خطأ في فتح أداة تحديد المساحة: {e}", True)

    def _launch_area_selector(self):
        from snipglide.ui_qt.video_area_overlay import VideoAreaOverlayWidget
        if self._active_overlay:
            try:
                self._active_overlay.close()
            except Exception:
                pass
            self._active_overlay = None

        self._active_overlay = VideoAreaOverlayWidget(on_area_selected=self._on_area_selected)
        self._active_overlay.show()
        self._active_overlay.raise_()
        self._active_overlay.activateWindow()

    def _on_area_selected(self, rect: Optional[QRect]):
        self._active_overlay = None
        if rect and rect.width() >= 60 and rect.height() >= 60:
            self._start_recording(region=rect, capture_type="video_area")
        elif rect is not None:
            self.notification_requested.emit("المساحة المحددة صغيرة جداً لتسجيل الفيديو (أقل من 60×60).", True)
        else:
            self.notification_requested.emit("تم إلغاء تحديد مساحة الفيديو.", False)

    def _start_recording(self, region: Optional[QRect], capture_type: str):
        settings = self.settings_provider()
        save_dir = self.get_save_dir()

        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        suffix = "full" if capture_type == "video_full" else "area"
        video_filename = f"recording_{timestamp_str}_{suffix}.mp4"
        thumb_filename = f"recording_{timestamp_str}_{suffix}_thumb.jpg"

        video_path = save_dir / video_filename
        thumb_path = save_dir / thumb_filename

        fps = int(settings.get("video_fps", 24))
        show_cursor = bool(settings.get("video_show_cursor", True))
        record_audio = bool(settings.get("video_record_audio", False))

        self.current_capture_type = capture_type
        self.current_region = region

        self.worker = VideoRecorderWorker(
            output_file=video_path,
            thumb_file=thumb_path,
            region=region,
            fps=fps,
            show_cursor=show_cursor,
            record_audio=record_audio
        )

        self.worker.tick_signal.connect(self.recording_tick.emit)
        self.worker.finished_signal.connect(self._on_recording_finished)
        self.worker.error_signal.connect(self._on_recording_error)

        self.worker.start()

        type_str = "شاشة كاملة" if capture_type == "video_full" else "مساحة محددة"
        logger.info(f"Screen video recording started: {type_str}")
        self.recording_started.emit(capture_type, region or QRect())
        self.notification_requested.emit(f"🔴 بدأ تسجيل الفيديو ({type_str})!", False)

    def pause_recording(self):
        if self.worker and self.worker.is_recording():
            self.worker.pause()
            self.recording_paused.emit(True)
            self.notification_requested.emit("⏸️ تم إيقاف تسجيل الفيديو مؤقتاً.", False)

    def resume_recording(self):
        if self.worker and self.worker.is_recording():
            self.worker.resume()
            self.recording_paused.emit(False)
            self.notification_requested.emit("▶️ تم استئناف تسجيل الفيديو.", False)

    def toggle_pause(self):
        if self.worker and self.worker.is_recording():
            is_paused = self.worker.toggle_pause()
            self.recording_paused.emit(is_paused)
            msg = "⏸️ تم إيقاف التسجيل مؤقتاً." if is_paused else "▶️ تم استئناف التسجيل."
            self.notification_requested.emit(msg, False)

    def stop_recording(self):
        """Stop and save the current recording."""
        if self.worker and self.worker.is_recording():
            self.worker.stop()
            logger.info("Stop recording requested by user.")

    def cancel_recording(self):
        """Cancel recording and discard any written files."""
        if self.worker and self.worker.is_recording():
            self.worker.cancel()
            self.recording_cancelled.emit()
            self.notification_requested.emit("❌ تم إلغاء تسجيل الفيديو وحذف الملف المؤقت.", False)

    def _on_recording_finished(self, file_path: str, duration: float, width: int, height: int, thumb_path: str):
        try:
            fp = Path(file_path)
            file_size = fp.stat().st_size if fp.exists() else 0
            filename = fp.name

            # Add to database
            add_screenshot(
                file_path=file_path,
                filename=filename,
                capture_type=self.current_capture_type,
                width=width,
                height=height,
                file_size=file_size,
                duration=duration,
                thumbnail_path=thumb_path,
                note=""
            )

            mins = int(duration) // 60
            secs = int(duration) % 60
            dur_str = f"{mins:02d}:{secs:02d}"

            logger.info(f"Recording saved successfully: {file_path} [{dur_str}, {width}x{height}, {file_size} bytes]")
            self.recording_saved.emit(file_path, self.current_capture_type)

            type_name = "الشاشة كاملة" if self.current_capture_type == "video_full" else "المساحة المحددة"
            self.notification_requested.emit(f"🎬 تم حفظ تسجيل {type_name} ({dur_str}) بنجاح!", False)
        except Exception as e:
            logger.error(f"Error handling finished recording: {e}", exc_info=True)
            self.notification_requested.emit(f"خطأ أثناء حفظ تسجيل الفيديو: {e}", True)
        finally:
            self.worker = None

    def _on_recording_error(self, err: str):
        logger.error(f"Recording error: {err}")
        self.notification_requested.emit(err, True)
        self.worker = None
