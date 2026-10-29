from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ModuleScreen(QWidget):
    def __init__(
        self,
        *,
        title: str,
        lines: list[str],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel(title)
        heading.setObjectName("ScreenTitle")
        layout.addWidget(heading)

        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            label.setObjectName("PanelText")
            layout.addWidget(label)

        layout.addStretch(1)
        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)
