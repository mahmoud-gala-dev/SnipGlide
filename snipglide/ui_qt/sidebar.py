from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QButtonGroup
)

class SidebarQt(QFrame):
    page_selected = Signal(str)
    collapse_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setFixedWidth(250)
        self.setStyleSheet("""
            QFrame#sidebarFrame {
                background-color: #0c1317;
                border-right: 1px solid #1f2c34;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(6)

        # App Brand Header with Drawer Collapse Button
        header_box = QHBoxLayout()
        header_box.setContentsMargins(0, 0, 0, 0)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)
        brand_lbl = QLabel("SnipGlide")
        brand_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        brand_col.addWidget(brand_lbl)

        sub_lbl = QLabel("Text Expander Pro")
        sub_lbl.setStyleSheet("font-size: 12px; color: #8696a0;")
        brand_col.addWidget(sub_lbl)
        header_box.addLayout(brand_col)

        header_box.addStretch()

        self.btn_collapse = QPushButton("◀")
        self.btn_collapse.setToolTip("إخفاء القائمة الجانبية (Drawer) - Ctrl+B")
        self.btn_collapse.setFixedSize(30, 30)
        self.btn_collapse.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #8696a0;
                border: 1px solid #2a3942;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #202c33;
                color: #60a5fa;
                border-color: #3b82f6;
            }
        """)
        self.btn_collapse.clicked.connect(self.collapse_requested.emit)
        header_box.addWidget(self.btn_collapse)
        layout.addLayout(header_box)

        layout.addSpacing(14)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.buttons = {}

        pages = [
            ("Dashboard", "📊 لوحة التحكم (Dashboard)", "#2563eb"),
            ("Snippets", "✂️ الاختصارات (Snippets)", "#16a34a"),
            ("Notes", "📝 الملاحظات (Notes)", "#f59e0b"),
            ("ChatNotes", "💬 شات نوت (Chat Notes)", "#25D366"),
            ("Notepad", "🗒️ المفكرة (Notepad)", "#0ea5e9"),
            ("Screenshots", "📸 لقطات وتسجيل الفيديو", "#8b5cf6"),
            ("Search", "🔍 البحث الموحد (Search)", "#14b8a6"),
            ("Clipboard", "📋 سجل الحافظة (Clipboard)", "#06b6d4"),
        ]

        for page_id, title, color in pages:
            btn = QPushButton(title)
            btn.setProperty("class", "navButton")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFixedHeight(46)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding-left: 16px;
                    border-radius: 8px;
                    background-color: transparent;
                    color: #8696a0;
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1f2c34;
                    color: #e9edef;
                }
                QPushButton:checked {
                    background-color: #172554;
                    color: #60a5fa;
                    border-left: 4px solid #3b82f6;
                }
            """)
            btn.clicked.connect(lambda _, p=page_id: self.select_page(p))
            self.btn_group.addButton(btn)
            self.buttons[page_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def select_page(self, page_id: str):
        if page_id in self.buttons:
            self.buttons[page_id].setChecked(True)
            self.page_selected.emit(page_id)
