from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from controllers.app_controller import AppController
from main_window import MainWindow
from models.config import GridConfig, UiConfig
from models.state import AppState


def main() -> int:
    # CHANGE THIS:
    IMAGE_PATH = r"images/image3.jpg"

    state = AppState(
        image_path=IMAGE_PATH,
        choices=["Humidity Intensity Gradient", "Color Saturation Variation", "Contour Line Density"],
        grid=GridConfig(rows=12, cols=12),
    )

    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QListWidget { 
            font-size: 18px; 
            padding: 8px; 
            background: #111; 
            color: white;
            border: 1px solid #333;
            border-radius: 10px;
        }
        QListWidget::item { padding: 10px; border-radius: 8px; }
        QListWidget[mode="choosing"]::item:selected { 
            background: #2a4; 
            color: black;
            border: 2px solid #7f7;
        }
        QListWidget[mode="running"]::item:selected { 
            background: #333; 
            color: white; 
            border: 1px solid #666;
        }
    """)

    controller = AppController(state)
    window = MainWindow(controller, ui=UiConfig(window_title="VisionMouse"))
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
