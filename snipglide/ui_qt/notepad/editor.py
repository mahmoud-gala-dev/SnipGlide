import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer, QRegularExpression, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QTextFormat, QTextCursor, QFont, QKeySequence,
    QShortcut, QAction, QIcon, QTextDocument, QCursor, QTextCharFormat,
    QTextOption, QTextBlockFormat, QFontDatabase, QPixmap, QPainterPath, QPen
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit, QTabWidget,
    QTabBar, QLabel, QPushButton, QToolButton, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QInputDialog, QFontDialog, QMenu,
    QApplication, QFrame, QDialog, QDialogButtonBox, QGridLayout,
    QMenuBar, QToolBar, QSizePolicy, QComboBox, QFontComboBox
)
from snipglide.core.config import get_arabic_font_family
from snipglide.database.note_repo import add_note
from snipglide.database.chat_note_repo import add_chat_note
from snipglide.models.note import Note
from snipglide.services.notepad_session import add_recent_file
from snipglide.ui_qt.notepad.icons import create_vector_icon

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

    def _find_notepad_page(self) -> Optional[Any]:
        """Find the enclosing NotepadPageQt instance."""
        p = getattr(self, "page", None)
        if p:
            return p
        p = self.parent()
        while p:
            if p.__class__.__name__ == "NotepadPageQt" or hasattr(p, "_is_focus_mode"):
                return p
            p = p.parent()
        return None

    # ── Key Event Handling & Indentation ──
    def keyPressEvent(self, event):
        # Esc or F11 -> Immediately exit Focus Mode if active
        if event.key() in (Qt.Key_Escape, Qt.Key_F11):
            page = self._find_notepad_page()
            if page and getattr(page, "_is_focus_mode", False):
                page.exit_focus_mode()
                event.accept()
                return

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

    def select_current_line(self):
        """Select the full line under the cursor."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

    def duplicate_current_line(self):
        """Duplicate the current line or selection."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.insertText("\n" + line_text)
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم تكرار السطر! 📑", False)

    def delete_current_line(self):
        """Delete the current line entirely."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        if not cursor.atEnd():
            cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم حذف السطر! 🗑️", False)

    def transform_case(self, mode: str):
        """Transform text case for selection or entire document."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            txt = cursor.selectedText().replace('\u2029', '\n')
            if mode == "upper":
                txt = txt.upper()
            elif mode == "lower":
                txt = txt.lower()
            elif mode == "title":
                txt = txt.title()
            elif mode in ("toggle", "swap"):
                txt = txt.swapcase()
            cursor.insertText(txt)
            cursor.setPosition(start)
            cursor.setPosition(start + len(txt), QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            txt = self.toPlainText()
            if mode == "upper":
                txt = txt.upper()
            elif mode == "lower":
                txt = txt.lower()
            elif mode == "title":
                txt = txt.title()
            elif mode in ("toggle", "swap"):
                txt = txt.swapcase()
            self.setPlainText(txt)
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم تحويل حالة الأحرف! 🔠", False)

    def sort_lines(self, ascending: bool = True):
        """Sort lines alphabetically ascending or descending."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            txt = cursor.selectedText()
            lines = txt.split("\u2029")
            lines.sort(reverse=not ascending)
            cursor.insertText("\n".join(lines))
        else:
            txt = self.toPlainText()
            lines = txt.splitlines()
            lines.sort(reverse=not ascending)
            self.setPlainText("\n".join(lines))
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم فرز وترتيب الأسطر بنجاح! 🔀", False)

    def remove_empty_lines(self):
        """Remove blank/empty lines."""
        txt = self.toPlainText()
        filtered = "\n".join([l for l in txt.splitlines() if l.strip()])
        self.setPlainText(filtered)
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم حذف كافة الأسطر الفارغة! 🧹", False)

    def trim_whitespace(self):
        """Remove leading and trailing spaces from each line."""
        txt = self.toPlainText()
        trimmed = "\n".join([l.strip() for l in txt.splitlines()])
        self.setPlainText(trimmed)
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تمت إزالة الفراغات الزائدة بنجاح! ✂️", False)

    def number_lines(self):
        """Number all lines in the document sequentially."""
        txt = self.toPlainText()
        lines = txt.splitlines()
        numbered = "\n".join([f"{i+1}. {l}" for i, l in enumerate(lines)])
        self.setPlainText(numbered)
        page = self._find_notepad_page()
        if page and hasattr(page, "_toast"):
            page._toast("تم ترقيم كافة الأسطر! 🔢", False)

    def insert_time_date(self):
        """Insert current date and time formatted string."""
        now_str = datetime.now().strftime("%I:%M %p %m/%d/%Y")
        self.insertPlainText(now_str)

    def contextMenuEvent(self, event):
        page = self._find_notepad_page()

        # If right clicked outside existing selection, move cursor to click position
        click_cursor = self.cursorForPosition(event.pos())
        curr_cursor = self.textCursor()
        if not (curr_cursor.hasSelection() and curr_cursor.selectionStart() <= click_cursor.position() <= curr_cursor.selectionEnd()):
            self.setTextCursor(click_cursor)

        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: #111b21;
                border: 1px solid #2a3942;
                border-radius: 8px;
                padding: 4px;
                color: #e9edef;
                font-family: 'Segoe UI', 'Cairo', sans-serif;
                font-size: 12.5px;
            }
            QMenu::item {
                padding: 5px 18px 5px 14px;
                border-radius: 5px;
                margin: 1px 2px;
            }
            QMenu::item:selected {
                background-color: #172554;
                color: #60a5fa;
            }
            QMenu::item:disabled {
                color: #64748b;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #202c33;
                margin: 3px 6px;
            }
        """)

        def _sub(parent, title):
            s = parent.addMenu(title)
            s.setLayoutDirection(Qt.RightToLeft)
            s.setStyleSheet(menu.styleSheet())
            return s

        # ── 1. وضع التركيز (Focus Mode) ──
        if page:
            is_focus = getattr(page, "_is_focus_mode", False)
            if is_focus:
                act_focus = menu.addAction("↩️ إنهاء وضع التركيز (Esc / F11)")
                act_focus.triggered.connect(page.exit_focus_mode)
            else:
                act_focus = menu.addAction("⛶ وضع التركيز بكامل الشاشة (F11)")
                act_focus.triggered.connect(page.enter_focus_mode)
            menu.addSeparator()

        # ── 2. العمليات الأساسية المباشرة (قص، نسخ، لصق، حذف) ──
        has_selection = self.textCursor().hasSelection()

        act_cut = menu.addAction("✂️ قص (Cut)\tCtrl+X")
        act_cut.setEnabled(has_selection)
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction("📋 نسخ (Copy)\tCtrl+C")
        act_copy.setEnabled(has_selection)
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction("📥 لصق (Paste)\tCtrl+V")
        act_paste.setEnabled(self.canPaste())
        act_paste.triggered.connect(self.paste)

        act_del = menu.addAction("🗑️ حذف (Delete)\tDel")
        act_del.setEnabled(has_selection)
        def _do_del():
            c = self.textCursor()
            if c.hasSelection():
                c.removeSelectedText()
            else:
                c.deleteChar()
        act_del.triggered.connect(_do_del)

        menu.addSeparator()

        # ── 3. التراجع والتحديد ──
        act_undo = menu.addAction("↩️ تراجع (Undo)\tCtrl+Z")
        act_undo.setEnabled(self.document().isUndoAvailable())
        act_undo.triggered.connect(self.undo)

        act_redo = menu.addAction("↪️ إعادة (Redo)\tCtrl+Y")
        act_redo.setEnabled(self.document().isRedoAvailable())
        act_redo.triggered.connect(self.redo)

        act_sel_all = menu.addAction("✨ تحديد كل النص (Select All)\tCtrl+A")
        act_sel_all.triggered.connect(self.selectAll)

        menu.addSeparator()

        # ── 4. قائمة فرعية: البحث والتنقل ──
        if page:
            sub_search = _sub(menu, "🔍 البحث والتنقل ▾")
            act_find = sub_search.addAction("🔍 بحث في المستند...\tCtrl+F")
            act_find.triggered.connect(lambda: page.find_replace_bar.show_search(False))

            act_replace = sub_search.addAction("⇄ استبدال في المستند...\tCtrl+H")
            act_replace.triggered.connect(lambda: page.find_replace_bar.show_search(True))

            act_goto = sub_search.addAction("🚀 الانتقال إلى سطر...\tCtrl+G")
            act_goto.triggered.connect(page.go_to_line_dialog)

        # ── 5. قائمة فرعية: تحرير الأسطر والنصوص ──
        sub_text = _sub(menu, "⚡ تحرير الأسطر والنصوص ▾")

        act_sel_line = sub_text.addAction("📌 تحديد السطر الحالي")
        act_sel_line.triggered.connect(self.select_current_line)

        act_dup = sub_text.addAction("📑 تكرار السطر الحالي\tCtrl+D")
        act_dup.triggered.connect(self.duplicate_current_line)

        act_del_line = sub_text.addAction("🗑️ حذف السطر الحالي")
        act_del_line.triggered.connect(self.delete_current_line)

        act_time = sub_text.addAction("⏰ إدراج الوقت والتاريخ\tF5")
        act_time.triggered.connect(self.insert_time_date)

        sub_text.addSeparator()

        # حالة الأحرف
        sub_case = _sub(sub_text, "🔠 حالة الأحرف ▾")
        act_upper = sub_case.addAction("🔠 أحرف كبيرة (UPPERCASE)")
        act_upper.triggered.connect(lambda: self.transform_case("upper"))
        act_lower = sub_case.addAction("🔡 أحرف صغيرة (lowercase)")
        act_lower.triggered.connect(lambda: self.transform_case("lower"))
        act_title = sub_case.addAction("🔤 حالة العنوان (Title Case)")
        act_title.triggered.connect(lambda: self.transform_case("title"))
        act_swap = sub_case.addAction("🔀 عكس حالة الأحرف (Toggle Case)")
        act_swap.triggered.connect(lambda: self.transform_case("swap"))

        # فرز وترتيب الأسطر
        sub_sort = _sub(sub_text, "🔀 فرز وترتيب الأسطر ▾")
        act_sort_asc = sub_sort.addAction("⬆️ ترتيب تصاعدياً (A ➔ Z)")
        act_sort_asc.triggered.connect(lambda: self.sort_lines(True))
        act_sort_desc = sub_sort.addAction("⬇️ ترتيب تنازلياً (Z ➔ A)")
        act_sort_desc.triggered.connect(lambda: self.sort_lines(False))

        # تنظيف وتنسيق الأسطر
        sub_clean = _sub(sub_text, "🧹 تنظيف وتنسيق الأسطر ▾")
        act_clean = sub_clean.addAction("🧹 حذف كافة الأسطر الفارغة")
        act_clean.triggered.connect(self.remove_empty_lines)
        act_trim = sub_clean.addAction("✂️ إزالة الفراغات الزائدة (Trim)")
        act_trim.triggered.connect(self.trim_whitespace)
        act_nums = sub_clean.addAction("🔢 ترقيم كافة الأسطر")
        act_nums.triggered.connect(self.number_lines)

        # ── 6. قائمة فرعية: التنسيق والمظهر ──
        sub_fmt = _sub(menu, "🎨 التنسيق والمظهر ▾")

        if page:
            act_font = sub_fmt.addAction("🔤 خيارات وتنسيق الخط...")
            act_font.triggered.connect(page.choose_font_dialog)

        is_wrapped = self.lineWrapMode() != QPlainTextEdit.LineWrapMode.NoWrap
        act_wrap = sub_fmt.addAction("↩️ التفاف النص (Word Wrap)")
        act_wrap.setCheckable(True)
        act_wrap.setChecked(is_wrapped)
        def _toggle_wrap():
            now_wrap = not (self.lineWrapMode() != QPlainTextEdit.LineWrapMode.NoWrap)
            self.toggle_word_wrap(now_wrap)
            if page and hasattr(page, "act_word_wrap"):
                page.act_word_wrap.setChecked(now_wrap)
            if page and hasattr(page, "_toast"):
                page._toast("تم تفعيل التفاف النص (Word Wrap)" if now_wrap else "تم إلغاء التفاف النص", False)
        act_wrap.triggered.connect(_toggle_wrap)

        sub_fmt.addSeparator()

        sub_dir = _sub(sub_fmt, "↔️ اتجاه ومحاذاة النص ▾")
        act_rtl = sub_dir.addAction("➡️ اتجاه: من اليمين لليسار (RTL - عربي)")
        act_rtl.triggered.connect(lambda: page._set_direction(True) if page else self.set_text_direction(True))
        act_ltr = sub_dir.addAction("⬅️ اتجاه: من اليسار لليمين (LTR - إنجليزي)")
        act_ltr.triggered.connect(lambda: page._set_direction(False) if page else self.set_text_direction(False))
        sub_dir.addSeparator()
        act_al_r = sub_dir.addAction("➡️ محاذاة لليمين")
        act_al_r.triggered.connect(lambda: self.set_text_alignment(Qt.AlignRight))
        act_al_c = sub_dir.addAction("↔️ محاذاة للوسط")
        act_al_c.triggered.connect(lambda: self.set_text_alignment(Qt.AlignCenter))
        act_al_l = sub_dir.addAction("⬅️ محاذاة لليسار")
        act_al_l.triggered.connect(lambda: self.set_text_alignment(Qt.AlignLeft))

        sub_zoom = _sub(sub_fmt, "🔍 التكبير والتصغير ▾")
        act_zin = sub_zoom.addAction("➕ تكبير (Zoom In)\tCtrl++")
        act_zin.triggered.connect(self.zoom_in)
        act_zout = sub_zoom.addAction("➖ تصغير (Zoom Out)\tCtrl+-")
        act_zout.triggered.connect(self.zoom_out)
        act_zres = sub_zoom.addAction("🔄 الحجم الطبيعي 100%\tCtrl+0")
        act_zres.triggered.connect(self.reset_zoom)

        # ── 7. قائمة فرعية: إدارة الملف والمستند ──
        if page:
            sub_doc = _sub(menu, "📁 المستند والملف ▾")
            act_new = sub_doc.addAction("📄 علامة تبويب جديدة\tCtrl+N")
            act_new.triggered.connect(lambda: page.new_tab())

            act_save = sub_doc.addAction("💾 حفظ المستند\tCtrl+S")
            act_save.triggered.connect(page.save_current_tab)

            act_save_as = sub_doc.addAction("💾 حفظ باسم...\tCtrl+Shift+S")
            act_save_as.triggered.connect(page.save_as_current_tab)

            act_open = sub_doc.addAction("📂 فتح ملف...\tCtrl+O")
            act_open.triggered.connect(page.open_file)

            act_stats = sub_doc.addAction("📊 إحصائيات النص...")
            act_stats.triggered.connect(page.show_text_stats_dialog)

            act_print = sub_doc.addAction("🖨️ طباعة / تصدير PDF...\tCtrl+P")
            act_print.triggered.connect(page.print_or_export_pdf)

            sub_doc.addSeparator()

            act_close = sub_doc.addAction("✕ إغلاق التبويب الحالي\tCtrl+W")
            act_close.triggered.connect(lambda: page.close_tab(page.tab_widget.currentIndex()))

            # ── 8. قائمة فرعية: أدوات SnipGlide ──
            sub_snip = _sub(menu, "🚀 أدوات SnipGlide ▾")
            act_snip = sub_snip.addAction("✂️ تحويل المحدد إلى اختصار SnipGlide")
            act_snip.setEnabled(has_selection)
            act_snip.triggered.connect(page.convert_selection_to_snippet)

            act_notes = sub_snip.addAction("📝 حفظ في ملاحظات SnipGlide اللاصقة")
            act_notes.triggered.connect(page.save_to_snipglide_notes)

            act_chat = sub_snip.addAction("💬 إرسال إلى شات نوت (Chat Notes)")
            act_chat.triggered.connect(page.send_to_chat_notes)

        menu.exec(event.globalPos())


QTextEditSelection = QTextEdit.ExtraSelection


