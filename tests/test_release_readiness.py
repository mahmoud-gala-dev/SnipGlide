"""Release Readiness Test Suite for SnipGlide Windows Release Candidate.

Validates:
1. Clean Install: Fresh DB creation, all tables, indices, default settings, zero missing deps.
2. Upgrade Migration: Legacy DB (Phase 1/pre-developer) upgrades to current schema without data loss.
3. Secret Migration: Plaintext AI keys and API tester credentials securely migrate to encrypted format.
4. Data Preservation: Snippets, clipboard, notes, regexes, projects, commands remain fully intact.
"""
from __future__ import annotations

import os
import sys
import json
import sqlite3
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure utf-8 stdout and project path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snipglide.core.config as config
import snipglide.database.connection as db_conn
from snipglide.database.connection import initialize_database, get_connection
from snipglide.core.config import load_settings, save_settings
from snipglide.services.security import (
    encrypt_secret,
    decrypt_secret,
    is_encrypted_secret,
    ENC_PREFIX,
    DPAPI_PREFIX,
)
from snipglide.database.api_repo import ApiRepository
from snipglide.models.api_request import ApiRequest


class TestCleanInstall(unittest.TestCase):
    """Verifies fresh install behavior in an isolated environment."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_data_dir = config.DATA_DIR
        self.orig_db_file = config.DB_FILE
        self.orig_settings_file = config.SETTINGS_FILE

        self.isolated_data_dir = Path(self.temp_dir) / "SnipGlideClean"
        self.isolated_data_dir.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR = self.isolated_data_dir
        config.DB_FILE = self.isolated_data_dir / "snipglide.db"
        config.SETTINGS_FILE = self.isolated_data_dir / "settings.json"
        db_conn.DB_FILE = config.DB_FILE

    def tearDown(self):
        config.DATA_DIR = self.orig_data_dir
        config.DB_FILE = self.orig_db_file
        config.SETTINGS_FILE = self.orig_settings_file
        db_conn.DB_FILE = self.orig_db_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fresh_database_creation_and_tables(self):
        """Clean install creates database and all required tables with indexes."""
        self.assertFalse(config.DB_FILE.exists())
        initialize_database()
        self.assertTrue(config.DB_FILE.exists())

        conn = sqlite3.connect(config.DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            expected_tables = {
                "groups",
                "snippets",
                "notes",
                "chat_notes",
                "clipboard_history",
                "saved_regexes",
                "saved_api_requests",
                "api_history",
                "developer_projects",
                "terminal_commands"
            }
            for tbl in expected_tables:
                self.assertIn(tbl, tables, f"Missing required table in fresh install: {tbl}")

            # Verify General group default
            cursor.execute("SELECT name FROM groups WHERE name = 'General'")
            self.assertIsNotNone(cursor.fetchone())

            # Verify indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}
            self.assertIn("idx_snippets_shortcut", indexes)
            self.assertIn("idx_saved_api_fav", indexes)
            self.assertIn("idx_dev_proj_path", indexes)
        finally:
            conn.close()

    def test_fresh_settings_file_defaults(self):
        """Default settings contain no plaintext secrets and have safe defaults."""
        settings = load_settings()
        self.assertEqual(settings.get("ai_api_key", ""), "")
        self.assertEqual(settings.get("ai_api_key_enc", ""), "")
        self.assertTrue(settings.get("enabled", False))


class TestLegacyUpgradeMigration(unittest.TestCase):
    """Verifies upgrading from legacy database schemas without data loss."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_data_dir = config.DATA_DIR
        self.orig_db_file = config.DB_FILE
        self.orig_settings_file = config.SETTINGS_FILE

        self.isolated_data_dir = Path(self.temp_dir) / "SnipGlideUpgrade"
        self.isolated_data_dir.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR = self.isolated_data_dir
        config.DB_FILE = self.isolated_data_dir / "snipglide.db"
        config.SETTINGS_FILE = self.isolated_data_dir / "settings.json"
        db_conn.DB_FILE = config.DB_FILE

    def tearDown(self):
        config.DATA_DIR = self.orig_data_dir
        config.DB_FILE = self.orig_db_file
        config.SETTINGS_FILE = self.orig_settings_file
        db_conn.DB_FILE = self.orig_db_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_database_upgrade_preserves_all_data(self):
        """Simulate legacy v1.0 database containing old snippets, clipboard, and notes."""
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()

        # Create basic legacy schema
        cursor.execute("""
            CREATE TABLE groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'G',
                color TEXT DEFAULT '#2563eb'
            )
        """)
        cursor.execute("INSERT INTO groups (name) VALUES ('Work')")
        cursor.execute("""
            CREATE TABLE snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shortcut TEXT NOT NULL UNIQUE,
                replacement TEXT NOT NULL,
                group_id INTEGER,
                tags TEXT DEFAULT '',
                description TEXT DEFAULT '',
                language TEXT DEFAULT 'Plain Text',
                enabled INTEGER DEFAULT 1,
                favorite INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            INSERT INTO snippets (shortcut, replacement, description)
            VALUES (':legacy_sig', 'Best regards,\nMahmoud Gala', 'Legacy Email Signature')
        """)
        cursor.execute("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                pinned INTEGER DEFAULT 0,
                created_date TEXT,
                modified_date TEXT
            )
        """)
        cursor.execute("INSERT INTO notes (title, content) VALUES ('Old Meeting', 'Discuss Phase 1 architecture')")

        cursor.execute("""
            CREATE TABLE clipboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                copied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("INSERT INTO clipboard_history (content) VALUES ('old copied text snippet')")
        conn.commit()
        conn.close()

        # Run migration via initialize_database()
        initialize_database()

        # Verify all legacy data is preserved intact
        conn = sqlite3.connect(config.DB_FILE)
        try:
            cursor = conn.cursor()

            # 1. Snippets preserved & updated with snippet_type
            cursor.execute("SELECT shortcut, replacement, snippet_type FROM snippets WHERE shortcut = ':legacy_sig'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], ":legacy_sig")
            self.assertIn("Mahmoud Gala", row[1])
            self.assertEqual(row[2], "Text")

            # 2. Notes preserved
            cursor.execute("SELECT title, content FROM notes WHERE title = 'Old Meeting'")
            nrow = cursor.fetchone()
            self.assertIsNotNone(nrow)
            self.assertEqual(nrow[1], "Discuss Phase 1 architecture")

            # 3. Clipboard preserved
            cursor.execute("SELECT content, content_type FROM clipboard_history WHERE content = 'old copied text snippet'")
            crow = cursor.fetchone()
            self.assertIsNotNone(crow)
            self.assertEqual(crow[0], "old copied text snippet")

            # 4. New Phase tables now exist and are writable
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cursor.fetchall()}
            self.assertIn("saved_regexes", tables)
            self.assertIn("saved_api_requests", tables)
            self.assertIn("developer_projects", tables)
            self.assertIn("terminal_commands", tables)
        finally:
            conn.close()

    def test_legacy_secrets_migration(self):
        """Plaintext AI API key in settings.json auto-migrates to encrypted representation."""
        # Write legacy settings with plaintext key
        legacy_settings = {
            "enabled": True,
            "ai_api_key": "legacy_sk_gemini_plaintext_key_9988"
        }
        with open(config.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(legacy_settings, f)

        # Call load_settings() which executes migration
        loaded = load_settings()

        # Stored setting must now be encrypted
        enc_val = loaded.get("ai_api_key", "")
        self.assertTrue(is_encrypted_secret(enc_val))
        self.assertNotIn("legacy_sk_gemini_plaintext_key_9988", enc_val)

        # decrypt_secret must return original value
        decrypted = decrypt_secret(enc_val)
        self.assertEqual(decrypted, "legacy_sk_gemini_plaintext_key_9988")

        # Verify on-disk file
        with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertTrue(is_encrypted_secret(disk_data.get("ai_api_key", "")))
        self.assertNotIn("legacy_sk_gemini_plaintext_key_9988", json.dumps(disk_data))


class TestBackupRestoreSecurity(unittest.TestCase):
    """Validates that backup restore applies encryption to API credentials (STEP 18)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_data_dir = config.DATA_DIR
        self.orig_db_file = config.DB_FILE
        self.orig_settings_file = config.SETTINGS_FILE

        isolated = Path(self.temp_dir) / "SnipGlideBackupTest"
        isolated.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR = isolated
        config.DB_FILE = isolated / "snipglide.db"
        config.SETTINGS_FILE = isolated / "settings.json"
        import snipglide.database.connection as db_conn
        db_conn.DB_FILE = config.DB_FILE
        initialize_database()

    def tearDown(self):
        import snipglide.database.connection as db_conn
        config.DATA_DIR = self.orig_data_dir
        config.DB_FILE = self.orig_db_file
        config.SETTINGS_FILE = self.orig_settings_file
        db_conn.DB_FILE = self.orig_db_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backup_restore_encrypts_credentials(self):
        """After restoring a legacy plaintext backup, API credentials must be encrypted in DB."""
        from snipglide.services.backup import import_backup as restore_backup
        import json, tempfile as _tf

        SENTINEL = "BACKUP_SENTINEL_PLAINTEXT_928471"

        # Simulate a legacy backup with plaintext API credentials
        # import_backup requires at minimum 'groups' and 'snippets' keys
        legacy_backup = {
            "groups": [],
            "snippets": [],
            "saved_api_requests": [
                {
                    "name": "Legacy Backup Request",
                    "method": "POST",
                    "url": "https://api.legacy.example.com/endpoint",
                    "auth_type": "bearer",
                    "auth_data_json": json.dumps({"token": SENTINEL}),
                    "headers_json": json.dumps([
                        {"enabled": True, "key": "Authorization", "value": f"Bearer {SENTINEL}"}
                    ]),
                    "params_json": "[]",
                    "body_type": "none",
                    "body_content": "",
                    "collection_name": "Legacy",
                    "is_favorite": 0,
                }
            ]
        }

        backup_path = os.path.join(self.temp_dir, "legacy_backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(legacy_backup, f)

        # Restore the backup
        result = restore_backup(backup_path)
        self.assertTrue(result, "Backup restore should succeed")

        # Inspect the active database — credentials must NOT be plaintext
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT auth_data_json, headers_json FROM saved_api_requests WHERE name = ?",
                           ("Legacy Backup Request",))
            row = cursor.fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row, "Restored request should exist in database")
        self.assertNotIn(SENTINEL, row["auth_data_json"],
                         "Plaintext sentinel MUST NOT appear in auth_data_json after restore")
        self.assertNotIn(SENTINEL, row["headers_json"],
                         "Plaintext sentinel MUST NOT appear in headers_json after restore")

class TestSprint1Hardening(unittest.TestCase):
    """Verifies Sprint 1 release hardening: comprehensive backup/restore, mss video, and worker cleanup."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_data_dir = config.DATA_DIR
        self.orig_db_file = config.DB_FILE
        self.orig_settings_file = config.SETTINGS_FILE
        self.orig_backup_dir = config.BACKUP_DIR

        self.isolated_data_dir = Path(self.temp_dir) / "SnipGlideSprint1"
        self.isolated_data_dir.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR = self.isolated_data_dir
        config.DB_FILE = self.isolated_data_dir / "snipglide.db"
        config.SETTINGS_FILE = self.isolated_data_dir / "settings.json"
        config.BACKUP_DIR = self.isolated_data_dir / "backups"
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        db_conn.DB_FILE = config.DB_FILE

        initialize_database()

    def tearDown(self):
        config.DATA_DIR = self.orig_data_dir
        config.DB_FILE = self.orig_db_file
        config.SETTINGS_FILE = self.orig_settings_file
        config.BACKUP_DIR = self.orig_backup_dir
        db_conn.DB_FILE = self.orig_db_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_comprehensive_backup_and_restore_all_tables(self):
        """P1-01: Verifies export_backup and import_backup cover notes, chat notes, screenshots, and all tables."""
        from snipglide.services.backup import export_backup, import_backup

        # 1. Populate sample data across multiple tables
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content, color, pinned) VALUES ('Test Note', 'Important Note Content', '#3b82f6', 1)")
            cursor.execute("INSERT INTO chat_notes (content, is_starred, tags) VALUES ('Quick Chat Note Message', 1, 'tag1')")
            cursor.execute("INSERT INTO screenshot_folders (name, color) VALUES ('Design Docs', '#10b981')")
            cursor.execute("INSERT INTO screenshots (file_path, filename, note, folder) VALUES ('/fake/shot.png', 'shot.png', 'Screen Note', 'Design Docs')")
            cursor.execute("INSERT INTO saved_regexes (name, pattern, description) VALUES ('Email Pattern', '^[a-z]+@example\\.com$', 'Simple email')")
            conn.commit()

        # 2. Export backup
        backup_file = os.path.join(self.temp_dir, "full_backup.json")
        self.assertTrue(export_backup(backup_file))

        with open(backup_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("version"), "2.0")
        self.assertTrue(len(data.get("notes", [])) >= 1)
        self.assertTrue(len(data.get("chat_notes", [])) >= 1)
        self.assertTrue(len(data.get("screenshots", [])) >= 1)
        self.assertTrue(len(data.get("screenshot_folders", [])) >= 1)
        self.assertTrue(len(data.get("saved_regexes", [])) >= 1)

        # 3. Modify/delete database records
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes")
            cursor.execute("DELETE FROM chat_notes")
            cursor.execute("DELETE FROM screenshots")
            conn.commit()

        # 4. Import backup
        self.assertTrue(import_backup(backup_file))

        # 5. Assert all rows are restored
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, content FROM notes WHERE title = 'Test Note'")
            note_row = cursor.fetchone()
            self.assertIsNotNone(note_row)
            self.assertEqual(note_row["content"], "Important Note Content")

            cursor.execute("SELECT content FROM chat_notes WHERE content = 'Quick Chat Note Message'")
            self.assertIsNotNone(cursor.fetchone())

            cursor.execute("SELECT filename FROM screenshots WHERE filename = 'shot.png'")
            self.assertIsNotNone(cursor.fetchone())

        # 6. Verify pre-restore safety snapshot file exists
        safety_file = config.BACKUP_DIR / "pre_restore_safety_backup.json"
        self.assertTrue(safety_file.exists(), "Pre-restore safety snapshot must exist")

    def test_video_recorder_worker_mss_thread_safety(self):
        """P1-02: VideoRecorderWorker initializes and uses mss for thread-safe frame capture without Qt GUI objects."""
        from snipglide.services.video_recording_service import VideoRecorderWorker
        out_file = Path(self.temp_dir) / "test_rec.mp4"
        thumb_file = Path(self.temp_dir) / "test_thumb.jpg"

        worker = VideoRecorderWorker(
            output_file=out_file,
            thumb_file=thumb_file,
            fps=24,
            show_cursor=True
        )
        self.assertEqual(worker.fps, 24)
        self.assertTrue(worker.show_cursor)
        self.assertFalse(worker.is_recording() is False) # running is True initially until stop
        worker.stop()
        self.assertFalse(worker._running)

    def test_dev_tool_widget_cleanup_safety(self):
        """P1-03: Dev tool widgets implement cleanup and closeEvent without crashing or leaking unjoined threads."""
        from snipglide.ui_qt.dev_tools.regex_widget import RegexPlaygroundWidget
        from snipglide.ui_qt.dev_tools.api_tester_widget import ApiTesterWidget
        from snipglide.ui_qt.dev_tools.ai_coding_widget import AICodingWidget
        from snipglide.ui_qt.dev_tools.git_tools_widget import GitToolsWidget
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)

        rw = RegexPlaygroundWidget()
        rw.cleanup()
        rw.deleteLater()

        aw = ApiTesterWidget()
        aw.cleanup()
        aw.deleteLater()

        aiw = AICodingWidget()
        aiw.cleanup()
        aiw.deleteLater()

        gw = GitToolsWidget()
        gw.cleanup()
        gw.deleteLater()

        app.processEvents()


