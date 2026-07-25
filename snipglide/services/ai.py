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
    if not api_key:
        clean = prompt.replace("Rewrite the following text to make it professional:", "").strip()
        clean = clean.replace("Correct grammar for:", "").strip()
        clean = clean.replace("Rewrite this in friendly tone:", "").strip()
        clean = clean.replace("Rewrite the text:", "").strip()
        return f"{clean} (Optimized by AI)"
        
    if provider != "gemini":
        return f"[AI response placeholder] {prompt}"

    model_list = get_available_models(api_key)
    if model_list:
        model_list = sort_models(model_list)
    else:
        model_list = [
            "models/gemini-3.6-flash",
            "models/gemini-3.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-2.0-flash-exp",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-latest",
            "models/gemini-1.5-pro",
            "models/gemini-pro",
        ]
        
    last_error = None
    for model_resource in model_list:
        model_name = model_resource if model_resource.startswith("models/") else f"models/{model_resource}"
        
        for api_version in ["v1", "v1beta"]:
            try:
                url = f"https://generativelanguage.googleapis.com/{api_version}/{model_name}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature
                    }
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10) as res:
                    response = _read_json_response(res)
                    return response["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                try:
                    err_content = _read_error_text(e)
                    err_json = json.loads(err_content)
                    msg = err_json.get("error", {}).get("message", str(e))
                    last_error = f"API Error ({e.code}) on {model_name} ({api_version}): {msg}"
                except Exception:
                    last_error = f"HTTP Error {e.code} on {model_name} ({api_version}): {e.reason}"
                logger.warning(f"Candidate {model_name} ({api_version}) failed: {last_error}")
                
                # If we hit quota limit (429), return the retry duration to user immediately instead of trying next models
                if e.code == 429:
                    return f"[AI Rate Limit (429): {msg}]"
                    
                if e.code == 404:
                    continue
                else:
                    return f"[AI Error: {last_error}]"
            except Exception as e:
                last_error = f"Connection failed on {model_name} ({api_version}): {e}"
                logger.warning(last_error)
                continue
                
    return f"[AI Error: All models failed. Last error: {last_error}]"

def test_ai_key(api_key: str, provider: str = "gemini") -> tuple[bool, str]:
    if not api_key:
        return False, "API key is empty."
    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as res:
                data = _read_json_response(res)
                models = data.get("models", [])
                if models:
                    return True, "API Key is valid! Connection established successfully."
                return False, "No models returned by Gemini API."
        else:
            return True, "Mock provider connection valid."
    except urllib.error.HTTPError as e:
        try:
            err_content = _read_error_text(e)
            err_json = json.loads(err_content)
            msg = err_json.get("error", {}).get("message", str(e))
            return False, f"API Error ({e.code}): {msg}"
        except Exception:
            return False, f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return False, f"Connection failed: {e}"
