import sys
import re
import tkinter as tk
from pathlib import Path


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent.parent / relative

import os
import time
import ctypes

_user32 = ctypes.windll.user32 if os.name == "nt" else None
_kernel32 = ctypes.windll.kernel32 if os.name == "nt" else None

if _kernel32:
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

if _user32:
    _user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    _user32.OpenClipboard.restype = ctypes.c_bool
    _user32.CloseClipboard.argtypes = []
    _user32.CloseClipboard.restype = ctypes.c_bool
    _user32.EmptyClipboard.argtypes = []
    _user32.EmptyClipboard.restype = ctypes.c_bool
    _user32.SetClipboardData.restype = ctypes.c_void_p
    _user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    _user32.GetClipboardData.restype = ctypes.c_void_p
    _user32.GetClipboardData.argtypes = [ctypes.c_uint]


def get_clipboard_text(max_chars: int = 50000) -> str:
    """Fast, thread-safe, native Windows clipboard text reader."""
    if os.name != "nt" or not _user32:
        return ""

    CF_UNICODETEXT = 13
    for _ in range(8):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        return ""

    try:
        h_data = _user32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return ""
        ptr = _kernel32.GlobalLock(h_data)
        if not ptr:
            return ""
        try:
            val = ctypes.wstring_at(ptr)
            if len(val) > max_chars:
                return val[:max_chars]
            return val
        finally:
            _kernel32.GlobalUnlock(h_data)
    except Exception:
        return ""
    finally:
        _user32.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    """Fast, thread-safe, native Windows clipboard text writer."""
    if os.name != "nt" or not _user32:
        return False

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    data = (text + "\x00").encode("utf-16-le")
    h_mem = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h_mem:
        return False

    ptr = _kernel32.GlobalLock(h_mem)
    if not ptr:
        _kernel32.GlobalFree(h_mem)
        return False

    ctypes.memmove(ptr, data, len(data))
    _kernel32.GlobalUnlock(h_mem)

    for _ in range(8):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        _kernel32.GlobalFree(h_mem)
        return False

    try:
        _user32.EmptyClipboard()
        res = _user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        return bool(res)
    except Exception:
        return False
    finally:
        _user32.CloseClipboard()


def safe_clear_frame(frame):
    """
    Safely destroy all children of a CTkScrollableFrame/CTkFrame.
    Unbinds <Configure> from every descendant before destroying to prevent
    CustomTkinter's '_update_dimensions_event' firing on dead widget references.
    """
    def _unbind_and_destroy(widget):
        try:
            for child in widget.winfo_children():
                _unbind_and_destroy(child)
            try:
                widget.unbind("<Configure>")
            except Exception:
                pass
            widget.destroy()
        except Exception:
            pass

    for child in list(frame.winfo_children()):
        _unbind_and_destroy(child)

