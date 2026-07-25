from typing import List, Optional, Dict
from datetime import datetime
from snipglide.database.connection import get_connection
from snipglide.models.snippet import Snippet

def row_to_snippet(row) -> Snippet:
    tags_str = row["tags"]
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    
    return Snippet(
        id=row["id"],
        shortcut=row["shortcut"],
        replacement=row["replacement"],
        group_id=row["group_id"],
        tags=tags,
        description=row["description"],
        language=row["language"],
        enabled=bool(row["enabled"]),
        favorite=bool(row["favorite"]),
        usage_counter=row["usage_counter"],
        created_date=row["created_date"],
        modified_date=row["modified_date"],
        hotkey=row["hotkey"],
        regex_enabled=bool(row["regex_enabled"]),
        app_filter=row["app_filter"],
        window_filter=row["window_filter"],
        notes=row["notes"]
    )

def get_all_snippets() -> List[Snippet]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM snippets ORDER BY shortcut ASC")
        rows = cursor.fetchall()
        return [row_to_snippet(r) for r in rows]

def get_enabled_snippets() -> List[Snippet]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM snippets WHERE enabled = 1 ORDER BY shortcut ASC")
        rows = cursor.fetchall()
        return [row_to_snippet(r) for r in rows]

def get_snippet_by_shortcut(shortcut: str) -> Optional[Snippet]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM snippets WHERE shortcut = ?", (shortcut,))
        row = cursor.fetchone()
        if row:
            return row_to_snippet(row)
        return None

def get_snippet_by_id(snippet_id: int) -> Optional[Snippet]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
        row = cursor.fetchone()
        if row:
            return row_to_snippet(row)
        return None

def get_snippets_for_list(query: str = "", group_id: int | None = None, limit: int = 150) -> List[Snippet]:
    clauses = []
    params = []

    if group_id is not None:
        clauses.append("group_id = ?")
        params.append(group_id)

    if query:
        term = f"%{query}%"
        clauses.append("(shortcut LIKE ? OR description LIKE ? OR replacement LIKE ?)")
        params.extend([term, term, term])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, shortcut, substr(replacement, 1, 500) AS replacement,
                   group_id, tags, description, language, enabled, favorite,
                   usage_counter, created_date, modified_date, hotkey,
                   regex_enabled, app_filter, window_filter, notes
            FROM snippets
            {where_sql}
            ORDER BY favorite DESC, lower(shortcut) ASC
            LIMIT ?
            """,
            params,
        )
        rows = cursor.fetchall()
        return [row_to_snippet(r) for r in rows]

def add_snippet(snippet: Snippet) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        tags_str = ",".join(snippet.tags)
        cursor.execute("""
            INSERT INTO snippets (
                shortcut, replacement, group_id, tags, description, language,
                enabled, favorite, usage_counter, created_date, modified_date,
                hotkey, regex_enabled, app_filter, window_filter, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snippet.shortcut, snippet.replacement, snippet.group_id, tags_str,
            snippet.description, snippet.language, int(snippet.enabled), int(snippet.favorite),
            snippet.usage_counter, snippet.created_date, snippet.modified_date,
            snippet.hotkey, int(snippet.regex_enabled), snippet.app_filter,
            snippet.window_filter, snippet.notes
        ))
        conn.commit()
        return cursor.lastrowid

def update_snippet(snippet: Snippet):
    with get_connection() as conn:
        cursor = conn.cursor()
        tags_str = ",".join(snippet.tags)
        cursor.execute("""
            UPDATE snippets SET
                shortcut=?, replacement=?, group_id=?, tags=?, description=?, language=?,
                enabled=?, favorite=?, usage_counter=?, modified_date=?,
                hotkey=?, regex_enabled=?, app_filter=?, window_filter=?, notes=?
            WHERE id=?
        """, (
            snippet.shortcut, snippet.replacement, snippet.group_id, tags_str,
            snippet.description, snippet.language, int(snippet.enabled), int(snippet.favorite),
            snippet.usage_counter, datetime.now().isoformat(),
            snippet.hotkey, int(snippet.regex_enabled), snippet.app_filter,
            snippet.window_filter, snippet.notes, snippet.id
        ))
        conn.commit()

def delete_snippet(snippet_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        conn.commit()

def increment_usage(snippet_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE snippets SET usage_counter = usage_counter + 1 WHERE id = ?", (snippet_id,))
        cursor.execute("INSERT INTO usage_history (snippet_id) VALUES (?)", (snippet_id,))
        conn.commit()

def get_statistics() -> Dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM snippets")
        total_snippets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM groups")
        total_groups = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(usage_counter) FROM snippets")
        total_expansions = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT shortcut, usage_counter FROM snippets ORDER BY usage_counter DESC LIMIT 5")
        most_used = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT shortcut, modified_date FROM snippets ORDER BY modified_date DESC LIMIT 5")
        recent = [dict(row) for row in cursor.fetchall()]
        
        # Query past 7 days daily counts
        cursor.execute("""
            SELECT date(used_at) as day, COUNT(*) as count 
            FROM usage_history 
            WHERE used_at >= date('now', '-6 days') 
            GROUP BY date(used_at)
            ORDER BY date(used_at) ASC
        """)
        daily_stats = {row["day"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "total_snippets": total_snippets,
            "total_groups": total_groups,
            "total_expansions": total_expansions,
            "most_used": most_used,
            "recent": recent,
            "daily_stats": daily_stats
        }
