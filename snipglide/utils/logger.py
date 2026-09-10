"""Secure logging system with automatic secret redaction for SnipGlide."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from snipglide.core.config import DATA_DIR

# Sensitive patterns to scrub from all logs
_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(?i)(basic\s+)[A-Za-z0-9+/=]{8,}"), r"\1[REDACTED_BASIC_AUTH]"),
    (re.compile(r"(?i)(?:api[-_]?key|apikey|password|passwd|secret|auth[-_]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{6,}['\"]?"), r"[REDACTED_SECRET]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"AIzaSy[A-Za-z0-9_\-]{33}"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
]


class RedactingFilter(logging.Filter):
    """Filter that intercepts and masks sensitive secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize(v) if isinstance(v, str) else v for v in record.args)
        return True

    @staticmethod
    def _sanitize(text: str) -> str:
        for pattern, replacement in _SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_logger():
    log_file = DATA_DIR / "snipglide.log"
    logger = logging.getLogger("SnipGlide")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        redacting_filter = RedactingFilter()
        file_handler.addFilter(redacting_filter)
        stream_handler.addFilter(redacting_filter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


logger = setup_logger()


def redact_sensitive_text(text: str) -> str:
    """Centralized utility to scrub secrets, tokens, keys, and credentials from text."""
    if not text:
        return ""
    return RedactingFilter._sanitize(text)
