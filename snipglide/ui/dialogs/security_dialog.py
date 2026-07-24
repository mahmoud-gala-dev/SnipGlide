import customtkinter as ctk

class SecurityDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Master Password", setup_mode=False):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.setup_mode = setup_mode
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 100
        self.geometry(f"+{x}+{y}")
        
        label_text = "Set a new master password:" if setup_mode else "Enter master password to unlock:"
        ctk.CTkLabel(self, text=label_text, font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(20, 5), anchor="w", padx=25)
        
        self.password_entry = ctk.CTkEntry(self, show="*", width=330)
        self.password_entry.pack(pady=5, padx=25)
        self.password_entry.focus_set()
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(20, 10), fill="x", padx=25)
        
        btn_text = "Save" if setup_mode else "Unlock"
        ctk.CTkButton(btn_frame, text=btn_text, width=155, command=self._on_submit).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Cancel", width=155, fg_color=("gray70", "gray30"), command=self._on_cancel).pack(side="right")
        
        self.bind("<Return>", lambda _e: self._on_submit())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.wait_window()
        
    def _on_submit(self):
        passwd = self.password_entry.get().strip()
        if not passwd:
            return
        self.result = passwd
        self.destroy()
        
    def _on_cancel(self):
        self.destroy()
