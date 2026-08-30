import customtkinter as ctk

from snipglide.database.search_repo import get_search_result_body, search_all


class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, toast_callback, navigate_to_snippet_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.toast_callback = toast_callback
        self.navigate_to_snippet_callback = navigate_to_snippet_callback
        self._render_job = None
        self._search_job = None
        self._last_query = None
        self._last_results = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Unified Search", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 10)
        )

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search snippets, notes, and clipboard...")
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._schedule_search())

        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self._show_empty("Type to search.")

    def _schedule_search(self):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(160, self._run_search)

    def _run_search(self):
        self._search_job = None
        if self._render_job:
            self.after_cancel(self._render_job)
            self._render_job = None

        query = self.search_entry.get().strip().lower()
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not query:
            self._show_empty("Type to search.")
            return

        if query == self._last_query:
            results = self._last_results
        else:
            results = search_all(query, limit=40)
            self._last_query = query
            self._last_results = results

        if not results:
            self._show_empty("No results found.")
            return

        self._render_search_batch(results, start_idx=0, batch_size=15)

    def _render_search_batch(self, results, start_idx, batch_size):
        end_idx = min(start_idx + batch_size, len(results))
        for i in range(start_idx, end_idx):
            item = results[i]
            self._create_result_row(
                item["kind"],
                item["title"],
                item["body"],
                lambda kind=item["kind"], ref=item["ref"]: self._copy_result_body(kind, ref),
            )

        if end_idx < len(results):
            self._render_job = self.after(
                5,
                lambda: self._render_search_batch(results, end_idx, batch_size),
            )
        else:
            self._render_job = None

    def _create_result_row(self, kind: str, title: str, body: str, action):
        row = ctk.CTkFrame(self.results_frame, fg_color=("gray90", "gray15"))
        row.pack(fill="x", pady=5, padx=5)
        row.grid_columnconfigure(0, weight=1)

        preview = body.strip().replace("\n", " ")
        if len(preview) > 140:
            preview = preview[:140] + "..."

        ctk.CTkLabel(row, text=f"{kind}: {title}", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(8, 2)
        )
        ctk.CTkLabel(row, text=preview, anchor="w", justify="left", text_color=("gray35", "gray70")).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 8)
        )
        ctk.CTkButton(row, text="Copy", width=70, height=28, command=action).grid(
            row=0, column=1, rowspan=2, padx=10, pady=8
        )

    def _copy_text(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.toast_callback("Copied to clipboard.")

    def _copy_result_body(self, kind: str, ref: str):
        text = get_search_result_body(kind, ref)
        if text:
            self._copy_text(text)
        else:
            self.toast_callback("Result no longer exists.", error=True)

    def _show_empty(self, message: str):
        ctk.CTkLabel(self.results_frame, text=message, text_color="gray").pack(pady=40)
