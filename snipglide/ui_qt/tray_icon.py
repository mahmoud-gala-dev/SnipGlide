from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from snipglide.database.snippet_repo import get_all_snippets
from snipglide.database.chat_note_repo import get_all_chat_notes

class SnipGlideTrayIcon(QSystemTrayIcon):
    def __init__(self, main_window, parent=None):
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        super().__init__(icon, parent)
        self.main_window = main_window

        self.setToolTip("SnipGlide Pro - Text Expander & Notes")
        self._setup_menu()
        self.activated.connect(self._on_tray_activated)

    def _setup_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
                padding: 6px;
                color: #f0f2f5;
                font-size: 13px;
                font-weight: bold;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #172554;
                color: #93c5fd;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2a3942;
                margin: 4px 8px;
            }
        """)

        # Open Window
        act_open = menu.addAction("🟢 فتح SnipGlide Pro")
        act_open.triggered.connect(self._show_window)

        # Screenshots & Video Quick Actions
        act_shot_full = menu.addAction("📸 التقاط الشاشة كاملة (Ctrl + Print)")
        act_shot_full.triggered.connect(self._capture_full_screen)

        act_shot_area = menu.addAction("✂️ تحديد جزء من الشاشة (Win + Print)")
        act_shot_area.triggered.connect(self._start_area_capture)

        act_rec_full = menu.addAction("🎥 بدء تسجيل فيديو (شاشة كاملة)")
        act_rec_full.triggered.connect(self._start_video_record_full)

        act_rec_area = menu.addAction("🎬 بدء تسجيل فيديو (مساحة محددة)")
        act_rec_area.triggered.connect(self._start_video_record_area)

        act_open_shots = menu.addAction("🖼️ استعراض اللقطات والتسجيلات")
        act_open_shots.triggered.connect(self._open_screenshots_page)

        menu.addSeparator()

        act_paste_bar = menu.addAction("⚡ شريط اللصق السريع (Alt+Space)")
        act_paste_bar.triggered.connect(self._open_paste_bar)

        act_cmd = menu.addAction("⌨️ لوحة الأوامر (Ctrl+K)")
        act_cmd.triggered.connect(self._open_cmd_palette)

        # Tools Submenu
        tools_menu = menu.addMenu("🛠️ أدوات وقوالب")
        act_head = tools_menu.addAction("💬 فقاعة شات نوت العائمة")
        act_head.triggered.connect(self._toggle_chat_head)
        act_emails = tools_menu.addAction("📧 قوالب البريد الإلكتروني")
        act_emails.triggered.connect(self._open_email_templates)

        menu.addSeparator()

        # Recent Snippets Submenu
        snip_menu = menu.addMenu("✂️ آخر الاختصارات (نسخ بنقرة)")
        for s in get_all_snippets()[:6]:
            act = snip_menu.addAction(f"[{s.shortcut}] {s.description or s.replacement[:30]}")
            act.triggered.connect(lambda _, text=s.replacement: self._copy_text(text))

        # Recent Chat Notes Submenu
        chat_menu = menu.addMenu("💬 آخر الملاحظات السريعة")
        for c in get_all_chat_notes()[:6]:
            act = chat_menu.addAction(f"💬 {c.content.replace(chr(10), ' ')[:35]}")
            act.triggered.connect(lambda _, text=c.content: self._copy_text(text))

        menu.addSeparator()

        # Exit
        act_exit = menu.addAction("🚪 إغلاق التطبيق نهائياً")
        act_exit.triggered.connect(QApplication.instance().quit)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_window()

    def _toggle_window(self):
        if self.main_window:
            if self.main_window.isVisible() and not self.main_window.isMinimized():
                self.main_window.hide()
            else:
                self.main_window.show_and_activate()

    def _show_window(self):
        if self.main_window:
            if hasattr(self.main_window, "show_and_activate"):
                self.main_window.show_and_activate()
            else:
                self.main_window.showNormal()
                self.main_window.raise_()
                self.main_window.activateWindow()

    def _open_paste_bar(self):
        if self.main_window and hasattr(self.main_window, "open_quick_paste_bar"):
            self.main_window.open_quick_paste_bar()

    def _open_cmd_palette(self):
        if self.main_window and hasattr(self.main_window, "open_command_palette"):
            self.main_window.open_command_palette()

    def _open_email_templates(self):
        if self.main_window and hasattr(self.main_window, "open_email_templates"):
            self.main_window.open_email_templates()

    def _toggle_chat_head(self):
        if self.main_window and hasattr(self.main_window, "toggle_floating_chat_head"):
            self.main_window.toggle_floating_chat_head()

    def _capture_full_screen(self):
        if self.main_window and hasattr(self.main_window, "_capture_full_screen"):
            self.main_window._capture_full_screen()

    def _start_area_capture(self):
        if self.main_window and hasattr(self.main_window, "_start_area_capture"):
            self.main_window._start_area_capture()

    def _start_video_record_full(self):
        if self.main_window and hasattr(self.main_window, "_trigger_full_video_record"):
            self.main_window._trigger_full_video_record()

    def _start_video_record_area(self):
        if self.main_window and hasattr(self.main_window, "_trigger_area_video_record"):
            self.main_window._trigger_area_video_record()

    def _open_screenshots_page(self):
        if self.main_window:
            self.main_window.show_and_activate()
            if hasattr(self.main_window, "sidebar"):
                self.main_window.sidebar.select_page("Screenshots")

    def _copy_text(self, text: str):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.showMessage("SnipGlide", "تم نسخ النص إلى الحافظة! 📋", QSystemTrayIcon.Information, 1500)
