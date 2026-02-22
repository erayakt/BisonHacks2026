import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Qt, QPointF
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QMessageBox,
)


# -----------------------------
# Model / App State
# -----------------------------
@dataclass
class AppState:
    image_path: str
    choices: list[str]


class AppController(QObject):
    image_changed = Signal(QPixmap)
    marker_changed = Signal(QPointF)
    selection_changed = Signal(int, str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

    def load_initial_image(self) -> None:
        path = Path(self.state.image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        pix = QPixmap(str(path))
        if pix.isNull():
            raise ValueError(f"Failed to load image: {path}")

        self.image_changed.emit(pix)

    @Slot(int, str)
    def on_choice_selected(self, index: int, text: str) -> None:
        self.selection_changed.emit(index, text)

        # Demo: move marker to a few fixed spots so you see overlay works
        offsets = [QPointF(60, 60), QPointF(160, 120), QPointF(260, 220), QPointF(360, 180)]
        self.marker_changed.emit(offsets[index % len(offsets)])


# -----------------------------
# View: Left Image Canvas
# -----------------------------
class ImageCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._pix_item: QGraphicsPixmapItem | None = None
        self._marker: QGraphicsEllipseItem | None = None

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    @Slot(QPixmap)
    def set_image(self, pixmap: QPixmap) -> None:
        self.scene().clear()
        self._pix_item = self.scene().addPixmap(pixmap)
        self._pix_item.setZValue(0)

        # Overlay marker
        r = 7
        self._marker = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        self._marker.setZValue(10)
        self.scene().addItem(self._marker)

        self.setSceneRect(self._pix_item.boundingRect())
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        self.set_marker(QPointF(50, 50))

    @Slot(QPointF)
    def set_marker(self, pos: QPointF) -> None:
        if not self._pix_item or not self._marker:
            return

        rect = self._pix_item.boundingRect()

        x = min(max(pos.x(), rect.left()), rect.right())
        y = min(max(pos.y(), rect.top()), rect.bottom())
        self._marker.setPos(QPointF(x, y))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else (1 / 1.15)
        self.scale(factor, factor)


# -----------------------------
# View: Right Choices Panel
# -----------------------------
class ChoicesPanel(QWidget):
    choice_selected = Signal(int, str)

    def __init__(self, choices: list[str]):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Choices")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        for c in choices:
            self.list.addItem(QListWidgetItem(c))

        self.list.currentRowChanged.connect(self._emit_current)
        layout.addWidget(self.list)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _emit_current(self, row: int) -> None:
        if row < 0:
            return
        item = self.list.item(row)
        if item:
            self.choice_selected.emit(row, item.text())


# -----------------------------
# Main Window
# -----------------------------
class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("UI Prototype (No TTS Yet)")
        self.resize(1100, 700)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = ImageCanvas()
        splitter.addWidget(self.canvas)

        self.choices_panel = ChoicesPanel(controller.state.choices)
        splitter.addWidget(self.choices_panel)

        # Make LEFT (image) larger than RIGHT (list)
        splitter.setStretchFactor(0, 5)   # image
        splitter.setStretchFactor(1, 1)   # list
        splitter.setSizes([900, 250])     # force initial widths

        # Optional: keep right side in a comfortable range
        self.choices_panel.setMinimumWidth(220)
        self.choices_panel.setMaximumWidth(320)

        self.setCentralWidget(splitter)

        # Wiring
        self.controller.image_changed.connect(self.canvas.set_image)
        self.controller.marker_changed.connect(self.canvas.set_marker)
        self.choices_panel.choice_selected.connect(self.controller.on_choice_selected)
        self.controller.selection_changed.connect(self._on_selection_changed)

        # Optional shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.choices_panel.list.setFocus)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.canvas.setFocus)

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


def main():
    # CHANGE THIS:
    IMAGE_PATH = r"images/image1.jpg"

    state = AppState(
        image_path=IMAGE_PATH,
        choices=["Apple", "River", "Triangle", "Guitar"],
    )

    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QListWidget { font-size: 18px; padding: 8px; }
        QListWidget::item { padding: 10px; }
        QListWidget::item:selected { border-radius: 8px; }
    """)

    controller = AppController(state)
    window = MainWindow(controller)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()