def create_context_menu(widget, has_ai=False, ai_callback=None):
    import tkinter as tk
    
    # Check if widget has an inner textbox or entry, and target it for native compatibility
    target = getattr(widget, "_textbox", getattr(widget, "_entry", widget))
    
    menu = tk.Menu(target, tearoff=0, font=("Segoe UI", 13))
    
    def cut():
        target.event_generate("<<Cut>>")
    def copy():
        target.event_generate("<<Copy>>")
    def paste():
        target.event_generate("<<Paste>>")
    def select_all():
        target.event_generate("<<SelectAll>>")
        
    menu.add_command(label="✂️ Cut", command=cut)
    menu.add_command(label="📋 Copy", command=copy)
    menu.add_command(label="📥 Paste", command=paste)
    menu.add_separator()
    menu.add_command(label="🔍 Select All", command=select_all)
    
    if has_ai and ai_callback:
        menu.add_separator()
        menu.add_command(label="🤖 AI Optimize", command=ai_callback)
        
    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            
    target.bind("<Button-3>", show_menu)

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def apply_rtl_support(widget):
    target = getattr(widget, "_textbox", getattr(widget, "_entry", widget))
    rtl_job = None
    last_text = None
    current_state = None  # (is_arabic, font_family, align)
    
    from snipglide.core.config import get_arabic_font_family
    
    if isinstance(target, tk.Text):
        target.tag_configure("rtl_align", justify="right")
        target.tag_configure("ltr_align", justify="left")
    
    def on_check():
        nonlocal last_text, current_state
        try:
            if isinstance(target, tk.Entry):
                text = target.get()
                if text == last_text:
                    return
                last_text = text
                has_arabic = bool(ARABIC_RE.search(text))
                align = "right" if has_arabic else "left"
                family = get_arabic_font_family() if has_arabic else "Segoe UI"
                new_state = (has_arabic, family, align)
                if new_state != current_state:
                    current_state = new_state
                    target.configure(justify=align, font=(family, 13))
            elif isinstance(target, tk.Text):
                text = target.get("1.0", "end-1c")
                if text == last_text:
                    return
                last_text = text
                has_arabic = bool(ARABIC_RE.search(text))
                family = get_arabic_font_family() if has_arabic else "Consolas"
                new_state = (has_arabic, family)
                if new_state != current_state:
                    current_state = new_state
                    target.configure(font=(family, 13))
                    if has_arabic:
                        target.tag_remove("ltr_align", "1.0", "end")
                        target.tag_add("rtl_align", "1.0", "end")
                    else:
                        target.tag_remove("rtl_align", "1.0", "end")
                        target.tag_add("ltr_align", "1.0", "end")
        except Exception:
            pass

    def schedule_text_check(event=None):
        nonlocal rtl_job
        if rtl_job:
            target.after_cancel(rtl_job)
        # 180ms debounce avoids re-evaluating on every micro keystroke
        rtl_job = target.after(180, on_check)

    target.bind("<KeyRelease>", schedule_text_check, add="+")
    target.after(50, on_check)


def download_and_load_arabic_font(font_name: str = "Tajawal") -> str:
    import urllib.request
    import ctypes
    import os
    from pathlib import Path
    from snipglide.utils.logger import logger
    
    font_dir = Path(os.environ.get("APPDATA", ".")) / "SnipGlide" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    
    font_urls = {
        "Tajawal": ("Tajawal-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/tajawal/Tajawal-Regular.ttf"),
        "Cairo": ("Cairo-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-Regular.ttf"),
        "Almarai": ("Almarai-Regular.ttf", "https://github.com/google/fonts/raw/main/ofl/almarai/Almarai-Regular.ttf"),
    }
    
    selected = font_urls.get(font_name, ("Tajawal-Regular.ttf", font_urls["Tajawal"][1]))
    font_filename, font_url = selected
    font_path = font_dir / font_filename
    
    if not font_path.exists():
        try:
            logger.info(f"Downloading {font_name} Arabic Font from Google Fonts...")
            urllib.request.urlretrieve(font_url, str(font_path))
            logger.info(f"{font_name} font downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download {font_name} font: {e}")
            return "Segoe UI"
            
    actual_family = font_name
    try:
        from PySide6.QtGui import QFontDatabase
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                actual_family = families[0]
                logger.info(f"Registered Qt Application Font: {actual_family}")
    except Exception:
        pass

    try:
        FR_PRIVATE = 0x10
        res = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
        if res != 0:
            logger.info(f"{font_name} Arabic font loaded via GDI.")
            return actual_family
    except Exception as e:
        logger.error(f"Failed to load {font_name} font via GDI: {e}")
        
    return actual_family if actual_family else "Segoe UI"


def ensure_sound_asset() -> Path:
    """Ensure that the soft expansion sound WAV asset exists, generating it if needed."""
    import wave
    import struct
    import math

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    sound_path = assets_dir / "expand_sound.wav"

    if sound_path.exists() and sound_path.stat().st_size > 500:
        return sound_path

    try:
        sample_rate = 44100
        duration = 0.055  # 55ms - short, subtle, soft chime
        num_samples = int(sample_rate * duration)

        with wave.open(str(sound_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            for i in range(num_samples):
                t = i / sample_rate
                envelope = math.sin(math.pi * (i / num_samples)) ** 0.6 * math.exp(-18 * t)
                freq = 680 - (140 * (i / num_samples))
                sample_val = (
                    0.65 * math.sin(2 * math.pi * freq * t) +
                    0.35 * math.sin(2 * math.pi * (freq * 1.5) * t)
                ) * envelope

                int_sample = int(sample_val * 32767 * 0.22)
                int_sample = max(-32768, min(32767, int_sample))
                wav_file.writeframes(struct.pack("<h", int_sample))
    except Exception:
        pass

    return sound_path


