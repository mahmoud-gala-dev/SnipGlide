import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from snipglide.core.config import APP_NAME, load_settings, save_settings
from snipglide.database.connection import initialize_database
from snipglide.engine.listener import ExpansionEngine
from snipglide.services.clipboard_monitor import ClipboardMonitor
from snipglide.ui_qt.main_window import MainWindowQt
from snipglide.utils.helpers import download_and_load_arabic_font
from snipglide.utils.logger import logger

class AppCoordinatorQt:
    def __init__(self, app: QApplication):
        self.app = app
        initialize_database()
        self.settings = load_settings()
        self.window = None

        # Load Google Arabic Font and set globally
        self.font_family = download_and_load_arabic_font("Tajawal")
        self.app.setFont(QFont(self.font_family, 12))

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
        if self.window and hasattr(self.window, "settings"):
            return self.window.settings
        return self.settings

    def run(self):
        self.window = MainWindowQt(
            engine_toggle_callback=self.toggle_engine,
            snippets_changed_callback=self.notify_snippets_changed,
            font_family=self.font_family,
        )
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        exit_code = self.app.exec()
        if self.engine:
            self.engine.stop()
        if self.clipboard_monitor:
            self.clipboard_monitor.stop()
        sys.exit(exit_code)

    def toggle_engine(self):
        if self.engine.is_running:
            self.engine.stop()
        else:
            self.engine.start()

    def notify_snippets_changed(self):
        self.engine.reload_snippets()

def run_app():
    import ctypes
    from pathlib import Path
    from PySide6.QtGui import QIcon

    try:
        myappid = "snipglide.text.expander.pro.v2"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    icon_ico = Path(__file__).resolve().parent / "assets" / "icon.ico"
    icon_png = Path(__file__).resolve().parent / "assets" / "icon.png"
    if icon_ico.exists():
        app.setWindowIcon(QIcon(str(icon_ico)))
    elif icon_png.exists():
        app.setWindowIcon(QIcon(str(icon_png)))

    coordinator = AppCoordinatorQt(app)
    coordinator.run()
