from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame
)
from snipglide.services.dev_tools_service import TimestampTools
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, wrap_in_labeled_box,
    copy_text_to_clipboard
)

class TimestampConverterWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()
        self.show_current_time()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # Quick Current Time Action
        top_row = QHBoxLayout()
        btn_now = create_tool_button("🕒 الوقت الحالي (Current Time)", "#3b82f6", self.show_current_time)
        btn_copy = create_tool_button("📋 نسخ النتائج", "#16a34a", self.copy_result)
        top_row.addWidget(btn_now)
        top_row.addStretch()
        top_row.addWidget(btn_copy)
        layout.addLayout(top_row)

        # Inputs section
        in_frame = QFrame()
        in_frame.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 10px; padding: 14px;")
        f_layout = QVBoxLayout(in_frame)
        f_layout.setSpacing(10)

        # Row 1: Timestamp to Date
        r1 = QHBoxLayout()
        lbl1 = QLabel("تحويل من Unix Epoch (ثواني أو ميلي ثانية):")
        lbl1.setStyleSheet("font-weight: bold; color: #f0f2f5; min-width: 250px;")
        r1.addWidget(lbl1)

        self.input_epoch = QLineEdit()
        self.input_epoch.setPlaceholderText("مثال: 1700000000 أو 1700000000000")
        self.input_epoch.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 8px 12px; border-radius: 6px; font-family: monospace;")
        r1.addWidget(self.input_epoch, stretch=1)

        btn_conv_epoch = create_tool_button("🔄 تحويل", "#10b981", self.convert_epoch)
        r1.addWidget(btn_conv_epoch)
        f_layout.addLayout(r1)

        # Row 2: Date string to Timestamp
        r2 = QHBoxLayout()
        lbl2 = QLabel("تحويل من نص تاريخ (ISO 8601 أو عادي):")
        lbl2.setStyleSheet("font-weight: bold; color: #f0f2f5; min-width: 250px;")
        r2.addWidget(lbl2)

        self.input_date = QLineEdit()
        self.input_date.setPlaceholderText("مثال: 2026-09-10 14:30:00 أو 2026-09-10T14:30:00Z")
        self.input_date.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 8px 12px; border-radius: 6px; font-family: monospace;")
        r2.addWidget(self.input_date, stretch=1)

        btn_conv_date = create_tool_button("🔄 تحويل", "#8b5cf6", self.convert_date)
        r2.addWidget(btn_conv_date)
        f_layout.addLayout(r2)

        layout.addWidget(in_frame)

        # Output Results
        self.editor_output = create_code_editor("نتائج التحويل بجميع الصيغ ستظهر هنا...", readonly=True)
        layout.addWidget(wrap_in_labeled_box("النتائج بجميع التنسيقات (Converted Datetime Formats):", self.editor_output), stretch=1)

    def show_current_time(self):
        curr = TimestampTools.get_current()
        self._render_results(curr)

    def convert_epoch(self):
        txt = self.input_epoch.text().strip()
        if not txt:
            if self.toast_callback:
                self.toast_callback("يرجى إدخال قيمة الـ Timestamp أولاً!", True)
            return
        try:
            val = float(txt)
            ok, res = TimestampTools.from_timestamp(val)
            if ok:
                self._render_results(res)
                if self.toast_callback:
                    self.toast_callback("تم تحويل الـ Timestamp بنجاح! ⏰", False)
            else:
                self.editor_output.setPlainText(res.get("error", "خطأ"))
                if self.toast_callback:
                    self.toast_callback(res.get("error", "خطأ"), True)
        except ValueError:
            if self.toast_callback:
                self.toast_callback("القيمة المدخلة ليست رقماً صالحاً!", True)

    def convert_date(self):
        txt = self.input_date.text().strip()
        if not txt:
            if self.toast_callback:
                self.toast_callback("يرجى إدخال نص التاريخ أولاً!", True)
            return
        ok, res = TimestampTools.from_datetime_string(txt)
        if ok:
            self._render_results(res)
            if self.toast_callback:
                self.toast_callback("تم تحويل التاريخ بنجاح! ⏰", False)
        else:
            self.editor_output.setPlainText(res.get("error", "خطأ"))
            if self.toast_callback:
                self.toast_callback(res.get("error", "خطأ"), True)

    def _render_results(self, data: dict[str, str]):
        lines = [
            f"• Unix Timestamp (Seconds):      {data.get('unix_seconds', '')}",
            f"• Unix Timestamp (Milliseconds): {data.get('unix_milliseconds', '')}",
            f"• Local Datetime (التوقيت المحلي): {data.get('local_datetime', '')}",
            f"• UTC Datetime (توقيت جرينتش):     {data.get('utc_datetime', '')}",
            f"• ISO 8601 Standard:             {data.get('iso_8601', '')}",
        ]
        self.editor_output.setPlainText("\n\n".join(lines))

    def copy_result(self):
        copy_text_to_clipboard(self.editor_output.toPlainText(), self.toast_callback)
