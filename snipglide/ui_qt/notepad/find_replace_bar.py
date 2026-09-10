from typing import Optional, List
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QFrame, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QToolButton, QLabel, QCheckBox, QSizePolicy, QTextEdit
)
from snipglide.ui_qt.notepad.icons import create_vector_icon

class FindReplaceBar(QFrame):
    """
    Modern embedded search & replace bar with regex, case sensitivity,
    match counting, and replace-all capabilities.
    """
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("findReplaceBar")
        self.setStyleSheet("""
            QFrame#findReplaceBar {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
                padding: 6px;
            }
            QLineEdit {
                background-color: #202c33;
                color: #f0f2f5;
                border: 1.5px solid #3b4a54;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #25D366;
            }
            QPushButton, QToolButton {
                background-color: #202c33;
                color: #f0f2f5;
                border: 1px solid #3b4a54;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #2a3942;
                border-color: #25D366;
            }
            QToolButton:checked {
                background-color: #172554;
                color: #60a5fa;
                border-color: #3b82f6;
            }
            QLabel {
                color: #94a3b8;
                font-size: 12px;
            }
        """)

        self.editor: Optional[NotepadEditor] = None
        self.matches: List[QTextCursor] = []
        self.current_match_idx: int = -1

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(6)

        # Row 1: Find row
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_icon = QLabel("🔍")
        lbl_icon.setStyleSheet("font-size: 14px;")
        row1.addWidget(lbl_icon)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("بحث... (Find)")
        self.find_input.textChanged.connect(self._on_search_query_changed)
        self.find_input.returnPressed.connect(self.find_next)
        row1.addWidget(self.find_input, stretch=2)

        self.match_count_lbl = QLabel("0 نتائج")
        row1.addWidget(self.match_count_lbl)

        # Prev / Next
        self.btn_prev = QPushButton("▲ سابق")
        self.btn_prev.setToolTip("السابق (Shift+F3)")
        self.btn_prev.clicked.connect(self.find_prev)
        row1.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▼ تالي")
        self.btn_next.setToolTip("التالي (F3 أو Enter)")
        self.btn_next.clicked.connect(self.find_next)
        row1.addWidget(self.btn_next)

        # Options
        self.btn_case = QToolButton()
        self.btn_case.setText("Aa")
        self.btn_case.setCheckable(True)
        self.btn_case.setToolTip("حساسية حالة الأحرف (Match Case)")
        self.btn_case.toggled.connect(self._on_search_query_changed)
        row1.addWidget(self.btn_case)

        self.btn_word = QToolButton()
        self.btn_word.setText(r"\b")
        self.btn_word.setCheckable(True)
        self.btn_word.setToolTip("تطابق الكلمة بالكامل (Whole Word)")
        self.btn_word.toggled.connect(self._on_search_query_changed)
        row1.addWidget(self.btn_word)

        self.btn_regex = QToolButton()
        self.btn_regex.setText(".*")
        self.btn_regex.setCheckable(True)
        self.btn_regex.setToolTip("تعبير نمطي (Regular Expression)")
        self.btn_regex.toggled.connect(self._on_search_query_changed)
        row1.addWidget(self.btn_regex)

        # Toggle Replace row button
        self.btn_toggle_replace = QToolButton()
        self.btn_toggle_replace.setText("⇄ استبدال")
        self.btn_toggle_replace.setCheckable(True)
        self.btn_toggle_replace.toggled.connect(self._toggle_replace_row)
        row1.addWidget(self.btn_toggle_replace)

        # Close button
        btn_close = QToolButton()
        btn_close.setText("✕")
        btn_close.setStyleSheet("border: none; background: transparent; font-size: 14px; color: #94a3b8;")
        btn_close.clicked.connect(self.hide_bar)
        row1.addWidget(btn_close)

        main_layout.addLayout(row1)

        # Row 2: Replace row (Collapsible)
        self.replace_widget = QWidget()
        row2 = QHBoxLayout(self.replace_widget)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)

        lbl_rep = QLabel("📝")
        lbl_rep.setStyleSheet("font-size: 14px;")
        row2.addWidget(lbl_rep)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("استبدال بـ... (Replace with)")
        self.replace_input.returnPressed.connect(self.replace_current)
        row2.addWidget(self.replace_input, stretch=2)

        self.btn_replace = QPushButton("استبدال")
        self.btn_replace.clicked.connect(self.replace_current)
        row2.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton("استبدال الكل")
        self.btn_replace_all.clicked.connect(self.replace_all)
        row2.addWidget(self.btn_replace_all)

        main_layout.addWidget(self.replace_widget)
        self.replace_widget.hide()

    def set_editor(self, editor: NotepadEditor):
        self.editor = editor
        self.matches.clear()
        self.current_match_idx = -1
        self._on_search_query_changed()

    def show_search(self, show_replace: bool = False):
        self.show()
        if show_replace:
            self.btn_toggle_replace.setChecked(True)
            self.replace_widget.show()
        if self.editor:
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                self.find_input.setText(cursor.selectedText())
        self.find_input.selectAll()
        self.find_input.setFocus()
        self._on_search_query_changed()

    def hide_bar(self):
        self.hide()
        if self.editor:
            self.editor.set_find_highlights([])
            self.editor.setFocus()
        self.closed.emit()

    def _toggle_replace_row(self, checked: bool):
        self.replace_widget.setVisible(checked)
        if checked:
            self.replace_input.setFocus()

    def _apply_highlights(self):
        """Highlight all occurrences in the document with vivid glowing contrast."""
        if not self.editor:
            return
        if not self.matches:
            self.editor.set_find_highlights([])
            return

        highlight_selections = []
        for idx, match_cursor in enumerate(self.matches):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = QTextCursor(match_cursor)
            if idx == self.current_match_idx:
                # Active / Current match: Radiant neon yellow with deep black text and bold weight
                sel.format.setBackground(QColor("#facc15"))
                sel.format.setForeground(QColor("#000000"))
                sel.format.setFontWeight(QFont.Bold)
            else:
                # All other matches: Warm amber with light yellow text
                sel.format.setBackground(QColor("#b45309"))
                sel.format.setForeground(QColor("#fef08a"))
            highlight_selections.append(sel)

        self.editor.set_find_highlights(highlight_selections)

    def _on_search_query_changed(self):
        if not self.editor:
            return
        query = self.find_input.text()
        if not query:
            self.matches.clear()
            self.current_match_idx = -1
            self.match_count_lbl.setText("0 نتائج")
            self._apply_highlights()
            return

        doc = self.editor.document()
        flags = QTextDocument.FindFlags()
        if self.btn_case.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.btn_word.isChecked():
            flags |= QTextDocument.FindWholeWords

        self.matches.clear()

        is_regex = self.btn_regex.isChecked()
        if is_regex:
            try:
                reg_options = QRegularExpression.NoPatternOption
                if not self.btn_case.isChecked():
                    reg_options |= QRegularExpression.CaseInsensitiveOption
                regex = QRegularExpression(query, reg_options)
                cursor = doc.find(regex, 0)
                while not cursor.isNull():
                    self.matches.append(QTextCursor(cursor))
                    cursor = doc.find(regex, cursor.position())
            except Exception:
                self.match_count_lbl.setText("Regex خطأ")
                self._apply_highlights()
                return
        else:
            cursor = doc.find(query, 0, flags)
            while not cursor.isNull():
                self.matches.append(QTextCursor(cursor))
                cursor = doc.find(query, cursor.position(), flags)

        total = len(self.matches)
        if total == 0:
            self.match_count_lbl.setText("لم يتم العثور")
            self.current_match_idx = -1
            self._apply_highlights()
        else:
            # Find closest match relative to current cursor
            current_pos = self.editor.textCursor().position()
            self.current_match_idx = 0
            for i, m in enumerate(self.matches):
                if m.position() >= current_pos:
                    self.current_match_idx = i
                    break
            self._apply_highlights()
            self.match_count_lbl.setText(f"{self.current_match_idx + 1} من {total}")

    def find_next(self):
        if not self.matches or not self.editor:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        cursor = self.matches[self.current_match_idx]
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self._apply_highlights()
        self.match_count_lbl.setText(f"{self.current_match_idx + 1} من {len(self.matches)}")

    def find_prev(self):
        if not self.matches or not self.editor:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.matches)
        cursor = self.matches[self.current_match_idx]
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self._apply_highlights()
        self.match_count_lbl.setText(f"{self.current_match_idx + 1} من {len(self.matches)}")

    def replace_current(self):
        if not self.editor or not self.matches or self.current_match_idx < 0:
            return
        cursor = self.editor.textCursor()
        replacement = self.replace_input.text()
        if cursor.hasSelection():
            cursor.insertText(replacement)
            self._on_search_query_changed()
            self.find_next()

    def replace_all(self):
        if not self.editor or not self.matches:
            return
        replacement = self.replace_input.text()
        count = len(self.matches)
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        # Replace backwards so indices do not shift
        for m in reversed(self.matches):
            m.insertText(replacement)
        cursor.endEditBlock()
        self._on_search_query_changed()
        self.match_count_lbl.setText(f"تم استبدال {count}")
        main_win = self.window()
        if hasattr(main_win, "toast"):
            main_win.toast(f"تم استبدال {count} من النتائج بنجاح! ✨", False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_bar()
            event.accept()
            return
        super().keyPressEvent(event)


