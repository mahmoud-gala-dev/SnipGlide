"""AI Coding Platform Widget for SnipGlide.

Provides multi-provider code explanation, bug finding, refactoring, test generation,
type annotation, regex/SQL assistance, and code translation with strict privacy guarantees.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from snipglide.core.config import DEFAULT_SETTINGS, load_settings, save_settings
from snipglide.models.ai_models import (
    AIProviderConfig,
    CODING_ACTIONS,
    CodingActionType,
    ProviderType,
)
from snipglide.services.ai_providers import BaseAIProvider, get_ai_provider
from snipglide.ui_qt.dev_tools.ai_context_preview_dialog import AIContextPreviewDialog


class AIWorker(QThread):
    """Background thread executing AI completion with token streaming."""
    chunk_received = Signal(str)
    completed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, provider: BaseAIProvider, prompt: str, system_prompt: str = "", stream: bool = True):
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.should_stream = stream
        self._is_cancelled = False
        self.finished.connect(self.deleteLater)

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.should_stream:
                def on_chunk(token: str):
                    if not self._is_cancelled:
                        self.chunk_received.emit(token)

                full = self.provider.stream(self.prompt, on_chunk, system_prompt=self.system_prompt)
                if not self._is_cancelled:
                    self.completed.emit(full)
            else:
                res = self.provider.generate(self.prompt, system_prompt=self.system_prompt)
                if not self._is_cancelled:
                    self.completed.emit(res)
        except Exception as e:
            if not self._is_cancelled:
                self.error_occurred.emit(str(e))


class AITaskType:
    TEST_CONNECTION = "TEST_CONNECTION"
    LIST_MODELS = "LIST_MODELS"


class AIProviderTaskWorker(QThread):
    """
    Reusable background worker for executing AI provider operations (Test Connection, List Models)
    asynchronously without freezing or blocking the Qt UI thread.
    """
    task_completed = Signal(str, bool, object)  # task_type, success, result_data

    def __init__(self, provider: BaseAIProvider, task_type: str):
        super().__init__()
        self.provider = provider
        self.task_type = task_type
        self.is_cancelled = False
        self.finished.connect(self.deleteLater)

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if self.is_cancelled:
            return
        try:
            if self.task_type == AITaskType.TEST_CONNECTION:
                ok, msg = self.provider.test_connection()
                if not self.is_cancelled:
                    self.task_completed.emit(self.task_type, ok, msg)
            elif self.task_type == AITaskType.LIST_MODELS:
                models = self.provider.list_models()
                if not self.is_cancelled:
                    self.task_completed.emit(self.task_type, bool(models), models)
            else:
                if not self.is_cancelled:
                    self.task_completed.emit(self.task_type, False, f"Unknown task type: {self.task_type}")
        except Exception as e:
            if not self.is_cancelled:
                self.task_completed.emit(self.task_type, False, str(e))


class AIConnectionTestWorker(AIProviderTaskWorker):
    """Compatibility subclass for testing connectivity."""
    result_ready = Signal(bool, str)

    def __init__(self, provider: BaseAIProvider):
        super().__init__(provider, AITaskType.TEST_CONNECTION)
        self.task_completed.connect(lambda t, ok, msg: self.result_ready.emit(ok, str(msg)))


class AIModelListWorker(AIProviderTaskWorker):
    """Compatibility subclass for querying model lists."""
    models_ready = Signal(list)

    def __init__(self, provider: BaseAIProvider):
        super().__init__(provider, AITaskType.LIST_MODELS)
        self.task_completed.connect(lambda t, ok, data: self.models_ready.emit(data if isinstance(data, list) else []))


class AICodingWidget(QWidget):
    """Full-featured AI Coding Platform tab widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: Optional[AIWorker] = None
        self._setup_ui()
        self._load_saved_config()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Provider & Configuration Bar
        cfg_group = QGroupBox("AI Provider & Settings")
        cfg_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        cfg_layout = QVBoxLayout(cfg_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider:"))
        self.cb_provider = QComboBox()
        self.cb_provider.addItems(["Gemini (Google)", "OpenAI", "Ollama (Local)", "OpenAI Compatible"])
        self.cb_provider.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        self.cb_provider.currentIndexChanged.connect(self._on_provider_changed)
        row1.addWidget(self.cb_provider)

        row1.addWidget(QLabel("API Key:"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Enter API key...")
        self.txt_api_key.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        row1.addWidget(self.txt_api_key, 1)

        self.btn_toggle_key = QPushButton("👁️")
        self.btn_toggle_key.setFixedWidth(32)
        self.btn_toggle_key.setStyleSheet("background-color: #313244; color: #cdd6f4; border-radius: 4px;")
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        row1.addWidget(self.btn_toggle_key)

        self.btn_test = QPushButton("🔌 Test")
        self.btn_test.setStyleSheet("background-color: #313244; color: #89b4fa; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
        self.btn_test.clicked.connect(self._test_connection)
        row1.addWidget(self.btn_test)

        cfg_layout.addLayout(row1)

        # Row 2: Base URL (if compatible/ollama), Model, Temperature
        row2 = QHBoxLayout()
        self.lbl_base_url = QLabel("Base URL:")
        self.txt_base_url = QLineEdit()
        self.txt_base_url.setPlaceholderText("e.g. http://localhost:11434/v1")
        self.txt_base_url.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        row2.addWidget(self.lbl_base_url)
        row2.addWidget(self.txt_base_url, 1)

        row2.addWidget(QLabel("Model:"))
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_model.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        row2.addWidget(self.cb_model, 1)

        self.btn_refresh_models = QPushButton("🔄")
        self.btn_refresh_models.setFixedWidth(30)
        self.btn_refresh_models.setToolTip("Fetch available models from provider")
        self.btn_refresh_models.setStyleSheet("background-color: #313244; color: #cdd6f4; border-radius: 4px;")
        self.btn_refresh_models.clicked.connect(self._refresh_models)
        row2.addWidget(self.btn_refresh_models)

        row2.addWidget(QLabel("Temp:"))
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.5)
        self.spin_temp.setSingleStep(0.1)
        self.spin_temp.setValue(0.7)
        self.spin_temp.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        row2.addWidget(self.spin_temp)

        cfg_layout.addLayout(row2)
        main_layout.addWidget(cfg_group)

        # 2. Action & Controls Bar
        act_row = QHBoxLayout()
        act_row.addWidget(QLabel("Coding Action:"))

        self.cb_action = QComboBox()
        for action_meta in CODING_ACTIONS.values():
            self.cb_action.addItem(action_meta.label, action_meta.action_type)
        self.cb_action.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 5px; font-weight: bold;")
        self.cb_action.currentIndexChanged.connect(self._on_action_changed)
        act_row.addWidget(self.cb_action, 1)

        # Convert languages container
        self.convert_container = QWidget()
        convert_layout = QHBoxLayout(self.convert_container)
        convert_layout.setContentsMargins(0, 0, 0, 0)
        convert_layout.addWidget(QLabel("From:"))
        self.cb_source_lang = QComboBox()
        self.cb_source_lang.addItems(["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C#", "C++", "PHP", "SQL", "JSON"])
        self.cb_source_lang.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a;")
        convert_layout.addWidget(self.cb_source_lang)

        convert_layout.addWidget(QLabel("To:"))
        self.cb_target_lang = QComboBox()
        self.cb_target_lang.addItems(["TypeScript", "JavaScript", "Python", "Go", "Rust", "Java", "C#", "C++", "PHP", "SQL", "JSON"])
        self.cb_target_lang.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a;")
        convert_layout.addWidget(self.cb_target_lang)
        self.convert_container.setVisible(False)
        act_row.addWidget(self.convert_container)

        self.chk_stream = QCheckBox("Stream Tokens")
        self.chk_stream.setChecked(True)
        self.chk_stream.setStyleSheet("color: #a6adc8;")
        act_row.addWidget(self.chk_stream)

        self.chk_preview = QCheckBox("Privacy Preview Confirmation")
        self.chk_preview.setChecked(True)
        self.chk_preview.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        act_row.addWidget(self.chk_preview)

        main_layout.addLayout(act_row)

        # 3. Main Splitter: Code Input (Left) | AI Response (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Input Code / Query
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("Input Code / Error / Requirement:"))
        btn_clear_input = QPushButton("Clear")
        btn_clear_input.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 2px 8px; border-radius: 4px;")
        btn_clear_input.clicked.connect(lambda: self.txt_input.clear())
        left_header.addWidget(btn_clear_input)
        left_layout.addLayout(left_header)

        self.txt_input = QPlainTextEdit()
        self.txt_input.setFont(QFont("Consolas", 10))
        self.txt_input.setPlaceholderText("Paste your code, traceback, or prompt here...")
        self.txt_input.setStyleSheet("background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px; padding: 6px;")
        left_layout.addWidget(self.txt_input)

        # Submit / Cancel Bar
        btn_run_row = QHBoxLayout()
        self.btn_send = QPushButton("🚀 Run AI Action")
        self.btn_send.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 8px 16px; border-radius: 4px; font-size: 13px;")
        self.btn_send.clicked.connect(self._run_action)
        btn_run_row.addWidget(self.btn_send)

        self.btn_stop = QPushButton("⏹️ Cancel")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; padding: 8px 16px; border-radius: 4px;")
        self.btn_stop.clicked.connect(self._stop_action)
        btn_run_row.addWidget(self.btn_stop)

        left_layout.addLayout(btn_run_row)
        splitter.addWidget(left_widget)

        # Right: AI Output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        right_header = QHBoxLayout()
        self.lbl_output_status = QLabel("AI Response:")
        self.lbl_output_status.setStyleSheet("font-weight: bold; color: #89b4fa;")
        right_header.addWidget(self.lbl_output_status)
        right_header.addStretch()

        btn_copy = QPushButton("📋 Copy Output")
        btn_copy.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 4px 10px; border-radius: 4px;")
        btn_copy.clicked.connect(self._copy_output)
        right_header.addWidget(btn_copy)
        right_layout.addLayout(right_header)

        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setFont(QFont("Consolas", 10))
        self.txt_output.setPlaceholderText("AI generated code and explanation will appear here...")
        self.txt_output.setStyleSheet("background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px; padding: 6px;")
        right_layout.addWidget(self.txt_output)

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 550])

        main_layout.addWidget(splitter, 1)

    def _on_provider_changed(self):
        idx = self.cb_provider.currentIndex()
        if idx == 0:  # Gemini
            self.lbl_base_url.setVisible(False)
            self.txt_base_url.setVisible(False)
            self.cb_model.clear()
            self.cb_model.addItems(["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"])
        elif idx == 1:  # OpenAI
            self.lbl_base_url.setVisible(False)
            self.txt_base_url.setVisible(False)
            self.cb_model.clear()
            self.cb_model.addItems(["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
        elif idx == 2:  # Ollama
            self.lbl_base_url.setVisible(True)
            self.txt_base_url.setVisible(True)
            self.txt_base_url.setText("http://localhost:11434/v1")
            self.cb_model.clear()
            self.cb_model.addItems(["llama3", "codellama", "mistral", "qwen2.5-coder"])
        elif idx == 3:  # OpenAI Compatible
            self.lbl_base_url.setVisible(True)
            self.txt_base_url.setVisible(True)
            if not self.txt_base_url.text():
                self.txt_base_url.setText("https://api.deepseek.com/v1")
            self.cb_model.clear()
            self.cb_model.addItems(["default-model"])

    def _on_action_changed(self):
        action_type = self.cb_action.currentData()
        self.convert_container.setVisible(action_type == CodingActionType.CONVERT_CODE)

    def _toggle_key_visibility(self):
        if self.txt_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("🙈")
        else:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("👁️")

    def _get_current_config(self) -> AIProviderConfig:
        idx = self.cb_provider.currentIndex()
        p_types = [
            ProviderType.GEMINI,
            ProviderType.OPENAI,
            ProviderType.OLLAMA,
            ProviderType.OPENAI_COMPATIBLE,
        ]
        return AIProviderConfig(
            provider_type=p_types[idx],
            api_key=self.txt_api_key.text().strip(),
            base_url=self.txt_base_url.text().strip(),
            model=self.cb_model.currentText().strip(),
            temperature=self.spin_temp.value(),
        )

    def _test_connection(self):
        cfg = self._get_current_config()
        provider = get_ai_provider(cfg)
        self.btn_test.setEnabled(False)
        self.btn_test.setText("⏳ Testing...")

        def on_task_completed(task_type: str, ok: bool, msg: object):
            if task_type != AITaskType.TEST_CONNECTION:
                return
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔌 Test")
            if ok:
                QMessageBox.information(self, "Connection Successful", str(msg))
            else:
                QMessageBox.warning(self, "Connection Failed", str(msg))

        self._conn_worker = AIProviderTaskWorker(provider, AITaskType.TEST_CONNECTION)
        self._conn_worker.task_completed.connect(on_task_completed)
        self._conn_worker.start()

    def _refresh_models(self):
        cfg = self._get_current_config()
        provider = get_ai_provider(cfg)
        self.btn_refresh_models.setEnabled(False)
        self.btn_refresh_models.setText("⏳")

        def on_models_completed(task_type: str, ok: bool, models: object):
            if task_type != AITaskType.LIST_MODELS:
                return
            self.btn_refresh_models.setEnabled(True)
            self.btn_refresh_models.setText("🔄")
            if ok and isinstance(models, list) and models:
                self.cb_model.clear()
                self.cb_model.addItems(models)
                QMessageBox.information(self, "Models Updated", f"Retrieved {len(models)} model(s).")
            else:
                QMessageBox.warning(self, "Models", "Could not fetch models. Check connection/API key.")

        self._models_worker = AIProviderTaskWorker(provider, AITaskType.LIST_MODELS)
        self._models_worker.task_completed.connect(on_models_completed)
        self._models_worker.start()

    def _run_action(self):
        code_input = self.txt_input.toPlainText().strip()
        if not code_input:
            QMessageBox.warning(self, "Input Empty", "Please provide input code or text first.")
            return

        action_type = self.cb_action.currentData()
        action_meta = CODING_ACTIONS.get(action_type)
        if not action_meta:
            return

        cfg = self._get_current_config()

        # Build prompt
        source_lang = self.cb_source_lang.currentText()
        target_lang = self.cb_target_lang.currentText()
        formatted_prompt = action_meta.user_prompt_template.format(
            code=code_input,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # Privacy preview confirmation
        if self.chk_preview.isChecked():
            preview_dlg = AIContextPreviewDialog(
                provider_name=self.cb_provider.currentText(),
                model_name=cfg.model,
                prompt_text=formatted_prompt,
                system_prompt=action_meta.system_prompt,
                parent=self,
            )
            if preview_dlg.exec() != QDialog.DialogCode.Accepted:
                return

        self._save_current_config()

        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.txt_output.clear()
        self.lbl_output_status.setText("⏳ Generating...")

        provider = get_ai_provider(cfg)
        should_stream = self.chk_stream.isChecked()

        self.worker = AIWorker(
            provider=provider,
            prompt=formatted_prompt,
            system_prompt=action_meta.system_prompt,
            stream=should_stream,
        )
        if should_stream:
            self.worker.chunk_received.connect(self._on_chunk_received)
        self.worker.completed.connect(self._on_completed)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_chunk_received(self, chunk: str):
        self.txt_output.insertPlainText(chunk)
        # Scroll to bottom
        sb = self.txt_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_completed(self, full_text: str):
        if not self.chk_stream.isChecked():
            self.txt_output.setPlainText(full_text)
        self.lbl_output_status.setText("✅ Completed")
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_error(self, err_msg: str):
        self.txt_output.setPlainText(f"❌ Error occurred:\n\n{err_msg}")
        self.lbl_output_status.setText("❌ Error")
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _stop_action(self):
        if self.worker:
            self.worker.cancel()
            try:
                self.worker.chunk_received.disconnect()
                self.worker.completed.disconnect()
                self.worker.error_occurred.disconnect()
            except Exception:
                pass
            self.worker.wait(50)
            self.lbl_output_status.setText("⏹️ Cancelled by user")
            self.btn_send.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _copy_output(self):
        out = self.txt_output.toPlainText()
        if out:
            QApplication.clipboard().setText(out)
            QMessageBox.information(self, "Copied", "AI output copied to clipboard!")

    def _load_saved_config(self):
        from snipglide.services.security import decrypt_secret
        settings = load_settings()
        stored_key = settings.get("ai_api_key", "")
        if stored_key:
            try:
                decrypted_key = decrypt_secret(stored_key)
                self.txt_api_key.setText(decrypted_key)
            except Exception:
                self.txt_api_key.setText("")
        else:
            self.txt_api_key.setText("")
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)

        prov = settings.get("ai_provider", "gemini").lower()
        if "openai" in prov:
            self.cb_provider.setCurrentIndex(1)
        elif "ollama" in prov:
            self.cb_provider.setCurrentIndex(2)
        else:
            self.cb_provider.setCurrentIndex(0)
        self._on_provider_changed()

    def _save_current_config(self):
        from snipglide.services.security import encrypt_secret
        settings = load_settings()
        key_text = self.txt_api_key.text().strip()
        if key_text:
            try:
                settings["ai_api_key"] = encrypt_secret(key_text)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "خطأ أمني",
                    f"فشل تشفير مفتاح API: {e}\nتم إلغاء الحفظ لمنع حفظ المفتاح كنص صريح (Fail-Closed)."
                )
                return
        else:
            settings["ai_api_key"] = ""

        settings["ai_provider"] = self.cb_provider.currentText().lower()
        save_settings(settings)
