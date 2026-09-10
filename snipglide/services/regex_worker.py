"""Isolated worker process for executing regex operations safely.

Runs as a separate OS process to guarantee that catastrophic backtracking (ReDoS)
can be terminated via OS process kill without holding the Python GIL or freezing Qt UI.
"""
import json
import re
import sys
from typing import Any

# Ensure UTF-8 I/O on Windows console / subprocess streams
if hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _parse_flags(flags_str: str) -> int:
    flags = 0
    f_lower = (flags_str or "").lower()
    if "i" in f_lower or "ignorecase" in f_lower:
        flags |= re.IGNORECASE
    if "m" in f_lower or "multiline" in f_lower:
        flags |= re.MULTILINE
    if "s" in f_lower or "dotall" in f_lower:
        flags |= re.DOTALL
    if "x" in f_lower or "verbose" in f_lower:
        flags |= re.VERBOSE
    return flags


def _handle_find(req: dict[str, Any]) -> dict[str, Any]:
    pattern_str = req.get("pattern", "")
    text = req.get("text", "")
    flags_str = req.get("flags", "")
    max_matches = int(req.get("max_matches", 200))

    if not pattern_str:
        return {"success": True, "matches": [], "summary": "أدخل نمط Regex للبدء في المطابقة."}
    if not text:
        return {"success": True, "matches": [], "summary": "نص الاختبار فارغ (0 مطابقة)."}

    flags = _parse_flags(flags_str)
    try:
        compiled = re.compile(pattern_str, flags)
    except re.error as e:
        pos = getattr(e, "pos", None)
        pos_info = f" عند الموضع {pos}" if pos is not None else ""
        return {"success": False, "matches": [], "summary": f"خطأ في الـ Regex: {e.msg}{pos_info}"}

    matches = []
    count = 0
    target_text = text[:100_000] if len(text) > 100_000 else text
    truncated = len(text) > 100_000

    for match in compiled.finditer(target_text):
        count += 1
        named_groups = match.groupdict()
        all_groups = {str(i): match.group(i) for i in range(1, len(match.groups()) + 1)}
        matches.append({
            "index": count,
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "groups": all_groups,
            "named_groups": named_groups,
        })
        if count >= max_matches:
            break

    summary = f"تم العثور على {count} مطابقة" + (f" (تم الوصول للحد الأقصى المعروض: {max_matches})" if count >= max_matches else ".")
    if truncated:
        summary += " [تم فحص أول 100 ألف حرف فقط لحماية الأداء]"

    return {"success": True, "matches": matches, "summary": summary}


def _handle_replace(req: dict[str, Any]) -> dict[str, Any]:
    pattern_str = req.get("pattern", "")
    text = req.get("text", "")
    replacement_str = req.get("replacement", "")
    flags_str = req.get("flags", "")
    replace_all = bool(req.get("replace_all", True))

    if not pattern_str:
        return {"success": False, "result": "نمط Regex فارغ."}

    flags = _parse_flags(flags_str)
    try:
        compiled = re.compile(pattern_str, flags)
        count = 0 if replace_all else 1
        result = compiled.sub(replacement_str, text, count=count)
        return {"success": True, "result": result}
    except re.error as e:
        return {"success": False, "result": f"خطأ في صيغة الـ Regex أو الاستبدال: {e.msg}"}


def main():
    raw_input = sys.stdin.read()
    if not raw_input.strip():
        return
    try:
        req = json.loads(raw_input)
        action = req.get("action", "find")
        if action == "replace":
            res = _handle_replace(req)
        else:
            res = _handle_find(req)
        sys.stdout.write(json.dumps(res, ensure_ascii=False))
        sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
