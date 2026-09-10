from typing import Optional, Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter
)
from snipglide.services.dev_tools_service import Base64Tools, UrlTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    copy_text_to_clipboard
)

class Base64Widget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tb_layout = QHBoxLayout()
        btn_enc = create_tool_button("🔒 تشفير (Encode to Base64)", "#3b82f6", self.encode)
        btn_dec = create_tool_button("🔓 فك تشفير (Decode Base64)", "#10b981", self.decode)
        btn_copy = create_tool_button("📋 نسخ النتيجة", "#16a34a", self.copy_result)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)

        tb_layout.addWidget(btn_enc)
        tb_layout.addWidget(btn_dec)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.editor_input = create_code_editor("أدخل النص المراد تشفيره أو كود Base64 لفك تشفيره...")
        self.editor_output = create_code_editor("النتيجة ستظهر هنا...", readonly=True)

        splitter.addWidget(wrap_in_labeled_box("المدخلات (Plain Text / Base64):", self.editor_input))
        splitter.addWidget(wrap_in_labeled_box("المخرجات (Result):", self.editor_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

    def encode(self):
        text = self.editor_input.toPlainText()
        ok, res = Base64Tools.encode(text)
        if ok:
            self.editor_output.setPlainText(res)
            if self.toast_callback:
                self.toast_callback("تم تشفير Base64 بنجاح! 🔒", False)
        else:
            if self.toast_callback:
                self.toast_callback(res, True)

    def decode(self):
        text = self.editor_input.toPlainText()
        ok, res = Base64Tools.decode(text)
        self.editor_output.setPlainText(res)
        if self.toast_callback:
            if ok:
                self.toast_callback("تم فك تشفير Base64 بنجاح! 🔓", False)
            else:
                self.toast_callback(res, True)

    def clear_all(self):
        self.editor_input.clear()
        self.editor_output.clear()

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)


class UrlToolsWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tb_layout = QHBoxLayout()
        btn_enc = create_tool_button("🌐 URL Encode", "#3b82f6", self.encode)
        btn_dec = create_tool_button("🔄 URL Decode", "#10b981", self.decode)
        btn_parse = create_tool_button("🔍 تحليل Query String (Parser)", "#8b5cf6", self.parse_query)
        btn_copy = create_tool_button("📋 نسخ النتيجة", "#16a34a", self.copy_result)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)

        tb_layout.addWidget(btn_enc)
        tb_layout.addWidget(btn_dec)
        tb_layout.addWidget(btn_parse)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.editor_input = create_code_editor("أدخل الرابط أو الـ Query String هنا...")
        self.editor_output = create_code_editor("النتيجة ستظهر هنا...", readonly=True)

        splitter.addWidget(wrap_in_labeled_box("الرابط / المدخلات:", self.editor_input))
        splitter.addWidget(wrap_in_labeled_box("المخرجات (Encoded / Decoded / JSON Params):", self.editor_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

    def encode(self):
        text = self.editor_input.toPlainText()
        res = UrlTools.encode(text)
        self.editor_output.setPlainText(res)
        if self.toast_callback:
            self.toast_callback("تم ترميز الرابط (URL Encode)! 🌐", False)

    def decode(self):
        text = self.editor_input.toPlainText()
        res = UrlTools.decode(text)
        self.editor_output.setPlainText(res)
        if self.toast_callback:
            self.toast_callback("تم فك ترميز الرابط (URL Decode)! 🔄", False)

    def parse_query(self):
        text = self.editor_input.toPlainText()
        ok, flat, pretty = UrlTools.parse_query_string(text)
        self.editor_output.setPlainText(pretty)
        if self.toast_callback:
            if ok:
                self.toast_callback("تم تفكيك الـ Query String بنجاح! 🔍", False)
            else:
                self.toast_callback(pretty, True)

    def clear_all(self):
        self.editor_input.clear()
        self.editor_output.clear()

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)
