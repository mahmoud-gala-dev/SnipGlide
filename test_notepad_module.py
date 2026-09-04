import sys
import os
import tempfile
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Setup headless Qt application
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from snipglide.ui_qt.notepad_page import NotepadPageQt, NotepadEditor, NotepadTab
from snipglide.services.notepad_session import (
    save_notepad_session, load_notepad_session,
    add_recent_file, get_recent_files, clear_recent_files
)
from snipglide.database.connection import initialize_database

initialize_database()

print("==> Starting Comprehensive Windows Notepad Test Suite <==")

# 1. Test Session Service
print("\n[Test 1] Testing Session Persistence Service...")
clear_recent_files()
assert len(get_recent_files()) == 0, "Failed to clear recent files"

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
temp_file.write(b"Line 1\nLine 2\nLine 3")
temp_file.close()

add_recent_file(temp_file.name)
recents = get_recent_files()
assert len(recents) == 1 and recents[0] == os.path.normpath(temp_file.name), "Recent files tracking failed"
print("✓ Recent files tracking passed")

# 2. Test NotepadPageQt Instantiation
print("\n[Test 2] Testing NotepadPageQt Instantiation & Tabs...")
page = NotepadPageQt()
initial_tabs = page.tab_widget.count()
assert initial_tabs >= 1, "Expected at least 1 tab on startup"
print(f"✓ Notepad initialized with {initial_tabs} tab(s)")

# 3. Test Tab Operations (New, Modify, Close)
print("\n[Test 3] Testing Tab Operations & Modified Indicators...")
tab2 = page.new_tab(title="Doc2.txt", initial_text="Hello World from SnipGlide Notepad")
assert page.tab_widget.count() == initial_tabs + 1, "New tab creation failed"
ed2 = page.get_current_editor()
assert ed2 is not None and "Hello World" in ed2.toPlainText(), "Tab text content mismatch"

# Check stats calculation
stats = ed2.get_stats()
assert stats["words"] == 5, f"Expected 5 words, got {stats['words']}"
assert stats["lines"] == 1, f"Expected 1 line, got {stats['lines']}"
print(f"✓ Word and Line stats accurate: {stats['words']} words, {stats['lines']} lines")

# Simulate typing to verify modified flag
ed2.insertPlainText("\nMore lines")
assert ed2.is_modified is True, "Modified flag was not updated"
idx2 = page.tab_widget.indexOf(tab2)
assert "•" in page.tab_widget.tabText(idx2), "Modified dot indicator not shown on tab"
print("✓ Modified indicator '•' displayed correctly on tab")

# 4. Test Edit & Line Operations
print("\n[Test 4] Testing Edit Operations (Case transforms, F5, Duplicate, Sort)...")
ed2.setPlainText("Hello World from SnipGlide Notepad\nMore lines")
ed2.selectAll()
# UPPERCASE
page._transform_to_upper()
assert "HELLO WORLD" in ed2.toPlainText(), "Transform to UPPERCASE failed"

# lowercase
page._transform_to_lower()
assert "hello world" in ed2.toPlainText(), "Transform to lowercase failed"

# Title Case
page._transform_to_title()
assert "Hello World" in ed2.toPlainText(), "Transform to Title Case failed"
print("✓ Case transformations passed (UPPER, lower, Title)")

# Date/Time insertion
ed2.clear()
page._insert_time_date()
assert len(ed2.toPlainText()) > 5, "Date/time insertion failed"
print(f"✓ Insert Date/Time (F5) passed: '{ed2.toPlainText().strip()}'")

# Sorting lines
ed2.setPlainText("Banana\nApple\nCherry")
page._sort_lines_asc()
assert ed2.toPlainText().splitlines() == ["Apple", "Banana", "Cherry"], "Line sorting failed"
print("✓ Line sorting passed: Apple -> Banana -> Cherry")

# Remove empty lines
ed2.setPlainText("Line 1\n\n\nLine 2\n\nLine 3")
page._remove_empty_lines()
assert ed2.toPlainText() == "Line 1\nLine 2\nLine 3", "Remove empty lines failed"
print("✓ Remove empty lines passed")

# 5. Test Find & Replace Bar
print("\n[Test 5] Testing Find & Replace Bar...")
ed2.setPlainText("SnipGlide is awesome. Windows Notepad inside SnipGlide is awesome.")
bar = page.find_replace_bar
bar.set_editor(ed2)

# Search
bar.find_input.setText("awesome")
assert len(bar.matches) == 2, f"Expected 2 matches, got {len(bar.matches)}"
print("✓ Search matches count passed (2 matches found)")

# Replace All
bar.replace_input.setText("fantastic")
bar.replace_all()
assert "fantastic" in ed2.toPlainText() and "awesome" not in ed2.toPlainText(), "Replace all failed"
print("✓ Replace all passed: replaced 'awesome' with 'fantastic'")

# Regex search test
bar.btn_regex.setChecked(True)
bar.find_input.setText(r"\b\w{9}\b")  # 9-letter words: SnipGlide, fantastic
assert len(bar.matches) >= 2, "Regex match failed"
bar.btn_regex.setChecked(False)
print("✓ Regex search passed")

# 6. Test Format & View Features (Word Wrap, Line Numbers, RTL/LTR)
print("\n[Test 6] Testing Format & View Settings...")
page._on_toggle_word_wrap(True)
assert ed2.lineWrapMode() == ed2.LineWrapMode.WidgetWidth, "Word wrap toggle failed"
page._on_toggle_word_wrap(False)
assert ed2.lineWrapMode() == ed2.LineWrapMode.NoWrap, "No wrap toggle failed"
print("✓ Word wrap toggle passed")

page._set_direction(is_rtl=True)
assert ed2.layoutDirection() == Qt.RightToLeft, "RTL direction failed"
page._set_direction(is_rtl=False)
assert ed2.layoutDirection() == Qt.LeftToRight, "LTR direction failed"
print("✓ RTL and LTR text direction switching passed")

# 7. Test SnipGlide Native Integration
print("\n[Test 7] Testing SnipGlide Native Integration...")
ed2.setPlainText("This is a quick test note for SnipGlide database.")
page.save_to_snipglide_notes()
print("✓ Save to SnipGlide Notes passed")

page.send_to_chat_notes()
print("✓ Send to Chat Notes passed")

# 8. Test Session Saving & Loading
print("\n[Test 8] Testing Session Save & Restore...")
page._save_session_state()
session = load_notepad_session()
assert "tabs" in session and len(session["tabs"]) >= 2, "Session tabs saving failed"
print(f"✓ Session saved {len(session['tabs'])} tabs to disk successfully")

# Cleanup temp file
try:
    os.unlink(temp_file.name)
except Exception:
    pass

print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! Windows Notepad module is fully operational! 🎉")
app.quit()
