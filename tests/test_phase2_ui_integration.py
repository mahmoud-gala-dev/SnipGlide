import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure single QApplication
app = QApplication.instance() or QApplication(sys.argv)

from snipglide.database.connection import init_db
from snipglide.database.clipboard_repo import clear_clipboard_history, add_clipboard_entry
from snipglide.database.regex_repo import RegexRepository, SavedRegex
from snipglide.database.search_repo import search_all, get_search_result_body
from snipglide.ui_qt.dev_tools.toolbox_page import DevToolboxPageQt
from snipglide.ui_qt.dev_tools.regex_widget import RegexPlaygroundWidget, SavedRegexLibraryDialog
from snipglide.ui_qt.clipboard_page import ClipboardPageQt, ClipboardItemWidget
from snipglide.ui_qt.command_palette import CommandPaletteQt
from snipglide.services.clipboard_content_detector import (
    TYPE_JSON, TYPE_URL, TYPE_JWT, TYPE_SQL, TYPE_CODE, TYPE_UUID
)

class TestPhase2UIIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        clear_clipboard_history()

    def tearDown(self):
        clear_clipboard_history()

    def test_dev_toolbox_tabs_includes_regex_playground(self):
        page = DevToolboxPageQt()
        # Verify at least 9 tabs total (expanded in later phases)
        self.assertGreaterEqual(page.tabs.count(), 9)
        # Verify Tab 8 is Regex Playground

        self.assertIn("Regex Playground", page.tabs.tabText(8))
        self.assertIsInstance(page.regex_widget, RegexPlaygroundWidget)

        # Check compatibility aliases
        self.assertIsNotNone(page.regex_pattern_input)
        self.assertIsNotNone(page.regex_test_input)
        self.assertIsNotNone(page.regex_replace_input)

    def test_regex_playground_widget_matching_and_replace(self):
        widget = RegexPlaygroundWidget()

        # Set test text and pattern
        widget.pattern_input.setText(r"(?P<user>\w+)@(?P<domain>\w+\.\w+)")
        widget.test_input.setPlainText("Send email to support@snipglide.com now.")
        widget.flag_i.setChecked(True)

        # Trigger immediate match
        widget._run_matching()

        # Check results
        self.assertEqual(widget.results_table.count(), 1)
        self.assertIn("1 مطابقة", widget.match_count_badge.text())

        # Test replacement
        widget.replace_input.setText(r"\g<user>@[REDACTED]")
        widget._replace_all()
        self.assertEqual(widget.replace_output.toPlainText(), "Send email to support@[REDACTED] now.")

    def test_regex_playground_invalid_pattern_no_crash(self):
        widget = RegexPlaygroundWidget()
        widget.pattern_input.setText(r"(broken[regex")
        widget.test_input.setPlainText("Some text")
        widget._run_matching()

        self.assertEqual(widget.results_table.count(), 0)
        self.assertIn("خطأ", widget.status_lbl.text())
        # Test text remains untouched
        self.assertEqual(widget.test_input.toPlainText(), "Some text")

    def test_command_palette_has_regex_actions(self):
        palette = CommandPaletteQt()
        action_names = [item[1] for item in palette._all_items if item[0] == "action"]
        self.assertIn("dev_regex", action_names)
        self.assertIn("dev_regex_library", action_names)

    def test_clipboard_page_ui_and_badges(self):
        # Insert diverse entries
        add_clipboard_entry('{"appName": "SnipGlide", "version": 2}')
        add_clipboard_entry("https://github.com/mahmoud-gala-dev/SnipGlide")
        add_clipboard_entry("SELECT * FROM snippets;")

        page = ClipboardPageQt()
        self.assertEqual(page.clip_list.count(), 3)

        # Top item is SQL
        top_item = page.clip_list.item(0)
        top_entry = top_item.data(Qt.UserRole)
        self.assertEqual(top_entry["content_type"], TYPE_SQL)

        # Search inside clipboard page
        page.search_edit.setText("github")
        self.assertEqual(page.clip_list.count(), 1)
        found_entry = page.clip_list.item(0).data(Qt.UserRole)
        self.assertEqual(found_entry["content_type"], TYPE_URL)

        # Clear search
        page.search_edit.setText("")
        self.assertEqual(page.clip_list.count(), 3)

    def test_unified_search_includes_regex_library(self):
        # Save a regex
        saved = SavedRegex(
            name="AlphaNumeric Slug Matcher",
            pattern=r"^[a-z0-9-]+$",
            description="Matches URL friendly slugs",
            flags="i",
            favorite=True,
        )
        saved_id = RegexRepository.create(saved)

        try:
            results = search_all("Slug Matcher")
            self.assertTrue(any(r["kind"] == "Regex" for r in results))
            regex_result = next(r for r in results if r["kind"] == "Regex")
            self.assertEqual(regex_result["title"], "AlphaNumeric Slug Matcher")

            body = get_search_result_body("Regex", str(saved_id))
            self.assertEqual(body, r"^[a-z0-9-]+$")
        finally:
            RegexRepository.delete(saved_id)


if __name__ == "__main__":
    unittest.main()
