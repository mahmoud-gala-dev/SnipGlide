import re
import tkinter as tk
from datetime import datetime
import customtkinter as ctk

from snipglide.database.chat_note_repo import (
    add_chat_note,
    add_chat_section,
    clear_all_chat_notes,
    delete_chat_note,
    delete_chat_section,
    get_all_chat_notes,
    get_all_chat_sections,
    get_chat_notes_count,
    seed_demo_chat_notes,
    toggle_star_chat_note,
)
from snipglide.database.note_settings_repo import get_note_setting, set_note_setting
from snipglide.models.chat_note import ChatNote, ChatNoteSection
from snipglide.utils.helpers import apply_rtl_support, create_context_menu, download_and_load_arabic_font, safe_clear_frame
from snipglide.core.config import get_arabic_font_family, set_arabic_font_family


class ChatNotesPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, navigate_to_snippet_callback=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.navigate_to_snippet_callback = navigate_to_snippet_callback

        self.selected_section_id = None  # None = All sections
        self.starred_filter_active = False
        self._search_job = None
        self._render_job = None
        self._notes_cache = []
        self._sections_cache = []
        self._is_dirty = True

        # Load saved font size (Default 22px) and font family
        self.chat_font_size = self._get_saved_font_size()
        self.chat_font_family = self._get_saved_font_family()

        # Grid configuration: Row 0 Header, Row 1 Sections Bar, Row 2 Chat Feed, Row 3 Compose Bar
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_sections_bar()
        self._build_chat_feed()
        self._build_compose_bar()

        # Check if chat notes are empty, seed demo data if first time
        if get_chat_notes_count() == 0:
            try:
                seed_demo_chat_notes()
            except Exception:
                pass

        # Initial load
        self.after(60, self.refresh_sections)
        self.after(90, self.refresh_chat)

    def _get_saved_font_size(self) -> int:
        try:
            val = int(get_note_setting("chat_font_size", "22"))
            if val < 18:
                val = 22  # Upgrade default to 22px
                set_note_setting("chat_font_size", "22")
            return min(max(val, 12), 36)
        except Exception:
            return 22

    def _get_saved_font_family(self) -> str:
        saved = get_note_setting("chat_font_family", "Tajawal")
        return saved if saved else get_arabic_font_family()

    def _get_font(self, size: int | None = None, weight: str = "normal") -> ctk.CTkFont:
        """Helper to get a consistent font with the active Google Arabic font family."""
        s = size if size is not None else self.chat_font_size
        return ctk.CTkFont(family=self.chat_font_family, size=s, weight=weight)

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color=("gray92", "#111b21"), corner_radius=12)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 6))
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Avatar & Title (WhatsApp Green Avatar)
        left_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_box.grid(row=0, column=0, sticky="w", padx=15, pady=8)

        avatar = ctk.CTkLabel(
            left_box,
            text="💬",
            font=self._get_font(size=22),
            fg_color="#25D366",
            text_color="white",
            width=42,
            height=42,
            corner_radius=21,
        )
        avatar.pack(side="left", padx=(0, 10))

        title_info = ctk.CTkFrame(left_box, fg_color="transparent")
        title_info.pack(side="left")

        self.title_lbl = ctk.CTkLabel(
            title_info,
            text="شات الملاحظات السريعة (Quick Chat Notes)",
            font=self._get_font(size=17, weight="bold"),
            anchor="w",
        )
        self.title_lbl.pack(anchor="w")

        self.count_badge = ctk.CTkLabel(
            title_info,
            text="سجل ملاحظاتك ورسائلك السريعة بأسلوب الواتساب المريح",
            font=self._get_font(size=12),
            text_color="gray",
            anchor="w",
        )
        self.count_badge.pack(anchor="w")

        # Right-side action controls
        right_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_box.grid(row=0, column=1, sticky="e", padx=12, pady=8)

        # Font size adjustment controls: [A-] [22px] [A+]
        font_box = ctk.CTkFrame(right_box, fg_color=("gray85", "#182229"), corner_radius=8)
        font_box.pack(side="left", padx=4)

        self.font_down_btn = ctk.CTkButton(
            font_box,
            text="A-",
            width=30,
            height=30,
            corner_radius=6,
            fg_color="transparent",
            hover_color=("gray75", "#2a3942"),
            text_color=("black", "white"),
            font=self._get_font(size=12, weight="bold"),
            command=lambda: self._change_font_size(-1),
        )
        self.font_down_btn.pack(side="left", padx=2, pady=2)

        self.font_size_lbl = ctk.CTkLabel(
            font_box,
            text=f"{self.chat_font_size}px",
            font=self._get_font(size=13, weight="bold"),
            width=42,
        )
        self.font_size_lbl.pack(side="left", padx=2)

        self.font_up_btn = ctk.CTkButton(
            font_box,
            text="A+",
            width=30,
            height=30,
            corner_radius=6,
            fg_color="transparent",
            hover_color=("gray75", "#2a3942"),
            text_color=("black", "white"),
            font=self._get_font(size=12, weight="bold"),
            command=lambda: self._change_font_size(1),
        )
        self.font_up_btn.pack(side="left", padx=2, pady=2)

        # Font Family Dropdown
        self.font_menu = ctk.CTkOptionMenu(
            right_box,
            values=["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"],
            font=self._get_font(size=12, weight="bold"),
            dropdown_font=self._get_font(size=13),
            width=110,
            height=32,
            corner_radius=8,
            command=self._on_font_family_change,
        )
        self.font_menu.set(self.chat_font_family if self.chat_font_family in ["Tajawal", "Cairo", "Almarai", "Segoe UI", "Tahoma"] else "Tajawal")
        self.font_menu.pack(side="left", padx=4)

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            right_box,
            placeholder_text="🔍 بحث...",
            font=self._get_font(size=13),
            width=140,
            height=32,
            corner_radius=8,
        )
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        apply_rtl_support(self.search_entry)
        create_context_menu(self.search_entry)

        # Star Filter Button
        self.star_btn = ctk.CTkButton(
            right_box,
            text="⭐ المفضلة",
            width=80,
            height=32,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            text_color=("black", "white"),
            corner_radius=8,
            font=self._get_font(size=12),
            command=self._toggle_star_filter,
        )
        self.star_btn.pack(side="left", padx=3)

        # Seed Demo Button
        self.demo_btn = ctk.CTkButton(
            right_box,
            text="🌱 عينات",
            width=70,
            height=32,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            text_color=("black", "white"),
            corner_radius=8,
            font=self._get_font(size=12),
            command=self._seed_demo_data,
        )
        self.demo_btn.pack(side="left", padx=3)

        # Clear All Button
        self.clear_btn = ctk.CTkButton(
            right_box,
            text="🗑️ مسح",
            width=65,
            height=32,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="white",
            corner_radius=8,
            font=self._get_font(size=12),
            command=self._confirm_clear_all,
        )
        self.clear_btn.pack(side="left", padx=(3, 0))

    def _build_sections_bar(self):
        """Build horizontal sections / categories pill bar."""
        self.sections_outer = ctk.CTkFrame(self, fg_color="transparent", height=42)
        self.sections_outer.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 6))
        self.sections_outer.grid_columnconfigure(0, weight=1)

        self.sections_scroll = ctk.CTkScrollableFrame(
            self.sections_outer,
            orientation="horizontal",
            height=40,
            fg_color="transparent",
        )
        self.sections_scroll.grid(row=0, column=0, sticky="ew")

    def _build_chat_feed(self):
        self.chat_container = ctk.CTkFrame(self, fg_color=("gray95", "#0b141a"), corner_radius=12)
        self.chat_container.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.chat_container.grid_columnconfigure(0, weight=1)
        self.chat_container.grid_rowconfigure(0, weight=1)

        self.chat_scroll = ctk.CTkScrollableFrame(
            self.chat_container,
            fg_color="transparent",
            corner_radius=12,
        )
        self.chat_scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.chat_scroll.grid_columnconfigure(0, weight=1)

    def _build_compose_bar(self):
        self.compose_frame = ctk.CTkFrame(self, fg_color=("gray92", "#111b21"), corner_radius=12)
        self.compose_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.compose_frame.grid_columnconfigure(2, weight=1)

        # Left tools: Section Picker + Timestamp + Star
        tools_frame = ctk.CTkFrame(self.compose_frame, fg_color="transparent")
        tools_frame.grid(row=0, column=0, padx=(10, 5), pady=8)

        self.compose_section_var = ctk.StringVar(value="💬 عام")
        self.compose_section_menu = ctk.CTkOptionMenu(
            tools_frame,
            variable=self.compose_section_var,
            values=["💬 عام"],
            font=self._get_font(size=12, weight="bold"),
            dropdown_font=self._get_font(size=13),
            width=120,
            height=38,
            corner_radius=8,
        )
        self.compose_section_menu.pack(side="left", padx=2)

        self.time_stamp_btn = ctk.CTkButton(
            tools_frame,
            text="🕒",
            width=38,
            height=38,
            corner_radius=8,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            font=self._get_font(size=14),
            command=self._insert_timestamp,
        )
        self.time_stamp_btn.pack(side="left", padx=2)

        self.star_new_var = ctk.BooleanVar(value=False)
        self.star_new_btn = ctk.CTkButton(
            tools_frame,
            text="⭐",
            width=38,
            height=38,
            corner_radius=8,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            font=self._get_font(size=14),
            command=self._toggle_new_note_star,
        )
        self.star_new_btn.pack(side="left", padx=2)

        # Message Textbox with large 22px font
        self.message_input = ctk.CTkTextbox(
            self.compose_frame,
            height=62,
            corner_radius=10,
            font=self._get_font(size=self.chat_font_size),
            wrap="word",
        )
        self.message_input.grid(row=0, column=2, sticky="ew", padx=5, pady=8)
        self.message_input.bind("<Return>", self._handle_return_key)
        apply_rtl_support(self.message_input)
        create_context_menu(self.message_input)

        # Right Send Action
        send_frame = ctk.CTkFrame(self.compose_frame, fg_color="transparent")
        send_frame.grid(row=0, column=3, padx=(5, 10), pady=8)

        self.send_btn = ctk.CTkButton(
            send_frame,
            text="➤ إرسال",
            width=90,
            height=46,
            corner_radius=10,
            fg_color="#25D366",
            hover_color="#1da851",
            text_color="white",
            font=self._get_font(size=14, weight="bold"),
            command=self._send_message,
        )
        self.send_btn.pack(side="left")

    def _apply_theme_to_header_and_controls(self):
        """Update all header and control widgets with the active font family and size."""
        self.title_lbl.configure(font=self._get_font(size=17, weight="bold"))
        self.count_badge.configure(font=self._get_font(size=12))
        self.font_down_btn.configure(font=self._get_font(size=12, weight="bold"))
        self.font_size_lbl.configure(font=self._get_font(size=13, weight="bold"), text=f"{self.chat_font_size}px")
        self.font_up_btn.configure(font=self._get_font(size=12, weight="bold"))
        self.font_menu.configure(font=self._get_font(size=12, weight="bold"), dropdown_font=self._get_font(size=13))
        self.search_entry.configure(font=self._get_font(size=13))
        self.star_btn.configure(font=self._get_font(size=12))
        self.demo_btn.configure(font=self._get_font(size=12))
        self.clear_btn.configure(font=self._get_font(size=12))
        self.compose_section_menu.configure(font=self._get_font(size=12, weight="bold"), dropdown_font=self._get_font(size=13))
        self.message_input.configure(font=self._get_font(size=self.chat_font_size))
        self.send_btn.configure(font=self._get_font(size=14, weight="bold"))

    def _change_font_size(self, delta: int):
        new_size = min(max(self.chat_font_size + delta, 12), 36)
        if new_size != self.chat_font_size:
            self.chat_font_size = new_size
            set_note_setting("chat_font_size", str(new_size))
            self._apply_theme_to_header_and_controls()
            self.refresh_chat(scroll_to_bottom=False)

    def _on_font_family_change(self, family: str):
        download_and_load_arabic_font(family)
        self.chat_font_family = family
        set_arabic_font_family(family)
        set_note_setting("chat_font_family", family)
        self._apply_theme_to_header_and_controls()
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=False)

    def refresh_sections(self):
        """Load and display section pills in the horizontal scroll bar."""
        for w in self.sections_scroll.winfo_children():
            w.destroy()

        sections = get_all_chat_sections()
        self._sections_cache = sections

        # Update compose dropdown options
        sec_options = [f"{s.icon} {s.name}" for s in sections]
        if sec_options:
            self.compose_section_menu.configure(values=sec_options)
            if self.compose_section_var.get() not in sec_options:
                self.compose_section_var.set(sec_options[0])

        # All button
        is_all_active = self.selected_section_id is None
        all_btn = ctk.CTkButton(
            self.sections_scroll,
            text=f"💬 الكل ({get_chat_notes_count()})",
            height=34,
            corner_radius=17,
            fg_color="#25D366" if is_all_active else ("gray80", "#1f2c34"),
            hover_color="#1da851" if is_all_active else ("gray70", "#2a3942"),
            text_color="white" if is_all_active else ("black", "white"),
            font=self._get_font(size=12, weight="bold" if is_all_active else "normal"),
            command=lambda: self._select_section(None),
        )
        all_btn.pack(side="left", padx=(0, 5))

        # Dynamic Section Pills
        for sec in sections:
            is_active = self.selected_section_id == sec.id
            count = get_chat_notes_count(section_id=sec.id)
            btn = ctk.CTkButton(
                self.sections_scroll,
                text=f"{sec.icon} {sec.name} ({count})",
                height=34,
                corner_radius=17,
                fg_color=sec.color if is_active else ("gray80", "#1f2c34"),
                hover_color="#1da851" if is_active else ("gray70", "#2a3942"),
                text_color="white" if is_active else ("black", "white"),
                font=self._get_font(size=12, weight="bold" if is_active else "normal"),
                command=lambda s=sec: self._select_section(s.id),
            )
            btn.pack(side="left", padx=4)
            if sec.id != 1:
                self._attach_section_context_menu(btn, sec)

        # Add New Section Button
        add_sec_btn = ctk.CTkButton(
            self.sections_scroll,
            text="➕ قسم جديد",
            height=34,
            width=95,
            corner_radius=17,
            fg_color=("gray75", "#2a3942"),
            hover_color=("gray65", "#37474f"),
            text_color=("black", "white"),
            font=self._get_font(size=12, weight="bold"),
            command=self._prompt_add_section,
        )
        add_sec_btn.pack(side="left", padx=6)

    def _select_section(self, section_id: int | None):
        self.selected_section_id = section_id
        if section_id:
            sec = next((s for s in self._sections_cache if s.id == section_id), None)
            if sec:
                self.compose_section_var.set(f"{sec.icon} {sec.name}")
        self.refresh_sections()
        self.refresh_chat(scroll_to_bottom=True)

    def _attach_section_context_menu(self, widget, section: ChatNoteSection):
        menu = tk.Menu(self, tearoff=0, font=(self.chat_font_family, 12))
        menu.add_command(label=f"🗑️ حذف قسم '{section.name}'", command=lambda: self._delete_section(section))

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", popup)

    def _prompt_add_section(self):
        from snipglide.ui.dialogs.group_dialog import GroupDialog
        dialog = GroupDialog(self, title="إضافة قسم شات جديد")
        if dialog.result:
            name = dialog.result.get("name", "").strip()
            icon = dialog.result.get("icon", "💬")
            color = dialog.result.get("color", "#25D366")
            if name:
                try:
                    new_sec = add_chat_section(name=name, icon=icon, color=color)
                    self.selected_section_id = new_sec.id
                    self.refresh_sections()
                    self.refresh_chat()
                    self.toast_callback(f"تم إنشاء قسم '{name}' بنجاح! 🎉")
                except Exception as e:
                    self.toast_callback(f"فشل إنشاء القسم: {e}", error=True)

    def _delete_section(self, section: ChatNoteSection):
        try:
            delete_chat_section(section.id)
            if self.selected_section_id == section.id:
                self.selected_section_id = None
            self.refresh_sections()
            self.refresh_chat()
            self.toast_callback(f"تم حذف قسم '{section.name}'")
        except Exception as e:
            self.toast_callback(f"فشل الحذف: {e}", error=True)

    def _seed_demo_data(self):
        try:
            seed_demo_chat_notes()
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
            self.toast_callback("تمت إضافة عينات الملاحظات التجريبية بنجاح! 💬")
        except Exception as e:
            self.toast_callback(f"خطأ: {e}", error=True)

    def on_page_activated(self):
        if getattr(self, "_is_dirty", True):
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
        else:
            self.after(30, self._scroll_to_end)

    def _insert_timestamp(self):
        now_str = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
        self.message_input.insert("insert", now_str)
        self.message_input.focus_set()

    def _toggle_new_note_star(self):
        cur = self.star_new_var.get()
        self.star_new_var.set(not cur)
        if not cur:
            self.star_new_btn.configure(fg_color="#f59e0b", text_color="white")
        else:
            self.star_new_btn.configure(fg_color=("gray80", "#1f2c34"), text_color=("black", "white"))

    def _handle_return_key(self, event):
        if event.state & 0x0001 or event.state & 0x0004:
            return None
        self._send_message()
        return "break"

    def _send_message(self):
        content = self.message_input.get("1.0", "end-1c").strip()
        if not content:
            return

        is_starred = self.star_new_var.get()
        
        # Resolve target section
        sec_str = self.compose_section_var.get()
        target_sec_id = 1
        for s in self._sections_cache:
            if f"{s.icon} {s.name}" == sec_str or s.name == sec_str:
                target_sec_id = s.id
                break

        try:
            add_chat_note(content=content, is_starred=is_starred, section_id=target_sec_id)
            self.message_input.delete("1.0", "end")

            if self.star_new_var.get():
                self.star_new_var.set(False)
                self.star_new_btn.configure(fg_color=("gray80", "#1f2c34"), text_color=("black", "white"))

            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=True)
            self.toast_callback("تم حفظ الملاحظة بنجاح 💬")
        except Exception as e:
            self.toast_callback(f"فشل الحفظ: {e}", error=True)

    def _on_search_key(self, _event=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(140, self.refresh_chat)

    def _toggle_star_filter(self):
        self.starred_filter_active = not self.starred_filter_active
        if self.starred_filter_active:
            self.star_btn.configure(fg_color="#f59e0b", text_color="white", text="⭐ المفضلة")
        else:
            self.star_btn.configure(fg_color=("gray80", "#1f2c34"), text_color=("black", "white"), text="⭐ المفضلة")
        self.refresh_chat()

    def refresh_chat(self, scroll_to_bottom: bool = True):
        if self._render_job:
            self.after_cancel(self._render_job)
            self._render_job = None

        query = self.search_entry.get().strip()
        notes = get_all_chat_notes(
            query=query,
            starred_only=self.starred_filter_active,
            section_id=self.selected_section_id,
        )
        self._notes_cache = notes
        self._is_dirty = False

        total_count = get_chat_notes_count(section_id=self.selected_section_id)
        current_count = len(notes)
        filter_text = " (المفضلة)" if self.starred_filter_active else ""
        if query:
            filter_text += f" (نتائج: '{query}')"

        sec_name = "الكل"
        if self.selected_section_id:
            s_obj = next((s for s in self._sections_cache if s.id == self.selected_section_id), None)
            if s_obj:
                sec_name = s_obj.name

        self.count_badge.configure(text=f"القسم: [{sec_name}] • الإجمالي: {total_count} • المعروض: {current_count}{filter_text}")

        safe_clear_frame(self.chat_scroll)

        if not notes:
            self._render_empty_state(query)
            return

        self._render_chat_batch(notes, start_idx=0, batch_size=25, last_date_str=None, scroll_to_bottom=scroll_to_bottom)

    def _render_chat_batch(self, notes, start_idx, batch_size, last_date_str, scroll_to_bottom):
        end_idx = min(start_idx + batch_size, len(notes))
        for i in range(start_idx, end_idx):
            note = notes[i]
            note_date_str = self._format_date_header(note.created_at)
            if note_date_str != last_date_str:
                self._render_date_divider(note_date_str)
                last_date_str = note_date_str
            self._render_chat_bubble(note)

        if end_idx < len(notes):
            self._render_job = self.after(
                3,
                lambda: self._render_chat_batch(notes, end_idx, batch_size, last_date_str, scroll_to_bottom),
            )
        else:
            self._render_job = None
            if scroll_to_bottom:
                self.after(30, self._scroll_to_end)

    def _scroll_to_end(self):
        try:
            canvas = getattr(self.chat_scroll, "_parent_canvas", None)
            if canvas:
                canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _format_date_header(self, created_at_str: str) -> str:
        try:
            dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if dt.date() == now.date():
                return "اليوم - Today"
            elif (now.date() - dt.date()).days == 1:
                return "أمس - Yesterday"
            else:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            return "ملاحظات"

    def _render_date_divider(self, text: str):
        divider_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        divider_frame.pack(fill="x", pady=(8, 4))

        pill = ctk.CTkLabel(
            divider_frame,
            text=f"  {text}  ",
            font=self._get_font(size=12, weight="bold"),
            fg_color=("gray85", "#182229"),
            text_color=("gray30", "gray70"),
            corner_radius=10,
            padx=12,
            pady=4,
        )
        pill.pack(anchor="center")

    def _render_empty_state(self, query: str):
        empty_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        empty_frame.pack(fill="both", expand=True, pady=50)

        icon_text = "🔍" if query else "💬"
        ctk.CTkLabel(empty_frame, text=icon_text, font=self._get_font(size=44)).pack(pady=(0, 10))

        if query:
            msg = f"لم يتم العثور على ملاحظات تطابق '{query}'"
        elif self.starred_filter_active:
            msg = "لا توجد ملاحظات مميزة بنجمة ⭐"
        else:
            msg = "صندوق الملاحظات في هذا القسم فارغ.\nاكتب فكرتك أو ملاحظتك في صندوق الكتابة بالأسفل واضغط Enter لحفظها فوراً!"

        ctk.CTkLabel(
            empty_frame,
            text=msg,
            font=self._get_font(size=14),
            text_color="gray",
            justify="center",
        ).pack()

    def _render_chat_bubble(self, note: ChatNote):
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = self.chat_font_family if has_arabic else "Segoe UI"
        text_align = "right" if has_arabic else "left"

        bubble_bg = ("#d9fdd3", "#005c4b") if not note.is_starred else ("#fef08a", "#064e3b")
        border_color = "#f59e0b" if note.is_starred else None
        border_width = 1 if note.is_starred else 0

        # Flat, lightweight bubble directly in scrollable frame for maximum responsiveness
        bubble = ctk.CTkFrame(
            self.chat_scroll,
            fg_color=bubble_bg,
            border_color=border_color,
            border_width=border_width,
            corner_radius=14,
        )
        bubble.pack(anchor="e", fill="none", padx=(60, 10), pady=4)

        # Section tag & Star indicator
        sec_name = None
        if note.section_id and self.selected_section_id is None:
            s_obj = next((s for s in self._sections_cache if s.id == note.section_id), None)
            if s_obj:
                sec_name = f"{s_obj.icon} {s_obj.name}"

        if note.is_starred or sec_name:
            top_bar = ctk.CTkFrame(bubble, fg_color="transparent")
            top_bar.pack(fill="x", padx=12, pady=(6, 0))
            if note.is_starred:
                ctk.CTkLabel(
                    top_bar,
                    text="⭐ مميزة",
                    font=self._get_font(size=12, weight="bold"),
                    text_color=("#854d0e", "#fde047"),
                ).pack(side="left", padx=(0, 6))
            if sec_name:
                ctk.CTkLabel(
                    top_bar,
                    text=sec_name,
                    font=self._get_font(size=12, weight="bold"),
                    text_color=("gray40", "#a7f3d0"),
                ).pack(side="left")

        # Note text content (Comfortable large font 22px)
        content_box = ctk.CTkLabel(
            bubble,
            text=note.content,
            font=ctk.CTkFont(family=font_family, size=self.chat_font_size),
            text_color=("black", "white"),
            wraplength=640,
            justify=text_align,
            anchor="e" if has_arabic else "w",
        )
        content_box.pack(anchor="e" if has_arabic else "w", padx=14, pady=(6, 4))

        # Bottom row of bubble: Action buttons + Timestamp
        bottom_bar = ctk.CTkFrame(bubble, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=10, pady=(2, 6))

        # Left: Quick action buttons directly packed
        copy_btn = ctk.CTkButton(
            bottom_bar,
            text="📋 نسخ",
            width=54,
            height=26,
            font=self._get_font(size=11),
            fg_color=("white", "#128c7e"),
            hover_color=("#bbf7d0", "#075e54"),
            text_color=("black", "white"),
            corner_radius=6,
            command=lambda n=note: self._copy_note(n),
        )
        copy_btn.pack(side="left", padx=2)

        star_icon = "⭐" if note.is_starred else "☆"
        star_btn = ctk.CTkButton(
            bottom_bar,
            text=star_icon,
            width=30,
            height=26,
            font=self._get_font(size=12),
            fg_color=("white", "#128c7e"),
            hover_color=("#bbf7d0", "#075e54"),
            text_color=("#eab308", "#fde047") if note.is_starred else ("black", "white"),
            corner_radius=6,
            command=lambda n=note: self._toggle_star_note(n),
        )
        star_btn.pack(side="left", padx=2)

        if self.navigate_to_snippet_callback:
            snip_btn = ctk.CTkButton(
                bottom_bar,
                text="✂️ اختصار",
                width=62,
                height=26,
                font=self._get_font(size=11),
                fg_color=("white", "#128c7e"),
                hover_color=("#bbf7d0", "#075e54"),
                text_color=("black", "white"),
                corner_radius=6,
                command=lambda n=note: self._convert_to_snippet(n),
            )
            snip_btn.pack(side="left", padx=2)

        del_btn = ctk.CTkButton(
            bottom_bar,
            text="🗑️",
            width=30,
            height=26,
            font=self._get_font(size=11),
            fg_color=("white", "#128c7e"),
            hover_color=("#fecaca", "#991b1b"),
            text_color=("#dc2626", "#f87171"),
            corner_radius=6,
            command=lambda n=note: self._delete_note_instant(n),
        )
        del_btn.pack(side="left", padx=2)

        # Right: Time + Blue Checkmark (WhatsApp ✓✓)
        time_str = self._format_note_time(note.created_at)
        check_lbl = ctk.CTkLabel(
            bottom_bar,
            text="✓✓",
            font=self._get_font(size=12, weight="bold"),
            text_color="#53bdeb",
        )
        check_lbl.pack(side="right", padx=(2, 4))

        time_lbl = ctk.CTkLabel(
            bottom_bar,
            text=time_str,
            font=self._get_font(size=11),
            text_color=("gray40", "gray75"),
        )
        time_lbl.pack(side="right", padx=(4, 0))

        self._attach_bubble_context_menu(bubble, content_box, note)

    def _format_note_time(self, created_at_str: str) -> str:
        try:
            dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return created_at_str[-8:]

    def _copy_note(self, note: ChatNote):
        try:
            self.clipboard_clear()
            self.clipboard_append(note.content)
            self.toast_callback("تم نسخ الملاحظة إلى الحافظة! 📋")
        except Exception as e:
            self.toast_callback(f"فشل النسخ: {e}", error=True)

    def _toggle_star_note(self, note: ChatNote):
        try:
            new_state = toggle_star_chat_note(note.id)
            note.is_starred = new_state
            self.refresh_chat(scroll_to_bottom=False)
            status_text = "تم تمييز الملاحظة بنجمة ⭐" if new_state else "تمت إزالة النجمة"
            self.toast_callback(status_text)
        except Exception as e:
            self.toast_callback(f"خطأ: {e}", error=True)

    def _delete_note_instant(self, note: ChatNote):
        try:
            delete_chat_note(note.id)
            self.refresh_sections()
            self.refresh_chat(scroll_to_bottom=False)
            self.toast_callback("تم حذف الملاحظة 🗑️")
        except Exception as e:
            self.toast_callback(f"فشل الحذف: {e}", error=True)

    def _convert_to_snippet(self, note: ChatNote):
        if self.navigate_to_snippet_callback:
            self.navigate_to_snippet_callback(note.content)
            self.toast_callback("تم نقل الملاحظة إلى محرر الاختصارات ✂️")

    def _confirm_clear_all(self):
        if not self._notes_cache:
            self.toast_callback("السجل فارغ بالفعل.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("تأكيد المسح")
        dialog.geometry("400x190")
        dialog.transient(self)
        dialog.grab_set()

        sec_label = "الحالي" if self.selected_section_id else "الكلي"
        ctk.CTkLabel(
            dialog,
            text=f"⚠️ هل أنت متأكد من مسح جميع الملاحظات في هذا القسم {sec_label}؟",
            font=self._get_font(size=14, weight="bold"),
            text_color="#dc2626",
            wraplength=360,
        ).pack(pady=(25, 10))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=15)

        def do_clear():
            dialog.destroy()
            try:
                clear_all_chat_notes(section_id=self.selected_section_id)
                self.refresh_sections()
                self.refresh_chat()
                self.toast_callback("تم مسح الملاحظات بنجاح 🗑️")
            except Exception as e:
                self.toast_callback(f"فشل المسح: {e}", error=True)

        ctk.CTkButton(
            btn_row,
            text="نعم، امسح",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            width=120,
            height=34,
            font=self._get_font(size=13, weight="bold"),
            command=do_clear,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row,
            text="إلغاء",
            fg_color="gray",
            width=100,
            height=34,
            font=self._get_font(size=13),
            command=dialog.destroy,
        ).pack(side="left", padx=10)

    def _attach_bubble_context_menu(self, bubble, content_box, note: ChatNote):
        menu = tk.Menu(self, tearoff=0, font=(self.chat_font_family, 12))
        menu.add_command(label="📋 نسخ النص", command=lambda: self._copy_note(note))
        menu.add_command(
            label="⭐ إلغاء/تمييز بنجمة" if note.is_starred else "⭐ تمييز بنجمة",
            command=lambda: self._toggle_star_note(note),
        )
        if self.navigate_to_snippet_callback:
            menu.add_command(label="✂️ تحويل إلى اختصار (Snippet)", command=lambda: self._convert_to_snippet(note))
        menu.add_separator()
        menu.add_command(label="🗑️ حذف الملاحظة", command=lambda: self._delete_note_instant(note))

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        for widget in [bubble, content_box]:
            widget.bind("<Button-3>", popup)
