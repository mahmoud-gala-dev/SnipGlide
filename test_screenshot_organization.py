import os
import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from snipglide.database.connection import initialize_database, get_connection
from snipglide.database.screenshot_repo import (
    add_screenshot, get_all_screenshots, get_screenshots_count,
    get_screenshots_count_filtered, get_screenshot_folders,
    add_screenshot_folder, rename_screenshot_folder, delete_screenshot_folder,
    move_screenshot_to_folder, delete_all_screenshots, get_screenshot_by_id
)
from snipglide.models.screenshot import Screenshot
from snipglide.ui_qt.screenshots_page import (
    FolderDropButton, ScreenshotCardWidget, ScreenshotCompactCardWidget,
    ScreenshotListRowWidget, ScreenshotsPageQt
)

def run_tests():
    print("=== Testing Screenshot Organization, Views, Pagination, and Folders ===")

    # Initialize QApplication for Qt tests
    app = QApplication.instance() or QApplication(sys.argv)

    # Step 1: Ensure DB initialization
    initialize_database()
    folders = get_screenshot_folders()
    print(f"[✓] Folders in database: {[f['name'] for f in folders]}")
    assert any(f["name"] == "العامة" for f in folders), "Missing default 'العامة' folder!"
    assert any(f["name"] == "العمل" for f in folders), "Missing default 'العمل' folder!"

    # Step 2: Test Folder Creation, Rename, and Move
    custom_folder = "مجلد_اختبار_خاص"
    success = add_screenshot_folder(custom_folder, "#10b981")
    print(f"[✓] Added folder '{custom_folder}': {success}")
    assert success, "Failed to create folder"

    # Create temporary dummy screenshot files
    temp_dir = tempfile.mkdtemp()
    dummy_img1 = os.path.join(temp_dir, "test_shot_1.png")
    with open(dummy_img1, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    dummy_vid1 = os.path.join(temp_dir, "test_vid_1.mp4")
    with open(dummy_vid1, "wb") as f:
        f.write(b"dummy video data")

    # Add screenshots with folders
    shot1_id = add_screenshot(
        file_path=dummy_img1,
        filename="test_shot_1.png",
        capture_type="full",
        width=1920,
        height=1080,
        file_size=1024,
        folder="العامة"
    )
    print(f"[✓] Added screenshot 1 (ID: {shot1_id}) in folder 'العامة'")

    shot2_id = add_screenshot(
        file_path=dummy_vid1,
        filename="test_vid_1.mp4",
        capture_type="video_full",
        width=1280,
        height=720,
        file_size=2048,
        duration=15.5,
        folder="العامة"
    )
    print(f"[✓] Added video 1 (ID: {shot2_id}) in folder 'العامة'")

    # Move item to custom folder
    move_res = move_screenshot_to_folder(shot1_id, custom_folder)
    print(f"[✓] Moved shot {shot1_id} to '{custom_folder}': {move_res}")
    assert move_res, "Failed to move screenshot"

    shot1 = get_screenshot_by_id(shot1_id)
    assert shot1.folder == custom_folder, f"Expected folder '{custom_folder}', got '{shot1.folder}'"
    print(f"[✓] Verified shot1 folder in DB is '{shot1.folder}'")

    # Filtered counts
    cnt_custom = get_screenshots_count_filtered(folder=custom_folder)
    print(f"[✓] Items count in '{custom_folder}': {cnt_custom}")
    assert cnt_custom >= 1, "Count in custom folder should be at least 1"

    # Rename folder
    renamed_folder = "مجلد_اختبار_معدل"
    ren_res = rename_screenshot_folder(custom_folder, renamed_folder)
    print(f"[✓] Renamed folder to '{renamed_folder}': {ren_res}")
    assert ren_res, "Failed to rename folder"

    shot1_renamed = get_screenshot_by_id(shot1_id)
    assert shot1_renamed.folder == renamed_folder, f"Screenshot folder should update on folder rename! Got '{shot1_renamed.folder}'"
    print(f"[✓] Verified screenshot folder updated to '{shot1_renamed.folder}' after folder rename")

    # Delete folder (items should fall back to 'العامة')
    del_res = delete_screenshot_folder(renamed_folder)
    print(f"[✓] Deleted folder '{renamed_folder}': {del_res}")
    assert del_res, "Failed to delete folder"

    shot1_after_del = get_screenshot_by_id(shot1_id)
    assert shot1_after_del.folder == "العامة", f"Items in deleted folder should revert to 'العامة', got '{shot1_after_del.folder}'"
    print(f"[✓] Verified items reverted to 'العامة' after folder deletion")

    # Step 3: Test UI components
    print("\n--- Testing UI Widgets ---")

    # FolderDropButton
    f_btn = FolderDropButton("العمل", count=5, color="#3b82f6", is_active=False)
    assert f_btn.acceptDrops(), "FolderDropButton must accept drops"
    assert "العمل" in f_btn.text()
    f_btn.set_active(True)
    assert f_btn.is_active
    print("[✓] FolderDropButton created and tested successfully")

    # ScreenshotCardWidget (Cards View)
    card = ScreenshotCardWidget(shot1_after_del)
    assert card is not None
    print("[✓] ScreenshotCardWidget instantiated successfully")

    # ScreenshotCompactCardWidget (Compact Grid View)
    compact_card = ScreenshotCompactCardWidget(shot1_after_del)
    assert compact_card.width() == 170 and compact_card.height() == 190
    print("[✓] ScreenshotCompactCardWidget instantiated successfully")

    # ScreenshotListRowWidget (List View)
    list_row = ScreenshotListRowWidget(shot1_after_del)
    assert list_row.height() == 54
    print("[✓] ScreenshotListRowWidget instantiated successfully")

    # Step 4: Test ScreenshotsPageQt integration
    print("\n--- Testing ScreenshotsPageQt Page Integration ---")
    page = ScreenshotsPageQt(toast_callback=lambda msg, err=False: print(f"Toast: {msg}"))

    # Verify View Mode Switcher
    page._set_view_mode("compact")
    assert page.active_view_mode == "compact"
    print("[✓] View mode switched to compact")

    page._set_view_mode("list")
    assert page.active_view_mode == "list"
    print("[✓] View mode switched to list")

    page._set_view_mode("cards")
    assert page.active_view_mode == "cards"
    print("[✓] View mode switched to cards")

    # Verify Pagination
    page._on_page_size_changed("12")
    assert page.page_size == 12
    page._on_page_size_changed("الكل")
    assert page.page_size == -1
    page._on_page_size_changed("24")
    assert page.page_size == 24
    print("[✓] Pagination page size switching works")

    # Verify Folder filtering
    page._on_folder_selected("العامة")
    assert page.active_folder == "العامة"
    page._on_folder_selected("كافة الملفات")
    assert page.active_folder == "كافة الملفات"
    print("[✓] Folder switching works")

    # Clean up test shots
    from snipglide.database.screenshot_repo import delete_screenshot
    delete_screenshot(shot1_id, delete_file=True)
    delete_screenshot(shot2_id, delete_file=True)
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

    print("\n=======================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! 100% COMPLETE & VERIFIED")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
