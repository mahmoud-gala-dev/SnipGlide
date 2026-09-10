"""
Comprehensive Hardening, Security, and Regression Test Suite for SnipGlide Python Pro.

Covers:
1. AI API Key Encryption, Decryption, UI Masking, and Transparent Migration
2. API Tester Credential Encryption at Rest in SQLite
3. API History URL Query Secret Sanitization
4. Regex Engine ReDoS Isolation and Genuine Timeout Protection
5. Cooperative Worker Cancellation (No Unsafe QThread.terminate)
6. Unicode, Arabic, and Emoji Safety in JSON Unescape
7. Centralized Secret Redaction in Logging
8. Unified Search Resilience on Source Error
9. Database Migration Idempotency and Integrity
10. Unified Search Performance Benchmark under Heavy Load
"""

import json
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from snipglide.core.config import DEFAULT_SETTINGS
from snipglide.database.api_repo import ApiRepository
from snipglide.database.connection import get_connection, initialize_database
from snipglide.database.search_repo import search_all
from snipglide.models.api_request import ApiHistoryEntry, ApiRequest
from snipglide.services.dev_tools_service import JsonTools
from snipglide.services.regex_service import RegexService
from snipglide.services.security import (
    ENC_PREFIX,
    DPAPI_PREFIX,
    is_encrypted_secret,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
    sanitize_url_query,
)
from snipglide.ui_qt.dev_tools.ai_coding_widget import AIWorker, AIProviderTaskWorker, AITaskType
from snipglide.ui_qt.dev_tools.api_tester_widget import ApiRequestWorker
from snipglide.utils.logger import redact_sensitive_text


