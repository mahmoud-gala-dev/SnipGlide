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
