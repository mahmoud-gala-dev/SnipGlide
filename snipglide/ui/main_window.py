import customtkinter as ctk
from snipglide.ui.sidebar import Sidebar
from snipglide.ui.toolbar import Toolbar
from snipglide.core.config import load_settings, save_settings, APP_NAME
from tkinter import filedialog

class MainWindow(ctk.CTk):
    def __init__(self, engine_toggle_callback, snippets_changed_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.engine_toggle_callback = engine_toggle_callback
        self.snippets_changed_callback = snippets_changed_callback
        self.settings = load_settings()
        
        self.title(APP_NAME)
        self.geometry("1280x760")
        self.minsize(1180, 680)
        
        # Store current zoom level
        self._zoom_level = float(self.settings.get("ui_zoom", 1.0))
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Initialize attributes first to prevent callback crashes
        self.active_page = None
        self.pages = {}
        self.page_order = ["Dashboard", "Snippets", "Notes", "ChatNotes", "Search", "Clipboard", "AIAssistant", "Settings", "Health", "Marketplace"]
        
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.grid(row=0, column=1, sticky="nsew")
        self.right_container.grid_columnconfigure(0, weight=1)
        self.right_container.grid_rowconfigure(1, weight=1)
        
        toolbar_callbacks = {
            "new": self._trigger_new_snippet,
            "run_background": self._run_in_background,
            "import_xlsx": self._import_xlsx,
            "export_xlsx": self._export_xlsx,
            "template": self._download_template,
            "import_yaml": self._import_yaml,
            "export_yaml": self._export_yaml,
            "backup_json": self._backup_json,
            "restore_json": self._restore_json,
            "zoom_in": self.zoom_in,
            "zoom_out": self.zoom_out,
            "zoom_reset": self.zoom_reset,
        }
        self.toolbar = Toolbar(self.right_container, callbacks=toolbar_callbacks)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        self._apply_widget_zoom(show_toast=False)
        
        self.content_frame = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(8, 15))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        self._create_pages()
        
        # Create and place Sidebar after pages are configured
        self.sidebar = Sidebar(self, select_callback=self.switch_page)
        # Apply saved sidebar customizations on startup
        self.sidebar.set_sidebar_font_size(self.settings.get("sidebar_font_size", 13))
        self.sidebar.apply_sidebar_direction(self.settings.get("sidebar_direction", "ltr"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self._bind_window_shortcuts()
        
    def get_settings(self) -> dict:
        return self.settings

    def _bind_window_shortcuts(self):
        self.bind("<Control-plus>", lambda _e: self.zoom_in())
        self.bind("<Control-equal>", lambda _e: self.zoom_in())
        self.bind("<Control-minus>", lambda _e: self.zoom_out())
        self.bind("<Control-0>", lambda _e: self.zoom_reset())
        self.bind("<Control-f>", lambda _e: self._select_page_from_shortcut("Search"))
        self.bind("<Escape>", lambda _e: self._hide_from_escape())
        for index, page_id in enumerate(self.page_order[:9], start=1):
            self.bind(f"<Control-Key-{index}>", lambda _e, p=page_id: self._select_page_from_shortcut(p))
        self.bind("<Alt-Left>", lambda _e: self._switch_relative_page(-1))
        self.bind("<Alt-Right>", lambda _e: self._switch_relative_page(1))

    def _hide_from_escape(self):
        self.withdraw()
        return "break"

    def _select_page_from_shortcut(self, page_id: str):
        self.sidebar.select_page(page_id)
        return "break"

    def _switch_relative_page(self, step: int):
        current_id = self._current_page_id()
        if current_id not in self.page_order:
            target = self.page_order[0]
        else:
            current_index = self.page_order.index(current_id)
            target = self.page_order[(current_index + step) % len(self.page_order)]
        self.sidebar.select_page(target)
        return "break"

    def _current_page_id(self):
        for page_id, page in self.pages.items():
            if page is self.active_page:
                return page_id
        return None

    def _create_pages(self):
        from snipglide.ui.dashboard import Dashboard
        from snipglide.ui.snippet_editor_view import SnippetEditorView
        from snipglide.ui.notes_page import NotesPage
        from snipglide.ui.chat_notes_page import ChatNotesPage
        from snipglide.ui.search_page import SearchPage
        from snipglide.ui.settings_page import SettingsPage
        from snipglide.ui.health_page import HealthPage
        from snipglide.ui.marketplace import Marketplace
        from snipglide.ui.clipboard_history_page import ClipboardHistoryPage
        from snipglide.ui.ai_assistant_page import AIAssistantPage

        self.pages = {
            "Dashboard": Dashboard(self.content_frame),
            "Snippets": SnippetEditorView(
                self.content_frame,
                toast_callback=self.toast,
                settings_provider=self.get_settings,
                snippets_changed_callback=self._notify_snippets_changed,
            ),
            "Notes": NotesPage(self.content_frame, toast_callback=self.toast),
            "ChatNotes": ChatNotesPage(
                self.content_frame,
                toast_callback=self.toast,
                navigate_to_snippet_callback=self._navigate_to_snippet,
            ),
            "Search": SearchPage(
                self.content_frame,
                toast_callback=self.toast,
                navigate_to_snippet_callback=self._navigate_to_snippet,
            ),
            "Settings": SettingsPage(self.content_frame, settings_dict=self.settings, save_callback=self._save_settings),
            "Health": HealthPage(
                self.content_frame,
                toast_callback=self.toast,
                settings_provider=self.get_settings,
                save_settings_callback=self._save_settings,
            ),
            "Marketplace": Marketplace(self.content_frame, toast_callback=self.toast, refresh_callback=self._refresh_all_views),
            "Clipboard": ClipboardHistoryPage(
                self.content_frame,
                toast_callback=self.toast,
                navigate_to_snippet_callback=self._navigate_to_snippet,
            ),
            "AIAssistant": AIAssistantPage(
                self.content_frame,
                toast_callback=self.toast,
                settings_provider=self.get_settings,
                refresh_callback=self._refresh_all_views,
            ),
        }
        
    def switch_page(self, page_id: str):
        if self.active_page is self.pages.get(page_id):
            return

        if self.active_page:
            self.active_page.grid_forget()
            
        page = self.pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")
        self.active_page = page
        
        if page_id == "Dashboard":
            page.refresh_stats()
        elif page_id == "Clipboard":
            page.refresh_history()
        elif page_id == "ChatNotes":
            page.refresh_chat(scroll_to_bottom=True)
            
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
        # Apply sidebar customizations after saving settings
        try:
            self.sidebar.set_sidebar_font_size(self.settings.get("sidebar_font_size", 13))
            self.sidebar.apply_sidebar_direction(self.settings.get("sidebar_direction", "ltr"))
        except Exception as e:
            from snipglide.utils.logger import logger
            logger.error(f"Failed to apply sidebar settings: {e}")
        self.engine_toggle_callback()
        self.toast("Settings saved successfully!")
        
    def _refresh_all_views(self):
        snippets_page = self.pages.get("Snippets")
        if snippets_page:
            snippets_page.update_group_dropdowns()
            snippets_page.refresh_list()
        self._notify_snippets_changed()

    def _notify_snippets_changed(self):
        if self.snippets_changed_callback:
            self.snippets_changed_callback()
        
    def _trigger_new_snippet(self):
        self.switch_page("Snippets")
        self.sidebar.select_page("Snippets")
        self.pages["Snippets"]._new_snippet()
        
    def _import_xlsx(self):
        file_path = filedialog.askopenfilename(title="Import Excel file", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                from snipglide.services.backup import import_from_excel

                count = import_from_excel(file_path)
                self._refresh_all_views()
                self.toast(f"Imported {count} snippets.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _export_xlsx(self):
        file_path = filedialog.asksaveasfilename(title="Export Excel file", defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                from snipglide.database.snippet_repo import get_all_snippets
                from snipglide.services.backup import export_to_excel

                export_to_excel(get_all_snippets(), file_path)
                self.toast("Export completed successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _download_template(self):
        file_path = filedialog.asksaveasfilename(title="Download Excel Template", defaultextension=".xlsx", initialfile="snipglide_template.xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                import openpyxl

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
                from snipglide.services.backup import import_from_yaml

                count = import_from_yaml(file_path)
                self._refresh_all_views()
                self.toast(f"Imported {count} snippets.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _export_yaml(self):
        file_path = filedialog.asksaveasfilename(title="Export YAML file", defaultextension=".yaml", filetypes=[("YAML files", "*.yaml")])
        if file_path:
            try:
                from snipglide.database.snippet_repo import get_all_snippets
                from snipglide.services.backup import export_to_yaml

                export_to_yaml(get_all_snippets(), file_path)
                self.toast("Export completed successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _backup_json(self):
        file_path = filedialog.asksaveasfilename(title="Backup to JSON", defaultextension=".json", initialfile="snipglide_backup.json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                from snipglide.services.maintenance import export_full_package

                export_full_package(file_path)
                self.toast("Backup exported successfully.")
            except Exception as e:
                self.toast(str(e), error=True)
                
    def _restore_json(self):
        file_path = filedialog.askopenfilename(title="Restore from JSON", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                from snipglide.services.maintenance import import_full_package

                import_full_package(file_path)
                self._refresh_all_views()
                self.toast("Restore completed. Restart recommended.")
            except Exception as e:
                self.toast(str(e), error=True)

    def _navigate_to_snippet(self, text: str):
        self.switch_page("Snippets")
        self.sidebar.select_page("Snippets")
        self.pages["Snippets"]._new_snippet()
        self.pages["Snippets"].editor.set_text(text)

    def _run_in_background(self):
        """Minimize the window to system tray (run in background mode)."""
        self.withdraw()
        self.toast("Running in background - Press Ctrl+Alt+Shift+S to show")

    def zoom_in(self):
        """Increase UI zoom by 10%."""
        self._zoom_level = min(round(self._zoom_level + 0.1, 2), 1.8)
        self._apply_widget_zoom()

    def zoom_out(self):
        """Decrease UI zoom by 10%."""
        self._zoom_level = max(round(self._zoom_level - 0.1, 2), 0.8)
        self._apply_widget_zoom()

    def zoom_reset(self):
        """Reset UI zoom to default."""
        self._zoom_level = 1.0
        self._apply_widget_zoom()

    def _apply_widget_zoom(self, show_toast: bool = True):
        """Apply zoom to CustomTkinter widgets and persist the setting."""
        ctk.set_widget_scaling(self._zoom_level)
        self.settings["ui_zoom"] = self._zoom_level
        save_settings(self.settings)
        if show_toast:
            self.toast(f"Zoom: {int(self._zoom_level * 100)}%")
