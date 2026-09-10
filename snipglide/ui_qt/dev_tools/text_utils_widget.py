from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from snipglide.services.dev_tools_service import TextUtils
from snipglide.ui_qt.dev_tools.common import (
    create_tool_button, create_code_editor, copy_text_to_clipboard
)

class TextUtilsWidget(QWidget):
    def __init__(self, toast_callback: Optional[Callable[[str, bool], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Toolbar Transformations
        tb1 = QHBoxLayout()
        tb1.addWidget(create_tool_button("UPPERCASE", "#3b82f6", lambda: self.apply_transform(TextUtils.to_uppercase)))
        tb1.addWidget(create_tool_button("lowercase", "#3b82f6", lambda: self.apply_transform(TextUtils.to_lowercase)))
        tb1.addWidget(create_tool_button("camelCase", "#8b5cf6", lambda: self.apply_transform(TextUtils.to_camel_case)))
        tb1.addWidget(create_tool_button("PascalCase", "#8b5cf6", lambda: self.apply_transform(TextUtils.to_pascal_case)))
        tb1.addWidget(create_tool_button("snake_case", "#10b981", lambda: self.apply_transform(TextUtils.to_snake_case)))
        tb1.addWidget(create_tool_button("kebab-case", "#10b981", lambda: self.apply_transform(TextUtils.to_kebab_case)))
        tb1.addStretch()
        layout.addLayout(tb1)

        tb2 = QHBoxLayout()
        tb2.addWidget(create_tool_button("🧹 إزالة الأسطر المكررة", "#f59e0b", lambda: self.apply_transform(TextUtils.remove_duplicate_lines)))
        tb2.addWidget(create_tool_button("🔤 فرز الأسطر (Sort)", "#f59e0b", lambda: self.apply_transform(TextUtils.sort_lines)))
        tb2.addWidget(create_tool_button("✂️ تنظيف الفراغات (Trim)", "#06b6d4", lambda: self.apply_transform(TextUtils.trim_whitespace)))
        tb2.addStretch()

        btn_copy = create_tool_button("📋 نسخ النتيجة", "#16a34a", self.copy_result)
        btn_clear = create_tool_button("🗑️ مسح", "#dc2626", self.clear_all)
        tb2.addWidget(btn_clear)
        tb2.addWidget(btn_copy)
        layout.addLayout(tb2)

        # Editor
        self.editor = create_code_editor("اكتب أو الصق النص هنا لتطبيق العمليات والإحصائيات...")
        self.editor.textChanged.connect(self.update_metrics)
        layout.addWidget(self.editor, stretch=1)

        # Metrics Bar
        self.metrics_label = QLabel("📊 الأحرف: 0 | الأحرف بدون مسافات: 0 | الكلمات: 0 | الأسطر: 0")
        self.metrics_label.setStyleSheet("background-color: #182229; color: #93c5fd; padding: 8px 16px; border-radius: 8px; border: 1px solid #2a3942; font-weight: bold;")
        layout.addWidget(self.metrics_label)

    def apply_transform(self, func: Callable[[str], str]):
        text = self.editor.toPlainText()
        transformed = func(text)
        self.editor.setPlainText(transformed)
        if self.toast_callback:
            self.toast_callback("تم تطبيق التحويل النصي بنجاح! 🔤", False)

    def update_metrics(self):
        text = self.editor.toPlainText()
        m = TextUtils.count_metrics(text)
        self.metrics_label.setText(
            f"📊 الأحرف الإجمالية: {m['characters']}  |  بدون مسافات: {m['characters_no_spaces']}  |  الكلمات: {m['words']}  |  الأسطر: {m['lines']}"
        )

    def clear_all(self):
        self.editor.clear()

    def copy_result(self):
        copy_text_to_clipboard(self.editor.toPlainText(), self.toast_callback)
