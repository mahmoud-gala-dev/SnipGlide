import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from snipglide.core.config import APP_NAME, load_settings, save_settings
from snipglide.database.connection import initialize_database
from snipglide.engine.listener import ExpansionEngine
from snipglide.services.clipboard_monitor import ClipboardMonitor
from snipglide.ui_qt.main_window import MainWindowQt
from snipglide.utils.helpers import download_and_load_arabic_font
from snipglide.utils.logger import logger

class AppCoordinatorQt:
    def __init__(self):
        initialize_database()
        self.settings = load_settings()
        
        # Load Google Arabic Font
        download_and_load_arabic_font("Tajawal")

        # Initialize background engine
        self.engine = ExpansionEngine(
            settings_provider=self.get_current_settings,
        )
        self.engine.start()

        # Initialize clipboard monitor
        self.clipboard_monitor = ClipboardMonitor(
            settings_provider=self.get_current_settings,
        )
        self.clipboard_monitor.start()

    def get_current_settings(self) -> dict:
        if hasattr(self, "window") and self.window and hasattr(self.window, "settings"):
            return self.window.settings
        return self.settings

    def run(self):
        # Enable High DPI scaling
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName(APP_NAME)

        self.window = MainWindowQt(
            engine_toggle_callback=self.toggle_engine,
            snippets_changed_callback=self.notify_snippets_changed,
        )
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        sys.exit(app.exec())

    def toggle_engine(self):
        if self.engine.is_running:
            self.engine.stop()
        else:
            self.engine.start()

    def notify_snippets_changed(self):
        self.engine.reload_snippets()

def run_app():
    coordinator = AppCoordinatorQt()
    coordinator.run()
