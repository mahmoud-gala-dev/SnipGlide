"""Unit tests for Phase 8 Unified Developer Search."""
from __future__ import annotations

import unittest

from snipglide.database.api_repo import ApiRepository
from snipglide.database.command_repo import CommandRepository
from snipglide.database.connection import get_connection, initialize_database
from snipglide.database.project_repo import ProjectRepository
from snipglide.database.search_repo import get_search_result_body, search_all
from snipglide.models.api_request import ApiRequest
from snipglide.models.project_models import DeveloperProject, TerminalCommand


class TestUnifiedSearch(unittest.TestCase):
    """Test suite for unified global search across all 10 sources."""

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        # Insert test data across multiple tables
        self.api_repo = ApiRepository()
        self.proj_repo = ProjectRepository()
        self.cmd_repo = CommandRepository()

        import uuid

        # Add a test project with unique path
        unique_path = f"/dummy/unified/test_{uuid.uuid4().hex[:8]}"

        self.test_proj_path = unique_path
        self.test_proj_id = self.proj_repo.create(
            DeveloperProject(
                name="UnifiedSearchTestProject",
                project_path=unique_path,
                language="Python",
                framework="Django",
                favorite=True,
            )
        )

        # Add a test API request
        self.test_api_id = self.api_repo.add_request(
            ApiRequest(
                name="UnifiedSearchTestEndpoint",
                method="GET",
                url="https://api.test.local/v1/search",
                is_favorite=True,
            )
        )


        # Add a test command
        self.test_cmd_id = self.cmd_repo.create(
            TerminalCommand(
                name="unified_custom_cmd",
                command="echo 'unified test'",
                description="Special command description",
                category="Custom",
            )
        )

    def tearDown(self):
        try:
            self.proj_repo.delete(self.test_proj_id)
            self.api_repo.delete_request(self.test_api_id)
            self.cmd_repo.delete(self.test_cmd_id)
        except Exception:
            pass

    def test_empty_query(self):
        self.assertEqual(search_all(""), [])
        self.assertEqual(search_all("   "), [])

    def test_multi_source_search(self):
        # Search for project
        res_proj = search_all("UnifiedSearchTestProject")
        self.assertTrue(any(r["kind"] == "Project" and "UnifiedSearchTestProject" in r["title"] for r in res_proj))

        # Search for API request
        res_api = search_all("UnifiedSearchTestEndpoint")
        self.assertTrue(any(r["kind"] == "API Request" and "UnifiedSearchTestEndpoint" in r["title"] for r in res_api))

        # Search for Command
        res_cmd = search_all("unified_custom_cmd")
        self.assertTrue(any(r["kind"] == "Command" and "unified_custom_cmd" in r["title"] for r in res_cmd))

    def test_search_ranking(self):
        # Exact match should have a higher score than partial contains
        results = search_all("UnifiedSearchTestProject")
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertEqual(top["kind"], "Project")
        self.assertGreaterEqual(top["score"], 100)

    def test_unicode_and_arabic_search(self):
        # Insert Arabic chat note
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chat_notes (content) VALUES (?)", ("تجربة البحث الموحد بالعربية 123",))
            note_id = cursor.lastrowid
            conn.commit()

        try:
            results = search_all("بالعربية")
            self.assertTrue(any(r["kind"] == "Chat Note" and "بالعربية" in r["body"] for r in results))
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM chat_notes WHERE id = ?", (note_id,))
                conn.commit()

    def test_get_search_result_body(self):
        # Test body retrieval for Project and Command
        proj_path = get_search_result_body("Project", str(self.test_proj_id))
        self.assertEqual(proj_path, self.test_proj_path)

        cmd_body = get_search_result_body("Command", str(self.test_cmd_id))
        self.assertEqual(cmd_body, "echo 'unified test'")


if __name__ == "__main__":
    unittest.main()
