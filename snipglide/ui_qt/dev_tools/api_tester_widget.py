import json
import time
from typing import Optional, Any
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCursor, QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QFrame, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QSplitter, QDialog,
    QListWidget, QListWidgetItem, QMessageBox, QApplication, QFileDialog
)

from snipglide.models.api_request import ApiRequest, ApiHistoryEntry, ApiResponse
from snipglide.services.api_client_service import ApiClientService
from snipglide.database.api_repo import ApiRepository
from snipglide.ui_qt.dev_tools.common import (
    create_section_card, create_tool_button, create_code_editor,
    show_status_badge, copy_to_clipboard
)


class ApiRequestWorker(QThread):
    """Executes network request in background to keep UI responsive."""
    result_ready = Signal(object)

    def __init__(self, method: str, url: str, headers: dict, body_bytes: Optional[bytes], timeout: float = 15.0):
        super().__init__()
        self.method = method
        self.url = url
        self.headers = headers
        self.body_bytes = body_bytes
        self.timeout = timeout
        self.is_cancelled = False
        self.finished.connect(self.deleteLater)

    def run(self):
        if self.is_cancelled:
            return
        res = ApiClientService.execute_request(
            method=self.method,
            url=self.url,
            headers=self.headers,
            body_bytes=self.body_bytes,
            timeout=self.timeout
        )
        if not self.is_cancelled:
            self.result_ready.emit(res)

    def cancel(self):
        self.is_cancelled = True


class KeyValueTable(QTableWidget):
    """Reusable table widget for Query Params and Headers editing."""
    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["تفعيل", "المفتاح (Key)", "القيمة (Value)"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setColumnWidth(1, 160)
        self.setStyleSheet("""
            QTableWidget {
                background-color: #111b21;
                border: 1px solid #2a3942;
                border-radius: 8px;
                color: #f0f2f5;
                font-family: 'Consolas', monospace;
                gridline-color: #202c33;
            }
            QHeaderView::section {
                background-color: #182229;
                color: #94a3b8;
                font-weight: bold;
                border: none;
                padding: 6px;
            }
        """)

    def add_pair(self, key: str = "", value: str = "", enabled: bool = True):
        row = self.rowCount()
        self.insertRow(row)

        chk = QCheckBox()
        chk.setChecked(enabled)
        chk.setStyleSheet("margin-left: 8px;")
        self.setCellWidget(row, 0, chk)

        k_item = QTableWidgetItem(key)
        v_item = QTableWidgetItem(value)
        self.setItem(row, 1, k_item)
        self.setItem(row, 2, v_item)

    def get_pairs(self) -> list[dict[str, Any]]:
        pairs = []
        for r in range(self.rowCount()):
            chk = self.cellWidget(r, 0)
            enabled = chk.isChecked() if isinstance(chk, QCheckBox) else True
            k = self.item(r, 1).text() if self.item(r, 1) else ""
            v = self.item(r, 2).text() if self.item(r, 2) else ""
            if k.strip():
                pairs.append({"key": k.strip(), "value": v, "enabled": enabled})
        return pairs

    def set_pairs(self, pairs: list[dict[str, Any]]):
        self.setRowCount(0)
        for p in pairs or []:
            self.add_pair(p.get("key", ""), str(p.get("value", "")), p.get("enabled", True))


class SavedApiRequestsDialog(QDialog):
    """Dialog to view, search, load, duplicate, and delete saved API requests."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("مكتبة طلبات الـ API المحفوظة")
        self.resize(750, 500)
        self.setStyleSheet("background-color: #111b21; color: #f0f2f5; font-family: 'Segoe UI', 'Tajawal', sans-serif;")
        self.selected_request: Optional[ApiRequest] = None
        self._setup_ui()
        self._load_requests()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header & Search
        top_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 ابحث في الطلبات المحفوظة بالاسم أو الرابط...")
        self.search_edit.setFixedHeight(38)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #182229;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px 12px;
                color: #f0f2f5;
            }
        """)
        self.search_edit.textChanged.connect(self._load_requests)
        top_row.addWidget(self.search_edit)
        layout.addLayout(top_row)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #182229;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
                margin-bottom: 4px;
                background-color: #111b21;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_load_selected)
        layout.addWidget(self.list_widget, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_load = create_tool_button("تحميل الطلب (Load)", "#16a34a", self._on_load_selected)
        btn_dup = create_tool_button("تكرار (Duplicate)", "#3b82f6", self._on_duplicate_selected)
        btn_del = create_tool_button("حذف", "#dc2626", self._on_delete_selected)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_dup)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _load_requests(self):
        self.list_widget.clear()
        query = self.search_edit.text().strip()
        items = ApiRepository.get_all_requests(search=query)
        for r in items:
            fav = "⭐ " if r.is_favorite else ""
            item = QListWidgetItem(f"{fav}[{r.method}] {r.name}  —  {r.url}")
            item.setData(Qt.UserRole, r.id)
            self.list_widget.addItem(item)

    def _on_load_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        rid = item.data(Qt.UserRole)
        self.selected_request = ApiRepository.get_request_by_id(rid)
        if self.selected_request:
            self.accept()

    def _on_duplicate_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        rid = item.data(Qt.UserRole)
        req = ApiRepository.get_request_by_id(rid)
        if req:
            req.id = None
            req.name = f"{req.name} (Copy)"
            ApiRepository.add_request(req)
            self._load_requests()

    def _on_delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        rid = item.data(Qt.UserRole)
        if QMessageBox.question(self, "تأكيد الحذف", "هل تريد حذف هذا الطلب المحفوظ؟") == QMessageBox.Yes:
            ApiRepository.delete_request(rid)
            self._load_requests()


