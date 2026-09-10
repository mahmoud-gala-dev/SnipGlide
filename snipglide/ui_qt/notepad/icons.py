from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QIcon, QPixmap, QPainterPath, QPen


def create_vector_icon(icon_type: str, color: str = "#60a5fa", size: int = 20, hover_color: Optional[str] = None) -> QIcon:
    """
    Creates a crisp, DPI-independent vector QIcon using QPainterPath.
    Ensures beautiful rendering across all Windows display scales without missing font glyphs.
    """
    def _draw_pixmap(col: str) -> QPixmap:
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(col))
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

        path = QPainterPath()
        if icon_type in ("left", "chevron-left", "prev"):
            path.moveTo(size * 0.62, size * 0.22)
            path.lineTo(size * 0.35, size * 0.5)
            path.lineTo(size * 0.62, size * 0.78)
            p.drawPath(path)
        elif icon_type in ("right", "chevron-right", "next"):
            path.moveTo(size * 0.38, size * 0.22)
            path.lineTo(size * 0.65, size * 0.5)
            path.lineTo(size * 0.38, size * 0.78)
            p.drawPath(path)
        elif icon_type in ("plus", "add"):
            path.moveTo(size * 0.5, size * 0.22)
            path.lineTo(size * 0.5, size * 0.78)
            path.moveTo(size * 0.22, size * 0.5)
            path.lineTo(size * 0.78, size * 0.5)
            p.drawPath(path)
        elif icon_type in ("close", "exit", "x"):
            path.moveTo(size * 0.28, size * 0.28)
            path.lineTo(size * 0.72, size * 0.72)
            path.moveTo(size * 0.72, size * 0.28)
            path.lineTo(size * 0.28, size * 0.72)
            p.drawPath(path)
        elif icon_type in ("search", "find"):
            r = size * 0.26
            cx, cy = size * 0.42, size * 0.42
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            path.moveTo(size * 0.62, size * 0.62)
            path.lineTo(size * 0.82, size * 0.82)
            p.drawPath(path)
        p.end()
        return pm

    icon = QIcon()
    icon.addPixmap(_draw_pixmap(color), QIcon.Normal)
    if hover_color:
        icon.addPixmap(_draw_pixmap(hover_color), QIcon.Active)
    return icon
