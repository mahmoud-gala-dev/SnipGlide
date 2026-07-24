import customtkinter as ctk
from tkinter import filedialog

from snipglide.services.maintenance import (
    export_full_package,
    export_sync_copy,
    get_health_report,
    import_full_package,
    optimize_database,
    read_log_tail,
)


class HealthPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, settings_provider, save_settings_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.settings_provider = settings_provider
        self.save_settings_callback = save_settings_callback

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Health & Tools", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 10)
        )

        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=(0, 20))
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 20), pady=(0, 20))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self.health_text = ctk.CTkTextbox(left, height=220, wrap="word")
        self.health_text.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        buttons = ctk.CTkFrame(left, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        ctk.CTkButton(buttons, text="Refresh", command=self.refresh_health).pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Optimize DB", command=self._optimize_database).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Optimize + Clear Clipboard", command=self._optimize_and_clear).pack(side="left", padx=6)

        package_buttons = ctk.CTkFrame(left, fg_color="transparent")
        package_buttons.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(package_buttons, text="Export Full Package", command=self._export_package).pack(side="left", padx=(0, 6))
        ctk.CTkButton(package_buttons, text="Import Full Package", command=self._import_package).pack(side="left", padx=6)

        sync_frame = ctk.CTkFrame(left, fg_color="transparent")
        sync_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        sync_frame.grid_columnconfigure(0, weight=1)
        self.sync_entry = ctk.CTkEntry(sync_frame, placeholder_text="Local sync folder, e.g. OneDrive\\SnipGlide")
        self.sync_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.sync_entry.insert(0, self.settings_provider().get("sync_path", ""))
        ctk.CTkButton(sync_frame, text="Browse", width=80, command=self._browse_sync_folder).grid(row=0, column=1, padx=4)
        ctk.CTkButton(sync_frame, text="Sync Now", width=90, command=self._sync_now).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(right, text="Application Log", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        self.log_text = ctk.CTkTextbox(right, wrap="none")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        ctk.CTkButton(right, text="Refresh Log", command=self.refresh_log).grid(row=2, column=0, sticky="e", padx=12, pady=(0, 12))

        self.refresh_health()
        self.refresh_log()

    def refresh_health(self):
        report = get_health_report()
        lines = [
            f"Database: {report['database_path']}",
            f"Database size: {report['database_size_kb']} KB",
            f"Integrity: {report['integrity']}",
            f"Last backup: {report['last_backup']}",
            "",
            "Counts:",
        ]
        for key, value in report["counts"].items():
            lines.append(f"- {key}: {value}")

        self.health_text.delete("1.0", "end")
        self.health_text.insert("1.0", "\n".join(lines))

    def refresh_log(self):
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", read_log_tail())

    def _optimize_database(self):
        result = optimize_database(clear_clipboard=False)
        self.refresh_health()
        self.toast_callback(f"Optimized DB: {result['before_kb']} KB -> {result['after_kb']} KB")

    def _optimize_and_clear(self):
        result = optimize_database(clear_clipboard=True)
        self.refresh_health()
        self.toast_callback(f"Optimized and cleared clipboard: {result['before_kb']} KB -> {result['after_kb']} KB")

    def _export_package(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path and export_full_package(path):
            self.toast_callback("Full package exported.")
        elif path:
            self.toast_callback("Export failed.", error=True)

    def _import_package(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path and import_full_package(path):
            self.toast_callback("Full package imported. Restart recommended.")
            self.refresh_health()
        elif path:
            self.toast_callback("Import failed.", error=True)

    def _browse_sync_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.sync_entry.delete(0, "end")
            self.sync_entry.insert(0, folder)

    def _sync_now(self):
        folder = self.sync_entry.get().strip()
        if not folder:
            self.toast_callback("Choose a sync folder first.", error=True)
            return

        settings = self.settings_provider()
        settings["sync_enabled"] = True
        settings["sync_path"] = folder
        self.save_settings_callback()

        try:
            target = export_sync_copy(folder)
            self.toast_callback(f"Sync package saved: {target}")
        except Exception as e:
            self.toast_callback(str(e), error=True)
