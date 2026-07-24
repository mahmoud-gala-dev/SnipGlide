from snipglide.database.connection import get_connection


MAX_CLIPBOARD_HISTORY = 50


def get_clipboard_history(limit: int = 10, offset: int = 0) -> list[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM clipboard_history ORDER BY copied_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [row["content"] for row in cursor.fetchall()]


def get_clipboard_history_count() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clipboard_history")
        return min(cursor.fetchone()[0], MAX_CLIPBOARD_HISTORY)

def add_clipboard_entry(content: str):
    if not content.strip():
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        # To avoid duplicates, delete existing match first to move it to top of history
        cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (content,))
        cursor.execute("INSERT OR REPLACE INTO clipboard_history (content) VALUES (?)", (content,))
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
        conn.commit()

def clear_clipboard_history():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clipboard_history")
        conn.commit()
