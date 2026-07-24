import customtkinter as ctk
import threading
from snipglide.models.snippet import Snippet
from snipglide.models.group import Group
from snipglide.database.snippet_repo import get_all_snippets, add_snippet, update_snippet, delete_snippet
from snipglide.database.group_repo import get_all_groups, add_group
from snipglide.ui.widgets.code_editor import CodeEditor
from snipglide.ui.dialogs.group_dialog import GroupDialog
from snipglide.services.ai import call_ai_completion
from snipglide.utils.logger import logger

class SnippetEditorView(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, settings_provider, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.settings_provider = settings_provider
        self.selected_index = None
        self.snippets_list = []
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        # Left Panel (Snippets list & filter)
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)
        
        # Search & Group Filter
        self.search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search shortcut...")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_list())
        
        self.group_filter = ctk.CTkOptionMenu(self.left_frame, values=["All Groups"], command=lambda _: self.refresh_list())
        self.group_filter.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        
        # Scrollable list
        self.scroll_list = ctk.CTkScrollableFrame(self.left_frame, label_text="Snippet Triggers")
        self.scroll_list.grid(row=2, column=0, sticky="nsew", padx=15, pady=(5, 15))
        
        # Right Panel (Editor)
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(6, weight=1)
        
        # UI Fields inside editor
        ctk.CTkLabel(self.right_frame, text="Snippet Editor", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))
        
        # Row 1: Shortcut & Favorite
        r1_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r1_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=4)
        r1_frame.grid_columnconfigure(0, weight=1)
        
        self.shortcut_entry = ctk.CTkEntry(r1_frame, placeholder_text="Trigger (e.g. #sig, $date, !@#)")
        self.shortcut_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.favorite_var = ctk.BooleanVar(value=False)
        self.favorite_cb = ctk.CTkCheckBox(r1_frame, text="⭐ Fav", variable=self.favorite_var, width=60)
        self.favorite_cb.grid(row=0, column=1, sticky="e")
        
        # Row 2: Description
        self.desc_entry = ctk.CTkEntry(self.right_frame, placeholder_text="Description / Notes")
        self.desc_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        
        # Row 3: Group & Language
        r3_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r3_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=4)
        r3_frame.grid_columnconfigure((0, 1), weight=1)
        
        g_sub = ctk.CTkFrame(r3_frame, fg_color="transparent")
        g_sub.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        g_sub.grid_columnconfigure(0, weight=1)
        self.group_var = ctk.StringVar(value="📁 General")
        self.group_menu = ctk.CTkOptionMenu(g_sub, variable=self.group_var, values=["📁 General"])
        self.group_menu.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.add_group_btn = ctk.CTkButton(g_sub, text="+", width=32, command=self._add_new_group)
        self.add_group_btn.grid(row=0, column=1, sticky="e")
        
        self.lang_var = ctk.StringVar(value="Plain Text")
        self.lang_menu = ctk.CTkOptionMenu(r3_frame, variable=self.lang_var, values=["Plain Text", "Python", "JavaScript", "HTML", "CSS", "SQL", "JSON", "XML", "YAML", "Markdown", "C#", "Java", "C++"], command=lambda _: self._on_lang_change())
        self.lang_menu.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        
        # Row 4: Regex, App & Window Filter
        r4_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r4_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=4)
        r4_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.regex_var = ctk.BooleanVar(value=False)
        self.regex_cb = ctk.CTkCheckBox(r4_frame, text="Regex", variable=self.regex_var)
        self.regex_cb.grid(row=0, column=0, sticky="w")
        
        self.app_filter_entry = ctk.CTkEntry(r4_frame, placeholder_text="App Filter (e.g. notepad.exe)", height=28)
        self.app_filter_entry.grid(row=0, column=1, sticky="ew", padx=2)
        self.win_filter_entry = ctk.CTkEntry(r4_frame, placeholder_text="Window Title Filter", height=28)
        self.win_filter_entry.grid(row=0, column=2, sticky="ew", padx=(2, 0))
        
        # Row 5: Code Editor
        self.editor = CodeEditor(self.right_frame)
        self.editor.grid(row=5, column=0, sticky="nsew", padx=20, pady=8)
        
        # Row 6: AI Toolbar
        ai_frame = ctk.CTkFrame(self.right_frame, height=35, fg_color="transparent")
        ai_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=4)
        ctk.CTkLabel(ai_frame, text="AI Assist:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        
        ai_actions = [
            ("Professional", "👔 Professional"),
            ("Friendly", "😊 Friendly"),
            ("Grammar", "✍️ Correct"),
            ("Translate", "🌐 Translate")
        ]
        for aid, label in ai_actions:
            btn = ctk.CTkButton(ai_frame, text=label, width=80, height=24, font=ctk.CTkFont(size=11), fg_color=("gray80", "gray20"), text_color=("black", "white"), command=lambda a=aid: self._run_ai_assist(a))
            btn.pack(side="left", padx=3)
            
        # Row 7: Actions
        btn_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        btn_frame.grid(row=7, column=0, sticky="ew", padx=20, pady=(8, 15))
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.save_btn = ctk.CTkButton(btn_frame, text="Save Snippet", command=self._save_snippet)
        self.save_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        self.new_btn = ctk.CTkButton(btn_frame, text="New", fg_color=("gray70", "gray30"), command=self._new_snippet)
        self.new_btn.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.delete_btn = ctk.CTkButton(btn_frame, text="Delete", fg_color="#dc2626", hover_color="#b91c1c", command=self._delete_snippet)
        self.delete_btn.grid(row=0, column=2, sticky="ew", padx=(5, 0))
        
        # Load initial values
        self.update_group_dropdowns()
        self.refresh_list()
        self._new_snippet()
        
        from snipglide.utils.helpers import create_context_menu
        for attr in [self.search_entry, self.shortcut_entry, self.desc_entry, self.app_filter_entry, self.win_filter_entry]:
            create_context_menu(attr)
        
    def _on_lang_change(self):
        self.editor.highlight_code(self.lang_var.get())
        
    def _run_ai_assist(self, mode: str):
        settings = self.settings_provider()
        api_key = settings.get("ai_api_key", "")
        provider = settings.get("ai_provider", "gemini")
        
        text = self.editor.get_text()
        if not text.strip():
            self.toast_callback("Please write some text in the editor first.", error=True)
            return
            
        self.toast_callback("Processing with AI...")
        
        if mode == "Professional":
            prompt = f"Rewrite the following text to make it professional:\n{text}"
        elif mode == "Friendly":
            prompt = f"Rewrite this in friendly tone:\n{text}"
        elif mode == "Grammar":
            prompt = f"Correct grammar for:\n{text}"
        elif mode == "Translate":
            prompt = f"Translate the text to English if it is not, or translate to Arabic if it is English:\n{text}"
        else:
            prompt = text
            
        # Call service in a separate thread so UI does not freeze
        def run():
            result = call_ai_completion(prompt, api_key, provider)
            # Update textbox on main thread
            self.after(0, lambda: self.editor.set_text(result))
            self.after(0, lambda: self._on_lang_change())
            self.after(0, lambda: self.toast_callback("AI assist completed!"))
            
        threading.Thread(target=run, daemon=True).start()
        
    def _add_new_group(self):
        dialog = GroupDialog(self, title="Create New Group")
        if dialog.result:
            name = dialog.result["name"]
            icon = dialog.result["icon"]
            color = dialog.result["color"]
            desc = dialog.result["description"]
            try:
                g_id = add_group(Group(name=name, icon=icon, color=color, description=desc))
                self.update_group_dropdowns()
                self.group_var.set(f"{icon} {name}")
                self.toast_callback("Group created successfully!")
            except Exception as e:
                self.toast_callback(f"Failed to create group: {e}", error=True)
                
    def update_group_dropdowns(self):
        groups = get_all_groups()
        display_groups = [f"{g.icon} {g.name}" for g in groups]
        self.group_menu.configure(values=display_groups)
        self.group_filter.configure(values=["All Groups"] + display_groups)
        
    def refresh_list(self):
        for widget in self.scroll_list.winfo_children():
            widget.destroy()
            
        query = self.search_entry.get().strip().lower()
        selected_filter = self.group_filter.get()
        
        # Clean group filter name
        clean_filter = "All Groups"
        if selected_filter != "All Groups":
            parts = selected_filter.split(" ", 1)
            clean_filter = parts[1] if len(parts) > 1 else selected_filter
            
        snippets = get_all_snippets()
        self.snippets_list = []
        
        # Resolve group names for mapping
        groups_map = {g.id: g.name for g in get_all_groups()}
        groups_icons = {g.id: g.icon for g in get_all_groups()}
        
        visible = []
        for s in snippets:
            s_group = groups_map.get(s.group_id, "General")
            if clean_filter != "All Groups" and s_group != clean_filter:
                continue
                
            text = f"{s.shortcut} {s.description}".lower()
            if not query or query in text:
                visible.append(s)
                
        if not visible:
            ctk.CTkLabel(self.scroll_list, text="No snippets match.", text_color="gray").pack(pady=20)
            return
            
        for i, s in enumerate(visible):
            icon = groups_icons.get(s.group_id, "📁")
            preview = s.replacement.replace("\n", " ")
            if len(preview) > 30:
                preview = preview[:30] + "..."
                
            # Keep index pointer
            btn = ctk.CTkButton(
                self.scroll_list,
                text=f"{icon} {s.shortcut}\n{preview}",
                anchor="w",
                height=55,
                fg_color=("gray88", "gray18"),
                hover_color=("gray80", "gray25"),
                text_color=("black", "white"),
                command=lambda snippet=s: self._select_snippet(snippet)
            )
            btn.pack(fill="x", pady=4)
            
    def _select_snippet(self, s: Snippet):
        self.selected_snippet_id = s.id
        self.shortcut_entry.delete(0, "end")
        self.shortcut_entry.insert(0, s.shortcut)
        self.desc_entry.delete(0, "end")
        self.desc_entry.insert(0, s.description)
        self.favorite_var.set(s.favorite)
        self.regex_var.set(s.regex_enabled)
        self.app_filter_entry.delete(0, "end")
        self.app_filter_entry.insert(0, s.app_filter)
        self.win_filter_entry.delete(0, "end")
        self.win_filter_entry.insert(0, s.window_filter)
        
        # Set Group dropdown
        groups = get_all_groups()
        groups_map = {g.id: (g.name, g.icon) for g in groups}
        g_name, g_icon = groups_map.get(s.group_id, ("General", "📁"))
        self.group_var.set(f"{g_icon} {g_name}")
        
        # Set Language dropdown
        self.lang_var.set(s.language)
        
        # Set replacement text
        self.editor.set_text(s.replacement)
        self._on_lang_change()
        
    def _new_snippet(self):
        self.selected_snippet_id = None
        self.shortcut_entry.delete(0, "end")
        self.desc_entry.delete(0, "end")
        self.favorite_var.set(False)
        self.regex_var.set(False)
        self.app_filter_entry.delete(0, "end")
        self.win_filter_entry.delete(0, "end")
        self.group_var.set("📁 General")
        self.lang_var.set("Plain Text")
        self.editor.set_text("")
        self._on_lang_change()
        self.shortcut_entry.focus_set()
        
    def _save_snippet(self):
        shortcut = self.shortcut_entry.get().strip()
        replacement = self.editor.get_text()
        
        if not shortcut or not replacement:
            self.toast_callback("Shortcut and replacement are required.", error=True)
            return
            
        # Clean group selection
        g_selection = self.group_var.get()
        g_parts = g_selection.split(" ", 1)
        g_name = g_parts[1] if len(g_parts) > 1 else g_selection
        
        groups = {g.name: g.id for g in get_all_groups()}
        g_id = groups.get(g_name, 1)
        
        snippet = Snippet(
            shortcut=shortcut,
            replacement=replacement,
            group_id=g_id,
            description=self.desc_entry.get().strip(),
            language=self.lang_var.get(),
            favorite=self.favorite_var.get(),
            regex_enabled=self.regex_var.get(),
            app_filter=self.app_filter_entry.get().strip(),
            window_filter=self.win_filter_entry.get().strip()
        )
        
        try:
            if getattr(self, "selected_snippet_id", None) is None:
                existing = get_snippet_by_shortcut(shortcut)
                if existing:
                    self.toast_callback("Shortcut already exists.", error=True)
                    return
                add_snippet(snippet)
                self.toast_callback("Snippet created!")
            else:
                snippet.id = self.selected_snippet_id
                update_snippet(snippet)
                self.toast_callback("Snippet updated!")
                
            self.refresh_list()
            self._new_snippet()
        except Exception as e:
            self.toast_callback(f"Failed to save: {e}", error=True)
            
    def _delete_snippet(self):
        s_id = getattr(self, "selected_snippet_id", None)
        if s_id is None:
            self.toast_callback("Select a snippet first.", error=True)
            return
        try:
            delete_snippet(s_id)
            self.toast_callback("Snippet deleted.")
            self.refresh_list()
            self._new_snippet()
        except Exception as e:
            self.toast_callback(f"Delete failed: {e}", error=True)
