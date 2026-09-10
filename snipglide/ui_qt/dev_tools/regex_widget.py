from typing import Optional, Callable, Any
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QCursor, QTextCharFormat, QColor, QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QCheckBox, QSplitter, QListWidget, QListWidgetItem,
    QFrame, QDialog, QInputDialog, QMessageBox
)

from snipglide.services.regex_service import RegexService
from snipglide.models.saved_regex import SavedRegex
from snipglide.database.regex_repo import (
    create_regex, get_all_regexes, search_regexes, delete_regex, toggle_favorite
)
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    show_status_badge, copy_text_to_clipboard
)


class RegexMatchWorker(QThread):
    """Background worker for non-blocking regex matching with ReDoS protection."""
    result_ready = Signal(int, bool, list, str)

    def __init__(self, gen: int, pattern: str, text: str, flags: str, timeout: float = 2.0):
        super().__init__()
        self.gen = gen
        self.pattern = pattern
        self.text = text
        self.flags = flags
        self.timeout = timeout
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if self.is_cancelled:
            return
        ok, matches, summary = RegexService.find_matches(
            self.pattern, self.text, flags_str=self.flags, timeout=self.timeout
        )
        if not self.is_cancelled:
            self.result_ready.emit(self.gen, ok, matches, summary)


class RegexPlaygroundWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback

        # Debounce timer for live matching (250ms)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._run_matching_now)

        self._current_matches: list[dict[str, Any]] = []
        self._worker_gen: int = 0
        self._current_worker: Optional[RegexMatchWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ── Row 1: Pattern Input & Action Buttons ──
        p_row = QHBoxLayout()
        lbl_p = QLabel("نمط Regex:")
        lbl_p.setStyleSheet("font-weight: bold; color: #f0f2f5; font-size: 14px; min-width: 80px;")
        p_row.addWidget(lbl_p)

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText(r"مثال: ([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
        self.pattern_input.setStyleSheet("""
            QLineEdit {
                background-color: #0b141a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border: 1.5px solid #202c33;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.pattern_input.textChanged.connect(self._schedule_live_match)
        p_row.addWidget(self.pattern_input, stretch=1)

        btn_save = create_tool_button("💾 حفظ (Ctrl+S)", "#10b981", self.save_regex_dialog)
        btn_library = create_tool_button("📂 المكتبة المحفوظة", "#8b5cf6", self.open_saved_library)
        p_row.addWidget(btn_save)
        p_row.addWidget(btn_library)
        layout.addLayout(p_row)

        # ── Row 2: Flags & Match Count Badge ──
        f_row = QHBoxLayout()
        lbl_flags = QLabel("الخيارات (Flags):")
        lbl_flags.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 13px;")
        f_row.addWidget(lbl_flags)

        self.chk_i = QCheckBox("تجاهل حالة الأحرف (i)")
        self.chk_m = QCheckBox("أسطر متعددة (m)")
        self.chk_s = QCheckBox("النقطة تشمل السطر الجديد (s)")
        self.chk_x = QCheckBox("تجاهل المسافات والتعليقات (x)")

        for chk in (self.chk_i, self.chk_m, self.chk_s, self.chk_x):
            chk.setStyleSheet("color: #e9edef; font-size: 12px; font-weight: bold;")
            chk.stateChanged.connect(self._schedule_live_match)
            f_row.addWidget(chk)

        f_row.addStretch()

        self.match_badge = QLabel("0 مطابقة")
        self.match_badge.setStyleSheet("background-color: #182229; color: #93c5fd; font-weight: bold; padding: 5px 12px; border-radius: 6px; border: 1px solid #2a3942;")
        f_row.addWidget(self.match_badge)
        layout.addLayout(f_row)

        # Status / Error Label
        self.status_lbl = QLabel("")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        # ── Splitter: Test Text (Left) & Groups/Matches (Right) ──
        splitter = QSplitter(Qt.Horizontal)

        # Left Column: Test Text
        left_box = QWidget()
        l_layout = QVBoxLayout(left_box)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(6)

        lbl_test = QLabel("نص الاختبار (Test Text):")
        lbl_test.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 13px;")
        l_layout.addWidget(lbl_test)

        self.test_editor = create_code_editor("اكتب أو الصق نص الاختبار هنا لفحص مطابقات الـ Regex فورياً...")
        self.test_editor.textChanged.connect(self._schedule_live_match)
        l_layout.addWidget(self.test_editor, stretch=1)
        splitter.addWidget(left_box)

        # Right Column: Match details & Captured Groups
        right_box = QWidget()
        r_layout = QVBoxLayout(right_box)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(6)

        lbl_groups = QLabel("تفاصيل المطابقات والمجموعات (Match Details & Groups):")
        lbl_groups.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 13px;")
        r_layout.addWidget(lbl_groups)

        self.matches_list = QListWidget()
        self.matches_list.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 8px 10px;
                border-radius: 6px;
                margin-bottom: 4px;
                border: 1px solid #2a3942;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #202c33;
            }
        """)
        r_layout.addWidget(self.matches_list, stretch=1)
        splitter.addWidget(right_box)

        splitter.setSizes([550, 450])
        layout.addWidget(splitter, stretch=1)

        # ── Replacement Bar ──
        rep_box = QFrame()
        rep_box.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 10px; padding: 10px;")
        r_box_layout = QVBoxLayout(rep_box)
        r_box_layout.setSpacing(8)

        rep_row = QHBoxLayout()
        lbl_rep = QLabel("الاستبدال (Replacement):")
        lbl_rep.setStyleSheet("font-weight: bold; color: #f0f2f5; font-size: 13px; min-width: 150px;")
        rep_row.addWidget(lbl_rep)

        self.replacement_input = QLineEdit()
        self.replacement_input.setPlaceholderText(r"نص الاستبدال أو المجموعات مثل: \1 أو \g<name>")
        self.replacement_input.setStyleSheet("""
            QLineEdit {
                background-color: #111b21;
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                border: 1px solid #3b4a54;
                padding: 6px 10px;
                border-radius: 6px;
            }
        """)
        rep_row.addWidget(self.replacement_input, stretch=1)

        btn_rep_first = create_tool_button("استبدال أول مطابقة", "#3b82f6", lambda: self._do_replace(replace_all=False))
        btn_rep_all = create_tool_button("استبدال الكل", "#0ea5e9", lambda: self._do_replace(replace_all=True))
        btn_copy_res = create_tool_button("📋 نسخ النتيجة", "#16a34a", self._copy_replacement_result)

        rep_row.addWidget(btn_rep_first)
        rep_row.addWidget(btn_rep_all)
        rep_row.addWidget(btn_copy_res)
        r_box_layout.addLayout(rep_row)

        self.preview_output = create_code_editor("معاينة نتيجة الاستبدال ستظهر هنا...", readonly=True)
        self.preview_output.setFixedHeight(80)
        r_box_layout.addWidget(self.preview_output)

        layout.addWidget(rep_box)

        # Aliases for compatibility
        self.test_input = self.test_editor
        self.replace_input = self.replacement_input
        self.replace_output = self.preview_output
        self.results_table = self.matches_list
        self.match_count_badge = self.match_badge
        self.flag_i = self.chk_i
        self.flag_m = self.chk_m
        self.flag_s = self.chk_s
        self.flag_x = self.chk_x
        self.open_library = self.open_saved_library

    def _run_matching(self):
        self._run_matching_now()
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.wait(3000)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

    def _replace_all(self):
        self._do_replace(replace_all=True)

    def _replace_first(self):
        self._do_replace(replace_all=False)

    def _get_active_flags_string(self) -> str:
        flags = ""
        if self.chk_i.isChecked():
            flags += "i"
        if self.chk_m.isChecked():
            flags += "m"
        if self.chk_s.isChecked():
            flags += "s"
        if self.chk_x.isChecked():
            flags += "x"
        return flags

    def _schedule_live_match(self):
        self._debounce_timer.stop()
        self._debounce_timer.start()

    def _run_matching_now(self):
        pattern = self.pattern_input.text()
        text = self.test_editor.toPlainText()
        flags = self._get_active_flags_string()

        if not pattern:
            self.status_lbl.hide()
            self.match_badge.setText("0 مطابقة")
            self.matches_list.clear()
            self._clear_highlights()
            return

        # Cancel active worker if running
        if self._current_worker:
            self._current_worker.cancel()

        self._worker_gen += 1
        gen = self._worker_gen

        self.match_badge.setText("⏳ جاري الفحص...")
        self._current_worker = RegexMatchWorker(gen, pattern, text, flags, timeout=2.0)
        self._current_worker.result_ready.connect(self._on_matches_computed)
        self._current_worker.start()

    def _on_matches_computed(self, gen: int, ok: bool, matches: list[dict[str, Any]], summary: str):
        if gen != self._worker_gen:
            return  # Discard stale result

        if not ok:
            show_status_badge(self.status_lbl, summary, is_error=True)
            self.match_badge.setText("❌ خطأ Regex")
            self.matches_list.clear()
            self._clear_highlights()
            return

        self.status_lbl.hide()
        self._current_matches = matches
        self.match_badge.setText(f"✓ {len(matches)} مطابقة")

        # Update Matches list
        self.matches_list.clear()
        for m in matches:
            item_text = f"Match #{m['index']}: '{m['text']}' [{m['start']} -> {m['end']}]"
            if m.get("groups"):
                groups_str = ", ".join(f"Group {k}={v}" for k, v in m["groups"].items())
                item_text += f"\n  • {groups_str}"
            if m.get("named_groups"):
                named_str = ", ".join(f"<{k}>={v}" for k, v in m["named_groups"].items())
                item_text += f"\n  • Named: {named_str}"

            item = QListWidgetItem(item_text)
            self.matches_list.addItem(item)

        # Highlight matches in test editor
        self._highlight_matches(matches)

    def _clear_highlights(self):
        cursor = self.test_editor.textCursor()
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        cursor.setCharFormat(fmt)

    def _highlight_matches(self, matches: list[dict[str, Any]]):
        self._clear_highlights()
        if not matches:
            return

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#1e3a8a"))
        fmt.setForeground(QColor("#93c5fd"))
        fmt.setFontWeight(QFont.Bold)

        cursor = self.test_editor.textCursor()
        for m in matches:
            cursor.setPosition(m["start"])
            cursor.setPosition(m["end"], QTextCursor.KeepAnchor)
            cursor.setCharFormat(fmt)

    def _do_replace(self, replace_all: bool = True):
        pattern = self.pattern_input.text()
        text = self.test_editor.toPlainText()
        replacement = self.replacement_input.text()
        flags = self._get_active_flags_string()

        ok, result = RegexService.replace(pattern, text, replacement, flags_str=flags, replace_all=replace_all)
        if ok:
            self.preview_output.setPlainText(result)
            if self.toast_callback:
                self.toast_callback("تم تطبيق الاستبدال بنجاح! 🔄", False)
        else:
            self.preview_output.setPlainText(result)
            if self.toast_callback:
                self.toast_callback(result, True)

    def _copy_replacement_result(self):
        text = self.preview_output.toPlainText()
        copy_text_to_clipboard(text, self.toast_callback)

    def save_regex_dialog(self):
        pattern = self.pattern_input.text().strip()
        if not pattern:
            if self.toast_callback:
                self.toast_callback("يرجى كتابة نمط Regex أولاً قبل الحفظ!", True)
            return

        name, ok = QInputDialog.getText(self, "حفظ Regex", "اسم النمط (Name):")
        if not ok or not name.strip():
            return

        desc, _ = QInputDialog.getText(self, "حفظ Regex", "الوصف (اختياري):")

        saved = SavedRegex(
            name=name.strip(),
            pattern=pattern,
            description=desc.strip(),
            flags=self._get_active_flags_string(),
            replacement=self.replacement_input.text(),
        )
        try:
            reg_id = create_regex(saved)
            if self.toast_callback:
                self.toast_callback(f"تم حفظ نمط الـ Regex بنجاح! ⭐ [ID: {reg_id}]", False)
        except Exception as e:
            if self.toast_callback:
                self.toast_callback(f"فشل الحفظ: {str(e)}", True)

    def open_saved_library(self):
        dlg = SavedRegexLibraryDialog(self)
        if dlg.exec():
            selected = dlg.selected_regex
            if selected:
                self.pattern_input.setText(selected.pattern)
                self.replacement_input.setText(selected.replacement)
                # Set flags
                self.chk_i.setChecked("i" in selected.flags)
                self.chk_m.setChecked("m" in selected.flags)
                self.chk_s.setChecked("s" in selected.flags)
                self.chk_x.setChecked("x" in selected.flags)
                self._run_matching_now()
                if self.toast_callback:
                    self.toast_callback(f"تم تحميل النمط '{selected.name}' بنجاح! 📂", False)


class SavedRegexLibraryDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("📂 مكتبة أنماط الـ Regex المحفوظة (Regex Library)")
        self.resize(750, 520)
        self.selected_regex: Optional[SavedRegex] = None
        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Search Bar
        top_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 ابحث في الأنماط بالاسم، النمط، أو الوصف...")
        self.search_edit.setStyleSheet("background-color: #182229; color: white; padding: 8px 12px; border: 1px solid #2a3942; border-radius: 8px;")
        self.search_edit.textChanged.connect(self._filter_items)
        top_row.addWidget(self.search_edit, stretch=1)

        self.btn_fav_filter = QPushButton("⭐ المفضلة فقط")
        self.btn_fav_filter.setCheckable(True)
        self.btn_fav_filter.setStyleSheet("background-color: #1f2c34; color: #f59e0b; font-weight: bold; padding: 8px 14px; border-radius: 8px;")
        self.btn_fav_filter.clicked.connect(self._filter_items)
        top_row.addWidget(self.btn_fav_filter)
        layout.addLayout(top_row)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 1px solid #202c33;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 10px 14px;
                border-radius: 8px;
                margin-bottom: 4px;
                border: 1px solid #2a3942;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #202c33;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._select_and_accept)
        layout.addWidget(self.list_widget, stretch=1)

        # Actions Row
        b_row = QHBoxLayout()
        btn_fav = QPushButton("⭐ تبديل المفضلة")
        btn_fav.setStyleSheet("background-color: #f59e0b; color: black; font-weight: bold; padding: 8px 16px; border-radius: 8px;")
        btn_fav.clicked.connect(self._toggle_fav_selected)

        btn_del = QPushButton("🗑️ حذف")
        btn_del.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 8px 16px; border-radius: 8px;")
        btn_del.clicked.connect(self._delete_selected)

        btn_load = QPushButton("✓ استخدام النمط المحدد")
        btn_load.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 8px 20px; border-radius: 8px;")
        btn_load.clicked.connect(self._select_and_accept)

        b_row.addWidget(btn_fav)
        b_row.addWidget(btn_del)
        b_row.addStretch()
        b_row.addWidget(btn_load)
        layout.addLayout(b_row)

    def _load_items(self):
        self._filter_items()

    def _filter_items(self):
        query = self.search_edit.text().strip()
        fav_only = self.btn_fav_filter.isChecked()

        if query:
            items = search_regexes(query, favorites_only=fav_only)
        else:
            items = get_all_regexes(favorites_only=fav_only)

        self.list_widget.clear()
        for r in items:
            fav_star = "⭐ " if r.favorite else ""
            flags_tag = f" [{r.flags}]" if r.flags else ""
            desc = f" - {r.description}" if r.description else ""
            label = f"{fav_star}{r.name}{desc}\nالنمط: {r.pattern}{flags_tag}"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, r)
            self.list_widget.addItem(item)

    def _select_and_accept(self):
        curr = self.list_widget.currentItem()
        if not curr:
            return
        self.selected_regex = curr.data(Qt.UserRole)
        self.accept()

    def _toggle_fav_selected(self):
        curr = self.list_widget.currentItem()
        if not curr:
            return
        reg = curr.data(Qt.UserRole)
        toggle_favorite(reg.id)
        self._filter_items()

    def _delete_selected(self):
        curr = self.list_widget.currentItem()
        if not curr:
            return
        reg = curr.data(Qt.UserRole)
        res = QMessageBox.question(self, "تأكيد الحذف", f"هل أنت متأكد من حذف النمط '{reg.name}'؟")
        if res == QMessageBox.Yes:
            delete_regex(reg.id)
            self._filter_items()
