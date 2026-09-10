import sys
sys.stdout.reconfigure(encoding='utf-8')
import os

from PySide6.QtWidgets import QApplication
from snipglide.ui_qt.dev_toolbox_page import DevToolboxPageQt
from snipglide.services.dev_tools_service import (
    JsonTools, Base64Tools, UrlTools, JwtTools,
    UuidTools, TimestampTools, HashTools, TextUtils
)

def test_phase1_ui():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    print("==> Starting Phase 1 Developer Toolbox UI & Integration Test...")

    # 1. Instantiate Page
    page = DevToolboxPageQt()
    assert page.tabs.count() == 8, f"Expected 8 tabs, found {page.tabs.count()}"
    print("✓ DevToolboxPageQt instantiated with all 8 sub-tools successfully")

    # 2. Test JSON Tool in UI
    page.json_input.setPlainText('{"app": "SnipGlide", "code": 2026}')
    page._json_beautify()
    assert '"app": "SnipGlide"' in page.json_output.toPlainText(), "UI JSON Beautify failed"
    page._json_minify()
    assert '{"app":"SnipGlide","code":2026}' in page.json_output.toPlainText(), "UI JSON Minify failed"
    print("✓ UI JSON Tab interaction verified")

    # 3. Test Base64 Tool in UI
    page.b64_input.setPlainText("Hello SnipGlide Pro")
    page._b64_encode()
    encoded = page.b64_output.toPlainText()
    assert len(encoded) > 0, "UI Base64 Encode failed"
    page.b64_input.setPlainText(encoded)
    page._b64_decode()
    assert page.b64_output.toPlainText() == "Hello SnipGlide Pro", "UI Base64 Decode failed"
    print("✓ UI Base64 Tab interaction verified")

    # 4. Test URL Tool in UI
    page.url_input.setPlainText("hello world & python")
    page._url_encode()
    assert "hello%20world%20%26%20python" in page.url_output.toPlainText(), "UI URL Encode failed"
    print("✓ UI URL Tab interaction verified")

    # 5. Test UUID Tool in UI
    page._uuid_generate_single()
    assert len(page.uuid_output.toPlainText()) == 36, "UI UUID Single failed"
    page.uuid_spin.setValue(3)
    page._uuid_generate_batch()
    lines = [l for l in page.uuid_output.toPlainText().splitlines() if l.strip()]
    assert len(lines) == 3, "UI UUID Batch failed"
    print("✓ UI UUID Tab interaction verified")

    # 6. Test Timestamp Tool in UI
    page.ts_input_epoch.setText("1700000000")
    page._ts_convert_epoch()
    assert "1700000000" in page.ts_output.toPlainText(), "UI Timestamp Epoch failed"
    print("✓ UI Timestamp Tab interaction verified")

    # 7. Test Hash Tool in UI
    page.hash_input.setPlainText("TestPassword123!")
    assert len(page.hash_fields["md5"].text()) == 32, "UI Hash MD5 failed"
    assert len(page.hash_fields["sha256"].text()) == 64, "UI Hash SHA-256 failed"
    print("✓ UI Hash Tab interaction verified")

    # 8. Test Text Utilities Tool in UI
    page.text_editor.setPlainText("make this pascal case")
    page._apply_text_transform(TextUtils.to_pascal_case)
    assert page.text_editor.toPlainText() == "MakeThisPascalCase", "UI Text PascalCase failed"
    print("✓ UI Text Utilities Tab interaction verified")

    print("\n🎉 ALL PHASE 1 UI & INTEGRATION TESTS PASSED 100%! 🎉")

if __name__ == "__main__":
    test_phase1_ui()
