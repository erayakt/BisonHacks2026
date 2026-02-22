from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from controllers.app_controller import AppController
from main_window import MainWindow
from models.config import GridConfig, UiConfig
from models.state import AppState


def main() -> int:
    # CHANGE THIS:
    IMAGE_PATH = r"images/image1.jpg"

    state = AppState(
        image_path=IMAGE_PATH,
        choices=["Apple", "River", "Triangle", "Guitar"],
        grid=GridConfig(rows=12, cols=12),
    )

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QListWidget { font-size: 18px; padding: 8px; }
        QListWidget::item { padding: 10px; }
        QListWidget::item:selected { border-radius: 8px; }
    """)

    controller = AppController(state)
    window = MainWindow(controller, ui=UiConfig())
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
