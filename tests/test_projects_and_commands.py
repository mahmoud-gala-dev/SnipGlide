"""Unit tests for Developer Projects, Command Library, and Framework Detection."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from snipglide.database.command_repo import CommandRepository
from snipglide.database.connection import get_db_connection, initialize_database
from snipglide.database.project_repo import ProjectRepository
from snipglide.models.project_models import DeveloperProject, TerminalCommand
from snipglide.services.project_context import active_project_mgr
from snipglide.services.project_detector import detect_project_type


class TestProjectsAndCommands(unittest.TestCase):
    """Test suite for Phase 7: Developer Projects and Command Library."""

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="snipglide_test_p7_")
        self.proj_repo = ProjectRepository()
        self.cmd_repo = CommandRepository()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        active_project_mgr.set_active_project(None)

    def test_project_crud_and_search(self):
        # 1. Create
        p = DeveloperProject(
            name="SnipGlide Test",
            project_path=self.temp_dir,
            language="Python",
            framework="PySide6",
            description="Desktop app test project",
            favorite=False,
        )
        p_id = self.proj_repo.create(p)
        self.assertIsNotNone(p_id)

        # 2. Get by ID and Path
        fetched = self.proj_repo.get_by_id(p_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "SnipGlide Test")
        self.assertEqual(fetched.language, "Python")

        by_path = self.proj_repo.get_by_path(self.temp_dir)
        self.assertIsNotNone(by_path)
        self.assertEqual(by_path.id, p_id)

        # 3. Toggle favorite
        self.proj_repo.toggle_favorite(p_id)
        refetched = self.proj_repo.get_by_id(p_id)
        self.assertTrue(refetched.favorite)

        # 4. Search
        results = self.proj_repo.search("SnipGlide")
        self.assertTrue(any(item.id == p_id for item in results))

        # 5. Update
        refetched.name = "SnipGlide Updated"
        self.assertTrue(self.proj_repo.update(refetched))
        updated = self.proj_repo.get_by_id(p_id)
        self.assertEqual(updated.name, "SnipGlide Updated")

        # 6. Delete
        self.assertTrue(self.proj_repo.delete(p_id))
        self.assertIsNone(self.proj_repo.get_by_id(p_id))

    def test_command_crud_and_categories(self):
        # 1. Verify default seeds
        all_cmds = self.cmd_repo.get_all()
        self.assertGreater(len(all_cmds), 5)
        categories = {c.category for c in all_cmds}
        self.assertIn("Git", categories)
        self.assertIn("Python", categories)

        # 2. Create custom command
        cmd = TerminalCommand(
            name="pytest verbose",
            command="pytest -v -s",
            description="Run pytest verbosely",
            category="Python",
            favorite=False,
        )
        c_id = self.cmd_repo.create(cmd)
        self.assertIsNotNone(c_id)

        # 3. Filter by category
        py_cmds = self.cmd_repo.get_all(category="Python")
        self.assertTrue(any(c.id == c_id for c in py_cmds))

        # 4. Search
        search_res = self.cmd_repo.search("pytest verbose")
        self.assertTrue(any(c.id == c_id for c in search_res))

        # 5. Toggle favorite
        self.cmd_repo.toggle_favorite(c_id)
        fetched = self.cmd_repo.get_by_id(c_id)
        self.assertTrue(fetched.favorite)

        # 6. Delete
        self.assertTrue(self.cmd_repo.delete(c_id))
        self.assertIsNone(self.cmd_repo.get_by_id(c_id))

    def test_project_auto_detection(self):
        # 1. Django detection
        d1 = tempfile.mkdtemp(prefix="django_")
        try:
            with open(os.path.join(d1, "manage.py"), "w") as f:
                f.write("#!/usr/bin/env python\n")
            lang, fw = detect_project_type(d1)
            self.assertEqual(lang, "Python")
            self.assertEqual(fw, "Django")
        finally:
            shutil.rmtree(d1, ignore_errors=True)

        # 2. FastAPI detection
        d2 = tempfile.mkdtemp(prefix="fastapi_")
        try:
            with open(os.path.join(d2, "requirements.txt"), "w") as f:
                f.write("fastapi>=0.100.0\nuvicorn\n")
            lang, fw = detect_project_type(d2)
            self.assertEqual(lang, "Python")
            self.assertEqual(fw, "FastAPI")
        finally:
            shutil.rmtree(d2, ignore_errors=True)

        # 3. TypeScript / Next.js detection
        d3 = tempfile.mkdtemp(prefix="nextjs_")
        try:
            with open(os.path.join(d3, "package.json"), "w") as f:
                f.write('{"dependencies": {"next": "14.0.0", "react": "18.0.0"}}')
            with open(os.path.join(d3, "tsconfig.json"), "w") as f:
                f.write('{}')
            lang, fw = detect_project_type(d3)
            self.assertEqual(lang, "TypeScript")
            self.assertEqual(fw, "Next.js")
        finally:
            shutil.rmtree(d3, ignore_errors=True)

        # 4. Docker fallback
        d4 = tempfile.mkdtemp(prefix="docker_")
        try:
            with open(os.path.join(d4, "Dockerfile"), "w") as f:
                f.write("FROM alpine\n")
            lang, fw = detect_project_type(d4)
            self.assertEqual(fw, "Docker Container")
        finally:
            shutil.rmtree(d4, ignore_errors=True)

    def test_active_project_manager(self):
        p = DeveloperProject(id=999, name="TestContext", project_path="C:/dummy")
        notifications = []

        def listener(proj):
            notifications.append(proj.name if proj else None)

        active_project_mgr.add_listener(listener)
        active_project_mgr.set_active_project(p)

        self.assertEqual(active_project_mgr.active_project.name, "TestContext")
        self.assertIn("TestContext", notifications)

        active_project_mgr.set_active_project(None)
        self.assertIsNone(active_project_mgr.active_project)
        self.assertIn(None, notifications)
        active_project_mgr.remove_listener(listener)


if __name__ == "__main__":
    unittest.main()
