from datetime import datetime
import os
import re
import socket
import uuid
import random
import tkinter as tk

def get_clipboard_text() -> str:
    try:
        r = tk.Tk()
        r.withdraw()
        clip = r.clipboard_get()
        r.destroy()
        return str(clip)
    except Exception:
        return ""

def parse_variables(text: str, usage_count: int = 0) -> str:
    now = datetime.now()
    text = text.replace("{{date}}", now.strftime("%Y-%m-%d"))
    text = text.replace("{{time}}", now.strftime("%H:%M:%S"))
    text = text.replace("{{datetime}}", now.strftime("%Y-%m-%d %H:%M:%S"))
    
    try:
        username = os.getlogin()
    except Exception:
        username = os.getenv("USERNAME", "user")
        
    text = text.replace("{{username}}", username)
    text = text.replace("{{computer}}", socket.gethostname())
    text = text.replace("{{hostname}}", socket.gethostname())
    
    if "{{clipboard}}" in text:
        text = text.replace("{{clipboard}}", get_clipboard_text())
        
    text = text.replace("{{uuid}}", str(uuid.uuid4()))
    if "{{random}}" in text:
        text = text.replace("{{random}}", str(random.randint(1000, 9999)))
    text = text.replace("{{counter}}", str(usage_count))
    
    env_matches = re.findall(r"\{\{env:([a-zA-Z0-9_]+)\}\}", text)
    for var in env_matches:
        val = os.getenv(var, "")
        text = text.replace(f"{{{{env:{var}}}}}", val)
        
    if "{{active_window}}" in text:
        from snipglide.engine.window_tracker import get_active_window_info
        title, _ = get_active_window_info()
        text = text.replace("{{active_window}}", title)
        
    return text

def get_form_fields(text: str) -> list[str]:
    matches = re.findall(r"\{\{form:([^}]+)\}\}", text)
    return list(dict.fromkeys(matches))

def replace_form_fields(text: str, answers: dict[str, str]) -> str:
    for field_name, value in answers.items():
        text = text.replace(f"{{{{form:{field_name}}}}}", value)
    return text
