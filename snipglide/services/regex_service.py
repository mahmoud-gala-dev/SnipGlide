import re
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
        f_lower = flags_str.lower()
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
    def find_matches(
        pattern_str: str,
        text: str,
        flags_str: str = "",
        max_matches: int = 200,
        timeout: float = 2.0
    ) -> tuple[bool, list[dict[str, Any]], str]:
        """
        Finds all matches and captures groups safely with ReDoS protection.
        Returns: (success, list_of_match_dicts, summary_or_error)
        """
        if not pattern_str:
            return True, [], "أدخل نمط Regex للبدء في المطابقة."
        if not text:
            return True, [], "نص الاختبار فارغ (0 مطابقة)."

        if RegexService.is_catastrophic_pattern(pattern_str) and len(text) > 20:
            return False, [], "⚠️ نمط Regex عالي الخطورة لتضمنه تكراراً كمياً متداخلاً (Catastrophic Backtracking / ReDoS). يرجى تبسيط النمط."

        try:
            flags = RegexService.parse_flags(flags_str)
            compiled = re.compile(pattern_str, flags)
        except re.error as e:
            pos = getattr(e, "pos", None)
            pos_info = f" عند الموضع {pos}" if pos is not None else ""
            return False, [], f"خطأ في الـ Regex: {e.msg}{pos_info}"
        except Exception as e:
            return False, [], f"فشل تجميع Regex: {str(e)}"

        matches: list[dict[str, Any]] = []
        count = 0
        try:
            for match in compiled.finditer(text):
                count += 1
                named_groups = match.groupdict()
                all_groups = {i: match.group(i) for i in range(1, len(match.groups()) + 1)}

                match_info = {
                    "index": count,
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": all_groups,
                    "named_groups": named_groups,
                }
                matches.append(match_info)
                if count >= max_matches:
                    break

            summary = f"تم العثور على {count} مطابقة" + (f" (تم الوصول للحد الأقصى المعروض: {max_matches})" if count >= max_matches else ".")
            return True, matches, summary
        except Exception as e:
            return False, [], f"خطأ أثناء فحص المطابقات: {str(e)}"

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
        Replaces matched patterns with replacement text with ReDoS protection.
        Handles Python regex backreferences (\\1, \\g<name>) and invalid groups safely.
        """
        if not pattern_str:
            return False, "نمط Regex فارغ."

        if RegexService.is_catastrophic_pattern(pattern_str) and len(text) > 20:
            return False, "⚠️ نمط Regex عالي الخطورة لتضمنه تكراراً كمياً متداخلاً (Catastrophic Backtracking / ReDoS). يرجى تبسيط النمط."

        try:
            flags = RegexService.parse_flags(flags_str)
            compiled = re.compile(pattern_str, flags)
            count = 0 if replace_all else 1
            result = compiled.sub(replacement_str, text, count=count)
            return True, result
        except re.error as e:
            return False, f"خطأ في صيغة الـ Regex أو الاستبدال: {e.msg}"
        except Exception as e:
            return False, f"فشل الاستبدال: {str(e)}"
