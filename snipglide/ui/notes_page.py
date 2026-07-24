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
            command=lambda _: self.refresh_list(),
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
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_list())
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

        self.content_text = ctk.CTkTextbox(self.right_frame, font=ctk.CTkFont(size=13), wrap="word")
        self.content_text.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
        create_context_menu(self.content_text)

        btn_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=20, pady=5)

        self.copy_btn = ctk.CTkButton(
            btn_row,
            text="Copy Note",
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            command=self._copy_note,
        )
        self.copy_btn.pack(side="left", padx=(0, 5))

        self.pin_btn = ctk.CTkButton(
            btn_row,
            text="Pin",
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side="left", padx=5)

        action_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        action_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(5, 15))
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
        self.refresh_list()
        self._new_note()

    def _bind_shortcuts(self):
        top = self.winfo_toplevel()
        top.bind("<Control-s>", lambda _e: self._save_note())
        top.bind("<Control-n>", lambda _e: self._new_note())
        top.bind("<Control-d>", lambda _e: self._delete_note())

    def _category_display(self, category: NoteCategory) -> str:
        return f"{category.icon} {category.name}".strip()

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

    def refresh_list(self):
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

        for note in notes:
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

    def _select_note(self, note: Note):
        self.selected_note_id = note.id
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, note.title)
        self.content_text.delete("1.0", "end")
        self.content_text.insert("1.0", note.content)
        self.category_var.set(self.category_id_to_display.get(note.category_id, self.category_var.get()))
        self.pin_btn.configure(
            text="Unpin" if note.pinned else "Pin",
            fg_color="#f59e0b" if note.pinned else ("gray75", "gray25"),
        )

    def _new_note(self):
        self.selected_note_id = None
        self.title_entry.delete(0, "end")
        self.content_text.delete("1.0", "end")
        if self.category_filter.get() != "All Notes":
            self.category_var.set(self.category_filter.get())
        self.pin_btn.configure(text="Pin", fg_color=("gray75", "gray25"))
        self.title_entry.focus_set()

    def _save_note(self):
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
            if self.selected_note_id is None:
                self.selected_note_id = add_note(note)
                self.toast_callback("Note created.")
            else:
                update_note(note)
                self.toast_callback("Note updated.")

            self.refresh_list()
        except Exception as e:
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

        self.clipboard_clear()
        self.clipboard_append(content)
        self.toast_callback("Note copied to clipboard.")

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
