from __future__ import annotations

from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter

from controllers.app_controller import AppController
from ui.choices_panel import ChoicesPanel
from ui.image_canvas import ImageCanvas
from models.config import UiConfig


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, ui: UiConfig = UiConfig()):
        super().__init__()
        self.controller = controller

        self.setWindowTitle(ui.window_title)
        self.resize(ui.window_width, ui.window_height)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = ImageCanvas()
        splitter.addWidget(self.canvas)

        self.choices_panel = ChoicesPanel(controller.state.choices)
        splitter.addWidget(self.choices_panel)

        # Make LEFT (image) larger than RIGHT (list)
        splitter.setStretchFactor(0, ui.left_pane_weight)
        splitter.setStretchFactor(1, ui.right_pane_weight)
        splitter.setSizes([int(ui.window_width * 0.8), int(ui.window_width * 0.2)])

        self.choices_panel.setMinimumWidth(ui.right_min_width)
        self.choices_panel.setMaximumWidth(ui.right_max_width)

        self.setCentralWidget(splitter)

        # Wiring
        self.controller.image_changed.connect(self.canvas.set_image)
        self.controller.point_changed.connect(self.canvas.set_point)
        self.controller.grid_config_changed.connect(self.canvas.set_grid_config)

        self.choices_panel.choice_selected.connect(self.controller.on_choice_selected)
        self.controller.selection_changed.connect(self._on_selection_changed)

        # Optional shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.choices_panel.list.setFocus)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.canvas.setFocus)

        # Demo shortcut: random-ish point update (until you add websocket)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._demo_move_point)

    @Slot(int, str)
    def _on_selection_changed(self, idx: int, text: str) -> None:
        self.statusBar().showMessage(f"Selected: {idx} — {text}")

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.controller.load_initial_image()
            self.choices_panel.list.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _demo_move_point(self) -> None:
        # Small demo: move point based on current selection (replace with websocket later)
        row = self.choices_panel.list.currentRow()
        offsets = [(80, 80), (220, 140), (340, 260), (420, 190)]
        x, y = offsets[row % len(offsets)] if row >= 0 else (60, 60)
        from PySide6.QtCore import QPointF
        self.controller.update_point(QPointF(x, y))
