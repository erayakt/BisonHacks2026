from __future__ import annotations

from typing import Iterable, List, Optional

from PySide6.QtCore import QObject, Signal, Slot, QPointF
from PySide6.QtGui import QPixmap

from models.state import AppState


class AppController(QObject):
    """Application controller (signals-only; no UI code).

    Future external integration points:
      - WebSocket / BLE / serial: call update_point(...) and update_highlighted_choice(...)
      - Model inference: call update_point(...) + update_choices(...)
    """

    # Image + overlays
    image_changed = Signal(QPixmap)
    point_changed = Signal(QPointF)              # a dynamic point in image coords
    grid_config_changed = Signal(int, int)       # rows, cols

    # Choice selection UX
    choices_updated = Signal(list)               # list[str]
    highlighted_choice_changed = Signal(int)     # "look-at" index (in choosing mode)
    chosen_choice_changed = Signal(int, str)     # chosen index + text
    choose_mode_changed = Signal(bool)           # True: choosing, False: running

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        # Selection state machine:
        #   choosing=True  -> user is browsing options (arrow keys)
        #   choosing=False -> user has chosen and app logic runs
        self._choosing: bool = False
        self._highlighted_index: int = 0
        self._chosen_index: Optional[int] = None

    # -----------------------------
    # Boot
    # -----------------------------
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

        # initial choices
        self.choices_updated.emit(list(self.state.choices))
        self._highlighted_index = 0 if self.state.choices else -1
        if self._highlighted_index >= 0:
            self.highlighted_choice_changed.emit(self._highlighted_index)

        self.choose_mode_changed.emit(self._choosing)

    # -----------------------------
    # Choice UX state machine
    # -----------------------------
    def is_choosing(self) -> bool:
        return self._choosing

    def enter_choose_mode(self) -> None:
        if self._choosing:
            return
        self._choosing = True
        self.choose_mode_changed.emit(True)
        # Ensure highlight is valid
        if self.state.choices:
            self._highlighted_index = min(max(self._highlighted_index, 0), len(self.state.choices) - 1)
            self.highlighted_choice_changed.emit(self._highlighted_index)

    def confirm_choice(self) -> None:
        if not self._choosing:
            return
        if not self.state.choices:
            return
        idx = min(max(self._highlighted_index, 0), len(self.state.choices) - 1)
        self._chosen_index = idx
        text = self.state.choices[idx]

        # Exit choose mode and notify
        self._choosing = False
        self.choose_mode_changed.emit(False)
        self.chosen_choice_changed.emit(idx, text)

    def move_highlight(self, delta: int) -> None:
        if not self._choosing:
            return
        if not self.state.choices:
            return
        n = len(self.state.choices)
        self._highlighted_index = (self._highlighted_index + int(delta)) % n
        self.highlighted_choice_changed.emit(self._highlighted_index)

    # For later: when highlight is driven by external input (websocket)
    def update_highlighted_choice(self, index: int) -> None:
        if not self.state.choices:
            return
        idx = min(max(int(index), 0), len(self.state.choices) - 1)
        self._highlighted_index = idx
        self.highlighted_choice_changed.emit(idx)

    # For later: when the list itself changes (websocket/model)
    def update_choices(self, choices: Iterable[str]) -> None:
        new_choices: List[str] = list(choices)
        self.state.choices = new_choices

        # Keep highlight/chosen indices in range
        if new_choices:
            self._highlighted_index = min(max(self._highlighted_index, 0), len(new_choices) - 1)
            if self._chosen_index is not None:
                self._chosen_index = min(max(self._chosen_index, 0), len(new_choices) - 1)
        else:
            self._highlighted_index = -1
            self._chosen_index = None
            if self._choosing:
                self._choosing = False
                self.choose_mode_changed.emit(False)

        self.choices_updated.emit(new_choices)
        if self._highlighted_index >= 0:
            self.highlighted_choice_changed.emit(self._highlighted_index)
        if self._chosen_index is not None and self._chosen_index >= 0 and self._chosen_index < len(new_choices):
            self.chosen_choice_changed.emit(self._chosen_index, new_choices[self._chosen_index])

    # Click selection from UI should behave like "confirm choice"
    @Slot(int, str)
    def on_choice_clicked(self, index: int, text: str) -> None:
        if self.state.choices:
            self.update_highlighted_choice(index)
        if self._choosing:
            self.confirm_choice()
        else:
            self._chosen_index = index
            self.chosen_choice_changed.emit(index, text)

    # -----------------------------
    # Grid/point entry points
    # -----------------------------
    def update_point(self, pos: QPointF) -> None:
        """External systems should call this to move the point (image coords)."""
        self.point_changed.emit(pos)

    def set_grid(self, rows: int, cols: int) -> None:
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        self.state.grid = self.state.grid.__class__(rows=rows, cols=cols, line_width=self.state.grid.line_width)
        self.grid_config_changed.emit(rows, cols)
