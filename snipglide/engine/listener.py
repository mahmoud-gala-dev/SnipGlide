import threading
import time
import re
from typing import Optional, Callable
from pynput import keyboard
from snipglide.database.snippet_repo import get_all_snippets, increment_usage
from snipglide.database.autocorrect_repo import get_all_corrections
from snipglide.engine.parser import parse_variables, get_form_fields, replace_form_fields
from snipglide.engine.window_tracker import get_active_window_info, is_password_field_active
from snipglide.utils.logger import logger

class ExpansionEngine:
    def __init__(self, settings_provider: Callable[[], dict], form_prompt_callback: Callable[[object, list], Optional[dict]] = None):
        self.settings_provider = settings_provider
        self.form_prompt_callback = form_prompt_callback
        self.buffer = ""
        self.controller = keyboard.Controller()
        self.listener: Optional[keyboard.Listener] = None
        self.running = False
        self.suspended = False
        self._lock = threading.RLock()

    def start(self):
        if self.listener is not None:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.daemon = True
        self.listener.start()
        logger.info("Expansion engine started.")

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        logger.info("Expansion engine stopped.")

    def set_suspended(self, value: bool):
        self.suspended = value
        self.buffer = ""

    def _on_press(self, key):
        if not self.running or self.suspended:
            return
            
        settings = self.settings_provider()
        if not settings.get("enabled", True):
            return

        if is_password_field_active():
            self.buffer = ""
            return

        try:
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                return

            if key in {
                keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab,
                keyboard.Key.esc, keyboard.Key.left, keyboard.Key.right,
                keyboard.Key.up, keyboard.Key.down, keyboard.Key.home,
                keyboard.Key.end, keyboard.Key.page_up, keyboard.Key.page_down,
                keyboard.Key.delete,
            }:
                if key in {keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab}:
                    self._check_autocorrect(key)
                self.buffer = ""
                return

            char = getattr(key, "char", None)
            if char is None:
                return

            self.buffer += char
            max_len = int(settings.get("max_buffer", 250))
            self.buffer = self.buffer[-max_len:]

            win_title, win_proc = get_active_window_info()
            
            blacklist = settings.get("blacklist", "")
            if blacklist:
                blocked_procs = [p.strip().lower() for p in blacklist.split(",") if p.strip()]
                for bp in blocked_procs:
                    if bp in win_proc.lower():
                        self.buffer = ""
                        return

            snippets = get_all_snippets()
            
            matched_snippet = None
            matched_trigger = None

            for s in sorted(snippets, key=lambda x: len(x.shortcut), reverse=True):
                if not s.enabled:
                    continue
                
                if s.app_filter and s.app_filter.lower() not in win_proc.lower():
                    continue
                if s.window_filter and s.window_filter.lower() not in win_title.lower():
                    continue

                if s.regex_enabled:
                    match = re.search(s.shortcut + "$", self.buffer)
                    if match:
                        matched_snippet = s
                        matched_trigger = match.group(0)
                        break
                else:
                    case_sensitive = settings.get("case_sensitive", True)
                    if case_sensitive:
                        matched = self.buffer.endswith(s.shortcut)
                    else:
                        matched = self.buffer.lower().endswith(s.shortcut.lower())
                        
                    if matched:
                        matched_snippet = s
                        matched_trigger = s.shortcut
                        break

            if matched_snippet:
                self._expand(matched_trigger, matched_snippet)

        except Exception as e:
            logger.error(f"Listener error: {e}")
            self.buffer = ""

    def _expand(self, trigger: str, snippet):
        with self._lock:
            self.suspended = True
            try:
                fields = get_form_fields(snippet.replacement)
                replacement = snippet.replacement
                
                if fields and self.form_prompt_callback:
                    answers = self.form_prompt_callback(snippet, fields)
                    if answers is None:
                        self.buffer = ""
                        return
                    replacement = replace_form_fields(replacement, answers)

                replacement = parse_variables(replacement, snippet.usage_counter)

                for _ in range(len(trigger)):
                    self.controller.press(keyboard.Key.backspace)
                    self.controller.release(keyboard.Key.backspace)
                    time.sleep(0.002)

                self.controller.type(replacement)
                self.buffer = ""
                
                increment_usage(snippet.id)
            except Exception as e:
                logger.error(f"Expansion failed: {e}")
            finally:
                time.sleep(0.03)
                self.suspended = False

    def _check_autocorrect(self, trigger_key):
        try:
            corrections = get_all_corrections()
        except Exception as e:
            logger.error(f"Failed to fetch auto-corrections: {e}")
            return
            
        for typo, correction in corrections.items():
            pattern = r"(?:^|\s)" + re.escape(typo) + r"$"
            match = re.search(pattern, self.buffer)
            if match:
                self._perform_autocorrect(typo, correction, trigger_key)
                break

    def _perform_autocorrect(self, typo, correction, trigger_key):
        with self._lock:
            self.suspended = True
            try:
                for _ in range(len(typo)):
                    self.controller.press(keyboard.Key.backspace)
                    self.controller.release(keyboard.Key.backspace)
                    time.sleep(0.002)
                self.controller.type(correction)
            except Exception as e:
                logger.error(f"Autocorrect failed: {e}")
            finally:
                time.sleep(0.01)
                self.suspended = False
