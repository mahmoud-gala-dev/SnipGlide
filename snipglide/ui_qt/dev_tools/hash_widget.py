from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame
)
from snipglide.services.dev_tools_service import HashTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    copy_text_to_clipboard
)

class HashGeneratorWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self.hash_fields: dict[str, QLineEdit] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Warning banner
        warn = QLabel(
            "⚠️ تنبيه أمني: دوال MD5 و SHA-1 ضعيفة ومخترقة تصادمياً ولا تصلح إطلاقاً لتخزين كلمات المرور. "
            "استخدم SHA-256 أو التهشير المملح (Argon2 / PBKDF2 / Bcrypt)."
        )
        warn.setStyleSheet(
            "background-color: #451a03; color: #fde047; padding: 10px 14px; border-radius: 8px; "
            "border: 1.5px solid #ca8a04; font-size: 13px; font-weight: bold;"
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # Input
        self.editor_input = create_code_editor("اكتب النص المراد توليد قيم التهشير (Hashes) له هنا...")
        self.editor_input.textChanged.connect(self.recalculate_hashes)
        layout.addWidget(wrap_in_labeled_box("النص الأصلي (Input Text):", self.editor_input), stretch=1)

        # Results Grid
        res_frame = QFrame()
        res_frame.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 10px; padding: 12px;")
        r_layout = QVBoxLayout(res_frame)
        r_layout.setSpacing(10)

        algos = [("md5", "#f59e0b"), ("sha1", "#f97316"), ("sha256", "#10b981"), ("sha512", "#3b82f6")]
        for algo, color in algos:
            row = QHBoxLayout()
            lbl = QLabel(algo.upper() + ":")
            lbl.setStyleSheet(f"font-weight: bold; color: {color}; min-width: 90px; font-size: 14px;")
            row.addWidget(lbl)

            field = QLineEdit()
            field.setReadOnly(True)
            field.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 7px 10px; border-radius: 6px; font-family: monospace;")
            row.addWidget(field, stretch=1)

            btn_c = create_tool_button("📋 نسخ", "#1f2c34", lambda f=field: copy_text_to_clipboard(f.text(), self.toast_callback))
            btn_c.setFixedHeight(34)
            row.addWidget(btn_c)

            self.hash_fields[algo] = field
            r_layout.addLayout(row)

        layout.addWidget(res_frame)

    def recalculate_hashes(self):
        text = self.editor_input.toPlainText()
        if not text:
            for f in self.hash_fields.values():
                f.clear()
            return
        hashes = HashTools.compute_hashes(text)
        for algo, f in self.hash_fields.items():
            f.setText(hashes.get(algo, ""))
