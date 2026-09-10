import json
import base64
import urllib.parse
import uuid
import datetime
import hashlib
import re
from typing import Optional, Any, Union

class JsonTools:
    @staticmethod
    def beautify(text: str, indent: int = 2) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """
        Parses and formats JSON with specified indentation.
        Returns: (success, result_or_error_msg, error_details_dict)
        error_details_dict: {"line": int, "column": int, "msg": str} if error
        """
        if not text or not text.strip():
            return False, "النص البرمجي لـ JSON فارغ.", {"line": 1, "column": 1, "msg": "Empty text"}
        try:
            parsed = json.loads(text)
            formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)
            return True, formatted, None
        except json.JSONDecodeError as e:
            err_details = {
                "line": e.lineno,
                "column": e.colno,
                "msg": e.msg,
                "pos": e.pos
            }
            err_str = f"خطأ في تحليل JSON: السطر {e.lineno}، العمود {e.colno} - {e.msg}"
            return False, err_str, err_details
        except Exception as e:
            return False, f"خطأ غير متوقع: {str(e)}", None

    @staticmethod
    def minify(text: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """Minifies JSON by removing all unnecessary whitespace."""
        if not text or not text.strip():
            return False, "النص البرمجي لـ JSON فارغ.", {"line": 1, "column": 1, "msg": "Empty text"}
        try:
            parsed = json.loads(text)
            minified = json.dumps(parsed, separators=(',', ':'), ensure_ascii=False)
            return True, minified, None
        except json.JSONDecodeError as e:
            return False, f"خطأ في تحليل JSON: السطر {e.lineno}، العمود {e.colno} - {e.msg}", {
                "line": e.lineno, "column": e.colno, "msg": e.msg
            }
        except Exception as e:
            return False, f"خطأ غير متوقع: {str(e)}", None

    @staticmethod
    def validate(text: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """Validates JSON and returns syntax error line and column if invalid."""
        if not text or not text.strip():
            return False, "النص البرمجي لـ JSON فارغ.", {"line": 1, "column": 1, "msg": "Empty text"}
        try:
            json.loads(text)
            return True, "✓ كود JSON صالح وسليم تماماً (Valid JSON).", None
        except json.JSONDecodeError as e:
            return False, f"❌ كود JSON غير صالح: سطر {e.lineno}، عمود {e.colno} - {e.msg}", {
                "line": e.lineno, "column": e.colno, "msg": e.msg
            }
        except Exception as e:
            return False, f"❌ خطأ غير متوقع: {str(e)}", None

    @staticmethod
    def sort_keys(text: str, indent: int = 2) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """Sorts dictionary keys alphabetically."""
        if not text or not text.strip():
            return False, "النص البرمجي لـ JSON فارغ.", None
        try:
            parsed = json.loads(text)
            sorted_json = json.dumps(parsed, indent=indent, sort_keys=True, ensure_ascii=False)
            return True, sorted_json, None
        except json.JSONDecodeError as e:
            return False, f"خطأ في تحليل JSON: السطر {e.lineno}، العمود {e.colno} - {e.msg}", {
                "line": e.lineno, "column": e.colno, "msg": e.msg
            }
        except Exception as e:
            return False, f"خطأ غير متوقع: {str(e)}", None

    @staticmethod
    def escape(text: str) -> str:
        """Escapes special characters for embedding in string literals."""
        # Dump as JSON string and slice off outer quotes
        return json.dumps(text)[1:-1]

    @staticmethod
    def unescape(text: str) -> tuple[bool, str]:
        """Unescapes a previously escaped string."""
        try:
            # Wrap in quotes and load as JSON string
            unescaped = json.loads(f'"{text}"')
            return True, unescaped
        except Exception as e:
            # Fallback for raw escape sequences
            try:
                unescaped = bytes(text, "utf-8").decode("unicode_escape")
                return True, unescaped
            except Exception as e2:
                return False, f"فشل إلغاء الهروب (Unescape): {str(e2)}"


class Base64Tools:
    @staticmethod
    def encode(text: str) -> tuple[bool, str]:
        """Encodes UTF-8 string to Base64 safely."""
        try:
            text_bytes = text.encode("utf-8")
            encoded_bytes = base64.b64encode(text_bytes)
            return True, encoded_bytes.decode("ascii")
        except Exception as e:
            return False, f"فشل ترميز Base64: {str(e)}"

    @staticmethod
    def decode(text: str) -> tuple[bool, str]:
        """Decodes Base64 to UTF-8 string safely with error detection without crash."""
        if not text or not text.strip():
            return False, "النص المشفر بـ Base64 فارغ."
        cleaned = text.strip().replace("\r", "").replace("\n", "").replace(" ", "")
        
        # Add required padding if missing
        missing_padding = len(cleaned) % 4
        if missing_padding:
            cleaned += "=" * (4 - missing_padding)

        try:
            decoded_bytes = base64.b64decode(cleaned, validate=True)
            # Try decoding as UTF-8
            try:
                return True, decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # If binary data, show hex representation gracefully
                return True, f"[بيانات ثنائية Binary Data]:\n{decoded_bytes.hex(' ')}"
        except Exception as e:
            return False, f"رمز Base64 غير صالح: {str(e)}"


class UrlTools:
    @staticmethod
    def encode(text: str) -> str:
        """URL encodes a string component."""
        return urllib.parse.quote(text, safe="")

    @staticmethod
    def decode(text: str) -> str:
        """URL decodes an encoded string."""
        return urllib.parse.unquote(text)

    @staticmethod
    def parse_query_string(url_or_query: str) -> tuple[bool, dict[str, Any], str]:
        """
        Parses full URL or query string into structured parameters dictionary and pretty JSON.
        """
        if not url_or_query or not url_or_query.strip():
            return False, {}, "الرابط أو Query String فارغ."

        text = url_or_query.strip()
        # If full URL, extract query part
        if "?" in text:
            query = text.split("?", 1)[1]
        else:
            query = text

        # Strip fragment identifier (#...) if present
        if "#" in query:
            query = query.split("#", 1)[0]

        try:
            parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
            # Flatten single item lists for cleaner output
            flat: dict[str, Any] = {}
            for k, v in parsed.items():
                if len(v) == 1:
                    flat[k] = v[0]
                else:
                    flat[k] = v
            pretty_json = json.dumps(flat, indent=2, ensure_ascii=False)
            return True, flat, pretty_json
        except Exception as e:
            return False, {}, f"فشل تحليل الـ Query String: {str(e)}"


class JwtTools:
    @staticmethod
    def _base64url_decode(input_str: str) -> bytes:
        rem = len(input_str) % 4
        if rem > 0:
            input_str += "=" * (4 - rem)
        return base64.urlsafe_b64decode(input_str.encode("ascii"))

    @staticmethod
    def decode_jwt(token: str) -> tuple[bool, dict[str, Any], str]:
        """
        Decodes JWT header and payload without verifying signature.
        Returns: (success, details_dict, formatted_summary)
        """
        if not token or not token.strip():
            return False, {}, "رمز JWT فارغ."

        cleaned = token.strip()
        parts = cleaned.split(".")
        if len(parts) < 2:
            return False, {}, "رمز JWT غير صالح: يجب أن يحتوي على جزئين على الأقل مفصولين بنقطة (Header.Payload)."

        header_b64, payload_b64 = parts[0], parts[1]
        signature_b64 = parts[2] if len(parts) > 2 else ""

        try:
            header_bytes = JwtTools._base64url_decode(header_b64)
            header_dict = json.loads(header_bytes.decode("utf-8"))
        except Exception as e:
            return False, {}, f"فشل فك تشفير ترويسة JWT (Header): {str(e)}"

        try:
            payload_bytes = JwtTools._base64url_decode(payload_b64)
            payload_dict = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            return False, {}, f"فشل فك تشفير حمولة JWT (Payload): {str(e)}"

        # Analyze timestamps in payload
        human_exp = None
        human_iat = None
        human_nbf = None
        is_expired = None

        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        if "exp" in payload_dict and isinstance(payload_dict["exp"], (int, float)):
            exp_val = payload_dict["exp"]
            exp_dt = datetime.datetime.fromtimestamp(exp_val, tz=datetime.timezone.utc)
            human_exp = exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            is_expired = now_ts > exp_val

        if "iat" in payload_dict and isinstance(payload_dict["iat"], (int, float)):
            iat_val = payload_dict["iat"]
            iat_dt = datetime.datetime.fromtimestamp(iat_val, tz=datetime.timezone.utc)
            human_iat = iat_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        if "nbf" in payload_dict and isinstance(payload_dict["nbf"], (int, float)):
            nbf_val = payload_dict["nbf"]
            nbf_dt = datetime.datetime.fromtimestamp(nbf_val, tz=datetime.timezone.utc)
            human_nbf = nbf_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        details = {
            "header": header_dict,
            "payload": payload_dict,
            "signature": signature_b64,
            "human_exp": human_exp,
            "human_iat": human_iat,
            "human_nbf": human_nbf,
            "is_expired": is_expired,
            "warning": "تنبيه هام: عملية فك التشفير (Decode) لا تعني التحقق من صحة التوقيع (Signature Verification)."
        }

        # Format friendly markdown/text output
        lines = [
            "⚠️ تنبيه أمني: فك التشفير الحالي هو لقراءة المحتوى فقط ولا يثبت صحة التوقيع الرقمي (Signature).",
            "",
            "📋 [1] Header (الترويسة):",
            json.dumps(header_dict, indent=2, ensure_ascii=False),
            "",
            "📦 [2] Payload (الحمولة والبيانات):",
            json.dumps(payload_dict, indent=2, ensure_ascii=False),
            "",
            "⏰ [3] التحليل الزمني (Timestamps):"
        ]
        if human_iat:
            lines.append(f"  • تاريخ الإصدار (iat): {human_iat}")
        if human_nbf:
            lines.append(f"  • غير صالح قبل (nbf): {human_nbf}")
        if human_exp:
            status_tag = " [منتهي الصلاحية ❌ EXPIRED]" if is_expired else " [صالح زمنياً ✓ ACTIVE]"
            lines.append(f"  • تاريخ الانتهاء (exp): {human_exp}{status_tag}")
        if not human_iat and not human_exp:
            lines.append("  • لا توجد حقول تواريخ (exp / iat) داخل التوكن.")

        return True, details, "\n".join(lines)


class UuidTools:
    @staticmethod
    def generate_v4() -> str:
        """Generates a single RFC 4122 compliant UUID v4 string."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_batch(count: int = 5) -> list[str]:
        """Generates a batch of UUID v4 strings (clamped between 1 and 100)."""
        safe_count = max(1, min(count, 100))
        return [str(uuid.uuid4()) for _ in range(safe_count)]


class TimestampTools:
    @staticmethod
    def from_timestamp(ts: Union[int, float]) -> tuple[bool, dict[str, str]]:
        """
        Converts a Unix timestamp (seconds or milliseconds) to all standard formats.
        """
        try:
            # Auto-detect milliseconds if timestamp is large (e.g. > 100,000,000,000)
            if ts > 1e11:
                seconds = ts / 1000.0
                millis = int(ts)
            else:
                seconds = float(ts)
                millis = int(seconds * 1000)

            utc_dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
            local_dt = datetime.datetime.fromtimestamp(seconds)

            return True, {
                "unix_seconds": str(int(seconds)),
                "unix_milliseconds": str(millis),
                "local_datetime": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "utc_datetime": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "iso_8601": utc_dt.isoformat()
            }
        except Exception as e:
            return False, {"error": f"قيمة Timestamp غير صالحة: {str(e)}"}

    @staticmethod
    def from_datetime_string(dt_str: str) -> tuple[bool, dict[str, str]]:
        """
        Converts a date string (ISO 8601 or standard formats) to timestamp and related formats.
        """
        if not dt_str or not dt_str.strip():
            return False, {"error": "النص الزمني فارغ."}

        cleaned = dt_str.strip()
        dt: Optional[datetime.datetime] = None

        # Try ISO format
        try:
            dt = datetime.datetime.fromisoformat(cleaned)
        except Exception:
            pass

        # Try common datetime formats
        if dt is None:
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y"
            ]
            for fmt in formats:
                try:
                    dt = datetime.datetime.strptime(cleaned, fmt)
                    break
                except Exception:
                    continue

        if dt is None:
            return False, {"error": "صيغة التاريخ غير مدعومة. يرجى استخدام ISO 8601 أو YYYY-MM-DD HH:MM:SS"}

        # If naive, assume local timezone
        if dt.tzinfo is None:
            local_dt = dt
            utc_dt = dt.astimezone(datetime.timezone.utc)
            seconds = local_dt.timestamp()
        else:
            utc_dt = dt.astimezone(datetime.timezone.utc)
            local_dt = dt.astimezone()
            seconds = dt.timestamp()

        millis = int(seconds * 1000)

        return True, {
            "unix_seconds": str(int(seconds)),
            "unix_milliseconds": str(millis),
            "local_datetime": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_datetime": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "iso_8601": utc_dt.isoformat()
        }

    @staticmethod
    def get_current() -> dict[str, str]:
        """Returns current system time in all formats."""
        now_dt = datetime.datetime.now()
        utc_dt = datetime.datetime.now(datetime.timezone.utc)
        seconds = now_dt.timestamp()
        millis = int(seconds * 1000)

        return {
            "unix_seconds": str(int(seconds)),
            "unix_milliseconds": str(millis),
            "local_datetime": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_datetime": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "iso_8601": utc_dt.isoformat()
        }


class HashTools:
    @staticmethod
    def compute_hashes(text: str) -> dict[str, str]:
        """Computes MD5, SHA-1, SHA-256, and SHA-512 hashes."""
        encoded = text.encode("utf-8")
        return {
            "md5": hashlib.md5(encoded).hexdigest(),
            "sha1": hashlib.sha1(encoded).hexdigest(),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "sha512": hashlib.sha512(encoded).hexdigest(),
            "warning": "⚠️ تنبيه أمني: خوارزميات MD5 و SHA-1 تعتبر ضعيفة ومخترقة تصادمياً ولا تصلح إطلاقاً لتشفير وتخزين كلمات المرور أو التوقيعات الحساسة. استخدم SHA-256 أو خوارزميات التمليح والتهشير الحديثة (مثل Argon2 أو PBKDF2 أو Bcrypt)."
        }


class TextUtils:
    @staticmethod
    def to_uppercase(text: str) -> str:
        return text.upper()

    @staticmethod
    def to_lowercase(text: str) -> str:
        return text.lower()

    @staticmethod
    def to_words(text: str) -> list[str]:
        """Splits camelCase, PascalCase, snake_case, kebab-case, or spaces into tokens."""
        # Replace non-alphanumeric with spaces
        s = re.sub(r"[-_]+", " ", text)
        # Split camelCase and PascalCase
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
        s = re.sub(r"([A-Z]+)([A-Z][a-z0-9])", r"\1 \2", s)
        return [w.strip() for w in s.split() if w.strip()]

    @staticmethod
    def to_camel_case(text: str) -> str:
        words = TextUtils.to_words(text)
        if not words:
            return ""
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])

    @staticmethod
    def to_pascal_case(text: str) -> str:
        words = TextUtils.to_words(text)
        return "".join(w.capitalize() for w in words)

    @staticmethod
    def to_snake_case(text: str) -> str:
        words = TextUtils.to_words(text)
        return "_".join(w.lower() for w in words)

    @staticmethod
    def to_kebab_case(text: str) -> str:
        words = TextUtils.to_words(text)
        return "-".join(w.lower() for w in words)

    @staticmethod
    def remove_duplicate_lines(text: str) -> str:
        lines = text.splitlines()
        seen = set()
        unique = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        return "\n".join(unique)

    @staticmethod
    def sort_lines(text: str, reverse: bool = False, case_sensitive: bool = False) -> str:
        lines = text.splitlines()
        if case_sensitive:
            lines.sort(reverse=reverse)
        else:
            lines.sort(key=lambda s: s.lower(), reverse=reverse)
        return "\n".join(lines)

    @staticmethod
    def trim_whitespace(text: str) -> str:
        """Trims leading/trailing whitespace per line and overall."""
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    @staticmethod
    def count_metrics(text: str) -> dict[str, int]:
        """Counts characters (with and without whitespace), words, and lines."""
        chars_total = len(text)
        chars_no_spaces = len(re.sub(r"\s+", "", text))
        lines_count = len(text.splitlines()) if text else 0
        words_count = len(text.split()) if text else 0
        return {
            "characters": chars_total,
            "characters_no_spaces": chars_no_spaces,
            "words": words_count,
            "lines": lines_count
        }
