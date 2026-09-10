from typing import Optional
from datetime import datetime
from snipglide.database.connection import get_connection
from snipglide.models.saved_regex import SavedRegex

def _row_to_regex(row) -> SavedRegex:
    return SavedRegex(
        id=row["id"],
        name=row["name"],
        pattern=row["pattern"],
        description=row["description"] or "",
        flags=row["flags"] or "",
        replacement=row["replacement"] or "",
        favorite=bool(row["favorite"]),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )

def create_regex(regex: SavedRegex) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO saved_regexes (name, pattern, description, flags, replacement, favorite, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regex.name.strip(),
                    regex.pattern,
                    regex.description.strip(),
                    regex.flags.strip(),
                    regex.replacement,
                    1 if regex.favorite else 0,
                    regex.created_at or now,
                    regex.updated_at or now,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()

def update_regex(regex: SavedRegex) -> bool:
    if not regex.id:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE saved_regexes
                SET name = ?, pattern = ?, description = ?, flags = ?, replacement = ?, favorite = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    regex.name.strip(),
                    regex.pattern,
                    regex.description.strip(),
                    regex.flags.strip(),
                    regex.replacement,
                    1 if regex.favorite else 0,
                    now,
                    regex.id,
                ),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()

def delete_regex(regex_id: int) -> bool:
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM saved_regexes WHERE id = ?", (regex_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def get_regex_by_id(regex_id: int) -> Optional[SavedRegex]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_regexes WHERE id = ?", (regex_id,))
        row = cursor.fetchone()
        return _row_to_regex(row) if row else None
    finally:
        conn.close()

def get_all_regexes(favorites_only: bool = False) -> list[SavedRegex]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if favorites_only:
            cursor.execute(
                "SELECT * FROM saved_regexes WHERE favorite = 1 ORDER BY updated_at DESC, id DESC"
            )
        else:
            cursor.execute(
                "SELECT * FROM saved_regexes ORDER BY favorite DESC, updated_at DESC, id DESC"
            )
        return [_row_to_regex(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def search_regexes(query: str, favorites_only: bool = False) -> list[SavedRegex]:
    term = f"%{query.strip()}%"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if favorites_only:
            cursor.execute(
                """
                SELECT * FROM saved_regexes
                WHERE favorite = 1 AND (name LIKE ? OR pattern LIKE ? OR description LIKE ?)
                ORDER BY updated_at DESC, id DESC
                """,
                (term, term, term),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM saved_regexes
                WHERE name LIKE ? OR pattern LIKE ? OR description LIKE ?
                ORDER BY favorite DESC, updated_at DESC, id DESC
                """,
                (term, term, term),
            )
        return [_row_to_regex(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def toggle_favorite(regex_id: int) -> bool:
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT favorite FROM saved_regexes WHERE id = ?", (regex_id,))
            row = cursor.fetchone()
            if not row:
                return False
            new_val = 0 if row["favorite"] else 1
            cursor.execute(
                "UPDATE saved_regexes SET favorite = ? WHERE id = ?",
                (new_val, regex_id),
            )
            return bool(new_val)
    finally:
        conn.close()

class RegexRepository:
    """Class interface for SavedRegex repository operations."""
    create = staticmethod(create_regex)
    update = staticmethod(update_regex)
    delete = staticmethod(delete_regex)
    get_by_id = staticmethod(get_regex_by_id)
    list_all = staticmethod(get_all_regexes)
    search = staticmethod(search_regexes)
    toggle_favorite = staticmethod(toggle_favorite)
