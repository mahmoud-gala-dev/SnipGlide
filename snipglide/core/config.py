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

# Default configuration parameters
DEFAULT_SETTINGS = {
    "enabled": True,
    "start_minimized": False,
    "case_sensitive": True,
    "max_buffer": 250,
    "sync_enabled": False,
    "sync_provider": "local",
    "sync_path": "",
    "master_password_enabled": False,
    "lock_on_startup": False,
    "ai_api_key": "",
    "ai_provider": "gemini",
    "theme": "System",
    "sidebar_font_size": 13,
    "sidebar_direction": "ltr",
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
