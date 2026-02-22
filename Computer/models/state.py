from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .config import GridConfig


@dataclass
class AppState:
    image_path: str
    choices: List[str]
    grid: GridConfig = GridConfig()

    def image_file(self) -> Path:
        return Path(self.image_path)
