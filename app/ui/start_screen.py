from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class StartScreen(QWidget):
    def __init__(
        self,
        *,
        can_load: bool,
        on_new_game: Callable[[], None],
        on_load: Callable[[], None],
        on_view_db: Callable[[], None],
        on_display_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        title = QLabel("ChungmuroTycoon")
        title.setObjectName("Title")
        subtitle = QLabel("한국 영화 산업 운영 시뮬레이션")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        new_button = QPushButton("새 게임")
        load_button = QPushButton("불러오기")
        db_button = QPushButton("데이터베이스")
        display_button = QPushButton("화면 설정")
        quit_button = QPushButton("종료")

        load_button.setEnabled(can_load)
        new_button.clicked.connect(on_new_game)
        load_button.clicked.connect(on_load)
        db_button.clicked.connect(on_view_db)
        display_button.clicked.connect(on_display_settings)
        quit_button.clicked.connect(on_quit)

        for button in (new_button, load_button, db_button, display_button, quit_button):
            button.setMinimumWidth(240)
            button.setMinimumHeight(42)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(new_button)
        layout.addWidget(load_button)
        layout.addWidget(db_button)
        layout.addWidget(display_button)
        layout.addWidget(quit_button)
