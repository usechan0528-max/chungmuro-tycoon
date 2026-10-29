from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget


class SaveLoadScreen(QWidget):
    def __init__(
        self,
        *,
        slots: list[dict[str, Any]],
        on_save_slot: Callable[[int], None],
        on_load_slot: Callable[[int], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("세이브 슬롯 관리")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        for slot in slots:
            layout.addWidget(self._slot_row(slot, on_save_slot, on_load_slot))

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        back_button.setMinimumHeight(42)
        layout.addWidget(back_button)
        layout.addStretch(1)

    @staticmethod
    def _slot_row(
        slot: dict[str, Any],
        on_save_slot: Callable[[int], None],
        on_load_slot: Callable[[int], None],
    ) -> QWidget:
        slot_number = int(slot["slot"])
        box = QGroupBox(str(slot["label"]))
        grid = QGridLayout(box)

        summary = QLabel(str(slot["summary"]))
        summary.setWordWrap(True)
        modified = QLabel(f"수정 시각: {slot['modified_at']}" if slot["exists"] else "수정 시각: -")
        modified.setObjectName("PanelText")

        save_button = QPushButton("이 슬롯에 저장")
        load_button = QPushButton("이 슬롯 불러오기")
        load_button.setEnabled(bool(slot["exists"]))
        save_button.clicked.connect(lambda checked=False, selected=slot_number: on_save_slot(selected))
        load_button.clicked.connect(lambda checked=False, selected=slot_number: on_load_slot(selected))

        grid.addWidget(summary, 0, 0, 1, 2)
        grid.addWidget(modified, 1, 0, 1, 2)
        grid.addWidget(save_button, 2, 0)
        grid.addWidget(load_button, 2, 1)
        return box
