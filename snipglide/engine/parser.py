from datetime import datetime
import os
import re
import socket
import uuid
import random
from typing import Any
from snipglide.utils.helpers import get_clipboard_text

# Regex patterns for form variables
_INPUT_PATTERN = re.compile(r"\{\{input:([a-zA-Z0-9_]+)(?::([^}]+))?\}\}")
_CHOICE_PATTERN = re.compile(r"\{\{choice:([a-zA-Z0-9_]+):([^}]+)\}\}")
_LEGACY_FORM_PATTERN = re.compile(r"\{\{form:([a-zA-Z0-9_]+)\}\}")

def extract_form_fields(text: str) -> list[dict[str, Any]]:
    """
    Extracts all interactive form variables from snippet replacement text.
    Supports:
      - {{input:variable_name}} or {{input:variable_name:default_value}}
      - {{choice:variable_name:opt1,opt2,opt3,...}}
      - {{form:variable_name}} (legacy compatibility)
    Returns an ordered list of unique field definitions.
    """
    fields: list[dict[str, Any]] = []
    seen_names = set()
    raw_matches: list[tuple[int, dict[str, Any]]] = []

    # 1. Choices
    for m in _CHOICE_PATTERN.finditer(text):
        name = m.group(1).strip()
        raw_opts = m.group(2)
        opts = [o.strip() for o in raw_opts.split(",") if o.strip()]
        raw_matches.append((m.start(), {
            "type": "choice",
            "name": name,
            "label": name.replace("_", " ").title(),
            "default": opts[0] if opts else "",
            "options": opts,
        }))

    # 2. Inputs
    for m in _INPUT_PATTERN.finditer(text):
        name = m.group(1).strip()
        default_val = m.group(2) or ""
        raw_matches.append((m.start(), {
            "type": "input",
            "name": name,
            "label": name.replace("_", " ").title(),
            "default": default_val.strip(),
            "options": [],
        }))

    # 3. Legacy forms
    for m in _LEGACY_FORM_PATTERN.finditer(text):
        name = m.group(1).strip()
        raw_matches.append((m.start(), {
            "type": "input",
            "name": name,
            "label": name.replace("_", " ").title(),
            "default": "",
            "options": [],
        }))

    # Sort matches by appearance in text
    raw_matches.sort(key=lambda x: x[0])
    for _, item in raw_matches:
        if item["name"] not in seen_names:
            seen_names.add(item["name"])
            fields.append(item)

    return fields

def replace_form_variables(text: str, answers: dict[str, str]) -> str:
    """
    Replaces all form variables with their filled values.
    """
    if not answers:
        return text

    # Replace choice variables
    def _sub_choice(m):
        name = m.group(1).strip()
        return str(answers.get(name, m.group(2).split(",")[0].strip()))

    text = _CHOICE_PATTERN.sub(_sub_choice, text)

    # Replace input variables
    def _sub_input(m):
        name = m.group(1).strip()
        fallback = m.group(2) or ""
        return str(answers.get(name, fallback))

    text = _INPUT_PATTERN.sub(_sub_input, text)

    # Replace legacy form variables
    for k, v in answers.items():
        text = text.replace(f"{{{{form:{k}}}}}", str(v))

    return text

def _detect_active_filename(window_title: str) -> str:
    """
    Extracts filename from active window title (e.g. VS Code, Notepad, editors).
    """
    if not window_title:
        return ""
    # Pattern matching filename with extension in title: 'filename.ext - App' or 'filename.ext'
    m = re.search(r"(?:^|[\s\-\*\/\\\[\(])([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,10})\b", window_title)
    if m:
        return m.group(1)
    return ""

def _detect_active_project(window_title: str) -> str:
    """
    Extracts project name from active window title or current directory.
    """
    if window_title:
        parts = [p.strip() for p in window_title.split(" - ") if p.strip()]
        if len(parts) >= 3:
            # Often VS Code format: 'file.py - ProjectFolder - Visual Studio Code'
            return parts[1]
        elif len(parts) == 2 and not any(app in parts[1].lower() for app in ("notepad", "chrome", "edge")):
            return parts[0]

    # Fallback to current working directory name
    try:
        return os.path.basename(os.getcwd())
    except Exception:
        return ""

