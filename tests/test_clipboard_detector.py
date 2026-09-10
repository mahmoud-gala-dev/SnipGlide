import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import base64
import unittest

from snipglide.services.clipboard_content_detector import (
    ClipboardContentDetector,
    TYPE_PLAIN_TEXT, TYPE_URL, TYPE_JSON, TYPE_XML, TYPE_SQL,
    TYPE_CODE, TYPE_STACK_TRACE, TYPE_UUID, TYPE_JWT, TYPE_EMAIL
)

class TestClipboardContentDetector(unittest.TestCase):

    def test_detect_uuid(self):
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(ClipboardContentDetector.detect_type(valid_uuid), TYPE_UUID)

        # Invalid UUID format
        invalid_uuid = "123e4567-e89b-12d3-a456-42661417400Z"
        self.assertNotEqual(ClipboardContentDetector.detect_type(invalid_uuid), TYPE_UUID)

    def test_detect_jwt(self):
        # Valid JWT structure (Base64url JSON header and payload)
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(b'{"sub":"1234567890","name":"Mahmoud"}').decode().rstrip("=")
        sig = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        valid_jwt = f"{header}.{payload}.{sig}"

        self.assertEqual(ClipboardContentDetector.detect_type(valid_jwt), TYPE_JWT)

    def test_detect_jwt_like_invalid_string(self):
        # 3 parts with dots but not valid base64 json
        bogus_jwt = "some.random.string"
        self.assertNotEqual(ClipboardContentDetector.detect_type(bogus_jwt), TYPE_JWT)

    def test_detect_email(self):
        valid_email = "dev@snipglide.com"
        self.assertEqual(ClipboardContentDetector.detect_type(valid_email), TYPE_EMAIL)

        # Invalid email (no domain dot)
        invalid_email = "dev@snipglide"
        self.assertNotEqual(ClipboardContentDetector.detect_type(invalid_email), TYPE_EMAIL)

    def test_detect_url(self):
        https_url = "https://github.com/mahmoud-gala-dev/SnipGlide"
        self.assertEqual(ClipboardContentDetector.detect_type(https_url), TYPE_URL)

        www_url = "www.google.com/search?q=python"
        self.assertEqual(ClipboardContentDetector.detect_type(www_url), TYPE_URL)

    def test_detect_json(self):
        valid_json_obj = '{"app": "SnipGlide", "version": 2.0, "active": true}'
        self.assertEqual(ClipboardContentDetector.detect_type(valid_json_obj), TYPE_JSON)

        valid_json_arr = '[1, 2, 3, "test"]'
        self.assertEqual(ClipboardContentDetector.detect_type(valid_json_arr), TYPE_JSON)

    def test_detect_json_containing_url(self):
        # JSON containing URL inside string values should still be classified as JSON
        json_with_url = '{"service": "github", "url": "https://github.com/mahmoud-gala-dev/SnipGlide"}'
        self.assertEqual(ClipboardContentDetector.detect_type(json_with_url), TYPE_JSON)

    def test_detect_xml(self):
        xml_text = "<?xml version='1.0' encoding='UTF-8'?><note><to>Dev</to><from>Antigravity</from></note>"
        self.assertEqual(ClipboardContentDetector.detect_type(xml_text), TYPE_XML)

        html_snippet = "<div class='container'><p>Hello World</p></div>"
        self.assertEqual(ClipboardContentDetector.detect_type(html_snippet), TYPE_XML)

    def test_detect_sql(self):
        select_sql = "SELECT id, name, email FROM users WHERE active = 1 ORDER BY created_at DESC;"
        self.assertEqual(ClipboardContentDetector.detect_type(select_sql), TYPE_SQL)

        insert_sql = "INSERT INTO settings (key, value) VALUES ('theme', 'dark');"
        self.assertEqual(ClipboardContentDetector.detect_type(insert_sql), TYPE_SQL)

    def test_sql_keyword_in_normal_sentence_not_sql(self):
        # Regular conversational English containing words like "select" or "update"
        sentence = "I will select the best option tomorrow morning."
        self.assertNotEqual(ClipboardContentDetector.detect_type(sentence), TYPE_SQL)

    def test_detect_python_stack_trace(self):
        tb = """Traceback (most recent call last):
  File "app.py", line 42, in <module>
    main()
  File "app.py", line 25, in main
    raise ValueError("Something went wrong!")
ValueError: Something went wrong!"""
        self.assertEqual(ClipboardContentDetector.detect_type(tb), TYPE_STACK_TRACE)

    def test_detect_node_stack_trace(self):
        node_err = """Error: Cannot find module 'express'
    at Function.Module._resolveFilename (internal/modules/cjs/loader.js:889:15)
    at Function.Module._load (internal/modules/cjs/loader.js:745:27)
    at Function.executeUserEntryPoint [as runMain] (internal/modules/run_main.js:76:12)"""
        self.assertEqual(ClipboardContentDetector.detect_type(node_err), TYPE_STACK_TRACE)

    def test_detect_code(self):
        py_code = "def calculate_total(price, tax=0.15):\n    return price * (1 + tax)"
        self.assertEqual(ClipboardContentDetector.detect_type(py_code), TYPE_CODE)

        js_code = "const handleClick = (e) => {\n  console.log('Button clicked');\n};"
        self.assertEqual(ClipboardContentDetector.detect_type(js_code), TYPE_CODE)

    def test_plain_text_and_arabic(self):
        arabic_note = "تذكر شراء القهوة وإنهاء التقرير الأسبوعي قبل الساعة الخامسة."
        self.assertEqual(ClipboardContentDetector.detect_type(arabic_note), TYPE_PLAIN_TEXT)

        english_note = "Just a quick note about the meeting tomorrow at 10 AM."
        self.assertEqual(ClipboardContentDetector.detect_type(english_note), TYPE_PLAIN_TEXT)

    def test_empty_and_whitespace_input(self):
        self.assertEqual(ClipboardContentDetector.detect_type(""), TYPE_PLAIN_TEXT)
        self.assertEqual(ClipboardContentDetector.detect_type("   \n\t  "), TYPE_PLAIN_TEXT)

    def test_very_large_text_fast_path(self):
        # Generate > 32KB of data
        big_json = json.dumps([{"id": i, "name": f"User_{i}"} for i in range(1200)])
        self.assertGreater(len(big_json), 32768)
        self.assertEqual(ClipboardContentDetector.detect_type(big_json), TYPE_JSON)

        big_text = "Standard sentence for testing large clipboard payloads.\n" * 800
        self.assertGreater(len(big_text), 32768)
        self.assertEqual(ClipboardContentDetector.detect_type(big_text), TYPE_PLAIN_TEXT)

    def test_sensitive_detection(self):
        # Private key
        private_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        self.assertTrue(ClipboardContentDetector.is_sensitive(private_key))

        # API secret
        api_token = 'api_key = "sample_dummy_mock_secret_key_12345"'
        self.assertTrue(ClipboardContentDetector.is_sensitive(api_token))

        # Normal text
        self.assertFalse(ClipboardContentDetector.is_sensitive("Hello world from SnipGlide"))


if __name__ == "__main__":
    unittest.main()
