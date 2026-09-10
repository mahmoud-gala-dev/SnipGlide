"""Comprehensive Standalone Test Suite for REST API Tester & Credential Security.

Uses a local mock HTTP server on 127.0.0.1 without any external internet dependency.
Validates HTTP methods, body parsing, auth formats, timeout handling, security encryption,
URL query redaction in history, cURL redaction, and repository CRUD.
"""
import http.server
import json
import os
import sqlite3
import sys
import threading
import time
import unittest
import urllib.parse
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from snipglide.database.connection import get_connection, initialize_database
from snipglide.database.api_repo import ApiRepository
from snipglide.models.api_request import ApiRequest, ApiHistoryEntry
from snipglide.services.api_client_service import ApiClientService
from snipglide.services.security import (
    encrypt_secret,
    decrypt_secret,
    sanitize_url_query,
    is_sensitive_header,
    ENC_PREFIX,
    DPAPI_PREFIX,
)


class MockApiHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP Request Handler for testing API client interactions."""

    def log_message(self, format, *args):
        # Silence standard HTTP access logging during tests
        pass

    def _send_json(self, status: int, data: dict):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/slow":
            time.sleep(1.5)
            self._send_json(200, {"status": "delayed"})
            return

        if parsed.path == "/error-401":
            self._send_json(401, {"error": "Unauthorized"})
            return

        if parsed.path == "/error-404":
            self._send_json(404, {"error": "Not Found"})
            return

        if parsed.path == "/error-500":
            self._send_json(500, {"error": "Internal Server Error"})
            return

        if parsed.path == "/large":
            # Stream payload > 5MB to test safety limit
            chunk = b"A" * (1024 * 1024)  # 1MB
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(chunk) * 6))
            self.end_headers()
            for _ in range(6):
                self.wfile.write(chunk)
            return

        query_params = dict(urllib.parse.parse_qsl(parsed.query))
        headers_dict = {k: v for k, v in self.headers.items()}
        self._send_json(200, {
            "method": "GET",
            "path": parsed.path,
            "query": query_params,
            "headers": headers_dict,
        })

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        self._send_json(201, {
            "method": "POST",
            "body": body,
            "content_type": self.headers.get("Content-Type", ""),
            "auth": self.headers.get("Authorization", ""),
        })

    def do_PUT(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        self._send_json(200, {"method": "PUT", "body": body})

    def do_PATCH(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        self._send_json(200, {"method": "PATCH", "body": body})

    def do_DELETE(self):
        self._send_json(200, {"method": "DELETE", "deleted": True})

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("X-Custom-Head", "Head-OK")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS")
        self.end_headers()


class TestApiTesterComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), MockApiHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    # ─────────────────────────────────────────────────────────
    # 1. HTTP Client Methods & Execution Tests
    # ─────────────────────────────────────────────────────────

    def test_01_get_request_with_query_params(self):
        url = ApiClientService.build_final_url(
            f"{self.base_url}/test",
            [{"key": "search", "value": "snipglide", "enabled": True}, {"key": "page", "value": "1", "enabled": True}]
        )
        resp = ApiClientService.execute_request("GET", url)
        self.assertFalse(resp.is_error)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["method"], "GET")
        self.assertEqual(data["query"]["search"], "snipglide")
        self.assertEqual(data["query"]["page"], "1")

    def test_02_post_json_body(self):
        headers = ApiClientService.build_headers([], body_type="json")
        body_payload = json.dumps({"name": "SnipGlide Pro", "active": True})
        body_bytes = ApiClientService.prepare_body("json", body_payload)

        resp = ApiClientService.execute_request(
            "POST", f"{self.base_url}/items", headers=headers, body_bytes=body_bytes
        )
        self.assertFalse(resp.is_error)
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.body)
        self.assertEqual(data["method"], "POST")
        self.assertIn("application/json", data["content_type"])
        parsed_body = json.loads(data["body"])
        self.assertEqual(parsed_body["name"], "SnipGlide Pro")

    def test_03_put_and_patch_and_delete(self):
        # PUT
        put_bytes = ApiClientService.prepare_body("raw", "update-payload")
        resp_put = ApiClientService.execute_request("PUT", f"{self.base_url}/item/1", body_bytes=put_bytes)
        self.assertEqual(resp_put.status_code, 200)
        self.assertEqual(json.loads(resp_put.body)["method"], "PUT")

        # PATCH
        patch_bytes = ApiClientService.prepare_body("raw", "patch-payload")
        resp_patch = ApiClientService.execute_request("PATCH", f"{self.base_url}/item/1", body_bytes=patch_bytes)
        self.assertEqual(resp_patch.status_code, 200)
        self.assertEqual(json.loads(resp_patch.body)["method"], "PATCH")

        # DELETE
        resp_del = ApiClientService.execute_request("DELETE", f"{self.base_url}/item/1")
        self.assertEqual(resp_del.status_code, 200)
        self.assertEqual(json.loads(resp_del.body)["method"], "DELETE")

    def test_04_head_and_options(self):
        resp_head = ApiClientService.execute_request("HEAD", f"{self.base_url}/info")
        self.assertEqual(resp_head.status_code, 200)
        self.assertIn("X-Custom-Head", resp_head.headers)

        resp_opt = ApiClientService.execute_request("OPTIONS", f"{self.base_url}/info")
        self.assertEqual(resp_opt.status_code, 204)
        self.assertIn("Allow", resp_opt.headers)

    def test_05_auth_bearer_and_basic(self):
        # Bearer
        headers_bearer = ApiClientService.build_headers(
            [], auth_type="bearer", auth_data={"token": "test-secret-token-123"}
        )
        self.assertEqual(headers_bearer.get("Authorization"), "Bearer test-secret-token-123")
        resp_b = ApiClientService.execute_request("POST", f"{self.base_url}/auth", headers=headers_bearer)
        self.assertEqual(json.loads(resp_b.body)["auth"], "Bearer test-secret-token-123")

        # Basic
        headers_basic = ApiClientService.build_headers(
            [], auth_type="basic", auth_data={"username": "admin", "password": "secret-pass"}
        )
        self.assertTrue(headers_basic.get("Authorization", "").startswith("Basic "))

    def test_06_auth_api_key_header_and_query(self):
        # Header API Key
        headers_ak = ApiClientService.build_headers(
            [], auth_type="api_key", auth_data={"key": "X-API-KEY", "value": "my-secret-val", "add_to": "header"}
        )
        self.assertEqual(headers_ak.get("X-API-KEY"), "my-secret-val")

        # Query API Key
        url_q = ApiClientService.build_final_url(
            f"{self.base_url}/api",
            [],
            auth_type="api_key",
            auth_data={"key": "api_key", "value": "query-secret-999", "add_to": "query"}
        )
        self.assertIn("api_key=query-secret-999", url_q)
        resp = ApiClientService.execute_request("GET", url_q)
        self.assertEqual(json.loads(resp.body)["query"]["api_key"], "query-secret-999")

    def test_07_http_errors_and_invalid_urls(self):
        # 401
        r401 = ApiClientService.execute_request("GET", f"{self.base_url}/error-401")
        self.assertEqual(r401.status_code, 401)
        self.assertFalse(r401.is_error)

        # 404
        r404 = ApiClientService.execute_request("GET", f"{self.base_url}/error-404")
        self.assertEqual(r404.status_code, 404)

        # 500
        r500 = ApiClientService.execute_request("GET", f"{self.base_url}/error-500")
        self.assertEqual(r500.status_code, 500)

        # Invalid URL
        r_empty = ApiClientService.execute_request("GET", "")
        self.assertTrue(r_empty.is_error)

        # Timeout
        r_timeout = ApiClientService.execute_request("GET", f"{self.base_url}/slow", timeout=0.2)
        self.assertTrue(r_timeout.is_error)
        self.assertIn("Timed Out", r_timeout.error_message)

    def test_08_response_size_limit(self):
        resp = ApiClientService.execute_request("GET", f"{self.base_url}/large")
        self.assertFalse(resp.is_error)
        self.assertIn("[⚠️ Response was truncated at 5MB limit]", resp.body)

    # ─────────────────────────────────────────────────────────
    # 2. Security Tests (Encrypted Credentials & URL Redaction)
    # ─────────────────────────────────────────────────────────

    def test_09_saved_request_auth_credentials_not_plaintext(self):
        # Save request with Bearer token
        req = ApiRequest(
            name="Secure Bearer Test",
            method="GET",
            url=f"{self.base_url}/secure",
            auth_type="bearer",
            auth_data={"token": "super_secret_bearer_token_xyz"},
            headers=[{"enabled": True, "key": "Authorization", "value": "Bearer header_token_xyz"}]
        )
        req_id = ApiRepository.add_request(req)
        self.assertIsNotNone(req_id)

        # Direct database inspection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auth_data_json, headers_json FROM saved_api_requests WHERE id = ?", (req_id,))
        row = cursor.fetchone()
        conn.close()

        raw_auth_json = row["auth_data_json"]
        raw_headers_json = row["headers_json"]

        # MUST NOT contain plaintext secrets!
        self.assertNotIn("super_secret_bearer_token_xyz", raw_auth_json)
        self.assertNotIn("header_token_xyz", raw_headers_json)

        # MUST contain enc:v1: or dpapi:v1: prefix
        self.assertTrue(ENC_PREFIX in raw_auth_json or DPAPI_PREFIX in raw_auth_json)
        self.assertTrue(ENC_PREFIX in raw_headers_json or DPAPI_PREFIX in raw_headers_json)

        # Decrypted retrieval through repository must return original secrets
        loaded = ApiRepository.get_request_by_id(req_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.auth_data.get("token"), "super_secret_bearer_token_xyz")
        header_val = [h["value"] for h in loaded.headers if h.get("key") == "Authorization"][0]
        self.assertEqual(header_val, "Bearer header_token_xyz")

    def test_10_saved_request_basic_auth_not_plaintext(self):
        req = ApiRequest(
            name="Secure Basic Test",
            method="POST",
            url=f"{self.base_url}/login",
            auth_type="basic",
            auth_data={"username": "superadmin", "password": "TopSecretPassword123!"}
        )
        req_id = ApiRepository.add_request(req)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auth_data_json FROM saved_api_requests WHERE id = ?", (req_id,))
        raw_auth = cursor.fetchone()["auth_data_json"]
        conn.close()

        self.assertNotIn("TopSecretPassword123!", raw_auth)
        self.assertTrue(ENC_PREFIX in raw_auth or DPAPI_PREFIX in raw_auth)

        loaded = ApiRepository.get_request_by_id(req_id)
        self.assertEqual(loaded.auth_data.get("password"), "TopSecretPassword123!")

    def test_11_history_query_secrets_redacted(self):
        secret_url = f"{self.base_url}/endpoint?token=secret_abc_123&user=john&api_key=sk-999888&secret=xyz"
        entry = ApiHistoryEntry(
            method="GET",
            url=secret_url,
            status_code=200,
            status_text="OK"
        )
        entry_id = ApiRepository.add_history_entry(entry)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM api_history WHERE id = ?", (entry_id,))
        stored_url = cursor.fetchone()["url"]
        conn.close()

        self.assertNotIn("secret_abc_123", stored_url)
        self.assertNotIn("sk-999888", stored_url)
        self.assertNotIn("xyz", stored_url)
        self.assertIn("token=%5BREDACTED%5D", stored_url)
        self.assertIn("api_key=%5BREDACTED%5D", stored_url)
        self.assertIn("user=john", stored_url)

    def test_12_curl_generation_redacts_by_default(self):
        url = "https://api.example.com/data?token=secret123&page=2"
        headers = {
            "Authorization": "Bearer token_xyz",
            "X-API-Key": "my-key-999",
            "Accept": "application/json"
        }

        # Default redaction = True
        curl_redacted = ApiClientService.generate_curl_command("GET", url, headers)
        self.assertNotIn("token_xyz", curl_redacted)
        self.assertNotIn("my-key-999", curl_redacted)
        self.assertIn("[REDACTED]", curl_redacted)
        self.assertIn("token=%5BREDACTED%5D", curl_redacted)
        self.assertIn("page=2", curl_redacted)

        # Explicit redaction = False (when user opts in)
        curl_raw = ApiClientService.generate_curl_command("GET", url, headers, redact_secrets=False)
        self.assertIn("token_xyz", curl_raw)
        self.assertIn("my-key-999", curl_raw)
        self.assertIn("token=secret123", curl_raw)

    # ─────────────────────────────────────────────────────────
    # 3. Repository CRUD & Legacy Migration Tests
    # ─────────────────────────────────────────────────────────

    def test_13_repository_crud_operations(self):
        # Create
        req = ApiRequest(name="CRUD Test", method="POST", url="https://example.com/api", collection_name="Suite")
        req_id = ApiRepository.add_request(req)
        self.assertIsNotNone(req_id)

        # Read
        fetched = ApiRepository.get_request_by_id(req_id)
        self.assertEqual(fetched.name, "CRUD Test")
        self.assertEqual(fetched.collection_name, "Suite")

        # Update
        fetched.name = "CRUD Test Updated"
        fetched.is_favorite = True
        self.assertTrue(ApiRepository.update_request(fetched))

        updated = ApiRepository.get_request_by_id(req_id)
        self.assertEqual(updated.name, "CRUD Test Updated")
        self.assertTrue(updated.is_favorite)

        # Toggle Favorite
        ApiRepository.toggle_favorite(req_id)
        toggled = ApiRepository.get_request_by_id(req_id)
        self.assertFalse(toggled.is_favorite)

        # Search & Collections
        found = ApiRepository.get_all_requests(collection="Suite", search="Updated")
        self.assertTrue(any(r.id == req_id for r in found))
        colls = ApiRepository.get_collections()
        self.assertIn("Suite", colls)

        # Delete
        self.assertTrue(ApiRepository.delete_request(req_id))
        self.assertIsNone(ApiRepository.get_request_by_id(req_id))

    def test_14_legacy_saved_requests_backward_compatibility(self):
        """Ensure requests saved before encryption can still be read and updated without data loss."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO saved_api_requests (
                name, method, url, auth_type, auth_data_json, headers_json, collection_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "Legacy Plaintext Request",
            "GET",
            "https://legacy.example.com",
            "bearer",
            json.dumps({"token": "raw_unencrypted_legacy_token"}),
            json.dumps([{"enabled": True, "key": "Authorization", "value": "Bearer raw_legacy_auth"}]),
            "Legacy"
        ))
        conn.commit()
        legacy_id = cursor.lastrowid
        conn.close()

        # Load via repository
        loaded = ApiRepository.get_request_by_id(legacy_id)
        self.assertIsNotNone(loaded)
        # Should gracefully return the legacy value without error
        self.assertEqual(loaded.auth_data.get("token"), "raw_unencrypted_legacy_token")
        self.assertEqual(loaded.headers[0]["value"], "Bearer raw_legacy_auth")

        # Saving/Updating it now must securely encrypt it
        ApiRepository.update_request(loaded)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auth_data_json FROM saved_api_requests WHERE id = ?", (legacy_id,))
        updated_auth = cursor.fetchone()["auth_data_json"]
        conn.close()

        self.assertNotIn("raw_unencrypted_legacy_token", updated_auth)
        self.assertTrue(ENC_PREFIX in updated_auth or DPAPI_PREFIX in updated_auth)

        # Re-read
        migrated = ApiRepository.get_request_by_id(legacy_id)
        self.assertEqual(migrated.auth_data.get("token"), "raw_unencrypted_legacy_token")


if __name__ == "__main__":
    unittest.main()
