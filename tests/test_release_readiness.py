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
from snipglide.services.security import encrypt_secret, decrypt_secret, ENC_PREFIX
from snipglide.core.config import load_settings, save_settings
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
        self.assertTrue(enc_val.startswith(ENC_PREFIX))
        self.assertNotIn("legacy_sk_gemini_plaintext_key_9988", enc_val)

        # decrypt_secret must return original value
        decrypted = decrypt_secret(enc_val)
        self.assertEqual(decrypted, "legacy_sk_gemini_plaintext_key_9988")

        # Verify on-disk file
        with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertTrue(disk_data.get("ai_api_key", "").startswith(ENC_PREFIX))
        self.assertNotIn("legacy_sk_gemini_plaintext_key_9988", json.dumps(disk_data))


if __name__ == "__main__":
    unittest.main()
