from typing import List, Optional
from snipglide.database.connection import get_connection
from snipglide.models.group import Group

def get_all_groups() -> List[Group]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups ORDER BY name ASC")
        rows = cursor.fetchall()
        return [
            Group(
                id=row["id"],
                name=row["name"],
                icon=row["icon"],
                color=row["color"],
                description=row["description"],
                is_collapsed=bool(row["is_collapsed"])
            )
            for row in rows
        ]

def get_group_by_name(name: str) -> Optional[Group]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return Group(
                id=row["id"],
                name=row["name"],
                icon=row["icon"],
                color=row["color"],
                description=row["description"],
                is_collapsed=bool(row["is_collapsed"])
            )
        return None

def add_group(group: Group) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO groups (name, icon, color, description, is_collapsed) VALUES (?, ?, ?, ?, ?)",
            (group.name, group.icon, group.color, group.description, int(group.is_collapsed))
        )
        conn.commit()
        return cursor.lastrowid

def update_group(group: Group):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE groups SET name=?, icon=?, color=?, description=?, is_collapsed=? WHERE id=?",
            (group.name, group.icon, group.color, group.description, int(group.is_collapsed), group.id)
        )
        conn.commit()

def delete_group(group_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM groups WHERE name = 'General'")
        row = cursor.fetchone()
        general_id = row["id"] if row else None
        
        if general_id and general_id != group_id:
            cursor.execute("UPDATE snippets SET group_id = ? WHERE group_id = ?", (general_id, group_id))
            
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        conn.commit()
