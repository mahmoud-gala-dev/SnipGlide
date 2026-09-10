import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import base64
import hashlib
import re
import unittest

from snipglide.services.dev_tools_service import (
    JsonTools, Base64Tools, UrlTools, JwtTools,
    UuidTools, TimestampTools, HashTools, TextUtils
)

class TestDevToolsService(unittest.TestCase):

    # ══════════════════════════════════════════════════════════════════
    # 1. JSON TOOLS TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_json_valid_beautify_and_minify(self):
        data = {
            "name": "سنيب جلايد",
            "version": 2.0,
            "emoji": "🚀✨",
            "nested": {
                "active": True,
                "items": [1, 2, 3]
            }
        }
        raw_json = json.dumps(data, ensure_ascii=False)
        ok, beautified, err = JsonTools.beautify(raw_json)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertIn("سنيب جلايد", beautified)
        self.assertIn("🚀✨", beautified)
        self.assertIn("\n", beautified)

        ok, minified, err = JsonTools.minify(beautified)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertNotIn("\n", minified)
        self.assertEqual(json.loads(minified), data)

    def test_json_invalid_returns_line_and_col(self):
        broken = '{\n  "title": "SnipGlide",\n  "broken": \n}'
        ok, msg, err_details = JsonTools.validate(broken)
        self.assertFalse(ok)
        self.assertIsNotNone(err_details)
        self.assertIn("line", err_details)
        self.assertIn("column", err_details)
        self.assertEqual(err_details["line"], 4)
        self.assertIn("سطر 4", msg)

    def test_json_sort_keys(self):
        sample = '{"zeta": 1, "alpha": 2, "mid": {"z": 9, "a": 1}}'
        ok, sorted_res, _ = JsonTools.sort_keys(sample)
        self.assertTrue(ok)
        self.assertTrue(sorted_res.index('"alpha"') < sorted_res.index('"mid"') < sorted_res.index('"zeta"'))

    def test_json_escape_and_safe_unescape_arabic_emoji(self):
        # 1. Test Arabic and Emoji unescaping without Mojibake/corruption
        arabic_text = 'مرحبا بك في "SnipGlide"!\nالسطر الثاني\tعلامة تبويب \\ شرطة مائلة 🚀'
        escaped = JsonTools.escape(arabic_text)
        self.assertNotIn("\n", escaped)
        self.assertNotIn("\t", escaped)

        ok, unescaped = JsonTools.unescape(escaped)
        self.assertTrue(ok)
        self.assertEqual(unescaped, arabic_text)
        self.assertIn("مرحبا", unescaped)
        self.assertIn("🚀", unescaped)

        # 2. Test specific unicode escape sequences: \t \" \\ \u0645\u0631\u062d\u0628\u0627
        raw_escaped = r'Greeting: \u0645\u0631\u062d\u0628\u0627 \"World\" \\ path \t tab \n newline'
        ok, res = JsonTools.unescape(raw_escaped)
        self.assertTrue(ok)
        self.assertIn("Greeting: مرحبا \"World\" \\ path \t tab \n newline", res)

        # 3. Test that pure Arabic string is NEVER corrupted when unescaped
        pure_arabic = "اللغة العربية الجميلة لا تتشوه أبداً"
        ok, res = JsonTools.unescape(pure_arabic)
        self.assertTrue(ok)
        self.assertEqual(res, pure_arabic)

    def test_json_empty_input(self):
        ok, _, err = JsonTools.beautify("")
        self.assertFalse(ok)
        ok, _, err = JsonTools.minify("   ")
        self.assertFalse(ok)
        ok, _, err = JsonTools.validate("")
        self.assertFalse(ok)

    # ══════════════════════════════════════════════════════════════════
    # 2. BASE64 TOOLS TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_base64_ascii_utf8_arabic_emoji(self):
        cases = [
            "Hello World",
            "أهلاً وسهلاً بكم في نظام ويندوز",
            "Developer Tools Pro 🛠️🚀🔥",
            "",
            "Lines with\nNewlines and\tTabs and Special chars: <>&\"'/$%#"
        ]
        for c in cases:
            ok, enc = Base64Tools.encode(c)
            self.assertTrue(ok)
            ok, dec = Base64Tools.decode(enc)
            self.assertTrue(ok)
            self.assertEqual(dec, c)

    def test_base64_invalid_input_safe_no_crash(self):
        # Corrupted characters
        ok, res = Base64Tools.decode("Invalid!@#$Base64*&^%")
        self.assertFalse(ok)
        self.assertIn("غير صالح", res)

        # Truncated padding
        ok, res = Base64Tools.decode("SGVsbG8")  # missing '='
        self.assertTrue(ok)
        self.assertEqual(res, "Hello")

    # ══════════════════════════════════════════════════════════════════
    # 3. URL TOOLS TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_url_encode_decode(self):
        original = "https://snipglide.dev/search?q=محرر الأكواد & أدوات&lang=ar#section"
        encoded = UrlTools.encode(original)
        self.assertNotIn(" ", encoded)
        self.assertNotIn("محرر", encoded)
        decoded = UrlTools.decode(encoded)
        self.assertEqual(decoded, original)

    def test_url_query_string_parser(self):
        # Repeated params and special chars
        url = "https://api.example.com/v1/query?tag=python&tag=qt&tag=windows&user=محمود&page=1&empty=&flag#frag"
        ok, flat, pretty = UrlTools.parse_query_string(url)
        self.assertTrue(ok)
        self.assertEqual(flat["tag"], ["python", "qt", "windows"])
        self.assertEqual(flat["user"], "محمود")
        self.assertEqual(flat["page"], "1")
        self.assertEqual(flat["empty"], "")

        # Empty input
        ok, _, err = UrlTools.parse_query_string("")
        self.assertFalse(ok)

    # ══════════════════════════════════════════════════════════════════
    # 4. JWT TOOLS TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_jwt_decode_and_signature_disclaimer(self):
        # Construct realistic JWT with header and payload
        header = {"alg": "HS256", "typ": "JWT", "kid": "key_123"}
        payload = {
            "sub": "user_101",
            "name": "محمود جلال",
            "iat": 1600000000,
            "nbf": 1600000000,
            "exp": 2000000000
        }
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode().rstrip("=")
        token = f"{h_b64}.{p_b64}.mockedsignature"

        ok, details, summary = JwtTools.decode_jwt(token)
        self.assertTrue(ok)
        self.assertEqual(details["header"]["alg"], "HS256")
        self.assertEqual(details["payload"]["sub"], "user_101")
        self.assertEqual(details["payload"]["name"], "محمود جلال")
        self.assertIsNotNone(details["human_exp"])
        self.assertIsNotNone(details["human_iat"])
        self.assertIsNotNone(details["human_nbf"])
        self.assertIn("UTC", details["human_exp"])

        # Crucial security verification: decoder MUST clearly state it does NOT verify signature
        self.assertIn("لا تعني التحقق من صحة التوقيع", details["warning"])
        self.assertIn("لا يثبت صحة التوقيع", summary)

    def test_jwt_invalid_format(self):
        ok, _, err = JwtTools.decode_jwt("not_a_jwt_token")
        self.assertFalse(ok)
        self.assertIn("غير صالح", err)

        ok, _, err = JwtTools.decode_jwt("")
        self.assertFalse(ok)

        # Invalid base64 in header
        ok, _, err = JwtTools.decode_jwt("???invalid???.payload.sig")
        self.assertFalse(ok)

    # ══════════════════════════════════════════════════════════════════
    # 5. UUID TOOLS TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_uuid_v4_generation_and_validation(self):
        u = UuidTools.generate_v4()
        self.assertTrue(UuidTools.is_valid_uuid(u))
        self.assertEqual(len(u), 36)
        self.assertEqual(u.count("-"), 4)

        # Batch generation
        batch = UuidTools.generate_batch(10)
        self.assertEqual(len(batch), 10)
        self.assertEqual(len(set(batch)), 10)
        for uid in batch:
            self.assertTrue(UuidTools.is_valid_uuid(uid))

        # Test boundary clamping (e.g. negative or >100)
        clamped_min = UuidTools.generate_batch(-5)
        self.assertEqual(len(clamped_min), 1)
        clamped_max = UuidTools.generate_batch(500)
        self.assertEqual(len(clamped_max), 100)

        self.assertFalse(UuidTools.is_valid_uuid("not-a-uuid"))
        self.assertFalse(UuidTools.is_valid_uuid(""))

    # ══════════════════════════════════════════════════════════════════
    # 6. TIMESTAMP CONVERTER TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_timestamp_conversions_and_boundaries(self):
        # 1. Normal seconds
        ok, res = TimestampTools.from_timestamp(1700000000)
        self.assertTrue(ok)
        self.assertEqual(res["unix_seconds"], "1700000000")
        self.assertEqual(res["unix_milliseconds"], "1700000000000")
        self.assertIn("UTC", res["utc_datetime"])

        # 2. Milliseconds auto-detection
        ok, res = TimestampTools.from_timestamp(1700000000000)
        self.assertTrue(ok)
        self.assertEqual(res["unix_seconds"], "1700000000")

        # 3. Epoch boundary (0)
        ok, res = TimestampTools.from_timestamp(0)
        self.assertTrue(ok)
        self.assertEqual(res["unix_seconds"], "0")
        self.assertIn("1970-01-01", res["utc_datetime"])

        # 4. From Datetime string (ISO & standard)
        ok, res = TimestampTools.from_datetime_string("2026-09-10 10:00:00")
        self.assertTrue(ok)
        self.assertTrue(int(res["unix_seconds"]) > 0)

        # 5. Invalid datetime string
        ok, res = TimestampTools.from_datetime_string("invalid_date_format_xyz")
        self.assertFalse(ok)
        self.assertIn("error", res)

    # ══════════════════════════════════════════════════════════════════
    # 7. HASH TOOLS TESTS (Comparing with hashlib standards)
    # ══════════════════════════════════════════════════════════════════
    def test_hash_standards_comparison(self):
        test_inputs = [
            "SnipGlide Python Pro 2026",
            "مرحبا بكم في تجربة الهاش العربي",
            "",
            "Special characters: !@#$%^&*()_+{}[]:;\"'\\|<>,.?/~`"
        ]
        for text in test_inputs:
            h = HashTools.compute_hashes(text)
            b = text.encode("utf-8")
            self.assertEqual(h["md5"], hashlib.md5(b).hexdigest())
            self.assertEqual(h["sha1"], hashlib.sha1(b).hexdigest())
            self.assertEqual(h["sha256"], hashlib.sha256(b).hexdigest())
            self.assertEqual(h["sha512"], hashlib.sha512(b).hexdigest())
            self.assertIn("تنبيه أمني", h["warning"])

    # ══════════════════════════════════════════════════════════════════
    # 8. TEXT UTILITIES TESTS
    # ══════════════════════════════════════════════════════════════════
    def test_text_casing_transformations(self):
        input_text = "get user_profile-data.withMixed:punctuation"
        self.assertEqual(TextUtils.to_camel_case(input_text), "getUserProfileDataWithMixedPunctuation")
        self.assertEqual(TextUtils.to_pascal_case(input_text), "GetUserProfileDataWithMixedPunctuation")
        self.assertEqual(TextUtils.to_snake_case(input_text), "get_user_profile_data_with_mixed_punctuation")
        self.assertEqual(TextUtils.to_kebab_case(input_text), "get-user-profile-data-with-mixed-punctuation")
        self.assertEqual(TextUtils.to_uppercase("hello world"), "HELLO WORLD")
        self.assertEqual(TextUtils.to_lowercase("HELLO WORLD"), "hello world")

    def test_text_lines_and_metrics(self):
        multiline = "Banana\nApple\nBanana\nOrange\nApple\nMango"
        no_dups = TextUtils.remove_duplicate_lines(multiline)
        self.assertEqual(no_dups, "Banana\nApple\nOrange\nMango")

        sorted_lines = TextUtils.sort_lines(no_dups)
        self.assertEqual(sorted_lines, "Apple\nBanana\nMango\nOrange")

        spaced = "   line 1   \n   line 2   "
        self.assertEqual(TextUtils.trim_whitespace(spaced), "line 1\nline 2")

        arabic_text = "بسم الله الرحمن الرحيم\nنص عربي للتجربة والعد"
        metrics = TextUtils.count_metrics(arabic_text)
        self.assertEqual(metrics["lines"], 2)
        self.assertEqual(metrics["words"], 8)
        self.assertTrue(metrics["characters"] > 0)
        self.assertTrue(metrics["characters_no_spaces"] < metrics["characters"])

if __name__ == "__main__":
    unittest.main()
