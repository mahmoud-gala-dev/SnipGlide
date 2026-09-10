import urllib.request
import urllib.error
import json
import hashlib
import time
from snipglide.utils.logger import logger

_MODEL_CACHE_TTL = 3600
_MAX_HTTP_RESPONSE_BYTES = 2 * 1024 * 1024
_model_cache: dict[str, tuple[float, list[str]]] = {}

def _read_json_response(response):
    data = response.read(_MAX_HTTP_RESPONSE_BYTES + 1)
    if len(data) > _MAX_HTTP_RESPONSE_BYTES:
        raise ValueError("AI response is too large.")
    return json.loads(data.decode("utf-8"))

def _read_error_text(error):
    data = error.read(_MAX_HTTP_RESPONSE_BYTES + 1)
    if len(data) > _MAX_HTTP_RESPONSE_BYTES:
        return "AI error response is too large."
    return data.decode("utf-8", errors="replace")

def get_available_models(api_key: str) -> list[str]:
    cache_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cached = _model_cache.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < _MODEL_CACHE_TTL:
        return cached[1]

    try:
        url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=6) as res:
            data = _read_json_response(res)
            models = []
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    models.append(m["name"])
            _model_cache[cache_key] = (now, models)
            return models
    except Exception as e:
        logger.error(f"Failed to query models dynamically: {e}")
        return []

def sort_models(model_names: list[str]) -> list[str]:
    def get_priority(name: str) -> int:
        name_lower = name.lower()
        if "3.6-flash" in name_lower:
            return 120
        if "3.5-flash" in name_lower:
            return 110
        if "2.0-flash" in name_lower or "2.0-flash-exp" in name_lower:
            return 100
        if "1.5-flash" in name_lower:
            return 90
        if "1.5-pro" in name_lower:
            return 80
        if "2.0-pro" in name_lower:
            return 75
        if "gemini-pro" in name_lower:
            return 50
        return 0
    return sorted(model_names, key=get_priority, reverse=True)

def call_ai_completion(prompt: str, api_key: str, provider: str = "gemini", temperature: float = 0.7) -> str:
    if not api_key and provider not in ("ollama", "local"):
        clean = prompt.replace("Rewrite the following text to make it professional:", "").strip()
        clean = clean.replace("Correct grammar for:", "").strip()
        clean = clean.replace("Rewrite this in friendly tone:", "").strip()
        clean = clean.replace("Rewrite the text:", "").strip()
        return f"{clean} (Optimized by AI)"
        
    try:
        from snipglide.models.ai_models import AIProviderConfig, ProviderType
        from snipglide.services.ai_providers import get_ai_provider

        p_type = ProviderType.GEMINI
        if provider == "openai":
            p_type = ProviderType.OPENAI
        elif provider in ("ollama", "local"):
            p_type = ProviderType.OLLAMA
        elif provider == "openai_compatible":
            p_type = ProviderType.OPENAI_COMPATIBLE

        config = AIProviderConfig(
            provider_type=p_type,
            api_key=api_key,
            temperature=temperature,
        )
        ai_prov = get_ai_provider(config)
        return ai_prov.generate(prompt)
    except Exception as e:
        logger.error(f"Error in call_ai_completion: {e}")
        return f"[AI Error: {e}]"

def test_ai_key(api_key: str, provider: str = "gemini") -> tuple[bool, str]:
    if not api_key and provider not in ("ollama", "local"):
        return False, "API key is empty."
    try:
        from snipglide.models.ai_models import AIProviderConfig, ProviderType
        from snipglide.services.ai_providers import get_ai_provider

        p_type = ProviderType.GEMINI
        if provider == "openai":
            p_type = ProviderType.OPENAI
        elif provider in ("ollama", "local"):
            p_type = ProviderType.OLLAMA
        elif provider == "openai_compatible":
            p_type = ProviderType.OPENAI_COMPATIBLE

        config = AIProviderConfig(provider_type=p_type, api_key=api_key)
        ai_prov = get_ai_provider(config)
        return ai_prov.test_connection()
    except Exception as e:
        return False, f"Connection failed: {e}"

