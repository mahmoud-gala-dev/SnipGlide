import customtkinter as ctk
from snipglide.ui.dialogs.security_dialog import SecurityDialog
from snipglide.services.security import hash_password

class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, settings_dict: dict, save_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.settings_dict = settings_dict
        self.save_callback = save_callback
        
        self.title_label = ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10), anchor="w", padx=20)
        
        self.tabview = ctk.CTkTabview(self, width=600)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tabview.add("General")
        self.tabview.add("Engine")
        self.tabview.add("Security")
        self.tabview.add("AI Configuration")
        self.tabview.add("Autocorrect")
        
        self._build_general_tab()
        self._build_engine_tab()
        self._build_security_tab()
        self._build_ai_tab()
        self._build_autocorrect_tab()
        
        self.save_btn = ctk.CTkButton(self, text="Save Settings", command=self._save_all, height=35)
        self.save_btn.pack(pady=20, anchor="e", padx=20)
        
    def _build_general_tab(self):
        tab = self.tabview.tab("General")
        
        self.start_min_switch = ctk.CTkSwitch(tab, text="Start Minimized")
        self.start_min_switch.pack(pady=10, anchor="w", padx=20)
        if self.settings_dict.get("start_minimized", False):
            self.start_min_switch.select()
            
        self.play_sound_switch = ctk.CTkSwitch(tab, text="Play sound on trigger expansion")
        self.play_sound_switch.pack(pady=10, anchor="w", padx=20)
        if self.settings_dict.get("play_sound", True):
            self.play_sound_switch.select()
            
        self.start_on_boot_switch = ctk.CTkSwitch(tab, text="Launch automatically on Windows Startup")
        self.start_on_boot_switch.pack(pady=10, anchor="w", padx=20)

        # Sidebar Font Size
        ctk.CTkLabel(tab, text="Sidebar Font Size:").pack(pady=(12, 2), anchor="w", padx=20)
        self.sidebar_font_size_slider = ctk.CTkSlider(tab, from_=10, to=20, number_of_steps=10)
        self.sidebar_font_size_slider.set(self.settings_dict.get("sidebar_font_size", 13))
        self.sidebar_font_size_slider.pack(pady=2, anchor="w", padx=20)

        # Sidebar RTL Direction
        self.sidebar_rtl_switch = ctk.CTkSwitch(tab, text="Sidebar RTL Direction")
        self.sidebar_rtl_switch.pack(pady=10, anchor="w", padx=20)
        if self.settings_dict.get("sidebar_direction", "ltr") == "rtl":
            self.sidebar_rtl_switch.select()
        if self.settings_dict.get("start_on_boot", False):
            self.start_on_boot_switch.select()
            
        ctk.CTkLabel(tab, text="Max buffer length (keys tracked):").pack(pady=(12, 2), anchor="w", padx=20)
        self.max_buffer_entry = ctk.CTkEntry(tab, width=200)
        self.max_buffer_entry.pack(pady=2, anchor="w", padx=20)
        self.max_buffer_entry.insert(0, str(self.settings_dict.get("max_buffer", 250)))
        
        ctk.CTkLabel(tab, text="Color Theme Mode:").pack(pady=(12, 2), anchor="w", padx=20)
        self.theme_var = ctk.StringVar(value=self.settings_dict.get("theme", "System"))
        self.theme_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.theme_var,
            values=["System", "Dark", "Light"],
            width=200,
            command=self._on_theme_change
        )
        self.theme_menu.pack(pady=2, anchor="w", padx=20)
        
        ctk.CTkLabel(tab, text="Database Maintenance & Backups:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5), anchor="w", padx=20)
        
        backup_frame = ctk.CTkFrame(tab, fg_color="transparent")
        backup_frame.pack(pady=5, anchor="w", padx=20)
        
        self.export_btn = ctk.CTkButton(backup_frame, text="📤 Export Full Backup", command=self._export_db_backup, width=160)
        self.export_btn.pack(side="left", padx=(0, 10))
        
        self.import_btn = ctk.CTkButton(backup_frame, text="📥 Import Backup", command=self._import_db_backup, width=160, fg_color=("gray75", "gray35"), text_color=("black", "white"))
        self.import_btn.pack(side="left")
        
    def _build_engine_tab(self):
        tab = self.tabview.tab("Engine")
        
        self.engine_enabled_switch = ctk.CTkSwitch(tab, text="Enable Snippet Replacement")
        self.engine_enabled_switch.pack(pady=15, anchor="w", padx=20)
        if self.settings_dict.get("enabled", True):
            self.engine_enabled_switch.select()
            
        self.case_sensitive_switch = ctk.CTkSwitch(tab, text="Case Sensitive Matching")
        self.case_sensitive_switch.pack(pady=15, anchor="w", padx=20)
        if self.settings_dict.get("case_sensitive", True):
            self.case_sensitive_switch.select()
            
        ctk.CTkLabel(tab, text="Application Blacklist (comma-separated executables):").pack(pady=(15, 2), anchor="w", padx=20)
        self.blacklist_entry = ctk.CTkEntry(tab, width=350)
        self.blacklist_entry.pack(pady=2, anchor="w", padx=20)
        self.blacklist_entry.insert(0, str(self.settings_dict.get("blacklist", "")))
            
    def _build_security_tab(self):
        tab = self.tabview.tab("Security")
        
        self.security_enabled_switch = ctk.CTkSwitch(tab, text="Enable Master Password Protection", command=self._toggle_master_password)
        self.security_enabled_switch.pack(pady=15, anchor="w", padx=20)
        if self.settings_dict.get("master_password_enabled", False):
            self.security_enabled_switch.select()
            
        self.lock_startup_switch = ctk.CTkSwitch(tab, text="Lock Application on Startup")
        self.lock_startup_switch.pack(pady=15, anchor="w", padx=20)
        if self.settings_dict.get("lock_on_startup", False):
            self.lock_startup_switch.select()
            
        self.change_pwd_btn = ctk.CTkButton(tab, text="Set / Change Master Password", fg_color="transparent", border_width=1, command=self._set_master_password)
        self.change_pwd_btn.pack(pady=15, anchor="w", padx=20)
        
    def _build_ai_tab(self):
        tab = self.tabview.tab("AI Configuration")
        
        ctk.CTkLabel(tab, text="AI API Provider:").pack(pady=(15, 2), anchor="w", padx=20)
        self.ai_provider_var = ctk.StringVar(value=self.settings_dict.get("ai_provider", "gemini"))
        self.ai_provider_menu = ctk.CTkOptionMenu(tab, variable=self.ai_provider_var, values=["gemini", "openai"], width=200)
        self.ai_provider_menu.pack(pady=2, anchor="w", padx=20)
        
        ctk.CTkLabel(tab, text="AI Secret API Key:").pack(pady=(15, 2), anchor="w", padx=20)
        self.ai_key_entry = ctk.CTkEntry(tab, show="*", width=350)
        self.ai_key_entry.pack(pady=2, anchor="w", padx=20)
        self.ai_key_entry.insert(0, self.settings_dict.get("ai_api_key", ""))
        
        self.test_key_btn = ctk.CTkButton(
            tab,
            text="⚡ Test Connection",
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            command=self._test_api_connection
        )
        self.test_key_btn.pack(pady=15, anchor="w", padx=20)
        
        ctk.CTkLabel(tab, text="AI Temperature (0.0 = Precise, 1.0 = Creative):").pack(pady=(10, 2), anchor="w", padx=20)
        self.ai_temp_var = ctk.DoubleVar(value=float(self.settings_dict.get("ai_temperature", 0.7)))
        
        slider_frame = ctk.CTkFrame(tab, fg_color="transparent")
        slider_frame.pack(pady=2, anchor="w", padx=20, fill="x")
        
        self.ai_temp_slider = ctk.CTkSlider(slider_frame, from_=0.0, to=1.0, number_of_steps=10, variable=self.ai_temp_var, width=250, command=self._on_temp_slider_change)
        self.ai_temp_slider.pack(side="left")
        
        self.ai_temp_val_lbl = ctk.CTkLabel(slider_frame, text=f"{self.ai_temp_var.get():.1f}")
        self.ai_temp_val_lbl.pack(side="left", padx=10)
        
    def _toggle_master_password(self):
        enabled = bool(self.security_enabled_switch.get())
        if enabled and not self.settings_dict.get("master_password_hash"):
            self._set_master_password()
            if not self.settings_dict.get("master_password_hash"):
                self.security_enabled_switch.deselect()
                
    def _set_master_password(self):
        dialog = SecurityDialog(self, title="Set Master Password", setup_mode=True)
        if dialog.result:
            pwd_hash = hash_password(dialog.result)
            self.settings_dict["master_password_hash"] = pwd_hash
            self.settings_dict["master_password_enabled"] = True
            self.security_enabled_switch.select()
            
    def _save_all(self):
        self.settings_dict["start_minimized"] = bool(self.start_min_switch.get())
        self.settings_dict["max_buffer"] = int(self.max_buffer_entry.get().strip() or "250")

        self.settings_dict["play_sound"] = bool(self.play_sound_switch.get())

        boot_changed = bool(self.start_on_boot_switch.get()) != self.settings_dict.get("start_on_boot", False)
        self.settings_dict["start_on_boot"] = bool(self.start_on_boot_switch.get())
        if boot_changed:
            from snipglide.services.startup import set_autostart
            set_autostart(self.settings_dict["start_on_boot"])

        self.settings_dict["enabled"] = bool(self.engine_enabled_switch.get())
        self.settings_dict["case_sensitive"] = bool(self.case_sensitive_switch.get())
        self.settings_dict["blacklist"] = self.blacklist_entry.get().strip()
        self.settings_dict["theme"] = self.theme_var.get()

        # Sidebar custom settings
        self.settings_dict["sidebar_font_size"] = int(self.sidebar_font_size_slider.get())
        self.settings_dict["sidebar_direction"] = "rtl" if self.sidebar_rtl_switch.get() else "ltr"

        self.settings_dict["master_password_enabled"] = bool(self.security_enabled_switch.get())
        self.settings_dict["lock_on_startup"] = bool(self.lock_startup_switch.get())

        self.settings_dict["ai_provider"] = self.ai_provider_var.get()
        self.settings_dict["ai_api_key"] = self.ai_key_entry.get().strip()
        self.settings_dict["ai_temperature"] = float(self.ai_temp_var.get())

        self.save_callback()

    def _test_api_connection(self):
        api_key = self.ai_key_entry.get().strip()
        provider = self.ai_provider_var.get()
        
        if not api_key:
            self._show_info_popup("AI Connection Test", "API Key field is empty.", error=True)
            return
            
        self.test_key_btn.configure(state="disabled", text="Testing...")
        
        def run():
            from snipglide.services.ai import test_ai_key
            success, msg = test_ai_key(api_key, provider)
            self.after(0, lambda: self.test_key_btn.configure(state="normal", text="⚡ Test Connection"))
            self.after(0, lambda: self._show_info_popup("AI Connection Test", msg, error=not success))
            
        import threading
        threading.Thread(target=run, daemon=True).start()

    def _show_info_popup(self, title: str, message: str, error: bool = False):
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("380x180")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        
        popup.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 190
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 90
        popup.geometry(f"+{x}+{y}")
        
        color = "#dc2626" if error else "#16a34a"
        icon_text = "❌ Connection Failed" if error else "✅ Connection Success"
        
        ctk.CTkLabel(popup, text=icon_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=color).pack(pady=(20, 10))
        
        msg_lbl = ctk.CTkLabel(popup, text=message, wraplength=320, justify="center")
        msg_lbl.pack(pady=10, fill="both", expand=True)
        
        ok_btn = ctk.CTkButton(popup, text="OK", width=100, command=popup.destroy)
        ok_btn.pack(pady=(5, 15))

    def _on_theme_change(self, mode: str):
        ctk.set_appearance_mode(mode)

    def _export_db_backup(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if not path:
            return
        from snipglide.services.maintenance import export_full_package
        if export_full_package(path):
            self._show_info_popup("Export Backup", "Full backup exported successfully.", error=False)
        else:
            self._show_info_popup("Export Backup", "Failed to export backup. Check logs for details.", error=True)

    def _import_db_backup(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not path:
            return
        from snipglide.services.maintenance import import_full_package
        if import_full_package(path):
            self._show_info_popup("Import Backup", "Full backup imported successfully. Please restart the application to reload changes.", error=False)
        else:
            self._show_info_popup("Import Backup", "Failed to import backup. Verify file schema.", error=True)

    def _on_temp_slider_change(self, val):
        self.ai_temp_val_lbl.configure(text=f"{float(val):.1f}")

    def _build_autocorrect_tab(self):
        tab = self.tabview.tab("Autocorrect")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        add_frame = ctk.CTkFrame(tab, fg_color="transparent")
        add_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        ctk.CTkLabel(add_frame, text="Add New Correction", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(add_frame, text="Typo (misspelled word):").pack(anchor="w", pady=(5, 2))
        self.typo_entry = ctk.CTkEntry(add_frame, placeholder_text="e.g. teh", width=220)
        self.typo_entry.pack(anchor="w", pady=2)
        
        ctk.CTkLabel(add_frame, text="Correction (correct word):").pack(anchor="w", pady=(10, 2))
        self.correction_entry = ctk.CTkEntry(add_frame, placeholder_text="e.g. the", width=220)
        self.correction_entry.pack(anchor="w", pady=2)
        
        self.add_correct_btn = ctk.CTkButton(add_frame, text="➕ Add Mapping", command=self._add_autocorrect_mapping, width=220)
        self.add_correct_btn.pack(anchor="w", pady=15)
        
        from snipglide.utils.helpers import create_context_menu
        create_context_menu(self.typo_entry)
        create_context_menu(self.correction_entry)
        
        list_frame = ctk.CTkFrame(tab, fg_color="transparent")
        list_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(list_frame, text="Current Corrections Mappings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        self.autocorrect_scroll = ctk.CTkScrollableFrame(list_frame, height=220)
        self.autocorrect_scroll.grid(row=1, column=0, sticky="nsew")
        
        self._refresh_autocorrect_list()
        
    def _refresh_autocorrect_list(self):
        for widget in self.autocorrect_scroll.winfo_children():
            widget.destroy()
            
        from snipglide.database.autocorrect_repo import get_all_corrections
        try:
            corrections = get_all_corrections()
        except Exception:
            corrections = {}
            
        if not corrections:
            ctk.CTkLabel(self.autocorrect_scroll, text="No corrections defined.", text_color="gray").pack(pady=20)
            return
            
        for typo, correction in corrections.items():
            row = ctk.CTkFrame(self.autocorrect_scroll, fg_color=("gray85", "gray20"))
            row.pack(fill="x", pady=3, padx=2)
            
            lbl = ctk.CTkLabel(row, text=f"{typo} ➡️ {correction}", anchor="w", font=ctk.CTkFont(size=11))
            lbl.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            
            del_btn = ctk.CTkButton(
                row,
                text="🗑️",
                width=24,
                height=24,
                fg_color="#dc2626",
                hover_color="#b91c1c",
                command=lambda t=typo: self._delete_autocorrect_mapping(t)
            )
            del_btn.pack(side="right", padx=5)
            
    def _add_autocorrect_mapping(self):
        typo = self.typo_entry.get().strip().lower()
        correction = self.correction_entry.get().strip()
        
        if not typo or not correction:
            return
            
        from snipglide.database.autocorrect_repo import add_autocorrect
        try:
            add_autocorrect(typo, correction)
            self.typo_entry.delete(0, "end")
            self.correction_entry.delete(0, "end")
            self._refresh_autocorrect_list()
        except Exception as e:
            from snipglide.utils.logger import logger
            logger.error(f"Failed to add autocorrect: {e}")
            
    def _delete_autocorrect_mapping(self, typo: str):
        from snipglide.database.autocorrect_repo import delete_autocorrect
        try:
            delete_autocorrect(typo)
            self._refresh_autocorrect_list()
        except Exception as e:
            from snipglide.utils.logger import logger
            logger.error(f"Failed to delete autocorrect: {e}")
