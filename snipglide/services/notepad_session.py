import json
import os
from pathlib import Path
from typing import Dict, Any, List
from snipglide.core.config import DATA_DIR

NOTEPAD_SESSION_FILE = DATA_DIR / "notepad_session.json"
RECENT_FILES_FILE = DATA_DIR / "notepad_recent.json"

DEFAULT_NOTEPAD_SETTINGS = {
    "word_wrap": True,
    "line_numbers": True,
    "status_bar": True,
    "highlight_current_line": True,
    "font_family": "Consolas",
    "font_size": 14,
    "zoom_percent": 100,
    "direction": "ltr",
    "bold": False,
    "italic": False,
    "underline": False,
    "folders": ["العامة", "العمل", "شخصي"],
    "current_folder": "كافة الملفات",
    "active_filter": "all",
}

def sanitize_folders_list(folders: Any) -> List[str]:
    """Clean and deduplicate folders list while preserving order."""
    if not isinstance(folders, list):
        return ["العامة", "العمل", "شخصي"]
    seen = set()
    cleaned = []
    for f in folders:
        if isinstance(f, str):
            f_clean = f.strip()
            if f_clean and f_clean not in seen and f_clean not in ["كافة الملفات", "المفضلة", "الأرشيف"]:
                seen.add(f_clean)
                cleaned.append(f_clean)
    if not cleaned:
        cleaned = ["العامة", "العمل", "شخصي"]
    elif "العامة" not in cleaned:
        cleaned.insert(0, "العامة")
    return cleaned

def load_notepad_session() -> Dict[str, Any]:
    """Load the saved tabs, drafts, and preferences of Notepad."""
    if NOTEPAD_SESSION_FILE.exists():
        try:
            data = json.loads(NOTEPAD_SESSION_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Ensure folders list exists and is sanitized/deduplicated
                data["folders"] = sanitize_folders_list(data.get("folders"))
                return data
        except Exception:
            pass
    return {
        "tabs": [],
        "active_index": 0,
        "folders": ["العامة", "العمل", "شخصي"],
        "current_folder": "كافة الملفات",
        "active_filter": "all",
        "settings": DEFAULT_NOTEPAD_SETTINGS.copy()
    }

def save_notepad_session(data: Dict[str, Any]) -> bool:
    """Save the current tabs, drafts, and settings to disk."""
    try:
        if isinstance(data, dict) and "folders" in data:
            data["folders"] = sanitize_folders_list(data["folders"])
        NOTEPAD_SESSION_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return True
    except Exception:
        return False

def get_recent_files() -> List[str]:
    """Get list of recently opened files."""
    if RECENT_FILES_FILE.exists():
        try:
            files = json.loads(RECENT_FILES_FILE.read_text(encoding="utf-8"))
            if isinstance(files, list):
                # Filter out files that no longer exist
                valid_files = [f for f in files if isinstance(f, str) and os.path.exists(f)]
                return valid_files[:15]
        except Exception:
            pass
    return []

def add_recent_file(file_path: str) -> None:
    """Add a file path to the recent files list."""
    if not file_path or not os.path.exists(file_path):
        return
    norm_path = os.path.normpath(file_path)
    files = get_recent_files()
    if norm_path in files:
        files.remove(norm_path)
    files.insert(0, norm_path)
    files = files[:15]
    try:
        RECENT_FILES_FILE.write_text(
            json.dumps(files, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

def clear_recent_files() -> None:
    """Clear recent files history."""
    try:
        if RECENT_FILES_FILE.exists():
            RECENT_FILES_FILE.unlink()
    except Exception:
        pass
