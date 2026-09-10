"""Unit tests for AI Provider Abstraction and Coding Platform."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from snipglide.models.ai_models import (
    AIProviderConfig,
    CODING_ACTIONS,
    CodingActionType,
    ProviderType,
)
from snipglide.services.ai_providers import (
    GeminiProvider,
    LocalOllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    get_ai_provider,
)


class TestAIPlatform(unittest.TestCase):
    """Test suite for AI Provider abstraction, coding actions, and secret safety."""

    def test_provider_factory(self):
        cfg_gemini = AIProviderConfig(provider_type=ProviderType.GEMINI, api_key="test-key")
        self.assertIsInstance(get_ai_provider(cfg_gemini), GeminiProvider)

        cfg_openai = AIProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk-test")
        self.assertIsInstance(get_ai_provider(cfg_openai), OpenAIProvider)

        cfg_ollama = AIProviderConfig(provider_type=ProviderType.OLLAMA)
        self.assertIsInstance(get_ai_provider(cfg_ollama), LocalOllamaProvider)

        cfg_compat = AIProviderConfig(provider_type=ProviderType.OPENAI_COMPATIBLE, base_url="http://mock:8000/v1")
        self.assertIsInstance(get_ai_provider(cfg_compat), OpenAICompatibleProvider)

    def test_config_validation(self):
        # Gemini requires key
        p1 = GeminiProvider(AIProviderConfig(api_key=""))
        ok, msg = p1.validate_config()
        self.assertFalse(ok)
        self.assertIn("key is required", msg)

        p1_ok = GeminiProvider(AIProviderConfig(api_key="AIzaSyTest123"))
        self.assertTrue(p1_ok.validate_config()[0])

        # OpenAI requires key
        p2 = OpenAIProvider(AIProviderConfig(api_key=""))
        self.assertFalse(p2.validate_config()[0])

        # Ollama local doesn't require key
        p3 = LocalOllamaProvider(AIProviderConfig())
        self.assertTrue(p3.validate_config()[0])

        # OpenAI Compatible requires base_url
        p4 = OpenAICompatibleProvider(AIProviderConfig(base_url=""))
        self.assertFalse(p4.validate_config()[0])

    def test_secret_redaction(self):
        secret = "secret-sk-abcdef1234567890"
        cfg = AIProviderConfig(api_key=secret)
        provider = OpenAIProvider(cfg)

        leaked_msg = f"Failed to connect using key {secret} and Bearer abcdef1234567890"
        sanitized = provider.redact_secrets(leaked_msg)

        self.assertNotIn(secret, sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)

    def test_http_error_mapping(self):
        provider = OpenAIProvider(AIProviderConfig(api_key="test-key"))

        # 401
        err_401 = urllib.error.HTTPError(
            url="https://api.openai.com",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
        )
        msg_401 = provider._map_http_error(err_401)
        self.assertIn("Authentication Failed (401)", msg_401)

        # 429
        err_429 = urllib.error.HTTPError(
            url="https://api.openai.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "You exceeded your current quota"}}'),
        )
        msg_429 = provider._map_http_error(err_429)
        self.assertIn("Rate Limit Exceeded (429)", msg_429)

    @patch("urllib.request.urlopen")
    def test_openai_generate_mock(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "def add(a, b): return a + b"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        cfg = AIProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk-test-123456789")
        provider = OpenAIProvider(cfg)
        result = provider.generate("Write an add function in Python")

        self.assertEqual(result, "def add(a, b): return a + b")

    @patch("urllib.request.urlopen")
    def test_openai_stream_mock(self, mock_urlopen):
        # Mock SSE stream lines
        sse_lines = [
            b'data: {"choices": [{"delta": {"content": "def"}}]}\n',
            b'data: {"choices": [{"delta": {"content": " foo"}}]}\n',
            b'data: {"choices": [{"delta": {"content": "(): pass"}}]}\n',
            b'data: [DONE]\n',
        ]
        mock_resp = MagicMock()
        mock_resp.__iter__.return_value = iter(sse_lines)
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        cfg = AIProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk-test-123456789")
        provider = OpenAIProvider(cfg)

        chunks = []
        full = provider.stream("Define foo", lambda c: chunks.append(c))

        self.assertEqual("".join(chunks), "def foo(): pass")
        self.assertEqual(full, "def foo(): pass")

    def test_coding_actions_templates(self):
        # Test that all required coding actions exist and format properly
        expected_actions = [
            CodingActionType.EXPLAIN_CODE,
            CodingActionType.FIND_BUGS,
            CodingActionType.REFACTOR,
            CodingActionType.OPTIMIZE,
            CodingActionType.GENERATE_TESTS,
            CodingActionType.GENERATE_DOCSTRINGS,
            CodingActionType.ADD_TYPE_HINTS,
            CodingActionType.EXPLAIN_ERROR,
            CodingActionType.GENERATE_REGEX,
            CodingActionType.EXPLAIN_REGEX,
            CodingActionType.GENERATE_SQL,
            CodingActionType.EXPLAIN_SQL,
            CodingActionType.CONVERT_CODE,
        ]

        sample_code = "print('Hello World')"
        for act in expected_actions:
            self.assertIn(act, CODING_ACTIONS)
            meta = CODING_ACTIONS[act]
            self.assertTrue(len(meta.label) > 0)
            self.assertTrue(len(meta.system_prompt) > 0)
            formatted = meta.user_prompt_template.format(
                code=sample_code,
                source_lang="Python",
                target_lang="JavaScript",
            )
            self.assertIn(sample_code, formatted)


if __name__ == "__main__":
    unittest.main()
