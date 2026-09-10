import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox
from PySide6.QtCore import Qt

# Ensure single QApplication
app = QApplication.instance() or QApplication(sys.argv)

from snipglide.database.connection import init_db
from snipglide.models.snippet import Snippet
from snipglide.database.snippet_repo import (
    add_snippet, get_snippet_by_id, update_snippet, delete_snippet, get_snippets_for_list
)
from snipglide.engine.parser import (
    extract_form_fields, replace_form_variables, parse_variables,
    get_form_fields, replace_form_fields, _detect_active_filename, _detect_active_project
)
from snipglide.ui_qt.dialogs.snippet_form_dialog import SnippetFormDialog
from snipglide.ui_qt.snippet_editor_view import SnippetEditorViewQt


class TestSmartSnippetsEngine(unittest.TestCase):
    """Test engine parsing, form variable extraction, and dynamic placeholders."""

    def test_extract_form_fields_basic_input(self):
        text = "def {{input:function_name}}():\n    pass"
        fields = extract_form_fields(text)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["name"], "function_name")
        self.assertEqual(fields[0]["type"], "input")
        self.assertEqual(fields[0]["default"], "")

    def test_extract_form_fields_input_with_default(self):
        text = "class {{input:class_name:UserModel}}:\n    pass"
        fields = extract_form_fields(text)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["name"], "class_name")
        self.assertEqual(fields[0]["type"], "input")
        self.assertEqual(fields[0]["default"], "UserModel")

    def test_extract_form_fields_choice(self):
        text = "fetch(url, { method: '{{choice:http_method:GET,POST,PUT,PATCH,DELETE}}' })"
        fields = extract_form_fields(text)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["name"], "http_method")
        self.assertEqual(fields[0]["type"], "choice")
        self.assertEqual(fields[0]["options"], ["GET", "POST", "PUT", "PATCH", "DELETE"])

    def test_extract_form_fields_deduplication(self):
        text = "def {{input:name}}():\n    print('Inside {{input:name}}')\n    return '{{input:name}}'"
        fields = extract_form_fields(text)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["name"], "name")

    def test_extract_form_fields_legacy_and_mixed(self):
        text = "Hello {{form:user_name}}, please use {{choice:action:login,signup}} with role {{input:role:admin}}!"
        fields = extract_form_fields(text)
        self.assertEqual(len(fields), 3)
        self.assertEqual(fields[0]["name"], "user_name")
        self.assertEqual(fields[1]["name"], "action")
        self.assertEqual(fields[2]["name"], "role")

    def test_replace_form_variables(self):
        text = "def {{input:fn_name}}():\n    # Method: {{choice:method:GET,POST}}\n    return '{{input:fn_name}}'"
        answers = {
            "fn_name": "get_user_profile",
            "method": "GET"
        }
        res = replace_form_variables(text, answers)
        expected = "def get_user_profile():\n    # Method: GET\n    return 'get_user_profile'"
        self.assertEqual(res, expected)

    def test_backward_compatibility_form_fields(self):
        text = "User {{form:first_name}} {{form:last_name}}"
        fields = get_form_fields(text)
        self.assertEqual(fields, ["first_name", "last_name"])
        res = replace_form_fields(text, {"first_name": "Mahmoud", "last_name": "Gala"})
        self.assertEqual(res, "User Mahmoud Gala")

    def test_extract_filename_from_title(self):
        self.assertEqual(_detect_active_filename("snippet_repo.py - SnipGlide - Visual Studio Code"), "snippet_repo.py")
        self.assertEqual(_detect_active_filename("index.html - Google Chrome"), "index.html")
        self.assertEqual(_detect_active_filename("notes.txt - Notepad"), "notes.txt")
        self.assertEqual(_detect_active_filename("Untitled"), "")
        self.assertEqual(_detect_active_project("snippet_repo.py - SnipGlide - Visual Studio Code"), "SnipGlide")

    def test_parse_variables_dynamic(self):
        text = "UUID: {{uuid}}, DATE: {{date}}, TIME: {{time}}, CLIPBOARD: {{clipboard}}"
        rendered = parse_variables(text)
        self.assertNotIn("{{uuid}}", rendered)
        self.assertNotIn("{{date}}", rendered)
        self.assertNotIn("{{time}}", rendered)
        self.assertNotIn("{{clipboard}}", rendered)
        self.assertIn("UUID: ", rendered)
        self.assertIn("DATE: ", rendered)

    def test_parse_variables_filename_and_project(self):
        text = "File: {{filename}}, Project: {{project}}, Selection: {{selection}}"
        rendered = parse_variables(text)
        self.assertNotIn("{{filename}}", rendered)
        self.assertNotIn("{{project}}", rendered)
        self.assertNotIn("{{selection}}", rendered)


