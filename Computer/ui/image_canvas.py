from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Slot, Qt, QRect, QRectF
from PySide6.QtGui import QPainter, QPixmap, QImage
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

        # Last known marker point in image coordinates
        self._current_point: Optional[QPointF] = None

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
        self._current_point = p

        self._grid.set_active_cell_from_point(p)


    def current_point(self) -> Optional[QPointF]:
        """Return the last point set on the canvas (image coordinates)."""
        return self._current_point

    def crop_around_point(self, size: int = 256) -> Optional[QImage]:
        """Crop a square QImage of `size` x `size` around the current point.

        - The crop is centered on the red marker.
        - If the crop rectangle goes out of bounds, the missing area is padded with black.
        """
        if not self._pix_item or self._current_point is None:
            return None

        pix = self._pix_item.pixmap()
        if pix.isNull():
            return None

        src_img = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)

        w = src_img.width()
        h = src_img.height()
        if w <= 0 or h <= 0:
            return None

        half = int(size // 2)
        cx = int(round(self._current_point.x()))
        cy = int(round(self._current_point.y()))

        # Desired source rect (may be out of bounds)
        src_rect = QRect(cx - half, cy - half, int(size), int(size))

        # Intersect with actual image bounds
        bounds = QRect(0, 0, w, h)
        intersect = src_rect.intersected(bounds)

        # Target image (padded)
        out = QImage(int(size), int(size), QImage.Format.Format_RGBA8888)
        out.fill(Qt.GlobalColor.black)

        if intersect.isEmpty():
            return out

        # Where to place the intersected patch in the output
        dx = int(intersect.x() - src_rect.x())
        dy = int(intersect.y() - src_rect.y())

        painter = QPainter(out)
        try:
            painter.drawImage(QRect(dx, dy, intersect.width(), intersect.height()), src_img, intersect)
        finally:
            painter.end()

        return out


    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else (1 / 1.15)
        self.scale(factor, factor)
