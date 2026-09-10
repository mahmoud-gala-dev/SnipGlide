from typing import Optional, Any
from snipglide.database.connection import get_connection

MAX_CLIPBOARD_HISTORY = 50

def get_clipboard_history(limit: int = 10, offset: int = 0) -> list[str]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM clipboard_history ORDER BY copied_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [row["content"] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_clipboard_entries(limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content, content_type, copied_at FROM clipboard_history ORDER BY copied_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        entries = []
        for row in cursor.fetchall():
            cols = row.keys()
            c_type = row["content_type"] if "content_type" in cols and row["content_type"] else "PLAIN_TEXT"
            entries.append({
                "id": row["id"],
                "content": row["content"],
                "content_type": c_type,
                "copied_at": row["copied_at"],
            })
        return entries
    finally:
        conn.close()

def get_clipboard_history_count() -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clipboard_history")
        return min(cursor.fetchone()[0], MAX_CLIPBOARD_HISTORY)
    finally:
        conn.close()

def add_clipboard_entry(content: str, content_type: Optional[str] = None):
    if not content or not content.strip():
        return
    if content_type is None:
        from snipglide.services.clipboard_content_detector import ClipboardContentDetector
        content_type = ClipboardContentDetector.detect_type(content)

    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # To avoid duplicates, delete existing match first to move it to top of history
            cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (content,))
            cursor.execute(
                "INSERT OR REPLACE INTO clipboard_history (content, content_type) VALUES (?, ?)",
                (content, content_type),
            )
            cursor.execute(
                """
                DELETE FROM clipboard_history
                WHERE id NOT IN (
                    SELECT id FROM clipboard_history
                    ORDER BY copied_at DESC, id DESC
                    LIMIT ?
                )
                """,
                (MAX_CLIPBOARD_HISTORY,),
            )
    finally:
        conn.close()

def delete_clipboard_entry(content: str) -> bool:
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (content,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def clear_clipboard_history():
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clipboard_history")
    finally:
        conn.close()

def search_clipboard_entries(query: str, limit: int = 10, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        pattern = f"%{query}%"
        cursor.execute("SELECT COUNT(*) FROM clipboard_history WHERE content LIKE ?", (pattern,))
        total = min(cursor.fetchone()[0], MAX_CLIPBOARD_HISTORY)

        cursor.execute(
            "SELECT id, content, content_type, copied_at FROM clipboard_history WHERE content LIKE ? ORDER BY copied_at DESC, id DESC LIMIT ? OFFSET ?",
            (pattern, limit, offset),
        )
        entries = []
        for row in cursor.fetchall():
            cols = row.keys()
            c_type = row["content_type"] if "content_type" in cols and row["content_type"] else "PLAIN_TEXT"
            entries.append({
                "id": row["id"],
                "content": row["content"],
                "content_type": c_type,
                "copied_at": row["copied_at"],
            })
        return entries, total
    finally:
        conn.close()

def update_clipboard_content_type(entry_id: int, content_type: str):
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clipboard_history SET content_type = ? WHERE id = ?", (content_type, entry_id))
    finally:
        conn.close()
