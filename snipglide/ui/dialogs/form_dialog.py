import customtkinter as ctk

class FormDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Fill-in Form", fields: list[str] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.entries = {}
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 225
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text="Please fill in the fields below:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=15, padx=25, anchor="w")
        
        scroll_frame = ctk.CTkScrollableFrame(self, width=400, height=240, fg_color="transparent")
        scroll_frame.pack(padx=25, fill="both", expand=True)
        
        for field in fields or []:
            ctk.CTkLabel(scroll_frame, text=f"{field}:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            entry = ctk.CTkEntry(scroll_frame, width=370)
            entry.pack(pady=2, fill="x")
            self.entries[field] = entry
            
        if fields:
            self.entries[fields[0]].focus_set()
            
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15, fill="x", padx=25)
        
        ctk.CTkButton(btn_frame, text="Submit", width=190, command=self._on_submit).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Cancel", width=190, fg_color=("gray70", "gray30"), command=self._on_cancel).pack(side="right")
        
        self.bind("<Return>", lambda _e: self._on_submit())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.wait_window()
        
    def _on_submit(self):
        self.result = {field: entry.get().strip() for field, entry in self.entries.items()}
        self.destroy()
        
    def _on_cancel(self):
        self.destroy()
