"""AI Provider Abstraction Layer for SnipGlide.

Supports Gemini, OpenAI, OpenAI-Compatible APIs, and local Ollama instances
without introducing external HTTP dependencies.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

from snipglide.models.ai_models import AIProviderConfig, ProviderType
from snipglide.utils.logger import logger

_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5MB safety limit


class BaseAIProvider(ABC):
    """Base abstract class for all AI providers."""

    def __init__(self, config: AIProviderConfig):
        self.config = config

    def redact_secrets(self, text: str) -> str:
        """Sanitize any occurrence of the provider's API key from logs or messages."""
        if not text:
            return ""
        if self.config.api_key and len(self.config.api_key) >= 6:
            text = text.replace(self.config.api_key, "[REDACTED_API_KEY]")
        # Redact generic bearer token or Authorization patterns
        text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED_TOKEN]", text)
        return text

    def _read_body(self, resp) -> str:
        data = resp.read(_MAX_RESPONSE_BYTES + 1)
        if len(data) > _MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeded maximum allowed size (5MB).")
        return data.decode("utf-8", errors="replace")

    def _map_http_error(self, e: urllib.error.HTTPError) -> str:
        """Map HTTP error status codes to user-friendly diagnostic messages."""
        raw = ""
        try:
            raw = self._read_body(e)
            data = json.loads(raw)
            if "error" in data:
                err_val = data["error"]
                if isinstance(err_val, dict):
                    msg = err_val.get("message", raw)
                else:
                    msg = str(err_val)
            else:
                msg = raw
        except Exception:
            msg = e.reason or str(e)

        msg = self.redact_secrets(str(msg))

        if e.code == 401:
            return f"Authentication Failed (401): Invalid API key or unauthorized. ({msg})"
        if e.code == 403:
            return f"Permission Denied (403): Your API key does not have access to this resource. ({msg})"
        if e.code == 404:
            return f"Model Not Found (404): The requested model or endpoint does not exist. ({msg})"
        if e.code == 429:
            return f"Rate Limit Exceeded (429): Quota exhausted or too many requests. ({msg})"
        return f"HTTP Error ({e.code}): {msg}"

    @abstractmethod
    def validate_config(self) -> Tuple[bool, str]:
        """Verify the configuration format before sending requests."""
        pass

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Test authentication and endpoint connectivity."""
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Fetch available models from the provider."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Execute a completion request synchronously."""
        pass

    def stream(self, prompt: str, callback: Callable[[str], None], system_prompt: str = "") -> str:
        """Stream completion tokens. Defaults to fallback non-streaming if unsupported."""
        result = self.generate(prompt, system_prompt=system_prompt)
        callback(result)
        return result


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI Provider implementation."""

    def validate_config(self) -> Tuple[bool, str]:
        if not self.config.api_key.strip():
            return False, "Gemini API key is required."
        return True, "Valid configuration."

    def list_models(self) -> List[str]:
        ok, msg = self.validate_config()
        if not ok:
            return []
        try:
            base_url = self.config.get_effective_base_url()
            url = f"{base_url}/v1/models?key={self.config.api_key}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(self._read_body(resp))
                models = []
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        name = m.get("name", "")
                        if name.startswith("models/"):
                            name = name[len("models/"):]
                        models.append(name)
                return models
        except Exception as e:
            logger.warning(self.redact_secrets(f"Failed to list Gemini models: {e}"))
            return [
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ]

    def test_connection(self) -> Tuple[bool, str]:
        ok, msg = self.validate_config()
        if not ok:
            return False, msg
        try:
            models = self.list_models()
            if models:
                return True, f"Connected successfully. Found {len(models)} model(s)."
            return True, "Connected successfully to Gemini API."
        except urllib.error.HTTPError as e:
            return False, self._map_http_error(e)
        except Exception as e:
            return False, self.redact_secrets(f"Connection failed: {e}")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        ok, msg = self.validate_config()
        if not ok:
            return f"[Config Error: {msg}]"

        model = self.config.model.strip() or "gemini-1.5-flash"
        if model.startswith("models/"):
            model = model[len("models/"):]

        base_url = self.config.get_effective_base_url()
        url = f"{base_url}/v1beta/models/{model}:generateContent?key={self.config.api_key}"

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow your instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(self._read_body(resp))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return "[Gemini returned empty response]"
        except urllib.error.HTTPError as e:
            return f"[AI Error: {self._map_http_error(e)}]"
        except Exception as e:
            return f"[AI Connection Error: {self.redact_secrets(str(e))}]"


class OpenAIProvider(BaseAIProvider):
    """OpenAI /v1/chat/completions Provider implementation."""

    def validate_config(self) -> Tuple[bool, str]:
        if not self.config.api_key.strip():
            return False, "OpenAI API key is required."
        return True, "Valid configuration."

    def list_models(self) -> List[str]:
        ok, msg = self.validate_config()
        if not ok:
            return ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        try:
            base_url = self.config.get_effective_base_url()
            url = f"{base_url}/models"
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(self._read_body(resp))
                models = [m.get("id") for m in data.get("data", []) if "gpt" in m.get("id", "").lower()]
                return sorted(models) or ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        except Exception as e:
            logger.warning(self.redact_secrets(f"Failed to query OpenAI models: {e}"))
            return ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]

    def test_connection(self) -> Tuple[bool, str]:
        ok, msg = self.validate_config()
        if not ok:
            return False, msg
        try:
            base_url = self.config.get_effective_base_url()
            url = f"{base_url}/models"
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                if resp.status == 200:
                    return True, "Connected successfully to OpenAI API."
            return False, "Unexpected response from OpenAI."
        except urllib.error.HTTPError as e:
            return False, self._map_http_error(e)
        except Exception as e:
            return False, self.redact_secrets(f"Connection failed: {e}")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        ok, msg = self.validate_config()
        if not ok:
            return f"[Config Error: {msg}]"

        model = self.config.model.strip() or "gpt-4o-mini"
        base_url = self.config.get_effective_base_url()
        url = f"{base_url}/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(self._read_body(resp))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
                return "[OpenAI returned empty response]"
        except urllib.error.HTTPError as e:
            return f"[AI Error: {self._map_http_error(e)}]"
        except Exception as e:
            return f"[AI Connection Error: {self.redact_secrets(str(e))}]"

    def stream(self, prompt: str, callback: Callable[[str], None], system_prompt: str = "") -> str:
        """Stream SSE response line-by-line from /v1/chat/completions."""
        ok, msg = self.validate_config()
        if not ok:
            err = f"[Config Error: {msg}]"
            callback(err)
            return err

        model = self.config.model.strip() or "gpt-4o-mini"
        base_url = self.config.get_effective_base_url()
        url = f"{base_url}/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        full_text = []
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                full_text.append(token)
                                callback(token)
                    except json.JSONDecodeError:
                        continue
            return "".join(full_text)
        except Exception:
            # Fallback to non-streaming if stream connection encounters issues
            fallback_res = self.generate(prompt, system_prompt=system_prompt)
            callback(fallback_res)
            return fallback_res


class OpenAICompatibleProvider(OpenAIProvider):
    """Generic OpenAI-compatible API provider (Custom Base URL, LM Studio, Groq, vLLM)."""

    def validate_config(self) -> Tuple[bool, str]:
        if not self.config.base_url.strip():
            return False, "Base URL is required for OpenAI-compatible endpoint."
        return True, "Valid configuration."

    def list_models(self) -> List[str]:
        try:
            base_url = self.config.get_effective_base_url()
            url = f"{base_url}/models"
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=min(6, self.config.timeout)) as resp:
                data = json.loads(self._read_body(resp))
                return [m.get("id") for m in data.get("data", [])]
        except Exception:
            return ["default-model"]


class LocalOllamaProvider(OpenAICompatibleProvider):
    """Local Ollama instance provider (defaults to http://localhost:11434/v1)."""

    def validate_config(self) -> Tuple[bool, str]:
        # Ollama local endpoint does not require an API key
        return True, "Valid Ollama configuration."

    def list_models(self) -> List[str]:
        try:
            base_url = self.config.get_effective_base_url()
            # Try /api/tags (standard Ollama endpoint) or /v1/models
            req = urllib.request.Request(f"{base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(self._read_body(resp))
                return [m.get("id") for m in data.get("data", [])]
        except Exception:
            return ["llama3", "codellama", "mistral", "qwen2.5-coder"]


def get_ai_provider(config: AIProviderConfig) -> BaseAIProvider:
    """Factory creating the appropriate AI provider instance."""
    p_type = config.provider_type
    if p_type == ProviderType.GEMINI or p_type == "gemini":
        return GeminiProvider(config)
    elif p_type == ProviderType.OPENAI or p_type == "openai":
        return OpenAIProvider(config)
    elif p_type == ProviderType.OLLAMA or p_type == "ollama":
        return LocalOllamaProvider(config)
    elif p_type == ProviderType.OPENAI_COMPATIBLE or p_type == "openai_compatible":
        return OpenAICompatibleProvider(config)
    # Default fallback
    return GeminiProvider(config)
