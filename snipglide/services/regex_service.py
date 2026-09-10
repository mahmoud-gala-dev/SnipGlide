import json
import os
import re
import subprocess
import sys
from typing import Optional, Any

_DANGEROUS_NESTED_QUANTIFIER = re.compile(r"\([^)]*([*+]\??|\{\d+,?\d*\}\??)\)[*+]")


class RegexService:
    @staticmethod
    def is_catastrophic_pattern(pattern_str: str) -> bool:
        """Detects high-risk nested quantifiers known to cause exponential backtracking (ReDoS)."""
        if not pattern_str:
            return False
        return bool(_DANGEROUS_NESTED_QUANTIFIER.search(pattern_str))

    @staticmethod
    def parse_flags(flags_str: str) -> int:
        """Converts flags string (e.g. 'imsx') to Python re flags bitmask."""
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

    @staticmethod
    def flags_to_string(flags: int) -> str:
        """Converts bitmask back to standard short flag letters (i, m, s, x)."""
        chars = []
        if flags & re.IGNORECASE:
            chars.append("i")
        if flags & re.MULTILINE:
            chars.append("m")
        if flags & re.DOTALL:
            chars.append("s")
        if flags & re.VERBOSE:
            chars.append("x")
        return "".join(chars)

    @staticmethod
    def validate_pattern(pattern_str: str, flags_str: str = "") -> tuple[bool, str, Optional[int]]:
        """
        Validates regex pattern syntax.
        Returns: (is_valid, message, error_pos)
        """
        if not pattern_str:
            return False, "نمط الـ Regex فارغ.", None
        try:
            flags = RegexService.parse_flags(flags_str)
            re.compile(pattern_str, flags)
            return True, "✓ نمط Regex سليم وصالح.", None
        except re.error as e:
            pos = getattr(e, "pos", None)
            pos_info = f" (موضع الخطأ: {pos})" if pos is not None else ""
            return False, f"❌ خطأ في بناء Regex: {e.msg}{pos_info}", pos
        except Exception as e:
            return False, f"❌ خطأ غير متوقع: {str(e)}", None

    @staticmethod
    def validate(pattern_str: str, flags_str: str = "") -> tuple[bool, str, Optional[int]]:
        """Alias for validate_pattern."""
        return RegexService.validate_pattern(pattern_str, flags_str)

    @staticmethod
    def _execute_isolated(req_dict: dict[str, Any], timeout: float = 2.0) -> tuple[bool, dict[str, Any], str]:
        """
        Executes regex in an isolated child process with strict OS-level timeout enforcement.
        Kills process immediately if timeout expires to guarantee ReDoS immunity.
        """
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--regex-worker"]
        else:
            cmd = [sys.executable, "-m", "snipglide.services.regex_worker"]

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
            )
            req_payload = json.dumps(req_dict, ensure_ascii=False)
            stdout, _ = proc.communicate(input=req_payload, timeout=timeout)
            if proc.returncode == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    return True, data, ""
                except Exception:
                    pass
            return False, {}, "Worker process failed"
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=0.5)
            except Exception:
                pass
            return False, {}, "Regex execution timed out. The pattern may cause excessive backtracking."
        except Exception:
            # SECURITY: No unsafe fallback. A catastrophic regex in an unkillable thread
            # cannot be safely stopped. Return a clear error instead.
            return False, {}, (
                "Regex execution failed: isolated process could not be started. "
                "Please try a simpler pattern."
            )

    @staticmethod
    def find_matches(
        pattern_str: str,
        text: str,
        flags_str: str = "",
        max_matches: int = 200,
        timeout: float = 2.0
    ) -> tuple[bool, list[dict[str, Any]], str]:
        """
        Finds all matches and captures groups safely with ReDoS protection and real timeout enforcement.
        Returns: (success, list_of_match_dicts, summary_or_error)
        """
        if not pattern_str:
            return True, [], "أدخل نمط Regex للبدء في المطابقة."
        if not text:
            return True, [], "نص الاختبار فارغ (0 مطابقة)."

        req = {
            "action": "find",
            "pattern": pattern_str,
            "text": text,
            "flags": flags_str,
            "max_matches": max_matches,
        }

        ok, data, err = RegexService._execute_isolated(req, timeout=timeout)
        if not ok:
            return False, [], err

        matches = data.get("matches", [])
        # Convert integer group keys back from JSON string keys
        for m in matches:
            if "groups" in m and isinstance(m["groups"], dict):
                m["groups"] = {int(k): v for k, v in m["groups"].items() if k.isdigit()}

        return data.get("success", True), matches, data.get("summary", data.get("error", ""))

    @staticmethod
    def replace(
        pattern_str: str,
        text: str,
        replacement_str: str,
        flags_str: str = "",
        replace_all: bool = True,
        timeout: float = 2.0
    ) -> tuple[bool, str]:
        """
        Replaces matched patterns with replacement text with ReDoS protection and real timeout enforcement.
        """
        if not pattern_str:
            return False, "نمط Regex فارغ."

        req = {
            "action": "replace",
            "pattern": pattern_str,
            "text": text,
            "replacement": replacement_str,
            "flags": flags_str,
            "replace_all": replace_all,
        }

        ok, data, err = RegexService._execute_isolated(req, timeout=timeout)
        if not ok:
            return False, err

        return data.get("success", False), data.get("result", data.get("error", ""))

