from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Slot, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from .grid_overlay import GridOverlay


class ImageCanvas(QGraphicsView):
    """Left pane: image + overlays.

    Coordinates for point/grid are in *image coordinates* (i.e., the pixmap's scene rect).
    """

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._pix_item: Optional[QGraphicsPixmapItem] = None

        # Dynamic point marker
        self._marker: Optional[QGraphicsEllipseItem] = None

        # Grid overlay manager
        self._grid = GridOverlay(self.scene())

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    @Slot(QPixmap)
    def set_image(self, pixmap: QPixmap) -> None:
        self.scene().clear()
        self._pix_item = self.scene().addPixmap(pixmap)
        self._pix_item.setZValue(0)

        # Overlay marker
        r = 6
        self._marker = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        self._marker.setZValue(10)
        self._marker.setBrush(Qt.GlobalColor.red)
        self._marker.setPen(Qt.PenStyle.NoPen)
        self.scene().addItem(self._marker)

        self.setSceneRect(self._pix_item.boundingRect())
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        # Rebuild grid with current config (defaults to 1x1 until set_grid_config called)
        self._grid.set_config(1, 1, self._pix_item.boundingRect())

        # initial marker/active-cell
        self.set_point(QPointF(50, 50))

    @Slot(int, int)
    def set_grid_config(self, rows: int, cols: int) -> None:
        if not self._pix_item:
            return
        self._grid.set_config(rows, cols, self._pix_item.boundingRect())

    @Slot(QPointF)
    def set_point(self, pos: QPointF) -> None:
        if not self._pix_item or not self._marker:
            return

        rect = self._pix_item.boundingRect()

        x = min(max(pos.x(), rect.left()), rect.right())
        y = min(max(pos.y(), rect.top()), rect.bottom())
        p = QPointF(x, y)

        # Move marker and update active cell highlight
        self._marker.setPos(p)
        self._grid.set_active_cell_from_point(p)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else (1 / 1.15)
        self.scale(factor, factor)
