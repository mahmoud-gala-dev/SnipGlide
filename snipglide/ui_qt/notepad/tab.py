from typing import Optional
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabBar
from snipglide.ui_qt.notepad.editor import NotepadEditor

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


