import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent.parent / relative

def create_context_menu(widget, has_ai=False, ai_callback=None):
    import tkinter as tk
    
    # Check if widget has an inner textbox or entry, and target it for native compatibility
    target = getattr(widget, "_textbox", getattr(widget, "_entry", widget))
    
    menu = tk.Menu(target, tearoff=0)
    
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

def apply_rtl_support(widget):
    import re
    target = getattr(widget, "_textbox", getattr(widget, "_entry", widget))
    
    from snipglide.core.config import get_arabic_font_family
    font_family = get_arabic_font_family()
    
    def on_key_release(event):
        try:
            if hasattr(target, "get"):
                if hasattr(target, "index"):
                    text = target.get()
                else:
                    text = target.get("1.0", "end-1c")
            else:
                return
                
            has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
            align = "right" if has_arabic else "left"
            if has_arabic:
                target.configure(justify=align, font=(font_family, 11))
            else:
                target.configure(justify=align, font=("Consolas", 11) if not hasattr(target, "index") else ("Segoe UI", 11))
        except Exception:
            pass
            
    target.bind("<KeyRelease>", on_key_release, add="+")
    on_key_release(None)

def download_and_load_arabic_font() -> str:
    import urllib.request
    import ctypes
    import os
    from pathlib import Path
    from snipglide.utils.logger import logger
    
    font_dir = Path(os.environ.get("APPDATA", ".")) / "SnipGlide" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    font_path = font_dir / "Tajawal-Regular.ttf"
    
    if not font_path.exists():
        try:
            url = "https://github.com/google/fonts/raw/main/ofl/tajawal/Tajawal-Regular.ttf"
            logger.info("Downloading Tajawal Arabic Font from Google Fonts...")
            urllib.request.urlretrieve(url, str(font_path))
            logger.info("Tajawal font downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download Tajawal font: {e}")
            return "Segoe UI"
            
    try:
        FR_PRIVATE = 0x10
        res = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
        if res != 0:
            logger.info("Tajawal Arabic font loaded successfully.")
            return "Tajawal"
    except Exception as e:
        logger.error(f"Failed to load Tajawal font: {e}")
        
    return "Segoe UI"
