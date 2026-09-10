import json
import re
import urllib.parse
import uuid
from typing import Optional

# Content Type Constants
TYPE_PLAIN_TEXT = "PLAIN_TEXT"
TYPE_URL = "URL"
TYPE_JSON = "JSON"
TYPE_XML = "XML"
TYPE_SQL = "SQL"
TYPE_CODE = "CODE"
TYPE_STACK_TRACE = "STACK_TRACE"
TYPE_UUID = "UUID"
TYPE_JWT = "JWT"
TYPE_EMAIL = "EMAIL"

ALL_TYPES = [
    TYPE_PLAIN_TEXT,
    TYPE_URL,
    TYPE_JSON,
    TYPE_XML,
    TYPE_SQL,
    TYPE_CODE,
    TYPE_STACK_TRACE,
    TYPE_UUID,
    TYPE_JWT,
    TYPE_EMAIL,
]

# Fast regex patterns
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_URL_REGEX = re.compile(r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

_SQL_KEYWORDS = re.compile(
    r"\b(SELECT\s+.+\s+FROM|INSERT\s+INTO\s+.+|UPDATE\s+.+\s+SET|DELETE\s+FROM\s+.+|CREATE\s+(TABLE|VIEW|INDEX)|ALTER\s+TABLE|DROP\s+TABLE|WITH\s+.+\s+AS\s*\()\b",
    re.IGNORECASE | re.DOTALL
)

_PYTHON_TRACEBACK = re.compile(r"(Traceback \(most recent call last\):|File \".+\", line \d+, in )", re.MULTILINE)
_NODE_STACK = re.compile(r"(\s+at\s+.+\s+\(.+:\d+:\d+\)|\s+at\s+.+:\d+:\d+|Error:\s+.+\n\s+at\s+)", re.MULTILINE)
_POWERSHELL_ERROR = re.compile(r"(CategoryInfo\s*:|FullyQualifiedErrorId\s*:|\+ CategoryInfo\s*:)", re.MULTILINE)
_GIT_ERROR = re.compile(r"^(fatal:|error: failed to push|CONFLICT \(content\):)", re.MULTILINE | re.IGNORECASE)

_CODE_PATTERNS = re.compile(
    r"(\b(def\s+[a-zA-Z_]\w*\s*\(|class\s+[a-zA-Z_]\w*[:\(]|function\s+[a-zA-Z_]\w*\s*\(|const\s+[a-zA-Z_]\w*\s*=|let\s+[a-zA-Z_]\w*\s*=|var\s+[a-zA-Z_]\w*\s*=|import\s+.+\s+from|from\s+.+\s+import|public\s+(class|static|void)|#include\s+[<\"].+[>\"]|package\s+[a-zA-Z_]|fn\s+[a-zA-Z_]\w*\s*\(|func\s+[a-zA-Z_]\w*\s*\()|\b(console\.log|print\(|return\s+.+;))",
    re.MULTILINE
)

_SENSITIVE_PATTERNS = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|-----BEGIN CERTIFICATE-----|(?i:(password|passwd|secret|api_key|apikey|bearer)\s*[:=]\s*['\"][^'\"]{8,}['\"]))"
)

class ClipboardContentDetector:
    @staticmethod
    def is_sensitive(text: str) -> bool:
        """Detects if clipboard text contains sensitive security secrets, tokens, or private keys."""
        if not text:
            return False
        return bool(_SENSITIVE_PATTERNS.search(text[:4096]))

    @staticmethod
    def detect_type(text: str) -> str:
        """
        Classifies clipboard content locally and rapidly using priority heuristics.
        Returns one of the canonical type strings.
        """
        if not text or not text.strip():
            return TYPE_PLAIN_TEXT

        stripped = text.strip()
        length = len(stripped)

        # ── Fast Path for Large Text (> 32KB) ──
        if length > 32768:
            # Check JSON start/end quickly
            if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
                try:
                    json.loads(stripped)
                    return TYPE_JSON
                except Exception:
                    pass
            if stripped.startswith("<?xml") or (stripped.startswith("<") and stripped.endswith(">")):
                return TYPE_XML
            if _PYTHON_TRACEBACK.search(stripped[:4096]) or _NODE_STACK.search(stripped[:4096]):
                return TYPE_STACK_TRACE
            return TYPE_CODE if _CODE_PATTERNS.search(stripped[:4096]) else TYPE_PLAIN_TEXT

        # ── 1. UUID (Strict 36 chars, 4 hyphens, standard hex format) ──
        if length == 36 and stripped.count("-") == 4 and " " not in stripped:
            try:
                val = uuid.UUID(stripped)
                if str(val).lower() == stripped.lower():
                    return TYPE_UUID
            except ValueError:
                pass

        # ── 2. JWT (Header.Payload.Signature) ──
        if stripped.count(".") == 2 and "\n" not in stripped and " " not in stripped and length > 20:
            parts = stripped.split(".")
            if len(parts) == 3 and len(parts[0]) > 4 and len(parts[1]) > 4:
                import base64
                try:
                    def _b64_pad(s):
                        return s + "=" * ((4 - len(s) % 4) % 4)
                    h_bytes = base64.urlsafe_b64decode(_b64_pad(parts[0]))
                    h_json = json.loads(h_bytes.decode("utf-8"))
                    p_bytes = base64.urlsafe_b64decode(_b64_pad(parts[1]))
                    p_json = json.loads(p_bytes.decode("utf-8"))
                    if isinstance(h_json, dict) and isinstance(p_json, dict):
                        return TYPE_JWT
                except Exception:
                    pass

        # ── 3. Email ──
        if "\n" not in stripped and " " not in stripped and "@" in stripped and "." in stripped:
            if _EMAIL_REGEX.match(stripped):
                return TYPE_EMAIL

        # ── 4. URL ──
        if "\n" not in stripped and " " not in stripped:
            if _URL_REGEX.match(stripped) or stripped.startswith("http://") or stripped.startswith("https://"):
                try:
                    parsed = urllib.parse.urlparse(stripped)
                    if parsed.scheme in ("http", "https", "ftp") and parsed.netloc:
                        return TYPE_URL
                except Exception:
                    pass
            elif stripped.startswith("www.") and "." in stripped[4:]:
                return TYPE_URL

        # ── 5. JSON ──
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (dict, list)):
                    return TYPE_JSON
            except Exception:
                pass

        # ── 6. XML / HTML ──
        if (stripped.startswith("<?xml") or stripped.startswith("<")) and stripped.endswith(">") and "</" in stripped:
            return TYPE_XML

        # ── 7. Stack Trace / Terminal Errors ──
        if _PYTHON_TRACEBACK.search(stripped) or _NODE_STACK.search(stripped) or _POWERSHELL_ERROR.search(stripped) or _GIT_ERROR.search(stripped):
            return TYPE_STACK_TRACE

        # ── 8. SQL Query ──
        if _SQL_KEYWORDS.search(stripped):
            # Avoid single sentence matching by checking semicolon or length/lines
            if ";" in stripped or "\n" in stripped or any(kw in stripped.upper() for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")):
                return TYPE_SQL

        # ── 9. Source Code ──
        if _CODE_PATTERNS.search(stripped):
            return TYPE_CODE

        # ── 10. Fallback: Plain Text ──
        return TYPE_PLAIN_TEXT
