import threading
import time
import re
from typing import Optional, Callable
from pynput import keyboard
from snipglide.database.snippet_repo import get_enabled_snippets, increment_usage
from snipglide.database.autocorrect_repo import get_all_corrections
from snipglide.engine.parser import (
    parse_variables, extract_form_fields, replace_form_variables,
    get_form_fields, replace_form_fields
)
from snipglide.engine.window_tracker import get_active_window_info
from snipglide.utils.helpers import get_clipboard_text, set_clipboard_text
from snipglide.utils.logger import logger

class WindowsGlobalHotkeyThread(threading.Thread):
    """
    Dedicated Windows OS kernel-level hotkey listener using RegisterHotKey.
    Guarantees 100% reliable detection of Ctrl+Alt+PrintScreen and Ctrl+PrintScreen
    even when Alt is held or Windows shell attempts to intercept VK_SNAPSHOT.
    """
    def __init__(self, on_full_callback: Callable[[], None], on_area_callback: Callable[[], None]):
        super().__init__()
        self.daemon = True
        self.on_full_callback = on_full_callback
        self.on_area_callback = on_area_callback
        self._thread_id = None
        self._running = False

    def run(self):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        self._running = True

        HOTKEY_ID_FULL = 9911
        HOTKEY_ID_AREA = 9912
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_NOREPEAT = 0x4000
        VK_SNAPSHOT = 0x2C

        reg_area = user32.RegisterHotKey(None, HOTKEY_ID_AREA, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_SNAPSHOT)
        if not reg_area:
            reg_area = user32.RegisterHotKey(None, HOTKEY_ID_AREA, MOD_CONTROL | MOD_ALT, VK_SNAPSHOT)

        reg_full = user32.RegisterHotKey(None, HOTKEY_ID_FULL, MOD_CONTROL | MOD_NOREPEAT, VK_SNAPSHOT)
        if not reg_full:
            reg_full = user32.RegisterHotKey(None, HOTKEY_ID_FULL, MOD_CONTROL, VK_SNAPSHOT)

        logger.info(f"Windows Native Hotkeys registered: Area={bool(reg_area)}, Full={bool(reg_full)}")

        msg = wintypes.MSG()
        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            if msg.message == 0x0312:  # WM_HOTKEY
                hid = msg.wParam
                if hid == HOTKEY_ID_AREA:
                    logger.info("Windows Native Hotkey [Ctrl + Alt + PrintScreen] fired!")
                    if self.on_area_callback:
                        self.on_area_callback()
                elif hid == HOTKEY_ID_FULL:
                    logger.info("Windows Native Hotkey [Ctrl + PrintScreen] fired!")
                    if self.on_full_callback:
                        self.on_full_callback()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.UnregisterHotKey(None, HOTKEY_ID_AREA)
            user32.UnregisterHotKey(None, HOTKEY_ID_FULL)
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self._thread_id:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
            except Exception:
                pass

