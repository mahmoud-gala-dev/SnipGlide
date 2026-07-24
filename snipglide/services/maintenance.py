import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from snipglide.core.config import BACKUP_DIR, DB_FILE, SETTINGS_FILE
from snipglide.database.connection import get_connection
from snipglide.utils.logger import logger


PACKAGE_TABLES = [
    "groups",
    "snippets",
    "autocorrect",
    "note_categories",
    "notes",
    "note_settings",
    "clipboard_history",
]


def get_health_report() -> dict:
    report = {
        "database_path": str(DB_FILE),
        "database_size_kb": _file_size_kb(DB_FILE),
        "settings_path": str(SETTINGS_FILE),
        "last_backup": _last_backup_name(),
        "integrity": "unknown",
        "counts": {},
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            report["integrity"] = cursor.fetchone()[0]

            for table in ["snippets", "groups", "notes", "clipboard_history", "autocorrect", "usage_history"]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                report["counts"][table] = cursor.fetchone()[0]
    except Exception as e:
        report["integrity"] = f"error: {e}"

    return report


def optimize_database(clear_clipboard: bool = False) -> dict:
    result = {"before_kb": _file_size_kb(DB_FILE), "after_kb": 0, "clipboard_cleared": clear_clipboard}
    with get_connection() as conn:
        cursor = conn.cursor()
        if clear_clipboard:
            cursor.execute("DELETE FROM clipboard_history")
        cursor.execute("VACUUM")
        conn.commit()
    result["after_kb"] = _file_size_kb(DB_FILE)
    logger.info("Database optimized.")
    return result


def export_full_package(file_path: str) -> bool:
    try:
        package = {
            "version": "2.0",
            "exported_at": datetime.now().isoformat(),
            "settings": _read_json(SETTINGS_FILE),
            "tables": {},
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            for table in PACKAGE_TABLES:
                cursor.execute(f"SELECT * FROM {table}")
                package["tables"][table] = [dict(row) for row in cursor.fetchall()]

        Path(file_path).write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Full package exported to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Full package export failed: {e}")
        return False


def import_full_package(file_path: str) -> bool:
    try:
        package = json.loads(Path(file_path).read_text(encoding="utf-8"))
        tables = package.get("tables", {})
        if not isinstance(tables, dict) or "snippets" not in tables:
            return False

        _backup_current_files()

        with get_connection() as conn:
            cursor = conn.cursor()
            for table in reversed(PACKAGE_TABLES):
                cursor.execute(f"DELETE FROM {table}")

            for table in PACKAGE_TABLES:
                rows = tables.get(table, [])
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ", ".join("?" for _ in columns)
                columns_sql = ", ".join(columns)
                cursor.executemany(
                    f"INSERT OR REPLACE INTO {table} ({columns_sql}) VALUES ({placeholders})",
                    [[row.get(column) for column in columns] for row in rows],
                )
            conn.commit()

        settings = package.get("settings")
        if isinstance(settings, dict):
            SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Full package imported from {file_path}")
        return True
    except Exception as e:
        logger.error(f"Full package import failed: {e}")
        return False


def export_sync_copy(sync_dir: str) -> str:
    target_dir = Path(sync_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "snipglide_sync_package.json"
    if not export_full_package(str(target)):
        raise RuntimeError("Failed to export sync package.")
    return str(target)


def read_log_tail(max_lines: int = 200) -> str:
    log_file = DB_FILE.parent / "snipglide.log"
    if not log_file.exists():
        return "No log file found."
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _file_size_kb(path: Path) -> int:
    return int(path.stat().st_size / 1024) if path.exists() else 0


def _last_backup_name() -> str:
    backups = sorted(BACKUP_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0].name if backups else "None"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _backup_current_files():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if DB_FILE.exists():
        shutil.copy2(DB_FILE, BACKUP_DIR / f"pre_import_{timestamp}.db")
    if SETTINGS_FILE.exists():
        shutil.copy2(SETTINGS_FILE, BACKUP_DIR / f"pre_import_settings_{timestamp}.json")
