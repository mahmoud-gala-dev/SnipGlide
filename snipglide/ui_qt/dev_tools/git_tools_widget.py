"""Git Developer Tools Widget for SnipGlide.

Provides repository inspection, branch information, status tracking,
diff viewing with syntax coloring, and conventional commit message generation.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from snipglide.models.git_info import GitCommit, GitRepoInfo
from snipglide.services.git_service import GitService


class DiffHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for git diffs."""

    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self.add_format = QTextCharFormat()
        self.add_format.setForeground(QColor("#4ade80"))  # soft green

        self.del_format = QTextCharFormat()
        self.del_format.setForeground(QColor("#f87171"))  # soft red

        self.header_format = QTextCharFormat()
        self.header_format.setForeground(QColor("#38bdf8"))  # soft cyan

        self.meta_format = QTextCharFormat()
        self.meta_format.setForeground(QColor("#94a3b8"))  # slate gray

    def highlightBlock(self, text: str):
        if not text:
            return
        if text.startswith("+") and not text.startswith("+++"):
            self.setFormat(0, len(text), self.add_format)
        elif text.startswith("-") and not text.startswith("---"):
            self.setFormat(0, len(text), self.del_format)
        elif text.startswith("@@"):
            self.setFormat(0, len(text), self.header_format)
        elif text.startswith("diff ") or text.startswith("index ") or text.startswith("---") or text.startswith("+++"):
            self.setFormat(0, len(text), self.meta_format)


class GitWorker(QThread):
    """Background worker for git repository operations to prevent UI freezing."""
    info_ready = Signal(object)      # GitRepoInfo
    commits_ready = Signal(list)    # list[GitCommit]
    diff_ready = Signal(str)        # str
    error_occurred = Signal(str)

    def __init__(self, service: GitService, path: str, op: str, **kwargs):
        super().__init__()
        self.service = service
        self.path = path
        self.op = op
        self.kwargs = kwargs

    def run(self):
        try:
            if self.op == "info":
                info = self.service.get_repo_info(self.path)
                self.info_ready.emit(info)
            elif self.op == "commits":
                count = self.kwargs.get("count", 25)
                commits = self.service.get_recent_commits(self.path, count=count)
                self.commits_ready.emit(commits)
            elif self.op == "diff":
                staged = self.kwargs.get("staged", False)
                file_path = self.kwargs.get("file_path", None)
                diff = self.service.get_diff(self.path, staged=staged, file_path=file_path)
                self.diff_ready.emit(diff)
        except Exception as e:
            self.error_occurred.emit(str(e))


class CommitMessageDialog(QDialog):
    """Dialog displaying generated conventional commit messages with copy/edit."""

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generated Commit Message")
        self.resize(560, 360)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)

        info_lbl = QLabel("Conventional Commit Message (Heuristic & Context-Aware):")
        info_lbl.setStyleSheet("font-weight: bold; color: #89b4fa;")
        layout.addWidget(info_lbl)

        self.txt_message = QPlainTextEdit(message)
        self.txt_message.setFont(QFont("Consolas", 10))
        self.txt_message.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.txt_message)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy to Clipboard")
        btn_copy.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_copy.clicked.connect(self._copy)
        btn_row.addWidget(btn_copy)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #45475a; color: #cdd6f4; padding: 6px 14px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _copy(self):
        QApplication.clipboard().setText(self.txt_message.toPlainText())
        QMessageBox.information(self, "Copied", "Commit message copied to clipboard!")


