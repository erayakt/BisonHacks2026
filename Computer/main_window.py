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

        # Used to suppress first highlight speech when entering choosing mode
        self._suppress_next_highlight_tts = False

        self.setWindowTitle(ui.window_title)
        self.resize(ui.window_width, ui.window_height)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = ImageCanvas()
        splitter.addWidget(self.canvas)

        self.choices_panel = ChoicesPanel(controller.state.choices)
        splitter.addWidget(self.choices_panel)

        splitter.setStretchFactor(0, ui.left_pane_weight)
        splitter.setStretchFactor(1, ui.right_pane_weight)
        splitter.setSizes([int(ui.window_width * 0.8), int(ui.window_width * 0.2)])

        self.choices_panel.setMinimumWidth(ui.right_min_width)
        self.choices_panel.setMaximumWidth(ui.right_max_width)

        self.setCentralWidget(splitter)

        # Wiring: image + overlays
        self.controller.image_changed.connect(self.canvas.set_image)
        self.controller.point_changed.connect(self.canvas.set_point)
        self.controller.grid_config_changed.connect(self.canvas.set_grid_config)

        # Wiring: choices
        self.controller.choices_updated.connect(self.choices_panel.set_choices)
        self.controller.highlighted_choice_changed.connect(self._on_highlight_changed)
        self.controller.chosen_choice_changed.connect(self._on_chosen_changed)

        # Mode: update UI + speak mode
        self.controller.choose_mode_changed.connect(self.choices_panel.set_choose_mode)
        self.controller.choose_mode_changed.connect(self._on_mode_changed)

        self.choices_panel.choice_clicked.connect(self.controller.on_choice_clicked)

        # Optional shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.choices_panel.list.setFocus)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.canvas.setFocus)

        # CHOOSING/RUNNING controls
        QShortcut(QKeySequence("Space"), self, activated=self._on_space)
        QShortcut(QKeySequence("Up"), self, activated=lambda: self.controller.move_highlight(-1))
        QShortcut(QKeySequence("Down"), self, activated=lambda: self.controller.move_highlight(+1))

        # Demo shortcut
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._demo_move_point)

    @Slot(bool)
    def _on_mode_changed(self, choosing: bool) -> None:
        mode = "CHOOSING" if choosing else "RUNNING"
        print(f"[TTS] MODE: {mode}")
        self.statusBar().showMessage(f"Mode: {mode}")

        if choosing:
            # Suppress immediate highlight TTS triggered by entering choose mode
            self._suppress_next_highlight_tts = True

    @Slot(int)
    def _on_highlight_changed(self, idx: int) -> None:
        self.choices_panel.set_highlighted_index(idx)

        if self._suppress_next_highlight_tts:
            self._suppress_next_highlight_tts = False
            return

        item = self.choices_panel.list.item(idx) if idx >= 0 else None
        if item is not None and self.controller.is_choosing():
            print(f"[TTS] {item.text()}")

    @Slot(int, str)
    def _on_chosen_changed(self, idx: int, text: str) -> None:
        self.choices_panel.set_chosen_index(idx)
        self.statusBar().showMessage(f"Chosen: {idx} — {text}")
        print(f"[TTS] CHOSEN: {text}")

    def _on_space(self) -> None:
        if not self.controller.is_choosing():
            self.controller.enter_choose_mode()
            self.choices_panel.list.setFocus()
        else:
            self.controller.confirm_choice()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.controller.load_initial_image()
            self.choices_panel.list.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _demo_move_point(self) -> None:
        row = self.choices_panel.list.currentRow()
        offsets = [(80, 80), (220, 140), (340, 260), (420, 190)]
        x, y = offsets[row % len(offsets)] if row >= 0 else (60, 60)
        from PySide6.QtCore import QPointF
        self.controller.update_point(QPointF(x, y))
