import customtkinter as ctk
import openpyxl
from snipglide.ui.sidebar import Sidebar
from snipglide.ui.toolbar import Toolbar
from snipglide.ui.dashboard import Dashboard
from snipglide.ui.snippet_editor_view import SnippetEditorView
from snipglide.ui.settings_page import SettingsPage
from snipglide.ui.marketplace import Marketplace
from snipglide.ui.clipboard_history_page import ClipboardHistoryPage
from snipglide.ui.ai_assistant_page import AIAssistantPage
from snipglide.core.config import load_settings, save_settings, APP_NAME
from snipglide.database.snippet_repo import get_all_snippets
from snipglide.services.backup import (
    export_to_excel, import_from_excel, export_to_yaml, import_from_yaml,
    export_to_json, import_from_json
)
from tkinter import filedialog
import os

class MainWindow(ctk.CTk):
    def __init__(self, engine_toggle_callback, **kwargs):
        super().__init__(**kwargs)
        self.engine_toggle_callback = engine_toggle_callback
        self.settings = load_settings()
        
        self.title(APP_NAME)
        self.geometry("1100x700")
        self.minsize(980, 600)
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Initialize attributes first to prevent callback crashes
        self.active_page = None
        self.pages = {}
        
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.grid(row=0, column=1, sticky="nsew")
        self.right_container.grid_columnconfigure(0, weight=1)
        self.right_container.grid_rowconfigure(1, weight=1)
        
        toolbar_callbacks = {
            "new": self._trigger_new_snippet,
            "import_xlsx": self._import_xlsx,
            "export_xlsx": self._export_xlsx,
            "template": self._download_template,
            "import_yaml": self._import_yaml,
            "export_yaml": self._export_yaml,
            "backup_json": self._backup_json,
            "restore_json": self._restore_json,
        }
        self.toolbar = Toolbar(self.right_container, callbacks=toolbar_callbacks)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        
        self.content_frame = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 15))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        self.pages["Dashboard"] = Dashboard(self.content_frame)
        self.pages["Snippets"] = SnippetEditorView(self.content_frame, toast_callback=self.toast, settings_provider=self.get_settings)
        self.pages["Settings"] = SettingsPage(self.content_frame, settings_dict=self.settings, save_callback=self._save_settings)
        self.pages["Marketplace"] = Marketplace(self.content_frame, toast_callback=self.toast, refresh_callback=self._refresh_all_views)
        self.pages["Clipboard"] = ClipboardHistoryPage(self.content_frame, toast_callback=self.toast, navigate_to_snippet_callback=self._navigate_to_snippet)
        self.pages["AIAssistant"] = AIAssistantPage(self.content_frame, toast_callback=self.toast, settings_provider=self.get_settings, refresh_callback=self._refresh_all_views)
        
        # Create and place Sidebar after pages are configured
        self.sidebar = Sidebar(self, select_callback=self.switch_page)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
    def get_settings(self) -> dict:
        return self.settings
        
    def switch_page(self, page_id: str):
        if self.active_page:
            self.active_page.grid_forget()
            
        page = self.pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")
        self.active_page = page
        
        if page_id == "Dashboard":
            self.pages["Dashboard"].refresh_stats()
        elif page_id == "Clipboard":
            self.pages["Clipboard"].refresh_history()
            
    def toast(self, message: str, error: bool = False):
        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        color = "#dc2626" if error else "#16a34a"
        label = ctk.CTkLabel(
            popup,
            text=message,
            fg_color=color,
            text_color="white",
            corner_radius=8,
            padx=15,
            pady=8,
        )
        label.pack()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() - 320
        y = self.winfo_y() + 45
        popup.geometry(f"+{x}+{y}")
        popup.after(1800, popup.destroy)
        
    def _save_settings(self):
        save_settings(self.settings)
        self.engine_toggle_callback()
        self.toast("Settings saved successfully!")
        
    def _refresh_all_views(self):
        self.pages["Snippets"].update_group_dropdowns()
        self.pages["Snippets"].refresh_list()
        
    def _trigger_new_snippet(self):
        self.switch_page("Snippets")
        self.sidebar.select_page("Snippets")
        self.pages["Snippets"]._new_snippet()
        
    def _import_xlsx(self):
        file_path = filedialog.askopenfilename(title="Import Excel file", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                count = import_from_excel(file_path)
                self._refresh_all_views()
                self.toast(f"Imported {count} snippets.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _export_xlsx(self):
        file_path = filedialog.asksaveasfilename(title="Export Excel file", defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                export_to_excel(get_all_snippets(), file_path)
                self.toast("Export completed successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _download_template(self):
        file_path = filedialog.asksaveasfilename(title="Download Excel Template", defaultextension=".xlsx", initialfile="snipglide_template.xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Template"
                ws.append(["Shortcut", "Replacement", "Group", "Tags", "Description", "Language", "Enabled", "Favorite"])
                ws.append(["#sig", "Best regards,\n{{username}}", "Work", "tag1,tag2", "My Email signature", "Plain Text", "TRUE", "TRUE"])
                wb.save(file_path)
                self.toast("Template downloaded successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _import_yaml(self):
        file_path = filedialog.askopenfilename(title="Import YAML file", filetypes=[("YAML files", "*.yaml;*.yml")])
        if file_path:
            try:
                count = import_from_yaml(file_path)
                self._refresh_all_views()
                self.toast(f"Imported {count} snippets.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _export_yaml(self):
        file_path = filedialog.asksaveasfilename(title="Export YAML file", defaultextension=".yaml", filetypes=[("YAML files", "*.yaml")])
        if file_path:
            try:
                export_to_yaml(get_all_snippets(), file_path)
                self.toast("Export completed successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _backup_json(self):
        file_path = filedialog.asksaveasfilename(title="Backup to JSON", defaultextension=".json", initialfile="snipglide_backup.json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                export_to_json(get_all_snippets(), file_path)
                self.toast("Backup exported successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _restore_json(self):
        file_path = filedialog.askopenfilename(title="Restore from JSON", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                count = import_from_json(file_path)
                self._refresh_all_views()
                self.toast(f"Restored {count} snippets.")
            except Exception as e:
                self.toast(str(e), error=True)

    def _navigate_to_snippet(self, text: str):
        self.switch_page("Snippets")
        self.sidebar.select_page("Snippets")
        self.pages["Snippets"]._new_snippet()
        self.pages["Snippets"].editor.set_text(text)
