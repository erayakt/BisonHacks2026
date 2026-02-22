from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class ChoicesPanel(QWidget):
    """Right pane: a list of choices with visual states."""

    choice_clicked = Signal(int, str)

    def __init__(self, choices: list[str]):
        super().__init__()
        layout = QVBoxLayout(self)

        # Short mode label (2-3 words max).
        self._mode_label = QLabel("RUNNING")
        self._mode_label.setStyleSheet("font-size: 14px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(self._mode_label)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._chosen_index: Optional[int] = None
        self._choosing: bool = False

        self.set_choices(choices)

        self.list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)

        self._apply_mode_visuals()

    def set_choices(self, choices: List[str]) -> None:
        self.list.clear()
        for c in choices:
            self.list.addItem(QListWidgetItem(c))
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self._chosen_index = None
        self._refresh_chosen_visual()

    def set_highlighted_index(self, row: int) -> None:
        if row < 0 or row >= self.list.count():
            return
        self.list.setCurrentRow(row)
        self.list.scrollToItem(self.list.item(row))

    def set_chosen_index(self, row: int) -> None:
        self._chosen_index = row
        self._refresh_chosen_visual()

    def set_choose_mode(self, choosing: bool) -> None:
        self._choosing = bool(choosing)
        self._apply_mode_visuals()

    def _apply_mode_visuals(self) -> None:
        self._mode_label.setText("CHOOSING" if self._choosing else "RUNNING")

        self.list.setProperty("mode", "choosing" if self._choosing else "running")
        self.list.style().unpolish(self.list)
        self.list.style().polish(self.list)

        self._refresh_chosen_visual()

    def _refresh_chosen_visual(self) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setBackground(Qt.GlobalColor.transparent)
            it.setForeground(Qt.GlobalColor.white)
            f = it.font()
            f.setBold(False)
            it.setFont(f)

        if self._chosen_index is None:
            return
        if 0 <= self._chosen_index < self.list.count():
            it = self.list.item(self._chosen_index)
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setForeground(Qt.GlobalColor.green)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        row = self.list.row(item)
        self.choice_clicked.emit(row, item.text())
