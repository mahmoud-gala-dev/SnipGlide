from typing import Optional, Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter
)
from snipglide.services.dev_tools_service import JwtTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    copy_text_to_clipboard
)

class JwtDecoderWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Prominent Warning Banner
        warn = QLabel(
            "⚠️ ملاحظة أمنية هامة: عملية فك التشفير (Decode) مخصصة لقراءة ومعاينة الـ Header و Payload "
            "والتأكد من أوقات الصلاحية (exp/iat)، ولا تشمل التحقق من صحة التوقيع الرقمي (Signature Verification)."
        )
        warn.setStyleSheet(
            "background-color: #451a03; color: #fde047; padding: 10px 14px; border-radius: 8px; "
            "border: 1.5px solid #ca8a04; font-size: 13px; font-weight: bold;"
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)

        tb_layout = QHBoxLayout()
        btn_decode = create_tool_button("🎫 فك تشفير التوكن (Decode JWT)", "#3b82f6", self.decode_jwt)
        btn_copy = create_tool_button("📋 نسخ التحليل", "#16a34a", self.copy_result)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)

        tb_layout.addWidget(btn_decode)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.editor_input = create_code_editor("ألصق توكن الـ JWT هنا (eyJh...).")
        self.editor_output = create_code_editor("تحليل الترويسة والحمولة والتواريخ سيظهر هنا...", readonly=True)

        splitter.addWidget(wrap_in_labeled_box("رمز التوكن (JWT Token):", self.editor_input))
        splitter.addWidget(wrap_in_labeled_box("البيانات المفككة (Decoded JSON & Timestamps):", self.editor_output))
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, stretch=1)

    def decode_jwt(self):
        token = self.editor_input.toPlainText()
        ok, data, summary = JwtTools.decode_jwt(token)
        self.editor_output.setPlainText(summary)
        if self.toast_callback:
            if ok:
                self.toast_callback("تم فك تشفير توكن JWT بنجاح! 🎫", False)
            else:
                self.toast_callback(summary, True)

    def clear_all(self):
        self.editor_input.clear()
        self.editor_output.clear()

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)
