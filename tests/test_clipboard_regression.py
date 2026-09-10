import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from snipglide.database.clipboard_repo import (
    add_clipboard_entry, get_clipboard_history, get_clipboard_entries,
    get_clipboard_history_count, delete_clipboard_entry, clear_clipboard_history,
    search_clipboard_entries, MAX_CLIPBOARD_HISTORY
)
from snipglide.services.clipboard_content_detector import (
    ClipboardContentDetector, TYPE_JSON, TYPE_URL, TYPE_PLAIN_TEXT
)

class TestClipboardRegression(unittest.TestCase):

    def setUp(self):
        clear_clipboard_history()

    def tearDown(self):
        clear_clipboard_history()

    def test_capture_and_deduplication(self):
        # 1. Add entry
        add_clipboard_entry("https://example.com/test1")
        self.assertEqual(get_clipboard_history_count(), 1)

        # 2. Add second entry
        add_clipboard_entry('{"key": "value"}')
        self.assertEqual(get_clipboard_history_count(), 2)

        # 3. Add duplicate of first entry - should deduplicate and bump to top
        add_clipboard_entry("https://example.com/test1")
        self.assertEqual(get_clipboard_history_count(), 2)

        items = get_clipboard_history(limit=5)
        self.assertEqual(items[0], "https://example.com/test1")
        self.assertEqual(items[1], '{"key": "value"}')

    def test_content_type_automatic_tagging(self):
        add_clipboard_entry('{"user": "alice", "age": 30}')
        add_clipboard_entry("https://snipglide.dev")

        entries = get_clipboard_entries(limit=5)
        self.assertEqual(len(entries), 2)
        # Top entry is URL
        self.assertEqual(entries[0]["content_type"], TYPE_URL)
        # Second is JSON
        self.assertEqual(entries[1]["content_type"], TYPE_JSON)

    def test_search_clipboard(self):
        add_clipboard_entry("SELECT * FROM users WHERE active = 1;")
        add_clipboard_entry("npm run build")
        add_clipboard_entry("git checkout -b feature/phase2")

        res, total = search_clipboard_entries("git")
        self.assertEqual(total, 1)
        self.assertEqual(len(res), 1)
        self.assertIn("feature/phase2", res[0]["content"])

        res_none, total_none = search_clipboard_entries("nonexistent_string_123")
        self.assertEqual(total_none, 0)
        self.assertEqual(len(res_none), 0)

    def test_delete_entry(self):
        add_clipboard_entry("Item To Be Deleted")
        add_clipboard_entry("Item To Keep")
        self.assertEqual(get_clipboard_history_count(), 2)

        deleted = delete_clipboard_entry("Item To Be Deleted")
        self.assertTrue(deleted)
        self.assertEqual(get_clipboard_history_count(), 1)
        items = get_clipboard_history()
        self.assertNotIn("Item To Be Deleted", items)
        self.assertIn("Item To Keep", items)

    def test_clear_all_history(self):
        for i in range(5):
            add_clipboard_entry(f"Sample item {i}")
        self.assertEqual(get_clipboard_history_count(), 5)

        clear_clipboard_history()
        self.assertEqual(get_clipboard_history_count(), 0)
        self.assertEqual(len(get_clipboard_history()), 0)

    def test_pagination(self):
        for i in range(15):
            add_clipboard_entry(f"Paginated item #{i:02d}")

        total = get_clipboard_history_count()
        self.assertEqual(total, 15)

        page1 = get_clipboard_entries(limit=5, offset=0)
        self.assertEqual(len(page1), 5)

        page2 = get_clipboard_entries(limit=5, offset=5)
        self.assertEqual(len(page2), 5)

        # Disjoint
        page1_ids = {e["id"] for e in page1}
        page2_ids = {e["id"] for e in page2}
        self.assertTrue(page1_ids.isdisjoint(page2_ids))

    def test_max_history_cap(self):
        # Exceed MAX_CLIPBOARD_HISTORY
        for i in range(MAX_CLIPBOARD_HISTORY + 10):
            add_clipboard_entry(f"Overflow item {i}")

        total = get_clipboard_history_count()
        self.assertLessEqual(total, MAX_CLIPBOARD_HISTORY)


if __name__ == "__main__":
    unittest.main()
