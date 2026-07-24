import urllib.request
import json
from snipglide.utils.logger import logger

def call_ai_completion(prompt: str, api_key: str, provider: str = "gemini") -> str:
    if not api_key:
        # Return offline mockup formatting if no key is configured
        clean = prompt.replace("Rewrite the following text to make it professional:", "").strip()
        clean = clean.replace("Correct grammar for:", "").strip()
        clean = clean.replace("Rewrite this in friendly tone:", "").strip()
        clean = clean.replace("Rewrite the text:", "").strip()
        return f"{clean} (Optimized by AI)"
        
    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as res:
                response = json.loads(res.read().decode("utf-8"))
                return response["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            return f"[AI response placeholder] {prompt}"
    except Exception as e:
        logger.error(f"AI API request failed: {e}")
        return f"[AI Error: {e}]"
