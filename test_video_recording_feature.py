import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QColor

from snipglide.database.connection import initialize_database
from snipglide.database.screenshot_repo import (
    add_screenshot, get_all_screenshots, get_screenshot_by_id,
    delete_screenshot, get_screenshots_count
)
from snipglide.models.screenshot import Screenshot
from snipglide.services.video_recording_service import ScreenRecordingService, VideoRecorderWorker
from snipglide.ui_qt.video_player_dialog import VideoPlayerDialog
from snipglide.ui_qt.recording_floating_widget import ScreenRecorderFloatingWidget

def test_database_and_models():
    print("--- 1. Testing Database & Model for Video Support ---")
    initialize_database()

    test_video_file = str(BASE_DIR / "test_dummy_video.mp4")
    test_thumb_file = str(BASE_DIR / "test_dummy_thumb.jpg")

    # Create dummy files
    Path(test_video_file).write_bytes(b"dummy mp4 video bytes")
    pix = QPixmap(200, 150)
    pix.fill(QColor("purple"))
    pix.save(test_thumb_file, "JPEG")

    shot_id = add_screenshot(
        file_path=test_video_file,
        filename="test_dummy_video.mp4",
        capture_type="video_full",
        width=1920,
        height=1080,
        file_size=len(b"dummy mp4 video bytes"),
        note="Test screen recording",
        duration=75.4,
        thumbnail_path=test_thumb_file
    )
    assert shot_id is not None and shot_id > 0, "Failed to insert video record into DB!"
    print(f"[PASS] Video inserted with ID {shot_id}")

    shot = get_screenshot_by_id(shot_id)
    assert shot is not None, "Failed to retrieve video record"
    assert shot.is_video is True, "Screenshot.is_video should be True"
    assert shot.formatted_duration == "01:15", f"Expected 01:15, got {shot.formatted_duration}"
    assert shot.thumbnail_path == test_thumb_file
    assert abs(shot.duration - 75.4) < 0.01
    print(f"[PASS] Retrieved video record verified: {shot.filename}, duration={shot.formatted_duration}")

    # Test filtering by video
    video_items = get_all_screenshots(capture_type="video")
    assert any(v.id == shot_id for v in video_items), "Video filter did not include new video!"
    print(f"[PASS] Filter by 'video' returned {len(video_items)} items successfully.")

    # Test clean deletion of video and thumbnail
    del_res = delete_screenshot(shot_id, delete_file=True)
    assert del_res is True, "delete_screenshot failed"
    assert not os.path.exists(test_video_file), "Video file should have been deleted"
    assert not os.path.exists(test_thumb_file), "Thumbnail file should have been deleted"
    assert get_screenshot_by_id(shot_id) is None
    print("[PASS] Video and thumbnail cleanly deleted from disk and database.")

def test_screen_recording_pipeline(app):
    print("--- 2. Testing Screen Recording Service & Worker Pipeline ---")
    service = ScreenRecordingService()

    recorded_info = {}

    def on_saved(file_path, capture_type):
        recorded_info["path"] = file_path
        recorded_info["type"] = capture_type

    service.recording_saved.connect(on_saved)

    # Start recording a small region (e.g. 320x240)
    region = QRect(100, 100, 320, 240)
    service._start_recording(region=region, capture_type="video_area")

    assert service.is_recording() is True, "Service should be in recording state!"
    print("[PASS] Screen recording started successfully.")

    # Process events and record for 1.5 seconds
    t0 = time.time()
    while time.time() - t0 < 1.6:
        app.processEvents()
        time.sleep(0.05)

    assert service.worker._elapsed_time > 0.5, "Worker did not record frames!"
    print(f"[PASS] Recording in progress... frames recorded, elapsed: {service.worker._elapsed_time:.2f}s")

    # Stop recording
    worker_ref = service.worker
    service.stop_recording()
    t1 = time.time()
    while ("path" not in recorded_info) and time.time() - t1 < 5.0:
        app.processEvents()
        time.sleep(0.05)

    assert "path" in recorded_info, "Service did not emit recording_saved signal!"
    video_path = recorded_info["path"]
    assert os.path.exists(video_path), f"Output video file does not exist: {video_path}"
    file_size = os.path.getsize(video_path)
    assert file_size > 1000, f"Recorded file is suspiciously small: {file_size} bytes"
    print(f"[PASS] Video successfully recorded: {video_path} ({file_size} bytes)")

    # Verify entry in DB
    all_videos = get_all_screenshots(capture_type="video")
    saved_rec = next((v for v in all_videos if v.file_path == video_path), None)
    assert saved_rec is not None, "Recorded video not found in database!"
    assert saved_rec.duration > 0.5, f"Saved duration is invalid: {saved_rec.duration}"
    assert saved_rec.thumbnail_path and os.path.exists(saved_rec.thumbnail_path), "Thumbnail file was not created!"
    print(f"[PASS] Database contains verified record: {saved_rec.filename} [duration={saved_rec.formatted_duration}, thumb={os.path.basename(saved_rec.thumbnail_path)}]")

    # 3. Test UI Components
    print("--- 3. Testing UI Components (Floating Widget & Player Dialog) ---")
    floating_widget = ScreenRecorderFloatingWidget(service)
    assert floating_widget is not None
    floating_widget.close()
    print("[PASS] ScreenRecorderFloatingWidget initialized cleanly.")

    player = VideoPlayerDialog(saved_rec)
    assert player is not None
    assert player.windowTitle().startswith("مشغل الفيديو")
    player.close()
    print("[PASS] VideoPlayerDialog initialized and verified.")

    # Clean up test video and thumb
    delete_screenshot(saved_rec.id, delete_file=True)
    print("[PASS] Cleaned up test recording from disk and database.")

def main():
    print("==================================================")
    print("🚀 Running SnipGlide Video Recording Test Suite")
    print("==================================================")
    app = QApplication.instance() or QApplication(sys.argv)

    test_database_and_models()
    test_screen_recording_pipeline(app)

    print("\n==================================================")
    print("🎉 ALL VIDEO RECORDING TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    main()
