from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QPointF
from PySide6.QtGui import QPixmap

from models.state import AppState


class AppController(QObject):
    """Application controller (signals-only; no UI code).

    You can later plug in:
      - WebSocket / BLE / serial: call update_point(...)
      - Model inference: call update_point(...) + update_choices(...)
    """

    image_changed = Signal(QPixmap)
    point_changed = Signal(QPointF)              # a dynamic point in image coords
    selection_changed = Signal(int, str)         # choice selection
    grid_config_changed = Signal(int, int)       # rows, cols

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

    def load_initial_image(self) -> None:
        path = self.state.image_file()
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        pix = QPixmap(str(path))
        if pix.isNull():
            raise ValueError(f"Failed to load image: {path}")

        self.image_changed.emit(pix)
        self.grid_config_changed.emit(self.state.grid.rows, self.state.grid.cols)

        # initial point (top-left-ish)
        self.point_changed.emit(QPointF(50, 50))

    @Slot(int, str)
    def on_choice_selected(self, index: int, text: str) -> None:
        self.selection_changed.emit(index, text)

    # ---- future external integration entry points ----
    def update_point(self, pos: QPointF) -> None:
        """External systems should call this to move the point (image coords)."""
        self.point_changed.emit(pos)

    def set_grid(self, rows: int, cols: int) -> None:
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        self.state.grid = self.state.grid.__class__(rows=rows, cols=cols, line_width=self.state.grid.line_width)
        self.grid_config_changed.emit(rows, cols)
