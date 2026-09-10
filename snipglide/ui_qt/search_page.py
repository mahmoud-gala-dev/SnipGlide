"""Unified Search Page for SnipGlide.

Multi-source instant search with ranking, debouncing, and direct navigation
across Snippets, Notes, Chat Notes, Clipboard, Regexes, API Requests, Projects, and Commands.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from snipglide.database.search_repo import get_search_result_body, search_all

KIND_ICONS = {
    "Snippet": "✂️",
    "Note": "📝",
    "Chat Note": "💬",
    "Clipboard": "📋",
    "Regex": "🔍",
    "API Request": "🌐",
    "Project": "📁",
    "Command": "⌨️",
    "Screenshot": "📸",
}


class SearchPageQt(QWidget):
    toast_signal = Signal(str, bool)

    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        if toast_callback:
            self.toast_signal.connect(toast_callback)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._execute_search)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
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
        top_row.addWidget(btn_drawer)

        title = QLabel("البحث الموحد الشامل (Unified Global Search)")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #f0f2f5;")
        top_row.addWidget(title)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 ابحث فوراً عبر الاختصارات، الملاحظات، الشات، الحافظة، المشاريع، وأوامر الطرفية...")
        self.search_edit.setFixedHeight(48)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #182229;
                border: 2px solid #2a3942;
                border-radius: 10px;
                padding: 0 16px;
                font-size: 15px;
                color: #f0f2f5;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #111b21;
            }
        """)
        self.search_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_edit)

        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #111b21;
                border: 2px solid #202c33;
                border-radius: 12px;
                padding: 8px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 14px 18px;
                border-radius: 10px;
                margin-bottom: 6px;
                border: 1px solid #2a3942;
                font-size: 14px;
            }
            QListWidget::item:hover {
                background-color: #202c33;
                border-color: #3b4a54;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
                font-weight: bold;
                border: 1.5px solid #3b82f6;
            }
        """)
        self.results_list.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self.results_list, stretch=1)

    def _on_text_changed(self):
        self._debounce_timer.stop()
        self._debounce_timer.start()

    def _execute_search(self):
        self.results_list.clear()
        query = self.search_edit.text().strip()
        if not query:
            return

        results = search_all(query, limit=50)
        for r in results:
            icon = KIND_ICONS.get(r["kind"], "📌")
            fav_star = " ⭐" if r.get("is_fav") else ""
            header_text = f"{icon} [{r['kind']}] {r['title']}{fav_star}"
            body_preview = (r["body"] or "").replace("\n", " ").strip()
            if len(body_preview) > 120:
                body_preview = body_preview[:120] + "..."

            display_text = f"{header_text}\n  {body_preview}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, (r["kind"], r["ref"], r["title"]))
            self.results_list.addItem(item)

    def _on_item_activated(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data:
            return
        kind, ref, title = data
        win = self.window()

        # 1. Regex Navigation
        if kind == "Regex":
            if hasattr(win, "sidebar") and hasattr(win, "dev_toolbox_page"):
                from snipglide.database.regex_repo import RegexRepository
                try:
                    regex_obj = RegexRepository.get_by_id(int(ref))
                    if regex_obj:
                        win.sidebar.select_page("DevToolbox")
                        win.dev_toolbox_page.tabs.setCurrentIndex(8)
                        win.dev_toolbox_page.regex_widget.load_regex(regex_obj)
                        self.toast_signal.emit(f"تم فتح التعبير النمطي: {regex_obj.name} 🔍", False)
                        return
                except Exception:
                    pass

        # 2. API Request Navigation
        elif kind == "API Request":
            if hasattr(win, "sidebar") and hasattr(win, "dev_toolbox_page"):
                from snipglide.database.api_repo import ApiRepository
                repo = ApiRepository()
                try:
                    api_req = repo.get_by_id(int(ref))
                    if api_req:
                        win.sidebar.select_page("DevToolbox")
                        win.dev_toolbox_page.tabs.setCurrentIndex(9)
                        win.dev_toolbox_page.api_widget.load_request(api_req)
                        self.toast_signal.emit(f"تم تحميل طلب API: {api_req.name} 🌐", False)
                        return
                except Exception:
                    pass

        # 3. Developer Project Navigation
        elif kind == "Project":
            if hasattr(win, "sidebar") and hasattr(win, "dev_toolbox_page"):
                from snipglide.database.project_repo import ProjectRepository
                from snipglide.services.project_context import active_project_mgr
                repo = ProjectRepository()
                try:
                    proj = repo.get_by_id(int(ref))
                    if proj:
                        active_project_mgr.set_active_project(proj)
                        win.sidebar.select_page("DevToolbox")
                        win.dev_toolbox_page.tabs.setCurrentIndex(12)
                        self.toast_signal.emit(f"تم تعيين المشروع النشط: {proj.name} 📁", False)
                        return
                except Exception:
                    pass

        # 4. Terminal Command Navigation
        elif kind == "Command":
            if hasattr(win, "sidebar") and hasattr(win, "dev_toolbox_page"):
                body = get_search_result_body(kind, ref)
                if body:
                    QApplication.clipboard().setText(body)
                    win.sidebar.select_page("DevToolbox")
                    win.dev_toolbox_page.tabs.setCurrentIndex(13)
                    self.toast_signal.emit(f"تم نسخ الأمر البرمجي إلى الحافظة! ⌨️", False)
                    return

        # 5. Page Direct Navigations
        elif kind == "Note" and hasattr(win, "sidebar"):
            win.sidebar.select_page("Notes")
        elif kind == "Chat Note" and hasattr(win, "sidebar"):
            win.sidebar.select_page("ChatNotes")
        elif kind == "Clipboard" and hasattr(win, "sidebar"):
            win.sidebar.select_page("Clipboard")
        elif kind == "Screenshot" and hasattr(win, "sidebar"):
            win.sidebar.select_page("Screenshots")

        # Generic copy fallback
        body = get_search_result_body(kind, ref)
        if body:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(body)
                self.toast_signal.emit(f"تم نسخ {title} إلى الحافظة! 📋", False)
