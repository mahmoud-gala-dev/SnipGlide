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
        
        self._build_general_tab()
        self._build_engine_tab()
        self._build_security_tab()
        self._build_ai_tab()
        
        self.save_btn = ctk.CTkButton(self, text="Save Settings", command=self._save_all, height=35)
        self.save_btn.pack(pady=20, anchor="e", padx=20)
        
    def _build_general_tab(self):
        tab = self.tabview.tab("General")
        
        self.start_min_switch = ctk.CTkSwitch(tab, text="Start Minimized")
        self.start_min_switch.pack(pady=15, anchor="w", padx=20)
        if self.settings_dict.get("start_minimized", False):
            self.start_min_switch.select()
            
        ctk.CTkLabel(tab, text="Max buffer length (keys tracked):").pack(pady=(15, 2), anchor="w", padx=20)
        self.max_buffer_entry = ctk.CTkEntry(tab, width=200)
        self.max_buffer_entry.pack(pady=2, anchor="w", padx=20)
        self.max_buffer_entry.insert(0, str(self.settings_dict.get("max_buffer", 250)))
        
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
        
        self.settings_dict["enabled"] = bool(self.engine_enabled_switch.get())
        self.settings_dict["case_sensitive"] = bool(self.case_sensitive_switch.get())
        
        self.settings_dict["master_password_enabled"] = bool(self.security_enabled_switch.get())
        self.settings_dict["lock_on_startup"] = bool(self.lock_startup_switch.get())
        
        self.settings_dict["ai_provider"] = self.ai_provider_var.get()
        self.settings_dict["ai_api_key"] = self.ai_key_entry.get().strip()
        
        self.save_callback()
