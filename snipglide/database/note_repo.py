import sqlite3
from typing import List, Optional
from snipglide.database.connection import get_connection
from snipglide.models.note import Note

def get_all_notes() -> List[Note]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, category_id, created_date, modified_date, color, pinned 
            FROM notes 
            ORDER BY pinned DESC, modified_date DESC
        """)
        rows = cursor.fetchall()
        return [Note(**dict(row)) for row in rows]

def get_notes_by_category(cat_id: int) -> List[Note]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, category_id, created_date, modified_date, color, pinned 
            FROM notes 
            WHERE category_id = ?
            ORDER BY pinned DESC, modified_date DESC
        """, (cat_id,))
        rows = cursor.fetchall()
        return [Note(**dict(row)) for row in rows]

def get_note_by_id(note_id: int) -> Optional[Note]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, category_id, created_date, modified_date, color, pinned 
            FROM notes WHERE id = ?
        """, (note_id,))
        row = cursor.fetchone()
        return Note(**dict(row)) if row else None

def add_note(note: Note) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO notes (title, content, category_id, created_date, modified_date, color, pinned)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (note.title, note.content, note.category_id, note.created_date, note.modified_date, note.color, note.pinned)
        )
        conn.commit()
        return cursor.lastrowid

def update_note(note: Note):
    from datetime import datetime
    note.modified_date = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE notes SET title = ?, content = ?, category_id = ?, modified_date = ?, color = ?, pinned = ?
               WHERE id = ?""",
            (note.title, note.content, note.category_id, note.modified_date, note.color, note.pinned, note.id)
        )
        conn.commit()

def delete_note(note_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()

def toggle_pin(note_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET pinned = NOT pinned WHERE id = ?", (note_id,))
        conn.commit()
