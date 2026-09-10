import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QPlainTextEdit, QLineEdit, QSplitter, QSpinBox, QComboBox,
    QApplication, QButtonGroup, QScrollArea, QTabWidget
)

from snipglide.services.dev_tools_service import (
    JsonTools, Base64Tools, UrlTools, JwtTools,
    UuidTools, TimestampTools, HashTools, TextUtils
)

class DevToolboxPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(14)

        # ── Header Bar ──
        h_row = QHBoxLayout()

        btn_drawer = QPushButton("☰ القائمة")
        btn_drawer.setToolTip("إظهار / إخفاء القائمة الجانبية (Drawer) - Ctrl+B")
        btn_drawer.setCursor(QCursor(Qt.PointingHandCursor))
        btn_drawer.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #60a5fa;
                border: 1.5px solid #2a3942;
                border-radius: 9px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #172554;
                color: #93c5fd;
                border-color: #3b82f6;
            }
        """)
        btn_drawer.clicked.connect(lambda: self.window().toggle_sidebar() if hasattr(self.window(), "toggle_sidebar") else None)
        h_row.addWidget(btn_drawer)

        title = QLabel("🛠️ أدوات المطورين (Developer Toolbox)")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #f0f2f5;")
        h_row.addWidget(title)

        h_row.addStretch()

        badge = QLabel("⚡ أدوات سريعة بدون إنترنت 100% Local")
        badge.setStyleSheet("background-color: #172554; color: #93c5fd; padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: bold; border: 1px solid #1e3a8a;")
        h_row.addWidget(badge)

        main_layout.addLayout(h_row)

        # ── Tools Tab Bar ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1.5px solid #1f2c34;
                background-color: #111b21;
                border-radius: 12px;
                padding: 14px;
            }
            QTabBar::tab {
                background-color: #182229;
                color: #8696a0;
                padding: 10px 18px;
                border: 1px solid #2a3942;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #111b21;
                color: #60a5fa;
                border-top: 3px solid #3b82f6;
            }
            QTabBar::tab:hover:!selected {
                background-color: #202c33;
                color: #e9edef;
            }
        """)

        # Add all 8 sub-tools
        self.tabs.addTab(self._build_json_tab(), "📋 JSON")
        self.tabs.addTab(self._build_base64_tab(), "🔒 Base64")
        self.tabs.addTab(self._build_url_tab(), "🌐 URL")
        self.tabs.addTab(self._build_jwt_tab(), "🎫 JWT Decoder")
        self.tabs.addTab(self._build_uuid_tab(), "🆔 UUID")
        self.tabs.addTab(self._build_timestamp_tab(), "⏰ Timestamp")
        self.tabs.addTab(self._build_hash_tab(), "#️⃣ Hashing")
        self.tabs.addTab(self._build_text_tab(), "🔤 Text Utilities")

        main_layout.addWidget(self.tabs, stretch=1)

    # ══════════════════════════════════════════════════════════════════
    # 1. JSON TOOLS TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_json_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar
        tb_layout = QHBoxLayout()
        btn_beautify = self._create_btn("✨ تنسيق (Beautify)", "#3b82f6", self._json_beautify)
        btn_minify = self._create_btn("📦 ضغط (Minify)", "#0ea5e9", self._json_minify)
        btn_validate = self._create_btn("🔍 فحص الصحة (Validate)", "#10b981", self._json_validate)
        btn_sort = self._create_btn("🔤 فرز المفاتيح (Sort Keys)", "#8b5cf6", self._json_sort_keys)
        btn_escape = self._create_btn("🔀 Escape", "#64748b", self._json_escape)
        btn_unescape = self._create_btn("🔄 Unescape", "#64748b", self._json_unescape)
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: (self.json_input.clear(), self.json_output.clear(), self.json_status.clear()))
        btn_copy = self._create_btn("📋 نسخ النتيجة", "#16a34a", lambda: self._copy_to_clipboard(self.json_output.toPlainText()))

        for b in (btn_beautify, btn_minify, btn_validate, btn_sort, btn_escape, btn_unescape):
            tb_layout.addWidget(b)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        # Status Label for line & col errors
        self.json_status = QLabel("")
        self.json_status.setStyleSheet("font-size: 13px; font-weight: bold; padding: 4px 10px; border-radius: 6px;")
        self.json_status.hide()
        layout.addWidget(self.json_status)

        # Splitter with Input and Output
        splitter = QSplitter(Qt.Horizontal)
        self.json_input = self._create_code_editor("أدخل كود JSON هنا...")
        self.json_output = self._create_code_editor("النتيجة المنسقة ستظهر هنا...", readonly=True)

        splitter.addWidget(self._wrap_in_labeled_box("المدخلات (Input JSON):", self.json_input))
        splitter.addWidget(self._wrap_in_labeled_box("المخرجات (Formatted Output):", self.json_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        return widget

    def _json_beautify(self):
        text = self.json_input.toPlainText()
        ok, res, details = JsonTools.beautify(text)
        if ok:
            self.json_output.setPlainText(res)
            self._show_status(self.json_status, "✓ تم تنسيق كود JSON بنجاح.", is_error=False)
            self.toast_signal.emit("تم تنسيق JSON بنجاح! ✨", False)
        else:
            self._show_status(self.json_status, res, is_error=True)
            self.toast_signal.emit("خطأ في بنية JSON!", True)

    def _json_minify(self):
        text = self.json_input.toPlainText()
        ok, res, details = JsonTools.minify(text)
        if ok:
            self.json_output.setPlainText(res)
            self._show_status(self.json_status, "✓ تم ضغط كود JSON بنجاح.", is_error=False)
            self.toast_signal.emit("تم ضغط JSON بنجاح! 📦", False)
        else:
            self._show_status(self.json_status, res, is_error=True)
            self.toast_signal.emit("خطأ في بنية JSON!", True)

    def _json_validate(self):
        text = self.json_input.toPlainText()
        ok, res, details = JsonTools.validate(text)
        if ok:
            self._show_status(self.json_status, res, is_error=False)
            self.toast_signal.emit("كود JSON سليم وصالح! ✓", False)
        else:
            self._show_status(self.json_status, res, is_error=True)
            self.toast_signal.emit(f"خطأ في سطر {details['line']} عمود {details['column']}", True)

    def _json_sort_keys(self):
        text = self.json_input.toPlainText()
        ok, res, details = JsonTools.sort_keys(text)
        if ok:
            self.json_output.setPlainText(res)
            self._show_status(self.json_status, "✓ تم فرز المفاتيح أبجدياً بنجاح.", is_error=False)
            self.toast_signal.emit("تم فرز مفاتيح JSON أبجدياً! 🔤", False)
        else:
            self._show_status(self.json_status, res, is_error=True)

    def _json_escape(self):
        text = self.json_input.toPlainText()
        res = JsonTools.escape(text)
        self.json_output.setPlainText(res)
        self.toast_signal.emit("تم تطبيق Escape بنجاح!", False)

    def _json_unescape(self):
        text = self.json_input.toPlainText()
        ok, res = JsonTools.unescape(text)
        if ok:
            self.json_output.setPlainText(res)
            self.toast_signal.emit("تم إلغاء الهروب Unescape بنجاح!", False)
        else:
            self._show_status(self.json_status, res, is_error=True)

    # ══════════════════════════════════════════════════════════════════
    # 2. BASE64 TOOLS TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_base64_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tb_layout = QHBoxLayout()
        btn_enc = self._create_btn("🔒 تشفير (Encode to Base64)", "#3b82f6", self._b64_encode)
        btn_dec = self._create_btn("🔓 فك تشفير (Decode Base64)", "#10b981", self._b64_decode)
        btn_copy = self._create_btn("📋 نسخ النتيجة", "#16a34a", lambda: self._copy_to_clipboard(self.b64_output.toPlainText()))
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: (self.b64_input.clear(), self.b64_output.clear()))

        tb_layout.addWidget(btn_enc)
        tb_layout.addWidget(btn_dec)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.b64_input = self._create_code_editor("أدخل النص المراد تشفيره أو كود Base64 لفك تشفيره...")
        self.b64_output = self._create_code_editor("النتيجة ستظهر هنا...", readonly=True)

        splitter.addWidget(self._wrap_in_labeled_box("المدخلات (Plain Text / Base64):", self.b64_input))
        splitter.addWidget(self._wrap_in_labeled_box("المخرجات (Result):", self.b64_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        return widget

    def _b64_encode(self):
        text = self.b64_input.toPlainText()
        ok, res = Base64Tools.encode(text)
        if ok:
            self.b64_output.setPlainText(res)
            self.toast_signal.emit("تم تشفير Base64 بنجاح! 🔒", False)
        else:
            self.toast_signal.emit(res, True)

    def _b64_decode(self):
        text = self.b64_input.toPlainText()
        ok, res = Base64Tools.decode(text)
        if ok:
            self.b64_output.setPlainText(res)
            self.toast_signal.emit("تم فك تشفير Base64 بنجاح! 🔓", False)
        else:
            self.b64_output.setPlainText(res)
            self.toast_signal.emit(res, True)

    # ══════════════════════════════════════════════════════════════════
    # 3. URL TOOLS TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_url_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tb_layout = QHBoxLayout()
        btn_enc = self._create_btn("🌐 URL Encode", "#3b82f6", self._url_encode)
        btn_dec = self._create_btn("🔄 URL Decode", "#10b981", self._url_decode)
        btn_parse = self._create_btn("🔍 تحليل Query String (Parser)", "#8b5cf6", self._url_parse)
        btn_copy = self._create_btn("📋 نسخ النتيجة", "#16a34a", lambda: self._copy_to_clipboard(self.url_output.toPlainText()))
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: (self.url_input.clear(), self.url_output.clear()))

        tb_layout.addWidget(btn_enc)
        tb_layout.addWidget(btn_dec)
        tb_layout.addWidget(btn_parse)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.url_input = self._create_code_editor("أدخل الرابط أو الـ Query String هنا...")
        self.url_output = self._create_code_editor("النتيجة ستظهر هنا...", readonly=True)

        splitter.addWidget(self._wrap_in_labeled_box("الرابط / المدخلات:", self.url_input))
        splitter.addWidget(self._wrap_in_labeled_box("المخرجات (Encoded / Decoded / JSON Params):", self.url_output))
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        return widget

    def _url_encode(self):
        text = self.url_input.toPlainText()
        self.url_output.setPlainText(UrlTools.encode(text))
        self.toast_signal.emit("تم ترميز الرابط (URL Encode)! 🌐", False)

    def _url_decode(self):
        text = self.url_input.toPlainText()
        self.url_output.setPlainText(UrlTools.decode(text))
        self.toast_signal.emit("تم فك ترميز الرابط (URL Decode)! 🔄", False)

    def _url_parse(self):
        text = self.url_input.toPlainText()
        ok, flat, pretty = UrlTools.parse_query_string(text)
        if ok:
            self.url_output.setPlainText(pretty)
            self.toast_signal.emit("تم تفكيك الـ Query String بنجاح! 🔍", False)
        else:
            self.url_output.setPlainText(pretty)
            self.toast_signal.emit(pretty, True)

    # ══════════════════════════════════════════════════════════════════
    # 4. JWT DECODER TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_jwt_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Warning banner
        warn = QLabel("⚠️ ملاحظة أمنية هامة: عملية فك التشفير (Decode) مخصصة لقراءة ومعاينة الـ Header و Payload والتأكد من أوقات الصلاحية (exp/iat)، ولا تشمل التحقق من صحة التوقيع الرقمي (Signature).")
        warn.setStyleSheet("background-color: #451a03; color: #fde047; padding: 10px 14px; border-radius: 8px; border: 1.5px solid #ca8a04; font-size: 13px; font-weight: bold;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        tb_layout = QHBoxLayout()
        btn_decode = self._create_btn("🎫 فك تشفير التوكن (Decode JWT)", "#3b82f6", self._jwt_decode)
        btn_copy = self._create_btn("📋 نسخ التحليل", "#16a34a", lambda: self._copy_to_clipboard(self.jwt_output.toPlainText()))
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: (self.jwt_input.clear(), self.jwt_output.clear()))

        tb_layout.addWidget(btn_decode)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        splitter = QSplitter(Qt.Horizontal)
        self.jwt_input = self._create_code_editor("ألصق توكن الـ JWT هنا (eyJh...).")
        self.jwt_output = self._create_code_editor("تحليل الترويسة والحمولة والتواريخ سيظهر هنا...", readonly=True)

        splitter.addWidget(self._wrap_in_labeled_box("رمز التوكن (JWT Token):", self.jwt_input))
        splitter.addWidget(self._wrap_in_labeled_box("البيانات المفككة (Decoded JSON & Timestamps):", self.jwt_output))
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, stretch=1)

        return widget

    def _jwt_decode(self):
        token = self.jwt_input.toPlainText()
        ok, data, summary = JwtTools.decode_jwt(token)
        if ok:
            self.jwt_output.setPlainText(summary)
            self.toast_signal.emit("تم فك تشفير توكن JWT بنجاح! 🎫", False)
        else:
            self.jwt_output.setPlainText(summary)
            self.toast_signal.emit(summary, True)

    # ══════════════════════════════════════════════════════════════════
    # 5. UUID GENERATOR TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_uuid_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        tb_layout = QHBoxLayout()
        btn_single = self._create_btn("🆔 توليد UUID v4 واحد", "#3b82f6", self._uuid_generate_single)
        tb_layout.addWidget(btn_single)

        lbl_qty = QLabel("عدد المجموعة:")
        lbl_qty.setStyleSheet("color: #e9edef; font-weight: bold;")
        tb_layout.addWidget(lbl_qty)

        self.uuid_spin = QSpinBox()
        self.uuid_spin.setRange(1, 100)
        self.uuid_spin.setValue(5)
        self.uuid_spin.setStyleSheet("background-color: #182229; color: white; padding: 6px 10px; border: 1px solid #2a3942; border-radius: 6px;")
        tb_layout.addWidget(self.uuid_spin)

        btn_batch = self._create_btn("📦 توليد مجموعة UUIDs", "#8b5cf6", self._uuid_generate_batch)
        tb_layout.addWidget(btn_batch)

        tb_layout.addStretch()
        btn_copy = self._create_btn("📋 نسخ النتيجة", "#16a34a", lambda: self._copy_to_clipboard(self.uuid_output.toPlainText()))
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: self.uuid_output.clear())
        tb_layout.addWidget(btn_clear)
        tb_layout.addWidget(btn_copy)
        layout.addLayout(tb_layout)

        self.uuid_output = self._create_code_editor("معرفات الـ UUID ستظهر هنا...", readonly=True)
        layout.addWidget(self._wrap_in_labeled_box("المعرفات المولدة (Generated UUIDs):", self.uuid_output), stretch=1)

        return widget

    def _uuid_generate_single(self):
        u = UuidTools.generate_v4()
        self.uuid_output.setPlainText(u)
        self.toast_signal.emit("تم توليد UUID v4 بنجاح! 🆔", False)

    def _uuid_generate_batch(self):
        count = self.uuid_spin.value()
        batch = UuidTools.generate_batch(count)
        self.uuid_output.setPlainText("\n".join(batch))
        self.toast_signal.emit(f"تم توليد {count} معرفات UUID v4! 📦", False)

    # ══════════════════════════════════════════════════════════════════
    # 6. TIMESTAMP CONVERTER TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_timestamp_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # Quick Current Time Action
        top_row = QHBoxLayout()
        btn_now = self._create_btn("🕒 الوقت الحالي (Current Time)", "#3b82f6", self._ts_current)
        top_row.addWidget(btn_now)
        top_row.addStretch()
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

        self.ts_input_epoch = QLineEdit()
        self.ts_input_epoch.setPlaceholderText("مثال: 1700000000 أو 1700000000000")
        self.ts_input_epoch.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 8px 12px; border-radius: 6px; font-family: monospace;")
        r1.addWidget(self.ts_input_epoch, stretch=1)

        btn_conv_epoch = self._create_btn("🔄 تحويل", "#10b981", self._ts_convert_epoch)
        r1.addWidget(btn_conv_epoch)
        f_layout.addLayout(r1)

        # Row 2: Date string to Timestamp
        r2 = QHBoxLayout()
        lbl2 = QLabel("تحويل من نص تاريخ (ISO 8601 أو عادي):")
        lbl2.setStyleSheet("font-weight: bold; color: #f0f2f5; min-width: 250px;")
        r2.addWidget(lbl2)

        self.ts_input_date = QLineEdit()
        self.ts_input_date.setPlaceholderText("مثال: 2026-09-10 14:30:00 أو 2026-09-10T14:30:00Z")
        self.ts_input_date.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 8px 12px; border-radius: 6px; font-family: monospace;")
        r2.addWidget(self.ts_input_date, stretch=1)

        btn_conv_date = self._create_btn("🔄 تحويل", "#8b5cf6", self._ts_convert_date)
        r2.addWidget(btn_conv_date)
        f_layout.addLayout(r2)

        layout.addWidget(in_frame)

        # Output Results
        self.ts_output = self._create_code_editor("نتائج التحويل بجميع الصيغ ستظهر هنا...", readonly=True)
        layout.addWidget(self._wrap_in_labeled_box("النتائج بجميع التنسيقات (Converted Datetime Formats):", self.ts_output), stretch=1)

        # Initialize with current
        self._ts_current()

        return widget

    def _ts_current(self):
        curr = TimestampTools.get_current()
        self._render_ts_results(curr)

    def _ts_convert_epoch(self):
        txt = self.ts_input_epoch.text().strip()
        if not txt:
            self.toast_signal.emit("يرجى إدخال قيمة الـ Timestamp أولاً!", True)
            return
        try:
            val = float(txt)
            ok, res = TimestampTools.from_timestamp(val)
            if ok:
                self._render_ts_results(res)
                self.toast_signal.emit("تم تحويل الـ Timestamp بنجاح! ⏰", False)
            else:
                self.ts_output.setPlainText(res.get("error", "خطأ"))
        except ValueError:
            self.toast_signal.emit("القيمة المدخلة ليست رقماً صالحاً!", True)

    def _ts_convert_date(self):
        txt = self.ts_input_date.text().strip()
        if not txt:
            self.toast_signal.emit("يرجى إدخال نص التاريخ أولاً!", True)
            return
        ok, res = TimestampTools.from_datetime_string(txt)
        if ok:
            self._render_ts_results(res)
            self.toast_signal.emit("تم تحويل التاريخ بنجاح! ⏰", False)
        else:
            self.ts_output.setPlainText(res.get("error", "خطأ"))
            self.toast_signal.emit(res.get("error", "خطأ"), True)

    def _render_ts_results(self, data: dict[str, str]):
        lines = [
            f"• Unix Timestamp (Seconds):      {data.get('unix_seconds', '')}",
            f"• Unix Timestamp (Milliseconds): {data.get('unix_milliseconds', '')}",
            f"• Local Datetime (التوقيت المحلي): {data.get('local_datetime', '')}",
            f"• UTC Datetime (توقيت جرينتش):     {data.get('utc_datetime', '')}",
            f"• ISO 8601 Standard:             {data.get('iso_8601', '')}",
        ]
        self.ts_output.setPlainText("\n\n".join(lines))

    # ══════════════════════════════════════════════════════════════════
    # 7. HASH GENERATOR TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_hash_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Warning banner
        warn = QLabel("⚠️ تنبيه أمني: دوال MD5 و SHA-1 ضعيفة ومخترقة تصادمياً ولا تصلح إطلاقاً لتخزين كلمات المرور. استخدم SHA-256 أو التهشير المملح (Argon2 / PBKDF2).")
        warn.setStyleSheet("background-color: #451a03; color: #fde047; padding: 10px 14px; border-radius: 8px; border: 1.5px solid #ca8a04; font-size: 13px; font-weight: bold;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # Input
        self.hash_input = self._create_code_editor("اكتب النص المراد توليد قيم التهشير (Hashes) له هنا...")
        self.hash_input.textChanged.connect(self._recalculate_hashes)
        layout.addWidget(self._wrap_in_labeled_box("النص الأصلي (Input Text):", self.hash_input), stretch=1)

        # Results Grid
        res_frame = QFrame()
        res_frame.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 10px; padding: 12px;")
        r_layout = QVBoxLayout(res_frame)
        r_layout.setSpacing(10)

        self.hash_fields = {}
        for algo, color in [("md5", "#f59e0b"), ("sha1", "#f97316"), ("sha256", "#10b981"), ("sha512", "#3b82f6")]:
            row = QHBoxLayout()
            lbl = QLabel(algo.upper() + ":")
            lbl.setStyleSheet(f"font-weight: bold; color: {color}; min-width: 90px; font-size: 14px;")
            row.addWidget(lbl)

            field = QLineEdit()
            field.setReadOnly(True)
            field.setStyleSheet("background-color: #111b21; color: #38bdf8; border: 1px solid #3b4a54; padding: 7px 10px; border-radius: 6px; font-family: monospace;")
            row.addWidget(field, stretch=1)

            btn_c = self._create_btn("📋 نسخ", "#1f2c34", lambda f=field: self._copy_to_clipboard(f.text()))
            btn_c.setFixedHeight(34)
            row.addWidget(btn_c)

            self.hash_fields[algo] = field
            r_layout.addLayout(row)

        layout.addWidget(res_frame)
        return widget

    def _recalculate_hashes(self):
        text = self.hash_input.toPlainText()
        if not text:
            for f in self.hash_fields.values():
                f.clear()
            return
        hashes = HashTools.compute_hashes(text)
        for algo, f in self.hash_fields.items():
            f.setText(hashes.get(algo, ""))

    # ══════════════════════════════════════════════════════════════════
    # 8. TEXT UTILITIES TAB
    # ══════════════════════════════════════════════════════════════════
    def _build_text_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar Transformations
        tb1 = QHBoxLayout()
        tb1.addWidget(self._create_btn("UPPERCASE", "#3b82f6", lambda: self._apply_text_transform(TextUtils.to_uppercase)))
        tb1.addWidget(self._create_btn("lowercase", "#3b82f6", lambda: self._apply_text_transform(TextUtils.to_lowercase)))
        tb1.addWidget(self._create_btn("camelCase", "#8b5cf6", lambda: self._apply_text_transform(TextUtils.to_camel_case)))
        tb1.addWidget(self._create_btn("PascalCase", "#8b5cf6", lambda: self._apply_text_transform(TextUtils.to_pascal_case)))
        tb1.addWidget(self._create_btn("snake_case", "#10b981", lambda: self._apply_text_transform(TextUtils.to_snake_case)))
        tb1.addWidget(self._create_btn("kebab-case", "#10b981", lambda: self._apply_text_transform(TextUtils.to_kebab_case)))
        tb1.addStretch()
        layout.addLayout(tb1)

        tb2 = QHBoxLayout()
        tb2.addWidget(self._create_btn("🧹 إزالة الأسطر المكررة", "#f59e0b", lambda: self._apply_text_transform(TextUtils.remove_duplicate_lines)))
        tb2.addWidget(self._create_btn("🔤 فرز الأسطر (Sort)", "#f59e0b", lambda: self._apply_text_transform(TextUtils.sort_lines)))
        tb2.addWidget(self._create_btn("✂️ تنظيف الفراغات (Trim)", "#06b6d4", lambda: self._apply_text_transform(TextUtils.trim_whitespace)))
        tb2.addStretch()

        btn_copy = self._create_btn("📋 نسخ النتيجة", "#16a34a", lambda: self._copy_to_clipboard(self.text_editor.toPlainText()))
        btn_clear = self._create_btn("🗑️ مسح", "#dc2626", lambda: self.text_editor.clear())
        tb2.addWidget(btn_clear)
        tb2.addWidget(btn_copy)
        layout.addLayout(tb2)

        # Editor
        self.text_editor = self._create_code_editor("اكتب أو الصق النص هنا لتطبيق العمليات والإحصائيات...")
        self.text_editor.textChanged.connect(self._update_text_metrics)
        layout.addWidget(self.text_editor, stretch=1)

        # Metrics Bar
        self.metrics_label = QLabel("📊 الأحرف: 0 | الأحرف بدون مسافات: 0 | الكلمات: 0 | الأسطر: 0")
        self.metrics_label.setStyleSheet("background-color: #182229; color: #93c5fd; padding: 8px 16px; border-radius: 8px; border: 1px solid #2a3942; font-weight: bold;")
        layout.addWidget(self.metrics_label)

        return widget

    def _apply_text_transform(self, func):
        text = self.text_editor.toPlainText()
        transformed = func(text)
        self.text_editor.setPlainText(transformed)
        self.toast_signal.emit("تم تطبيق التحويل النصي بنجاح! 🔤", False)

    def _update_text_metrics(self):
        text = self.text_editor.toPlainText()
        m = TextUtils.count_metrics(text)
        self.metrics_label.setText(
            f"📊 الأحرف الإجمالية: {m['characters']}  |  بدون مسافات: {m['characters_no_spaces']}  |  الكلمات: {m['words']}  |  الأسطر: {m['lines']}"
        )

    # ══════════════════════════════════════════════════════════════════
    # HELPER WIDGET BUILDERS
    # ══════════════════════════════════════════════════════════════════
    def _create_btn(self, text: str, bg_color: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
        """)
        btn.clicked.connect(callback)
        return btn

    def _create_code_editor(self, placeholder: str = "", readonly: bool = False) -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setPlaceholderText(placeholder)
        editor.setReadOnly(readonly)
        editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b141a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 10px;
            }
            QPlainTextEdit:focus {
                border-color: #3b82f6;
            }
        """)
        return editor

    def _wrap_in_labeled_box(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #94a3b8;")
        layout.addWidget(lbl)
        layout.addWidget(widget, stretch=1)
        return container

    def _show_status(self, label: QLabel, text: str, is_error: bool = False):
        bg = "#450a0a" if is_error else "#052e16"
        color = "#f87171" if is_error else "#4ade80"
        border = "#dc2626" if is_error else "#16a34a"
        label.setStyleSheet(f"background-color: {bg}; color: {color}; border: 1px solid {border}; font-size: 13px; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        label.setText(text)
        label.show()

    def _copy_to_clipboard(self, text: str):
        if not text:
            self.toast_signal.emit("لا يوجد محتوى لنسخه!", True)
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.toast_signal.emit("تم نسخ المحتوى إلى الحافظة! 📋", False)
