import os
from pathlib import Path
from typing import List, Optional
from snipglide.database.connection import get_connection
from snipglide.models.screenshot import Screenshot
from snipglide.utils.logger import logger

def add_screenshot(
    file_path: str,
    filename: str,
    capture_type: str = "full",
    width: int = 0,
    height: int = 0,
    file_size: int = 0,
    note: str = ""
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO screenshots (file_path, filename, capture_type, width, height, file_size, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (file_path, filename, capture_type, width, height, file_size, note),
        )
        conn.commit()
        return cursor.lastrowid

def get_all_screenshots(
    search_query: str = "",
    capture_type: Optional[str] = None,
    favorites_only: bool = False,
    limit: int = 500,
    offset: int = 0
) -> List[Screenshot]:
    query = "SELECT * FROM screenshots WHERE 1=1"
    params = []

    if search_query:
        query += " AND (filename LIKE ? OR note LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term])

    if capture_type and capture_type != "all":
        query += " AND capture_type = ?"
        params.append(capture_type)

    if favorites_only:
        query += " AND is_favorite = 1"

    query += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    screenshots = []
    for r in rows:
        screenshots.append(
            Screenshot(
                id=r["id"],
                file_path=r["file_path"],
                filename=r["filename"],
                capture_type=r["capture_type"],
                width=r["width"],
                height=r["height"],
                file_size=r["file_size"],
                created_at=r["created_at"],
                is_favorite=bool(r["is_favorite"]),
                note=r["note"] or "",
            )
        )
    return screenshots

def get_screenshot_by_id(screenshot_id: int) -> Optional[Screenshot]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM screenshots WHERE id = ?", (screenshot_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return Screenshot(
            id=r["id"],
            file_path=r["file_path"],
            filename=r["filename"],
            capture_type=r["capture_type"],
            width=r["width"],
            height=r["height"],
            file_size=r["file_size"],
            created_at=r["created_at"],
            is_favorite=bool(r["is_favorite"]),
            note=r["note"] or "",
        )

def toggle_favorite_screenshot(screenshot_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_favorite FROM screenshots WHERE id = ?", (screenshot_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_favorite"] else 1
        cursor.execute("UPDATE screenshots SET is_favorite = ? WHERE id = ?", (new_val, screenshot_id))
        conn.commit()
        return bool(new_val)

def delete_screenshot(screenshot_id: int, delete_file: bool = True) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM screenshots WHERE id = ?", (screenshot_id,))
        row = cursor.fetchone()
        if not row:
            return False
        file_path = row["file_path"]

        cursor.execute("DELETE FROM screenshots WHERE id = ?", (screenshot_id,))
        conn.commit()

    if delete_file and file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted screenshot file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete screenshot file from disk: {e}")

    return True

def delete_all_screenshots(delete_files: bool = True) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM screenshots")
        rows = cursor.fetchall()
        cursor.execute("DELETE FROM screenshots")
        conn.commit()

    count = len(rows)
    if delete_files:
        for r in rows:
            fp = r["file_path"]
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
    return count

def get_screenshots_count() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM screenshots")
        row = cursor.fetchone()
        return row[0] if row else 0

def clean_missing_files():
    """Remove database entries whose files no longer exist on disk."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path FROM screenshots")
        rows = cursor.fetchall()
        missing_ids = [r["id"] for r in rows if not os.path.exists(r["file_path"])]
        if missing_ids:
            cursor.executemany("DELETE FROM screenshots WHERE id = ?", [(mid,) for mid in missing_ids])
            conn.commit()
            logger.info(f"Cleaned {len(missing_ids)} missing screenshot records from database.")
