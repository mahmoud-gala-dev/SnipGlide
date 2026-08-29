import sqlite3
from typing import List, Optional
from datetime import datetime
from snipglide.database.connection import get_connection
from snipglide.models.chat_note import ChatNote


def get_all_chat_notes(query: str = "", starred_only: bool = False, limit: int = 500) -> List[ChatNote]:
    """Retrieve chat notes ordered chronologically (oldest to newest for chat flow)."""
    clauses = []
    params = []

    if starred_only:
        clauses.append("is_starred = 1")

    if query.strip():
        term = f"%{query.strip()}%"
        clauses.append("content LIKE ?")
        params.append(term)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        # Query newest last (chronological ascending) so chat scrolls downwards naturally
        cursor.execute(
            f"""
            SELECT id, content, created_at, is_starred, tags, color
            FROM (
                SELECT id, content, created_at, is_starred, tags, color
                FROM chat_notes
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            )
            ORDER BY created_at ASC, id ASC
            """,
            params,
        )
        rows = cursor.fetchall()
        return [
            ChatNote(
                id=row["id"],
                content=row["content"],
                created_at=row["created_at"],
                is_starred=bool(row["is_starred"]),
                tags=row["tags"] or "",
                color=row["color"] or "#25D366",
            )
            for row in rows
        ]


def get_chat_note_by_id(note_id: int) -> Optional[ChatNote]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content, created_at, is_starred, tags, color FROM chat_notes WHERE id = ?",
            (note_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ChatNote(
            id=row["id"],
            content=row["content"],
            created_at=row["created_at"],
            is_starred=bool(row["is_starred"]),
            tags=row["tags"] or "",
            color=row["color"] or "#25D366",
        )


def add_chat_note(content: str, is_starred: bool = False, tags: str = "", color: str = "#25D366") -> ChatNote:
    if not content.strip():
        raise ValueError("Chat note content cannot be empty.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_notes (content, created_at, is_starred, tags, color)
            VALUES (?, ?, ?, ?, ?)
            """,
            (content.strip(), now_str, 1 if is_starred else 0, tags, color),
        )
        conn.commit()
        note_id = cursor.lastrowid
        return ChatNote(
            id=note_id,
            content=content.strip(),
            created_at=now_str,
            is_starred=is_starred,
            tags=tags,
            color=color,
        )


def delete_chat_note(note_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_notes WHERE id = ?", (note_id,))
        conn.commit()


def toggle_star_chat_note(note_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_starred FROM chat_notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_starred"] else 1
        cursor.execute("UPDATE chat_notes SET is_starred = ? WHERE id = ?", (new_val, note_id))
        conn.commit()
        return bool(new_val)


def update_chat_note_content(note_id: int, new_content: str):
    if not new_content.strip():
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_notes SET content = ? WHERE id = ?", (new_content.strip(), note_id))
        conn.commit()


def clear_all_chat_notes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_notes")
        conn.commit()


def get_chat_notes_count(starred_only: bool = False) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        if starred_only:
            cursor.execute("SELECT COUNT(*) FROM chat_notes WHERE is_starred = 1")
        else:
            cursor.execute("SELECT COUNT(*) FROM chat_notes")
        return cursor.fetchone()[0]
