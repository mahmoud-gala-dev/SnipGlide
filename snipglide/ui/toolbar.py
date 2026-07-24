import customtkinter as ctk

class Toolbar(ctk.CTkFrame):
    def __init__(self, parent, callbacks: dict, **kwargs):
        super().__init__(parent, height=50, corner_radius=8, **kwargs)
        self.callbacks = callbacks
        
        actions = [
            ("new", "➕ New", "primary"),
            ("import_xlsx", "📥 Imp Excel", "secondary"),
            ("export_xlsx", "📤 Exp Excel", "secondary"),
            ("template", "📁 Excel Temp", "secondary"),
            ("import_yaml", "📥 Imp YAML", "secondary"),
            ("export_yaml", "📤 Exp YAML", "secondary"),
            ("backup_json", "📤 Backup All", "secondary"),
            ("restore_json", "📥 Restore All", "secondary"),
        ]
        
        for act_id, label, style in actions:
            fg = ("#2563eb", "#1d4ed8") if style == "primary" else ("gray75", "gray25")
            text_color = "white" if style == "primary" else ("black", "white")
            
            btn = ctk.CTkButton(
                self,
                text=label,
                width=95,
                height=32,
                fg_color=fg,
                text_color=text_color,
                font=ctk.CTkFont(size=11, weight="bold" if style == "primary" else "normal"),
                command=self.callbacks.get(act_id)
            )
            btn.pack(side="left", padx=4, pady=8)
