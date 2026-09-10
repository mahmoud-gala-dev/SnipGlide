"""Repository for Developer Projects CRUD and search."""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from snipglide.database.connection import get_db_connection
from snipglide.models.project_models import DeveloperProject
from snipglide.utils.logger import logger


class ProjectRepository:
    """Handles persistence for local developer projects."""

    def create(self, project: DeveloperProject) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO developer_projects (name, project_path, language, framework, description, is_favorite)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.name,
                    project.project_path,
                    project.language,
                    project.framework,
                    project.description,
                    1 if project.favorite else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create developer project: {e}")
            raise
        finally:
            conn.close()

    def get_by_id(self, project_id: int) -> Optional[DeveloperProject]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM developer_projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_project(row)
        finally:
            conn.close()

    def get_by_path(self, path: str) -> Optional[DeveloperProject]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM developer_projects WHERE project_path = ?", (path,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_project(row)
        finally:
            conn.close()

    def get_all(self) -> List[DeveloperProject]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM developer_projects ORDER BY is_favorite DESC, name ASC")
            return [self._row_to_project(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update(self, project: DeveloperProject) -> bool:
        if not project.id:
            return False
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE developer_projects
                SET name = ?, project_path = ?, language = ?, framework = ?, description = ?, is_favorite = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    project.name,
                    project.project_path,
                    project.language,
                    project.framework,
                    project.description,
                    1 if project.favorite else 0,
                    project.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, project_id: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM developer_projects WHERE id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def toggle_favorite(self, project_id: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE developer_projects SET is_favorite = (CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END) WHERE id = ?",
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def search(self, query: str) -> List[DeveloperProject]:
        if not query.strip():
            return self.get_all()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            wildcard = f"%{query.strip()}%"
            cursor.execute(
                """
                SELECT * FROM developer_projects
                WHERE name LIKE ? OR language LIKE ? OR framework LIKE ? OR description LIKE ?
                ORDER BY is_favorite DESC, name ASC
                """,
                (wildcard, wildcard, wildcard, wildcard),
            )
            return [self._row_to_project(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> DeveloperProject:
        return DeveloperProject(
            id=row["id"],
            name=row["name"],
            project_path=row["project_path"],
            language=row["language"] or "",
            framework=row["framework"] or "",
            description=row["description"] or "",
            favorite=bool(row["is_favorite"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
