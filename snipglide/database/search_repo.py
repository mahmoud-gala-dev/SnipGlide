from snipglide.database.connection import get_connection


def search_all(query: str, limit: int = 40) -> list[dict]:
    term = f"%{query}%"
    per_source_limit = max(5, limit // 3 + 2)
    results = []

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 'Snippet' AS kind, shortcut AS title, replacement AS body
            FROM snippets
            WHERE shortcut LIKE ? OR description LIKE ? OR replacement LIKE ?
            ORDER BY favorite DESC, shortcut ASC
            LIMIT ?
            """,
            (term, term, term, per_source_limit),
        )
        results.extend(dict(row) for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT 'Note' AS kind, title, content AS body
            FROM notes
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY pinned DESC, modified_date DESC
            LIMIT ?
            """,
            (term, term, per_source_limit),
        )
        results.extend(dict(row) for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT 'Clipboard' AS kind, 'Clipboard entry' AS title, content AS body
            FROM clipboard_history
            WHERE content LIKE ?
            ORDER BY copied_at DESC, id DESC
            LIMIT ?
            """,
            (term, per_source_limit),
        )
        results.extend(dict(row) for row in cursor.fetchall())

    return results[:limit]
