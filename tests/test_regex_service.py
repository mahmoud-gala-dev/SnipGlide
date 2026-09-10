import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
import unittest
from snipglide.services.regex_service import RegexService
from snipglide.models.saved_regex import SavedRegex
from snipglide.database.regex_repo import RegexRepository
from snipglide.database.connection import get_connection, init_db

class TestRegexServiceAndRepo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    # ─────────────────────────────────────────────────────────────
    # REGEX SERVICE TESTS
    # ─────────────────────────────────────────────────────────────
    def test_valid_regex_matching(self):
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        text = "Contact john@example.com or admin@snipglide.org for info."
        ok, matches, summary = RegexService.find_matches(pattern, text)
        self.assertTrue(ok)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["text"], "john@example.com")
        self.assertEqual(matches[1]["text"], "admin@snipglide.org")
        self.assertIn("2 مطابقة", summary)

    def test_invalid_regex_error_handling(self):
        # Unclosed parenthesis
        pattern = r"(abc[0-9]+"
        ok, matches, err = RegexService.find_matches(pattern, "abc123")
        self.assertFalse(ok)
        self.assertIn("خطأ", err)
        self.assertEqual(len(matches), 0)

        # Validate method directly
        is_valid, err_msg, pos = RegexService.validate(pattern)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err_msg)

    def test_groups_and_named_groups(self):
        pattern = r"(?P<first>\w+)\s+(?P<last>\w+)"
        text = "Alan Turing, Ada Lovelace"
        ok, matches, summary = RegexService.find_matches(pattern, text)
        self.assertTrue(ok)
        self.assertEqual(len(matches), 2)

        m1 = matches[0]
        self.assertEqual(m1["text"], "Alan Turing")
        self.assertEqual(m1["groups"][1], "Alan")
        self.assertEqual(m1["groups"][2], "Turing")
        self.assertEqual(m1["named_groups"], {"first": "Alan", "last": "Turing"})
        self.assertEqual(m1["start"], 0)
        self.assertEqual(m1["end"], 11)

        m2 = matches[1]
        self.assertEqual(m2["text"], "Ada Lovelace")
        self.assertEqual(m2["groups"][1], "Ada")
        self.assertEqual(m2["groups"][2], "Lovelace")
        self.assertEqual(m2["named_groups"], {"first": "Ada", "last": "Lovelace"})

    def test_flags_handling(self):
        # IGNORECASE
        ok, matches, _ = RegexService.find_matches(
            r"snipglide", "SnipGlide is awesome", flags_str="i"
        )
        self.assertTrue(ok)
        self.assertEqual(len(matches), 1)

        # MULTILINE
        text = "First line\nSecond line\nThird line"
        ok, matches, _ = RegexService.find_matches(
            r"^Second", text, flags_str="m"
        )
        self.assertTrue(ok)
        self.assertEqual(len(matches), 1)

        # DOTALL
        text = "<div>\nHello\n</div>"
        ok, matches, _ = RegexService.find_matches(
            r"<div>.*</div>", text, flags_str="s"
        )
        self.assertTrue(ok)
        self.assertEqual(len(matches), 1)

        # VERBOSE
        pattern = """
        \\d{3}   # area code
        -
        \\d{4}   # local number
        """
        ok, matches, _ = RegexService.find_matches(
            pattern, "Call 123-4567 today", flags_str="x"
        )
        self.assertTrue(ok)
        self.assertEqual(len(matches), 1)

    def test_replace_first_and_all(self):
        pattern = r"cat"
        text = "The cat sat on the cat mat."

        # Replace first
        ok1, res1 = RegexService.replace(pattern, text, "dog", replace_all=False)
        self.assertTrue(ok1)
        self.assertEqual(res1, "The dog sat on the cat mat.")

        # Replace all
        ok_all, res_all = RegexService.replace(pattern, text, "dog", replace_all=True)
        self.assertTrue(ok_all)
        self.assertEqual(res_all, "The dog sat on the dog mat.")

    def test_replacement_with_capture_groups(self):
        pattern = r"(\w+)\s+(\w+)"
        text = "Hello World"
        ok, res = RegexService.replace(pattern, text, r"\2, \1!")
        self.assertTrue(ok)
        self.assertEqual(res, "World, Hello!")

    def test_invalid_replacement_syntax_no_crash(self):
        pattern = r"(\w+)"
        text = "Hello"
        # Invalid group reference like \g<nonexistent> or \99
        ok, res = RegexService.replace(pattern, text, r"\g<99>")
        self.assertFalse(ok)
        self.assertIn("خطأ", res)

    def test_unicode_arabic_and_emojis(self):
        arabic_text = "مرحباً بك في سنيب جلايد SnipGlide 🚀 2026"
        pattern = r"[\u0600-\u06FF]+"
        ok, matches, _ = RegexService.find_matches(pattern, arabic_text)
        self.assertTrue(ok)
        self.assertGreaterEqual(len(matches), 2)
        self.assertEqual(matches[0]["text"], "مرحباً")

        # Emoji matching
        emoji_pattern = r"[\U00010000-\U0010ffff]"
        ok, matches, _ = RegexService.find_matches(emoji_pattern, arabic_text)
        self.assertTrue(ok)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["text"], "🚀")

    def test_zero_length_matches(self):
        pattern = r"\b"
        text = "hi"
        ok, matches, _ = RegexService.find_matches(pattern, text)
        self.assertTrue(ok)
        self.assertGreaterEqual(len(matches), 2)

    def test_large_text_performance(self):
        large_text = "Line of sample text with number 12345.\n" * 1000
        ok, matches, summary = RegexService.find_matches(r"\d+", large_text, max_matches=100)
        self.assertTrue(ok)
        self.assertEqual(len(matches), 100)  # Capped at max_matches for UI safety
        self.assertIn("100", summary)

    # ─────────────────────────────────────────────────────────────
    # REPOSITORY & DATABASE MIGRATION TESTS
    # ─────────────────────────────────────────────────────────────
    def test_saved_regex_repository_crud(self):
        # 1. Create
        item = SavedRegex(
            name="Email Matcher Test",
            pattern=r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
            description="RFC compliant email regex pattern",
            flags="i,m",
            replacement="[REDACTED]",
            favorite=False,
        )
        created_id = RegexRepository.create(item)
        self.assertIsNotNone(created_id)
        self.assertGreater(created_id, 0)

        # 2. Get by ID
        fetched = RegexRepository.get_by_id(created_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Email Matcher Test")
        self.assertEqual(fetched.flags, "i,m")
        self.assertEqual(fetched.favorite, False)

        # 3. Update
        fetched.name = "Updated Email Matcher"
        fetched.favorite = True
        ok = RegexRepository.update(fetched)
        self.assertTrue(ok)

        re_fetched = RegexRepository.get_by_id(created_id)
        self.assertEqual(re_fetched.name, "Updated Email Matcher")
        self.assertTrue(re_fetched.favorite)

        # 4. Toggle Favorite
        new_fav = RegexRepository.toggle_favorite(created_id)
        self.assertFalse(new_fav)
        self.assertFalse(RegexRepository.get_by_id(created_id).favorite)

        # 5. Search
        search_res = RegexRepository.search("Updated Email")
        self.assertTrue(any(r.id == created_id for r in search_res))

        search_fav_only = RegexRepository.search("Updated Email", favorites_only=True)
        self.assertFalse(any(r.id == created_id for r in search_fav_only))

        # 6. Delete
        del_ok = RegexRepository.delete(created_id)
        self.assertTrue(del_ok)
        self.assertIsNone(RegexRepository.get_by_id(created_id))

    def test_database_migration_indexes(self):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Verify saved_regexes table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='saved_regexes'")
            self.assertIsNotNone(cursor.fetchone())

            # Verify clipboard_history content_type column exists
            cursor.execute("PRAGMA table_info(clipboard_history)")
            col_names = [row["name"] for row in cursor.fetchall()]
            self.assertIn("content_type", col_names)
        finally:
            conn.close()


    def test_catastrophic_backtracking_timeout(self):
        # A classic ReDoS pattern: (a+)+$ on a string of 'a's ending with '!'
        pattern = r"(a+)+$"
        text = "a" * 28 + "!"
        ok, matches, msg = RegexService.find_matches(pattern, text, timeout=0.3)
        self.assertFalse(ok)
        self.assertIn("Catastrophic Backtracking", msg)


if __name__ == "__main__":
    unittest.main()
