from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QFrame, QApplication
)

from snipglide.ui_qt.styles import get_stylesheet
from snipglide.ui_qt.sidebar import SidebarQt
from snipglide.ui_qt.chat_notes_page import ChatNotesPageQt
from snipglide.ui_qt.dashboard import DashboardQt
from snipglide.ui_qt.snippet_editor_view import SnippetEditorViewQt
from snipglide.ui_qt.notes_page import NotesPageQt
from snipglide.ui_qt.clipboard_page import ClipboardPageQt
from snipglide.ui_qt.search_page import SearchPageQt
from snipglide.core.config import load_settings, save_settings, APP_NAME, get_arabic_font_family

import os
from pathlib import Path

class MainWindowQt(QMainWindow):
    def __init__(self, engine_toggle_callback=None, snippets_changed_callback=None, font_family=None):
        super().__init__()
        self.engine_toggle_callback = engine_toggle_callback
        self.snippets_changed_callback = snippets_changed_callback
        self.settings = load_settings()
        self.font_family = font_family or get_arabic_font_family()

        self.setWindowTitle(f"{APP_NAME} - Professional Edition")
        # Enlarge main frame for ultra-comfortable viewing
        self.resize(1440, 900)
        self.setMinimumSize(1200, 750)

        # Set Window Favicon Icon
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Apply Global QSS with Google Arabic font and enlarged base size
        self.setStyleSheet(get_stylesheet(font_family=self.font_family, base_font_size=15, is_dark=True))

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──
        self.sidebar = SidebarQt(self)
        self.sidebar.page_selected.connect(self.switch_page)
        main_layout.addWidget(self.sidebar)

        # ── Stacked Pages Container ──
        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack, stretch=1)

        # Instantiate Pages
        self.pages = {}
        
        # 1. Dashboard
        self.dashboard_page = DashboardQt(self)
        self.pages["Dashboard"] = self.dashboard_page
        self.stack.addWidget(self.dashboard_page)

        # 2. Snippets
        self.snippets_page = SnippetEditorViewQt(
            toast_callback=self.toast,
            snippets_changed_callback=self._on_snippets_changed,
            parent=self
        )
        self.pages["Snippets"] = self.snippets_page
        self.stack.addWidget(self.snippets_page)

        # 3. Notes
        self.notes_page = NotesPageQt(toast_callback=self.toast, parent=self)
        self.pages["Notes"] = self.notes_page
        self.stack.addWidget(self.notes_page)

        # 4. Chat Notes (WhatsApp style)
        self.chat_page = ChatNotesPageQt(
            toast_callback=self.toast,
            navigate_to_snippet_callback=self._navigate_to_snippet,
            parent=self
        )
        self.pages["ChatNotes"] = self.chat_page
        self.stack.addWidget(self.chat_page)

        # 5. Search
        self.search_page = SearchPageQt(toast_callback=self.toast, parent=self)
        self.pages["Search"] = self.search_page
        self.stack.addWidget(self.search_page)

        # 6. Clipboard
        self.clip_page = ClipboardPageQt(toast_callback=self.toast, parent=self)
        self.pages["Clipboard"] = self.clip_page
        self.stack.addWidget(self.clip_page)

        # Floating Toast Label
        self.toast_label = QLabel(self)
        self.toast_label.setObjectName("toastLabel")
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setStyleSheet("""
            QLabel#toastLabel {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                padding: 8px 16px;
            }
        """)
        self.toast_label.hide()

        # Start on Dashboard
        self.sidebar.select_page("Dashboard")

    def switch_page(self, page_id: str):
        if page_id in self.pages:
            self.stack.setCurrentWidget(self.pages[page_id])
            # Trigger page activations
            if page_id == "Dashboard":
                self.dashboard_page.refresh_stats()
            elif page_id == "ChatNotes":
                self.chat_page.refresh_chat(scroll_to_bottom=False)
            elif page_id == "Clipboard":
                self.clip_page.refresh_history()

    def toast(self, message: str, error: bool = False):
        bg = "#dc2626" if error else "#16a34a"
        self.toast_label.setStyleSheet(f"""
            QLabel#toastLabel {{
                background-color: {bg};
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                padding: 8px 18px;
            }}
        """)
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self.toast_label.move(self.width() - self.toast_label.width() - 30, 20)
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(2000, self.toast_label.hide)

    def _on_snippets_changed(self):
        if self.snippets_changed_callback:
            self.snippets_changed_callback()

    def _navigate_to_snippet(self, text: str):
        self.sidebar.select_page("Snippets")
        self.snippets_page.new_snippet(initial_content=text)
