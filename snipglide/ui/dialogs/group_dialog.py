import customtkinter as ctk

class GroupDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Add Group", initial_name="", initial_icon="📁", initial_color="#2563eb", initial_desc=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 160
        self.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(self, text="Group Name:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 2), anchor="w", padx=25)
        self.name_entry = ctk.CTkEntry(self, width=350)
        self.name_entry.pack(padx=25, pady=2)
        self.name_entry.insert(0, initial_name)
        self.name_entry.focus_set()
        
        row_frame = ctk.CTkFrame(self, fg_color="transparent")
        row_frame.pack(padx=25, pady=10, fill="x")
        
        icon_sub = ctk.CTkFrame(row_frame, fg_color="transparent")
        icon_sub.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(icon_sub, text="Icon/Emoji:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.icons = ["📁", "💼", "👤", "💻", "🔑", "⚡", "📝", "🎨", "🌐", "🛠️", "⭐", "📅", "💬"]
        self.icon_var = ctk.StringVar(value=initial_icon)
        self.icon_menu = ctk.CTkOptionMenu(icon_sub, variable=self.icon_var, values=self.icons, width=160)
        self.icon_menu.pack(pady=2)
        
        color_sub = ctk.CTkFrame(row_frame, fg_color="transparent")
        color_sub.pack(side="right", fill="x", expand=True)
        ctk.CTkLabel(color_sub, text="Color Hex:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.colors = ["#2563eb", "#10b981", "#ef4444", "#f59e0b", "#8b5cf6", "#ec4899", "#6b7280"]
        self.color_var = ctk.StringVar(value=initial_color)
        self.color_menu = ctk.CTkOptionMenu(color_sub, variable=self.color_var, values=self.colors, width=160)
        self.color_menu.pack(pady=2)
        
        ctk.CTkLabel(self, text="Description:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=25)
        self.desc_entry = ctk.CTkEntry(self, width=350)
        self.desc_entry.pack(padx=25, pady=2)
        self.desc_entry.insert(0, initial_desc)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=25)
        
        ctk.CTkButton(btn_frame, text="Save", width=165, command=self._on_save).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Cancel", width=165, fg_color=("gray70", "gray30"), command=self._on_cancel).pack(side="right")
        
        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.wait_window()
        
    def _on_save(self):
        name = self.name_entry.get().strip()
        if not name:
            return
        self.result = {
            "name": name,
            "icon": self.icon_var.get(),
            "color": self.color_var.get(),
            "description": self.desc_entry.get().strip()
        }
        self.destroy()
        
    def _on_cancel(self):
        self.destroy()
