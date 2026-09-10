"""Repository for Terminal Command Library with default reference seeds."""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from snipglide.database.connection import get_db_connection
from snipglide.models.project_models import TerminalCommand
from snipglide.utils.logger import logger

DEFAULT_COMMAND_SEEDS = [
    # Git
    ("Git: Status Summary", "git status -sb", "Display compact branch status and modified files", "Git"),
    ("Git: Log One-Line Graph", "git log --oneline --graph --decorate -n 15", "Display visual commit tree", "Git"),
    ("Git: Discard Working Changes", "git restore .", "Discard all uncommitted changes in current directory", "Git"),
    ("Git: Switch New Branch", "git switch -c {{branch}}", "Create and switch to a new branch", "Git"),
    ("Git: Undo Last Commit (Keep Changes)", "git reset --soft HEAD~1", "Rewind HEAD one commit leaving files staged", "Git"),
    # Python & pip
    ("Python: Create Virtualenv", "python -m venv .venv", "Create standard virtual environment in .venv", "Python"),
    ("Python: Activate Windows venv", ".\\.venv\\Scripts\\Activate.ps1", "Activate virtualenv in PowerShell", "PowerShell"),
    ("Python: Run Compile All Check", "python -m compileall -q .", "Verify byte-compilation syntax for entire project", "Python"),
    ("pip: Install Requirements", "pip install -r requirements.txt", "Install dependencies from requirements file", "pip"),
    ("pip: Freeze Requirements", "pip freeze > requirements.txt", "Export active environment packages to requirements file", "pip"),
    ("pip: Upgrade pip", "python -m pip install --upgrade pip", "Upgrade pip to latest version", "pip"),
    # Node.js & npm
    ("npm: Install Dependencies", "npm install", "Install all project npm dependencies", "npm"),
    ("npm: Run Dev Server", "npm run dev", "Launch modern dev server (Vite/Next/React)", "npm"),
    ("npm: Run Build", "npm run build", "Bundle production assets", "npm"),
    ("npm: Run Tests", "npm test", "Execute configured test runner (Jest/Vitest)", "npm"),
    ("Node: Check Version", "node -v && npm -v", "Print installed Node and npm versions", "Node.js"),
    # Docker
    ("Docker: Build Image", "docker build -t {{input:image_name}}:latest .", "Build container image from Dockerfile", "Docker"),
    ("Docker: Run Container with Port", "docker run -d -p {{port}}:{{port}} --name {{input:container_name}} {{input:image_name}}", "Run detached container with port mapping", "Docker"),
    ("Docker: Compose Up", "docker compose up -d", "Start containers in background using compose", "Docker"),
    ("Docker: View Container Logs", "docker logs -f --tail 100 {{input:container_name}}", "Follow live container logs", "Docker"),
    # Django & FastAPI
    ("Django: Run Dev Server", "python manage.py runserver {{port}}", "Start Django development server", "Django"),
    ("Django: Make Migrations", "python manage.py makemigrations", "Create database schema migration files", "Django"),
    ("Django: Apply Migrations", "python manage.py migrate", "Execute pending database migrations", "Django"),
    ("Django: Create Superuser", "python manage.py createsuperuser", "Create an administrative superuser account", "Django"),
    ("FastAPI: Run with Uvicorn Reload", "uvicorn main:app --reload --port {{port}}", "Launch FastAPI with hot reloading", "FastAPI"),
    # PowerShell & Linux
    ("PowerShell: Port Listening Check", "Get-NetTCPConnection -LocalPort {{port}}", "Inspect which process is bound to port", "PowerShell"),
    ("Linux: Port Listening Check", "lsof -i :{{port}}", "List open sockets bound to port", "Linux"),
]


class CommandRepository:
    """Handles persistence and query operations for safe terminal commands."""

    def __init__(self):
        self._ensure_default_seeds()

    def _ensure_default_seeds(self):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM terminal_commands")
            count = cursor.fetchone()[0]
            if count == 0:
                for name, cmd, desc, cat in DEFAULT_COMMAND_SEEDS:
                    cursor.execute(
                        """
                        INSERT INTO terminal_commands (name, command, description, category, is_favorite)
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (name, cmd, desc, cat),
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not seed default terminal commands: {e}")
        finally:
            conn.close()

    def create(self, cmd: TerminalCommand) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO terminal_commands (name, command, description, category, project_id, is_favorite)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cmd.name,
                    cmd.command,
                    cmd.description,
                    cmd.category or "General",
                    cmd.project_id,
                    1 if cmd.favorite else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_by_id(self, cmd_id: int) -> Optional[TerminalCommand]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM terminal_commands WHERE id = ?", (cmd_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_command(row)
        finally:
            conn.close()

    def get_all(
        self,
        category: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> List[TerminalCommand]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM terminal_commands WHERE 1=1"
            params = []

            if category and category != "All":
                query += " AND category = ?"
                params.append(category)

            if project_id is not None:
                query += " AND (project_id = ? OR project_id IS NULL)"
                params.append(project_id)

            query += " ORDER BY is_favorite DESC, name ASC"
            cursor.execute(query, params)
            return [self._row_to_command(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update(self, cmd: TerminalCommand) -> bool:
        if not cmd.id:
            return False
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE terminal_commands
                SET name = ?, command = ?, description = ?, category = ?, project_id = ?, is_favorite = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    cmd.name,
                    cmd.command,
                    cmd.description,
                    cmd.category,
                    cmd.project_id,
                    1 if cmd.favorite else 0,
                    cmd.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, cmd_id: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM terminal_commands WHERE id = ?", (cmd_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def toggle_favorite(self, cmd_id: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE terminal_commands SET is_favorite = (CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END) WHERE id = ?",
                (cmd_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def search(self, query: str, category: Optional[str] = None) -> List[TerminalCommand]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM terminal_commands WHERE 1=1"
            params = []

            if query.strip():
                wildcard = f"%{query.strip()}%"
                sql += " AND (name LIKE ? OR command LIKE ? OR description LIKE ?)"
                params.extend([wildcard, wildcard, wildcard])

            if category and category != "All":
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY is_favorite DESC, name ASC"
            cursor.execute(sql, params)
            return [self._row_to_command(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _row_to_command(row: sqlite3.Row) -> TerminalCommand:
        return TerminalCommand(
            id=row["id"],
            name=row["name"],
            command=row["command"],
            description=row["description"] or "",
            category=row["category"] or "General",
            project_id=row["project_id"],
            favorite=bool(row["is_favorite"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
