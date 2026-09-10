import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import base64
import time

from snipglide.services.dev_tools_service import (
    JsonTools, Base64Tools, UrlTools, JwtTools,
    UuidTools, TimestampTools, HashTools, TextUtils
)

def run_tests():
    print("==================================================")
    print("🚀 Running SnipGlide Developer Toolbox Unit Tests")
    print("==================================================")

    # ── 1. Test JSON Tools ──
    print("\n[1] Testing JSON Tools...")
    valid_json = '{"name": "SnipGlide", "version": 2.0, "tools": ["json", "base64"]}'
    ok, beautified, _ = JsonTools.beautify(valid_json)
    assert ok and "  \"name\": \"SnipGlide\"" in beautified, "JSON Beautify failed"
    print("  ✓ JsonTools.beautify passed")

    ok, minified, _ = JsonTools.minify(beautified)
    assert ok and "\n" not in minified and '{"name":"SnipGlide"' in minified, "JSON Minify failed"
    print("  ✓ JsonTools.minify passed")

    ok, val_msg, _ = JsonTools.validate(valid_json)
    assert ok and "صالح" in val_msg, "JSON Validate passed condition failed"
    print("  ✓ JsonTools.validate (valid) passed")

    invalid_json = '{"name": "SnipGlide", "broken": }'
    ok, err_msg, details = JsonTools.validate(invalid_json)
    assert not ok and details is not None and "line" in details, "JSON Validate error reporting failed"
    print(f"  ✓ JsonTools.validate (invalid error reported correctly: line {details['line']}, col {details['column']})")

    ok, sorted_json, _ = JsonTools.sort_keys('{"z": 1, "a": 2, "m": 3}')
    assert ok and sorted_json.index('"a"') < sorted_json.index('"m"') < sorted_json.index('"z"'), "JSON Sort Keys failed"
    print("  ✓ JsonTools.sort_keys passed")

    escaped = JsonTools.escape('He said "Hello\nWorld"!')
    assert '\\"' in escaped and '\\n' in escaped, "JSON Escape failed"
    ok, unescaped = JsonTools.unescape(escaped)
    assert ok and unescaped == 'He said "Hello\nWorld"!', "JSON Unescape failed"
    print("  ✓ JsonTools.escape / unescape passed")

    # ── 2. Test Base64 Tools ──
    print("\n[2] Testing Base64 Tools...")
    raw_arabic = "مرحبا بكم في SnipGlide Pro! 🚀 2026"
    ok, b64 = Base64Tools.encode(raw_arabic)
    assert ok and len(b64) > 0, "Base64 Encode failed"
    ok, decoded = Base64Tools.decode(b64)
    assert ok and decoded == raw_arabic, "Base64 Decode UTF-8 mismatch"
    print("  ✓ Base64Tools UTF-8 encode/decode passed")

    # Safe error handling with broken base64
    ok, err = Base64Tools.decode("This is definitely not base64 !!!@@#")
    assert not ok or "[بيانات" in err, "Base64 invalid handling failed"
    print("  ✓ Base64Tools safe error handling without crash passed")

    # ── 3. Test URL Tools ──
    print("\n[3] Testing URL Tools...")
    raw_query = "https://example.com/api?user=Mahmoud Gala&category=Dev Tools&id=42&tag=python&tag=qt"
    encoded_url = UrlTools.encode("Mahmoud Gala & Co")
    assert "%20" in encoded_url and "%26" in encoded_url, "URL Encode failed"
    assert UrlTools.decode(encoded_url) == "Mahmoud Gala & Co", "URL Decode failed"
    print("  ✓ UrlTools encode / decode passed")

    ok, params, pretty_qs = UrlTools.parse_query_string(raw_query)
    assert ok and params["user"] == "Mahmoud Gala" and params["id"] == "42" and isinstance(params["tag"], list), "Query String parser failed"
    print("  ✓ UrlTools query string parser passed")

    # ── 4. Test JWT Tools ──
    print("\n[4] Testing JWT Decoder...")
    # Simulated standard JWT (Header: {"alg":"HS256","typ":"JWT"}, Payload: {"sub":"1234567890","name":"John Doe","iat":1516239022,"exp":1999999999})
    mock_header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    mock_payload = base64.urlsafe_b64encode(json.dumps({"sub": "user_42", "role": "admin", "iat": 1700000000, "exp": 1900000000}).encode()).decode().rstrip("=")
    mock_jwt = f"{mock_header}.{mock_payload}.signatureplaceholder"

    ok, jwt_data, summary = JwtTools.decode_jwt(mock_jwt)
    assert ok and jwt_data["payload"]["sub"] == "user_42", "JWT Decode failed"
    assert "human_exp" in jwt_data and jwt_data["human_exp"] is not None, "JWT exp parsing failed"
    assert "تنبيه" in jwt_data["warning"] or "Signature" in jwt_data["warning"], "JWT warning missing"
    print("  ✓ JwtTools decode, expiration parsing, and security warning passed")

    # ── 5. Test UUID Tools ──
    print("\n[5] Testing UUID Tools...")
    u1 = UuidTools.generate_v4()
    assert len(u1) == 36 and u1.count("-") == 4, "UUID v4 format invalid"
    batch = UuidTools.generate_batch(5)
    assert len(batch) == 5 and len(set(batch)) == 5, "UUID batch generation failed"
    print("  ✓ UuidTools single and batch v4 generation passed")

    # ── 6. Test Timestamp Tools ──
    print("\n[6] Testing Timestamp Tools...")
    curr = TimestampTools.get_current()
    assert "unix_seconds" in curr and "iso_8601" in curr, "Timestamp current generation failed"
    
    ok, conv = TimestampTools.from_timestamp(1700000000)
    assert ok and conv["unix_seconds"] == "1700000000" and "UTC" in conv["utc_datetime"], "Timestamp conversion from int failed"

    ok, conv_str = TimestampTools.from_datetime_string("2026-09-10 12:00:00")
    assert ok and int(conv_str["unix_seconds"]) > 0, "Timestamp conversion from string failed"
    print("  ✓ TimestampTools from_timestamp and from_datetime_string passed")

    # ── 7. Test Hash Tools ──
    print("\n[7] Testing Hash Tools...")
    sample_text = "SnipGlide Pro Security 2026"
    hashes = HashTools.compute_hashes(sample_text)
    assert len(hashes["md5"]) == 32, "MD5 length invalid"
    assert len(hashes["sha1"]) == 40, "SHA-1 length invalid"
    assert len(hashes["sha256"]) == 64, "SHA-256 length invalid"
    assert len(hashes["sha512"]) == 128, "SHA-512 length invalid"
    assert "تنبيه أمني" in hashes["warning"], "Hash security warning missing"
    print("  ✓ HashTools MD5, SHA-1, SHA-256, SHA-512 and security warning passed")

    # ── 8. Test Text Utilities ──
    print("\n[8] Testing Text Utilities...")
    assert TextUtils.to_uppercase("hello world") == "HELLO WORLD", "Uppercase failed"
    assert TextUtils.to_lowercase("HELLO WORLD") == "hello world", "Lowercase failed"
    assert TextUtils.to_camel_case("get user_profile_data") == "getUserProfileData", "camelCase failed"
    assert TextUtils.to_pascal_case("get user_profile_data") == "GetUserProfileData", "PascalCase failed"
    assert TextUtils.to_snake_case("getUserProfileData") == "get_user_profile_data", "snake_case failed"
    assert TextUtils.to_kebab_case("getUserProfileData") == "get-user-profile-data", "kebab-case failed"

    dup_text = "Apple\nBanana\nApple\nCherry\nBanana"
    no_dups = TextUtils.remove_duplicate_lines(dup_text)
    assert no_dups == "Apple\nBanana\nCherry", "Remove duplicate lines failed"

    sorted_lines = TextUtils.sort_lines("Zebra\nApple\nMango")
    assert sorted_lines == "Apple\nMango\nZebra", "Sort lines failed"

    metrics = TextUtils.count_metrics("Hello world from SnipGlide Pro\nSecond line")
    assert metrics["words"] == 7 and metrics["lines"] == 2 and metrics["characters"] > 0, "Metrics count failed"
    print("  ✓ TextUtils transformations, line ops, and metrics passed")

    print("\n==================================================")
    print("🎉 ALL DEVELOPER TOOLBOX UNIT TESTS PASSED (100%)!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
