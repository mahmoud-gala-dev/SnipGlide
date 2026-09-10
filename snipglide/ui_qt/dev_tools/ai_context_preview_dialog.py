"""AI Context Preview and Explicit User Confirmation Dialog.

Ensures strict privacy: prevents any automatic transmission of source code,
clipboard data, or file contents without explicit review and approval.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AIContextPreviewDialog(QDialog):
    """Dialog that displays full payload details and prompts for user confirmation before AI call."""

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        prompt_text: str,
        system_prompt: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("AI Context Privacy Preview - Explicit Confirmation")
        self.resize(650, 480)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Alert
        header = QLabel("🔒 Privacy & Transmission Review")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #f38ba8;")
        layout.addWidget(header)

        warning_lbl = QLabel(
            "SnipGlide requires your explicit confirmation before transmitting source code, "
            "diffs, or context to third-party AI providers. Please review the exact content below."
        )
        warning_lbl.setWordWrap(True)
        warning_lbl.setStyleSheet("color: #bac2de; font-size: 12px;")
        layout.addWidget(warning_lbl)

        # Meta row: Provider, Model, Size
        meta_row = QHBoxLayout()
        lbl_p = QLabel(f"🌐 Provider: <b style='color:#89b4fa;'>{provider_name}</b>")
        lbl_m = QLabel(f"🧠 Model: <b style='color:#a6e3a1;'>{model_name or 'Default'}</b>")
        total_chars = len(prompt_text) + len(system_prompt)
        est_tokens = max(1, total_chars // 4)
        lbl_s = QLabel(f"📊 Payload: <b style='color:#fab387;'>{total_chars:,} chars (~{est_tokens:,} tokens)</b>")
        meta_row.addWidget(lbl_p)
        meta_row.addWidget(lbl_m)
        meta_row.addWidget(lbl_s)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        # Preview Text
        lbl_prev = QLabel("Exact Text to be Sent:")
        lbl_prev.setStyleSheet("font-weight: bold; color: #cdd6f4; font-size: 13px;")
        layout.addWidget(lbl_prev)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFont(QFont("Consolas", 10))
        self.txt_preview.setStyleSheet("background-color: #11111b; border: 1px solid #45475a; border-radius: 4px; padding: 6px; color: #cdd6f4;")
        full_display = f"--- System Instructions ---\n{system_prompt}\n\n--- User Prompt / Code ---\n{prompt_text}" if system_prompt else prompt_text
        self.txt_preview.setPlainText(full_display)
        layout.addWidget(self.txt_preview, 1)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("❌ Cancel")
        btn_cancel.setStyleSheet("background-color: #45475a; color: #cdd6f4; padding: 8px 18px; border-radius: 4px; font-size: 13px;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_send = QPushButton("🚀 Confirm & Send to AI")
        btn_send.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 8px 20px; border-radius: 4px; font-size: 13px;")
        btn_send.clicked.connect(self.accept)
        btn_row.addWidget(btn_send)

        layout.addLayout(btn_row)
