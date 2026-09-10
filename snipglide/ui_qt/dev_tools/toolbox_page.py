from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget
)

from snipglide.ui_qt.dev_tools.json_widget import JsonToolsWidget
from snipglide.ui_qt.dev_tools.encoding_widget import Base64Widget, UrlToolsWidget
from snipglide.ui_qt.dev_tools.jwt_widget import JwtDecoderWidget
from snipglide.ui_qt.dev_tools.uuid_widget import UuidGeneratorWidget
from snipglide.ui_qt.dev_tools.timestamp_widget import TimestampConverterWidget
from snipglide.ui_qt.dev_tools.hash_widget import HashGeneratorWidget
from snipglide.ui_qt.dev_tools.text_utils_widget import TextUtilsWidget

class DevToolboxPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self._setup_ui()
        self._setup_compatibility_aliases()

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

        # Sub-widgets
        emit_toast = self.toast_signal.emit
        self.json_widget = JsonToolsWidget(toast_callback=emit_toast, parent=self)
        self.b64_widget = Base64Widget(toast_callback=emit_toast, parent=self)
        self.url_widget = UrlToolsWidget(toast_callback=emit_toast, parent=self)
        self.jwt_widget = JwtDecoderWidget(toast_callback=emit_toast, parent=self)
        self.uuid_widget = UuidGeneratorWidget(toast_callback=emit_toast, parent=self)
        self.ts_widget = TimestampConverterWidget(toast_callback=emit_toast, parent=self)
        self.hash_widget = HashGeneratorWidget(toast_callback=emit_toast, parent=self)
        self.text_widget = TextUtilsWidget(toast_callback=emit_toast, parent=self)

        # Add all 8 sub-tools
        self.tabs.addTab(self.json_widget, "📋 JSON")
        self.tabs.addTab(self.b64_widget, "🔒 Base64")
        self.tabs.addTab(self.url_widget, "🌐 URL")
        self.tabs.addTab(self.jwt_widget, "🎫 JWT Decoder")
        self.tabs.addTab(self.uuid_widget, "🆔 UUID")
        self.tabs.addTab(self.ts_widget, "⏰ Timestamp")
        self.tabs.addTab(self.hash_widget, "#️⃣ Hashing")
        self.tabs.addTab(self.text_widget, "🔤 Text Utilities")

        main_layout.addWidget(self.tabs, stretch=1)

    def _setup_compatibility_aliases(self):
        """Preserves backward-compatibility aliases for tests and external scripts."""
        # JSON aliases
        self.json_input = self.json_widget.editor_input
        self.json_output = self.json_widget.editor_output
        self.json_status = self.json_widget.status_lbl
        self._json_beautify = self.json_widget.beautify
        self._json_minify = self.json_widget.minify
        self._json_validate = self.json_widget.validate
        self._json_sort_keys = self.json_widget.sort_keys
        self._json_escape = self.json_widget.escape
        self._json_unescape = self.json_widget.unescape

        # Base64 aliases
        self.b64_input = self.b64_widget.editor_input
        self.b64_output = self.b64_widget.editor_output
        self._b64_encode = self.b64_widget.encode
        self._b64_decode = self.b64_widget.decode

        # URL aliases
        self.url_input = self.url_widget.editor_input
        self.url_output = self.url_widget.editor_output
        self._url_encode = self.url_widget.encode
        self._url_decode = self.url_widget.decode
        self._url_parse = self.url_widget.parse_query

        # JWT aliases
        self.jwt_input = self.jwt_widget.editor_input
        self.jwt_output = self.jwt_widget.editor_output
        self._jwt_decode = self.jwt_widget.decode_jwt

        # UUID aliases
        self.uuid_spin = self.uuid_widget.uuid_spin
        self.uuid_output = self.uuid_widget.editor_output
        self._uuid_generate_single = self.uuid_widget.generate_single
        self._uuid_generate_batch = self.uuid_widget.generate_batch

        # Timestamp aliases
        self.ts_input_epoch = self.ts_widget.input_epoch
        self.ts_input_date = self.ts_widget.input_date
        self.ts_output = self.ts_widget.editor_output
        self._ts_convert_epoch = self.ts_widget.convert_epoch
        self._ts_convert_date = self.ts_widget.convert_date

        # Hash aliases
        self.hash_input = self.hash_widget.editor_input
        self.hash_fields = self.hash_widget.hash_fields
        self._recalculate_hashes = self.hash_widget.recalculate_hashes

        # Text aliases
        self.text_editor = self.text_widget.editor
        self._apply_text_transform = self.text_widget.apply_transform
