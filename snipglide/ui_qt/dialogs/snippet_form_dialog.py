from typing import Optional, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QScrollArea, QWidget
)

class SnippetFormDialog(QDialog):
    """
    Sleek dark-themed Qt dialog displayed before expanding snippets
    that contain interactive {{input:...}} or {{choice:...}} form variables.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(kwargs.get("parent", None))
        shortcut = ":snippet"
        fields = []
        if len(args) >= 2:
            if isinstance(args[0], str) and isinstance(args[1], list):
                shortcut, fields = args[0], args[1]
            elif isinstance(args[0], list) and isinstance(args[1], str):
                fields, shortcut = args[0], args[1]
            else:
                shortcut, fields = str(args[0]), list(args[1])
        elif len(args) == 1:
            if isinstance(args[0], list):
                fields = args[0]
            elif isinstance(args[0], str):
                shortcut = args[0]

        if "snippet_shortcut" in kwargs:
            shortcut = kwargs["snippet_shortcut"]
        if "fields" in kwargs:
            fields = kwargs["fields"]

        self.shortcut = shortcut
        self.fields = fields
        self.field_widgets: dict[str, Any] = {}
        self.inputs: dict[str, Any] = {}
        self.answers: Optional[dict[str, str]] = None

        self.setWindowTitle(f"تعبئة متغيرات الاختصار: {self.shortcut}")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setFixedWidth(520)

        self._setup_ui()
        self.inputs = {name: widget for name, (_, widget) in self.field_widgets.items()}

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #111b21;
                color: #f0f2f5;
                font-family: 'Segoe UI', 'Tajawal', sans-serif;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # ── Header Card ──
        h_frame = QFrame()
        h_frame.setStyleSheet("""
            QFrame {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 12px;
                padding: 10px 14px;
            }
        """)
        h_layout = QHBoxLayout(h_frame)
        h_layout.setContentsMargins(8, 4, 8, 4)

        icon_lbl = QLabel("⚡")
        icon_lbl.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        h_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        t_lbl = QLabel(f"تعبئة المتغيرات للاختصار: {self.shortcut}")
        t_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #f0f2f5; background: transparent; border: none;")
        title_box.addWidget(t_lbl)

        sub_lbl = QLabel("أدخل القيم أو اختر الخيارات المطلوبة لإدراج الكود البرمجي:")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent; border: none;")
        title_box.addWidget(sub_lbl)

        h_layout.addLayout(title_box, stretch=1)
        main_layout.addWidget(h_frame)

        # ── Fields Scroll Area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #1f2c34;
                background-color: #0b141a;
                border-radius: 10px;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(14)

        for f in self.fields:
            field_name = f.get("name", "")
            field_label = f.get("label") or field_name.replace("_", " ").title()
            field_type = f.get("type", "input")
            default_val = f.get("default", "")

            row_box = QVBoxLayout()
            row_box.setSpacing(6)

            lbl = QLabel(f"• {field_label}:")
            lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #60a5fa;")
            row_box.addWidget(lbl)

            if field_type == "choice":
                combo = QComboBox()
                combo.setFixedHeight(38)
                combo.setStyleSheet("""
                    QComboBox {
                        background-color: #182229;
                        color: #f0f2f5;
                        border: 1.5px solid #2a3942;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QComboBox:focus, QComboBox:hover {
                        border-color: #3b82f6;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #111b21;
                        color: #f0f2f5;
                        selection-background-color: #172554;
                        border: 1px solid #2a3942;
                    }
                """)
                opts = f.get("options", [])
                for opt in opts:
                    combo.addItem(opt, opt)
                if default_val and default_val in opts:
                    combo.setCurrentText(default_val)
                row_box.addWidget(combo)
                self.field_widgets[field_name] = ("choice", combo)
            else:
                edit = QLineEdit()
                edit.setFixedHeight(38)
                edit.setText(default_val)
                edit.setPlaceholderText(f"أدخل {field_label}...")
                edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #182229;
                        color: #f0f2f5;
                        font-size: 13px;
                        border: 1.5px solid #2a3942;
                        border-radius: 8px;
                        padding: 6px 12px;
                    }
                    QLineEdit:focus {
                        border-color: #25D366;
                        background-color: #111b21;
                    }
                """)
                row_box.addWidget(edit)
                self.field_widgets[field_name] = ("input", edit)

            c_layout.addLayout(row_box)

        c_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, stretch=1)

        # ── Buttons Row ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("إلغاء (Esc)")
        cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                color: #e9edef;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2a3942;
                color: #f0f2f5;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        insert_btn = QPushButton("⚡ إدراج وتوسيع الكود")
        insert_btn.setDefault(True)
        insert_btn.setCursor(QCursor(Qt.PointingHandCursor))
        insert_btn.setFixedHeight(40)
        insert_btn.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: 800;
                border: none;
                border-radius: 8px;
                padding: 6px 22px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
        """)
        insert_btn.clicked.connect(self._on_insert)
        btn_row.addWidget(insert_btn)

        main_layout.addLayout(btn_row)

        # Focus first widget
        if self.field_widgets:
            first_w = list(self.field_widgets.values())[0][1]
            first_w.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # If not in a multiline edit, accept
            self._on_insert()
        else:
            super().keyPressEvent(event)

    def _on_insert(self):
        answers = {}
        for name, (kind, widget) in self.field_widgets.items():
            if kind == "choice":
                answers[name] = widget.currentText().strip()
            else:
                answers[name] = widget.text().strip()
        self.answers = answers
        self.accept()

    def get_answers(self) -> Optional[dict[str, str]]:
        return self.answers

    def get_values(self) -> dict[str, str]:
        """Returns current values of all form inputs."""
        if self.answers is not None:
            return self.answers
        vals = {}
        for name, (kind, widget) in self.field_widgets.items():
            if kind == "choice":
                vals[name] = widget.currentText().strip()
            else:
                vals[name] = widget.text().strip()
        return vals
