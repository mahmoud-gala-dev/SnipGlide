import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, select_callback, **kwargs):
        super().__init__(parent, width=220, corner_radius=0, **kwargs)
        self.select_callback = select_callback
        
        self.grid_propagate(False)
        
        ctk.CTkLabel(self, text="SnipGlide", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30, 2), padx=20)
        ctk.CTkLabel(self, text="Text Expander Pro", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 25), padx=20)
        
        self.nav_buttons = {}
        pages = [
            ("Dashboard", "📊 Dashboard"),
            ("Snippets", "📝 Snippets"),
            ("Clipboard", "📋 Clipboard"),
            ("AIAssistant", "🤖 AI Assistant"),
            ("Settings", "⚙️ Settings"),
            ("Marketplace", "🛍️ Marketplace")
        ]
        
        for page_id, label in pages:
            btn = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda p=page_id: self.select_page(p)
            )
            btn.pack(fill="x", padx=15, pady=4)
            self.nav_buttons[page_id] = btn
            
        self.select_page("Dashboard")
        
    def select_page(self, page_id: str):
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=("#2563eb", "#1d4ed8"), text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("black", "white"))
        self.select_callback(page_id)
