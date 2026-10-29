from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money


class CrewWorkScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_select_work: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.state = state
        self.options = list(state.get("options", []))
        self.on_select_work = on_select_work

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("현장 일거리")
        title.setObjectName("ScreenTitle")
        intro = QLabel(state.get("intro") or "")
        intro.setWordWrap(True)
        intro.setObjectName("PanelText")
        layout.addWidget(title)
        layout.addWidget(intro)

        body = QGridLayout()
        self.listing = QListWidget()
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        for option in self.options:
            item = QListWidgetItem(
                f"{option['title']} · {option['days']}일 · 예상 {money(option['totalPay'])}"
            )
            item.setData(Qt.ItemDataRole.UserRole, option["id"])
            self.listing.addItem(item)
        self.listing.itemClicked.connect(self._show_detail)
        body.addWidget(self.listing, 0, 0)
        body.addWidget(self.detail, 0, 1)
        layout.addLayout(body)

        if self.options:
            self.listing.setCurrentRow(0)
            self._set_detail(self.options[0])

        button_grid = QGridLayout()
        start_button = QPushButton("선택한 일거리 참여")
        back_button = QPushButton("대시보드로")
        start_button.clicked.connect(self._start_selected)
        back_button.clicked.connect(on_back)
        button_grid.addWidget(start_button, 0, 0)
        button_grid.addWidget(back_button, 0, 1)
        layout.addLayout(button_grid)

        history_box = QGroupBox("최근 참여 기록")
        history_layout = QVBoxLayout(history_box)
        history_list = QListWidget()
        for row in state.get("history", []):
            history_list.addItem(
                f"{row['period']} · {row['title']} · {row['daysWorked']}일 · {money(row['totalPay'])}"
            )
        if not state.get("history"):
            history_list.addItem("아직 현장 참여 기록 없음")
        history_layout.addWidget(history_list)
        layout.addWidget(history_box)

    def _show_detail(self, item: QListWidgetItem) -> None:
        work_id = str(item.data(Qt.ItemDataRole.UserRole))
        option = next((candidate for candidate in self.options if candidate["id"] == work_id), None)
        if option:
            self._set_detail(option)

    def _set_detail(self, option: dict[str, Any]) -> None:
        lines = [
            option["title"],
            f"역할: {option['roleLabel']}",
            f"기간: {option['days']}일",
            f"일당: {money(option['dailyWage'])}",
            f"기준: {option.get('wageBasis') or '현재 연도 물가 기준'}",
            f"예상 수입: {money(option['totalPay'])}",
            "",
            "하는 일",
            option["description"],
            "",
            "얻는 감각",
            option["learningText"],
            "",
            "얻는 인맥",
            option["networkText"],
        ]
        self.detail.setPlainText("\n".join(lines))

    def _start_selected(self) -> None:
        item = self.listing.currentItem()
        if not item:
            return
        self.on_select_work(str(item.data(Qt.ItemDataRole.UserRole)))
