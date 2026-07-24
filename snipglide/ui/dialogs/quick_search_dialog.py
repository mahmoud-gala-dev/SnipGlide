import tkinter as tk
import customtkinter as ctk
import time
import threading
from snipglide.database.snippet_repo import get_all_snippets, increment_usage

class QuickSearchDialog(ctk.CTkToplevel):
    def __init__(self, parent, parse_callback, **kwargs):
        super().__init__(parent, **kwargs)
        self.parse_callback = parse_callback
        
        # Borderless, floating window
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Geometry: 520x350, centered on screen
        width = 520
        height = 360
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Theme border color
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        bg_color = "#1e1e1e" if is_dark else "#f3f4f6"
        self.configure(fg_color=bg_color)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Inner Frame for border effect
        inner = ctk.CTkFrame(self, fg_color=bg_color, border_width=2, border_color="#3b82f6")
        inner.grid(row=0, column=0, rowspan=2, sticky="nsew")
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_rowconfigure(1, weight=1)
        
        # Search Entry
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            inner,
            textvariable=self.search_var,
            placeholder_text="🔍 Type to search... (Hit Enter to paste first result)",
            height=45,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Return>", self._on_enter_press)
        self.search_entry.bind("<Escape>", lambda e: self.destroy())
        
        # Scrollable area
        self.scroll = ctk.CTkScrollableFrame(inner, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Close on losing focus
        self.bind("<FocusOut>", self._on_focus_out)
        
        # Initial load
        self.all_snippets = get_all_snippets()
        self.filtered = list(self.all_snippets)
        self._render_list()
        
        # Force focus
        self.lift()
        self.after(100, lambda: self.search_entry.focus_force())
        
    def _on_focus_out(self, event):
        try:
            focused = self.focus_get()
            if focused and (focused == self or focused.winfo_toplevel() == self):
                return
        except Exception:
            pass
        self.destroy()

    def _on_search_change(self, event):
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered = list(self.all_snippets)
        else:
            self.filtered = [
                s for s in self.all_snippets 
                if query in s.shortcut.lower() or query in (s.description or "").lower() or query in s.replacement.lower()
            ]
        self._render_list()

    def _render_list(self):
        for w in self.scroll.winfo_children():
            w.destroy()
            
        if not self.filtered:
            ctk.CTkLabel(self.scroll, text="No matching snippets.", text_color="gray").pack(pady=20)
            return
            
        for i, snippet in enumerate(self.filtered):
            bg = ("gray80", "gray25") if i == 0 else "transparent"
            
            row = ctk.CTkFrame(self.scroll, fg_color=bg, height=36)
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)
            
            shortcut_lbl = ctk.CTkLabel(row, text=snippet.shortcut, font=ctk.CTkFont(weight="bold", size=12), text_color="#3b82f6")
            shortcut_lbl.pack(side="left", padx=10)
            
            desc = snippet.description or snippet.replacement[:40].replace("\n", " ")
            desc_lbl = ctk.CTkLabel(row, text=f"-  {desc}", font=ctk.CTkFont(size=11), text_color=("gray50", "gray70"))
            desc_lbl.pack(side="left", padx=5)
            
            for widget in [row, shortcut_lbl, desc_lbl]:
                widget.bind("<Button-1>", lambda e, s=snippet: self._select_snippet(s))

    def _on_enter_press(self, event):
        if self.filtered:
            self._select_snippet(self.filtered[0])

    def _select_snippet(self, snippet):
        self.destroy()
        
        def paste_action():
            time.sleep(0.12)
            
            import win32clipboard
            import win32con
            
            expanded_text = self.parse_callback(snippet.replacement)
            
            backup_text = ""
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    backup_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                pass
                
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(expanded_text, win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                return
                
            from pynput.keyboard import Controller, Key
            kb = Controller()
            with kb.pressed(Key.ctrl):
                kb.press('v')
                kb.release('v')
                
            time.sleep(0.4)
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(backup_text, win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                pass
                
            increment_usage(snippet.id)
            
        threading.Thread(target=paste_action, daemon=True).start()
