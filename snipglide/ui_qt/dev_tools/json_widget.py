from typing import Optional, Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter
)
from snipglide.services.dev_tools_service import JsonTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    show_status_badge, copy_text_to_clipboard
)

class JsonToolsWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar
        tb_layout = QHBoxLayout()
        btn_beautify = create_tool_button("✨ تنسيق (Beautify)", "#3b82f6", self.beautify)
        btn_minify = create_tool_button("📦 ضغط (Minify)", "#0ea5e9", self.minify)
        btn_validate = create_tool_button("🔍 فحص الصحة (Validate)", "#10b981", self.validate)
        btn_sort = create_tool_button("🔤 فرز المفاتيح (Sort Keys)", "#8b5cf6", self.sort_keys)
        btn_escape = create_tool_button("🔀 Escape", "#64748b", self.escape)
        btn_unescape = create_tool_button("🔄 Unescape", "#64748b", self.unescape)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)
        btn_copy = create_tool_button("📋 نسخ النتيجة", "#16a34a", self.copy_result)

        for b in (btn_beautify, btn_minify, btn_validate, btn_sort, btn_escape, btn_unescape):
            tb_layout.addWidget(b)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        # Status feedback label
        self.status_lbl = QLabel("")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        # Splitter with Input and Output
        splitter = QSplitter(Qt.Horizontal)
        self.editor_input = create_code_editor("أدخل كود JSON هنا...")
        self.editor_output = create_code_editor("النتيجة المنسقة ستظهر هنا...", readonly=True)

        splitter.addWidget(wrap_in_labeled_box("المدخلات (Input JSON):", self.editor_input))
        splitter.addWidget(wrap_in_labeled_box("المخرجات (Formatted Output):", self.editor_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

    def beautify(self):
        text = self.editor_input.toPlainText()
        ok, res, details = JsonTools.beautify(text)
        if ok:
            self.editor_output.setPlainText(res)
            show_status_badge(self.status_lbl, "✓ تم تنسيق كود JSON بنجاح.", is_error=False)
            if self.toast_callback:
                self.toast_callback("تم تنسيق JSON بنجاح! ✨", False)
        else:
            show_status_badge(self.status_lbl, res, is_error=True)
            if self.toast_callback:
                self.toast_callback("خطأ في بنية JSON!", True)

    def minify(self):
        text = self.editor_input.toPlainText()
        ok, res, details = JsonTools.minify(text)
        if ok:
            self.editor_output.setPlainText(res)
            show_status_badge(self.status_lbl, "✓ تم ضغط كود JSON بنجاح.", is_error=False)
            if self.toast_callback:
                self.toast_callback("تم ضغط JSON بنجاح! 📦", False)
        else:
            show_status_badge(self.status_lbl, res, is_error=True)
            if self.toast_callback:
                self.toast_callback("خطأ في بنية JSON!", True)

    def validate(self):
        text = self.editor_input.toPlainText()
        ok, res, details = JsonTools.validate(text)
        if ok:
            show_status_badge(self.status_lbl, res, is_error=False)
            if self.toast_callback:
                self.toast_callback("كود JSON سليم وصالح! ✓", False)
        else:
            show_status_badge(self.status_lbl, res, is_error=True)
            if self.toast_callback:
                msg = f"خطأ في سطر {details['line']} عمود {details['column']}" if details else "خطأ في JSON"
                self.toast_callback(msg, True)

    def sort_keys(self):
        text = self.editor_input.toPlainText()
        ok, res, details = JsonTools.sort_keys(text)
        if ok:
            self.editor_output.setPlainText(res)
            show_status_badge(self.status_lbl, "✓ تم فرز المفاتيح أبجدياً بنجاح.", is_error=False)
            if self.toast_callback:
                self.toast_callback("تم فرز مفاتيح JSON أبجدياً! 🔤", False)
        else:
            show_status_badge(self.status_lbl, res, is_error=True)

    def escape(self):
        text = self.editor_input.toPlainText()
        res = JsonTools.escape(text)
        self.editor_output.setPlainText(res)
        if self.toast_callback:
            self.toast_callback("تم تطبيق Escape بنجاح!", False)

    def unescape(self):
        text = self.editor_input.toPlainText()
        ok, res = JsonTools.unescape(text)
        if ok:
            self.editor_output.setPlainText(res)
            if self.toast_callback:
                self.toast_callback("تم إلغاء الهروب Unescape بنجاح!", False)
        else:
            show_status_badge(self.status_lbl, res, is_error=True)

    def clear_all(self):
        self.editor_input.clear()
        self.editor_output.clear()
        self.status_lbl.hide()

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)
