"""Unified Developer Search Repository for SnipGlide.

Performs indexed, multi-source searching across Snippets, Notes, Chat Notes,
Clipboard History, Screenshots, Saved Regexes, API Requests, Projects, and Commands.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from snipglide.database.connection import get_connection
from snipglide.utils.logger import logger


def search_all(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search across all 10 SnipGlide data sources with simple heuristic ranking."""
    query_clean = query.strip()
    if not query_clean:
        return []

    term = f"%{query_clean}%"
    term_lower = query_clean.lower()
    raw_results: List[Dict[str, Any]] = []
    per_source_limit = max(8, limit // 3)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Snippets
        try:
            cursor.execute(
                """
                SELECT 'Snippet' AS kind, CAST(id AS TEXT) AS ref, shortcut AS title,
                       substr(replacement, 1, 300) AS body, 'snippets' AS source,
                       favorite AS is_fav, NULL AS created_at
                FROM snippets
                WHERE shortcut LIKE ? OR description LIKE ? OR replacement LIKE ?
                ORDER BY favorite DESC, shortcut ASC
                LIMIT ?
                """,
                (term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on snippets: %s", e)

        # 2. Notes
        try:
            cursor.execute(
                """
                SELECT 'Note' AS kind, CAST(id AS TEXT) AS ref, title,
                       substr(content, 1, 300) AS body, 'notes' AS source,
                       pinned AS is_fav, modified_date AS created_at
                FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY pinned DESC, modified_date DESC
                LIMIT ?
                """,
                (term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on notes: %s", e)

        # 3. Chat Notes
        try:
            cursor.execute(
                """
                SELECT 'Chat Note' AS kind, CAST(id AS TEXT) AS ref,
                       substr(content, 1, 60) AS title,
                       substr(content, 1, 300) AS body, 'chat_notes' AS source,
                       is_starred AS is_fav, created_at
                FROM chat_notes
                WHERE content LIKE ?
                ORDER BY is_starred DESC, created_at DESC
                LIMIT ?
                """,
                (term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on chat_notes: %s", e)

        # 4. Clipboard History
        try:
            cursor.execute(
                """
                SELECT 'Clipboard' AS kind, CAST(id AS TEXT) AS ref,
                       substr(content, 1, 60) AS title,
                       substr(content, 1, 300) AS body, 'clipboard' AS source,
                       0 AS is_fav, copied_at AS created_at
                FROM clipboard_history
                WHERE content LIKE ?
                ORDER BY copied_at DESC, id DESC
                LIMIT ?
                """,
                (term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on clipboard_history: %s", e)

        # 5. Saved Regexes
        try:
            cursor.execute(
                """
                SELECT 'Regex' AS kind, CAST(id AS TEXT) AS ref, name AS title,
                       pattern AS body, 'saved_regexes' AS source,
                       favorite AS is_fav, NULL AS created_at
                FROM saved_regexes
                WHERE name LIKE ? OR pattern LIKE ? OR description LIKE ?
                ORDER BY favorite DESC, name ASC
                LIMIT ?
                """,
                (term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on saved_regexes: %s", e)

        # 6. Saved API Requests
        try:
            cursor.execute(
                """
                SELECT 'API Request' AS kind, CAST(id AS TEXT) AS ref,
                       (method || ' ' || name) AS title,
                       url AS body, 'saved_api_requests' AS source,
                       is_favorite AS is_fav, created_at
                FROM saved_api_requests
                WHERE name LIKE ? OR url LIKE ? OR collection_name LIKE ?
                ORDER BY is_favorite DESC, name ASC
                LIMIT ?
                """,
                (term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on saved_api_requests: %s", e)

        # 7. Developer Projects
        try:
            cursor.execute(
                """
                SELECT 'Project' AS kind, CAST(id AS TEXT) AS ref,
                       (name || ' (' || language || ')') AS title,
                       project_path AS body, 'developer_projects' AS source,
                       is_favorite AS is_fav, created_at
                FROM developer_projects
                WHERE name LIKE ? OR project_path LIKE ? OR language LIKE ? OR framework LIKE ?
                ORDER BY is_favorite DESC, name ASC
                LIMIT ?
                """,
                (term, term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on developer_projects: %s", e)

        # 8. Terminal Commands
        try:
            cursor.execute(
                """
                SELECT 'Command' AS kind, CAST(id AS TEXT) AS ref,
                       ('[' || category || '] ' || name) AS title,
                       command AS body, 'terminal_commands' AS source,
                       is_favorite AS is_fav, created_at
                FROM terminal_commands
                WHERE name LIKE ? OR command LIKE ? OR description LIKE ?
                ORDER BY is_favorite DESC, name ASC
                LIMIT ?
                """,
                (term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on terminal_commands: %s", e)

        # 9. Screenshots metadata
        try:
            cursor.execute(
                """
                SELECT 'Screenshot' AS kind, CAST(id AS TEXT) AS ref,
                       filename AS title,
                       (folder || ' | ' || note) AS body, 'screenshots' AS source,
                       is_favorite AS is_fav, created_at
                FROM screenshots
                WHERE filename LIKE ? OR note LIKE ? OR folder LIKE ?
                ORDER BY is_favorite DESC, created_at DESC
                LIMIT ?
                """,
                (term, term, term, per_source_limit),
            )
            raw_results.extend(dict(row) for row in cursor.fetchall())
        except Exception as e:
            logger.warning("Unified search query error on screenshots: %s", e)

    # Score and rank results
    scored_results = []
    for r in raw_results:
        title_l = (r.get("title") or "").lower()
        body_l = (r.get("body") or "").lower()
        score = 0

        # Exact title or exact name match
        if title_l == term_lower or title_l.startswith(term_lower + " (") or title_l.startswith(term_lower + " -"):
            score += 100
        # Title prefix match
        elif title_l.startswith(term_lower):
            score += 60

        # Title contains match
        elif term_lower in title_l:
            score += 40

        # Content contains match
        if term_lower in body_l:
            score += 20

        # Favorite / Pinned / Starred boost
        if r.get("is_fav"):
            score += 15

        # Recent timestamp boost
        if r.get("created_at"):
            score += 5

        r["score"] = score
        scored_results.append(r)

    # Sort descending by score
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:limit]


def get_search_result_body(kind: str, ref: str) -> str:
    """Retrieve full text/body content for a given search item."""
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

        if kind == "Chat Note":
            cursor.execute("SELECT content FROM chat_notes WHERE id = ?", (ref,))
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

        if kind == "API Request":
            cursor.execute("SELECT url FROM saved_api_requests WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["url"] if row else ""

        if kind == "Project":
            cursor.execute("SELECT project_path FROM developer_projects WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["project_path"] if row else ""

        if kind == "Command":
            cursor.execute("SELECT command FROM terminal_commands WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["command"] if row else ""

        if kind == "Screenshot":
            cursor.execute("SELECT file_path FROM screenshots WHERE id = ?", (ref,))
            row = cursor.fetchone()
            return row["file_path"] if row else ""

    return ""