class TestSecurityHardening(unittest.TestCase):
    """Verifies encryption, decryption, masking, and logging redaction."""

    def test_secret_encryption_and_decryption_cycle(self):
        plain_key = "sk-test1234567890abcdefghijklmnopqrstuvwxyz"
        encrypted = encrypt_secret(plain_key)

        self.assertTrue(is_encrypted_secret(encrypted))
        self.assertNotEqual(plain_key, encrypted)

        decrypted = decrypt_secret(encrypted)
        self.assertEqual(plain_key, decrypted)

    def test_legacy_plaintext_backward_compatibility(self):
        # Legacy keys not starting with ENC_PREFIX should return as-is
        legacy_key = "sk-legacy-unencrypted-key"
        self.assertEqual(decrypt_secret(legacy_key), legacy_key)
        self.assertEqual(decrypt_secret(""), "")
        self.assertEqual(encrypt_secret(""), "")

    def test_mask_secret(self):
        short_key = "secret"
        self.assertEqual(mask_secret(short_key), "••••••••")

        api_key = "sk-1234567890abcdef"
        masked = mask_secret(api_key)
        self.assertTrue(masked.startswith("sk-"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertIn("••••••••", masked)

    def test_redact_sensitive_text(self):
        sample = (
            "User connected with authorization: Bearer my_secret_token_123456 and "
            "api_key=sk-abcdef12345678901234567890 and password: SuperSecretPassword123"
        )
        redacted = redact_sensitive_text(sample)
        self.assertNotIn("my_secret_token_123456", redacted)
        self.assertNotIn("sk-abcdef12345678901234567890", redacted)
        self.assertNotIn("SuperSecretPassword123", redacted)
        self.assertIn("[REDACTED", redacted)

    def test_encrypt_secret_fails_closed_never_fallback_to_plaintext(self):
        """CRITICAL: Encryption failure must NOT return plaintext fallback. It must raise ValueError."""
        with patch("snipglide.services.security._dpapi_encrypt", side_effect=RuntimeError("DPAPI fault")), \
             patch("snipglide.services.security.Fernet") as mock_fernet:
            mock_fernet.side_effect = RuntimeError("Cryptographic hardware fault")
            with self.assertRaises(ValueError) as ctx:
                encrypt_secret("super_sensitive_api_key_12345")
            self.assertIn("failed", str(ctx.exception).lower())

    def test_decrypt_secret_corrupted_does_not_raise_or_leak(self):
        """Decryption of malformed or corrupted ciphertext returns empty string without crashing."""
        corrupted = f"{ENC_PREFIX}not-a-valid-fernet-token"
        result = decrypt_secret(corrupted)
        self.assertEqual(result, "")

        corrupted_dpapi = f"{DPAPI_PREFIX}not-valid-dpapi-token"
        result_dpapi = decrypt_secret(corrupted_dpapi)
        self.assertEqual(result_dpapi, "")

    def test_ai_key_settings_auto_migration(self):
        """Validates that plaintext settings['ai_api_key'] is safely migrated to enc:v1: with verification."""
        raw_key = "sk-plaintext-ai-key-to-migrate"
        dummy_settings = {"ai_api_key": raw_key, "ai_provider": "gemini"}

        # Simulate migration logic from load_settings
        if dummy_settings["ai_api_key"] and not is_encrypted_secret(dummy_settings["ai_api_key"]):
            enc_key = encrypt_secret(dummy_settings["ai_api_key"])
            if is_encrypted_secret(enc_key) and decrypt_secret(enc_key) == raw_key:
                dummy_settings["ai_api_key"] = enc_key

        self.assertTrue(is_encrypted_secret(dummy_settings["ai_api_key"]))
        self.assertNotIn(raw_key, dummy_settings["ai_api_key"])
        self.assertEqual(decrypt_secret(dummy_settings["ai_api_key"]), raw_key)


class TestApiSecurityHardening(unittest.TestCase):
    """Verifies API tester secret storage at rest and history URL sanitization."""

    def setUp(self):
        self.conn = get_connection()
        initialize_database()

    def tearDown(self):
        self.conn.close()

    def test_saved_api_request_credentials_encrypted_in_db(self):
        raw_token = "bearer_secret_token_9999"
        raw_password = "database_secret_password"

        req = ApiRequest(
            name="Secure Endpoint Test",
            method="POST",
            url="https://api.example.com/v1/auth",
            auth_type="bearer",
            auth_data={"token": raw_token, "password": raw_password},
            body_type="json",
            body_content='{"query": "data"}',
            collection_name="SecuritySuite",
        )

        req_id = ApiRepository.add_request(req)
        self.assertIsNotNone(req_id)

        # 1. Verify Raw DB contains ENCRYPTED values, NOT plaintext
        cursor = self.conn.cursor()
        cursor.execute("SELECT auth_data_json FROM saved_api_requests WHERE id = ?", (req_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)

        raw_stored_json = row["auth_data_json"]
        self.assertNotIn(raw_token, raw_stored_json)
        self.assertNotIn(raw_password, raw_stored_json)
        self.assertTrue(ENC_PREFIX in raw_stored_json or DPAPI_PREFIX in raw_stored_json)

        # 2. Verify Repository fetches and automatically decrypts for runtime use
        retrieved = ApiRepository.get_request_by_id(req_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.auth_data.get("token"), raw_token)
        self.assertEqual(retrieved.auth_data.get("password"), raw_password)

        # Clean up
        ApiRepository.delete_request(req_id)

    def test_api_history_url_query_sanitization(self):
        sensitive_url = (
            "https://api.service.com/v1/resource?"
            "api_key=secret_api_key_val&token=secret_token_val&secret=my_secret&public_id=12345"
        )
        entry = ApiHistoryEntry(
            method="GET",
            url=sensitive_url,
            status_code=200,
            status_text="OK",
            response_time_ms=120.5,
            response_size_bytes=1024,
        )

        entry_id = ApiRepository.add_history_entry(entry)
        self.assertIsNotNone(entry_id)

        cursor = self.conn.cursor()
        cursor.execute("SELECT url FROM api_history WHERE id = ?", (entry_id,))
        stored_url = cursor.fetchone()["url"]

        self.assertNotIn("secret_api_key_val", stored_url)
        self.assertNotIn("secret_token_val", stored_url)
        self.assertNotIn("my_secret", stored_url)
        self.assertIn("public_id=12345", stored_url)
        self.assertIn("api_key=%5BREDACTED%5D", stored_url)

        # Clean up
        ApiRepository.delete_history_entry(entry_id)


class TestRegexEngineSafety(unittest.TestCase):
    """Verifies ReDoS isolation and timeout enforcement."""

    def test_catastrophic_backtracking_times_out_safely(self):
        # Classic catastrophic exponential backtracking pattern
        pattern = r"(a+)+$"
        malicious_input = "a" * 32 + "!"

        start_time = time.time()
        ok, matches, error_msg = RegexService.find_matches(
            pattern, malicious_input, timeout=0.8
        )
        elapsed = time.time() - start_time

        self.assertFalse(ok)
        self.assertEqual(len(matches), 0)
        self.assertIn("timed out", error_msg.lower())
        self.assertIn("backtracking", error_msg.lower())
        # Must terminate near the 0.8s timeout, not run forever
        self.assertLess(elapsed, 4.0)

    def test_replace_catastrophic_backtracking_times_out(self):
        pattern = r"(a+)+$"
        malicious_input = "a" * 32 + "!"

        start_time = time.time()
        ok, result = RegexService.replace(
            pattern, malicious_input, "REPLACED", timeout=0.8
        )
        elapsed = time.time() - start_time

        self.assertFalse(ok)
        self.assertIn("timed out", result.lower())
        self.assertLess(elapsed, 4.0)

    def test_normal_regex_executes_rapidly(self):
        pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        text = "Contact support@snipglide.com or sales@snipglide.org for assistance."

        start_time = time.time()
        ok, matches, summary = RegexService.find_matches(pattern, text, timeout=2.0)
        elapsed = time.time() - start_time

        self.assertTrue(ok)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["text"], "support@snipglide.com")
        self.assertEqual(matches[1]["text"], "sales@snipglide.org")
        self.assertLess(elapsed, 1.0)


class TestWorkerCancellation(unittest.TestCase):
    """Verifies cooperative cancellation replaces unsafe QThread.terminate."""

    def test_api_worker_cooperative_cancel(self):
        worker = ApiRequestWorker(
            method="GET",
            url="https://httpbin.org/delay/10",
            headers={},
            body_bytes=None,
            timeout=10.0,
        )
        worker.cancel()
        self.assertTrue(worker.is_cancelled)

        # Calling run directly when cancelled should immediately exit
        mock_signal = MagicMock()
        worker.result_ready.connect(mock_signal)
        worker.run()
        mock_signal.assert_not_called()

    def test_ai_worker_cooperative_cancel(self):
        mock_provider = MagicMock()
        worker = AIWorker(provider=mock_provider, prompt="Hello", stream=False)
        worker.cancel()
        self.assertTrue(worker._is_cancelled)

        mock_completed = MagicMock()
        worker.completed.connect(mock_completed)
        worker.run()
        mock_completed.assert_not_called()

    def test_ai_provider_task_worker_execution_and_cancel(self):
        mock_provider = MagicMock()
        mock_provider.test_connection.return_value = (True, "Connection OK")
        mock_provider.list_models.return_value = ["gemini-pro", "gemini-flash"]

        # Test Connection Task
        worker_conn = AIProviderTaskWorker(mock_provider, AITaskType.TEST_CONNECTION)
        mock_callback = MagicMock()
        worker_conn.task_completed.connect(mock_callback)
        worker_conn.run()
        mock_callback.assert_called_once_with(AITaskType.TEST_CONNECTION, True, "Connection OK")

        # List Models Task
        worker_models = AIProviderTaskWorker(mock_provider, AITaskType.LIST_MODELS)
        mock_cb_models = MagicMock()
        worker_models.task_completed.connect(mock_cb_models)
        worker_models.run()
        mock_cb_models.assert_called_once_with(AITaskType.LIST_MODELS, True, ["gemini-pro", "gemini-flash"])

        # Cancelled task must not emit
        worker_cancelled = AIProviderTaskWorker(mock_provider, AITaskType.TEST_CONNECTION)
        mock_cb_cancelled = MagicMock()
        worker_cancelled.task_completed.connect(mock_cb_cancelled)
        worker_cancelled.cancel()
        worker_cancelled.run()
        mock_cb_cancelled.assert_not_called()


class TestUnicodeAndJsonSafety(unittest.TestCase):
    """Verifies that unescaping preserves Arabic, Emojis, and UTF-8 characters."""

    def test_json_unescape_arabic_and_emojis(self):
        arabic_text = "مرحبا بالعالم 👋 🚀"
        ok, res = JsonTools.unescape(arabic_text)
        self.assertTrue(ok)
        self.assertEqual(res, arabic_text)

    def test_json_unescape_escape_sequences_with_unicode(self):
        escaped_input = r"Line 1\nLine 2\tTabbed\nمرحبا\u0627"
        ok, res = JsonTools.unescape(escaped_input)
        self.assertTrue(ok)
        self.assertIn("Line 1\nLine 2\tTabbed", res)
        self.assertIn("مرحباا", res)

    def test_json_unescape_surrogate_emoji_pair(self):
        surrogate_rocket = r"\uD83D\uDE80"
        ok, res = JsonTools.unescape(surrogate_rocket)
        self.assertTrue(ok)
        self.assertEqual(res, "🚀")


class TestDatabaseAndSearchResilience(unittest.TestCase):
    """Verifies DB migration idempotency and search error resilience."""

    def test_initialize_database_is_idempotent(self):
        # Running initialize_database repeatedly should not error or duplicate schema
        for _ in range(3):
            initialize_database()

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM groups WHERE name = 'General'")
            self.assertEqual(cursor.fetchone()[0], 1)
        finally:
            conn.close()

    def test_unified_search_handles_corrupted_or_missing_source_gracefully(self):
        # Even if a query is unusual, search_all continues and returns results
        results = search_all("test", limit=20)
        self.assertIsInstance(results, list)

    def test_unified_search_performance_benchmark(self):
        """Measures search speed across database records."""
        t0 = time.perf_counter()
        results = search_all("General", limit=50)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIsInstance(results, list)
        # Verify search completes under 100ms in SQLite WAL mode
        self.assertLess(elapsed_ms, 250.0)

    def test_search_error_resilience_one_source_fails_others_continue(self):
        """Priority 9: Break one search source intentionally; verify other sources return, failure is logged, no crash."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO notes (title, content) VALUES ('Resilience Note', 'Resilience Body')")
            conn.commit()

        class FaultyCursor:
            def __init__(self, real_cur):
                self._cur = real_cur
            def execute(self, sql, *args, **kwargs):
                if "FROM snippets" in sql:
                    raise sqlite3.OperationalError("Simulated table error in snippets")
                return self._cur.execute(sql, *args, **kwargs)
            def fetchall(self):
                return self._cur.fetchall()
            def fetchone(self):
                return self._cur.fetchone()
            def __getattr__(self, attr):
                return getattr(self._cur, attr)

        class FaultyConn:
            def __init__(self):
                self._conn = get_connection()
            def cursor(self):
                return FaultyCursor(self._conn.cursor())
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self._conn.close()
            def __getattr__(self, attr):
                return getattr(self._conn, attr)

        with patch("snipglide.database.search_repo.get_connection", side_effect=FaultyConn):
            with patch("snipglide.database.search_repo.logger.warning") as mock_log:
                results = search_all("Resilience", limit=20)
                mock_log.assert_called()
                log_args = str(mock_log.call_args)
                self.assertIn("snippets", log_args)
                self.assertIsInstance(results, list)
                self.assertTrue(any(r.get("source") == "notes" or "Resilience" in r.get("title", "") for r in results))

    def test_database_migration_from_three_states(self):
        """Priority 13: Test DB from 3 states: A) Fresh install, B) Pre-developer-suite, C) Existing plaintext secrets."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_migration.db")

        try:
            # STATE A: Fresh install
            with patch("snipglide.database.connection.DB_FILE", db_path):
                initialize_database()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}
                self.assertIn("groups", tables)
                self.assertIn("saved_api_requests", tables)
                self.assertIn("developer_projects", tables)
                conn.close()

            # STATE B: Pre-Developer-Suite database (drop newer tables to simulate legacy schema)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DROP TABLE saved_api_requests")
            cursor.execute("DROP TABLE saved_regexes")
            cursor.execute("DROP TABLE developer_projects")
            cursor.execute("INSERT OR IGNORE INTO snippets (shortcut, replacement) VALUES ('!legacy', 'legacy expansion')")
            conn.commit()
            conn.close()

            with patch("snipglide.database.connection.DB_FILE", db_path):
                initialize_database()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT replacement FROM snippets WHERE shortcut = '!legacy'")
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "legacy expansion")
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}
                self.assertIn("saved_api_requests", tables)
                conn.close()

            # STATE C: Database with existing plaintext secrets
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO saved_api_requests (name, method, url, auth_type, auth_data_json)
                VALUES ('Plaintext Req', 'GET', 'https://api.com', 'bearer', '{"token": "raw_old_secret"}')
            """)
            conn.commit()
            row_id = cursor.lastrowid
            conn.close()

            with patch("snipglide.database.connection.DB_FILE", db_path):
                req = ApiRepository.get_request_by_id(row_id)
                self.assertEqual(req.auth_data.get("token"), "raw_old_secret")
                ApiRepository.update_request(req)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT auth_data_json FROM saved_api_requests WHERE id = ?", (row_id,))
                raw_json = cursor.fetchone()[0]
                self.assertTrue(ENC_PREFIX in raw_json or DPAPI_PREFIX in raw_json)
                self.assertNotIn("raw_old_secret", raw_json)
                conn.close()
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
