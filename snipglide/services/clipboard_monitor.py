import threading
import time
from snipglide.database.clipboard_repo import add_clipboard_entry
from snipglide.engine.window_tracker import get_active_window_info
from snipglide.utils.helpers import get_clipboard_text
from snipglide.utils.logger import logger

class ClipboardMonitor(threading.Thread):
    def __init__(self, settings_provider):
        super().__init__()
        self.settings_provider = settings_provider
        self.daemon = True
        self.running = False
        self.last_text = ""
        self._stop_event = threading.Event()
        
    def run(self):
        self.running = True
        self._stop_event.clear()
        logger.info("Clipboard monitor service started.")
        while self.running:
            try:
                settings = self.settings_provider()
                enabled = settings.get("clipboard_history_enabled", True)
                max_chars = max(100, min(int(settings.get("clipboard_max_chars", 10000)), 100000))
                interval = max(1.0, min(float(settings.get("clipboard_poll_interval", 3.0)), 60.0))

                if enabled and not self._should_skip_capture(settings):
                    text = get_clipboard_text(max_chars=max_chars)
                    if text and text != self.last_text and len(text) <= max_chars:
                        if len(text.strip()) > 1:
                            add_clipboard_entry(text)
                            self.last_text = text
            except Exception as e:
                logger.error(f"Clipboard monitor error: {e}")
                interval = 5.0
                
            self._stop_event.wait(interval)
            
    def stop(self):
        self.running = False
        self._stop_event.set()

    def _should_skip_capture(self, settings: dict) -> bool:
        if not settings.get("clipboard_skip_private_windows", True):
            return False

        title, process = get_active_window_info()
        lower_title = title.lower()
        if "password" in lower_title or "login" in lower_title or "sign in" in lower_title:
            return True

        blacklist = settings.get("blacklist", "")
        process_lower = process.lower()
        return any(part.strip().lower() in process_lower for part in blacklist.split(",") if part.strip())