class ExpansionEngine:
    def __init__(
        self,
        settings_provider: Callable[[], dict],
        form_prompt_callback: Callable[[object, list], Optional[dict]] = None,
        quick_open_callback: Callable[[], None] = None,
        capture_full_callback: Callable[[], None] = None,
        capture_area_callback: Callable[[], None] = None,
    ):
        self.settings_provider = settings_provider
        self.form_prompt_callback = form_prompt_callback
        self.quick_open_callback = quick_open_callback
        self.capture_full_callback = capture_full_callback
        self.capture_area_callback = capture_area_callback
        self.buffer = ""
        self.controller = keyboard.Controller()
        self.listener: Optional[keyboard.Listener] = None
        self.native_hotkey_thread: Optional[WindowsGlobalHotkeyThread] = None
        self.running = False
        self.suspended = False
        self._lock = threading.RLock()
        self._last_capture_time = 0
        self._win_pressed = False
        
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
        self._last_win_time = 0
        self._last_ctrl_time = 0
        self._last_alt_time = 0

    def _trigger_capture_full(self):
        now = time.time()
        if now - self._last_capture_time < 0.4:
            return
        self._last_capture_time = now
        logger.info("Global shortcut [Ctrl + PrintScreen] triggered! Capturing Full Screen.")
        if self.capture_full_callback:
            self.capture_full_callback()

    def _trigger_capture_area(self):
        now = time.time()
        if now - self._last_capture_time < 0.4:
            return
        self._last_capture_time = now
        logger.info("Global shortcut [Win + PrintScreen] triggered! Launching Area Snipping.")
        if self.capture_area_callback:
            self.capture_area_callback()

    def start(self):
        if self.listener is not None:
            return
        self.running = True

        # 1. Native Windows kernel-level global hotkey listener
        try:
            self.native_hotkey_thread = WindowsGlobalHotkeyThread(
                on_full_callback=self._trigger_capture_full,
                on_area_callback=self._trigger_capture_area,
            )
            self.native_hotkey_thread.start()
        except Exception as e:
            logger.warning(f"Failed to start native hotkey thread: {e}")

        # 2. Pynput low-level keyboard hook
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.listener.daemon = True
        self.listener.start()
        logger.info("Expansion engine started successfully with dual hotkey listeners.")

    def stop(self):
        self.running = False
        if self.native_hotkey_thread:
            try:
                self.native_hotkey_thread.stop()
            except Exception:
                pass
            self.native_hotkey_thread = None
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

    def _check_screenshot_keys(self, key) -> bool:
        """Check for Win+PrintScreen, Ctrl+Alt+PrintScreen, and Ctrl+PrintScreen combinations."""
        try:
            vk = getattr(key, "vk", None)
            key_name = getattr(key, "name", "")
            key_str = str(key)
            is_print_screen = (
                key == keyboard.Key.print_screen or
                key_name in ("print_screen", "snapshot", "print") or
                key_str in ("Key.print_screen", "<44>", "Key.snapshot", "'\\x2c'") or
                vk in (44, 0x2C)
            )
            if is_print_screen:
                import ctypes
                user32 = ctypes.windll.user32
                now = time.time()
                win_recent = (now - getattr(self, "_last_win_time", 0)) < 0.45
                ctrl_recent = (now - getattr(self, "_last_ctrl_time", 0)) < 0.45
                alt_recent = (now - getattr(self, "_last_alt_time", 0)) < 0.45

                win_pressed = bool(
                    self._win_pressed or
                    win_recent or
                    (user32.GetAsyncKeyState(0x5B) & 0x8000) or
                    (user32.GetAsyncKeyState(0x5C) & 0x8000) or
                    (user32.GetKeyState(0x5B) & 0x8000) or
                    (user32.GetKeyState(0x5C) & 0x8000)
                )
                ctrl_pressed = bool(
                    ctrl_recent or
                    (user32.GetAsyncKeyState(0x11) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA2) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA3) & 0x8000) or
                    (user32.GetKeyState(0x11) & 0x8000)
                )
                alt_pressed = bool(
                    alt_recent or
                    (user32.GetAsyncKeyState(0x12) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA4) & 0x8000) or
                    (user32.GetAsyncKeyState(0xA5) & 0x8000) or
                    (user32.GetKeyState(0x12) & 0x8000)
                )

                # 1. Win + PrintScreen (requested by user) OR Ctrl + Alt + PrintScreen -> Area Snipping
                if win_pressed or (ctrl_pressed and alt_pressed):
                    logger.info(f"Area snipping shortcut detected! (Win={win_pressed}, Ctrl={ctrl_pressed}, Alt={alt_pressed})")
                    self._trigger_capture_area()
                    return True

                # 2. Ctrl + PrintScreen -> Full Screen Capture
                if ctrl_pressed:
                    logger.info("Full screen capture shortcut [Ctrl + PrintScreen] detected!")
                    self._trigger_capture_full()
                    return True
        except Exception as e:
            logger.debug(f"Screenshot hotkey check failed: {e}")
        return False

    def _on_release(self, key):
        vk = getattr(key, "vk", None)
        now = time.time()
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r) or vk in (0x5B, 0x5C, 91, 92):
            self._win_pressed = False
            self._last_win_time = now
        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r) or vk in (0x11, 0xA2, 0xA3, 17, 162, 163):
            self._last_ctrl_time = now
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr) or vk in (0x12, 0xA4, 0xA5, 18, 164, 165):
            self._last_alt_time = now

        self._check_screenshot_keys(key)

    def _on_press(self, key):
        vk = getattr(key, "vk", None)
        now = time.time()
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r) or vk in (0x5B, 0x5C, 91, 92):
            self._win_pressed = True
            self._last_win_time = now
        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r) or vk in (0x11, 0xA2, 0xA3, 17, 162, 163):
            self._last_ctrl_time = now
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr) or vk in (0x12, 0xA4, 0xA5, 18, 164, 165):
            self._last_alt_time = now

        if self._check_screenshot_keys(key):
            return

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
                fields = extract_form_fields(snippet.replacement)
                replacement = snippet.replacement
                
                if fields and self.form_prompt_callback:
                    answers = self.form_prompt_callback(snippet, fields)
                    if answers is None:
                        self.buffer = ""
                        return
                    replacement = replace_form_variables(replacement, answers)

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
