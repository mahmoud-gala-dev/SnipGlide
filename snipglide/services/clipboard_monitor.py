import threading
import time
from snipglide.database.clipboard_repo import add_clipboard_entry
from snipglide.utils.helpers import get_clipboard_text
from snipglide.utils.logger import logger

class ClipboardMonitor(threading.Thread):
    def __init__(self, settings_provider):
        super().__init__()
        self.settings_provider = settings_provider
        self.daemon = True
        self.running = False
        self.last_text = ""
        
    def run(self):
        self.running = True
        logger.info("Clipboard monitor service started.")
        while self.running:
            try:
                text = get_clipboard_text()
                if text and text != self.last_text and len(text) < 10000:
                    if len(text.strip()) > 1:
                        add_clipboard_entry(text)
                        self.last_text = text
            except Exception as e:
                logger.error(f"Clipboard monitor error: {e}")
                
            time.sleep(2.0)
            
    def stop(self):
        self.running = False