class GitToolsWidget(QWidget):
    """Comprehensive Git Developer Tools tab widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = GitService()
        self.current_repo_path: str = os.getcwd()
        self.current_info: Optional[GitRepoInfo] = None
        self.worker: Optional[GitWorker] = None

        self._setup_ui()
        self._load_repo(self.current_repo_path)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Repository Selection Header Bar
        repo_group = QGroupBox("Git Repository")
        repo_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        repo_layout = QHBoxLayout(repo_group)

        self.txt_repo_path = QLineEdit(self.current_repo_path)
        self.txt_repo_path.setStyleSheet("background-color: #181825; border: 1px solid #45475a; border-radius: 4px; padding: 6px; color: #cdd6f4;")
        self.txt_repo_path.returnPressed.connect(self._on_path_entered)
        repo_layout.addWidget(self.txt_repo_path, 1)

        btn_browse = QPushButton("📁 Browse...")
        btn_browse.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_browse.clicked.connect(self._browse_folder)
        repo_layout.addWidget(btn_browse)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        btn_refresh.clicked.connect(self._refresh_all)
        repo_layout.addWidget(btn_refresh)

        btn_open_folder = QPushButton("📂 Open Folder")
        btn_open_folder.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 6px 12px; border-radius: 4px;")
        btn_open_folder.clicked.connect(self._open_folder)
        repo_layout.addWidget(btn_open_folder)

        main_layout.addWidget(repo_group)

        # 2. Repo Info Bar
        info_bar = QHBoxLayout()
        self.lbl_branch = QLabel("🌿 Branch: --")
        self.lbl_branch.setStyleSheet("font-weight: bold; color: #a6e3a1; background-color: #181825; padding: 4px 10px; border-radius: 4px; border: 1px solid #313244;")
        info_bar.addWidget(self.lbl_branch)

        btn_copy_branch = QPushButton("Copy Branch")
        btn_copy_branch.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        btn_copy_branch.clicked.connect(self._copy_branch)
        info_bar.addWidget(btn_copy_branch)

        self.lbl_sync = QLabel("Sync: ↑0 ↓0")
        self.lbl_sync.setStyleSheet("color: #89b4fa; background-color: #181825; padding: 4px 10px; border-radius: 4px; border: 1px solid #313244;")
        info_bar.addWidget(self.lbl_sync)

        self.lbl_status = QLabel("Status: Checking...")
        self.lbl_status.setStyleSheet("color: #fab387; background-color: #181825; padding: 4px 10px; border-radius: 4px; border: 1px solid #313244;")
        info_bar.addWidget(self.lbl_status)

        info_bar.addStretch()

        self.chk_confirm_ai = QCheckBox("Always ask before sending source code to AI")
        self.chk_confirm_ai.setChecked(True)
        self.chk_confirm_ai.setStyleSheet("color: #a6adc8; font-size: 11px;")
        info_bar.addWidget(self.chk_confirm_ai)

        main_layout.addLayout(info_bar)

        # 3. Main Splitter: Left (Files & Commits) | Right (Diff Viewer)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Tab Widget: Changes & Commits
        left_tabs = QTabWidget()
        left_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #313244; background: #181825; border-radius: 4px; }
            QTabBar::tab { background: #1e1e2e; color: #a6adc8; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #313244; color: #cdd6f4; font-weight: bold; }
        """)

        # Tab 1: Changed Files Tree
        changes_widget = QWidget()
        changes_layout = QVBoxLayout(changes_widget)
        changes_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_changes = QTreeWidget()
        self.tree_changes.setHeaderLabels(["File / Path", "Status"])
        self.tree_changes.setColumnWidth(0, 220)
        self.tree_changes.setStyleSheet("background-color: #181825; color: #cdd6f4; border: none;")
        self.tree_changes.itemClicked.connect(self._on_file_selected)
        changes_layout.addWidget(self.tree_changes)

        left_tabs.addTab(changes_widget, "📝 Changes")

        # Tab 2: Commits History
        commits_widget = QWidget()
        commits_layout = QVBoxLayout(commits_widget)
        commits_layout.setContentsMargins(6, 6, 6, 6)

        self.table_commits = QTableWidget()
        self.table_commits.setColumnCount(4)
        self.table_commits.setHorizontalHeaderLabels(["Hash", "Author", "Date", "Message"])
        self.table_commits.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_commits.setStyleSheet("background-color: #181825; color: #cdd6f4; border: none;")
        self.table_commits.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_commits.itemDoubleClicked.connect(self._on_commit_double_clicked)
        commits_layout.addWidget(self.table_commits)

        btn_copy_hash = QPushButton("📋 Copy Commit Hash")
        btn_copy_hash.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 4px 8px; border-radius: 4px;")
        btn_copy_hash.clicked.connect(self._copy_selected_commit_hash)
        commits_layout.addWidget(btn_copy_hash)

        left_tabs.addTab(commits_widget, "📜 Recent Commits")

        splitter.addWidget(left_tabs)

        # Right Panel: Diff Viewer
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 6, 6, 6)

        # Diff Control Bar
        diff_ctrl_layout = QHBoxLayout()
        self.rb_diff_working = QRadioButton("Working Tree Diff")
        self.rb_diff_working.setChecked(True)
        self.rb_diff_working.toggled.connect(self._on_diff_type_changed)
        diff_ctrl_layout.addWidget(self.rb_diff_working)

        self.rb_diff_staged = QRadioButton("Staged Diff")
        self.rb_diff_staged.toggled.connect(self._on_diff_type_changed)
        diff_ctrl_layout.addWidget(self.rb_diff_staged)

        diff_ctrl_layout.addStretch()

        btn_copy_diff = QPushButton("📋 Copy Diff")
        btn_copy_diff.setStyleSheet("background-color: #313244; color: #cdd6f4; padding: 4px 8px; border-radius: 4px;")
        btn_copy_diff.clicked.connect(self._copy_diff)
        diff_ctrl_layout.addWidget(btn_copy_diff)

        btn_gen_commit = QPushButton("✨ Generate Commit Message")
        btn_gen_commit.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_gen_commit.clicked.connect(self._generate_commit_message)
        diff_ctrl_layout.addWidget(btn_gen_commit)

        right_layout.addLayout(diff_ctrl_layout)

        # Diff Text View
        self.txt_diff = QPlainTextEdit()
        self.txt_diff.setReadOnly(True)
        self.txt_diff.setFont(QFont("Consolas", 10))
        self.txt_diff.setStyleSheet("background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px; padding: 6px;")
        self.highlighter = DiffHighlighter(self.txt_diff.document())
        right_layout.addWidget(self.txt_diff)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 580])

        main_layout.addWidget(splitter, 1)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory", self.current_repo_path)
        if folder:
            self.txt_repo_path.setText(folder)
            self._load_repo(folder)

    def _on_path_entered(self):
        path = self.txt_repo_path.text().strip()
        if path:
            self._load_repo(path)

    def _load_repo(self, path: str):
        self.current_repo_path = path
        self.lbl_status.setText("Checking repository...")
        self.txt_diff.setPlainText("Loading...")

        # Worker for repo info
        self._worker_info = GitWorker(self.service, path, "info")
        self._worker_info.info_ready.connect(self._on_info_ready)
        self._worker_info.error_occurred.connect(self._on_error)
        self._worker_info.start()

        # Worker for commits
        self._worker_commits = GitWorker(self.service, path, "commits", count=30)
        self._worker_commits.commits_ready.connect(self._on_commits_ready)
        self._worker_commits.start()

        # Worker for diff
        self._load_diff()

    def _refresh_all(self):
        self._load_repo(self.current_repo_path)

    def _open_folder(self):
        if os.path.isdir(self.current_repo_path):
            try:
                if os.name == "nt":
                    os.startfile(self.current_repo_path)
                else:
                    subprocess.Popen(["xdg-open", self.current_repo_path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")

    def _copy_branch(self):
        if self.current_info and self.current_info.current_branch:
            QApplication.clipboard().setText(self.current_info.current_branch)
            self.lbl_status.setText("Branch name copied!")

    def _on_info_ready(self, info: GitRepoInfo):
        self.current_info = info
        if not info.is_repo:
            self.lbl_branch.setText("🌿 Branch: N/A")
            self.lbl_sync.setText("Sync: --")
            self.lbl_status.setText(f"❌ {info.error_message or 'Not a Git repository'}")
            self.tree_changes.clear()
            self.txt_diff.setPlainText("Selected folder is not a Git repository.")
            return

        self.lbl_branch.setText(f"🌿 {info.current_branch}")
        self.lbl_sync.setText(f"Sync: ↑{info.ahead} ↓{info.behind}")

        if info.is_clean:
            self.lbl_status.setText("✅ Clean working directory")
        else:
            self.lbl_status.setText(f"⚠️ {info.total_changes} changed file(s)")

        # Populate Changes Tree
        self.tree_changes.clear()

        # Staged category
        if info.staged_files:
            staged_group = QTreeWidgetItem(self.tree_changes, [f"Staged Changes ({len(info.staged_files)})", ""])
            staged_group.setExpanded(True)
            for f in info.staged_files:
                item = QTreeWidgetItem(staged_group, [f.path, f.status_code])
                item.setData(0, Qt.ItemDataRole.UserRole, ("staged", f.path))

        # Modified category
        if info.modified_files:
            mod_group = QTreeWidgetItem(self.tree_changes, [f"Changes ({len(info.modified_files)})", ""])
            mod_group.setExpanded(True)
            for f in info.modified_files:
                item = QTreeWidgetItem(mod_group, [f.path, f.status_code])
                item.setData(0, Qt.ItemDataRole.UserRole, ("modified", f.path))

        # Untracked category
        if info.untracked_files:
            untrack_group = QTreeWidgetItem(self.tree_changes, [f"Untracked Files ({len(info.untracked_files)})", ""])
            untrack_group.setExpanded(True)
            for f in info.untracked_files:
                item = QTreeWidgetItem(untrack_group, [f.path, "??"])
                item.setData(0, Qt.ItemDataRole.UserRole, ("untracked", f.path))

    def _on_commits_ready(self, commits: list[GitCommit]):
        self.table_commits.setRowCount(0)
        for commit in commits:
            row = self.table_commits.rowCount()
            self.table_commits.insertRow(row)

            item_hash = QTableWidgetItem(commit.short_hash)
            item_hash.setData(Qt.ItemDataRole.UserRole, commit.hash)
            self.table_commits.setItem(row, 0, item_hash)

            self.table_commits.setItem(row, 1, QTableWidgetItem(commit.author))
            self.table_commits.setItem(row, 2, QTableWidgetItem(commit.date[:16]))
            self.table_commits.setItem(row, 3, QTableWidgetItem(commit.message))

    def _on_file_selected(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            # Clicked a category header
            return
        category, file_path = data
        staged = (category == "staged")
        self._load_diff(staged=staged, file_path=file_path)

    def _on_diff_type_changed(self):
        self._load_diff()

    def _load_diff(self, staged: Optional[bool] = None, file_path: Optional[str] = None):
        if staged is None:
            staged = self.rb_diff_staged.isChecked()

        self._worker_diff = GitWorker(self.service, self.current_repo_path, "diff", staged=staged, file_path=file_path)
        self._worker_diff.diff_ready.connect(lambda d: self.txt_diff.setPlainText(d))
        self._worker_diff.start()

    def _copy_diff(self):
        diff = self.txt_diff.toPlainText()
        if diff:
            QApplication.clipboard().setText(diff)
            self.lbl_status.setText("Diff copied to clipboard!")

    def _copy_selected_commit_hash(self):
        selected_rows = self.table_commits.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            full_hash = self.table_commits.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if full_hash:
                QApplication.clipboard().setText(full_hash)
                self.lbl_status.setText(f"Commit hash {full_hash[:8]} copied!")

    def _on_commit_double_clicked(self, item: QTableWidgetItem):
        self._copy_selected_commit_hash()

    def _generate_commit_message(self):
        diff = self.txt_diff.toPlainText()
        msg = self.service.generate_commit_message_heuristic(diff, self.current_info)
        dlg = CommitMessageDialog(msg, self)
        dlg.exec()

    def _on_error(self, err: str):
        self.lbl_status.setText(f"❌ Error: {err}")

    def cleanup(self):
        """Safely cancel and wait for running Git workers."""
        for w_attr in ("_worker_info", "_worker_commits", "_worker_diff"):
            w = getattr(self, w_attr, None)
            if w:
                if w.isRunning():
                    w.wait(1000)
                setattr(self, w_attr, None)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
