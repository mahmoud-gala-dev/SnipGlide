import customtkinter as ctk


class Toolbar(ctk.CTkFrame):
    def __init__(self, parent, callbacks: dict, **kwargs):
        super().__init__(parent, height=84, corner_radius=10, **kwargs)
        self.callbacks = callbacks

        self.grid_columnconfigure(0, weight=1)

        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        actions = [
            ("new", "+", "New", "#2563eb", "#1d4ed8"),
            ("run_background", "H", "Hide", "#7c3aed", "#5b21b6"),
            ("import_xlsx", "XI", "Imp Excel", "#16a34a", "#15803d"),
            ("export_xlsx", "XO", "Exp Excel", "#059669", "#047857"),
            ("template", "T", "Template", "#f59e0b", "#d97706"),
            ("import_yaml", "YI", "Imp YAML", "#0ea5e9", "#0284c7"),
            ("export_yaml", "YO", "Exp YAML", "#06b6d4", "#0891b2"),
            ("backup_json", "B", "Backup", "#64748b", "#475569"),
            ("restore_json", "R", "Restore", "#ef4444", "#dc2626"),
        ]

        for column, (act_id, icon, label, fg, hover) in enumerate(actions):
            btn = self._make_action_button(actions_frame, icon, label, fg, hover, self.callbacks.get(act_id))
            btn.grid(row=0, column=column, padx=4, pady=0)

        zoom_frame = ctk.CTkFrame(self, fg_color="transparent")
        zoom_frame.grid(row=0, column=1, sticky="e", padx=10, pady=10)

        for column, (label, callback_name, width) in enumerate(
            [
                ("-", "zoom_out", 38),
                ("100", "zoom_reset", 54),
                ("+", "zoom_in", 38),
            ]
        ):
            btn = ctk.CTkButton(
                zoom_frame,
                text=label,
                width=width,
                height=44,
                fg_color=("#e5e7eb", "#374151"),
                hover_color=("#d1d5db", "#4b5563"),
                text_color=("black", "white"),
                font=ctk.CTkFont(size=15, weight="bold"),
                command=self.callbacks.get(callback_name),
            )
            btn.grid(row=0, column=column, padx=3)

    def _make_action_button(self, parent, icon: str, label: str, fg: str, hover: str, command):
        button = ctk.CTkButton(
            parent,
            text=f"{icon}  {label}",
            width=104,
            height=44,
            fg_color=fg,
            hover_color=hover,
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
            command=command,
        )
        return button
