import base64
import hmac
import hashlib
import os
from cryptography.fernet import Fernet
from snipglide.utils.logger import logger

PBKDF2_ITERATIONS = 310_000

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )

def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False

    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
            expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)

def get_key_from_password(password: str, salt: bytes = b"snipglide_static_kdf_salt_v2") -> bytes:
    """Derive a Fernet-compatible 32-byte key from password using PBKDF2-HMAC-SHA256."""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return base64.urlsafe_b64encode(digest)

def encrypt_text(text: str, password: str) -> str:
    try:
        key = get_key_from_password(password)
        f = Fernet(key)
        return f.encrypt(text.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError("Encryption failed")

def decrypt_text(encrypted: str, password: str) -> str:
    try:
        key = get_key_from_password(password)
        f = Fernet(key)
        return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception:
        # Backwards compatibility fallback for older legacy SHA256-derived keys
        try:
            legacy_digest = hashlib.sha256(password.encode("utf-8")).digest()
            legacy_key = base64.urlsafe_b64encode(legacy_digest)
            f_legacy = Fernet(legacy_key)
            return f_legacy.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed")

ENC_PREFIX = "enc:v1:"
_MACHINE_SALT = b"snipglide_local_sec_salt_v1"

def _get_machine_identifier() -> str:
    parts = [
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        os.path.expanduser("~"),
        "SnipGlideLocalAppSecretKeyV1",
    ]
    return "::".join(p for p in parts if p)

def get_secret_encryption_key() -> bytes:
    """Derives a reproducible local machine/user-bound Fernet key."""
    ident = _get_machine_identifier()
    digest = hashlib.pbkdf2_hmac("sha256", ident.encode("utf-8"), _MACHINE_SALT, 100_000)
    return base64.urlsafe_b64encode(digest)

def encrypt_secret(plaintext: str) -> str:
    """
    Encrypts a sensitive string (API key, token, password) with a machine-bound Fernet key.
    Returns string prefixed with 'enc:v1:' or empty string if input was empty.
    Fails closed: raises ValueError on any encryption error, never falling back to plaintext.
    """
    if not plaintext:
        return ""
    if plaintext.startswith(ENC_PREFIX):
        return plaintext
    try:
        key = get_secret_encryption_key()
        f = Fernet(key)
        cipher_bytes = f.encrypt(plaintext.encode("utf-8"))
        return f"{ENC_PREFIX}{cipher_bytes.decode('ascii')}"
    except Exception as e:
        logger.error(f"Failed to encrypt secret: {type(e).__name__}")
        raise ValueError(f"Secret encryption failed: {e}")

def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypts an 'enc:v1:' prefixed string using the local machine key.
    If not encrypted (legacy plaintext), returns the input as-is for backward compatibility.
    Never leaks the secret or ciphertext to logs on failure.
    """
    if not ciphertext:
        return ""
    if not ciphertext.startswith(ENC_PREFIX):
        return ciphertext
    try:
        raw_cipher = ciphertext[len(ENC_PREFIX):]
        key = get_secret_encryption_key()
        f = Fernet(key)
        plain_bytes = f.decrypt(raw_cipher.encode("ascii"))
        return plain_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to decrypt secret: {type(e).__name__}")
        return ""

def mask_secret(secret: str) -> str:
    """
    Returns a masked representation of a secret (e.g. sk-••••••••abcd).
    """
    if not secret:
        return ""
    s = secret.strip()
    if len(s) <= 8:
        return "•" * 8
    prefix = s[:3]
    suffix = s[-4:]
    return f"{prefix}••••••••{suffix}"

# Centralized sensitive key definitions (case-insensitive)
SENSITIVE_KEYS: set[str] = {
    "api_key", "apikey", "api-key", "key",
    "token", "access_token", "refresh_token", "id_token", "x-token", "x-auth-token",
    "secret", "client_secret", "client-secret", "app_secret",
    "password", "passwd", "pwd", "pin",
    "authorization", "proxy-authorization", "auth",
    "bearer", "credential", "credentials", "private_key"
}

SENSITIVE_QUERY_KEYS: set[str] = {
    "api_key", "apikey", "api-key", "key",
    "token", "access_token", "refresh_token", "id_token",
    "secret", "client_secret", "password", "passwd", "pwd",
    "auth", "authorization", "bearer"
}

SENSITIVE_HEADER_KEYS: set[str] = {
    "authorization", "proxy-authorization",
    "x-api-key", "api-key", "apikey",
    "x-auth-token", "token", "secret", "x-token",
    "x-access-token", "cookie", "set-cookie"
}

def is_sensitive_key(key: str) -> bool:
    """Checks if a parameter or key name matches known sensitive key patterns."""
    if not key:
        return False
    k = key.strip().lower()
    return k in SENSITIVE_KEYS or any(s in k for s in ("password", "passwd", "secret", "api_key", "token"))

def is_sensitive_header(header: str) -> bool:
    """Checks if an HTTP header name matches known sensitive header patterns."""
    if not header:
        return False
    h = header.strip().lower()
    return h in SENSITIVE_HEADER_KEYS or any(s in h for s in ("auth", "token", "secret", "api-key", "apikey"))

def sanitize_url_query(url: str, redact_text: str = "[REDACTED]") -> str:
    """
    Removes or redacts sensitive keys from URL query parameters (e.g. api_key, token, secret).
    Preserves full URL structure including scheme, host, path, other query parameters, and fragments.
    """
    if not url or "?" not in url:
        return url
    try:
        import urllib.parse
        parsed = urllib.parse.urlsplit(url)
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        cleaned = []
        for k, v in params:
            if k.lower() in SENSITIVE_QUERY_KEYS:
                cleaned.append((k, redact_text))
            else:
                cleaned.append((k, v))
        new_query = urllib.parse.urlencode(cleaned)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))
    except Exception:
        return url

def sanitize_headers_dict(headers: dict[str, str], redact_text: str = "[REDACTED]") -> dict[str, str]:
    """
    Returns a copy of headers dict with sensitive authentication values redacted.
    """
    out = {}
    for k, v in (headers or {}).items():
        if is_sensitive_header(k):
            out[k] = redact_text
        else:
            out[k] = v
    return out

def sanitize_log_text(text: str) -> str:
    """
    Sanitizes log messages or exception text to prevent leaking API keys, Bearer tokens, or passwords.
    """
    if not text:
        return ""
    import re
    # Redact Bearer tokens
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED_TOKEN]", text)
    # Redact Basic auth hashes
    text = re.sub(r"(?i)(basic\s+)[A-Za-z0-9+/=]{10,}", r"\1[REDACTED_BASIC]", text)
    # Redact common key=value query patterns
    pattern = r"(?i)(api_key|apikey|api-key|key|token|access_token|refresh_token|secret|password)=([^&\s]+)"
    text = re.sub(pattern, r"\1=[REDACTED]", text)
    return text

