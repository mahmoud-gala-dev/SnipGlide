import customtkinter as ctk

from snipglide.database.note_category_repo import add_category, delete_category, get_all_categories
from snipglide.database.note_repo import (
    add_note,
    delete_note,
    get_all_notes,
    get_note_by_id,
    get_notes_by_category,
    toggle_pin,
    update_note,
)
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting, set_note_settings
from snipglide.models.note import Note
from snipglide.models.note_category import NoteCategory
from snipglide.ui.dialogs.group_dialog import GroupDialog
from snipglide.utils.helpers import apply_rtl_support, create_context_menu


class NotesPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.selected_note_id = None
        self.category_display_to_id = {}
        self.category_id_to_display = {}
        self._refresh_job = None
        self._editor_settings_job = None
        self._autosave_job = None
        self._last_copied_selection = ""
        self._last_saved_state = None
        self.editor_direction = get_note_setting("editor_direction", "auto")
        self.editor_font_size = self._get_int_note_setting("editor_font_size", 14, 10, 28)
        self.editor_line_spacing = self._get_int_note_setting("editor_line_spacing", 4, 0, 20)
        self._persist_editor_settings()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(3, weight=1)

        category_row = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        category_row.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        category_row.grid_columnconfigure(0, weight=1)

        self.category_filter = ctk.CTkOptionMenu(
            category_row,
            values=["All Notes"],
            command=self._on_filter_changed,
        )
        self.category_filter.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.add_filter_cat_btn = ctk.CTkButton(category_row, text="+", width=34, command=self._add_category)
        self.add_filter_cat_btn.grid(row=0, column=1, padx=(0, 5))

        self.delete_cat_btn = ctk.CTkButton(
            category_row,
            text="Del",
            width=44,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self._delete_selected_category,
        )
        self.delete_cat_btn.grid(row=0, column=2)

        self.search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search notes...")
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._schedule_refresh_list())
        create_context_menu(self.search_entry)
        apply_rtl_support(self.search_entry)

        ctk.CTkLabel(self.left_frame, text="Notes", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=2, column=0, sticky="ew", padx=15, pady=(8, 0)
        )

        self.scroll_list = ctk.CTkScrollableFrame(self.left_frame)
        self.scroll_list.grid(row=3, column=0, sticky="nsew", padx=15, pady=(5, 15))

        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.right_frame, text="Notes Editor", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(15, 5)
        )

        title_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        title_row.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        title_row.grid_columnconfigure(0, weight=2)
        title_row.grid_columnconfigure(1, weight=1)

        self.title_entry = ctk.CTkEntry(title_row, placeholder_text="Note title...", font=ctk.CTkFont(size=14))
        self.title_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.title_entry.bind("<KeyRelease>", lambda _e: self._schedule_autosave(), add="+")
        create_context_menu(self.title_entry)
        apply_rtl_support(self.title_entry)

        cat_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        cat_frame.grid(row=0, column=1, sticky="ew")
        cat_frame.grid_columnconfigure(0, weight=1)

        self.category_var = ctk.StringVar(value="General")
        self.category_menu = ctk.CTkOptionMenu(cat_frame, variable=self.category_var, values=["General"])
        self.category_menu.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.add_cat_btn = ctk.CTkButton(cat_frame, text="+", width=34, command=self._add_category)
        self.add_cat_btn.grid(row=0, column=1)

        self.content_text = ctk.CTkTextbox(self.right_frame, font=ctk.CTkFont(size=self.editor_font_size), wrap="word")
        self.content_text.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
        create_context_menu(self.content_text)
        apply_rtl_support(self.content_text)
        self.content_text.bind("<KeyRelease>", lambda _e: self._schedule_apply_editor_settings(), add="+")
        self.content_text.bind("<KeyRelease>", lambda _e: self._schedule_autosave(), add="+")
        self.content_text.bind("<ButtonRelease-1>", lambda _e: self._copy_current_selection(), add="+")
        self.title_entry.bind("<ButtonRelease-1>", lambda _e: self._copy_current_selection(), add="+")

        editor_settings_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        editor_settings_row.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        editor_settings_row.grid_columnconfigure(4, weight=1)

        self.direction_control = ctk.CTkSegmentedButton(
            editor_settings_row,
            values=["Auto", "LTR", "RTL"],
            command=self._set_editor_direction,
        )
        self.direction_control.set(self.editor_direction.upper() if self.editor_direction != "auto" else "Auto")
        self.direction_control.grid(row=0, column=0, sticky="w", padx=(0, 12))

        self.font_size_label = ctk.CTkLabel(editor_settings_row, text=f"Font {self.editor_font_size}")
        self.font_size_label.grid(row=0, column=1, sticky="w", padx=(0, 6))
        ctk.CTkButton(editor_settings_row, text="-", width=30, command=lambda: self._change_font_size(-1)).grid(
            row=0, column=2, padx=2
        )
        ctk.CTkButton(editor_settings_row, text="+", width=30, command=lambda: self._change_font_size(1)).grid(
            row=0, column=3, padx=(2, 12)
        )

        self.line_spacing_label = ctk.CTkLabel(editor_settings_row, text=f"Line {self.editor_line_spacing}")
        self.line_spacing_label.grid(row=0, column=4, sticky="e", padx=(0, 6))
        ctk.CTkButton(editor_settings_row, text="-", width=30, command=lambda: self._change_line_spacing(-1)).grid(
            row=0, column=5, padx=2
        )
        ctk.CTkButton(editor_settings_row, text="+", width=30, command=lambda: self._change_line_spacing(1)).grid(
            row=0, column=6, padx=2
        )

        btn_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="ew", padx=20, pady=5)

        self.copy_btn = ctk.CTkButton(
            btn_row,
            text="Copy Note",
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            command=self._copy_note,
        )
        self.copy_btn.pack(side="left", padx=(0, 5))

        self.save_state_label = ctk.CTkLabel(btn_row, text="Saved", text_color="gray")
        self.save_state_label.pack(side="right", padx=5)

        self.pin_btn = ctk.CTkButton(
            btn_row,
            text="Pin",
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side="left", padx=5)

        action_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        action_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(5, 15))
        action_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.save_btn = ctk.CTkButton(action_frame, text="Save (Ctrl+S)", command=self._save_note)
        self.save_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.new_btn = ctk.CTkButton(
            action_frame,
            text="New (Ctrl+N)",
            fg_color=("gray70", "gray30"),
            command=self._new_note,
        )
        self.new_btn.grid(row=0, column=1, sticky="ew", padx=3)

        self.delete_btn = ctk.CTkButton(
            action_frame,
            text="Delete (Ctrl+D)",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self._delete_note,
        )
        self.delete_btn.grid(row=0, column=2, sticky="ew", padx=3)

        self.after(100, self._bind_shortcuts)
        self.update_category_dropdowns()
        self._restore_note_settings()
        self.refresh_list()
        self._new_note()
        self._apply_editor_settings()

    def _bind_shortcuts(self):
        top = self.winfo_toplevel()
        top.bind("<Control-s>", lambda _e: self._save_note())
        top.bind("<Control-n>", lambda _e: self._new_note())
        top.bind("<Control-d>", lambda _e: self._delete_note())

    def _schedule_refresh_list(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(180, self.refresh_list)

    def _schedule_apply_editor_settings(self):
        if self._editor_settings_job:
            self.after_cancel(self._editor_settings_job)
        self._editor_settings_job = self.after(250, self._apply_editor_settings)

    def _schedule_autosave(self):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self.save_state_label.configure(text="Editing...", text_color="#f59e0b")
        self._autosave_job = self.after(1500, self._autosave_note)

    def _autosave_note(self):
        self._autosave_job = None
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", "end-1c")
        current_state = (self.selected_note_id, title, content, self.category_var.get())
        if current_state == self._last_saved_state:
            self.save_state_label.configure(text="Saved", text_color="gray")
            return
        if not title or not content.strip():
            self.save_state_label.configure(text="Draft", text_color="gray")
            return
        self._save_note(show_toast=False, refresh_list=False)

    def _category_display(self, category: NoteCategory) -> str:
        return f"{category.icon} {category.name}".strip()

    def _get_int_note_setting(self, key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(get_note_setting(key, str(default)))
        except ValueError:
            value = default
        return min(max(value, minimum), maximum)

    def _on_filter_changed(self, selected: str):
        set_note_setting("last_category_filter", selected)
        self.refresh_list()

    def _set_editor_direction(self, selected: str):
        self.editor_direction = selected.lower()
        self._persist_editor_settings()
        self._apply_editor_settings()

    def _change_font_size(self, delta: int):
        self.editor_font_size = min(max(self.editor_font_size + delta, 10), 28)
        self._persist_editor_settings()
        self.font_size_label.configure(text=f"Font {self.editor_font_size}")
        self._apply_editor_settings()

    def _change_line_spacing(self, delta: int):
        self.editor_line_spacing = min(max(self.editor_line_spacing + delta, 0), 20)
        self._persist_editor_settings()
        self.line_spacing_label.configure(text=f"Line {self.editor_line_spacing}")
        self._apply_editor_settings()

    def _persist_editor_settings(self):
        set_note_settings(
            {
                "editor_direction": self.editor_direction,
                "editor_font_size": str(self.editor_font_size),
                "editor_line_spacing": str(self.editor_line_spacing),
            }
        )

    def _apply_editor_settings(self):
        self._editor_settings_job = None
        target = getattr(self.content_text, "_textbox", self.content_text)
        try:
            from snipglide.core.config import get_arabic_font_family

            target.configure(font=(get_arabic_font_family(), self.editor_font_size))
            target.tag_configure(
                "note_spacing",
                spacing1=max(0, self.editor_line_spacing // 2),
                spacing2=0,
                spacing3=self.editor_line_spacing,
            )
            target.tag_add("note_spacing", "1.0", "end")
            if self.editor_direction == "rtl":
                target.tag_configure("forced_direction", justify="right")
                target.tag_add("forced_direction", "1.0", "end")
            elif self.editor_direction == "ltr":
                target.tag_configure("forced_direction", justify="left")
                target.tag_add("forced_direction", "1.0", "end")
            else:
                target.tag_remove("forced_direction", "1.0", "end")
        except Exception:
            pass

    def _restore_note_settings(self):
        saved_filter = get_note_setting("last_category_filter", "All Notes")
        values = ["All Notes"] + list(self.category_display_to_id.keys())
        if saved_filter in values:
            self.category_filter.set(saved_filter)

    def _add_category(self):
        dialog = GroupDialog(self, title="Create Note Category")
        if not dialog.result:
            return

        cat = NoteCategory(
            name=dialog.result["name"],
            icon=dialog.result.get("icon") or "N",
            color=dialog.result.get("color") or "#2563eb",
            description=dialog.result.get("description") or "",
        )
        try:
            cat.id = add_category(cat)
            self.update_category_dropdowns()
            self.category_var.set(self._category_display(cat))
            self.category_filter.set(self._category_display(cat))
            set_note_setting("last_category_filter", self._category_display(cat))
            self.refresh_list()
            self.toast_callback("Category created.")
        except Exception as e:
            self.toast_callback(f"Failed: {e}", error=True)

    def _delete_selected_category(self):
        selected = self.category_filter.get()
        cat_id = self.category_display_to_id.get(selected)
        if selected == "All Notes" or not cat_id:
            self.toast_callback("Select a category first.", error=True)
            return

        if self._category_name(selected).lower() == "general":
            self.toast_callback("General category cannot be deleted.", error=True)
            return

        try:
            delete_category(cat_id)
            self.category_filter.set("All Notes")
            self.update_category_dropdowns()
            self.refresh_list()
            self._new_note()
            self.toast_callback("Category deleted.")
        except Exception as e:
            self.toast_callback(f"Failed: {e}", error=True)

    def _category_name(self, display: str) -> str:
        for category_display, category_id in self.category_display_to_id.items():
            if category_display == display:
                categories = {c.id: c.name for c in get_all_categories()}
                return categories.get(category_id, display)
        return display.split(" ", 1)[-1]

    def update_category_dropdowns(self):
        cats = get_all_categories()
        display = [self._category_display(c) for c in cats]
        self.category_display_to_id = {self._category_display(c): c.id for c in cats}
        self.category_id_to_display = {c.id: self._category_display(c) for c in cats}

        if not display:
            display = ["General"]

        self.category_menu.configure(values=display)
        self.category_filter.configure(values=["All Notes"] + display)

        if self.category_var.get() not in display:
            self.category_var.set(display[0])
        if self.category_filter.get() not in ["All Notes"] + display:
            self.category_filter.set("All Notes")
            set_note_setting("last_category_filter", "All Notes")

    def refresh_list(self):
        self._refresh_job = None
        for widget in self.scroll_list.winfo_children():
            widget.destroy()

        query = self.search_entry.get().strip().lower()
        selected_cat = self.category_filter.get()
        cat_id = self.category_display_to_id.get(selected_cat)
        notes = get_notes_by_category(cat_id) if cat_id else get_all_notes()

        if query:
            notes = [n for n in notes if query in n.title.lower() or query in n.content.lower()]

        if not notes:
            ctk.CTkLabel(self.scroll_list, text="No notes found.", text_color="gray").pack(pady=20)
            return

        max_visible = 150
        hidden_count = max(0, len(notes) - max_visible)
        for note in notes[:max_visible]:
            cat_display = self.category_id_to_display.get(note.category_id, "Uncategorized")
            pin_prefix = "[Pinned] " if note.pinned else ""
            preview = note.content.replace("\n", " ").strip()[:60]
            if len(note.content) > 60:
                preview += "..."

            btn = ctk.CTkButton(
                self.scroll_list,
                text=f"{pin_prefix}{note.title}\n{cat_display} - {preview}",
                anchor="w",
                height=62,
                fg_color=("gray88", "gray18"),
                hover_color=("gray80", "gray25"),
                text_color=("black", "white"),
                command=lambda n=note: self._select_note(n),
            )
            btn.pack(fill="x", pady=4)

        if hidden_count:
            ctk.CTkLabel(
                self.scroll_list,
                text=f"{hidden_count} more notes hidden. Refine search to narrow the list.",
                text_color="gray",
            ).pack(pady=10)

    def _select_note(self, note: Note):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        self.selected_note_id = note.id
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, note.title)
        self.content_text.delete("1.0", "end")
        self.content_text.insert("1.0", note.content)
        self._apply_editor_settings()
        self.category_var.set(self.category_id_to_display.get(note.category_id, self.category_var.get()))
        self.pin_btn.configure(
            text="Unpin" if note.pinned else "Pin",
            fg_color="#f59e0b" if note.pinned else ("gray75", "gray25"),
        )
        if note.content.strip():
            self._copy_text_to_clipboard(note.content)
            self.toast_callback("Note copied to clipboard.")
        self._last_saved_state = (self.selected_note_id, note.title, note.content, self.category_var.get())
        self.save_state_label.configure(text="Saved", text_color="gray")

    def _new_note(self):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        self.selected_note_id = None
        self.title_entry.delete(0, "end")
        self.content_text.delete("1.0", "end")
        if self.category_filter.get() != "All Notes":
            self.category_var.set(self.category_filter.get())
        self._apply_editor_settings()
        self.pin_btn.configure(text="Pin", fg_color=("gray75", "gray25"))
        self._last_saved_state = None
        self.save_state_label.configure(text="Draft", text_color="gray")
        self.title_entry.focus_set()

    def _save_note(self, show_toast: bool = True, refresh_list: bool = True):
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", "end-1c")

        if not title:
            self.toast_callback("Title is required.", error=True)
            return

        selected_category = self.category_var.get()
        cat_id = self.category_display_to_id.get(selected_category)
        existing = get_note_by_id(self.selected_note_id) if self.selected_note_id else None

        note = Note(
            id=self.selected_note_id,
            title=title,
            content=content,
            category_id=cat_id,
            pinned=existing.pinned if existing else False,
            color=existing.color if existing else "#2563eb",
        )

        try:
            was_new = self.selected_note_id is None
            if self.selected_note_id is None:
                self.selected_note_id = add_note(note)
                if show_toast:
                    self.toast_callback("Note created.")
            else:
                update_note(note)
                if show_toast:
                    self.toast_callback("Note updated.")

            self._last_saved_state = (self.selected_note_id, title, content, selected_category)
            self.save_state_label.configure(text="Saved", text_color="#16a34a")
            if refresh_list or was_new:
                self.refresh_list()
        except Exception as e:
            self.save_state_label.configure(text="Save failed", text_color="#dc2626")
            if show_toast:
                self.toast_callback(f"Failed: {e}", error=True)

    def _delete_note(self):
        if not self.selected_note_id:
            self.toast_callback("Select a note first.", error=True)
            return

        try:
            delete_note(self.selected_note_id)
            self.toast_callback("Note deleted.")
            self.refresh_list()
            self._new_note()
        except Exception as e:
            self.toast_callback(f"Failed: {e}", error=True)

    def _copy_note(self):
        content = self.content_text.get("1.0", "end-1c")
        if not content.strip():
            self.toast_callback("Note is empty.", error=True)
            return

        self._copy_text_to_clipboard(content)
        self.toast_callback("Note copied to clipboard.")

    def _copy_current_selection(self):
        try:
            selected = self.selection_get().strip()
        except Exception:
            return

        if not selected or selected == self._last_copied_selection:
            return

        self._copy_text_to_clipboard(selected)
        self._last_copied_selection = selected
        self.toast_callback("Selection copied.")

    def _copy_text_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _toggle_pin(self):
        if not self.selected_note_id:
            self.toast_callback("Select a note first.", error=True)
            return

        toggle_pin(self.selected_note_id)
        note = get_note_by_id(self.selected_note_id)
        if note:
            self._select_note(note)
        self.refresh_list()
        self.toast_callback("Pin status updated.")
