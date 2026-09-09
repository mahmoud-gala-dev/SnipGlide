import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter
from PySide6.QtWidgets import QApplication

from snipglide.core.config import DATA_DIR, SCREENSHOTS_DIR, load_settings
from snipglide.database.screenshot_repo import add_screenshot
from snipglide.ui_qt.snipping_overlay import SnippingOverlayWidget
from snipglide.utils.helpers import ensure_camera_shutter_sound
from snipglide.utils.logger import logger

class ScreenshotService(QObject):
    """
    Central background service handling both full-screen captures
    and interactive region snips with sound, clipboard, and database integration.
    """
    screenshot_saved = Signal(str, str)  # (file_path, capture_type)
    notification_requested = Signal(str, bool)  # (message, is_error)

    def __init__(self, settings_provider: Optional[Callable[[], dict]] = None, parent=None):
        super().__init__(parent)
        self.settings_provider = settings_provider or load_settings
        self.active_overlay: Optional[SnippingOverlayWidget] = None

    def get_save_dir(self) -> Path:
        settings = self.settings_provider()
        dir_str = settings.get("screenshots_dir", "")
        if dir_str:
            p = Path(dir_str)
        else:
            p = SCREENSHOTS_DIR
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            return SCREENSHOTS_DIR

    @staticmethod
    def grab_virtual_desktop() -> QPixmap:
        """Capture all monitors combined into a single continuous high-resolution pixmap."""
        screens = QGuiApplication.screens()
        if not screens:
            return QPixmap()
        if len(screens) == 1:
            return screens[0].grabWindow(0)

        min_x = min(s.geometry().x() for s in screens)
        min_y = min(s.geometry().y() for s in screens)
        max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
        max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
        total_w = max_x - min_x
        total_h = max_y - min_y

        full_pixmap = QPixmap(total_w, total_h)
        full_pixmap.fill(Qt.black)
        painter = QPainter(full_pixmap)
        for s in screens:
            geo = s.geometry()
            screen_pix = s.grabWindow(0)
            painter.drawPixmap(geo.x() - min_x, geo.y() - min_y, geo.width(), geo.height(), screen_pix)
        painter.end()
        return full_pixmap

    def capture_full_screen(self) -> Optional[str]:
        """Trigger full screen capture immediately."""
        try:
            pixmap = self.grab_virtual_desktop()
            if pixmap.isNull():
                self.notification_requested.emit("تعذر التقاط الشاشة!", True)
                return None
            return self._process_and_save_pixmap(pixmap, capture_type="full")
        except Exception as e:
            logger.error(f"Error capturing full screen: {e}")
            self.notification_requested.emit(f"خطأ أثناء حفظ لقطة الشاشة: {e}", True)
            return None

    def start_area_capture(self):
        """Launch the interactive snipping overlay after a slight delay to settle any screen animations."""
        # 150ms delay allows any Windows screen dimming/flash or active menus to settle smoothly
        QTimer.singleShot(150, self._do_start_area_capture)

    def _do_start_area_capture(self):
        """Launch the interactive snipping overlay."""
        try:
            if self.active_overlay:
                try:
                    self.active_overlay.close()
                except Exception:
                    pass
                self.active_overlay = None

            pixmap = self.grab_virtual_desktop()
            if pixmap.isNull():
                self.notification_requested.emit("تعذر التقاط الشاشة لبدء التحديد!", True)
                return

            self.active_overlay = SnippingOverlayWidget(
                full_pixmap=pixmap,
                on_captured=self._on_area_captured
            )
            self.active_overlay.show()
            self.active_overlay.raise_()
            self.active_overlay.activateWindow()
            self.active_overlay.setFocus()
            logger.info("Snipping overlay opened successfully.")
        except Exception as e:
            logger.error(f"Error starting area capture: {e}")
            self.notification_requested.emit(f"خطأ في فتح أداة التحديد: {e}", True)

    def _on_area_captured(self, cropped_pixmap: QPixmap):
        self._process_and_save_pixmap(cropped_pixmap, capture_type="area")

    def _process_and_save_pixmap(self, pixmap: QPixmap, capture_type: str) -> Optional[str]:
        if pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
            return None

        settings = self.settings_provider()
        save_dir = self.get_save_dir()

        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        suffix = "full" if capture_type == "full" else "snip"
        filename = f"screenshot_{timestamp_str}_{suffix}.png"
        file_path = save_dir / filename

        # 1. Save PNG to disk
        saved = pixmap.save(str(file_path), "PNG")
        if not saved:
            logger.error(f"Failed to save screenshot to {file_path}")
            self.notification_requested.emit("تعذر حفظ ملف الصورة على القرص!", True)
            return None

        # 2. Copy image to Clipboard if enabled
        if settings.get("screenshot_copy_to_clipboard", True):
            try:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setPixmap(pixmap)
            except Exception as e:
                logger.warning(f"Could not copy screenshot to clipboard: {e}")

        # 3. Play camera shutter sound if enabled
        if settings.get("screenshot_play_sound", True):
            try:
                import winsound
                sound_file = ensure_camera_shutter_sound()
                if sound_file.exists():
                    winsound.PlaySound(str(sound_file), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:
                pass

        # 4. Save metadata to database
        width = pixmap.width()
        height = pixmap.height()
        file_size = file_path.stat().st_size if file_path.exists() else 0

        add_screenshot(
            file_path=str(file_path),
            filename=filename,
            capture_type=capture_type,
            width=width,
            height=height,
            file_size=file_size,
        )

        logger.info(f"Screenshot saved successfully: {file_path} [{width}x{height}, {file_size} bytes]")

        # 5. Emit signals
        self.screenshot_saved.emit(str(file_path), capture_type)

        type_text = "كامل الشاشة" if capture_type == "full" else "مساحة محددة"
        msg = f"📸 تم حفظ لقطة {type_text} ({width}×{height}) ونسخها إلى الحافظة!"
        self.notification_requested.emit(msg, False)

        return str(file_path)
