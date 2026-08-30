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
from snipglide.services.security import verify_password
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
        
        from snipglide.services.auto_backup import start_auto_backup_service
        start_auto_backup_service()
        
        self.engine = ExpansionEngine(
            settings_provider=self.get_current_settings,
            form_prompt_callback=self.show_form_prompt
        )
        
        self.clipboard_monitor = ClipboardMonitor(
            settings_provider=self.get_current_settings
        )
        
        self.window = None
        self.tray_icon = None
        self.hotkeys = None
        self._hotkey_refresh_job = None
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
        self.window = MainWindow(
            engine_toggle_callback=self.toggle_engine_state,
            snippets_changed_callback=self._on_snippets_changed,
        )
        self.clipboard_monitor.start()

        self._start_hotkeys()
        
        if self.settings.get("master_password_enabled", False) and self.settings.get("lock_on_startup", False):
            self.window.withdraw()
            self._prompt_startup_lock()
        else:
            if self.settings.get("start_minimized", False):
                self.window.withdraw()
            else:
                self.window.deiconify()
                self.window.lift()
                self.window.focus_force()
                
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._start_tray()
        
        self.window.mainloop()

    def _build_hotkey_map(self):
        hotkey_map = {
            '<ctrl>+<shift>+<space>': lambda: self.window.after(0, self.show_quick_search),
            '<ctrl>+<alt>+<shift>+s': lambda: self.window.after(0, self.toggle_window_visibility),
            '<ctrl>+<print_screen>': lambda: self.window.after(0, self.show_window),
        }
        hotkey_map.update(self._load_snippet_hotkeys())
        return hotkey_map

    def _start_hotkeys(self):
        from pynput.keyboard import GlobalHotKeys

        self.hotkeys = GlobalHotKeys(self._build_hotkey_map())
        self.hotkeys.start()

    def _restart_hotkeys(self):
        try:
            if self.hotkeys:
                self.hotkeys.stop()
        except Exception as e:
            logger.error(f"Failed to stop hotkeys: {e}")
        self._start_hotkeys()

    def _on_snippets_changed(self):
        self.engine.invalidate_cache()
        if self.window:
            if self._hotkey_refresh_job:
                self.window.after_cancel(self._hotkey_refresh_job)
            self._hotkey_refresh_job = self.window.after(250, self._refresh_hotkeys_after_change)

    def _refresh_hotkeys_after_change(self):
        self._hotkey_refresh_job = None
        self._restart_hotkeys()

    def show_quick_search(self):
        if not self.window:
            return
        from snipglide.ui.dialogs.quick_search_dialog import QuickSearchDialog
        from snipglide.engine.parser import parse_variables
        dialog = QuickSearchDialog(
            self.window,
            parse_callback=parse_variables
        )
        
    def _prompt_startup_lock(self):
        pwd_hash = self.settings.get("master_password_hash", "")
        
        def verify():
            dialog = SecurityDialog(self.window, title="Authentication Required")
            if dialog.result and verify_password(dialog.result, pwd_hash):
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
            self.window.after(10, lambda: self.window.state("normal"))
            self.window.after(20, self.window.lift)
            self.window.after(30, self.window.focus_force)

    def toggle_window_visibility(self):
        """Toggle between showing and hiding the main window (Ctrl+Alt+Shift+S)."""
        if self.window:
            if self.window.state() == "withdrawn":
                self.show_window()
            else:
                self.hide_window()

    def _load_snippet_hotkeys(self):
        mappings = {}
        try:
            from pynput.keyboard import HotKey
            from snipglide.database.snippet_repo import get_all_snippets
            for snippet in get_all_snippets():
                hotkey = (snippet.hotkey or "").strip()
                if not hotkey or not snippet.enabled:
                    continue
                try:
                    HotKey.parse(hotkey)
                except Exception:
                    logger.warning(f"Invalid snippet hotkey ignored: {hotkey}")
                    continue
                if hotkey in mappings:
                    logger.warning(f"Duplicate snippet hotkey ignored: {hotkey}")
                    continue
                mappings[hotkey] = lambda s=snippet: self.engine._expand("", s)
        except Exception as e:
            logger.error(f"Failed to load snippet hotkeys: {e}")
        return mappings
            
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