class SaveApiRequestDialog(QDialog):
    """Modal dialog for saving API requests with explicit credential security opt-in."""
    def __init__(self, default_name: str, collections: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("حفظ الطلب في المكتبة")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog {
                background-color: #111b21;
                color: #f0f2f5;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #202c33;
                border: 1px solid #3b4a54;
                border-radius: 6px;
                padding: 6px 10px;
                color: #f0f2f5;
                font-size: 13px;
            }
            QCheckBox {
                color: #f0f2f5;
                font-size: 13px;
                spacing: 8px;
            }
            QPushButton {
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(QLabel("اسم الطلب (Request Name):"))
        self.name_edit = QLineEdit(default_name)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("المجموعة (Collection):"))
        self.collection_combo = QComboBox()
        self.collection_combo.setEditable(True)
        colls = list(collections) if collections else ["General"]
        if "General" not in colls:
            colls.insert(0, "General")
        self.collection_combo.addItems(colls)
        layout.addWidget(self.collection_combo)

        self.chk_save_creds = QCheckBox("حفظ بيانات الاعتماد والمفاتيح السرية بأمان (Save credentials securely)")
        self.chk_save_creds.setChecked(False)  # DEFAULT = OFF!
        layout.addWidget(self.chk_save_creds)

        hint = QLabel("افتراضياً: يتم إزالة التوكن وكلمات المرور لحماية خصوصيتك وأمانك ما لم يتم تفعيل الخيار أعلاه وتشفيرها.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(hint)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("حفظ الطلب 💾")
        btn_save.setStyleSheet("background-color: #16a34a; color: white;")
        btn_save.clicked.connect(self.accept)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_data(self) -> tuple[str, str, bool]:
        return (
            self.name_edit.text().strip() or "API Request",
            self.collection_combo.currentText().strip() or "General",
            self.chk_save_creds.isChecked(),
        )


class CopyCurlDialog(QDialog):
    """Modal dialog for generating cURL with redaction by default and explicit confirmation for credentials."""
    def __init__(self, method: str, url: str, headers: dict, body: str, parent=None):
        super().__init__(parent)
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body

        self.setWindowTitle("نسخ أمر cURL")
        self.setMinimumWidth(560)
        self.setStyleSheet("""
            QDialog {
                background-color: #111b21;
                color: #f0f2f5;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
            QCheckBox {
                color: #f0f2f5;
                font-size: 13px;
            }
            QPlainTextEdit {
                background-color: #1a232a;
                border: 1px solid #3b4a54;
                border-radius: 6px;
                color: #a7f3d0;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton {
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(QLabel("معاينة أمر cURL:"))
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFixedHeight(120)
        layout.addWidget(self.preview_edit)

        self.chk_include_creds = QCheckBox("تضمين بيانات الاعتماد والمفاتيح السرية (Include credentials in cURL)")
        self.chk_include_creds.setChecked(False)  # DEFAULT = OFF!
        self.chk_include_creds.toggled.connect(self._on_creds_toggled)
        layout.addWidget(self.chk_include_creds)

        self.lbl_warning = QLabel("افتراضياً: يتم حجب الرموز السرية [REDACTED] لمنع تسريب بياناتك.")
        self.lbl_warning.setStyleSheet("color: #38bdf8; font-size: 11px;")
        layout.addWidget(self.lbl_warning)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_cancel.clicked.connect(self.reject)
        btn_copy = QPushButton("📋 نسخ إلى الحافظة")
        btn_copy.setStyleSheet("background-color: #2563eb; color: white;")
        btn_copy.clicked.connect(self._copy_and_close)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_copy)
        layout.addLayout(btn_box)

        self._update_preview()

    def _update_preview(self):
        include_creds = self.chk_include_creds.isChecked()
        cmd = ApiClientService.generate_curl_command(
            self.method, self.url, self.headers, self.body, redact_secrets=not include_creds
        )
        self.preview_edit.setPlainText(cmd)

    def _on_creds_toggled(self, checked: bool):
        if checked:
            reply = QMessageBox.warning(
                self,
                "تحذير أمني",
                "⚠️ تحذير: سيتم تضمين الرموز السرية ومفاتيح الـ API في أمر cURL كنص صريح!\nهل أنت متأكد من المتابعة؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.chk_include_creds.blockSignals(True)
                self.chk_include_creds.setChecked(False)
                self.chk_include_creds.blockSignals(False)
                return
            self.lbl_warning.setText("⚠️ تنبيه: أمر cURL يحتوي الآن على بيانات اعتماد صريحة.")
            self.lbl_warning.setStyleSheet("color: #f87171; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_warning.setText("افتراضياً: يتم حجب الرموز السرية [REDACTED] لمنع تسريب بياناتك.")
            self.lbl_warning.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self._update_preview()

    def _copy_and_close(self):
        text = self.preview_edit.toPlainText().strip()
        if text:
            copy_to_clipboard(text)
            QMessageBox.information(self, "تم النسخ", "تم نسخ أمر cURL إلى الحافظة بنجاح! 📋")
            self.accept()


class ApiTesterWidget(QWidget):
    """
    Main REST API Tester widget integrated inside SnipGlide Developer Tools.
    Features method selector, query/header/auth/body builders, response visualizer,
    cURL generation, and history/saved requests managers.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_worker: Optional[ApiRequestWorker] = None
        self.current_saved_id: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # ── Top Bar: Method, URL, Send & Cancel ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        self.method_combo.setFixedWidth(110)
        self.method_combo.setFixedHeight(40)
        self.method_combo.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.method_combo.setStyleSheet("""
            QComboBox {
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 8px;
                color: #22c55e;
                font-weight: bold;
                padding: 4px 8px;
            }
        """)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        top_bar.addWidget(self.method_combo)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("أدخل عنوان الرابط (URL)... مثال: https://api.github.com/users")
        self.url_edit.setFixedHeight(40)
        self.url_edit.setFont(QFont("Consolas", 12))
        self.url_edit.setStyleSheet("""
            QLineEdit {
                background-color: #111b21;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 6px 12px;
                color: #f0f2f5;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.url_edit.returnPressed.connect(self.send_request)
        top_bar.addWidget(self.url_edit, stretch=1)

        self.btn_send = QPushButton("⚡ إرسال (Send)")
        self.btn_send.setFixedHeight(40)
        self.btn_send.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 18px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }
        """)
        self.btn_send.clicked.connect(self.send_request)
        top_bar.addWidget(self.btn_send)

        self.btn_cancel = QPushButton("🛑 إلغاء")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 14px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover:!disabled {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #202c33;
                color: #64748b;
            }
        """)
        self.btn_cancel.clicked.connect(self.cancel_request)
        top_bar.addWidget(self.btn_cancel)

        main_layout.addLayout(top_bar)

        # ── Middle Area Splitter (Request Tabs | Response Tabs) ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1f2c34; height: 4px; }")

        # 1. Request Card
        req_card = QFrame()
        req_card.setStyleSheet("background-color: #111b21; border-radius: 10px; border: 1px solid #202c33;")
        req_layout = QVBoxLayout(req_card)
        req_layout.setContentsMargins(8, 8, 8, 8)

        self.req_tabs = QTabWidget()
        self.req_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background-color: #182229;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #172554;
                color: #60a5fa;
                border: 1px solid #3b82f6;
            }
        """)

        # Tab: Query Params
        tab_params = QWidget()
        p_layout = QVBoxLayout(tab_params)
        p_layout.setContentsMargins(4, 4, 4, 4)
        self.params_table = KeyValueTable()
        self.params_table.add_pair("", "", True)
        p_layout.addWidget(self.params_table, stretch=1)
        btn_add_p = create_tool_button("+ إضافة معامل (Param)", "#3b82f6", lambda: self.params_table.add_pair())
        p_layout.addWidget(btn_add_p)
        self.req_tabs.addTab(tab_params, "🔍 المعاملات (Params)")

        # Tab: Headers
        tab_headers = QWidget()
        h_layout = QVBoxLayout(tab_headers)
        h_layout.setContentsMargins(4, 4, 4, 4)
        self.headers_table = KeyValueTable()
        h_layout.addWidget(self.headers_table, stretch=1)
        btn_add_h = create_tool_button("+ إضافة ترويسة (Header)", "#3b82f6", lambda: self.headers_table.add_pair())
        h_layout.addWidget(btn_add_h)
        self.req_tabs.addTab(tab_headers, "📋 الترويسات (Headers)")

        # Tab: Auth
        tab_auth = QWidget()
        a_layout = QVBoxLayout(tab_auth)
        a_layout.setContentsMargins(10, 10, 10, 10)
        a_layout.setSpacing(10)

        auth_top = QHBoxLayout()
        auth_top.addWidget(QLabel("نوع المصادقة (Auth Type):"))
        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItems(["بدون مصادقة (None)", "Bearer Token", "Basic Auth", "API Key"])
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        auth_top.addWidget(self.auth_type_combo)
        auth_top.addStretch()
        a_layout.addLayout(auth_top)

        # Auth Inputs Frame
        self.auth_frame = QFrame()
        af_layout = QVBoxLayout(self.auth_frame)
        af_layout.setContentsMargins(0, 0, 0, 0)
        af_layout.setSpacing(6)

        # Bearer row
        self.bearer_edit = QLineEdit()
        self.bearer_edit.setPlaceholderText("أدخل رمز الـ Token هنا...")
        self.bearer_edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        af_layout.addWidget(self.bearer_edit)

        # Basic row
        self.basic_box = QWidget()
        bb_layout = QHBoxLayout(self.basic_box)
        bb_layout.setContentsMargins(0, 0, 0, 0)
        self.basic_user = QLineEdit()
        self.basic_user.setPlaceholderText("اسم المستخدم (Username)")
        self.basic_pass = QLineEdit()
        self.basic_pass.setPlaceholderText("كلمة المرور (Password)")
        self.basic_pass.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        bb_layout.addWidget(self.basic_user)
        bb_layout.addWidget(self.basic_pass)
        af_layout.addWidget(self.basic_box)

        # ApiKey row
        self.apikey_box = QWidget()
        ak_layout = QHBoxLayout(self.apikey_box)
        ak_layout.setContentsMargins(0, 0, 0, 0)
        self.ak_key = QLineEdit()
        self.ak_key.setPlaceholderText("Key (e.g. X-API-Key)")
        self.ak_val = QLineEdit()
        self.ak_val.setPlaceholderText("Value (e.g. secret_123)")
        self.ak_val.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.ak_loc = QComboBox()
        self.ak_loc.addItems(["Header", "Query"])
        ak_layout.addWidget(self.ak_key)
        ak_layout.addWidget(self.ak_val)
        ak_layout.addWidget(self.ak_loc)
        af_layout.addWidget(self.apikey_box)

        a_layout.addWidget(self.auth_frame)
        a_layout.addStretch()
        self._on_auth_type_changed(0)
        self.req_tabs.addTab(tab_auth, "🔑 المصادقة (Auth)")

        # Tab: Body
        tab_body = QWidget()
        b_layout = QVBoxLayout(tab_body)
        b_layout.setContentsMargins(4, 4, 4, 4)
        b_top = QHBoxLayout()
        b_top.addWidget(QLabel("نوع المحتوى:"))
        self.body_type_combo = QComboBox()
        self.body_type_combo.addItems(["None", "JSON", "Raw Text", "x-www-form-urlencoded"])
        self.body_type_combo.currentTextChanged.connect(self._on_body_type_changed)
        b_top.addWidget(self.body_type_combo)
        b_top.addStretch()
        btn_fmt_json = create_tool_button("تنسيق JSON", "#0ea5e9", self._format_request_json)
        b_top.addWidget(btn_fmt_json)
        b_layout.addLayout(b_top)

        self.body_edit = create_code_editor("أدخل محتوى الـ Body...")
        b_layout.addWidget(self.body_edit, stretch=1)
        self.req_tabs.addTab(tab_body, "📦 المحتوى (Body)")

        req_layout.addWidget(self.req_tabs)
        splitter.addWidget(req_card)

        # 2. Response Card
        resp_card = QFrame()
        resp_card.setStyleSheet("background-color: #111b21; border-radius: 10px; border: 1px solid #202c33;")
        resp_layout = QVBoxLayout(resp_card)
        resp_layout.setContentsMargins(8, 8, 8, 8)
        resp_layout.setSpacing(6)

        # Status row
        st_row = QHBoxLayout()
        self.status_badge = QLabel("جاهز للإرسال")
        self.status_badge.setStyleSheet("background-color: #202c33; color: #94a3b8; font-weight: bold; border-radius: 6px; padding: 4px 10px;")
        st_row.addWidget(self.status_badge)

        self.time_badge = QLabel("0 ms")
        self.time_badge.setStyleSheet("color: #60a5fa; font-weight: bold; padding: 4px 8px;")
        st_row.addWidget(self.time_badge)

        self.size_badge = QLabel("0 B")
        self.size_badge.setStyleSheet("color: #a855f7; font-weight: bold; padding: 4px 8px;")
        st_row.addWidget(self.size_badge)

        st_row.addStretch()
        btn_copy_resp = create_tool_button("📋 نسخ الاستجابة", "#3b82f6", self._copy_response)
        btn_save_resp = create_tool_button("💾 حفظ لملف", "#16a34a", self._save_response_to_file)
        st_row.addWidget(btn_copy_resp)
        st_row.addWidget(btn_save_resp)
        resp_layout.addLayout(st_row)

        self.resp_tabs = QTabWidget()
        self.resp_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background-color: #182229;
                color: #94a3b8;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #172554;
                color: #60a5fa;
            }
        """)

        self.resp_body_edit = create_code_editor("نتيجة الاستجابة (Response Body) ستظهر هنا...", readonly=True)
        self.resp_tabs.addTab(self.resp_body_edit, "📄 جسم الاستجابة (Response Body)")

        self.resp_headers_table = QTableWidget(0, 2)
        self.resp_headers_table.setHorizontalHeaderLabels(["الترويسة (Header)", "القيمة (Value)"])
        self.resp_headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.resp_headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.resp_headers_table.setStyleSheet("background-color: #111b21; color: #f0f2f5; font-family: 'Consolas', monospace;")
        self.resp_tabs.addTab(self.resp_headers_table, "📋 ترويسات الاستجابة (Headers)")

        resp_layout.addWidget(self.resp_tabs, stretch=1)
        splitter.addWidget(resp_card)

        splitter.setSizes([320, 360])
        main_layout.addWidget(splitter, stretch=1)

        # ── Bottom Bar: Actions (Saved Requests, History, cURL, Save) ──
        bot_bar = QHBoxLayout()
        btn_saved = create_tool_button("📁 الطلبات المحفوظة", "#6366f1", self.open_saved_requests)
        btn_hist = create_tool_button("🕒 سجل العمليات", "#0ea5e9", self.open_history)
        btn_curl = create_tool_button("📋 نسخ كـ cURL", "#3b82f6", self._copy_as_curl)
        btn_save_req = create_tool_button("💾 حفظ هذا الطلب", "#16a34a", self.save_current_request)

        bot_bar.addWidget(btn_saved)
        bot_bar.addWidget(btn_hist)
        bot_bar.addWidget(btn_curl)
        bot_bar.addStretch()
        bot_bar.addWidget(btn_save_req)
        main_layout.addLayout(bot_bar)

    def _on_method_changed(self, method: str):
        colors = {
            "GET": "#22c55e",
            "POST": "#3b82f6",
            "PUT": "#f59e0b",
            "PATCH": "#8b5cf6",
            "DELETE": "#ef4444",
            "HEAD": "#06b6d4",
            "OPTIONS": "#64748b"
        }
        col = colors.get(method, "#22c55e")
        self.method_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                border-radius: 8px;
                color: {col};
                font-weight: bold;
                padding: 4px 8px;
            }}
        """)

    def _on_auth_type_changed(self, idx: int):
        self.bearer_edit.hide()
        self.basic_box.hide()
        self.apikey_box.hide()

        if idx == 1:  # Bearer
            self.bearer_edit.show()
        elif idx == 2:  # Basic
            self.basic_box.show()
        elif idx == 3:  # ApiKey
            self.apikey_box.show()

    def _on_body_type_changed(self, btype: str):
        if btype == "None":
            self.body_edit.setEnabled(False)
        else:
            self.body_edit.setEnabled(True)

    def _format_request_json(self):
        text = self.body_edit.toPlainText().strip()
        if not text:
            return
        try:
            parsed = json.loads(text)
            self.body_edit.setPlainText(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception as e:
            QMessageBox.warning(self, "خطأ JSON", f"الصيغة غير صالحة:\n{e}")

    def _get_auth_payload(self) -> tuple[str, dict[str, str]]:
        idx = self.auth_type_combo.currentIndex()
        if idx == 1:
            return "bearer", {"token": self.bearer_edit.text().strip()}
        elif idx == 2:
            return "basic", {"username": self.basic_user.text().strip(), "password": self.basic_pass.text()}
        elif idx == 3:
            return "api_key", {
                "key": self.ak_key.text().strip(),
                "value": self.ak_val.text().strip(),
                "add_to": self.ak_loc.currentText().lower()
            }
        return "none", {}

    def send_request(self):
        raw_url = self.url_edit.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال عنوان الرابط (URL).")
            return

        method = self.method_combo.currentText()
        params = self.params_table.get_pairs()
        auth_type, auth_data = self._get_auth_payload()
        final_url = ApiClientService.build_final_url(raw_url, params, auth_type, auth_data)

        headers_list = self.headers_table.get_pairs()
        body_type = self.body_type_combo.currentText().lower()
        if body_type == "none":
            body_type_clean = "none"
        elif "json" in body_type:
            body_type_clean = "json"
        elif "urlencoded" in body_type:
            body_type_clean = "form_urlencoded"
        else:
            body_type_clean = "raw"

        req_headers = ApiClientService.build_headers(headers_list, auth_type, auth_data, body_type_clean)
        body_content = self.body_edit.toPlainText() if body_type_clean != "none" else ""
        body_bytes = ApiClientService.prepare_body(body_type_clean, body_content)

        # UI Loading state
        self.btn_send.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.status_badge.setText("⏳ جاري الإرسال...")
        self.status_badge.setStyleSheet("background-color: #172554; color: #60a5fa; font-weight: bold; border-radius: 6px; padding: 4px 10px;")

        # Cancel any previous active worker safely
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            try:
                self.current_worker.result_ready.disconnect()
            except Exception:
                pass

        # Launch Worker
        self.current_worker = ApiRequestWorker(method, final_url, req_headers, body_bytes)
        self.current_worker.result_ready.connect(self._on_response_received)
        self.current_worker.start()

    def cancel_request(self):
        if self.current_worker:
            self.current_worker.cancel()
            try:
                self.current_worker.result_ready.disconnect(self._on_response_received)
            except Exception:
                pass
            self.current_worker.wait(50)
            self.status_badge.setText("تم الإلغاء")
            self.status_badge.setStyleSheet("background-color: #3b0764; color: #c084fc; font-weight: bold; border-radius: 6px; padding: 4px 10px;")
            self.btn_send.setEnabled(True)
            self.btn_cancel.setEnabled(False)

    def _on_response_received(self, res: ApiResponse):
        self.btn_send.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        if res.is_error:
            self.status_badge.setText("❌ خطأ اتصال")
            self.status_badge.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; font-weight: bold; border-radius: 6px; padding: 4px 10px;")
            self.resp_body_edit.setPlainText(f"فشل الاتصال:\n{res.error_message}")
            self.time_badge.setText(f"{res.response_time_ms} ms")
            self.size_badge.setText("0 B")
            return

        # Status Code styling
        code = res.status_code
        if 200 <= code < 300:
            bg_col = "#064e3b"
            txt_col = "#4ade80"
        elif 300 <= code < 400:
            bg_col = "#172554"
            txt_col = "#60a5fa"
        elif 400 <= code < 500:
            bg_col = "#78350f"
            txt_col = "#f59e0b"
        else:
            bg_col = "#7f1d1d"
            txt_col = "#f87171"

        self.status_badge.setText(f"{res.status_code} {res.status_text}")
        self.status_badge.setStyleSheet(f"background-color: {bg_col}; color: {txt_col}; font-weight: bold; border-radius: 6px; padding: 4px 10px;")
        self.time_badge.setText(f"{res.response_time_ms} ms")

        # Format Size
        size = res.response_size_bytes
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{round(size / 1024.0, 1)} KB"
        else:
            size_str = f"{round(size / (1024.0 * 1024.0), 2)} MB"
        self.size_badge.setText(size_str)

        # Body formatting (Pretty JSON if applicable)
        body_to_display = res.body
        if "json" in res.content_type.lower():
            try:
                parsed = json.loads(res.body)
                body_to_display = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass

        self.resp_body_edit.setPlainText(body_to_display)

        # Populate response headers table
        self.resp_headers_table.setRowCount(0)
        for k, v in res.headers.items():
            r = self.resp_headers_table.rowCount()
            self.resp_headers_table.insertRow(r)
            self.resp_headers_table.setItem(r, 0, QTableWidgetItem(str(k)))
            self.resp_headers_table.setItem(r, 1, QTableWidgetItem(str(v)))

        # Record in history database (sanitized, no secrets!)
        try:
            entry = ApiHistoryEntry(
                method=self.method_combo.currentText(),
                url=self.url_edit.text().strip(),
                status_code=res.status_code,
                status_text=res.status_text,
                response_time_ms=res.response_time_ms,
                response_size_bytes=res.response_size_bytes
            )
            ApiRepository.add_history_entry(entry)
        except Exception:
            pass

    def _copy_response(self):
        copy_to_clipboard(self.resp_body_edit.toPlainText())

    def _save_response_to_file(self):
        text = self.resp_body_edit.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "حفظ الاستجابة لملف", "", "Text Files (*.txt);;JSON Files (*.json);;All Files (*)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل الحفظ: {e}")

    def _copy_as_curl(self):
        method = self.method_combo.currentText()
        raw_url = self.url_edit.text().strip()
        params = self.params_table.get_pairs()
        auth_type, auth_data = self._get_auth_payload()
        final_url = ApiClientService.build_final_url(raw_url, params, auth_type, auth_data)
        headers = ApiClientService.build_headers(self.headers_table.get_pairs(), auth_type, auth_data, self.body_type_combo.currentText().lower())
        body = self.body_edit.toPlainText() if self.body_type_combo.currentText() != "None" else ""
        dlg = CopyCurlDialog(method, final_url, headers, body, self)
        dlg.exec()

    def save_current_request(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال الرابط قبل الحفظ.")
            return

        collections = ApiRepository.get_collections()
        default_name = self.url_edit.text().split("?")[0].split("/")[-1] or "API Request"
        dlg = SaveApiRequestDialog(default_name, collections, self)
        if dlg.exec() != QDialog.Accepted:
            return

        name, collection, save_creds_securely = dlg.get_data()
        auth_type, auth_data = self._get_auth_payload()
        headers = self.headers_table.get_pairs()

        if not save_creds_securely:
            # Strip credentials if user did not opt in
            from snipglide.services.security import is_sensitive_header
            cleaned_auth = dict(auth_data)
            for k in ("token", "password", "value", "secret"):
                if k in cleaned_auth:
                    cleaned_auth[k] = ""
            auth_data = cleaned_auth

            cleaned_headers = []
            for h in headers:
                k = str(h.get("key", "")).strip()
                if not is_sensitive_header(k):
                    cleaned_headers.append(h)
                else:
                    cleaned_headers.append({"enabled": h.get("enabled", True), "key": k, "value": ""})
            headers = cleaned_headers

        req = ApiRequest(
            id=self.current_saved_id,
            name=name,
            method=self.method_combo.currentText(),
            url=url,
            params=self.params_table.get_pairs(),
            headers=headers,
            auth_type=auth_type,
            auth_data=auth_data,
            body_type=self.body_type_combo.currentText().lower(),
            body_content=self.body_edit.toPlainText(),
            collection_name=collection
        )
        try:
            if self.current_saved_id is None:
                self.current_saved_id = ApiRepository.add_request(req)
            else:
                ApiRepository.update_request(req)
            QMessageBox.information(self, "تم الحفظ", "تم حفظ الطلب في مكتبة الطلبات بنجاح! 💾")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def load_request(self, req: ApiRequest):
        self.current_saved_id = req.id
        self.method_combo.setCurrentText(req.method)
        self.url_edit.setText(req.url)
        self.params_table.set_pairs(req.params)
        self.headers_table.set_pairs(req.headers)

        # Auth
        auth_t = req.auth_type or "none"
        if auth_t == "bearer":
            self.auth_type_combo.setCurrentIndex(1)
            self.bearer_edit.setText(req.auth_data.get("token", ""))
        elif auth_t == "basic":
            self.auth_type_combo.setCurrentIndex(2)
            self.basic_user.setText(req.auth_data.get("username", ""))
            self.basic_pass.setText(req.auth_data.get("password", ""))
        elif auth_t == "api_key":
            self.auth_type_combo.setCurrentIndex(3)
            self.ak_key.setText(req.auth_data.get("key", ""))
            self.ak_val.setText(req.auth_data.get("value", ""))
            loc = req.auth_data.get("add_to", "header")
            self.ak_loc.setCurrentText(loc.capitalize())
        else:
            self.auth_type_combo.setCurrentIndex(0)

        # Body
        btype = req.body_type or "none"
        if "json" in btype:
            self.body_type_combo.setCurrentText("JSON")
        elif "urlencoded" in btype:
            self.body_type_combo.setCurrentText("x-www-form-urlencoded")
        elif btype == "raw":
            self.body_type_combo.setCurrentText("Raw Text")
        else:
            self.body_type_combo.setCurrentText("None")

        self.body_edit.setPlainText(req.body_content or "")

    def open_saved_requests(self):
        dlg = SavedApiRequestsDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_request:
            self.load_request(dlg.selected_request)

    def open_history(self):
        entries = ApiRepository.get_history(limit=50)
        dlg = QDialog(self)
        dlg.setWindowTitle("🕒 سجل طلبات الـ API")
        dlg.resize(680, 450)
        dlg.setStyleSheet("background-color: #111b21; color: #f0f2f5; font-family: 'Segoe UI', 'Tajawal', sans-serif;")
        l = QVBoxLayout(dlg)

        list_w = QListWidget()
        list_w.setStyleSheet("background-color: #182229; border: 1px solid #2a3942; border-radius: 8px; padding: 6px;")
        for e in entries:
            dt = e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else ""
            item = QListWidgetItem(f"[{e.method}] {e.url}  →  {e.status_code} ({e.response_time_ms} ms)  -  {dt}")
            item.setData(Qt.UserRole, e.url)
            item.setData(Qt.UserRole + 1, e.method)
            list_w.addItem(item)
        l.addWidget(list_w, stretch=1)

        b_row = QHBoxLayout()
        btn_apply = create_tool_button("تطبيق الرابط المختار", "#16a34a", lambda: self._apply_history_item(list_w, dlg))
        btn_clear = create_tool_button("مسح السجل", "#dc2626", lambda: self._clear_history_ui(list_w))
        b_row.addWidget(btn_apply)
        b_row.addWidget(btn_clear)
        b_row.addStretch()
        l.addLayout(b_row)
        dlg.exec()

    def _apply_history_item(self, list_w, dlg):
        item = list_w.currentItem()
        if not item:
            return
        url = item.data(Qt.UserRole)
        method = item.data(Qt.UserRole + 1)
        if url:
            self.url_edit.setText(url)
        if method:
            self.method_combo.setCurrentText(method)
        dlg.accept()

    def _clear_history_ui(self, list_w):
        if QMessageBox.question(self, "مسح السجل", "هل أنت متأكد من مسح سجل العمليات بالكامل؟") == QMessageBox.Yes:
            ApiRepository.clear_history()
            list_w.clear()
