from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


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
