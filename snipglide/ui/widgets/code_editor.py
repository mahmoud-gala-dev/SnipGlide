import re
import tkinter as tk
import customtkinter as ctk


class CodeEditor(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._current_font_size = 13
        self._current_line_spacing = 4
        self._line_numbers_job = None
        self._rtl_job = None
        self._last_line_count = None
        self._last_rtl_text = None

        # ── Toolbar: Font Size + Line Height ──────────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 2))

        ctk.CTkLabel(toolbar, text="Font:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))

        self.font_size_slider = ctk.CTkSlider(
            toolbar, from_=10, to=24, number_of_steps=14, width=100,
            command=self._on_font_size_change,
        )
        self.font_size_slider.set(self._current_font_size)
        self.font_size_slider.pack(side="left", padx=2)

        self.font_size_label = ctk.CTkLabel(toolbar, text="13", font=ctk.CTkFont(size=11), width=24)
        self.font_size_label.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(toolbar, text="Line:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))

        self.line_spacing_slider = ctk.CTkSlider(
            toolbar, from_=0, to=12, number_of_steps=12, width=90,
            command=self._on_line_spacing_change,
        )
        self.line_spacing_slider.set(self._current_line_spacing)
        self.line_spacing_slider.pack(side="left", padx=2)

        self.line_spacing_label = ctk.CTkLabel(toolbar, text="4", font=ctk.CTkFont(size=11), width=24)
        self.line_spacing_label.pack(side="left", padx=(0, 4))

        # ── Line Numbers ──────────────────────────────────────────
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        ln_bg = "#1e1e1e" if is_dark else "#f0f0f0"
        ln_fg = "#858585" if is_dark else "#6b7280"

        self.line_numbers = tk.Text(
            self, width=4, padx=5, takefocus=0, border=0,
            background=ln_bg, foreground=ln_fg,
            state="disabled", font=("Consolas", self._current_font_size),
        )
        self.line_numbers.grid(row=1, column=0, sticky="nsew")

        # ── Main Text Box ─────────────────────────────────────────
        self.textbox_wrapper = ctk.CTkTextbox(self, font=("Consolas", self._current_font_size), wrap="none")
        self.textbox_wrapper.grid(row=1, column=1, sticky="nsew")

        self.textbox = self.textbox_wrapper._textbox
        self.textbox.configure(spacing1=self._current_line_spacing)
        self.textbox.bind("<KeyRelease>", self._on_key_release)
        self.textbox.bind("<Configure>", self._on_configure)

        from snipglide.utils.helpers import create_context_menu
        create_context_menu(self.textbox)

        # Apply Arabic‑aware RTL + Tajawal font support
        self._bind_arabic_font_switch()

        self.update_line_numbers()

    # ── Arabic / Tajawal auto‑switch ──────────────────────────
    def _bind_arabic_font_switch(self):
        """Detect Arabic text and apply per-line RTL tags + Tajawal font."""
        # Pre-configure RTL and LTR justify tags
        self.textbox.tag_configure("rtl", justify="right")
        self.textbox.tag_configure("ltr", justify="left")
        self._is_arabic_mode = False

        def reshape_arabic(text: str) -> str:
            """Reshape Arabic text so letters connect correctly in Tkinter."""
            try:
                import arabic_reshaper
                from bidi.algorithm import get_display
                reshaped = arabic_reshaper.reshape(text)
                return get_display(reshaped)
            except Exception:
                return text

        def apply_rtl_per_line():
            """Apply RTL or LTR justify tag to every line based on content."""
            try:
                current_text = self.textbox.get("1.0", "end-1c")
                if current_text == self._last_rtl_text:
                    return getattr(self, "_is_arabic_mode", False)

                self._last_rtl_text = current_text
                self.textbox.tag_remove("rtl", "1.0", "end")
                self.textbox.tag_remove("ltr", "1.0", "end")
                total_lines = int(self.textbox.index("end-1c").split(".")[0])
                if total_lines > 1000:
                    any_arabic = bool(re.search(r"[\u0600-\u06FF]", current_text))
                    tag = "rtl" if any_arabic else "ltr"
                    self.textbox.tag_add(tag, "1.0", "end")
                    return any_arabic

                any_arabic = False
                for lineno in range(1, total_lines + 1):
                    line_text = self.textbox.get(f"{lineno}.0", f"{lineno}.end")
                    if re.search(r"[\u0600-\u06FF]", line_text):
                        self.textbox.tag_add("rtl", f"{lineno}.0", f"{lineno}.end+1c")
                        any_arabic = True
                    else:
                        self.textbox.tag_add("ltr", f"{lineno}.0", f"{lineno}.end+1c")
                return any_arabic
            except Exception:
                return False

        def on_key(event=None):
            self._rtl_job = None
            try:
                has_arabic = apply_rtl_per_line()
                from snipglide.core.config import get_arabic_font_family
                if has_arabic and not self._is_arabic_mode:
                    family = get_arabic_font_family()
                    self.textbox_wrapper.configure(font=(family, self._current_font_size))
                    self._is_arabic_mode = True
                elif not has_arabic and self._is_arabic_mode:
                    self.textbox_wrapper.configure(font=("Consolas", self._current_font_size))
                    self._is_arabic_mode = False
            except Exception:
                pass

        def schedule_rtl_check(event=None):
            if self._rtl_job:
                self.after_cancel(self._rtl_job)
            self._rtl_job = self.after(220, on_key)

        self.textbox.bind("<KeyRelease>", schedule_rtl_check, add="+")
        # Also apply on paste
        self.textbox.bind("<<Paste>>", lambda e: self.after(80, on_key), add="+")
        # Run once to set initial state
        self.after(300, on_key)

    # ── Toolbar callbacks ─────────────────────────────────────
    def _on_font_size_change(self, value):
        size = int(value)
        self._current_font_size = size
        self.font_size_label.configure(text=str(size))
        from snipglide.core.config import get_arabic_font_family
        if getattr(self, "_is_arabic_mode", False):
            self.textbox_wrapper.configure(font=(get_arabic_font_family(), size))
        else:
            self.textbox_wrapper.configure(font=("Consolas", size))
        self.line_numbers.configure(font=("Consolas", size))

    def _on_line_spacing_change(self, value):
        spacing = int(value)
        self._current_line_spacing = spacing
        self.line_spacing_label.configure(text=str(spacing))
        self.textbox.configure(spacing1=spacing)

    # ── Public API ────────────────────────────────────────────
    def get_text(self) -> str:
        return self.textbox_wrapper.get("1.0", "end-1c")

    def set_text(self, text: str):
        self.textbox_wrapper.delete("1.0", "end")
        self.textbox_wrapper.insert("1.0", text)
        self._last_line_count = None
        self._last_rtl_text = None
        self.update_line_numbers()
        # Re-evaluate RTL after loading text
        self.after(80, lambda: self.textbox.event_generate("<KeyRelease>"))

    def update_line_numbers(self):
        self._line_numbers_job = None
        lines_count = int(self.textbox.index("end-1c").split(".")[0])
        if lines_count == self._last_line_count:
            return

        self._last_line_count = lines_count
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")

        lines_text = "\n".join(str(i) for i in range(1, lines_count + 1))

        self.line_numbers.insert("1.0", lines_text)
        self.line_numbers.configure(state="disabled")

    # ── Internal events ───────────────────────────────────────
    def _on_key_release(self, event):
        self._schedule_line_numbers_update()

    def _on_configure(self, event):
        self._schedule_line_numbers_update()

    def _schedule_line_numbers_update(self):
        if self._line_numbers_job:
            self.after_cancel(self._line_numbers_job)
        self._line_numbers_job = self.after(120, self.update_line_numbers)

    # ── Syntax highlighting ───────────────────────────────────
    def setup_highlight_tags(self):
        token_colors = {
            "Token.Keyword": ("#569cd6", "#0000ff"),
            "Token.String": ("#ce9178", "#a31515"),
            "Token.Comment": ("#6a9955", "#008000"),
            "Token.Number": ("#b5cea8", "#098658"),
            "Token.Name.Function": ("#dcdcaa", "#795e26"),
            "Token.Name.Class": ("#4ec9b0", "#267f99"),
            "Token.Operator": ("#d4d4d4", "#000000"),
        }
        self.is_dark = ctk.get_appearance_mode().lower() == "dark"
        for tag_name, colors in token_colors.items():
            color = colors[0] if self.is_dark else colors[1]
            self.textbox.tag_configure(tag_name, foreground=color)

        # Update line numbers colors for current mode
        ln_bg = "#1e1e1e" if self.is_dark else "#f0f0f0"
        ln_fg = "#858585" if self.is_dark else "#6b7280"
        self.line_numbers.configure(background=ln_bg, foreground=ln_fg)

    def highlight_code(self, lang: str):
        self.setup_highlight_tags()

        for tag in self.textbox.tag_names():
            if tag.startswith("Token."):
                self.textbox.tag_remove(tag, "1.0", "end")

        if lang == "Plain Text":
            return

        try:
            from pygments import lex
            from pygments.lexers import get_lexer_by_name
            lexer = get_lexer_by_name(lang.lower())
        except Exception:
            return

        code = self.get_text()
        line = 1
        column = 0
        for token_type, value in lex(code, lexer):
            start_idx = f"{line}.{column}"
            newlines = value.count("\n")
            if newlines > 0:
                parts = value.split("\n")
                line += newlines
                column = len(parts[-1])
            else:
                column += len(value)
            end_idx = f"{line}.{column}"

            t_str = str(token_type)
            for conf_tag in [
                "Token.Keyword", "Token.String", "Token.Comment",
                "Token.Number", "Token.Name.Function", "Token.Name.Class",
                "Token.Operator",
            ]:
                if t_str.startswith(conf_tag):
                    self.textbox.tag_add(conf_tag, start_idx, end_idx)
                    break
