import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from snipglide.database.connection import init_db
from snipglide.models.api_request import ApiRequest, ApiHistoryEntry
from snipglide.services.api_client_service import ApiClientService
from snipglide.database.api_repo import ApiRepository


class MockHttpHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress console logging

    def do_GET(self):
        if self.path.startswith("/json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = json.dumps({"status": "ok", "message": "hello world", "auth": self.headers.get("Authorization", "")})
            self.wfile.write(payload.encode("utf-8"))
        elif self.path.startswith("/error-404"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Resource Not Found")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Plain Text OK")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {"received_length": len(body), "echo": body.decode("utf-8", errors="replace")}
        self.wfile.write(json.dumps(resp).encode("utf-8"))


class TestApiClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        # Start local mock HTTP server
        cls.server = HTTPServer(("127.0.0.1", 0), MockHttpHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_build_final_url_and_params(self):
        base = "https://api.example.com/v1/users?page=1"
        params = [
            {"key": "sort", "value": "desc", "enabled": True},
            {"key": "limit", "value": "20", "enabled": True},
            {"key": "unused", "value": "val", "enabled": False}
        ]
        url = ApiClientService.build_final_url(base, params)
        self.assertIn("page=1", url)
        self.assertIn("sort=desc", url)
        self.assertIn("limit=20", url)
        self.assertNotIn("unused", url)

    def test_build_final_url_api_key_query(self):
        base = "https://api.example.com/search"
        auth_data = {"key": "api_key", "value": "secret_abc123", "add_to": "query"}
        url = ApiClientService.build_final_url(base, [], auth_type="api_key", auth_data=auth_data)
        self.assertIn("api_key=secret_abc123", url)

    def test_build_headers_bearer_auth(self):
        auth_data = {"token": "my_jwt_token_12345"}
        headers = ApiClientService.build_headers([], auth_type="bearer", auth_data=auth_data, body_type="json")
        self.assertEqual(headers["Authorization"], "Bearer my_jwt_token_12345")
        self.assertIn("application/json", headers["Content-Type"])

    def test_build_headers_basic_auth(self):
        auth_data = {"username": "admin", "password": "secret_password"}
        headers = ApiClientService.build_headers([], auth_type="basic", auth_data=auth_data)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_sanitize_headers(self):
        headers = {
            "Authorization": "Bearer 1234567890abcdef",
            "X-Api-Key": "my-secret-key-12345678",
            "Content-Type": "application/json"
        }
        sanitized = ApiClientService.sanitize_headers_for_display(headers)
        self.assertNotIn("1234567890abcdef", sanitized["Authorization"])
        self.assertIn("...", sanitized["Authorization"])
        self.assertEqual(sanitized["Content-Type"], "application/json")

    def test_generate_curl_command(self):
        url = "https://httpbin.org/post"
        headers = {"Content-Type": "application/json"}
        curl = ApiClientService.generate_curl_command("POST", url, headers, '{"name": "test"}')
        self.assertTrue(curl.startswith("curl -X POST"))
        self.assertIn('https://httpbin.org/post', curl)
        self.assertIn('-H "Content-Type: application/json"', curl)

    def test_execute_get_success(self):
        url = f"http://127.0.0.1:{self.port}/json?test=true"
        headers = {"Authorization": "Bearer test-tok"}
        res = ApiClientService.execute_request("GET", url, headers=headers)

        self.assertFalse(res.is_error)
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/json", res.content_type)
        data = json.loads(res.body)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["auth"], "Bearer test-tok")
        self.assertGreater(res.response_time_ms, 0)
        self.assertGreater(res.response_size_bytes, 0)

    def test_execute_post_success(self):
        url = f"http://127.0.0.1:{self.port}/post-data"
        body_bytes = json.dumps({"hello": "snipglide"}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        res = ApiClientService.execute_request("POST", url, headers=headers, body_bytes=body_bytes)

        self.assertFalse(res.is_error)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.body)
        self.assertEqual(data["received_length"], len(body_bytes))

    def test_execute_http_404_error(self):
        url = f"http://127.0.0.1:{self.port}/error-404"
        res = ApiClientService.execute_request("GET", url)
        self.assertFalse(res.is_error)  # Valid HTTP response received
        self.assertEqual(res.status_code, 404)
        self.assertIn("Resource Not Found", res.body)

    def test_execute_invalid_url_and_connection_failure(self):
        # Port 59999 or non-existent address
        url = "http://127.0.0.1:59999/unreachable"
        res = ApiClientService.execute_request("GET", url, timeout=1.0)
        self.assertTrue(res.is_error)
        self.assertTrue("Timed Out" in res.error_message or "Connection" in res.error_message)

    def test_api_repository_crud(self):
        req = ApiRequest(
            name="Get User Profile",
            method="GET",
            url="https://api.github.com/user",
            params=[{"key": "id", "value": "123", "enabled": True}],
            headers=[{"key": "Accept", "value": "application/json", "enabled": True}],
            auth_type="bearer",
            auth_data={"token": "tok_123"},
            collection_name="GitHub API",
            is_favorite=True
        )

        req_id = ApiRepository.add_request(req)
        self.assertIsNotNone(req_id)

        # Retrieve
        fetched = ApiRepository.get_request_by_id(req_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Get User Profile")
        self.assertEqual(fetched.method, "GET")
        self.assertEqual(fetched.collection_name, "GitHub API")
        self.assertTrue(fetched.is_favorite)
        self.assertEqual(len(fetched.params), 1)

        # Update
        fetched.name = "Get User Profile Updated"
        fetched.method = "POST"
        ok = ApiRepository.update_request(fetched)
        self.assertTrue(ok)
        updated = ApiRepository.get_request_by_id(req_id)
        self.assertEqual(updated.name, "Get User Profile Updated")
        self.assertEqual(updated.method, "POST")

        # Toggle favorite
        ApiRepository.toggle_favorite(req_id)
        self.assertFalse(ApiRepository.get_request_by_id(req_id).is_favorite)

        # Delete
        del_ok = ApiRepository.delete_request(req_id)
        self.assertTrue(del_ok)
        self.assertIsNone(ApiRepository.get_request_by_id(req_id))

    def test_api_history_operations(self):
        ApiRepository.clear_history()
        entry = ApiHistoryEntry(
            method="GET",
            url="https://api.example.com/items",
            status_code=200,
            status_text="OK",
            response_time_ms=145.2,
            response_size_bytes=1024
        )
        hid = ApiRepository.add_history_entry(entry)
        self.assertIsNotNone(hid)

        history = ApiRepository.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].url, "https://api.example.com/items")
        self.assertEqual(history[0].status_code, 200)

        ApiRepository.clear_history()
        self.assertEqual(len(ApiRepository.get_history()), 0)


if __name__ == "__main__":
    unittest.main()
