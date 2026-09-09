import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import QRect

from snipglide.database.connection import initialize_database
from snipglide.database.screenshot_repo import (
    add_screenshot, get_all_screenshots, get_screenshot_by_id,
    toggle_favorite_screenshot, delete_screenshot, get_screenshots_count
)
from snipglide.services.screenshot_service import ScreenshotService
from snipglide.ui_qt.screenshots_page import ScreenshotsPageQt
from snipglide.ui_qt.snipping_overlay import SnippingOverlayWidget

def run_tests():
    print("=== Starting Screenshot Feature Tests ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 1. Initialize DB
    initialize_database()
    initial_count = get_screenshots_count()
    print(f"[PASS] DB initialized. Current screenshots count: {initial_count}")

    # 2. Test DB repo operations
    test_file = str(BASE_DIR / "test_screen.png")
    # create dummy image
    pix = QPixmap(100, 100)
    pix.fill(QColor("blue"))
    pix.save(test_file, "PNG")

    shot_id = add_screenshot(
        file_path=test_file,
        filename="test_screen.png",
        capture_type="full",
        width=100,
        height=100,
        file_size=os.path.getsize(test_file),
        note="Test screenshot"
    )
    assert shot_id is not None and shot_id > 0, "Failed to insert screenshot"
    print(f"[PASS] Added screenshot with ID: {shot_id}")

    shot = get_screenshot_by_id(shot_id)
    assert shot is not None, "Failed to retrieve screenshot"
    assert shot.width == 100 and shot.height == 100
    assert not shot.is_favorite
    print("[PASS] Retrieved screenshot matching attributes.")

    # Toggle favorite
    new_fav = toggle_favorite_screenshot(shot_id)
    assert new_fav is True
    assert get_screenshot_by_id(shot_id).is_favorite is True
    print("[PASS] Favorite toggled successfully.")

    # List screenshots
    all_shots = get_all_screenshots()
    assert any(s.id == shot_id for s in all_shots)
    print(f"[PASS] get_all_screenshots returned {len(all_shots)} items.")

    # Delete screenshot
    del_res = delete_screenshot(shot_id, delete_file=True)
    assert del_res is True
    assert not os.path.exists(test_file)
    assert get_screenshot_by_id(shot_id) is None
    print("[PASS] Screenshot deleted cleanly from DB and disk.")

    # 3. Test ScreenshotService and GUI components
    app = QApplication.instance() or QApplication(sys.argv)

    service = ScreenshotService()
    captured_file = service.capture_full_screen()
    assert captured_file is not None, "Failed to capture full screen!"
    assert os.path.exists(captured_file), f"Captured file does not exist: {captured_file}"
    print(f"[PASS] ScreenshotService captured full screen to: {captured_file}")

    # Verify clipboard has image
    clip_pix = QApplication.clipboard().pixmap()
    assert not clip_pix.isNull(), "Clipboard does not contain image!"
    print(f"[PASS] Clipboard successfully populated with captured image: {clip_pix.width()}x{clip_pix.height()}")

    # Check that new screenshot appears in DB
    assert get_screenshots_count() > initial_count
    print(f"[PASS] Database now has {get_screenshots_count()} screenshots.")

    # 4. Test SnippingOverlay instantiation
    frozen_pix = QPixmap(500, 300)
    frozen_pix.fill(QColor("red"))
    captured_box = []
    overlay = SnippingOverlayWidget(frozen_pix, on_captured=lambda p: captured_box.append(p))
    assert overlay is not None
    overlay.close()
    print("[PASS] SnippingOverlayWidget created and closed cleanly.")

    # 5. Test ScreenshotsPageQt instantiation
    page = ScreenshotsPageQt(screenshot_service=service)
    assert page is not None
    print("[PASS] ScreenshotsPageQt instantiated and initialized successfully.")

    # 6. Test ExpansionEngine shortcut detection for Win + PrintScreen
    from snipglide.engine.listener import ExpansionEngine
    from pynput import keyboard

    area_triggered = []
    full_triggered = []
    engine = ExpansionEngine(
        settings_provider=lambda: {},
        capture_full_callback=lambda: full_triggered.append(True),
        capture_area_callback=lambda: area_triggered.append(True),
    )

    # Test Win + PrintScreen
    engine._win_pressed = True
    key_prt = keyboard.Key.print_screen
    detected = engine._check_screenshot_keys(key_prt)
    assert detected is True, "Expected Win+PrintScreen to be detected!"
    assert len(area_triggered) == 1, "Expected area capture callback to be triggered!"
    print("[PASS] ExpansionEngine correctly detects Win + PrintScreen -> Area Snipping.")

    # Reset debounce and state
    engine._last_capture_time = 0
    engine._win_pressed = False
    engine._last_win_time = 0

    # Test Ctrl + PrintScreen
    import ctypes
    # Simulating ctrl_pressed via _last_ctrl_time
    engine._last_ctrl_time = time.time()
    detected_full = engine._check_screenshot_keys(key_prt)
    assert detected_full is True, "Expected Ctrl+PrintScreen to be detected!"
    assert len(full_triggered) == 1, "Expected full capture callback to be triggered!"
    print("[PASS] ExpansionEngine correctly detects Ctrl + PrintScreen -> Full Capture.")

    print("=== All 6 Screenshot Feature Tests Passed Successfully! ===")

if __name__ == "__main__":
    run_tests()

