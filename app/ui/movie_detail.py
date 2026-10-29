from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.services.movie_detail_service import detail_text
from app.ui.media_widgets import poster_media_frame


class MovieDetailScreen(QWidget):
    def __init__(self, *, detail: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(str(detail.get("title") or "작품 상세"))
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(poster_media_frame(detail.get("id")), alignment=Qt.AlignmentFlag.AlignTop)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(detail_text(detail))
        top_layout.addWidget(body, 1)
        layout.addWidget(top, 1)

        back_button = QPushButton("돌아가기")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)