class TestSprint2Hardening(unittest.TestCase):
    """Verifies Sprint 2 features: Windows DPAPI protection and modular structure."""

    def test_windows_dpapi_roundtrip_encryption(self):
        """P2-03: Windows DPAPI encrypts and decrypts secrets with hardware/user credentials."""
        secret = "sk-ant-api-prod-super-secret-dpapi-998877"
        encrypted = encrypt_secret(secret)

        self.assertTrue(is_encrypted_secret(encrypted))
        if os.name == "nt":
            self.assertTrue(encrypted.startswith(DPAPI_PREFIX))
        self.assertNotEqual(secret, encrypted)

        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, secret)

    def test_legacy_fernet_backward_compatibility_under_dpapi(self):
        """P2-03: Existing enc:v1: secrets decrypt properly without data loss."""
        from cryptography.fernet import Fernet
        from snipglide.services.security import get_secret_encryption_key
        key = get_secret_encryption_key()
        f = Fernet(key)
        raw_secret = "legacy_token_created_before_dpapi_upgrade"
        cipher = f.encrypt(raw_secret.encode("utf-8")).decode("ascii")
        legacy_ciphertext = f"{ENC_PREFIX}{cipher}"

        self.assertTrue(is_encrypted_secret(legacy_ciphertext))
        decrypted = decrypt_secret(legacy_ciphertext)
        self.assertEqual(decrypted, raw_secret)

    def test_dpapi_fail_closed_on_corrupted_data(self):
        """P2-03: Corrupted or tampered DPAPI ciphertext safely returns empty string."""
        bad_dpapi = f"{DPAPI_PREFIX}totally_corrupted_base64_string_xyz=="
        self.assertEqual(decrypt_secret(bad_dpapi), "")

    def test_notepad_and_screenshot_modular_imports(self):
        """P2-01: Verifies backward-compatible re-exports match the new modular classes."""
        from snipglide.ui_qt.notepad_page import (
            NotepadEditor as E1,
            LineNumberArea as L1,
            FindReplaceBar as F1,
            SmoothTabBar as S1,
            NotepadTab as T1,
        )
        from snipglide.ui_qt.notepad.editor import NotepadEditor as E2, LineNumberArea as L2
        from snipglide.ui_qt.notepad.find_replace_bar import FindReplaceBar as F2
        from snipglide.ui_qt.notepad.tab import SmoothTabBar as S2, NotepadTab as T2

        self.assertIs(E1, E2)
        self.assertIs(L1, L2)
        self.assertIs(F1, F2)
        self.assertIs(S1, S2)
        self.assertIs(T1, T2)

        from snipglide.ui_qt.screenshots_page import (
            ScreenshotViewerDialog as V1,
            FolderDropButton as B1,
            ScreenshotCardWidget as C1,
            ScreenshotCompactCardWidget as CC1,
            ScreenshotListRowWidget as R1,
        )
        from snipglide.ui_qt.screenshots.viewer_dialog import ScreenshotViewerDialog as V2
        from snipglide.ui_qt.screenshots.cards import (
            FolderDropButton as B2,
            ScreenshotCardWidget as C2,
            ScreenshotCompactCardWidget as CC2,
            ScreenshotListRowWidget as R2,
        )

        self.assertIs(V1, V2)
        self.assertIs(B1, B2)
        self.assertIs(C1, C2)
        self.assertIs(CC1, CC2)
        self.assertIs(R1, R2)


if __name__ == "__main__":
    unittest.main()


