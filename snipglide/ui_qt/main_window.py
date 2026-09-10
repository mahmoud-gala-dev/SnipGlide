import os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QKeySequence, QShortcut, QCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QFrame, QApplication, QFileDialog, QMenu, QPushButton
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
from snipglide.ui_qt.notepad_page import NotepadPageQt
from snipglide.ui_qt.screenshots_page import ScreenshotsPageQt
from snipglide.ui_qt.dev_toolbox_page import DevToolboxPageQt
from snipglide.services.exporter_importer import (
    export_data_to_json, import_data_from_json, export_snippets_to_csv
)
from snipglide.core.config import load_settings, save_settings, APP_NAME, get_arabic_font_family

class MainWindowQt(QMainWindow):
    def __init__(self, engine_toggle_callback=None, snippets_changed_callback=None, font_family=None, screenshot_service=None, recording_service=None):
        super().__init__()
        self.engine_toggle_callback = engine_toggle_callback
        self.snippets_changed_callback = snippets_changed_callback
        self.screenshot_service = screenshot_service
        self.recording_service = recording_service
        self.settings = load_settings()
        self.font_family = font_family or get_arabic_font_family()

        self.setWindowTitle(f"{APP_NAME} - Professional Edition")
        # Enlarge main frame for ultra-comfortable spacious viewing
        self.resize(1560, 960)
        self.setMinimumSize(1250, 780)

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
        self.sidebar.collapse_requested.connect(self.toggle_sidebar)
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

        # 2. Developer Toolbox
        self.dev_toolbox_page = DevToolboxPageQt(toast_callback=self.toast, parent=self)
        self.pages["DevToolbox"] = self.dev_toolbox_page
        self.stack.addWidget(self.dev_toolbox_page)

        # 3. Snippets
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

        # 5. Notepad (Windows Notepad Full-Featured)
        self.notepad_page = NotepadPageQt(toast_callback=self.toast, parent=self)
        self.pages["Notepad"] = self.notepad_page
        self.stack.addWidget(self.notepad_page)

        # 6. Screenshots
        self.screenshots_page = ScreenshotsPageQt(
            screenshot_service=self.screenshot_service,
            recording_service=self.recording_service,
            toast_callback=self.toast,
            parent=self
        )
        self.pages["Screenshots"] = self.screenshots_page
        self.stack.addWidget(self.screenshots_page)

        # 7. Search
        self.search_page = SearchPageQt(toast_callback=self.toast, parent=self)
        self.pages["Search"] = self.search_page
        self.stack.addWidget(self.search_page)

        # 8. Clipboard
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

        # Esc -> Exit focus mode if active, else minimize window
        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.shortcut_esc.activated.connect(self._on_esc_pressed)

        # Screenshots Shortcuts within Window
        try:
            self.shortcut_shot_full = QShortcut(QKeySequence("Ctrl+Print"), self)
            self.shortcut_shot_full.activated.connect(self._capture_full_screen)
            self.shortcut_shot_area = QShortcut(QKeySequence("Ctrl+Alt+Print"), self)
            self.shortcut_shot_area.activated.connect(self._start_area_capture)
        except Exception:
            pass

        # Ctrl+B -> Toggle Sidebar Drawer (إظهار / إخفاء القائمة الجانبية)
        self.shortcut_drawer = QShortcut(QKeySequence("Ctrl+B"), self)
        self.shortcut_drawer.activated.connect(self.toggle_sidebar)

    def toggle_sidebar(self):
        """Toggle sidebar visibility (drawer show/hide)."""
        is_vis = self.sidebar.isVisible()
        self.sidebar.setVisible(not is_vis)
        msg = "تم إخفاء القائمة الجانبية (Drawer)" if is_vis else "تم إظهار القائمة الجانبية (Drawer)"
        self.toast(msg, False)
        for page in getattr(self, "pages", {}).values():
            if hasattr(page, "on_sidebar_toggled"):
                try:
                    page.on_sidebar_toggled(not is_vis)
                except Exception:
                    pass

    def show_and_activate(self):
        """Bring window to foreground from background or system tray reliably."""
        # 1. Unminimize and reset Qt window flags
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

        # 2. Force Windows OS foreground focus
        try:
            import ctypes
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # SW_RESTORE = 9, SW_SHOW = 5
            user32.ShowWindow(hwnd, 9)

            fore_hwnd = user32.GetForegroundWindow()
            if fore_hwnd != hwnd:
                fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
                app_thread = kernel32.GetCurrentThreadId()
                if fore_thread and fore_thread != app_thread:
                    user32.AttachThreadInput(fore_thread, app_thread, True)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.AttachThreadInput(fore_thread, app_thread, False)
                else:
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
            else:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

        self.toast("⚡ تم استعادة وفتح نافذة SnipGlide", False)

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
            if data == "capture_full":
                self._capture_full_screen()
            elif data == "capture_area":
                self._start_area_capture()
            elif data == "new_snippet":
                self.sidebar.select_page("Snippets")
                self.snippets_page.new_snippet()
            elif data == "new_note":
                self.sidebar.select_page("Notes")
                self.notes_page.new_note()
            elif data == "new_notepad":
                self.sidebar.select_page("Notepad")
                self.notepad_page.new_tab()
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
            elif data == "dev_json":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(0)
            elif data == "dev_base64":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(1)
            elif data == "dev_url":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(2)
            elif data == "dev_jwt":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(3)
            elif data == "dev_uuid":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(4)
            elif data == "dev_timestamp":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(5)
            elif data == "dev_hash":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(6)
            elif data == "dev_text":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(7)
            elif data == "dev_regex":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(8)
            elif data == "dev_regex_library":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(8)
                if hasattr(self.dev_toolbox_page, "regex_widget"):
                    self.dev_toolbox_page.regex_widget.open_library()
            elif data == "dev_api":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(9)
            elif data == "dev_api_saved":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(9)
                if hasattr(self.dev_toolbox_page, "api_widget"):
                    self.dev_toolbox_page.api_widget.open_saved_requests()
            elif data == "dev_git":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(10)
            elif data == "dev_ai_coding":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(11)
            elif data == "dev_projects":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(12)
            elif data == "dev_commands":
                self.sidebar.select_page("DevToolbox")
                self.dev_toolbox_page.tabs.setCurrentIndex(13)
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
            elif page_id == "Screenshots":
                self.screenshots_page.refresh_list()

    def _capture_full_screen(self):
        if self.screenshot_service:
            self.screenshot_service.capture_full_screen()

    def _start_area_capture(self):
        if self.screenshot_service:
            self.screenshot_service.start_area_capture()

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
        menu_style = """
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
                padding: 9px 22px;
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
        """
        menu.setStyleSheet(menu_style)

        # ── Quick Access Direct Actions ──
        act_paste = menu.addAction("⚡ شريط اللصق السريع (Alt+Space)")
        act_cmd = menu.addAction("⌨️ لوحة الأوامر السريعة (Ctrl+K)")
        act_head = menu.addAction("💬 فقاعة شات نوت العائمة")
        menu.addSeparator()

        # ── 1. Navigation Submenu ──
        nav_menu = menu.addMenu("🚀 التنقل السريع")
        nav_menu.setStyleSheet(menu_style)
        nav_dash = nav_menu.addAction("📊 لوحة التحكم (Dashboard)")
        nav_dev = nav_menu.addAction("🛠️ أدوات المطورين (Dev Toolbox)")
        nav_snip = nav_menu.addAction("✂️ إدارة الاختصارات (Snippets)")
        nav_note = nav_menu.addAction("📝 الملاحظات العادية (Notes)")
        nav_chat = nav_menu.addAction("💬 شات نوت الواتساب (Chat Notes)")
        nav_notepad = nav_menu.addAction("🗒️ مفكرة ويندوز (Notepad)")
        nav_shots = nav_menu.addAction("📸 لقطات وقص الشاشة (Screenshots)")
        nav_search = nav_menu.addAction("🔍 البحث الموحد الشامل (Search)")
        nav_clip = nav_menu.addAction("📋 سجل الحافظة (Clipboard)")

        # ── 2. Quick Actions Submenu ──
        actions_menu = menu.addMenu("⚡ إجراءات سريعة")
        actions_menu.setStyleSheet(menu_style)
        act_shot_full = actions_menu.addAction("📸 التقاط الشاشة بالكامل (Ctrl+Print)")
        act_shot_area = actions_menu.addAction("✂️ تحديد جزء من الشاشة (Win+Print)")
        act_new_snip = actions_menu.addAction("➕ إنشاء اختصار جديد")
        act_new_note = actions_menu.addAction("📝 كتابة ملاحظة جديدة")
        act_new_notepad = actions_menu.addAction("🗒️ فتح مستند جديد في المفكرة")
        act_focus_chat = actions_menu.addAction("💬 التركيز على شات نوت")
        act_seed_demo = actions_menu.addAction("🌱 إضافة عينات وبيانات تجريبية")

        # ── 3. Tools & Templates Submenu ──
        tools_menu = menu.addMenu("🛠️ أدوات وقوالب")
        tools_menu.setStyleSheet(menu_style)
        act_web = tools_menu.addAction("💻 مستودع أكواد الويب (Web Dev)")
        act_emails = tools_menu.addAction("📧 قوالب البريد الإلكتروني")

        # ── 4. Backup & Maintenance Submenu ──
        data_menu = menu.addMenu("💾 النسخ الاحتياطي والبيانات")
        data_menu.setStyleSheet(menu_style)
        act_export = data_menu.addAction("💾 تصدير كافة البيانات (JSON)")
        act_import = data_menu.addAction("📥 استيراد البيانات (JSON)")
        act_export_csv = data_menu.addAction("📊 تصدير الاختصارات (CSV)")
        data_menu.addSeparator()
        act_reload_engine = data_menu.addAction("🔄 إعادة تحميل الاختصارات في المحرك")
        act_clear_clip = data_menu.addAction("🗑️ مسح سجل الحافظة")

        action = menu.exec(event.globalPos())
        if not action:
            return

        if action == act_paste:
            self.open_quick_paste_bar()
        elif action == act_cmd:
            self.open_command_palette()
        elif action == act_head:
            self.toggle_floating_chat_head()
        elif action == nav_dash:
            self.sidebar.select_page("Dashboard")
        elif action == nav_dev:
            self.sidebar.select_page("DevToolbox")
        elif action == nav_snip:
            self.sidebar.select_page("Snippets")
        elif action == nav_note:
            self.sidebar.select_page("Notes")
        elif action == nav_chat:
            self.sidebar.select_page("ChatNotes")
        elif action == nav_notepad:
            self.sidebar.select_page("Notepad")
        elif action == nav_shots:
            self.sidebar.select_page("Screenshots")
        elif action == nav_search:
            self.sidebar.select_page("Search")
        elif action == nav_clip:
            self.sidebar.select_page("Clipboard")
        elif action == act_shot_full:
            self._capture_full_screen()
        elif action == act_shot_area:
            self._start_area_capture()
        elif action == act_new_snip:
            self.sidebar.select_page("Snippets")
            self.snippets_page.new_snippet()
        elif action == act_new_note:
            self.sidebar.select_page("Notes")
            self.notes_page.new_note()
        elif action == act_new_notepad:
            self.sidebar.select_page("Notepad")
            self.notepad_page.new_tab()
        elif action == act_focus_chat:
            self.sidebar.select_page("ChatNotes")
            self.chat_page.message_input.setFocus()
        elif action == act_seed_demo:
            self.chat_page._seed_demo_data()
        elif action == act_web:
            self.open_web_dev_toolbox()
        elif action == act_emails:
            self.open_email_templates()
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

    def _capture_full_screen(self):
        if self.screenshot_service:
            self.screenshot_service.capture_full_screen()

    def _start_area_capture(self):
        if self.screenshot_service:
            self.screenshot_service.start_area_capture()

    def _trigger_full_video_record(self):
        if self.recording_service:
            self.recording_service.start_full_screen_recording()

    def _trigger_area_video_record(self):
        if self.recording_service:
            self.recording_service.start_area_recording()

    def _navigate_to_snippet(self, text: str):
        self.sidebar.select_page("Snippets")
        self.snippets_page.new_snippet(initial_content=text)

    def closeEvent(self, event):
        if hasattr(self, "notepad_page") and self.notepad_page:
            try:
                self.notepad_page._save_session_state()
            except Exception:
                pass

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

    def _on_esc_pressed(self):
        """Handle Escape key: if Notepad is in focus mode, exit it first; otherwise minimize."""
        if hasattr(self, "notepad_page") and getattr(self.notepad_page, "_is_focus_mode", False):
            self.notepad_page.exit_focus_mode()
            return
        self.showMinimized()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_esc_pressed()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
