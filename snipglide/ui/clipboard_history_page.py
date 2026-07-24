import customtkinter as ctk
from snipglide.database.clipboard_repo import get_clipboard_history, clear_clipboard_history
from snipglide.database.connection import get_connection

class ClipboardHistoryPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, navigate_to_snippet_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.navigate_to_snippet_callback = navigate_to_snippet_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header_frame, text="📋 Clipboard History Manager", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w")
        
        self.clear_btn = ctk.CTkButton(header_frame, text="🧹 Clear History", fg_color="#dc2626", hover_color="#b91c1c", width=120, command=self._clear_all)
        self.clear_btn.grid(row=0, column=1, sticky="e")
        
        self.scroll_list = ctk.CTkScrollableFrame(self)
        self.scroll_list.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        self.refresh_history()
        
    def refresh_history(self):
        for widget in self.scroll_list.winfo_children():
            widget.destroy()
            
        try:
            history = get_clipboard_history(15)
        except Exception as e:
            ctk.CTkLabel(self.scroll_list, text=f"Failed to load history: {e}", text_color="red").pack(pady=20)
            return
            
        if not history:
            ctk.CTkLabel(self.scroll_list, text="Clipboard history is empty.", text_color="gray").pack(pady=40)
            return
            
        for text in history:
            self._create_history_row(text)
            
    def _create_history_row(self, text: str):
        row = ctk.CTkFrame(self.scroll_list, fg_color=("gray90", "gray15"))
        row.pack(fill="x", pady=5, padx=5)
        
        preview = text.strip().replace("\n", " ")
        if len(preview) > 55:
            preview = preview[:55] + "..."
            
        lbl = ctk.CTkLabel(row, text=preview, anchor="w", font=ctk.CTkFont(size=12))
        lbl.pack(side="left", padx=15, pady=10, fill="x", expand=True)
        
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        
        ctk.CTkButton(btn_frame, text="📋 Copy", width=70, height=28, command=lambda t=text: self._copy_to_clipboard(t)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="➕ Save Snippet", width=110, height=28, fg_color="#2563eb", command=lambda t=text: self._save_as_snippet(t)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="❌", width=28, height=28, fg_color="#dc2626", hover_color="#b91c1c", command=lambda t=text: self._delete_entry(t)).pack(side="left", padx=2)
        
    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.toast_callback("Copied to clipboard!")
        
    def _save_as_snippet(self, text: str):
        self.navigate_to_snippet_callback(text)
        
    def _delete_entry(self, text: str):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (text,))
                conn.commit()
            self.refresh_history()
            self.toast_callback("Entry deleted.")
        except Exception as e:
            self.toast_callback(f"Failed to delete: {e}", error=True)
            
    def _clear_all(self):
        try:
            clear_clipboard_history()
            self.refresh_history()
            self.toast_callback("Clipboard history cleared.")
        except Exception as e:
            self.toast_callback(f"Clear failed: {e}", error=True)
