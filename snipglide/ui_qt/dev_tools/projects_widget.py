"""Developer Projects Management Widget for SnipGlide.

Allows developers to manage, detect, and activate local workspace profiles.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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

from snipglide.database.project_repo import ProjectRepository
from snipglide.models.project_models import DeveloperProject
from snipglide.services.project_context import active_project_mgr
from snipglide.services.project_detector import detect_project_type


class ProjectDialog(QDialog):
    """Dialog for creating or editing a developer project profile."""

    def __init__(self, project: Optional[DeveloperProject] = None, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Edit Project" if project else "Add Developer Project")
        self.resize(500, 360)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Path + Browse
        path_row = QHBoxLayout()
        self.txt_path = QLineEdit(project.project_path if project else "")
        self.txt_path.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        self.txt_path.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.txt_path, 1)

        btn_browse = QPushButton("📁 Browse")
        btn_browse.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 5px 12px; border-radius: 4px;")
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(btn_browse)
        form.addRow("Project Folder:", path_row)

        # Name
        self.txt_name = QLineEdit(project.name if project else "")
        self.txt_name.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Project Name:", self.txt_name)

        # Language
        self.txt_lang = QLineEdit(project.language if project else "")
        self.txt_lang.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Language:", self.txt_lang)

        # Framework
        self.txt_framework = QLineEdit(project.framework if project else "")
        self.txt_framework.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 5px; color: #cdd6f4;")
        form.addRow("Framework / Stack:", self.txt_framework)

        # Description
        self.txt_desc = QTextEdit(project.description if project else "")
        self.txt_desc.setMaximumHeight(80)
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

        btn_save = QPushButton("💾 Save Project")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Root Folder")
        if folder:
            self.txt_path.setText(folder)

    def _on_path_changed(self, path: str):
        path = path.strip()
        if os.path.isdir(path):
            if not self.txt_name.text().strip():
                self.txt_name.setText(os.path.basename(os.path.normpath(path)))
            lang, framework = detect_project_type(path)
            self.txt_lang.setText(lang)
            self.txt_framework.setText(framework)

    def _save(self):
        if not self.txt_path.text().strip():
            QMessageBox.warning(self, "Validation", "Project folder path cannot be empty.")
            return
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Validation", "Project name cannot be empty.")
            return
        self.accept()

    def get_data(self) -> DeveloperProject:
        p_id = self.project.id if self.project else None
        fav = self.project.favorite if self.project else False
        return DeveloperProject(
            id=p_id,
            name=self.txt_name.text().strip(),
            project_path=self.txt_path.text().strip(),
            language=self.txt_lang.text().strip(),
            framework=self.txt_framework.text().strip(),
            description=self.txt_desc.toPlainText().strip(),
            favorite=fav,
        )


class ProjectsWidget(QWidget):
    """Developer Projects tab widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ProjectRepository()
        self._setup_ui()
        self._load_projects()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Header with Active Project Indicator
        header_group = QGroupBox("Active Project Context")
        header_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        header_layout = QHBoxLayout(header_group)

        self.lbl_active = QLabel("Current Active Project: None")
        self.lbl_active.setStyleSheet("font-weight: bold; color: #a6e3a1; font-size: 13px;")
        header_layout.addWidget(self.lbl_active, 1)

        btn_clear_active = QPushButton("Clear Active")
        btn_clear_active.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        btn_clear_active.clicked.connect(self._clear_active)
        header_layout.addWidget(btn_clear_active)

        main_layout.addWidget(header_group)

        # 2. Control Bar (Search + Add)
        ctrl_bar = QHBoxLayout()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search projects by name, language, framework...")
        self.txt_search.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px;")
        self.txt_search.textChanged.connect(self._search)
        ctrl_bar.addWidget(self.txt_search, 1)

        btn_add = QPushButton("➕ Add Project")
        btn_add.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_add.clicked.connect(self._add_project)
        ctrl_bar.addWidget(btn_add)

        main_layout.addLayout(ctrl_bar)

        # 3. Projects Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Fav", "Active", "Project Name", "Language", "Framework", "Path"])
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 65)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 120)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px;")
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(lambda item: self._set_selected_as_active())
        main_layout.addWidget(self.table, 1)

        # 4. Action Buttons Bar
        act_row = QHBoxLayout()

        btn_set_active = QPushButton("⚡ Set as Active Project")
        btn_set_active.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_set_active.clicked.connect(self._set_selected_as_active)
        act_row.addWidget(btn_set_active)

        btn_git = QPushButton("🐙 Open in Git Tools")
        btn_git.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_git.clicked.connect(self._open_in_git_tools)
        act_row.addWidget(btn_git)

        btn_explorer = QPushButton("📂 Open Folder")
        btn_explorer.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_explorer.clicked.connect(self._open_folder)
        act_row.addWidget(btn_explorer)

        btn_fav = QPushButton("⭐ Toggle Favorite")
        btn_fav.setStyleSheet("background-color: #313244; color: #f9e2af; padding: 6px 12px; border-radius: 4px;")
        btn_fav.clicked.connect(self._toggle_fav)
        act_row.addWidget(btn_fav)

        btn_edit = QPushButton("✏️ Edit")
        btn_edit.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_edit.clicked.connect(self._edit_project)
        act_row.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Delete")
        btn_del.setStyleSheet("background-color: #45475a; color: #f38ba8; padding: 6px 12px; border-radius: 4px;")
        btn_del.clicked.connect(self._delete_project)
        act_row.addWidget(btn_del)

        act_row.addStretch()
        main_layout.addLayout(act_row)

    def _load_projects(self, projects=None):
        if projects is None:
            projects = self.repo.get_all()

        active = active_project_mgr.active_project
        if active:
            self.lbl_active.setText(f"Current Active Project: 🌟 {active.name} ({active.language} - {active.framework})")
        else:
            self.lbl_active.setText("Current Active Project: None")

        self.table.setRowCount(0)
        for p in projects:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Fav
            fav_item = QTableWidgetItem("⭐" if p.favorite else "☆")
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            fav_item.setData(Qt.ItemDataRole.UserRole, p)
            self.table.setItem(row, 0, fav_item)

            # Active status
            is_act = (active and active.id == p.id)
            act_item = QTableWidgetItem("🟢 Active" if is_act else "")
            act_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, act_item)

            # Name
            self.table.setItem(row, 2, QTableWidgetItem(p.name))

            # Lang
            self.table.setItem(row, 3, QTableWidgetItem(p.language))

            # Framework
            self.table.setItem(row, 4, QTableWidgetItem(p.framework))

            # Path
            self.table.setItem(row, 5, QTableWidgetItem(p.project_path))

    def _get_selected_project(self) -> Optional[DeveloperProject]:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _add_project(self):
        dlg = ProjectDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_p = dlg.get_data()
            try:
                p_id = self.repo.create(new_p)
                new_p.id = p_id
                self._load_projects()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save project: {e}")

    def _edit_project(self):
        p = self._get_selected_project()
        if not p:
            QMessageBox.information(self, "Select Project", "Please select a project from the list first.")
            return
        dlg = ProjectDialog(p, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_data()
            self.repo.update(updated)
            if active_project_mgr.active_project and active_project_mgr.active_project.id == updated.id:
                active_project_mgr.set_active_project(updated)
            self._load_projects()

    def _delete_project(self):
        p = self._get_selected_project()
        if not p:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to remove project profile '{p.name}'? (Your files on disk will NOT be touched).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.repo.delete(p.id)
            if active_project_mgr.active_project and active_project_mgr.active_project.id == p.id:
                active_project_mgr.set_active_project(None)
            self._load_projects()

    def _toggle_fav(self):
        p = self._get_selected_project()
        if p:
            self.repo.toggle_favorite(p.id)
            self._load_projects()

    def _set_selected_as_active(self):
        p = self._get_selected_project()
        if p:
            active_project_mgr.set_active_project(p)
            self._load_projects()
            QMessageBox.information(self, "Active Project Set", f"'{p.name}' is now your Active Project!")

    def _clear_active(self):
        active_project_mgr.set_active_project(None)
        self._load_projects()

    def _open_folder(self):
        p = self._get_selected_project()
        if p and os.path.isdir(p.project_path):
            try:
                if os.name == "nt":
                    os.startfile(p.project_path)
                else:
                    subprocess.Popen(["xdg-open", p.project_path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")

    def _open_in_git_tools(self):
        p = self._get_selected_project()
        if not p:
            return
        # Switch to Git tab in toolbox page if parent available
        parent_toolbox = self.window()
        if hasattr(parent_toolbox, "dev_toolbox_page"):
            parent_toolbox.dev_toolbox_page.tabs.setCurrentIndex(10)
            if hasattr(parent_toolbox.dev_toolbox_page, "git_widget"):
                parent_toolbox.dev_toolbox_page.git_widget.txt_repo_path.setText(p.project_path)
                parent_toolbox.dev_toolbox_page.git_widget._load_repo(p.project_path)

    def _search(self, q: str):
        projects = self.repo.search(q)
        self._load_projects(projects)
