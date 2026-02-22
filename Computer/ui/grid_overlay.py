from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsScene


@dataclass
class ActiveCell:
    row: int
    col: int
    rect: QRectF


class GridOverlay:
    """Draws a grid over the image and highlights the active cell for a point.

    Everything is kept in *image coordinates*.
    """

    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._rows = 1
        self._cols = 1
        self._bounds: QRectF | None = None

        self._line_items: list[QGraphicsLineItem] = []
        self._active_rect_item: QGraphicsRectItem | None = None

        # Pens/brushes are intentionally centralized for easy theming
        self._grid_pen = QPen(Qt.GlobalColor.white)
        self._grid_pen.setCosmetic(True)
        self._grid_pen.setWidthF(1.0)
        self._grid_pen.setStyle(Qt.PenStyle.DotLine)

        self._active_pen = QPen(Qt.GlobalColor.yellow)
        self._active_pen.setCosmetic(True)
        self._active_pen.setWidthF(2.0)

        self._active_brush = QBrush(Qt.GlobalColor.yellow)
        self._active_brush.setStyle(Qt.BrushStyle.Dense4Pattern)

    def set_config(self, rows: int, cols: int, bounds: QRectF) -> None:
        self._rows = max(1, int(rows))
        self._cols = max(1, int(cols))
        self._bounds = bounds
        self._rebuild()

    def clear(self) -> None:
        for item in self._line_items:
            self._scene.removeItem(item)
        self._line_items.clear()

        if self._active_rect_item is not None:
            self._scene.removeItem(self._active_rect_item)
            self._active_rect_item = None

    def _rebuild(self) -> None:
        self.clear()
        if self._bounds is None:
            return

        b = self._bounds
        w = b.width()
        h = b.height()

        # Vertical lines
        for c in range(1, self._cols):
            x = b.left() + w * (c / self._cols)
            li = self._scene.addLine(x, b.top(), x, b.bottom(), self._grid_pen)
            li.setZValue(5)
            self._line_items.append(li)

        # Horizontal lines
        for r in range(1, self._rows):
            y = b.top() + h * (r / self._rows)
            li = self._scene.addLine(b.left(), y, b.right(), y, self._grid_pen)
            li.setZValue(5)
            self._line_items.append(li)

        # Active cell rect (initially hidden until first point)
        self._active_rect_item = QGraphicsRectItem()
        self._active_rect_item.setPen(self._active_pen)
        self._active_rect_item.setBrush(self._active_brush)
        self._active_rect_item.setZValue(9)
        self._active_rect_item.setVisible(False)
        self._scene.addItem(self._active_rect_item)

    def cell_for_point(self, p: QPointF) -> Optional[ActiveCell]:
        if self._bounds is None:
            return None

        b = self._bounds
        x = min(max(p.x(), b.left()), b.right() - 1e-6)
        y = min(max(p.y(), b.top()), b.bottom() - 1e-6)

        col = int((x - b.left()) / b.width() * self._cols)
        row = int((y - b.top()) / b.height() * self._rows)

        col = min(max(col, 0), self._cols - 1)
        row = min(max(row, 0), self._rows - 1)

        cell_w = b.width() / self._cols
        cell_h = b.height() / self._rows

        rect = QRectF(
            b.left() + col * cell_w,
            b.top() + row * cell_h,
            cell_w,
            cell_h,
        )
        return ActiveCell(row=row, col=col, rect=rect)

    def set_active_cell_from_point(self, p: QPointF) -> Optional[ActiveCell]:
        cell = self.cell_for_point(p)
        if cell is None or self._active_rect_item is None:
            return None

        self._active_rect_item.setRect(cell.rect)
        self._active_rect_item.setVisible(True)
        return cell