def parse_variables(text: str, usage_count: int = 0) -> str:
    """
    Resolves all dynamic placeholders:
      {{date}}, {{time}}, {{datetime}}
      {{clipboard}}, {{uuid}}, {{random}}, {{counter}}
      {{username}}, {{computer}}, {{hostname}}, {{env:VAR}}, {{active_window}}
      {{filename}}, {{project}}, {{selection}}
    """
    now = datetime.now()

    # Dates & Times
    text = text.replace("{{date}}", now.strftime("%Y-%m-%d")).replace("{date}", now.strftime("%Y-%m-%d"))
    text = text.replace("{{time}}", now.strftime("%H:%M:%S")).replace("{time}", now.strftime("%H:%M:%S"))
    text = text.replace("{{datetime}}", now.strftime("%Y-%m-%d %H:%M:%S")).replace("{datetime}", now.strftime("%Y-%m-%d %H:%M:%S"))

    # Custom format: {{date:%Y/%m/%d}} or {date:%Y/%m/%d}
    dt_matches = re.findall(r"\{{1,2}(date|time|datetime):([^}]+)\}{1,2}", text)
    for macro, fmt in dt_matches:
        try:
            formatted = now.strftime(fmt)
        except Exception:
            formatted = ""
        pattern = r"\{{1,2}" + re.escape(macro) + r":" + re.escape(fmt) + r"\}{1,2}"
        text = re.sub(pattern, formatted, text)

    # User & Host
    try:
        username = os.getlogin()
    except Exception:
        username = os.getenv("USERNAME", "user")

    text = text.replace("{{username}}", username).replace("{username}", username)
    text = text.replace("{{computer}}", socket.gethostname()).replace("{computer}", socket.gethostname())
    text = text.replace("{{hostname}}", socket.gethostname()).replace("{hostname}", socket.gethostname())

    # Clipboard & Selection
    clip_text = None
    if re.search(r"\{{1,2}(clipboard|selection)\}{1,2}", text, re.IGNORECASE):
        clip_text = get_clipboard_text() or ""
        text = re.sub(r"\{{1,2}clipboard\}{1,2}", lambda _: clip_text, text, flags=re.IGNORECASE)
        text = re.sub(r"\{{1,2}selection\}{1,2}", lambda _: clip_text, text, flags=re.IGNORECASE)

    # UUID
    text = text.replace("{{uuid}}", str(uuid.uuid4())).replace("{uuid}", str(uuid.uuid4()))

    # Random & Counter
    if "{{random}}" in text or "{random}" in text:
        rnd = str(random.randint(1000, 9999))
        text = text.replace("{{random}}", rnd).replace("{random}", rnd)
    text = text.replace("{{counter}}", str(usage_count)).replace("{counter}", str(usage_count))

    # Environment variables
    env_matches = re.findall(r"\{{1,2}env:([a-zA-Z0-9_]+)\}{1,2}", text)
    for var in env_matches:
        val = os.getenv(var, "")
        pattern = r"\{{1,2}env:" + re.escape(var) + r"\}{1,2}"
        text = re.sub(pattern, val, text)

    # Window info, Filename & Project
    if any(k in text for k in ("{{active_window}}", "{active_window}", "{{filename}}", "{filename}", "{{project}}", "{project}")):
        try:
            from snipglide.engine.window_tracker import get_active_window_info
            title, _ = get_active_window_info()
        except Exception:
            title = ""

        text = text.replace("{{active_window}}", title).replace("{active_window}", title)

        fname = _detect_active_filename(title)
        text = text.replace("{{filename}}", fname).replace("{filename}", fname)

        proj = _detect_active_project(title)
        text = text.replace("{{project}}", proj).replace("{project}", proj)

    return text

# Backward compatibility aliases
def get_form_fields(text: str) -> list[str]:
    """Legacy helper returning string field names."""
    fields = extract_form_fields(text)
    return [f["name"] for f in fields]

def replace_form_fields(text: str, answers: dict[str, str]) -> str:
    """Legacy helper routing to replace_form_variables."""
    return replace_form_variables(text, answers)
