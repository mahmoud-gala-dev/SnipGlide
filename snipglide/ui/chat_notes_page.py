import re
import tkinter as tk
from datetime import datetime
import customtkinter as ctk

from snipglide.database.chat_note_repo import (
    add_chat_note,
    clear_all_chat_notes,
    delete_chat_note,
    get_all_chat_notes,
    get_chat_notes_count,
    toggle_star_chat_note,
)
from snipglide.models.chat_note import ChatNote
from snipglide.utils.helpers import apply_rtl_support, create_context_menu, safe_clear_frame
from snipglide.core.config import get_arabic_font_family


class ChatNotesPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, navigate_to_snippet_callback=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.navigate_to_snippet_callback = navigate_to_snippet_callback

        self.starred_filter_active = False
        self._search_job = None
        self._notes_cache = []

        # Grid configuration: Row 0 Header, Row 1 Chat Messages, Row 2 Compose Bar
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_chat_feed()
        self._build_compose_bar()

        # Initial load
        self.after(100, self.refresh_chat)

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color=("gray92", "#111b21"), corner_radius=12)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 8))
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Avatar & Title (WhatsApp Green Avatar)
        left_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        left_box.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        avatar = ctk.CTkLabel(
            left_box,
            text="💬",
            font=ctk.CTkFont(size=20),
            fg_color="#25D366",
            text_color="white",
            width=42,
            height=42,
            corner_radius=21,
        )
        avatar.pack(side="left", padx=(0, 10))

        title_info = ctk.CTkFrame(left_box, fg_color="transparent")
        title_info.pack(side="left")

        title_lbl = ctk.CTkLabel(
            title_info,
            text="Quick Chat Notes",
            font=ctk.CTkFont(size=17, weight="bold"),
            anchor="w",
        )
        title_lbl.pack(anchor="w")

        self.count_badge = ctk.CTkLabel(
            title_info,
            text="سجل ملاحظاتك ورسائلك السريعة بأسلوب الواتساب",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        )
        self.count_badge.pack(anchor="w")

        # Right-side action controls
        right_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_box.grid(row=0, column=1, sticky="e", padx=15, pady=10)

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            right_box,
            placeholder_text="🔍 بحث في الملاحظات...",
            width=180,
            height=34,
            corner_radius=8,
        )
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        apply_rtl_support(self.search_entry)
        create_context_menu(self.search_entry)

        # Star Filter Button
        self.star_btn = ctk.CTkButton(
            right_box,
            text="⭐ المفضلة",
            width=80,
            height=34,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            text_color=("black", "white"),
            corner_radius=8,
            command=self._toggle_star_filter,
        )
        self.star_btn.pack(side="left", padx=4)

        # Export Button
        self.export_btn = ctk.CTkButton(
            right_box,
            text="📋 نسخ الكل",
            width=80,
            height=34,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            text_color=("black", "white"),
            corner_radius=8,
            command=self._copy_all_notes,
        )
        self.export_btn.pack(side="left", padx=4)

        # Clear All Button
        self.clear_btn = ctk.CTkButton(
            right_box,
            text="🗑️ مسح الكل",
            width=80,
            height=34,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="white",
            corner_radius=8,
            command=self._confirm_clear_all,
        )
        self.clear_btn.pack(side="left", padx=(4, 0))

    def _build_chat_feed(self):
        # Chat feed scrollable container
        self.chat_container = ctk.CTkFrame(self, fg_color=("gray95", "#0b141a"), corner_radius=12)
        self.chat_container.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
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
        self.compose_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.compose_frame.grid_columnconfigure(1, weight=1)

        # Quick tools button on the left of input bar
        tools_frame = ctk.CTkFrame(self.compose_frame, fg_color="transparent")
        tools_frame.grid(row=0, column=0, padx=(10, 5), pady=8)

        self.time_stamp_btn = ctk.CTkButton(
            tools_frame,
            text="🕒",
            width=36,
            height=36,
            corner_radius=18,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            command=self._insert_timestamp,
        )
        self.time_stamp_btn.pack(side="left", padx=2)

        self.star_new_var = ctk.BooleanVar(value=False)
        self.star_new_btn = ctk.CTkButton(
            tools_frame,
            text="⭐",
            width=36,
            height=36,
            corner_radius=18,
            fg_color=("gray80", "#1f2c34"),
            hover_color=("gray70", "#2a3942"),
            command=self._toggle_new_note_star,
        )
        self.star_new_btn.pack(side="left", padx=2)

        # Message Textbox
        self.message_input = ctk.CTkTextbox(
            self.compose_frame,
            height=54,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            wrap="word",
        )
        self.message_input.grid(row=0, column=1, sticky="ew", padx=5, pady=8)
        self.message_input.bind("<Return>", self._handle_return_key)
        apply_rtl_support(self.message_input)
        create_context_menu(self.message_input)

        # Right Send Action
        send_frame = ctk.CTkFrame(self.compose_frame, fg_color="transparent")
        send_frame.grid(row=0, column=2, padx=(5, 10), pady=8)

        self.send_btn = ctk.CTkButton(
            send_frame,
            text="➤ إرسال",
            width=75,
            height=42,
            corner_radius=10,
            fg_color="#25D366",
            hover_color="#1da851",
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._send_message,
        )
        self.send_btn.pack(side="left")

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
        # Shift+Return or Ctrl+Return allows new lines; plain Return sends the message
        if event.state & 0x0001 or event.state & 0x0004:  # Shift or Ctrl pressed
            return None  # Let default newline insertion happen
        self._send_message()
        return "break"  # Prevent extra newline after send

    def _send_message(self):
        content = self.message_input.get("1.0", "end-1c").strip()
        if not content:
            return

        is_starred = self.star_new_var.get()
        try:
            new_note = add_chat_note(content=content, is_starred=is_starred)
            self.message_input.delete("1.0", "end")

            # Reset star button for next note
            if self.star_new_var.get():
                self.star_new_var.set(False)
                self.star_new_btn.configure(fg_color=("gray80", "#1f2c34"), text_color=("black", "white"))

            # If there's an active search filter or empty state, full refresh
            query = self.search_entry.get().strip()
            if query or not self._notes_cache:
                self.refresh_chat(scroll_to_bottom=True)
            else:
                self._notes_cache.append(new_note)
                self._render_chat_bubble(new_note)
                total_count = get_chat_notes_count()
                self.count_badge.configure(text=f"إجمالي الملاحظات: {total_count} • المعروض حالياً: {len(self._notes_cache)}")
                self.after(30, self._scroll_to_end)

            self.toast_callback("تم حفظ الملاحظة بنجاح 💬")
        except Exception as e:
            self.toast_callback(f"فشل الحفظ: {e}", error=True)


    def _on_search_key(self, _event=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(200, self.refresh_chat)

    def _toggle_star_filter(self):
        self.starred_filter_active = not self.starred_filter_active
        if self.starred_filter_active:
            self.star_btn.configure(fg_color="#f59e0b", text_color="white", text="⭐ المفضلة فقط")
        else:
            self.star_btn.configure(fg_color=("gray80", "#1f2c34"), text_color=("black", "white"), text="⭐ المفضلة")
        self.refresh_chat()

    def refresh_chat(self, scroll_to_bottom: bool = True):
        query = self.search_entry.get().strip()
        notes = get_all_chat_notes(query=query, starred_only=self.starred_filter_active)
        self._notes_cache = notes

        total_count = get_chat_notes_count()
        current_count = len(notes)
        filter_text = " (المفضلة)" if self.starred_filter_active else ""
        if query:
            filter_text += f" (نتائج البحث عن: '{query}')"

        self.count_badge.configure(text=f"إجمالي الملاحظات: {total_count} • المعروض حالياً: {current_count}{filter_text}")

        safe_clear_frame(self.chat_scroll)

        if not notes:
            self._render_empty_state(query)
            return

        last_date_str = None
        for note in notes:
            # Check if we should insert a date header divider
            note_date_str = self._format_date_header(note.created_at)
            if note_date_str != last_date_str:
                self._render_date_divider(note_date_str)
                last_date_str = note_date_str

            self._render_chat_bubble(note)

        if scroll_to_bottom:
            self.after(50, self._scroll_to_end)

    def _scroll_to_end(self):
        try:
            # CustomTkinter CTkScrollableFrame uses an internal canvas
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
        divider_frame.pack(fill="x", pady=(10, 6))

        pill = ctk.CTkLabel(
            divider_frame,
            text=f"  {text}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("gray85", "#182229"),
            text_color=("gray30", "gray70"),
            corner_radius=10,
            padx=10,
            pady=3,
        )
        pill.pack(anchor="center")

    def _render_empty_state(self, query: str):
        empty_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        empty_frame.pack(fill="both", expand=True, pady=60)

        icon_text = "🔍" if query else "💬"
        ctk.CTkLabel(empty_frame, text=icon_text, font=ctk.CTkFont(size=44)).pack(pady=(0, 10))

        if query:
            msg = f"لم يتم العثور على ملاحظات تطابق '{query}'"
        elif self.starred_filter_active:
            msg = "لا توجد ملاحظات مميزة بنجمة ⭐"
        else:
            msg = "صندوق الملاحظات فارغ.\nاكتب فكرتك أو ملاحظتك في صندوق الكتابة بالأسفل واضغط Enter لحفظها فوراً!"

        ctk.CTkLabel(
            empty_frame,
            text=msg,
            font=ctk.CTkFont(size=14),
            text_color="gray",
            justify="center",
        ).pack()

    def _render_chat_bubble(self, note: ChatNote):
        # Determine language & direction
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", note.content))
        font_family = get_arabic_font_family() if has_arabic else "Segoe UI"
        text_align = "right" if has_arabic else "left"

        # Outer row container aligned to WhatsApp outgoing style (right)
        row_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        row_frame.pack(fill="x", padx=10, pady=4)
        row_frame.grid_columnconfigure(0, weight=1)

        # Bubble Frame
        # WhatsApp colors:
        # Dark mode: #005c4b (outgoing message green) or #1f2c34
        # Light mode: #d9fdd3 (outgoing message soft green)
        bubble_bg = ("#d9fdd3", "#005c4b") if not note.is_starred else ("#fef08a", "#064e3b")
        border_color = "#f59e0b" if note.is_starred else None
        border_width = 1 if note.is_starred else 0

        bubble = ctk.CTkFrame(
            row_frame,
            fg_color=bubble_bg,
            border_color=border_color,
            border_width=border_width,
            corner_radius=14,
        )
        bubble.pack(anchor="e", padx=(40, 5), pady=2)
        bubble.grid_columnconfigure(0, weight=1)

        # Top row of bubble (if starred or has quick tag)
        if note.is_starred:
            top_bar = ctk.CTkFrame(bubble, fg_color="transparent")
            top_bar.pack(fill="x", padx=10, pady=(4, 0))
            star_indicator = ctk.CTkLabel(
                top_bar,
                text="⭐ مميزة",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=("#854d0e", "#fde047"),
            )
            star_indicator.pack(side="left")

        # Note text content (selectable label or wrapped textbox)
        content_box = ctk.CTkLabel(
            bubble,
            text=note.content,
            font=ctk.CTkFont(family=font_family, size=13),
            text_color=("black", "white"),
            wraplength=620,
            justify=text_align,
            anchor="e" if has_arabic else "w",
        )
        content_box.pack(anchor="e" if has_arabic else "w", padx=12, pady=(6, 2))

        # Bottom row of bubble: Time, Checkmarks, and Quick Action buttons
        bottom_bar = ctk.CTkFrame(bubble, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=8, pady=(2, 6))

        # Left: Quick action buttons (Copy, Star, To Snippet, Delete)
        actions_frame = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        actions_frame.pack(side="left", padx=2)

        copy_btn = ctk.CTkButton(
            actions_frame,
            text="📋 نسخ",
            width=48,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color=("white", "#128c7e"),
            hover_color=("#bbf7d0", "#075e54"),
            text_color=("black", "white"),
            corner_radius=6,
            command=lambda n=note: self._copy_note(n),
        )
        copy_btn.pack(side="left", padx=2)

        star_icon = "⭐" if note.is_starred else "☆"
        star_btn = ctk.CTkButton(
            actions_frame,
            text=star_icon,
            width=28,
            height=24,
            font=ctk.CTkFont(size=12),
            fg_color=("white", "#128c7e"),
            hover_color=("#bbf7d0", "#075e54"),
            text_color=("#eab308", "#fde047") if note.is_starred else ("black", "white"),
            corner_radius=6,
            command=lambda n=note: self._toggle_star_note(n),
        )
        star_btn.pack(side="left", padx=2)

        if self.navigate_to_snippet_callback:
            snip_btn = ctk.CTkButton(
                actions_frame,
                text="✂️ اختصار",
                width=55,
                height=24,
                font=ctk.CTkFont(size=11),
                fg_color=("white", "#128c7e"),
                hover_color=("#bbf7d0", "#075e54"),
                text_color=("black", "white"),
                corner_radius=6,
                command=lambda n=note: self._convert_to_snippet(n),
            )
            snip_btn.pack(side="left", padx=2)

        del_btn = ctk.CTkButton(
            actions_frame,
            text="🗑️",
            width=28,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color=("white", "#128c7e"),
            hover_color=("#fecaca", "#991b1b"),
            text_color=("#dc2626", "#f87171"),
            corner_radius=6,
            command=lambda n=note: self._delete_note_instant(n),
        )
        del_btn.pack(side="left", padx=2)

        # Right: Time + Blue Checkmark (WhatsApp ✓✓)
        time_frame = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        time_frame.pack(side="right", padx=4)

        time_str = self._format_note_time(note.created_at)
        time_lbl = ctk.CTkLabel(
            time_frame,
            text=time_str,
            font=ctk.CTkFont(size=10),
            text_color=("gray40", "gray75"),
        )
        time_lbl.pack(side="left", padx=(0, 4))

        check_lbl = ctk.CTkLabel(
            time_frame,
            text="✓✓",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#53bdeb",  # WhatsApp double blue check color
        )
        check_lbl.pack(side="left")

        # Context menu for right click
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
            self.refresh_chat(scroll_to_bottom=False)
            self.toast_callback("تم حذف الملاحظة 🗑️")
        except Exception as e:
            self.toast_callback(f"فشل الحذف: {e}", error=True)

    def _convert_to_snippet(self, note: ChatNote):
        if self.navigate_to_snippet_callback:
            self.navigate_to_snippet_callback(note.content)
            self.toast_callback("تم نقل الملاحظة إلى محرر الاختصارات ✂️")

    def _copy_all_notes(self):
        if not self._notes_cache:
            self.toast_callback("لا توجد ملاحظات لنسخها.", error=True)
            return

        full_text = "\n\n---\n\n".join(
            f"[{n.created_at}] {'⭐ ' if n.is_starred else ''}\n{n.content}" for n in self._notes_cache
        )
        try:
            self.clipboard_clear()
            self.clipboard_append(full_text)
            self.toast_callback(f"تم نسخ {len(self._notes_cache)} ملاحظة إلى الحافظة! 📋")
        except Exception as e:
            self.toast_callback(f"فشل النسخ: {e}", error=True)

    def _confirm_clear_all(self):
        if not self._notes_cache:
            self.toast_callback("السجل فارغ بالفعل.")
            return

        # Simple confirmation dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("تأكيد مسح الكل")
        dialog.geometry("380x180")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="⚠️ هل أنت متأكد من مسح جميع الملاحظات في الشات؟",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#dc2626",
            wraplength=340,
        ).pack(pady=(25, 10))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=15)

        def do_clear():
            dialog.destroy()
            try:
                clear_all_chat_notes()
                self.refresh_chat()
                self.toast_callback("تم مسح جميع الملاحظات بنجاح 🗑️")
            except Exception as e:
                self.toast_callback(f"فشل المسح: {e}", error=True)

        ctk.CTkButton(
            btn_row,
            text="نعم، امسح الكل",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            width=120,
            command=do_clear,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row,
            text="إلغاء",
            fg_color="gray",
            width=90,
            command=dialog.destroy,
        ).pack(side="left", padx=10)

    def _attach_bubble_context_menu(self, bubble, content_box, note: ChatNote):
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 12))
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
