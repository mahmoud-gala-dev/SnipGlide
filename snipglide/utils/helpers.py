import sys
import re
import tkinter as tk
from pathlib import Path


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent.parent / relative

def get_clipboard_text(max_chars: int = 10000) -> str:
    """Fast, thread-safe, native Windows clipboard text reader without GUI overhead."""
    import ctypes
    from ctypes import wintypes
    
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t

    try:
        if not user32.OpenClipboard(None):
            return ""
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            user32.CloseClipboard()
            return ""
        if kernel32.GlobalSize(handle) > (max_chars + 1) * 2:
            user32.CloseClipboard()
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            user32.CloseClipboard()
            return ""
        try:
            return ctypes.string_at(pointer).decode("utf-16-le").split("\x00", 1)[0]
        finally:
            kernel32.GlobalUnlock(handle)
            user32.CloseClipboard()
    except Exception:
        return ""

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
            
    try:
        FR_PRIVATE = 0x10
        res = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
        if res != 0:
            logger.info(f"{font_name} Arabic font loaded successfully.")
            return font_name
    except Exception as e:
        logger.error(f"Failed to load {font_name} font: {e}")
        
    return "Segoe UI"

