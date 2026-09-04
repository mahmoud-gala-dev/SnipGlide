import threading
import time
import re
from typing import Optional, Callable
from pynput import keyboard
from snipglide.database.snippet_repo import get_enabled_snippets, increment_usage
from snipglide.database.autocorrect_repo import get_all_corrections
from snipglide.engine.parser import parse_variables, get_form_fields, replace_form_fields
from snipglide.engine.window_tracker import get_active_window_info
from snipglide.utils.helpers import get_clipboard_text, set_clipboard_text
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
        
        # Cache with TTL to reduce database queries
        self._last_snippets_fetch = 0
        self._last_corrections_fetch = 0
        self._cached_snippets = []
        self._plain_snippets = []
        self._regex_snippets = []
        self._cached_corrections = {}
        self._cached_blacklist_raw = None
        self._cached_blacklist = []
        self._cache_ttl = 3.0
        
        # Throttle window info checks
        self._last_window_check = 0
        self._window_check_interval = 0.3
        self._cached_window_info = ("", "")
        self._last_key_time = time.time()

    def start(self):
        if self.listener is not None:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.daemon = True
        self.listener.start()
        logger.info("Expansion engine started successfully.")

    def stop(self):
        self.running = False
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
        logger.info("Expansion engine stopped.")

    def reload_snippets(self):
        """Invalidate cache immediately so new/updated snippets take effect instantly."""
        with self._lock:
            self._last_snippets_fetch = 0
            self._cached_snippets = []
            self._plain_snippets = []
            self._regex_snippets = []
            self.buffer = ""
        logger.info("Snippets reloaded in expansion engine.")

    def set_suspended(self, value: bool):
        self.suspended = value
        self.buffer = ""

    def _on_press(self, key):
        # 1. Global Hotkey Check: Ctrl + PrintScreen to open/restore/focus application
        try:
            vk = getattr(key, "vk", None)
            key_name = getattr(key, "name", "")
            key_str = str(key)
            is_print_screen = (
                key == keyboard.Key.print_screen or
                key_name in ("print_screen", "snapshot", "print") or
                key_str in ("Key.print_screen", "<44>", "Key.snapshot") or
                vk in (44, 0x2C)
            )
            if is_print_screen:
                import ctypes
                user32 = ctypes.windll.user32
                ctrl_pressed = bool(
                    (user32.GetAsyncKeyState(0x11) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA2) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA3) & 0x8000)
                )
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
            # Handle Backspace
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                return

            # Handle reset / navigation keys
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

            # Extract character
            char = getattr(key, "char", None)
            if char is None:
                # Modifier keys alone (Shift, Ctrl, Alt) do not modify or clear buffer
                return

            # Check for control chords (e.g. Ctrl+C = \x03, Ctrl+V = \x16, etc.)
            if ord(char) < 32 and char not in ("\t", "\n", "\r"):
                self.buffer = ""
                return

            self.buffer += char
            max_len = int(settings.get("max_buffer", 250))
            self.buffer = self.buffer[-max_len:]

            snippets = self._get_cached_snippets()
            if not snippets:
                return

            win_title, win_proc = self._get_cached_window_info()

            # Check user blacklist if configured
            blacklist = settings.get("blacklist", "")
            if blacklist and win_proc:
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
        self._get_cached_snippets()
        case_sensitive = settings.get("case_sensitive", True)
        cur_buffer = self.buffer
        cur_buffer_lower = cur_buffer.lower()

        # Check plain snippets (sorted by length descending - longest match first)
        for s in self._plain_snippets:
            if not self._passes_window_filters(s, win_title, win_proc):
                continue
            shortcut = s.shortcut
            if not shortcut:
                continue
            if case_sensitive:
                if cur_buffer.endswith(shortcut):
                    return (shortcut, s)
            else:
                if cur_buffer_lower.endswith(shortcut.lower()):
                    # Return actual typed slice length
                    matched_slice = cur_buffer[-len(shortcut):]
                    return (matched_slice, s)

        # Check regex snippets
        for pattern, s in self._regex_snippets:
            if not self._passes_window_filters(s, win_title, win_proc):
                continue
            match = pattern.search(cur_buffer)
            if match:
                return (match.group(0), s)

        return None

    def _passes_window_filters(self, s, win_title: str, win_proc: str) -> bool:
        if s.app_filter and win_proc:
            if s.app_filter.strip().lower() not in win_proc.lower():
                return False
        if s.window_filter and win_title:
            if s.window_filter.strip().lower() not in win_title.lower():
                return False
        return True
            
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

                # 1. Release modifier keys so Shift+Backspace or Ctrl+Shift+V don't collide
                for mod_key in (
                    keyboard.Key.shift, keyboard.Key.shift_r,
                    keyboard.Key.ctrl, keyboard.Key.ctrl_r,
                    keyboard.Key.alt, keyboard.Key.alt_r
                ):
                    try:
                        self.controller.release(mod_key)
                    except Exception:
                        pass

                time.sleep(0.008)

                # 2. Erase the trigger using Backspace
                for _ in range(len(trigger)):
                    self.controller.press(keyboard.Key.backspace)
                    self.controller.release(keyboard.Key.backspace)
                    time.sleep(0.004)

                time.sleep(0.01)

                # 3. Paste replacement text via Clipboard (fastest, supports multiline, RTL, emojis, code)
                orig_clip = get_clipboard_text()
                copied_ok = set_clipboard_text(replacement)
                if copied_ok:
                    self.controller.press(keyboard.Key.ctrl)
                    self.controller.press("v")
                    self.controller.release("v")
                    self.controller.release(keyboard.Key.ctrl)
                    time.sleep(0.04)
                    if orig_clip is not None:
                        set_clipboard_text(orig_clip)
                else:
                    self.controller.type(replacement)

                self.buffer = ""
                increment_usage(snippet.id)
                self._play_expansion_sound()
            except Exception as e:
                logger.error(f"Expansion failed: {e}")
            finally:
                time.sleep(0.02)
                self.suspended = False

    def invalidate_cache(self):
        self._last_snippets_fetch = 0
        self._last_corrections_fetch = 0

    def _get_cached_snippets(self):
        now = time.time()
        if now - self._last_snippets_fetch > self._cache_ttl:
            try:
                snippets = get_enabled_snippets()
                # Sort longest shortcut first
                self._cached_snippets = sorted(snippets, key=lambda x: len(x.shortcut or ""), reverse=True)
                self._rebuild_snippet_indexes()
            except Exception as e:
                logger.error(f"Failed to fetch snippets: {e}")
            self._last_snippets_fetch = now
        return self._cached_snippets

    def _rebuild_snippet_indexes(self):
        self._plain_snippets = []
        self._regex_snippets = []

        for snippet in self._cached_snippets:
            shortcut = snippet.shortcut or ""
            if not shortcut:
                continue

            if snippet.regex_enabled:
                try:
                    self._regex_snippets.append((re.compile(shortcut + "$"), snippet))
                except re.error as e:
                    logger.warning(f"Invalid regex snippet ignored: {shortcut} ({e})")
                continue

            self._plain_snippets.append(snippet)

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
                    time.sleep(0.004)
                time.sleep(0.01)

                orig_clip = get_clipboard_text()
                copied_ok = set_clipboard_text(correction)
                if copied_ok:
                    self.controller.press(keyboard.Key.ctrl)
                    self.controller.press("v")
                    self.controller.release("v")
                    self.controller.release(keyboard.Key.ctrl)
                    time.sleep(0.03)
                    if orig_clip is not None:
                        set_clipboard_text(orig_clip)
                else:
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
                from pathlib import Path
                sound_file = Path(__file__).resolve().parent.parent / "assets" / "expand_sound.wav"
                if sound_file.exists():
                    winsound.PlaySound(str(sound_file), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                else:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
