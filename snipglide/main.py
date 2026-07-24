import sys
import threading
from PIL import Image, ImageDraw
import pystray
import customtkinter as ctk

from snipglide.core.config import load_settings, APP_NAME
from snipglide.database.connection import initialize_database
from snipglide.engine.listener import ExpansionEngine
from snipglide.ui.main_window import MainWindow
from snipglide.ui.dialogs.security_dialog import SecurityDialog
from snipglide.services.security import hash_password
from snipglide.services.clipboard_monitor import ClipboardMonitor
from snipglide.utils.logger import logger

class AppCoordinator:
    def __init__(self):
        initialize_database()
        self.settings = load_settings()
        
        # Download and load Google Arabic Font asynchronously
        def load_font_async():
            from snipglide.utils.helpers import download_and_load_arabic_font
            from snipglide.core.config import set_arabic_font_family
            font_name = download_and_load_arabic_font()
            set_arabic_font_family(font_name)
            
        threading.Thread(target=load_font_async, daemon=True).start()
        
        self.engine = ExpansionEngine(
            settings_provider=self.get_current_settings,
            form_prompt_callback=self.show_form_prompt
        )
        
        self.clipboard_monitor = ClipboardMonitor(
            settings_provider=self.get_current_settings
        )
        
        self.window = None
        self.tray_icon = None
        self.engine.start()
        
    def get_current_settings(self) -> dict:
        if self.window:
            return self.window.settings
        return self.settings

    def show_form_prompt(self, snippet, fields: list[str]) -> dict:
        result_holder = {}
        completed_event = threading.Event()
        
        def show():
            from snipglide.ui.dialogs.form_dialog import FormDialog
            dialog = FormDialog(self.window, title=f"Fill Form: {snippet.shortcut}", fields=fields)
            result_holder["result"] = dialog.result
            completed_event.set()
            
        self.window.after(0, show)
        completed_event.wait()
        return result_holder.get("result")

    def run(self):
        self.window = MainWindow(engine_toggle_callback=self.toggle_engine_state)
        self.clipboard_monitor.start()
        
        from pynput.keyboard import GlobalHotKeys
        self.hotkeys = GlobalHotKeys({
            '<ctrl>+<shift>+<space>': lambda: self.window.after(0, self.show_quick_search)
        })
        self.hotkeys.start()
        
        if self.settings.get("master_password_enabled", False) and self.settings.get("lock_on_startup", False):
            self.window.withdraw()
            self._prompt_startup_lock()
        else:
            if self.settings.get("start_minimized", False):
                self.window.withdraw()
            else:
                self.window.deiconify()
                
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._start_tray()
        
        self.window.mainloop()

    def show_quick_search(self):
        if not self.window:
            return
        from snipglide.ui.dialogs.quick_search_dialog import QuickSearchDialog
        dialog = QuickSearchDialog(
            self.window,
            parse_callback=self.engine.parser.parse_variables
        )
        
    def _prompt_startup_lock(self):
        pwd_hash = self.settings.get("master_password_hash", "")
        
        def verify():
            dialog = SecurityDialog(self.window, title="Authentication Required")
            if dialog.result and hash_password(dialog.result) == pwd_hash:
                if self.settings.get("start_minimized", False):
                    self.window.withdraw()
                else:
                    self.window.deiconify()
            else:
                self._quit_app()
                
        self.window.after(100, verify)
        
    def toggle_engine_state(self):
        enabled = self.window.settings.get("enabled", True)
        self.engine.set_suspended(not enabled)
        
    def hide_window(self):
        if self.window:
            self.window.withdraw()
            
    def show_window(self):
        if self.window:
            self.window.after(0, self.window.deiconify)
            self.window.after(20, self.window.lift)
            self.window.after(30, self.window.focus_force)
            
    def _create_tray_image(self):
        image = Image.new("RGB", (64, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=15, fill=(37, 99, 235))
        draw.text((21, 14), "S", fill="white")
        return image
        
    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Open SnipGlide", lambda: self.show_window(), default=True),
            pystray.MenuItem("Pause / Resume", lambda: self._tray_toggle()),
            pystray.MenuItem("Exit", lambda: self._quit_app())
        )
        self.tray_icon = pystray.Icon(
            "SnipGlidePro",
            self._create_tray_image(),
            APP_NAME,
            menu
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        
    def _tray_toggle(self):
        if self.window:
            enabled = self.window.settings.get("enabled", True)
            self.window.settings["enabled"] = not enabled
            self.toggle_engine_state()
            state_str = "Suspended" if enabled else "Running"
            self.window.toast(f"Engine {state_str}")
            
    def _quit_app(self):
        self.engine.stop()
        if hasattr(self, "clipboard_monitor"):
            self.clipboard_monitor.stop()
        if hasattr(self, "hotkeys"):
            self.hotkeys.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.window:
            self.window.destroy()
        sys.exit(0)

def run_app():
    app = AppCoordinator()
    app.run()
