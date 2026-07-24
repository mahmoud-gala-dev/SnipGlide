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
            ("Marketplace", "🛍 Marketplace")
        ]
        
        for page_id, label in pages:
            btn = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray78", "gray30"),
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda p=page_id: self.select_page(p),
                corner_radius=8,
            )
            btn.pack(fill="x", padx=(2, 15), pady=2)
            self.nav_buttons[page_id] = btn
            
        self.select_page("Dashboard")
        
    def select_page(self, page_id: str):
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=("#2563eb", "#1d4ed8"), text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("black", "white"))
        self.select_callback(page_id)

    def set_sidebar_font_size(self, size: int):
        """Adjust font size for all navigation buttons in the sidebar."""
        for btn in self.nav_buttons.values():
            current_font = btn.cget("font")
            try:
                weight = "bold" if "bold" in str(current_font).lower() else None
            except Exception:
                weight = None
            btn.configure(font=ctk.CTkFont(size=size, weight=weight))

    def apply_sidebar_direction(self, direction: str):
        """Set text direction for sidebar buttons based on RTL/LTR setting."""
        anchor = "e" if direction.lower() == "rtl" else "w"
        for btn in self.nav_buttons.values():
            btn.configure(anchor=anchor)
