from snipglide.database.connection import get_connection

def get_clipboard_history(limit: int = 15) -> list[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM clipboard_history ORDER BY copied_at DESC LIMIT ?", (limit,))
        return [row["content"] for row in cursor.fetchall()]

def add_clipboard_entry(content: str):
    if not content.strip():
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        # To avoid duplicates, delete existing match first to move it to top of history
        cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (content,))
        cursor.execute("INSERT OR REPLACE INTO clipboard_history (content) VALUES (?)", (content,))
        conn.commit()

def clear_clipboard_history():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clipboard_history")
        conn.commit()
