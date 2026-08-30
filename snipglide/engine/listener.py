import threading
import time
import re
from typing import Optional, Callable
from pynput import keyboard
from snipglide.database.snippet_repo import get_enabled_snippets, increment_usage
from snipglide.database.autocorrect_repo import get_all_corrections
from snipglide.engine.parser import parse_variables, get_form_fields, replace_form_fields
from snipglide.engine.window_tracker import get_active_window_info
from snipglide.utils.logger import logger

class ExpansionEngine:
    def __init__(self, settings_provider: Callable[[], dict], form_prompt_callback: Callable[[object, list], Optional[dict]] = None, quick_open_callback: Callable[[], None] = None):
        self.settings_provider = settings_provider
        self.form_prompt_callback = form_prompt_callback
        self.quick_open_callback = quick_open_callback
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
        self._plain_snippets_by_last = {}
        self._plain_snippets_by_last_lower = {}
        self._regex_snippets = []
        self._snippet_order = {}
        self._cached_corrections = {}
        self._min_plain_trigger_len = 1
        self._has_regex_snippets = False
        self._cached_blacklist_raw = None
        self._cached_blacklist = []
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

    def reload_snippets(self):
        """Invalidate cache immediately so new/updated snippets take effect instantly."""
        with self._lock:
            self._last_snippets_fetch = 0
            self._cached_snippets = []
            self.buffer = ""
        logger.info("Snippets reloaded in expansion engine.")

    def set_suspended(self, value: bool):
        self.suspended = value
        self.buffer = ""

    def _is_idle_mode(self) -> bool:
        """Check if we're in idle mode (reduced processing)."""
        return (time.time() - self._last_key_time) > self._idle_threshold

    def _on_press(self, key):
        # 1. Global Hotkey Check: Ctrl + PrintScreen to open/focus application
        try:
            is_print_screen = (
                key == keyboard.Key.print_screen or
                getattr(key, "name", "") == "print_screen" or
                getattr(key, "vk", None) in (44, 0x2C)
            )
            if is_print_screen:
                import ctypes
                # VK_CONTROL = 0x11
                ctrl_pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
                if ctrl_pressed:
                    logger.info("Global shortcut [Ctrl + PrintScreen] detected! Activating SnipGlide.")
                    if self.quick_open_callback:
                        self.quick_open_callback()
                    return
        except Exception as e:
            logger.debug(f"Quick open check failed: {e}")

        if not self.running or self.suspended:
            return
            
        self._last_key_time = time.time()
        
        settings = self.settings_provider()
        if not settings.get("enabled", True):
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
                    if not self._is_sensitive_window():
                        self._check_autocorrect(key)
                self.buffer = ""
                return

            char = getattr(key, "char", None)
            if char is None:
                return

            self.buffer += char
            max_len = int(settings.get("max_buffer", 250))
            self.buffer = self.buffer[-max_len:]

            if not self._get_cached_snippets():
                return
            if not self._has_regex_snippets and len(self.buffer) < self._min_plain_trigger_len:
                return

            win_title, win_proc = self._get_cached_window_info()
            if self._is_sensitive_window(win_title):
                self.buffer = ""
                return

            blacklist = settings.get("blacklist", "")
            if blacklist:
                for bp in self._get_cached_blacklist(blacklist):
                    if bp in win_proc.lower():
                        self.buffer = ""
                        return

            match_result = self._find_snippet_match(settings, win_title, win_proc)
            if match_result:
                matched_trigger, matched_snippet = match_result
                self._expand(matched_trigger, matched_snippet)

        except Exception as e:
            logger.error(f"Listener error: {e}")
            self.buffer = ""

    def _find_snippet_match(self, settings: dict, win_title: str, win_proc: str):
        case_sensitive = settings.get("case_sensitive", True)
        last_char = self.buffer[-1:] if self.buffer else ""
        if case_sensitive:
            candidates = self._plain_snippets_by_last.get(last_char, [])
        else:
            candidates = self._plain_snippets_by_last_lower.get(last_char.lower(), [])

        best = None
        best_order = float("inf")

        for s in candidates:
            if not self._passes_window_filters(s, win_title, win_proc):
                continue
            shortcut = s.shortcut
            if not shortcut:
                continue
            if case_sensitive:
                matched = self.buffer.endswith(shortcut)
            else:
                matched = self.buffer.lower().endswith(shortcut.lower())
            if matched:
                order = self._snippet_order.get(id(s), best_order)
                if order < best_order:
                    best = (shortcut, s)
                    best_order = order

        for pattern, s in self._regex_snippets:
            if not self._passes_window_filters(s, win_title, win_proc):
                continue
            match = pattern.search(self.buffer)
            if match:
                order = self._snippet_order.get(id(s), best_order)
                if order < best_order:
                    best = (match.group(0), s)
                    best_order = order

        return best

    def _passes_window_filters(self, s, win_title: str, win_proc: str) -> bool:
        if s.app_filter and s.app_filter.lower() not in win_proc.lower():
            return False
        if s.window_filter and s.window_filter.lower() not in win_title.lower():
            return False
        return True
            
    def _get_cached_window_info(self):
        """Get window info with caching to reduce system calls."""
        now = time.time()
        if now - self._last_window_check > self._window_check_interval:
            self._cached_window_info = get_active_window_info()
            self._last_window_check = now
        return self._cached_window_info

    def _is_sensitive_window(self, win_title: str = None) -> bool:
        if win_title is None:
            win_title, _ = self._get_cached_window_info()
        lower_title = win_title.lower()
        return "password" in lower_title or "login" in lower_title or "sign in" in lower_title

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
                self._cached_snippets = sorted(get_enabled_snippets(), key=lambda x: len(x.shortcut), reverse=True)
                self._rebuild_snippet_indexes()
            except Exception as e:
                logger.error(f"Failed to fetch snippets: {e}")
            self._last_snippets_fetch = now
        return self._cached_snippets

    def _rebuild_snippet_indexes(self):
        self._plain_snippets_by_last = {}
        self._plain_snippets_by_last_lower = {}
        self._regex_snippets = []
        self._snippet_order = {}
        plain_lengths = []

        for index, snippet in enumerate(self._cached_snippets):
            self._snippet_order[id(snippet)] = index
            shortcut = snippet.shortcut or ""
            if not shortcut:
                continue

            if snippet.regex_enabled:
                try:
                    self._regex_snippets.append((re.compile(shortcut + "$"), snippet))
                except re.error as e:
                    logger.warning(f"Invalid regex snippet ignored: {shortcut} ({e})")
                continue

            plain_lengths.append(len(shortcut))
            self._plain_snippets_by_last.setdefault(shortcut[-1], []).append(snippet)
            self._plain_snippets_by_last_lower.setdefault(shortcut[-1].lower(), []).append(snippet)

        self._min_plain_trigger_len = min(plain_lengths) if plain_lengths else 1
        self._has_regex_snippets = bool(self._regex_snippets)

    def _get_cached_corrections(self):
        now = time.time()
        if now - self._last_corrections_fetch > self._cache_ttl:
            try:
                self._cached_corrections = get_all_corrections()
            except Exception as e:
                logger.error(f"Failed to fetch auto-corrections: {e}")
            self._last_corrections_fetch = now
        return self._cached_corrections

    def _get_cached_blacklist(self, blacklist: str):
        if blacklist != self._cached_blacklist_raw:
            self._cached_blacklist_raw = blacklist
            self._cached_blacklist = [p.strip().lower() for p in blacklist.split(",") if p.strip()]
        return self._cached_blacklist

    def _check_autocorrect(self, trigger_key):
        corrections = self._get_cached_corrections()
        if not corrections:
            return

        match = re.search(r"(?:^|\s)(\S+)$", self.buffer)
        if not match:
            return

        typo = match.group(1).lower()
        correction = corrections.get(typo)
        if correction:
            self._perform_autocorrect(typo, correction, trigger_key)

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
