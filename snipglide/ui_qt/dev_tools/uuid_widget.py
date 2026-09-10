from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox
)
from snipglide.services.dev_tools_service import UuidTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    copy_text_to_clipboard
)

class UuidGeneratorWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        tb_layout = QHBoxLayout()
        btn_single = create_tool_button("🆔 توليد UUID v4 واحد", "#3b82f6", self.generate_single)
        tb_layout.addWidget(btn_single)

        lbl_qty = QLabel("عدد المجموعة:")
        lbl_qty.setStyleSheet("color: #e9edef; font-weight: bold;")
        tb_layout.addWidget(lbl_qty)

        self.uuid_spin = QSpinBox()
        self.uuid_spin.setRange(1, 100)
        self.uuid_spin.setValue(5)
        self.uuid_spin.setStyleSheet("background-color: #182229; color: white; padding: 6px 10px; border: 1px solid #2a3942; border-radius: 6px;")
        tb_layout.addWidget(self.uuid_spin)

        btn_batch = create_tool_button("📦 توليد مجموعة UUIDs", "#8b5cf6", self.generate_batch)
        tb_layout.addWidget(btn_batch)

        tb_layout.addStretch()
        btn_copy = create_tool_button("📋 نسخ النتيجة", "#16a34a", self.copy_result)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        self.editor_output = create_code_editor("معرفات الـ UUID ستظهر هنا...", readonly=True)
        layout.addWidget(wrap_in_labeled_box("المعرفات المولدة (Generated UUIDs):", self.editor_output), stretch=1)

    def generate_single(self):
        u = UuidTools.generate_v4()
        self.editor_output.setPlainText(u)
        if self.toast_callback:
            self.toast_callback("تم توليد UUID v4 بنجاح! 🆔", False)

    def generate_batch(self):
        count = self.uuid_spin.value()
        batch = UuidTools.generate_batch(count)
        self.editor_output.setPlainText("\n".join(batch))
        if self.toast_callback:
            self.toast_callback(f"تم توليد {count} معرفات UUID v4! 📦", False)

    def clear_all(self):
        self.editor_output.clear()

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)
