from snipglide.database.connection import get_connection


def search_all(query: str, limit: int = 40) -> list[dict]:
    term = f"%{query}%"
    per_source_limit = max(5, limit // 3 + 2)
    results = []

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 'Snippet' AS kind, CAST(id AS TEXT) AS ref, shortcut AS title, substr(replacement, 1, 500) AS body
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
            SELECT 'Note' AS kind, CAST(id AS TEXT) AS ref, title, substr(content, 1, 500) AS body
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
            SELECT 'Clipboard' AS kind, CAST(id AS TEXT) AS ref, 'Clipboard entry' AS title, substr(content, 1, 500) AS body
            FROM clipboard_history
            WHERE content LIKE ?
            ORDER BY copied_at DESC, id DESC
            LIMIT ?
            """,
            (term, per_source_limit),
        )
        results.extend(dict(row) for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT 'Regex' AS kind, CAST(id AS TEXT) AS ref, name AS title, substr(pattern, 1, 500) AS body
            FROM saved_regexes
            WHERE name LIKE ? OR pattern LIKE ? OR description LIKE ?
            ORDER BY favorite DESC, name ASC
            LIMIT ?
            """,
            (term, term, term, per_source_limit),
        )
        results.extend(dict(row) for row in cursor.fetchall())

    return results[:limit]


def get_search_result_body(kind: str, ref: str) -> str:
    with get_connection() as conn:
        cursor = conn.cursor()

        if kind == "Snippet":
            cursor.execute("SELECT replacement FROM snippets WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["replacement"] if row else ""

        if kind == "Note":
            cursor.execute("SELECT content FROM notes WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["content"] if row else ""

        if kind == "Clipboard":
            cursor.execute("SELECT content FROM clipboard_history WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["content"] if row else ""

        if kind == "Regex":
            cursor.execute("SELECT pattern FROM saved_regexes WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["pattern"] if row else ""

    return ""
