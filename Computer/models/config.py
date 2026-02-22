from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridConfig:
    """Grid definition in *image coordinates*.

    rows/cols define how many cells the image is divided into.
    """
    rows: int = 12
    cols: int = 12
    line_width: float = 1.0


@dataclass(frozen=True)
class UiConfig:
    window_title: str = "Grid UI Prototype"
    window_width: int = 1100
    window_height: int = 700
    left_pane_weight: int = 5
    right_pane_weight: int = 1
    right_min_width: int = 220
    right_max_width: int = 320
