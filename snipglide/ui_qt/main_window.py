import os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QFrame, QApplication, QFileDialog, QMenu
)

from snipglide.ui_qt.styles import get_stylesheet
from snipglide.ui_qt.sidebar import SidebarQt
from snipglide.ui_qt.chat_notes_page import ChatNotesPageQt
from snipglide.ui_qt.dashboard import DashboardQt
from snipglide.ui_qt.snippet_editor_view import SnippetEditorViewQt
from snipglide.ui_qt.notes_page import NotesPageQt
from snipglide.ui_qt.clipboard_page import ClipboardPageQt
from snipglide.ui_qt.search_page import SearchPageQt
from snipglide.ui_qt.command_palette import CommandPaletteQt
from snipglide.ui_qt.quick_paste_bar import QuickPasteBarQt
from snipglide.ui_qt.tray_icon import SnipGlideTrayIcon
from snipglide.ui_qt.email_templates_dialog import EmailTemplatesDialogQt
from snipglide.ui_qt.floating_chat_head import FloatingChatHead
from snipglide.ui_qt.web_dev_dialog import WebDevDialogQt
from snipglide.services.exporter_importer import (
    export_data_to_json, import_data_from_json, export_snippets_to_csv
)
from snipglide.core.config import load_settings, save_settings, APP_NAME, get_arabic_font_family

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

        # Set Window Favicon Icon (prioritize ICO on Windows)
        icon_ico = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
        icon_png = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        if icon_ico.exists():
            self.setWindowIcon(QIcon(str(icon_ico)))
        elif icon_png.exists():
            self.setWindowIcon(QIcon(str(icon_png)))

        # Apply Global QSS with Google Arabic font and enlarged base size
        self.setStyleSheet(get_stylesheet(font_family=self.font_family, base_font_size=15, is_dark=True))

        self._setup_ui()
        self._setup_shortcuts()

        # System Tray Icon
        self.tray_icon = SnipGlideTrayIcon(self)
        self.tray_icon.show()

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
                font-size: 14px;
                border-radius: 10px;
                padding: 10px 20px;
                border: 1px solid #22c55e;
            }
        """)
        self.toast_label.hide()

        # Start on Dashboard
        self.sidebar.select_page("Dashboard")

    def _setup_shortcuts(self):
        # Ctrl+K -> Command Palette
        self.shortcut_cmd = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut_cmd.activated.connect(self.open_command_palette)

        # Alt+Space -> Quick Paste Bar
        self.shortcut_paste = QShortcut(QKeySequence("Alt+Space"), self)
        self.shortcut_paste.activated.connect(self.open_quick_paste_bar)

    def open_command_palette(self):
        palette = CommandPaletteQt(self)
        palette.action_triggered.connect(self._handle_command_palette_action)
        palette.exec()

    def open_quick_paste_bar(self):
        bar = QuickPasteBarQt(self)
        bar.show_centered()

    def open_web_dev_toolbox(self):
        dlg = WebDevDialogQt(self)
        if dlg.exec():
            self.toast("تم نسخ الكود البرمجي بنجاح! 💻", False)

    def open_email_templates(self):
        dlg = EmailTemplatesDialogQt(self)
        if dlg.exec():
            self.toast("تم نسخ قالب البريد الإلكتروني بنجاح! 📧", False)

    def toggle_floating_chat_head(self):
        if not hasattr(self, "chat_head") or self.chat_head is None:
            self.chat_head = FloatingChatHead()
            self.chat_head.drawer.note_saved_signal.connect(lambda msg: self.toast(msg, False))
            self.chat_head.show()
            self.toast("تم إظهار فقاعة شات نوت العائمة على الشاشة! 💬", False)
        else:
            if self.chat_head.isVisible():
                self.chat_head.hide()
                self.toast("تم إخفاء فقاعة شات نوت العائمة", False)
            else:
                self.chat_head.show()
                self.toast("تم إظهار فقاعة شات نوت العائمة على الشاشة! 💬", False)

    def _handle_command_palette_action(self, kind: str, data: object):
        if kind == "nav":
            self.sidebar.select_page(str(data))
        elif kind == "action":
            if data == "new_snippet":
                self.sidebar.select_page("Snippets")
                self.snippets_page.new_snippet()
            elif data == "new_note":
                self.sidebar.select_page("Notes")
                self.notes_page.new_note()
            elif data == "web_dev":
                self.open_web_dev_toolbox()
            elif data == "email_templates":
                self.open_email_templates()
            elif data == "toggle_chat_head":
                self.toggle_floating_chat_head()
            elif data == "export_data":
                self.export_json()
            elif data == "import_data":
                self.import_json()
            elif data == "seed_demo":
                self.chat_page._seed_demo_data()
        elif kind == "copy_snippet":
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(str(data))
                self.toast("تم نسخ الاختصار إلى الحافظة! ✂️", False)
        elif kind == "copy_chat":
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(str(data))
                self.toast("تم نسخ الملاحظة إلى الحافظة! 💬", False)

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "تصدير البيانات", "snipglide_backup.json", "JSON Files (*.json)")
        if path:
            success, msg = export_data_to_json(path)
            self.toast(msg, not success)

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "استيراد البيانات", "", "JSON Files (*.json)")
        if path:
            success, msg = import_data_from_json(path)
            self.toast(msg, not success)
            self.snippets_page.refresh_list()
            self.notes_page.refresh_list()
            self.chat_page.refresh_chat()
            self._on_snippets_changed()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "تصدير الاختصارات", "snippets.csv", "CSV Files (*.csv)")
        if path:
            success, msg = export_snippets_to_csv(path)
            self.toast(msg, not success)

    def switch_page(self, page_id: str):
        if page_id in self.pages:
            self.stack.setCurrentWidget(self.pages[page_id])
            if page_id == "Dashboard":
                self.dashboard_page.refresh_stats()
            elif page_id == "ChatNotes":
                self.chat_page.refresh_chat(scroll_to_bottom=False)
            elif page_id == "Clipboard":
                self.clip_page.refresh_history()

    def toast(self, message: str, error: bool = False):
        bg = "#dc2626" if error else "#16a34a"
        border = "#ef4444" if error else "#22c55e"
        self.toast_label.setStyleSheet(f"""
            QLabel#toastLabel {{
                background-color: {bg};
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 10px;
                padding: 10px 22px;
                border: 1.5px solid {border};
            }}
        """)
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self.toast_label.move(self.width() - self.toast_label.width() - 30, 20)
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(2500, self.toast_label.hide)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 12px;
                padding: 6px;
                color: #f0f2f5;
                font-size: 14px;
                font-weight: bold;
            }
            QMenu::item {
                padding: 10px 24px;
                border-radius: 8px;
                margin: 2px 4px;
            }
            QMenu::item:selected {
                background-color: #172554;
                color: #93c5fd;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2a3942;
                margin: 6px 10px;
            }
        """)

        # Fast Tools
        act_cmd = menu.addAction("⌨️ لوحة الأوامر السريعة (Ctrl+K)")
        act_paste = menu.addAction("⚡ شريط اللصق السريع (Alt+Space)")
        act_web = menu.addAction("🛠️ مستودع أكواد مبرمج الويب (Web Dev)")
        act_emails = menu.addAction("📧 قوالب البريد الإلكتروني الذكية")
        act_head = menu.addAction("💬 إظهار/إخفاء فقاعة شات نوت العائمة")
        menu.addSeparator()

        # Navigation Section
        menu.addSection("🚀 التنقل السريع")
        nav_dash = menu.addAction("📊 لوحة التحكم (Dashboard)")
        nav_snip = menu.addAction("✂️ إدارة الاختصارات (Snippets)")
        nav_note = menu.addAction("📝 الملاحظات العادية (Notes)")
        nav_chat = menu.addAction("💬 شات نوت الواتساب (Chat Notes)")
        nav_search = menu.addAction("🔍 البحث الموحد الشامل (Search)")
        nav_clip = menu.addAction("📋 سجل الحافظة (Clipboard)")

        menu.addSeparator()

        # Quick Actions Section
        menu.addSection("⚡ إجراءات سريعة")
        act_new_snip = menu.addAction("➕ إنشاء اختصار جديد")
        act_new_note = menu.addAction("📝 كتابة ملاحظة جديدة")
        act_focus_chat = menu.addAction("💬 التركيز على شات نوت")
        act_seed_demo = menu.addAction("🌱 إضافة عينات وبيانات تجريبية")

        menu.addSeparator()

        # Data & Tools
        menu.addSection("💾 النسخ الاحتياطي والبيانات")
        act_export = menu.addAction("💾 تصدير كافة البيانات (JSON)")
        act_import = menu.addAction("📥 استيراد البيانات (JSON)")
        act_export_csv = menu.addAction("📊 تصدير الاختصارات إلى (CSV)")

        menu.addSeparator()
        act_reload_engine = menu.addAction("🔄 إعادة تحميل الاختصارات في المحرك")
        act_clear_clip = menu.addAction("🗑️ مسح سجل الحافظة")

        action = menu.exec(event.globalPos())
        if not action:
            return

        if action == act_cmd:
            self.open_command_palette()
        elif action == act_paste:
            self.open_quick_paste_bar()
        elif action == act_web:
            self.open_web_dev_toolbox()
        elif action == act_emails:
            self.open_email_templates()
        elif action == act_head:
            self.toggle_floating_chat_head()
        elif action == nav_dash:
            self.sidebar.select_page("Dashboard")
        elif action == nav_snip:
            self.sidebar.select_page("Snippets")
        elif action == nav_note:
            self.sidebar.select_page("Notes")
        elif action == nav_chat:
            self.sidebar.select_page("ChatNotes")
        elif action == nav_search:
            self.sidebar.select_page("Search")
        elif action == nav_clip:
            self.sidebar.select_page("Clipboard")
        elif action == act_new_snip:
            self.sidebar.select_page("Snippets")
            self.snippets_page.new_snippet()
        elif action == act_new_note:
            self.sidebar.select_page("Notes")
            self.notes_page.new_note()
        elif action == act_focus_chat:
            self.sidebar.select_page("ChatNotes")
            self.chat_page.message_input.setFocus()
        elif action == act_seed_demo:
            self.chat_page._seed_demo_data()
        elif action == act_export:
            self.export_json()
        elif action == act_import:
            self.import_json()
        elif action == act_export_csv:
            self.export_csv()
        elif action == act_reload_engine:
            self._on_snippets_changed()
            self.toast("تمت إعادة تحميل الاختصارات في محرك التوسيع ⚡", False)
        elif action == act_clear_clip:
            self.clip_page._clear_all()

    def _on_snippets_changed(self):
        if self.snippets_changed_callback:
            self.snippets_changed_callback()

    def _navigate_to_snippet(self, text: str):
        self.sidebar.select_page("Snippets")
        self.snippets_page.new_snippet(initial_content=text)

    def closeEvent(self, event):
        if hasattr(self, "tray_icon") and self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "SnipGlide Pro",
                "التطبيق ما زال يعمل في الخلفية بجوار الساعة! ⚡\nانقر على الأيقونة لفتح البرنامج مجدداً.",
                self.tray_icon.MessageIcon.Information,
                2000
            )
        else:
            event.accept()

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            if hasattr(self, "tray_icon") and self.tray_icon and self.tray_icon.isVisible():
                QTimer.singleShot(0, self.hide)
        super().changeEvent(event)
