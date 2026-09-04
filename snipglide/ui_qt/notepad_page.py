import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer, QRegularExpression, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QTextFormat, QTextCursor, QFont, QKeySequence,
    QShortcut, QAction, QIcon, QTextDocument, QCursor, QTextCharFormat,
    QTextOption, QTextBlockFormat, QFontDatabase
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit, QTabWidget,
    QTabBar, QLabel, QPushButton, QToolButton, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QInputDialog, QFontDialog, QMenu,
    QApplication, QFrame, QDialog, QDialogButtonBox, QGridLayout,
    QMenuBar, QToolBar, QSizePolicy, QComboBox, QFontComboBox
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from snipglide.services.notepad_session import (
    load_notepad_session, save_notepad_session,
    get_recent_files, add_recent_file, clear_recent_files,
    DEFAULT_NOTEPAD_SETTINGS
)
from snipglide.core.config import get_arabic_font_family
from snipglide.database.note_repo import add_note
from snipglide.database.chat_note_repo import add_chat_note
from snipglide.models.note import Note


class LineNumberArea(QWidget):
    """Line number gutter widget painted beside the text editor."""
    def __init__(self, editor: 'NotepadEditor'):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


class NotepadEditor(QPlainTextEdit):
    """
    Enhanced plain text editor with line numbers, active line highlight,
    zooming, auto-indentation, and Windows Notepad shortcuts.
    """
    stats_changed = Signal()
    content_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notepadTextEditor")
        self.line_number_area = LineNumberArea(self)
        self.file_path: Optional[str] = None
        self.is_modified: bool = False
        self.encoding: str = "UTF-8"
        self.line_ending: str = "CRLF" if os.name == "nt" else "LF"
        self.zoom_factor: int = 0
        self.base_font_size: int = 14
        self.highlight_current_line_enabled: bool = True
        self.line_numbers_enabled: bool = True
        self.current_font = QFont("Consolas", self.base_font_size)
        self.current_font.setStyleHint(QFont.Monospace)

        # Editor UI Settings with internal padding and document margin
        self.setStyleSheet("""
            QPlainTextEdit#notepadTextEditor {
                background-color: #0b141a;
                color: #f0f2f5;
                border: none;
                selection-background-color: #172554;
                selection-color: #93c5fd;
                padding: 6px 12px;
            }
        """)
        self.document().setDocumentMargin(12)
        self.set_font_properties(self.current_font)

        # Connect signals for line numbers & active line
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self._emit_stats)
        self.textChanged.connect(self._on_text_changed)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self) -> int:
        if not self.line_numbers_enabled:
            return 0
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 28 + self.fontMetrics().horizontalAdvance('9') * digits
        return max(space, 48)

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth() + 10, 4, 8, 8)

    def updateLineNumberArea(self, rect: QRect, dy: int):
        if not self.line_numbers_enabled:
            return
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def set_line_numbers_visible(self, visible: bool):
        self.line_numbers_enabled = visible
        self.line_number_area.setVisible(visible)
        self.updateLineNumberAreaWidth(0)
        self.line_number_area.update()

    def lineNumberAreaPaintEvent(self, event):
        if not self.line_numbers_enabled:
            return
        painter = QPainter(self.line_number_area)
        # Background for line numbers margin
        painter.fillRect(event.rect(), QColor("#111b21"))

        # Right border line
        painter.setPen(QColor("#202c33"))
        painter.drawLine(
            self.line_number_area.width() - 1, event.rect().top(),
            self.line_number_area.width() - 1, event.rect().bottom()
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_line = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == current_line:
                    painter.setPen(QColor("#25D366"))
                    font = painter.font()
                    font.setBold(True)
                    painter.setFont(font)
                else:
                    painter.setPen(QColor("#64748b"))
                    font = painter.font()
                    font.setBold(False)
                    painter.setFont(font)

                painter.drawText(
                    0, top, self.line_number_area.width() - 10,
                    self.fontMetrics().height(),
                    Qt.AlignRight, number
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlightCurrentLine(self):
        extra_selections = []
        if not self.isReadOnly() and self.highlight_current_line_enabled:
            selection = QTextEditSelection()
            line_color = QColor("#142028")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        # Preserve find highlights if active
        if hasattr(self, "_find_selections") and self._find_selections:
            extra_selections.extend(self._find_selections)

        self.setExtraSelections(extra_selections)

    def set_current_line_highlight_enabled(self, enabled: bool):
        self.highlight_current_line_enabled = enabled
        self.highlightCurrentLine()

    def set_find_highlights(self, selections: List[QTextEditSelection]):
        self._find_selections = selections
        self.highlightCurrentLine()

    def _on_text_changed(self):
        self.is_modified = True
        self.content_modified.emit()
        self._emit_stats()

    def _emit_stats(self):
        self.stats_changed.emit()

    def get_stats(self) -> Dict[str, Any]:
        text = self.toPlainText()
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        selected_text = cursor.selectedText()
        selected_chars = len(selected_text.replace('\u2029', '\n'))

        words = len(re.findall(r'\S+', text))
        chars = len(text)
        lines = self.blockCount()

        return {
            "line": line,
            "col": col,
            "selected_chars": selected_chars,
            "words": words,
            "chars": chars,
            "lines": lines,
            "line_ending": self.line_ending,
            "encoding": self.encoding,
            "zoom_factor": self.zoom_factor,
        }

    # ── Key Event Handling & Indentation ──
    def keyPressEvent(self, event):
        # F5 -> Insert Windows Notepad Date/Time
        if event.key() == Qt.Key_F5:
            now_str = datetime.now().strftime("%I:%M %p %m/%d/%Y")
            self.insertPlainText(now_str)
            event.accept()
            return

        # Auto-indent on Enter
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indent = ""
            for ch in current_line:
                if ch in (" ", "\t"):
                    indent += ch
                else:
                    break
            super().keyPressEvent(event)
            if indent:
                self.insertPlainText(indent)
            return

        # Tab Indentation
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                # Indent block
                self._indent_selection(indent=True)
            else:
                self.insertPlainText("    ")
            event.accept()
            return

        # Shift+Tab Unindent
        if event.key() == Qt.Key_Backtab:
            self._indent_selection(indent=False)
            event.accept()
            return

        # Ctrl + Wheel Zoom is handled in wheelEvent
        super().keyPressEvent(event)

    def _indent_selection(self, indent: bool = True):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()

        cursor.beginEditBlock()
        cursor.setPosition(start)
        for _ in range(start_block, end_block + 1):
            cursor.movePosition(QTextCursor.StartOfBlock)
            if indent:
                cursor.insertText("    ")
            else:
                line_text = cursor.block().text()
                if line_text.startswith("    "):
                    for _ in range(4):
                        cursor.deleteChar()
                elif line_text.startswith("\t") or line_text.startswith(" "):
                    cursor.deleteChar()
            cursor.movePosition(QTextCursor.NextBlock)
        cursor.endEditBlock()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def zoom_in(self):
        if self.zoom_factor < 25:
            self.zoom_factor += 1
            new_size = max(6, min(72, self.base_font_size + self.zoom_factor * 2))
            f = QFont(self.current_font)
            f.setPointSize(new_size)
            self.set_font_properties(f, update_base=False)

    def zoom_out(self):
        if self.zoom_factor > -6:
            self.zoom_factor -= 1
            new_size = max(6, min(72, self.base_font_size + self.zoom_factor * 2))
            f = QFont(self.current_font)
            f.setPointSize(new_size)
            self.set_font_properties(f, update_base=False)

    def reset_zoom(self):
        self.zoom_factor = 0
        f = QFont(self.current_font)
        f.setPointSize(self.base_font_size)
        self.set_font_properties(f, update_base=False)

    def set_font_properties(self, font: QFont, update_base: bool = True):
        pt = font.pointSize()
        px = font.pixelSize()
        size = pt if pt > 0 else (px if px > 0 else self.base_font_size)
        if size <= 0:
            size = 14

        if update_base:
            self.base_font_size = size
            self.zoom_factor = 0

        self.current_font = QFont(font)
        self.current_font.setPointSize(size)
        self.setFont(self.current_font)
        self.document().setDefaultFont(self.current_font)

        # Set character format for subsequent user input
        fmt = QTextCharFormat()
        fmt.setFont(self.current_font)
        self.setCurrentCharFormat(fmt)

        # Apply format to all existing text blocks so text resizes immediately
        cursor = self.textCursor()
        pos = cursor.position()
        anchor = cursor.anchor()
        cursor.select(QTextCursor.Document)
        cursor.mergeCharFormat(fmt)
        cursor.setPosition(anchor)
        cursor.setPosition(pos, QTextCursor.KeepAnchor if anchor != pos else QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)

        self.updateLineNumberAreaWidth(0)
        self.line_number_area.update()
        self._emit_stats()

    def set_font_size(self, size: int):
        f = QFont(self.current_font)
        f.setPointSize(size)
        self.set_font_properties(f, update_base=True)

    def set_font_family(self, family: str):
        f = QFont(self.current_font)
        f.setFamily(family)
        self.set_font_properties(f, update_base=False)

    def toggle_bold(self) -> bool:
        f = QFont(self.current_font)
        f.setBold(not f.bold())
        self.set_font_properties(f, update_base=False)
        return f.bold()

    def toggle_italic(self) -> bool:
        f = QFont(self.current_font)
        f.setItalic(not f.italic())
        self.set_font_properties(f, update_base=False)
        return f.italic()

    def toggle_underline(self) -> bool:
        f = QFont(self.current_font)
        f.setUnderline(not f.underline())
        self.set_font_properties(f, update_base=False)
        return f.underline()

    def toggle_word_wrap(self, wrap: bool):
        if wrap:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setWordWrapMode(QTextOption.NoWrap)

    def set_text_direction(self, is_rtl: bool):
        align = Qt.AlignRight if is_rtl else Qt.AlignLeft
        self.setLayoutDirection(Qt.RightToLeft if is_rtl else Qt.LeftToRight)

        opt = self.document().defaultTextOption()
        opt.setTextDirection(Qt.RightToLeft if is_rtl else Qt.LeftToRight)
        opt.setAlignment(align)
        self.document().setDefaultTextOption(opt)

        cursor = self.textCursor()
        pos = cursor.position()
        anchor = cursor.anchor()
        cursor.select(QTextCursor.Document)
        b_fmt = QTextBlockFormat()
        b_fmt.setAlignment(align)
        cursor.mergeBlockFormat(b_fmt)
        cursor.setPosition(anchor)
        cursor.setPosition(pos, QTextCursor.KeepAnchor if anchor != pos else QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)

    def set_text_alignment(self, align: Qt.AlignmentFlag):
        opt = self.document().defaultTextOption()
        opt.setAlignment(align)
        self.document().setDefaultTextOption(opt)

        cursor = self.textCursor()
        pos = cursor.position()
        anchor = cursor.anchor()
        if cursor.hasSelection():
            b_fmt = QTextBlockFormat()
            b_fmt.setAlignment(align)
            cursor.mergeBlockFormat(b_fmt)
        else:
            cursor.select(QTextCursor.Document)
            b_fmt = QTextBlockFormat()
            b_fmt.setAlignment(align)
            cursor.mergeBlockFormat(b_fmt)
            cursor.setPosition(anchor)
            cursor.setPosition(pos, QTextCursor.KeepAnchor if anchor != pos else QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)


QTextEditSelection = QTextEdit.ExtraSelection


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

    def _on_search_query_changed(self):
        if not self.editor:
            return
        query = self.find_input.text()
        if not query:
            self.matches.clear()
            self.current_match_idx = -1
            self.match_count_lbl.setText("0 نتائج")
            self.editor.set_find_highlights([])
            return

        doc = self.editor.document()
        flags = QTextDocument.FindFlags()
        if self.btn_case.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.btn_word.isChecked():
            flags |= QTextDocument.FindWholeWords

        self.matches.clear()
        highlight_selections = []

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
                    sel = QTextEditSelection()
                    sel.cursor = QTextCursor(cursor)
                    sel.format.setBackground(QColor("#451a03"))
                    sel.format.setForeground(QColor("#fbbf24"))
                    highlight_selections.append(sel)
                    cursor = doc.find(regex, cursor.position())
            except Exception:
                self.match_count_lbl.setText("Regex خطأ")
                return
        else:
            cursor = doc.find(query, 0, flags)
            while not cursor.isNull():
                self.matches.append(QTextCursor(cursor))
                sel = QTextEditSelection()
                sel.cursor = QTextCursor(cursor)
                sel.format.setBackground(QColor("#451a03"))
                sel.format.setForeground(QColor("#fbbf24"))
                highlight_selections.append(sel)
                cursor = doc.find(query, cursor.position(), flags)

        self.editor.set_find_highlights(highlight_selections)

        total = len(self.matches)
        if total == 0:
            self.match_count_lbl.setText("لم يتم العثور")
            self.current_match_idx = -1
        else:
            # Find closest match relative to current cursor
            current_pos = self.editor.textCursor().position()
            self.current_match_idx = 0
            for i, m in enumerate(self.matches):
                if m.position() >= current_pos:
                    self.current_match_idx = i
                    break
            self.match_count_lbl.setText(f"{self.current_match_idx + 1} من {total}")

    def find_next(self):
        if not self.matches or not self.editor:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        cursor = self.matches[self.current_match_idx]
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.match_count_lbl.setText(f"{self.current_match_idx + 1} من {len(self.matches)}")

    def find_prev(self):
        if not self.matches or not self.editor:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.matches)
        cursor = self.matches[self.current_match_idx]
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
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


class SmoothTabBar(QTabBar):
    """
    Modern Windows 11 Fluent style tab bar with smooth mouse-wheel scrolling,
    arrow scroll buttons on overflow, and responsive tab widths.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideRight)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setExpanding(False)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def wheelEvent(self, event):
        # Allow mouse wheel over tabs to switch tabs smoothly
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta > 0:
            new_idx = max(0, self.currentIndex() - 1)
        else:
            new_idx = min(self.count() - 1, self.currentIndex() + 1)
        if new_idx != self.currentIndex():
            self.setCurrentIndex(new_idx)
        event.accept()

    def tabSizeHint(self, index: int) -> QSize:
        hint = super().tabSizeHint(index)
        w = max(135, min(240, hint.width() + 24))
        return QSize(w, 38)


class NotepadTab(QWidget):
    """Container holding a single Notepad document editor."""
    def __init__(
        self,
        file_path: Optional[str] = None,
        title: str = "مستند جديد",
        folder: str = "العامة",
        is_favorite: bool = False,
        is_archived: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.title = title
        self.folder = folder if folder else "العامة"
        self.is_favorite = is_favorite
        self.is_archived = is_archived
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.editor = NotepadEditor(self)
        self.layout.addWidget(self.editor)


class NotepadPageQt(QWidget):
    """
    Complete Windows Notepad application page with multi-tab interface,
    menus, toolbar, find & replace, real-time status bar, and SnipGlide integration.
    """
    def __init__(self, toast_callback=None, parent=None):
        super().__init__(parent)
        self.toast_callback = toast_callback
        self.setObjectName("notepadPage")
        self.active_font = QFont("Consolas", 14)
        self.is_current_direction_rtl = False

        # Organization state (Folders, Favorites, Archive)
        self.folders: List[str] = ["العامة", "العمل", "شخصي"]
        self.active_folder: str = "كافة الملفات"
        self.active_filter: str = "all"  # "all", "favorites", "archive", "folder"

        # Focus / Fullscreen mode state
        self._is_focus_mode: bool = False
        self._saved_geometry = None
        self._saved_maximized: bool = False

        self.session_save_timer = QTimer(self)
        self.session_save_timer.setSingleShot(True)
        self.session_save_timer.setInterval(1500)
        self.session_save_timer.timeout.connect(self._save_session_state)

        self._setup_ui()
        self._load_session_or_default()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # ── 1. Top Header Card (Spacious, rounded, high-contrast) ──
        self.header_card = QFrame(self)
        self.header_card.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 12px;
            }
        """)
        top_bar = QHBoxLayout(self.header_card)
        top_bar.setContentsMargins(14, 10, 14, 10)
        top_bar.setSpacing(12)

        icon_lbl = QLabel("🗒️")
        icon_lbl.setStyleSheet("font-size: 24px; border: none; background: transparent;")
        top_bar.addWidget(icon_lbl)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        app_title = QLabel("مفكرة ويندوز المتطورة (Windows Notepad Pro)")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f0f2f5; border: none; background: transparent;")
        title_layout.addWidget(app_title)

        sub_title = QLabel("محرر نصوص متطور بنظام التبويبات المتعددة واستعادة تلقائية للجلسة وحفظ فوري")
        sub_title.setStyleSheet("font-size: 12px; color: #94a3b8; border: none; background: transparent;")
        title_layout.addWidget(sub_title)
        top_bar.addLayout(title_layout)

        top_bar.addStretch()

        # Focus mode button
        btn_focus = QPushButton("⛶ وضع التركيز (F11)")
        btn_focus.setToolTip("وضع التركيز بكامل الشاشة على المفكرة فقط مع إخفاء كافة القوائم والأشرطة (Esc أو F11 للخروج)")
        btn_focus.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #c084fc;
                border: 1.5px solid #7e22ce;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7e22ce;
                color: #ffffff;
            }
        """)
        btn_focus.clicked.connect(self.toggle_focus_mode)
        top_bar.addWidget(btn_focus)

        # Quick New Document button
        btn_quick_new = QPushButton("➕ مستند جديد")
        btn_quick_new.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #25D366;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #25D366;
                color: #0b141a;
                border-color: #25D366;
            }
        """)
        btn_quick_new.clicked.connect(lambda: self.new_tab())
        top_bar.addWidget(btn_quick_new)

        # Quick Save All button
        btn_save_all = QPushButton("💾 حفظ الكل")
        btn_save_all.setStyleSheet("""
            QPushButton {
                background-color: #172554;
                color: #93c5fd;
                border: 1.5px solid #3b82f6;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        btn_save_all.clicked.connect(self.save_all_tabs)
        top_bar.addWidget(btn_save_all)

        main_layout.addWidget(self.header_card)

        # Floating Exit Focus Mode Pill Button
        self.focus_exit_pill = QPushButton("↩️ إنهاء وضع التركيز (Esc أو F11)", self)
        self.focus_exit_pill.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.95);
                color: #38bdf8;
                border: 2px solid #0284c7;
                border-radius: 18px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.focus_exit_pill.setCursor(Qt.PointingHandCursor)
        self.focus_exit_pill.clicked.connect(self.exit_focus_mode)
        self.focus_exit_pill.hide()

        # Focus mode shortcuts
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.esc_shortcut.activated.connect(self._on_esc_pressed)

        self.f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self.f11_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.f11_shortcut.activated.connect(self.toggle_focus_mode)

        # ── 2. Menu Bar (File, Edit, Format, View, SnipGlide) ──
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #182229;
                color: #f0f2f5;
                font-size: 14px;
                font-weight: bold;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
                padding: 4px 8px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 7px 16px;
                border-radius: 6px;
                margin-right: 4px;
            }
            QMenuBar::item:selected {
                background-color: #202c33;
                color: #25D366;
            }
            QMenu {
                background-color: #182229;
                border: 1.5px solid #2a3942;
                border-radius: 10px;
                padding: 6px;
                color: #f0f2f5;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 24px;
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
        main_layout.addWidget(self.menu_bar)

        # ── 3. Quick Action Toolbar ──
        self.toolbar = QToolBar(self)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 6px 10px;
                spacing: 8px;
            }
            QToolButton {
                background-color: #182229;
                color: #cbd5e1;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #202c33;
                border-color: #3b4a54;
                color: #ffffff;
            }
            QToolButton:pressed, QToolButton:checked {
                background-color: #172554;
                color: #60a5fa;
                border-color: #3b82f6;
            }
            QComboBox {
                background-color: #182229;
                color: #f0f2f5;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 13px;
                font-weight: bold;
                min-height: 20px;
            }
            QComboBox:hover {
                background-color: #202c33;
                border-color: #25D366;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #182229;
                color: #f0f2f5;
                selection-background-color: #172554;
                selection-color: #93c5fd;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        main_layout.addWidget(self.toolbar)

        # ── 3.5. Folder & Organization Bar (Folders, Favorites, Archive) ──
        self._build_folder_bar_ui()
        main_layout.addWidget(self.folder_bar_widget)

        # ── 4. Tab Widget Container with SmoothTabBar & Custom Styling ──
        self.tab_widget = QTabWidget(self)
        self.tab_bar = SmoothTabBar(self.tab_widget)
        self.tab_widget.setTabBar(self.tab_bar)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_switched)

        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        self.tab_bar.tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # Corner Widget (Transparent container for New Tab button)
        corner_widget = QWidget(self)
        corner_widget.setStyleSheet("background: transparent; border: none;")
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(4, 0, 4, 0)
        corner_layout.setSpacing(4)

        self.add_tab_btn = QToolButton(corner_widget)
        self.add_tab_btn.setText(" ➕ ")
        self.add_tab_btn.setToolTip("علامة تبويب جديدة (Ctrl+N أو Ctrl+T)")
        self.add_tab_btn.setStyleSheet("""
            QToolButton {
                background-color: #182229;
                color: #25D366;
                font-weight: bold;
                font-size: 15px;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 6px 12px;
                margin: 2px;
            }
            QToolButton:hover {
                background-color: #25D366;
                color: #0b141a;
                border-color: #25D366;
            }
            QToolButton:pressed {
                background-color: #1ea952;
            }
        """)
        self.add_tab_btn.clicked.connect(lambda: self.new_tab())
        corner_layout.addWidget(self.add_tab_btn)
        self.tab_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)

        self.tab_widget.setStyleSheet("""
            QTabWidget {
                background-color: transparent;
            }
            QTabWidget::pane {
                border: 1.5px solid #202c33;
                border-radius: 12px;
                background-color: #0b141a;
                padding: 6px;
                margin-top: 2px;
            }
            QTabBar {
                background: transparent;
                qproperty-drawBase: 0;
            }
            QTabBar::tab {
                background-color: #141e24;
                color: #94a3b8;
                border: 1.5px solid #202c33;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 16px;
                margin-right: 4px;
                margin-left: 2px;
                font-size: 13px;
                font-weight: bold;
                min-width: 135px;
                max-width: 240px;
                height: 24px;
            }
            QTabBar::tab:hover {
                background-color: #1f2c34;
                color: #f0f2f5;
                border-color: #3b4a54;
            }
            QTabBar::tab:selected {
                background-color: #0b141a;
                color: #60a5fa;
                border: 1.5px solid #3b82f6;
                border-bottom: 2px solid #0b141a;
                font-weight: bold;
            }
            QTabBar::close-button {
                subcontrol-position: right;
                margin-left: 8px;
                margin-right: 2px;
                border-radius: 9px;
                width: 18px;
                height: 18px;
                padding: 2px;
            }
            QTabBar::close-button:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
            QTabBar QToolButton {
                background-color: #182229;
                color: #25D366;
                border: 1.5px solid #2a3942;
                border-radius: 8px;
                padding: 4px 6px;
                margin: 2px;
            }
            QTabBar QToolButton:hover {
                background-color: #25D366;
                color: #0b141a;
                border-color: #25D366;
            }
            QTabBar QToolButton:disabled {
                background-color: transparent;
                border-color: transparent;
                color: #4b5563;
            }
        """)

        main_layout.addWidget(self.tab_widget, stretch=1)

        # ── 5. Embedded Find & Replace Bar ──
        self.find_replace_bar = FindReplaceBar(self)
        self.find_replace_bar.hide()
        main_layout.addWidget(self.find_replace_bar)

        # ── 6. Bottom Status Bar (Pill Badges with High-Contrast Spacing) ──
        self.status_bar_widget = QFrame(self)
        self.status_bar_widget.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 6px 12px;
            }
            QLabel {
                background-color: #182229;
                color: #cbd5e1;
                border: 1px solid #2a3942;
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QLabel:hover {
                border-color: #3b4a54;
                color: #ffffff;
            }
        """)
        status_layout = QHBoxLayout(self.status_bar_widget)
        status_layout.setContentsMargins(8, 4, 8, 4)
        status_layout.setSpacing(10)

        self.lbl_pos = QLabel("📍 السطر 1، العمود 1")
        status_layout.addWidget(self.lbl_pos)

        self.lbl_selection = QLabel("")
        self.lbl_selection.hide()
        status_layout.addWidget(self.lbl_selection)

        status_layout.addStretch()

        self.lbl_counts = QLabel("📊 0 كلمات | 0 أحرف | 1 أسطر")
        status_layout.addWidget(self.lbl_counts)

        self.lbl_zoom = QLabel("🔍 100%")
        status_layout.addWidget(self.lbl_zoom)

        self.lbl_ending = QLabel("⚡ Windows (CRLF)")
        self.lbl_ending.setCursor(QCursor(Qt.PointingHandCursor))
        self.lbl_ending.setToolTip("انقر للتبديل بين Windows (CRLF) و Unix (LF)")
        self.lbl_ending.mousePressEvent = self._toggle_line_ending
        status_layout.addWidget(self.lbl_ending)

        self.lbl_encoding = QLabel("🌐 UTF-8")
        status_layout.addWidget(self.lbl_encoding)

        self.lbl_direction = QLabel("🔤 LTR")
        status_layout.addWidget(self.lbl_direction)

        main_layout.addWidget(self.status_bar_widget)

        # Create menus and toolbar actions
        self._create_menus()
        self._create_toolbar_actions()

    # ── Menu & Toolbar Creation ──
    def _create_menus(self):
        # 1. File Menu
        file_menu = self.menu_bar.addMenu("ملف (File)")
        act_new = file_menu.addAction("📄 علامة تبويب جديدة")
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(lambda: self.new_tab())

        act_open = file_menu.addAction("📂 فتح ملف...")
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.open_file)

        file_menu.addSeparator()

        act_save = file_menu.addAction("💾 حفظ")
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.save_current_tab)

        act_save_as = file_menu.addAction("💾 حفظ باسم...")
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self.save_as_current_tab)

        act_save_all = file_menu.addAction("📚 حفظ كافة التبويبات")
        act_save_all.setShortcut(QKeySequence("Ctrl+Alt+S"))
        act_save_all.triggered.connect(self.save_all_tabs)

        file_menu.addSeparator()

        self.recent_menu = file_menu.addMenu("🕒 الملفات الأخيرة (Recent Files)")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        act_print = file_menu.addAction("🖨️ طباعة / تصدير PDF...")
        act_print.setShortcut(QKeySequence("Ctrl+P"))
        act_print.triggered.connect(self.print_or_export_pdf)

        act_close_tab = file_menu.addAction("✕ إغلاق التبويب الحالي")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))

        act_close_all = file_menu.addAction("✕ إغلاق كافة التبويبات")
        act_close_all.triggered.connect(self.close_all_tabs)

        # 2. Edit Menu
        edit_menu = self.menu_bar.addMenu("تحرير (Edit)")
        act_undo = edit_menu.addAction("↩️ تراجع")
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(lambda: self._call_editor("undo"))

        act_redo = edit_menu.addAction("↪️ إعادة")
        act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        act_redo.triggered.connect(lambda: self._call_editor("redo"))

        edit_menu.addSeparator()

        act_cut = edit_menu.addAction("✂️ قص")
        act_cut.setShortcut(QKeySequence("Ctrl+X"))
        act_cut.triggered.connect(lambda: self._call_editor("cut"))

        act_copy = edit_menu.addAction("📋 نسخ")
        act_copy.setShortcut(QKeySequence("Ctrl+C"))
        act_copy.triggered.connect(lambda: self._call_editor("copy"))

        act_paste = edit_menu.addAction("📥 لصق")
        act_paste.setShortcut(QKeySequence("Ctrl+V"))
        act_paste.triggered.connect(lambda: self._call_editor("paste"))

        act_del = edit_menu.addAction("🗑️ حذف")
        act_del.setShortcut(QKeySequence(Qt.Key_Delete))
        act_del.triggered.connect(self._delete_selected)

        edit_menu.addSeparator()

        act_find = edit_menu.addAction("🔍 بحث...")
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(lambda: self.find_replace_bar.show_search(show_replace=False))

        act_find_next = edit_menu.addAction("⬇️ بحث عن التالي")
        act_find_next.setShortcut(QKeySequence("F3"))
        act_find_next.triggered.connect(self.find_replace_bar.find_next)

        act_find_prev = edit_menu.addAction("⬆️ بحث عن السابق")
        act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        act_find_prev.triggered.connect(self.find_replace_bar.find_prev)

        act_replace = edit_menu.addAction("⇄ استبدال...")
        act_replace.setShortcut(QKeySequence("Ctrl+H"))
        act_replace.triggered.connect(lambda: self.find_replace_bar.show_search(show_replace=True))

        act_goto = edit_menu.addAction("🚀 الانتقال إلى سطر...")
        act_goto.setShortcut(QKeySequence("Ctrl+G"))
        act_goto.triggered.connect(self.go_to_line_dialog)

        edit_menu.addSeparator()

        act_select_all = edit_menu.addAction("✨ تحديد الكل")
        act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        act_select_all.triggered.connect(lambda: self._call_editor("selectAll"))

        act_time_date = edit_menu.addAction("⏰ الوقت/التاريخ (F5)")
        act_time_date.setShortcut(QKeySequence("F5"))
        act_time_date.triggered.connect(self._insert_time_date)

        # Advanced line tools submenu
        tools_sub = edit_menu.addMenu("⚡ أدوات الأسطر والنصوص")
        tools_sub.addAction("🔠 تحويل إلى أحرف كبيرة (UPPERCASE)", self._transform_to_upper)
        tools_sub.addAction("🔡 تحويل إلى أحرف صغيرة (lowercase)", self._transform_to_lower)
        tools_sub.addAction("🔤 تحويل إلى حالة العنوان (Title Case)", self._transform_to_title)
        tools_sub.addSeparator()
        tools_sub.addAction("📑 تكرار السطر الحالي (Duplicate Line)", self._duplicate_current_line)
        tools_sub.addAction("🔀 ترتيب الأسطر تصاعدياً (Sort Lines)", self._sort_lines_asc)
        tools_sub.addAction("🧹 حذف الأسطر الفارغة (Remove Empty Lines)", self._remove_empty_lines)

        # 3. Format Menu
        format_menu = self.menu_bar.addMenu("تنسيق (Format)")

        act_font = format_menu.addAction("🔤 الخط وحجم الخط المتقدم...")
        act_font.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_font.triggered.connect(self.choose_font_dialog)

        act_font_inc = format_menu.addAction("➕ زيادة حجم الخط (Font Size +2)")
        act_font_inc.setShortcut(QKeySequence("Ctrl+Shift+>"))
        act_font_inc.triggered.connect(self._quick_font_increase)

        act_font_dec = format_menu.addAction("➖ تصغير حجم الخط (Font Size -2)")
        act_font_dec.setShortcut(QKeySequence("Ctrl+Shift+<"))
        act_font_dec.triggered.connect(self._quick_font_decrease)

        act_font_reset = format_menu.addAction("🔄 استعادة حجم الخط الافتراضي (14pt)")
        act_font_reset.setShortcut(QKeySequence("Ctrl+Alt+0"))
        act_font_reset.triggered.connect(self._quick_font_reset)

        format_menu.addSeparator()

        self.act_bold = format_menu.addAction("<b>B</b> عريض (Bold)")
        self.act_bold.setShortcut(QKeySequence("Ctrl+B"))
        self.act_bold.setCheckable(True)
        self.act_bold.triggered.connect(self._quick_toggle_bold)

        self.act_italic = format_menu.addAction("<i>I</i> مائل (Italic)")
        self.act_italic.setShortcut(QKeySequence("Ctrl+I"))
        self.act_italic.setCheckable(True)
        self.act_italic.triggered.connect(self._quick_toggle_italic)

        self.act_underline = format_menu.addAction("<u>U</u> تسطير (Underline)")
        self.act_underline.setShortcut(QKeySequence("Ctrl+U"))
        self.act_underline.setCheckable(True)
        self.act_underline.triggered.connect(self._quick_toggle_underline)

        format_menu.addSeparator()

        self.act_word_wrap = format_menu.addAction("↩️ التفاف النص (Word Wrap)")
        self.act_word_wrap.setCheckable(True)
        self.act_word_wrap.setChecked(True)
        self.act_word_wrap.triggered.connect(self._on_toggle_word_wrap)

        format_menu.addSeparator()

        # Text direction & alignment
        align_sub = format_menu.addMenu("↔️ الاتجاه والمحاذاة (Direction & Alignment)")
        act_rtl = align_sub.addAction("➡️ اتجاه النص: من اليمين لليسار (RTL - عربي)")
        act_rtl.setShortcut(QKeySequence("Ctrl+Right"))
        act_rtl.triggered.connect(lambda: self._set_direction(is_rtl=True))

        act_ltr = align_sub.addAction("⬅️ اتجاه النص: من اليسار لليمين (LTR - إنجليزي)")
        act_ltr.setShortcut(QKeySequence("Ctrl+Left"))
        act_ltr.triggered.connect(lambda: self._set_direction(is_rtl=False))

        align_sub.addSeparator()
        act_align_r = align_sub.addAction("➡️ محاذاة لليمين (Align Right)")
        act_align_r.triggered.connect(lambda: self._set_alignment(Qt.AlignRight))

        act_align_c = align_sub.addAction("↔️ محاذاة للوسط (Align Center)")
        act_align_c.setShortcut(QKeySequence("Ctrl+E"))
        act_align_c.triggered.connect(lambda: self._set_alignment(Qt.AlignCenter))

        act_align_l = align_sub.addAction("⬅️ محاذاة لليسار (Align Left)")
        act_align_l.triggered.connect(lambda: self._set_alignment(Qt.AlignLeft))

        format_menu.addSeparator()

        # Text Transformations submenu
        text_tools_sub = format_menu.addMenu("⚡ أدوات تحويل النصوص والأسطر")
        text_tools_sub.addAction("🔠 تحويل إلى أحرف كبيرة (UPPERCASE)", self._transform_to_upper)
        text_tools_sub.addAction("🔡 تحويل إلى أحرف صغيرة (lowercase)", self._transform_to_lower)
        text_tools_sub.addAction("🔤 تحويل إلى حالة العنوان (Title Case)", self._transform_to_title)
        text_tools_sub.addAction("🔀 عكس حالة الأحرف (Toggle Case)", self._transform_toggle_case)
        text_tools_sub.addSeparator()
        text_tools_sub.addAction("📑 تكرار السطر الحالي (Duplicate Line)", self._duplicate_current_line)
        text_tools_sub.addAction("🗑️ حذف السطر الحالي (Delete Line)", self._delete_current_line)
        text_tools_sub.addSeparator()
        text_tools_sub.addAction("🔀 ترتيب الأسطر تصاعدياً (Sort Lines Asc)", self._sort_lines_asc)
        text_tools_sub.addAction("🔀 ترتيب الأسطر تنازلياً (Sort Lines Desc)", self._sort_lines_desc)
        text_tools_sub.addAction("🧹 حذف الأسطر الفارغة (Remove Empty Lines)", self._remove_empty_lines)
        text_tools_sub.addAction("✂️ إزالة الفراغات الزائدة من البداية والنهاية (Trim Whitespace)", self._trim_whitespace)
        text_tools_sub.addAction("🔢 ترقيم كافة الأسطر (Number Lines)", self._number_lines)

        # 4. View Menu
        view_menu = self.menu_bar.addMenu("عرض (View)")
        zoom_menu = view_menu.addMenu("🔍 تكبير/تصغير (Zoom)")
        act_zin = zoom_menu.addAction("➕ تكبير (Zoom In)")
        act_zin.setShortcut(QKeySequence("Ctrl++"))
        act_zin.triggered.connect(lambda: self._call_editor("zoom_in"))

        act_zout = zoom_menu.addAction("➖ تصغير (Zoom Out)")
        act_zout.setShortcut(QKeySequence("Ctrl+-"))
        act_zout.triggered.connect(lambda: self._call_editor("zoom_out"))

        act_zreset = zoom_menu.addAction("🔄 استعادة الحجم الافتراضي (100%)")
        act_zreset.setShortcut(QKeySequence("Ctrl+0"))
        act_zreset.triggered.connect(lambda: self._call_editor("reset_zoom"))

        view_menu.addSeparator()

        self.act_show_status = view_menu.addAction("📊 شريط الحالة (Status Bar)")
        self.act_show_status.setCheckable(True)
        self.act_show_status.setChecked(True)
        self.act_show_status.triggered.connect(lambda ch: self.status_bar_widget.setVisible(ch))

        self.act_show_linenums = view_menu.addAction("🔢 أرقام الأسطر (Line Numbers)")
        self.act_show_linenums.setCheckable(True)
        self.act_show_linenums.setChecked(True)
        self.act_show_linenums.triggered.connect(self._on_toggle_line_numbers)

        self.act_highlight_line = view_menu.addAction("💡 تمييز السطر الحالي")
        self.act_highlight_line.setCheckable(True)
        self.act_highlight_line.setChecked(True)
        self.act_highlight_line.triggered.connect(self._on_toggle_highlight_line)

        view_menu.addSeparator()
        self.act_focus_mode = view_menu.addAction("⛶ وضع التركيز بكامل الشاشة (Focus Mode)")
        self.act_focus_mode.setShortcut(QKeySequence("F11"))
        self.act_focus_mode.triggered.connect(self.toggle_focus_mode)

        # 5. SnipGlide Tools Menu
        snip_menu = self.menu_bar.addMenu("⚡ سنب جلايد (SnipGlide)")
        snip_menu.addAction("✂️ تحويل المحدد إلى اختصار SnipGlide", self.convert_selection_to_snippet)
        snip_menu.addAction("📝 حفظ المحتوى في الملاحظات اللاصقة", self.save_to_snipglide_notes)
        snip_menu.addAction("💬 إرسال إلى شات نوت (Chat Notes)", self.send_to_chat_notes)
        snip_menu.addSeparator()
        snip_menu.addAction("📊 إحصائيات تفصيلية للنص", self.show_text_stats_dialog)

    def _create_toolbar_actions(self):
        # 1. Documents: New, Open, Save
        btn_new = QToolButton()
        btn_new.setText("📄 جديد")
        btn_new.setToolTip("علامة تبويب جديدة (Ctrl+N)")
        btn_new.clicked.connect(lambda: self.new_tab())
        self.toolbar.addWidget(btn_new)

        btn_open = QToolButton()
        btn_open.setText("📂 فتح")
        btn_open.setToolTip("فتح ملف (Ctrl+O)")
        btn_open.clicked.connect(self.open_file)
        self.toolbar.addWidget(btn_open)

        btn_save = QToolButton()
        btn_save.setText("💾 حفظ")
        btn_save.setToolTip("حفظ الملف الحالي (Ctrl+S)")
        btn_save.clicked.connect(self.save_current_tab)
        self.toolbar.addWidget(btn_save)

        self.toolbar.addSeparator()

        # 2. History: Undo / Redo
        btn_undo = QToolButton()
        btn_undo.setText("↩️")
        btn_undo.setToolTip("تراجع (Ctrl+Z)")
        btn_undo.clicked.connect(lambda: self._call_editor("undo"))
        self.toolbar.addWidget(btn_undo)

        btn_redo = QToolButton()
        btn_redo.setText("↪️")
        btn_redo.setToolTip("إعادة (Ctrl+Y)")
        btn_redo.clicked.connect(lambda: self._call_editor("redo"))
        self.toolbar.addWidget(btn_redo)

        self.toolbar.addSeparator()

        # 3. Direct Font Family Picker
        lbl_font = QLabel("🔤 الخط:")
        lbl_font.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold; margin-left: 2px;")
        self.toolbar.addWidget(lbl_font)

        self.font_combo = QComboBox()
        self.font_combo.setToolTip("اختر نوع الخط المباشر للمفكرة")
        font_families = [
            "Consolas", "Tajawal", "Cairo", "Segoe UI", "Arial",
            "Courier New", "Cascadia Code", "Tahoma", "Amiri", "Times New Roman"
        ]
        try:
            sys_fonts = QFontDatabase.families()
            for f in sys_fonts:
                if f not in font_families and any(w in f.lower() for w in ["mono", "code", "arabic", "sans"]):
                    font_families.append(f)
        except Exception:
            pass
        self.font_combo.addItems(font_families[:25])
        self.font_combo.currentTextChanged.connect(self._on_font_family_selected)
        self.toolbar.addWidget(self.font_combo)

        # 4. Direct Font Size Picker
        self.size_combo = QComboBox()
        self.size_combo.setToolTip("اختر أو أدخل حجم الخط المباشر")
        self.size_combo.setEditable(True)
        sizes = ["9", "10", "11", "12", "14", "16", "18", "20", "22", "24", "28", "32", "36", "48", "72"]
        self.size_combo.addItems(sizes)
        self.size_combo.setCurrentText(str(self.active_font.pointSize()))
        self.size_combo.currentTextChanged.connect(self._on_font_size_selected)
        self.toolbar.addWidget(self.size_combo)

        # Quick A+ and A- buttons
        btn_plus = QToolButton()
        btn_plus.setText("A⁺")
        btn_plus.setToolTip("تكبير حجم الخط بنقطتين (Ctrl+Shift+>)")
        btn_plus.clicked.connect(self._quick_font_increase)
        self.toolbar.addWidget(btn_plus)

        btn_minus = QToolButton()
        btn_minus.setText("A⁻")
        btn_minus.setToolTip("تصغير حجم الخط بنقطتين (Ctrl+Shift+<)")
        btn_minus.clicked.connect(self._quick_font_decrease)
        self.toolbar.addWidget(btn_minus)

        self.toolbar.addSeparator()

        # 5. Bold, Italic, Underline
        self.btn_bold = QToolButton()
        self.btn_bold.setText("B")
        self.btn_bold.setStyleSheet("font-weight: 900; min-width: 22px;")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setToolTip("خط عريض (Ctrl+B)")
        self.btn_bold.clicked.connect(self._quick_toggle_bold)
        self.toolbar.addWidget(self.btn_bold)

        self.btn_italic = QToolButton()
        self.btn_italic.setText("I")
        self.btn_italic.setStyleSheet("font-style: italic; min-width: 22px;")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setToolTip("خط مائل (Ctrl+I)")
        self.btn_italic.clicked.connect(self._quick_toggle_italic)
        self.toolbar.addWidget(self.btn_italic)

        self.btn_underline = QToolButton()
        self.btn_underline.setText("U")
        self.btn_underline.setStyleSheet("text-decoration: underline; min-width: 22px;")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setToolTip("خط مسطر (Ctrl+U)")
        self.btn_underline.clicked.connect(self._quick_toggle_underline)
        self.toolbar.addWidget(self.btn_underline)

        self.toolbar.addSeparator()

        # 6. Alignment & Direction
        btn_align_right = QToolButton()
        btn_align_right.setText("🇸🇦 RTL عربي")
        btn_align_right.setToolTip("محاذاة لليمين واتجاه عربي (Ctrl+Right)")
        btn_align_right.clicked.connect(lambda: self._set_direction(is_rtl=True))
        self.toolbar.addWidget(btn_align_right)

        btn_align_center = QToolButton()
        btn_align_center.setText("↔️ وسط")
        btn_align_center.setToolTip("محاذاة النص للمنتصف (Ctrl+E)")
        btn_align_center.clicked.connect(lambda: self._set_alignment(Qt.AlignCenter))
        self.toolbar.addWidget(btn_align_center)

        btn_align_left = QToolButton()
        btn_align_left.setText("🌐 LTR إنجليزي")
        btn_align_left.setToolTip("محاذاة لليسار واتجاه إنجليزي (Ctrl+Left)")
        btn_align_left.clicked.connect(lambda: self._set_direction(is_rtl=False))
        self.toolbar.addWidget(btn_align_left)

        self.toolbar.addSeparator()

        # 7. More Font Dialog & Word Wrap
        btn_more_fonts = QToolButton()
        btn_more_fonts.setText("🔤 المزيد...")
        btn_more_fonts.setToolTip("فتح نافذة اختيار الخط المتقدمة لنظام ويندوز")
        btn_more_fonts.clicked.connect(self.choose_font_dialog)
        self.toolbar.addWidget(btn_more_fonts)

        btn_wrap = QToolButton()
        btn_wrap.setText("↩️ التفاف")
        btn_wrap.setToolTip("تبديل التفاف النص (Word Wrap)")
        btn_wrap.clicked.connect(lambda: self.act_word_wrap.trigger())
        self.toolbar.addWidget(btn_wrap)

        self.toolbar.addSeparator()

        # 8. Search & Replace
        btn_find = QToolButton()
        btn_find.setText("🔍 بحث")
        btn_find.setToolTip("بحث في النص (Ctrl+F)")
        btn_find.clicked.connect(lambda: self.find_replace_bar.show_search(show_replace=False))
        self.toolbar.addWidget(btn_find)

        btn_replace = QToolButton()
        btn_replace.setText("⇄ استبدال")
        btn_replace.setToolTip("بحث واستبدال (Ctrl+H)")
        btn_replace.clicked.connect(lambda: self.find_replace_bar.show_search(show_replace=True))
        self.toolbar.addWidget(btn_replace)

        self.toolbar.addSeparator()

        # 9. Integrations
        btn_snip = QToolButton()
        btn_snip.setText("✂️ إلى اختصار")
        btn_snip.setToolTip("تحويل النص المحدد إلى اختصار في SnipGlide")
        btn_snip.clicked.connect(self.convert_selection_to_snippet)
        self.toolbar.addWidget(btn_snip)

        btn_note = QToolButton()
        btn_note.setText("📝 إلى ملاحظة")
        btn_note.setToolTip("حفظ المحتوى في ملاحظات SnipGlide اللاصقة")
        btn_note.clicked.connect(self.save_to_snipglide_notes)
        self.toolbar.addWidget(btn_note)

    # ── Tab Management ──
    def _format_tab_title(self, tab: NotepadTab) -> str:
        # Wrap title in LTR isolate so .txt never flips in mixed Arabic/English text
        safe_title = f"\u2066{tab.title}\u2069"
        if tab.is_archived:
            icon = "📦"
        elif tab.is_favorite:
            icon = "⭐"
        else:
            icon = "📄"
        return f"{icon} {safe_title}"

    def new_tab(
        self,
        file_path: Optional[str] = None,
        title: Optional[str] = None,
        initial_text: str = "",
        folder: Optional[str] = None,
        is_favorite: bool = False,
        is_archived: bool = False
    ) -> NotepadTab:
        if not title:
            count = self.tab_widget.count() + 1
            title = f"مستند {count}.txt"

        if not folder:
            if self.active_filter == "folder" and self.active_folder in self.folders:
                folder = self.active_folder
            else:
                folder = "العامة"

        if self.active_filter == "favorites":
            is_favorite = True

        if self.active_filter == "archive":
            self.active_filter = "all"

        tab = NotepadTab(
            file_path=file_path,
            title=title,
            folder=folder,
            is_favorite=is_favorite,
            is_archived=is_archived,
            parent=self.tab_widget
        )
        editor = tab.editor

        # Apply current settings & font
        editor.set_font_properties(self.active_font)
        editor.toggle_word_wrap(self.act_word_wrap.isChecked())
        editor.set_line_numbers_visible(self.act_show_linenums.isChecked())
        editor.set_current_line_highlight_enabled(self.act_highlight_line.isChecked())
        if getattr(self, "is_current_direction_rtl", False):
            editor.set_text_direction(True)

        if initial_text:
            editor.setPlainText(initial_text)
            editor.is_modified = False

        editor.stats_changed.connect(self._update_status_bar)
        editor.content_modified.connect(lambda: self._on_editor_modified(tab))

        index = self.tab_widget.addTab(tab, self._format_tab_title(tab))
        self.tab_widget.setCurrentIndex(index)
        editor.setFocus()

        self._refresh_folder_bar()
        self._refresh_tab_visibility()
        self._update_status_bar()
        self.session_save_timer.start()
        return tab

    def get_current_editor(self) -> Optional[NotepadEditor]:
        tab = self.tab_widget.currentWidget()
        if isinstance(tab, NotepadTab):
            return tab.editor
        return None

    def get_current_tab(self) -> Optional[NotepadTab]:
        tab = self.tab_widget.currentWidget()
        if isinstance(tab, NotepadTab):
            return tab
        return None

    def _on_tab_switched(self, index: int):
        editor = self.get_current_editor()
        if editor:
            self.find_replace_bar.set_editor(editor)
            self._update_status_bar()
            editor.setFocus()
        self.session_save_timer.start()

    def _on_editor_modified(self, tab: NotepadTab):
        idx = self.tab_widget.indexOf(tab)
        if idx >= 0:
            formatted = self._format_tab_title(tab)
            if self.tab_widget.tabText(idx) != formatted:
                self.tab_widget.setTabText(idx, formatted)
        self.session_save_timer.start()

    def _on_tab_double_clicked(self, index: int):
        if index < 0 or index >= self.tab_widget.count():
            return
        tab = self.tab_widget.widget(index)
        if isinstance(tab, NotepadTab):
            self.rename_tab_dialog(tab)

    def rename_tab_dialog(self, tab: NotepadTab):
        current_name = tab.title
        new_name, ok = QInputDialog.getText(
            self,
            "إعادة تسمية المستند",
            "أدخل الاسم الجديد للمستند:",
            QLineEdit.Normal,
            current_name
        )
        if ok and new_name.strip():
            clean_name = new_name.strip()
            tab.title = clean_name
            self._on_editor_modified(tab)
            self._toast(f"تم تغيير اسم المستند إلى: {clean_name} ✏️", False)
            self.session_save_timer.start()

    def close_tab(self, index: int) -> bool:
        if index < 0 or index >= self.tab_widget.count():
            return False

        tab = self.tab_widget.widget(index)
        if isinstance(tab, NotepadTab) and tab.editor.is_modified:
            doc_name = tab.title
            reply = QMessageBox.question(
                self,
                "حفظ التغييرات",
                f"هل تريد حفظ التغييرات في \"{doc_name}\" قبل الإغلاق؟",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Save:
                saved = self.save_tab(tab)
                if not saved:
                    return False
            elif reply == QMessageBox.Cancel:
                return False

        self.tab_widget.removeTab(index)

        # If all tabs closed, open an empty one
        if self.tab_widget.count() == 0:
            self.new_tab()

        self._refresh_folder_bar()
        self._refresh_tab_visibility()
        self.session_save_timer.start()
        return True

    def close_all_tabs(self):
        while self.tab_widget.count() > 0:
            if not self.close_tab(0):
                break

    def _on_tab_context_menu(self, pos: QPoint):
        tab_idx = self.tab_widget.tabBar().tabAt(pos)
        if tab_idx < 0:
            return
        tab = self.tab_widget.widget(tab_idx)
        if not isinstance(tab, NotepadTab):
            return

        menu = QMenu(self)

        # 1. Favorites toggle
        if tab.is_favorite:
            act_fav = menu.addAction("☆ إزالة من المفضلة")
        else:
            act_fav = menu.addAction("⭐ إضافة إلى المفضلة")

        # 2. Folder Submenu
        folder_menu = menu.addMenu("📁 نقل إلى مجلد...")
        folder_actions = {}
        for fld in self.folders:
            prefix = "✓ " if tab.folder == fld else "  "
            act_f = folder_menu.addAction(f"{prefix}📂 {fld}")
            folder_actions[act_f] = fld
        folder_menu.addSeparator()
        act_new_folder_move = folder_menu.addAction("➕ مجلد جديد...")

        # 3. Archive toggle
        if tab.is_archived:
            act_archive = menu.addAction("📤 استعادة من الأرشيف")
        else:
            act_archive = menu.addAction("📦 نقل إلى الأرشيف")

        # 4. Rename
        act_rename = menu.addAction("✏️ إعادة تسمية المستند...")

        menu.addSeparator()
        act_save = menu.addAction("💾 حفظ")
        act_save_as = menu.addAction("💾 حفظ باسم...")
        menu.addSeparator()
        act_close = menu.addAction("✕ إغلاق التبويب")
        act_close_others = menu.addAction("✕ إغلاق التبويبات الأخرى")
        act_close_right = menu.addAction("✕ إغلاق التبويبات إلى اليمين")
        menu.addSeparator()
        act_copy_path = menu.addAction("📋 نسخ المسار الكامل للملف")
        act_open_dir = menu.addAction("📂 فتح مجلد الملف في المستكشف")

        action = menu.exec(self.tab_widget.tabBar().mapToGlobal(pos))
        if not action:
            return

        if action == act_fav:
            tab.is_favorite = not tab.is_favorite
            self._on_editor_modified(tab)
            self._refresh_folder_bar()
            self._refresh_tab_visibility()
            msg = "تمت إضافة المستند إلى المفضلة ⭐" if tab.is_favorite else "تمت إزالة المستند من المفضلة"
            self._toast(msg, False)
            self.session_save_timer.start()
        elif action in folder_actions:
            target_fld = folder_actions[action]
            tab.folder = target_fld
            self._refresh_folder_bar()
            self._refresh_tab_visibility()
            self._toast(f"تم نقل المستند إلى مجلد '{target_fld}' 📁", False)
            self.session_save_timer.start()
        elif action == act_new_folder_move:
            fld_name, ok = QInputDialog.getText(self, "مجلد جديد", "اسم المجلد الجديد:")
            if ok and fld_name.strip():
                clean_fld = fld_name.strip()
                if clean_fld not in self.folders:
                    self.folders.append(clean_fld)
                tab.folder = clean_fld
                self._refresh_folder_bar()
                self._refresh_tab_visibility()
                self._toast(f"تم إنشاء المجلد ونقل المستند إلى '{clean_fld}' 📁", False)
                self.session_save_timer.start()
        elif action == act_archive:
            tab.is_archived = not tab.is_archived
            self._on_editor_modified(tab)
            self._refresh_folder_bar()
            self._refresh_tab_visibility()
            msg = "تم نقل المستند إلى الأرشيف 📦" if tab.is_archived else "تم استعادة المستند من الأرشيف 📤"
            self._toast(msg, False)
            self.session_save_timer.start()
        elif action == act_rename:
            self.rename_tab_dialog(tab)
        elif action == act_save:
            self.save_tab(tab)
        elif action == act_save_as:
            self.save_as_tab(tab)
        elif action == act_close:
            self.close_tab(tab_idx)
        elif action == act_close_others:
            i = 0
            while i < self.tab_widget.count():
                if self.tab_widget.widget(i) != tab:
                    if not self.close_tab(i):
                        i += 1
                else:
                    i += 1
        elif action == act_close_right:
            while self.tab_widget.count() > tab_idx + 1:
                if not self.close_tab(tab_idx + 1):
                    break
        elif action == act_copy_path:
            if tab.file_path:
                QApplication.clipboard().setText(tab.file_path)
                self._toast("تم نسخ مسار الملف إلى الحافظة! 📋", False)
            else:
                self._toast("الملف غير محفوظ بعد على القرص", True)
        elif action == act_open_dir:
            if tab.file_path and os.path.exists(tab.file_path):
                os.startfile(os.path.dirname(tab.file_path))
            else:
                self._toast("الملف غير محفوظ بعد على القرص", True)

    # ── Folder Bar & Organization Management ──
    def _build_folder_bar_ui(self):
        self.folder_bar_widget = QFrame(self)
        self.folder_bar_widget.setStyleSheet("""
            QFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 10px;
                padding: 4px 6px;
            }
        """)
        self.folder_bar_layout = QHBoxLayout(self.folder_bar_widget)
        self.folder_bar_layout.setContentsMargins(6, 4, 6, 4)
        self.folder_bar_layout.setSpacing(6)

        self.folder_pills_layout = QHBoxLayout()
        self.folder_pills_layout.setSpacing(6)
        self.folder_bar_layout.addLayout(self.folder_pills_layout)

        self.folder_bar_layout.addStretch()

        # Add Folder Button
        btn_add_fld = QPushButton("➕ مجلد جديد")
        btn_add_fld.setToolTip("إنشاء مجلد جديد لتنظيم المستندات والتبويبات")
        btn_add_fld.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #25D366;
                border: 1.5px solid #2a3942;
                border-radius: 7px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #25D366;
                color: #0b141a;
                border-color: #25D366;
            }
        """)
        btn_add_fld.clicked.connect(self.create_new_folder)
        self.folder_bar_layout.addWidget(btn_add_fld)

        self._refresh_folder_bar()

    def _compute_counts(self) -> Dict[str, int]:
        counts = {
            "all": 0,
            "favorites": 0,
            "archive": 0,
        }
        for fld in self.folders:
            counts[fld] = 0

        if hasattr(self, "tab_widget"):
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if isinstance(tab, NotepadTab):
                    if tab.is_archived:
                        counts["archive"] += 1
                    else:
                        counts["all"] += 1
                        if tab.is_favorite:
                            counts["favorites"] += 1
                        fld = tab.folder if tab.folder in counts else "العامة"
                        counts[fld] = counts.get(fld, 0) + 1
        return counts

    def _create_pill_btn(self, text: str, is_active: bool) -> QPushButton:
        btn = QPushButton(text)
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #172554;
                    color: #60a5fa;
                    border: 1.5px solid #3b82f6;
                    border-radius: 7px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1e3a8a;
                    color: #93c5fd;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #182229;
                    color: #94a3b8;
                    border: 1.5px solid #2a3942;
                    border-radius: 7px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #202c33;
                    color: #f0f2f5;
                    border-color: #3b4a54;
                }
            """)
        return btn

    def _refresh_folder_bar(self):
        if not hasattr(self, "folder_pills_layout"):
            return

        while self.folder_pills_layout.count() > 0:
            item = self.folder_pills_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        counts = self._compute_counts()

        # 1. All Files
        btn_all = self._create_pill_btn(
            f"📁 كافة الملفات ({counts['all']})",
            is_active=(self.active_filter == "all")
        )
        btn_all.clicked.connect(lambda: self.set_folder_filter("all", "كافة الملفات"))
        self.folder_pills_layout.addWidget(btn_all)

        # 2. Favorites
        btn_fav = self._create_pill_btn(
            f"⭐ المفضلة ({counts['favorites']})",
            is_active=(self.active_filter == "favorites")
        )
        btn_fav.clicked.connect(lambda: self.set_folder_filter("favorites", ""))
        self.folder_pills_layout.addWidget(btn_fav)

        # 3. Archive
        btn_arch = self._create_pill_btn(
            f"📦 الأرشيف ({counts['archive']})",
            is_active=(self.active_filter == "archive")
        )
        btn_arch.clicked.connect(lambda: self.set_folder_filter("archive", ""))
        self.folder_pills_layout.addWidget(btn_arch)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #2a3942; width: 1px; margin: 2px 4px;")
        self.folder_pills_layout.addWidget(sep)

        # Dynamic Folder pills
        for fld in self.folders:
            is_act = (self.active_filter == "folder" and self.active_folder == fld)
            fld_cnt = counts.get(fld, 0)
            btn_f = self._create_pill_btn(
                f"📂 {fld} ({fld_cnt})",
                is_active=is_act
            )
            btn_f.setContextMenuPolicy(Qt.CustomContextMenu)
            btn_f.customContextMenuRequested.connect(
                lambda pos, name=fld: self._on_folder_pill_context_menu(pos, name)
            )
            btn_f.clicked.connect(
                lambda checked=False, name=fld: self.set_folder_filter("folder", name)
            )
            self.folder_pills_layout.addWidget(btn_f)

    def _on_folder_pill_context_menu(self, pos: QPoint, folder_name: str):
        sender = self.sender()
        if not sender:
            return
        menu = QMenu(self)
        act_rename = menu.addAction("✏️ إعادة تسمية المجلد...")
        act_delete = menu.addAction("🗑️ حذف المجلد...")
        if folder_name == "العامة":
            act_delete.setEnabled(False)

        action = menu.exec(sender.mapToGlobal(pos))
        if action == act_rename:
            self.rename_folder(folder_name)
        elif action == act_delete:
            self.delete_folder(folder_name)

    def create_new_folder(self):
        fld_name, ok = QInputDialog.getText(
            self, "إنشاء مجلد جديد", "اسم المجلد الجديد:",
            QLineEdit.Normal, ""
        )
        if ok and fld_name.strip():
            clean_name = fld_name.strip()
            if clean_name in ["كافة الملفات", "المفضلة", "الأرشيف"]:
                QMessageBox.warning(self, "اسم محجوز", "هذا الاسم محجوز للنظام، يرجى اختيار اسم آخر.")
                return
            if clean_name in self.folders:
                QMessageBox.information(self, "تنبيه", "هذا المجلد موجود بالفعل.")
                self.set_folder_filter("folder", clean_name)
                return
            self.folders.append(clean_name)
            self.set_folder_filter("folder", clean_name)
            self._toast(f"تم إنشاء مجلد جديد: {clean_name} 📂", False)
            self.session_save_timer.start()

    def rename_folder(self, old_name: str):
        if old_name == "العامة":
            QMessageBox.information(self, "تنبيه", "لا يمكن إعادة تسمية المجلد الافتراضي 'العامة'.")
            return
        new_name, ok = QInputDialog.getText(
            self, "إعادة تسمية المجلد", f"الاسم الجديد للمجلد '{old_name}':",
            QLineEdit.Normal, old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            clean_name = new_name.strip()
            if clean_name in self.folders:
                QMessageBox.warning(self, "تنبيه", "يوجد مجلد آخر بهذا الاسم بالفعل.")
                return
            idx = self.folders.index(old_name)
            self.folders[idx] = clean_name
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if isinstance(tab, NotepadTab) and tab.folder == old_name:
                    tab.folder = clean_name
            if self.active_folder == old_name:
                self.active_folder = clean_name
            self._refresh_folder_bar()
            self._refresh_tab_visibility()
            self._toast(f"تمت إعادة تسمية المجلد إلى: {clean_name} ✏️", False)
            self.session_save_timer.start()

    def delete_folder(self, folder_name: str):
        if folder_name == "العامة":
            QMessageBox.information(self, "تنبيه", "لا يمكن حذف مجلد 'العامة' لأنه المجلد الافتراضي للنظام.")
            return
        reply = QMessageBox.question(
            self,
            "حذف المجلد",
            f"هل أنت متأكد من حذف المجلد '{folder_name}'؟\nسيتم نقل كافة المستندات داخله تلقائياً إلى مجلد 'العامة'.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if folder_name in self.folders:
                self.folders.remove(folder_name)
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if isinstance(tab, NotepadTab) and tab.folder == folder_name:
                    tab.folder = "العامة"
            if self.active_folder == folder_name:
                self.active_folder = "العامة"
            self._refresh_folder_bar()
            self._refresh_tab_visibility()
            self._toast(f"تم حذف مجلد '{folder_name}' ونقل ملفاته إلى 'العامة' 🗑️", False)
            self.session_save_timer.start()

    def set_folder_filter(self, filter_type: str, folder_name: str = ""):
        self.active_filter = filter_type
        self.active_folder = folder_name
        self._refresh_tab_visibility()
        self._refresh_folder_bar()
        self.session_save_timer.start()

    def _refresh_tab_visibility(self):
        visible_indices = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if not isinstance(tab, NotepadTab):
                continue

            is_vis = False
            if self.active_filter == "all":
                is_vis = not tab.is_archived
            elif self.active_filter == "favorites":
                is_vis = tab.is_favorite and not tab.is_archived
            elif self.active_filter == "archive":
                is_vis = tab.is_archived
            elif self.active_filter == "folder":
                is_vis = (tab.folder == self.active_folder) and not tab.is_archived

            self.tab_widget.setTabVisible(i, is_vis)
            if is_vis:
                visible_indices.append(i)

        if not visible_indices:
            if self.active_filter == "folder" and self.active_folder in self.folders:
                self.new_tab(folder=self.active_folder)
                return
            elif self.active_filter == "favorites":
                self._toast("لا توجد ملفات في المفضلة حالياً ⭐ (انقر بزر الفأرة الأيمن على أي تبويب لإضافته)", False)
                self.set_folder_filter("all", "كافة الملفات")
                return
            elif self.active_filter == "archive":
                self._toast("الأرشيف فارغ حالياً 📦", False)
                self.set_folder_filter("all", "كافة الملفات")
                return

        curr_idx = self.tab_widget.currentIndex()
        if curr_idx not in visible_indices and visible_indices:
            self.tab_widget.setCurrentIndex(visible_indices[0])

    # ── Fullscreen Focus Mode ──
    def toggle_focus_mode(self):
        if self._is_focus_mode:
            self.exit_focus_mode()
        else:
            self.enter_focus_mode()

    def enter_focus_mode(self):
        main_win = self.window()
        self._saved_geometry = main_win.saveGeometry()
        self._saved_maximized = main_win.isMaximized()
        self._is_focus_mode = True

        # Hide main window sidebar if present
        if hasattr(main_win, "sidebar"):
            main_win.sidebar.hide()

        # Hide distracting toolbars & headers
        if hasattr(self, "header_card"):
            self.header_card.hide()
        if hasattr(self, "menu_bar"):
            self.menu_bar.hide()
        if hasattr(self, "toolbar"):
            self.toolbar.hide()
        if hasattr(self, "folder_bar_widget"):
            self.folder_bar_widget.hide()
        if hasattr(self, "status_bar_widget"):
            self.status_bar_widget.hide()

        # Maximize editor area
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        main_win.showFullScreen()

        self.focus_exit_pill.show()
        self.focus_exit_pill.raise_()
        pw = self.focus_exit_pill.sizeHint().width() + 40
        ph = 38
        px = (self.width() - pw) // 2
        self.focus_exit_pill.setGeometry(px, 12, pw, ph)

        editor = self.get_current_editor()
        if editor:
            editor.setFocus()

        self._toast("تم تفعيل وضع التركيز بكامل الشاشة ⛶ (اضغط Esc أو F11 للخروج)", False)

    def exit_focus_mode(self):
        if not self._is_focus_mode:
            return
        self._is_focus_mode = False

        self.focus_exit_pill.hide()

        # Restore headers & toolbars
        if hasattr(self, "header_card"):
            self.header_card.show()
        if hasattr(self, "menu_bar"):
            self.menu_bar.show()
        if hasattr(self, "toolbar"):
            self.toolbar.show()
        if hasattr(self, "folder_bar_widget"):
            self.folder_bar_widget.show()
        if hasattr(self, "status_bar_widget") and self.act_show_status.isChecked():
            self.status_bar_widget.show()

        # Restore margins
        self.layout().setContentsMargins(18, 14, 18, 14)
        self.layout().setSpacing(10)

        # Restore sidebar & window geometry
        main_win = self.window()
        if hasattr(main_win, "sidebar"):
            main_win.sidebar.show()

        if self._saved_maximized:
            main_win.showMaximized()
        else:
            main_win.showNormal()
            if self._saved_geometry:
                main_win.restoreGeometry(self._saved_geometry)

        editor = self.get_current_editor()
        if editor:
            editor.setFocus()

        self._toast("تم الخروج من وضع التركيز واستعادة الحجم الأصلي ↩️", False)

    def _on_esc_pressed(self):
        if self._is_focus_mode:
            self.exit_focus_mode()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'focus_exit_pill') and self.focus_exit_pill.isVisible():
            pw = self.focus_exit_pill.sizeHint().width() + 40
            ph = 38
            px = (self.width() - pw) // 2
            self.focus_exit_pill.setGeometry(px, 12, pw, ph)

    # ── File I/O Operations ──
    def open_file(self, target_path: Optional[str] = None):
        if not target_path:
            target_path, _ = QFileDialog.getOpenFileName(
                self, "فتح مستند نصي", "",
                "كافة الملفات النصية (*.txt *.py *.md *.json *.html *.xml *.csv *.log *.sql *.ini *.env);;جميع الملفات (*.*)"
            )
        if not target_path or not os.path.exists(target_path):
            return

        # Check if already opened in a tab
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab) and tab.file_path == target_path:
                self.tab_widget.setCurrentIndex(i)
                return

        # Read content with encoding fallback
        content = ""
        encoding_used = "UTF-8"
        for enc in ["utf-8-sig", "utf-8", "cp1256", "latin-1", "utf-16"]:
            try:
                with open(target_path, "r", encoding=enc) as f:
                    content = f.read()
                    encoding_used = enc.upper()
                    break
            except Exception:
                continue

        # Detect line endings
        line_ending = "CRLF" if "\r\n" in content else "LF"

        filename = os.path.basename(target_path)
        tab = self.new_tab(file_path=target_path, title=filename, initial_text=content)
        tab.editor.encoding = encoding_used
        tab.editor.line_ending = line_ending
        tab.editor.is_modified = False
        self._on_editor_modified(tab)

        add_recent_file(target_path)
        self._update_recent_files_menu()
        self._toast(f"تم فتح الملف بنجاح: {filename} 📂", False)

    def save_current_tab(self) -> bool:
        tab = self.get_current_tab()
        if tab:
            return self.save_tab(tab)
        return False

    def save_tab(self, tab: NotepadTab) -> bool:
        if not tab.file_path:
            return self.save_as_tab(tab)

        try:
            content = tab.editor.toPlainText()
            # Normalize line endings
            if tab.editor.line_ending == "CRLF":
                content = content.replace("\r\n", "\n").replace("\n", "\r\n")
            else:
                content = content.replace("\r\n", "\n")

            with open(tab.file_path, "w", encoding=tab.editor.encoding.lower()) as f:
                f.write(content)

            tab.editor.is_modified = False
            self._on_editor_modified(tab)
            add_recent_file(tab.file_path)
            self._update_recent_files_menu()
            self._toast(f"تم حفظ الملف بنجاح: {tab.title} 💾", False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "خطأ في الحفظ", f"تعذر حفظ الملف: {str(e)}")
            return False

    def save_as_current_tab(self) -> bool:
        tab = self.get_current_tab()
        if tab:
            return self.save_as_tab(tab)
        return False

    def save_as_tab(self, tab: NotepadTab) -> bool:
        default_name = tab.title if tab.title else "مستند.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "حفظ المستند باسم", default_name,
            "ملف نصي (*.txt);;ملف بايثون (*.py);;ملف ماركداون (*.md);;ملف جيسون (*.json);;جميع الملفات (*.*)"
        )
        if not file_path:
            return False

        tab.file_path = file_path
        tab.title = os.path.basename(file_path)
        return self.save_tab(tab)

    def save_all_tabs(self):
        saved_count = 0
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab) and tab.editor.is_modified:
                if self.save_tab(tab):
                    saved_count += 1
        self._toast(f"تم حفظ {saved_count} تبويبات معدلة بنجاح! 💾", False)

    def _update_recent_files_menu(self):
        self.recent_menu.clear()
        files = get_recent_files()
        if not files:
            act_none = self.recent_menu.addAction("لا توجد ملفات أخيرة")
            act_none.setEnabled(False)
            return

        for path in files:
            act = self.recent_menu.addAction(f"📄 {os.path.basename(path)}")
            act.setToolTip(path)
            act.triggered.connect(lambda _, p=path: self.open_file(p))

        self.recent_menu.addSeparator()
        act_clear = self.recent_menu.addAction("🗑️ مسح قائمة الملفات الأخيرة")
        act_clear.triggered.connect(self._clear_recent)

    def _clear_recent(self):
        clear_recent_files()
        self._update_recent_files_menu()
        self._toast("تم مسح سجل الملفات الأخيرة", False)

    def print_or_export_pdf(self):
        editor = self.get_current_editor()
        if not editor:
            return

        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("طباعة / تصدير المستند")
        if dialog.exec() == QPrintDialog.Accepted:
            editor.print_(printer)
            self._toast("تمت الطباعة بنجاح! 🖨️", False)

    # ── Edit & Formatting Helper Actions ──
    def _call_editor(self, method_name: str):
        editor = self.get_current_editor()
        if editor and hasattr(editor, method_name):
            getattr(editor, method_name)()

    def _delete_selected(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()

    def _insert_time_date(self):
        editor = self.get_current_editor()
        if editor:
            now_str = datetime.now().strftime("%I:%M %p %m/%d/%Y")
            editor.insertPlainText(now_str)

    def _transform_to_upper(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                transformed = cursor.selectedText().replace('\u2029', '\n').upper()
                cursor.insertText(transformed)
                cursor.setPosition(start)
                cursor.setPosition(start + len(transformed), QTextCursor.KeepAnchor)
                editor.setTextCursor(cursor)
            else:
                editor.setPlainText(editor.toPlainText().upper())

    def _transform_to_lower(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                transformed = cursor.selectedText().replace('\u2029', '\n').lower()
                cursor.insertText(transformed)
                cursor.setPosition(start)
                cursor.setPosition(start + len(transformed), QTextCursor.KeepAnchor)
                editor.setTextCursor(cursor)
            else:
                editor.setPlainText(editor.toPlainText().lower())

    def _transform_to_title(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                transformed = cursor.selectedText().replace('\u2029', '\n').title()
                cursor.insertText(transformed)
                cursor.setPosition(start)
                cursor.setPosition(start + len(transformed), QTextCursor.KeepAnchor)
                editor.setTextCursor(cursor)
            else:
                editor.setPlainText(editor.toPlainText().title())

    def _transform_toggle_case(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                transformed = cursor.selectedText().replace('\u2029', '\n').swapcase()
                cursor.insertText(transformed)
                cursor.setPosition(start)
                cursor.setPosition(start + len(transformed), QTextCursor.KeepAnchor)
                editor.setTextCursor(cursor)
            else:
                editor.setPlainText(editor.toPlainText().swapcase())
            self._toast("تم عكس حالة الأحرف! 🔀", False)

    def _duplicate_current_line(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()
            cursor.movePosition(QTextCursor.EndOfBlock)
            cursor.insertText("\n" + line_text)
            self._toast("تم تكرار السطر! 📑", False)

    def _delete_current_line(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            if not cursor.atEnd():
                cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self._toast("تم حذف السطر! 🗑️", False)

    def _sort_lines_asc(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            text = cursor.selectedText() if cursor.hasSelection() else editor.toPlainText()
            lines = text.split("\u2029" if cursor.hasSelection() else "\n")
            lines.sort()
            sorted_text = "\n".join(lines)
            if cursor.hasSelection():
                cursor.insertText(sorted_text)
            else:
                editor.setPlainText(sorted_text)
            self._toast("تم ترتيب الأسطر تصاعدياً! 🔀", False)

    def _sort_lines_desc(self):
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            text = cursor.selectedText() if cursor.hasSelection() else editor.toPlainText()
            lines = text.split("\u2029" if cursor.hasSelection() else "\n")
            lines.sort(reverse=True)
            sorted_text = "\n".join(lines)
            if cursor.hasSelection():
                cursor.insertText(sorted_text)
            else:
                editor.setPlainText(sorted_text)
            self._toast("تم ترتيب الأسطر تنازلياً! 🔀", False)

    def _remove_empty_lines(self):
        editor = self.get_current_editor()
        if editor:
            text = editor.toPlainText()
            filtered = "\n".join([line for line in text.splitlines() if line.strip()])
            editor.setPlainText(filtered)
            self._toast("تم حذف الأسطر الفارغة! 🧹", False)

    def _trim_whitespace(self):
        editor = self.get_current_editor()
        if editor:
            text = editor.toPlainText()
            trimmed = "\n".join([line.strip() for line in text.splitlines()])
            editor.setPlainText(trimmed)
            self._toast("تمت إزالة الفراغات الزائدة من البداية والنهاية! ✂️", False)

    def _number_lines(self):
        editor = self.get_current_editor()
        if editor:
            text = editor.toPlainText()
            lines = text.splitlines()
            numbered = "\n".join([f"{i+1}. {line}" for i, line in enumerate(lines)])
            editor.setPlainText(numbered)
            self._toast("تم ترقيم الأسطر بنجاح! 🔢", False)

    def go_to_line_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        total_lines = editor.blockCount()
        line_num, ok = QInputDialog.getInt(
            self, "الانتقال إلى سطر", f"أدخل رقم السطر (1 - {total_lines}):",
            editor.textCursor().blockNumber() + 1, 1, total_lines
        )
        if ok:
            block = editor.document().findBlockByLineNumber(line_num - 1)
            cursor = editor.textCursor()
            cursor.setPosition(block.position())
            editor.setTextCursor(cursor)
            editor.centerCursor()

    # ── Font & Text Formatting Handlers ──
    def apply_font_to_all_tabs(self, font: QFont):
        pt = font.pointSize()
        px = font.pixelSize()
        size = pt if pt > 0 else (px if px > 0 else 14)
        if size <= 0:
            size = 14

        self.active_font = QFont(font)
        self.active_font.setPointSize(size)

        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tab.editor.set_font_properties(self.active_font)

        self._sync_toolbar_font_controls()
        self.session_save_timer.start()

    def _sync_toolbar_font_controls(self):
        if hasattr(self, "font_combo") and self.font_combo:
            self.font_combo.blockSignals(True)
            fam = self.active_font.family()
            idx = self.font_combo.findText(fam, Qt.MatchContains)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
            else:
                self.font_combo.setEditText(fam)
            self.font_combo.blockSignals(False)

        if hasattr(self, "size_combo") and self.size_combo:
            self.size_combo.blockSignals(True)
            sz_str = str(self.active_font.pointSize())
            idx_sz = self.size_combo.findText(sz_str)
            if idx_sz >= 0:
                self.size_combo.setCurrentIndex(idx_sz)
            else:
                self.size_combo.setEditText(sz_str)
            self.size_combo.blockSignals(False)

        if hasattr(self, "btn_bold") and self.btn_bold:
            self.btn_bold.blockSignals(True)
            self.btn_bold.setChecked(self.active_font.bold())
            self.btn_bold.blockSignals(False)

        if hasattr(self, "btn_italic") and self.btn_italic:
            self.btn_italic.blockSignals(True)
            self.btn_italic.setChecked(self.active_font.italic())
            self.btn_italic.blockSignals(False)

        if hasattr(self, "btn_underline") and self.btn_underline:
            self.btn_underline.blockSignals(True)
            self.btn_underline.setChecked(self.active_font.underline())
            self.btn_underline.blockSignals(False)

        if hasattr(self, "act_bold"):
            self.act_bold.setChecked(self.active_font.bold())
        if hasattr(self, "act_italic"):
            self.act_italic.setChecked(self.active_font.italic())
        if hasattr(self, "act_underline"):
            self.act_underline.setChecked(self.active_font.underline())

    def _on_font_family_selected(self, family: str):
        if not family or not family.strip():
            return
        f = QFont(self.active_font)
        f.setFamily(family.strip())
        self.apply_font_to_all_tabs(f)
        self._toast(f"تم تغيير الخط إلى: {family.strip()} 🔤", False)

    def _on_font_size_selected(self, size_text: str):
        try:
            digits = re.sub(r'[^\d]', '', str(size_text))
            if digits:
                sz = int(digits)
                if 6 <= sz <= 120:
                    f = QFont(self.active_font)
                    f.setPointSize(sz)
                    self.apply_font_to_all_tabs(f)
                    self._toast(f"تم تغيير حجم الخط إلى: {sz}pt 📏", False)
        except Exception:
            pass

    def _quick_font_increase(self):
        cur_sz = self.active_font.pointSize()
        new_sz = min(72, cur_sz + 2)
        f = QFont(self.active_font)
        f.setPointSize(new_sz)
        self.apply_font_to_all_tabs(f)
        self._toast(f"حجم الخط: {new_sz}pt ➕", False)

    def _quick_font_decrease(self):
        cur_sz = self.active_font.pointSize()
        new_sz = max(6, cur_sz - 2)
        f = QFont(self.active_font)
        f.setPointSize(new_sz)
        self.apply_font_to_all_tabs(f)
        self._toast(f"حجم الخط: {new_sz}pt ➖", False)

    def _quick_font_reset(self):
        f = QFont(self.active_font)
        f.setPointSize(14)
        self.apply_font_to_all_tabs(f)
        self._toast("تمت استعادة حجم الخط الافتراضي (14pt) 🔄", False)

    def _quick_toggle_bold(self):
        f = QFont(self.active_font)
        f.setBold(not f.bold())
        self.apply_font_to_all_tabs(f)
        self._toast("تم تفعيل الخط العريض (Bold) <b>B</b>" if f.bold() else "تم إلغاء الخط العريض", False)

    def _quick_toggle_italic(self):
        f = QFont(self.active_font)
        f.setItalic(not f.italic())
        self.apply_font_to_all_tabs(f)
        self._toast("تم تفعيل الخط المائل (Italic) <i>I</i>" if f.italic() else "تم إلغاء الخط المائل", False)

    def _quick_toggle_underline(self):
        f = QFont(self.active_font)
        f.setUnderline(not f.underline())
        self.apply_font_to_all_tabs(f)
        self._toast("تم تفعيل تسطير النص (Underline) <u>U</u>" if f.underline() else "تم إلغاء التسطير", False)

    def choose_font_dialog(self):
        cur_font = QFont(self.active_font)
        dlg = QFontDialog(cur_font, self)
        dlg.setWindowTitle("اختيار خط وحجم خط المفكرة")
        if dlg.exec():
            selected_font = dlg.selectedFont()
            self.apply_font_to_all_tabs(selected_font)
            self._toast(f"تم تغيير الخط إلى: {selected_font.family()} بحجم {selected_font.pointSize()}", False)

    def _on_toggle_word_wrap(self, checked: bool):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tab.editor.toggle_word_wrap(checked)
        self.session_save_timer.start()
        self._toast("تم تفعيل التفاف النص (Word Wrap)" if checked else "تم إلغاء التفاف النص", False)

    def _on_toggle_line_numbers(self, checked: bool):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tab.editor.set_line_numbers_visible(checked)
        self.session_save_timer.start()

    def _on_toggle_highlight_line(self, checked: bool):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tab.editor.set_current_line_highlight_enabled(checked)
        self.session_save_timer.start()

    def _set_direction(self, is_rtl: bool):
        self.is_current_direction_rtl = is_rtl
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tab.editor.set_text_direction(is_rtl)
        self.lbl_direction.setText("🔤 RTL عربي" if is_rtl else "🔤 LTR إنجليزي")
        self.session_save_timer.start()
        self._toast("تم تعيين الاتجاه: من اليمين لليسار (RTL - عربي) 🇸🇦" if is_rtl else "تم تعيين الاتجاه: من اليسار لليمين (LTR - إنجليزي) 🌐", False)

    def _set_alignment(self, align: Qt.AlignmentFlag):
        editor = self.get_current_editor()
        if editor:
            editor.set_text_alignment(align)
            self._toast("تم ضبط محاذاة النص! ↔️", False)

    def _toggle_line_ending(self, event):
        editor = self.get_current_editor()
        if not editor:
            return
        if editor.line_ending == "CRLF":
            editor.line_ending = "LF"
            self.lbl_ending.setText("Unix (LF)")
            self._toast("تم تغيير نهاية الأسطر إلى Unix (LF)", False)
        else:
            editor.line_ending = "CRLF"
            self.lbl_ending.setText("Windows (CRLF)")
            self._toast("تم تغيير نهاية الأسطر إلى Windows (CRLF)", False)

    # ── Status Bar Updates ──
    def _update_status_bar(self):
        editor = self.get_current_editor()
        if not editor:
            return
        stats = editor.get_stats()
        self.lbl_pos.setText(f"📍 السطر {stats['line']}، العمود {stats['col']}")
        if stats['selected_chars'] > 0:
            self.lbl_selection.setText(f"✂️ ({stats['selected_chars']} محدد)")
            self.lbl_selection.show()
        else:
            self.lbl_selection.hide()

        self.lbl_counts.setText(f"📊 {stats['words']} كلمات | {stats['chars']} أحرف | {stats['lines']} أسطر")
        zoom_pct = 100 + stats['zoom_factor'] * 10
        self.lbl_zoom.setText(f"🔍 {zoom_pct}%")
        self.lbl_ending.setText(f"⚡ Windows ({stats['line_ending']})" if stats['line_ending'] == "CRLF" else "⚡ Unix (LF)")
        self.lbl_encoding.setText(f"🌐 {stats['encoding']}")
        is_rtl = editor.layoutDirection() == Qt.RightToLeft
        self.lbl_direction.setText("🔤 RTL عربي" if is_rtl else "🔤 LTR إنجليزي")

    # ── SnipGlide Integrations ──
    def convert_selection_to_snippet(self):
        editor = self.get_current_editor()
        if not editor:
            return
        text = editor.textCursor().selectedText().replace('\u2029', '\n')
        if not text:
            text = editor.toPlainText()
        if not text:
            self._toast("لا يوجد نص لتحويله إلى اختصار!", True)
            return

        main_win = self.window()
        if hasattr(main_win, "sidebar") and hasattr(main_win, "snippets_page"):
            main_win.sidebar.select_page("Snippets")
            main_win.snippets_page.new_snippet(initial_content=text)
            self._toast("تم فتح محرر الاختصارات مع النص المحدد! ✂️", False)
        else:
            QApplication.clipboard().setText(text)
            self._toast("تم نسخ النص للحافظة كاختصار! ✂️", False)

    def save_to_snipglide_notes(self):
        editor = self.get_current_editor()
        if not editor:
            return
        tab = self.get_current_tab()
        title = tab.title if tab else "ملاحظة من المفكرة"
        content = editor.toPlainText()
        if not content.strip():
            self._toast("المستند فارغ، لا يوجد محتوى للحفظ!", True)
            return

        try:
            note = Note(
                id=None,
                title=title,
                content=content,
                color="#0ea5e9"
            )
            add_note(note)
            self._toast("تم حفظ المحتوى في ملاحظات SnipGlide اللاصقة بنجاح! 📝", False)
        except Exception as e:
            self._toast(f"حدث خطأ أثناء الحفظ: {str(e)}", True)

    def send_to_chat_notes(self):
        editor = self.get_current_editor()
        if not editor:
            return
        text = editor.textCursor().selectedText().replace('\u2029', '\n')
        if not text:
            text = editor.toPlainText()
        if not text.strip():
            self._toast("لا يوجد نص لإرساله لشات نوت!", True)
            return

        try:
            add_chat_note(content=text, color="#25D366")
            self._toast("تم إرسال النص إلى شات نوت الواتساب بنجاح! 💬", False)
        except Exception as e:
            self._toast(f"خطأ أثناء الإرسال: {str(e)}", True)

    def show_text_stats_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        stats = editor.get_stats()
        text = editor.toPlainText()
        chars_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
        paragraphs = len([p for p in text.split("\n") if p.strip()])
        bytes_size = len(text.encode(editor.encoding.lower()))

        dialog = QDialog(self)
        dialog.setWindowTitle("إحصائيات النص التفصيلية")
        dialog.resize(360, 260)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #111b21;
                color: #f0f2f5;
            }
            QLabel {
                font-size: 13px;
                color: #f0f2f5;
            }
        """)
        layout = QVBoxLayout(dialog)

        grid = QGridLayout()
        grid.setSpacing(10)
        items = [
            ("إجمالي الكلمات:", f"{stats['words']:,}"),
            ("إجمالي الأحرف (مع المسافات):", f"{stats['chars']:,}"),
            ("الأحرف بدون مسافات:", f"{chars_no_spaces:,}"),
            ("عدد الأسطر الكلي:", f"{stats['lines']:,}"),
            ("الفقرات غير الفارغة:", f"{paragraphs:,}"),
            ("ترميز الملف:", stats['encoding']),
            ("حجم الملف التقديري:", f"{bytes_size:,} بايت"),
        ]
        for row, (k, v) in enumerate(items):
            lbl_k = QLabel(k)
            lbl_k.setStyleSheet("color: #94a3b8; font-weight: bold;")
            lbl_v = QLabel(v)
            lbl_v.setStyleSheet("color: #25D366; font-weight: bold;")
            grid.addWidget(lbl_k, row, 0)
            grid.addWidget(lbl_v, row, 1)

        layout.addLayout(grid)
        layout.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        dialog.exec()

    # ── Session State Persistence (Save & Restore) ──
    def _save_session_state(self):
        tabs_data = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, NotepadTab):
                tabs_data.append({
                    "file_path": tab.file_path,
                    "title": tab.title,
                    "content": tab.editor.toPlainText(),
                    "is_modified": tab.editor.is_modified,
                    "cursor_pos": tab.editor.textCursor().position(),
                    "encoding": tab.editor.encoding,
                    "line_ending": tab.editor.line_ending,
                    "direction": "rtl" if tab.editor.layoutDirection() == Qt.RightToLeft else "ltr",
                    "folder": tab.folder,
                    "is_favorite": tab.is_favorite,
                    "is_archived": tab.is_archived,
                })

        editor = self.get_current_editor()
        font_fam = editor.font().family() if editor else "Consolas"
        font_sz = editor.base_font_size if editor else 14

        session_data = {
            "tabs": tabs_data,
            "active_index": self.tab_widget.currentIndex(),
            "folders": self.folders,
            "active_folder": self.active_folder,
            "active_filter": self.active_filter,
            "settings": {
                "word_wrap": self.act_word_wrap.isChecked(),
                "line_numbers": self.act_show_linenums.isChecked(),
                "status_bar": self.act_show_status.isChecked(),
                "highlight_current_line": self.act_highlight_line.isChecked(),
                "font_family": self.active_font.family(),
                "font_size": self.active_font.pointSize(),
                "bold": self.active_font.bold(),
                "italic": self.active_font.italic(),
                "underline": self.active_font.underline(),
                "direction": "rtl" if self.is_current_direction_rtl else "ltr",
            }
        }
        save_notepad_session(session_data)

    def _load_session_or_default(self):
        session = load_notepad_session()
        settings = session.get("settings", DEFAULT_NOTEPAD_SETTINGS)

        # Organization state restore
        self.folders = session.get("folders", ["العامة", "العمل", "شخصي"])
        if not isinstance(self.folders, list) or not self.folders:
            self.folders = ["العامة", "العمل", "شخصي"]
        if "العامة" not in self.folders:
            self.folders.insert(0, "العامة")

        self.active_folder = session.get("active_folder", "كافة الملفات")
        self.active_filter = session.get("active_filter", "all")

        # Apply settings
        self.act_word_wrap.setChecked(settings.get("word_wrap", True))
        self.act_show_linenums.setChecked(settings.get("line_numbers", True))
        self.act_show_status.setChecked(settings.get("status_bar", True))
        self.status_bar_widget.setVisible(settings.get("status_bar", True))
        self.act_highlight_line.setChecked(settings.get("highlight_current_line", True))

        # Restore font & formatting preferences
        font_fam = settings.get("font_family", "Consolas")
        font_sz = settings.get("font_size", 14)
        if not isinstance(font_sz, int) or font_sz <= 0:
            font_sz = 14
        self.active_font = QFont(font_fam, font_sz)
        if settings.get("bold", False):
            self.active_font.setBold(True)
        if settings.get("italic", False):
            self.active_font.setItalic(True)
        if settings.get("underline", False):
            self.active_font.setUnderline(True)

        is_rtl = settings.get("direction") == "rtl"
        self.is_current_direction_rtl = is_rtl

        saved_tabs = session.get("tabs", [])
        if saved_tabs:
            for t_data in saved_tabs:
                fp = t_data.get("file_path")
                title = t_data.get("title", "مستند جديد")
                content = t_data.get("content", "")
                fld = t_data.get("folder", "العامة")
                is_fav = t_data.get("is_favorite", False)
                is_arch = t_data.get("is_archived", False)

                # If file exists on disk, reload fresh content if not modified
                if fp and os.path.exists(fp) and not t_data.get("is_modified", False):
                    try:
                        with open(fp, "r", encoding=t_data.get("encoding", "utf-8").lower()) as f:
                            content = f.read()
                    except Exception:
                        pass

                tab = self.new_tab(
                    file_path=fp,
                    title=title,
                    initial_text=content,
                    folder=fld,
                    is_favorite=is_fav,
                    is_archived=is_arch
                )
                tab.editor.is_modified = t_data.get("is_modified", False)
                tab.editor.encoding = t_data.get("encoding", "UTF-8")
                tab.editor.line_ending = t_data.get("line_ending", "CRLF")

                # Restore cursor position
                pos = t_data.get("cursor_pos", 0)
                cursor = tab.editor.textCursor()
                cursor.setPosition(min(pos, len(tab.editor.toPlainText())))
                tab.editor.setTextCursor(cursor)

                if t_data.get("direction") == "rtl":
                    tab.editor.set_text_direction(is_rtl=True)

                self._on_editor_modified(tab)

            active_idx = session.get("active_index", 0)
            if 0 <= active_idx < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(active_idx)
        else:
            # First launch: open a helpful starter tab
            welcome_text = (
                "# مرحباً بك في مفكرة ويندوز (Windows Notepad) المتطورة في SnipGlide!\n\n"
                "تم تصميم هذا القسم ليمنحك تجربة تحرير النصوص الأسرع والأكثر راحة، مع كافة مميزات نوت باد ويندوز الحديثة:\n\n"
                "✨ التبويبات المتعددة (Multi-Tabs): أنشئ عدة ملفات وتنقل بينها بسلاسة عبر زر (+).\n"
                "📁 تنظيم المجلدات: أنشئ مجلدات لمجموعات ملفاتك وتنقل بينها بضغطة زر واحدة.\n"
                "⭐ المفضلة والأرشيف: ميز ملاحظاتك الهامة بنجمة وأرشف الملفات المنتهية بكل سهولة.\n"
                "⛶ وضع التركيز بكامل الشاشة: استمتع بكتابة خالية من أي مشتتات بزر F11 واستعد حجمك بـ Esc.\n"
                "✏️ إعادة التسمية السريعة: انقر مرتين على أي تبويب لإعادة تسميته فوراً.\n"
                "💾 استعادة الجلسة التلقائية: مسوداتك وتبويباتك تحفظ تلقائياً ولن تفقد أي عمل عند إغلاق البرنامج!\n"
                "🔍 شريط البحث والاستبدال المدمج (Ctrl+F و Ctrl+H) مع دعم التعبيرات النمطية و Aa.\n"
                "⏰ إدراج الوقت والتاريخ عبر زر F5 كويندوز تماماً.\n"
                "🌐 دعم فوري للغتين العربية والإنجليزية (RTL / LTR).\n"
                "⚡ التكامل المباشر: تحويل أي نص إلى اختصار أو ملاحظة لاصقة بنقرة واحدة!\n\n"
                "ابدأ الكتابة الآن أو افتح ملفاتك النصية المفضلة..."
            )
            self.new_tab(title="ملاحظة ترحيبية.txt", initial_text=welcome_text)

        # Apply saved font to all tabs and sync toolbar controls
        self.apply_font_to_all_tabs(self.active_font)
        if self.is_current_direction_rtl:
            self._set_direction(is_rtl=True)

        self._refresh_folder_bar()
        self._refresh_tab_visibility()

    def _toast(self, message: str, error: bool = False):
        if self.toast_callback:
            self.toast_callback(message, error)
