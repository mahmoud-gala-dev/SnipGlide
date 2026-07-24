import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, select_callback, **kwargs):
        super().__init__(parent, width=220, corner_radius=0, **kwargs)
        self.select_callback = select_callback

        self.grid_propagate(False)

        ctk.CTkLabel(self, text="SnipGlide", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(30, 2), padx=20)
        ctk.CTkLabel(self, text="Text Expander Pro", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 25), padx=20)

        self.nav_buttons = {}
        self.nav_icons = {}
        self.nav_rows = {}
        self.selected_page_id = None
        pages = [
            ("Dashboard", "Dashboard", "#2563eb"),
            ("Snippets", "Snippets", "#16a34a"),
            ("Notes", "Notes", "#f59e0b"),
            ("Search", "Search", "#14b8a6"),
            ("Clipboard", "Clipboard", "#06b6d4"),
            ("AIAssistant", "AI Assistant", "#8b5cf6"),
            ("Settings", "Settings", "#64748b"),
            ("Health", "Health", "#0f766e"),
            ("Marketplace", "Marketplace", "#ef4444"),
        ]

        for page_id, label, color in pages:
            row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8)
            row.pack(fill="x", padx=(2, 15), pady=2)
            row.grid_columnconfigure(1, weight=1)

            icon = ctk.CTkFrame(row, width=12, height=12, corner_radius=3, fg_color=color)
            icon.grid(row=0, column=0, padx=(12, 8), pady=14)
            icon.grid_propagate(False)

            btn = ctk.CTkButton(
                row,
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
            btn.grid(row=0, column=1, sticky="ew")
            row.bind("<Button-1>", lambda _e, p=page_id: self.select_page(p))
            icon.bind("<Button-1>", lambda _e, p=page_id: self.select_page(p))

            self.nav_buttons[page_id] = btn
            self.nav_icons[page_id] = icon
            self.nav_rows[page_id] = row

        self.select_page("Dashboard")

    def select_page(self, page_id: str):
        if self.selected_page_id == page_id:
            return

        self.selected_page_id = page_id
        for pid, btn in self.nav_buttons.items():
            row = self.nav_rows[pid]
            if pid == page_id:
                row.configure(fg_color=("#dbeafe", "#172554"))
                btn.configure(fg_color="transparent", text_color=("#1d4ed8", "#bfdbfe"))
            else:
                row.configure(fg_color="transparent")
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
        is_rtl = direction.lower() == "rtl"
        anchor = "e" if is_rtl else "w"
        for btn in self.nav_buttons.values():
            btn.configure(anchor=anchor)
