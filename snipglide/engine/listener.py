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
        
        # Cache with longer TTL to reduce database queries
        self._last_snippets_fetch = 0
        self._last_corrections_fetch = 0
        self._cached_snippets = []
        self._cached_corrections = {}
        self._cache_ttl = 5.0  # Cache TTL in seconds (increased for better performance)
        
        # Throttle window info checks to reduce system calls
        self._last_window_check = 0
        self._window_check_interval = 0.5  # Check window info every 500ms max
        self._cached_window_info = ("", "")
        
        # Low-power mode when idle
        self._last_key_time = 0
        self._idle_threshold = 30.0  # Consider idle after 30 seconds

    def start(self):
        if self.listener is not None:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.daemon = True
        self.listener.start()
        logger.info("Expansion engine started (optimized mode).")

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        logger.info("Expansion engine stopped.")

    def set_suspended(self, value: bool):
        self.suspended = value
        self.buffer = ""
        
    def _is_idle_mode(self) -> bool:
        """Check if we're in idle mode (reduced processing)."""
        return (time.time() - self._last_key_time) > self._idle_threshold

    def _on_press(self, key):
        if not self.running or self.suspended:
            return
            
        self._last_key_time = time.time()
        
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

            # Use cached window info to reduce system calls
            win_title, win_proc = self._get_cached_window_info()
            
            blacklist = settings.get("blacklist", "")
            if blacklist:
                blocked_procs = [p.strip().lower() for p in blacklist.split(",") if p.strip()]
                for bp in blocked_procs:
                    if bp in win_proc.lower():
                        self.buffer = ""
                        return

            # Skip snippet matching if in idle mode and buffer is short
            if self._is_idle_mode() and len(self.buffer) < 3:
                return

            snippets = self._get_cached_snippets()
            
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
            
    def _get_cached_window_info(self):
        """Get window info with caching to reduce system calls."""
        now = time.time()
        if now - self._last_window_check > self._window_check_interval:
            self._cached_window_info = get_active_window_info()
            self._last_window_check = now
        return self._cached_window_info

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
                    time.sleep(0.001)  # Reduced delay for faster deletion

                self.controller.type(replacement)
                self.buffer = ""
                
                increment_usage(snippet.id)
                self._play_expansion_sound()
            except Exception as e:
                logger.error(f"Expansion failed: {e}")
            finally:
                time.sleep(0.02)  # Reduced delay
                self.suspended = False

    def invalidate_cache(self):
        self._last_snippets_fetch = 0
        self._last_corrections_fetch = 0

    def _get_cached_snippets(self):
        now = time.time()
        if now - self._last_snippets_fetch > self._cache_ttl:
            try:
                self._cached_snippets = get_all_snippets()
            except Exception as e:
                logger.error(f"Failed to fetch snippets: {e}")
            self._last_snippets_fetch = now
        return self._cached_snippets

    def _get_cached_corrections(self):
        now = time.time()
        if now - self._last_corrections_fetch > self._cache_ttl:
            try:
                self._cached_corrections = get_all_corrections()
            except Exception as e:
                logger.error(f"Failed to fetch auto-corrections: {e}")
            self._last_corrections_fetch = now
        return self._cached_corrections

    def _check_autocorrect(self, trigger_key):
        corrections = self._get_cached_corrections()
        if not corrections:
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
                    time.sleep(0.001)  # Reduced delay
                self.controller.type(correction)
                self._play_expansion_sound()
            except Exception as e:
                logger.error(f"Autocorrect failed: {e}")
            finally:
                time.sleep(0.01)
                self.suspended = False

    def _play_expansion_sound(self):
        settings = self.settings_provider()
        if settings.get("play_sound", True):
            try:
                import winsound
                import threading
                threading.Thread(target=lambda: winsound.Beep(2100, 32), daemon=True).start()
            except Exception:
                pass
