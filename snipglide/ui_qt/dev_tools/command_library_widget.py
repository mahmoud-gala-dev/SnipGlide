"""Terminal Command Library Widget for SnipGlide.

Safe reference tool to organize, template, and copy shell commands without direct execution.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from snipglide.database.command_repo import CommandRepository
from snipglide.models.project_models import TerminalCommand
from snipglide.services.git_service import GitService
from snipglide.services.project_context import active_project_mgr


class CommandDialog(QDialog):
    """Dialog for creating or editing a terminal command snippet."""

    def __init__(self, cmd: Optional[TerminalCommand] = None, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.setWindowTitle("Edit Command" if cmd else "Add Terminal Command")
        self.resize(520, 360)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit(cmd.name if cmd else "")
        self.txt_name.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Command Name:", self.txt_name)

        self.cb_category = QComboBox()
        categories = ["Git", "Python", "pip", "npm", "Node.js", "Docker", "PowerShell", "Linux", "Django", "FastAPI", "Custom"]
        self.cb_category.addItems(categories)
        self.cb_category.setEditable(True)
        if cmd and cmd.category:
            idx = self.cb_category.findText(cmd.category)
            if idx >= 0:
                self.cb_category.setCurrentIndex(idx)
            else:
                self.cb_category.setEditText(cmd.category)
        self.cb_category.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Category:", self.cb_category)

        self.txt_command = QTextEdit(cmd.command if cmd else "")
        self.txt_command.setFont(QFont("Consolas", 10))
        self.txt_command.setMaximumHeight(90)
        self.txt_command.setStyleSheet("background-color: #11111b; border: 1px solid #45475a; border-radius: 4px; padding: 6px; color: #cdd6f4;")
        form.addRow("Command Syntax:", self.txt_command)

        # Helper hint
        hint_lbl = QLabel("💡 Supported variables: {{project_path}}, {{branch}}, {{port}}, {{input:var_name}}")
        hint_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        form.addRow("", hint_lbl)

        self.txt_desc = QLineEdit(cmd.description if cmd else "")
        self.txt_desc.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Description:", self.txt_desc)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #45475a; color: #cdd6f4; padding: 6px 14px; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save Command")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _save(self):
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Validation", "Command name cannot be empty.")
            return
        if not self.txt_command.toPlainText().strip():
            QMessageBox.warning(self, "Validation", "Command string cannot be empty.")
            return
        self.accept()

    def get_data(self) -> TerminalCommand:
        c_id = self.cmd.id if self.cmd else None
        fav = self.cmd.favorite if self.cmd else False
        p_id = self.cmd.project_id if self.cmd else None
        return TerminalCommand(
            id=c_id,
            name=self.txt_name.text().strip(),
            command=self.txt_command.toPlainText().strip(),
            description=self.txt_desc.text().strip(),
            category=self.cb_category.currentText().strip() or "General",
            project_id=p_id,
            favorite=fav,
        )


class CommandLibraryWidget(QWidget):
    """Terminal Command Library tab widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = CommandRepository()
        self.git_service = GitService()
        self._setup_ui()
        self._load_commands()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Filter Bar (Category + Search + Add)
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Category:"))
        self.cb_filter_cat = QComboBox()
        categories = ["All", "Git", "Python", "pip", "npm", "Node.js", "Docker", "PowerShell", "Linux", "Django", "FastAPI", "Custom"]
        self.cb_filter_cat.addItems(categories)
        self.cb_filter_cat.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; padding: 4px;")
        self.cb_filter_cat.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.cb_filter_cat)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search commands, syntax, or description...")
        self.txt_search.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px;")
        self.txt_search.textChanged.connect(self._on_search)
        filter_bar.addWidget(self.txt_search, 1)

        btn_add = QPushButton("➕ Add Command")
        btn_add.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_add.clicked.connect(self._add_command)
        filter_bar.addWidget(btn_add)

        main_layout.addLayout(filter_bar)

        # 2. Commands Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Fav", "Name", "Category", "Command Syntax"])
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 110)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px;")
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(lambda item: self._copy_resolved_command())
        main_layout.addWidget(self.table, 1)

        # 3. Actions Bar
        act_row = QHBoxLayout()

        btn_copy = QPushButton("📋 Copy Command (Resolve Variables)")
        btn_copy.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_copy.clicked.connect(self._copy_resolved_command)
        act_row.addWidget(btn_copy)

        btn_dup = QPushButton("📑 Duplicate")
        btn_dup.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_dup.clicked.connect(self._duplicate_command)
        act_row.addWidget(btn_dup)

        btn_fav = QPushButton("⭐ Toggle Favorite")
        btn_fav.setStyleSheet("background-color: #313244; color: #f9e2af; padding: 6px 12px; border-radius: 4px;")
        btn_fav.clicked.connect(self._toggle_fav)
        act_row.addWidget(btn_fav)

        btn_edit = QPushButton("✏️ Edit")
        btn_edit.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_edit.clicked.connect(self._edit_command)
        act_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Delete")
        btn_del.setStyleSheet("background-color: #45475a; color: #f38ba8; padding: 6px 12px; border-radius: 4px;")
        btn_del.clicked.connect(self._delete_command)
        act_row.addWidget(btn_del)

        act_row.addStretch()

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        act_row.addWidget(self.lbl_feedback)

        main_layout.addLayout(act_row)

    def _load_commands(self, commands=None):
        if commands is None:
            cat = self.cb_filter_cat.currentText()
            commands = self.repo.get_all(category=cat)

        self.table.setRowCount(0)
        for cmd in commands:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Fav
            fav_item = QTableWidgetItem("⭐" if cmd.favorite else "☆")
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            fav_item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.table.setItem(row, 0, fav_item)

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(cmd.name))

            # Category
            self.table.setItem(row, 2, QTableWidgetItem(cmd.category))

            # Command syntax
            cmd_item = QTableWidgetItem(cmd.command)
            cmd_item.setFont(QFont("Consolas", 10))
            self.table.setItem(row, 3, cmd_item)

    def _get_selected_command(self) -> Optional[TerminalCommand]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _on_filter_changed(self):
        cat = self.cb_filter_cat.currentText()
        q = self.txt_search.text().strip()
        if q:
            self._on_search()
        else:
            self._load_commands(self.repo.get_all(category=cat))

    def _on_search(self):
        q = self.txt_search.text().strip()
        cat = self.cb_filter_cat.currentText()
        results = self.repo.search(q, category=cat)
        self._load_commands(results)

    def _resolve_template(self, command_template: str) -> str:
        """Resolve variables like {{project_path}}, {{branch}}, {{port}}, {{input:name}} safely."""
        text = command_template
        active_p = active_project_mgr.active_project

        # 1. {{project_path}}
        if "{{project_path}}" in text:
            path_val = active_p.project_path if active_p else os.getcwd()
            text = text.replace("{{project_path}}", path_val)

        # 2. {{branch}}
        if "{{branch}}" in text:
            cur_path = active_p.project_path if active_p else os.getcwd()
            branch = "main"
            if self.git_service.is_git_repo(cur_path):
                info = self.git_service.get_repo_info(cur_path)
                if info.current_branch:
                    branch = info.current_branch
            text = text.replace("{{branch}}", branch)

        # 3. {{port}}
        if "{{port}}" in text:
            val, ok = QInputDialog.getText(self, "Enter Port", "Port number:", QLineEdit.EchoMode.Normal, "8000")
            port_str = val.strip() if ok and val.strip() else "8000"
            text = text.replace("{{port}}", port_str)

        # 4. {{input:param_name}}
        import re
        for match in re.finditer(r"\{\{input:([^}]+)\}\}", text):
            param = match.group(1)
            val, ok = QInputDialog.getText(self, "Enter Value", f"Value for '{param}':", QLineEdit.EchoMode.Normal, "")
            text = text.replace(match.group(0), val.strip() if ok else "")

        return text

    def _copy_resolved_command(self):
        cmd = self._get_selected_command()
        if not cmd:
            QMessageBox.information(self, "Select Command", "Please select a command from the list.")
            return

        resolved = self._resolve_template(cmd.command)
        QApplication.clipboard().setText(resolved)
        self.lbl_feedback.setText(f"📋 Copied: {resolved[:35]}...")

    def _add_command(self):
        dlg = CommandDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_cmd = dlg.get_data()
            try:
                self.repo.create(new_cmd)
                self._load_commands()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add command: {e}")

    def _edit_command(self):
        cmd = self._get_selected_command()
        if not cmd:
            return
        dlg = CommandDialog(cmd, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_data()
            self.repo.update(updated)
            self._load_commands()

    def _duplicate_command(self):
        cmd = self._get_selected_command()
        if not cmd:
            return
        dup = TerminalCommand(
            name=f"{cmd.name} (Copy)",
            command=cmd.command,
            description=cmd.description,
            category=cmd.category,
            project_id=cmd.project_id,
            favorite=cmd.favorite,
        )
        self.repo.create(dup)
        self._load_commands()

    def _delete_command(self):
        cmd = self._get_selected_command()
        if not cmd:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{cmd.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.repo.delete(cmd.id)
            self._load_commands()

    def _toggle_fav(self):
        cmd = self._get_selected_command()
        if cmd:
            self.repo.toggle_favorite(cmd.id)
            self._load_commands()
