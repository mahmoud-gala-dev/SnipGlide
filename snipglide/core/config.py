import os
import json
from pathlib import Path

APP_NAME = "SnipGlide Python"
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "SnipGlidePythonPro"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DATA_DIR / "snipglide.db"
SETTINGS_FILE = DATA_DIR / "settings.json"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR = DATA_DIR / "plugins"
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR = DATA_DIR / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Default configuration parameters
DEFAULT_SETTINGS = {
    "enabled": True,
    "start_minimized": False,
    "case_sensitive": True,
    "max_buffer": 250,
    "play_sound": True,
    "sync_enabled": False,
    "sync_provider": "local",
    "sync_path": "",
    "master_password_enabled": False,
    "lock_on_startup": False,
    "master_password_hash": "",
    "ai_api_key": "",
    "ai_provider": "gemini",
    "theme": "System",
    "ui_zoom": 1.0,
    "sidebar_font_size": 13,
    "sidebar_direction": "ltr",
    "clipboard_history_enabled": True,
    "clipboard_poll_interval": 3.0,
    "clipboard_max_chars": 10000,
    "clipboard_skip_private_windows": True,
    "quick_open_hotkey": "<ctrl>+<shift>+<f12>",
    "screenshots_dir": str(SCREENSHOTS_DIR),
    "screenshot_copy_to_clipboard": True,
    "screenshot_play_sound": True,
    "screenshot_show_notification": True,
    "screenshot_format": "png",
    "hotkey_full_screenshot": "<ctrl>+<print_screen>",
    "hotkey_area_screenshot": "<win>+<print_screen>",
    "recordings_dir": str(RECORDINGS_DIR),
    "video_record_audio": False,
    "video_show_cursor": True,
    "video_fps": 24,
    "hotkey_video_record": "<ctrl>+<shift>+r",
}

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            default = DEFAULT_SETTINGS.copy()
            default.update(loaded)
            return default
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    import json
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

ARABIC_FONT_FAMILY = "Segoe UI"

def set_arabic_font_family(name: str):
    global ARABIC_FONT_FAMILY
    ARABIC_FONT_FAMILY = name

def get_arabic_font_family() -> str:
    global ARABIC_FONT_FAMILY
    return ARABIC_FONT_FAMILY