class TestSmartSnippetsDatabase(unittest.TestCase):
    """Test database persistence for snippet_type and language."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.created_ids = []

    def tearDown(self):
        for sid in self.created_ids:
            try:
                delete_snippet(sid)
            except Exception:
                pass

    def test_add_and_retrieve_code_snippet(self):
        snip = Snippet(
            shortcut=":pyfn",
            replacement="def {{input:name}}():\n    pass",
            description="Python Function Snippet",
            snippet_type="Code",
            language="Python"
        )
        sid = add_snippet(snip)
        self.assertIsNotNone(sid)
        self.created_ids.append(sid)

        fetched = get_snippet_by_id(sid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.shortcut, ":pyfn")
        self.assertEqual(fetched.snippet_type, "Code")
        self.assertEqual(fetched.language, "Python")

    def test_update_snippet_type_and_language(self):
        snip = Snippet(
            shortcut=":testtype",
            replacement="plain text",
            snippet_type="Text",
            language="Plain Text"
        )
        sid = add_snippet(snip)
        self.created_ids.append(sid)

        fetched = get_snippet_by_id(sid)
        self.assertEqual(fetched.snippet_type, "Text")

        # Update to Code Snippet TypeScript
        fetched.snippet_type = "Code"
        fetched.language = "TypeScript"
        fetched.replacement = "const greet = (name: string): string => `Hello ${name}`;"
        update_snippet(fetched)

        updated = get_snippet_by_id(sid)
        self.assertEqual(updated.snippet_type, "Code")
        self.assertEqual(updated.language, "TypeScript")
        self.assertIn("const greet", updated.replacement)

    def test_get_snippets_for_list_preserves_type(self):
        snip = Snippet(
            shortcut=":sqlselect",
            replacement="SELECT * FROM {{input:table_name}};",
            snippet_type="Code",
            language="SQL"
        )
        sid = add_snippet(snip)
        self.created_ids.append(sid)

        snippets = get_snippets_for_list(query=":sqlselect")
        matching = [s for s in snippets if s.id == sid]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].snippet_type, "Code")
        self.assertEqual(matching[0].language, "SQL")


class TestSmartSnippetsUI(unittest.TestCase):
    """Test SnippetFormDialog and SnippetEditorViewQt controls."""

    def test_snippet_form_dialog_inputs(self):
        fields = [
            {"name": "table_name", "type": "input", "default": "users"},
            {"name": "action", "type": "choice", "options": ["SELECT", "INSERT", "UPDATE", "DELETE"]}
        ]
        dialog = SnippetFormDialog(fields, snippet_shortcut=":sql_action")
        self.assertIn("table_name", dialog.inputs)
        self.assertIn("action", dialog.inputs)

        # Check types of generated inputs
        self.assertIsInstance(dialog.inputs["table_name"], QLineEdit)
        self.assertEqual(dialog.inputs["table_name"].text(), "users")
        self.assertIsInstance(dialog.inputs["action"], QComboBox)
        self.assertEqual(dialog.inputs["action"].count(), 4)
        self.assertEqual(dialog.inputs["action"].currentText(), "SELECT")

        # Test value retrieval
        dialog.inputs["table_name"].setText("orders")
        dialog.inputs["action"].setCurrentText("UPDATE")
        values = dialog.get_values()
        self.assertEqual(values["table_name"], "orders")
        self.assertEqual(values["action"], "UPDATE")

    def test_snippet_editor_view_type_and_lang_controls(self):
        view = SnippetEditorViewQt()

        # Check UI components existence
        self.assertIsNotNone(view.type_combo)
        self.assertIsNotNone(view.lang_combo)
        self.assertEqual(view.type_combo.count(), 2)
        self.assertIn("Python", [view.lang_combo.itemText(i) for i in range(view.lang_combo.count())])

        # Test switching to Code
        idx_code = view.type_combo.findData("Code")
        view.type_combo.setCurrentIndex(idx_code)
        self.assertTrue(view.lang_combo.isEnabled())
        self.assertEqual(view.content_edit.font().family(), "Consolas")

        # Test switching back to Text
        idx_text = view.type_combo.findData("Text")
        view.type_combo.setCurrentIndex(idx_text)
        self.assertFalse(view.lang_combo.isEnabled())

    def test_snippet_editor_new_snippet_with_code_args(self):
        view = SnippetEditorViewQt()
        view.new_snippet(initial_content="console.log('hi');", is_code=True, language="JavaScript")
        self.assertEqual(view.type_combo.currentData(), "Code")
        self.assertEqual(view.lang_combo.currentText(), "JavaScript")
        self.assertEqual(view.content_edit.toPlainText(), "console.log('hi');")


class TestSmartSnippetsExpansionCallback(unittest.TestCase):
    """Test ExpansionEngine interaction with form prompts callback."""

    def test_expand_with_form_prompt_success(self):
        from unittest.mock import MagicMock
        from snipglide.engine.listener import ExpansionEngine

        prompt_called = []
        def fake_prompt(snippet, fields):
            prompt_called.append((snippet.shortcut, fields))
            return {"func_name": "calc_total", "method": "POST"}

        engine = ExpansionEngine(
            settings_provider=lambda: {"enabled": True},
            form_prompt_callback=fake_prompt
        )
        engine.controller = MagicMock()

        snip = Snippet(
            id=9999,
            shortcut=":api",
            replacement="fetch('/api/{{input:func_name}}', { method: '{{choice:method:GET,POST}}' })",
            enabled=True
        )

        engine._expand(":api", snip)
        self.assertEqual(len(prompt_called), 1)
        self.assertEqual(prompt_called[0][0], ":api")
        self.assertEqual(len(prompt_called[0][1]), 2)

    def test_expand_with_form_prompt_cancelled(self):
        from unittest.mock import MagicMock
        from snipglide.engine.listener import ExpansionEngine

        def cancel_prompt(snippet, fields):
            return None  # user cancelled

        engine = ExpansionEngine(
            settings_provider=lambda: {"enabled": True},
            form_prompt_callback=cancel_prompt
        )
        engine.controller = MagicMock()
        engine.buffer = "prefix :api"

        snip = Snippet(
            id=9998,
            shortcut=":api",
            replacement="const x = '{{input:val}}';",
            enabled=True
        )

        engine._expand(":api", snip)
        # Should clear buffer and abort without pressing keys
        self.assertEqual(engine.buffer, "")
        engine.controller.press.assert_not_called()


if __name__ == "__main__":
    unittest.main()
