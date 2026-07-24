import sqlite3
from typing import List, Optional
from snipglide.database.connection import get_connection
from snipglide.models.note_category import NoteCategory

def get_all_categories() -> List[NoteCategory]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon, color, description FROM note_categories ORDER BY name")
        rows = cursor.fetchall()
        return [NoteCategory(**dict(row)) for row in rows]

def get_category_by_id(cat_id: int) -> Optional[NoteCategory]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon, color, description FROM note_categories WHERE id = ?", (cat_id,))
        row = cursor.fetchone()
        return NoteCategory(**dict(row)) if row else None

def add_category(category: NoteCategory) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO note_categories (name, icon, color, description) VALUES (?, ?, ?, ?)",
            (category.name, category.icon, category.color, category.description)
        )
        conn.commit()
        return cursor.lastrowid

def update_category(category: NoteCategory):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE note_categories SET name = ?, icon = ?, color = ?, description = ? WHERE id = ?",
            (category.name, category.icon, category.color, category.description, category.id)
        )
        conn.commit()

def delete_category(cat_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        # First set all notes in this category to uncategorized
        cursor.execute("UPDATE notes SET category_id = NULL WHERE category_id = ?", (cat_id,))
        cursor.execute("DELETE FROM note_categories WHERE id = ?", (cat_id,))
        conn.commit()
