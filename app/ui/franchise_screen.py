from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class FranchiseScreen(QWidget):
    def __init__(
        self,
        *,
        offers: list[dict[str, Any]],
        on_choice: Callable[[str, dict[str, Any], dict[str, Any]], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.offers = offers
        self._on_choice = on_choice
        self.choice_buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("시리즈/IP 개발")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        body = QHBoxLayout()
        self.listing = QListWidget()
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        for offer in offers:
            ip = offer.get("ip", {})
            item = QListWidgetItem(f"{ip.get('title', 'IP')} · {_ip_label(ip)}")
            item.setData(Qt.ItemDataRole.UserRole, offer)
            self.listing.addItem(item)
        if not offers:
            self.listing.addItem("현재 시리즈화 제안 없음")
            self.detail.setPlainText(
                "손익분기점을 넘겼거나 관객 반응, 컬트 잠재력, 2차 시장 가치가 충분한 작품이 생기면 이곳에 제안이 올라옵니다."
            )
        self.listing.currentItemChanged.connect(self._show_offer)
        body.addWidget(self.listing, 1)
        body.addWidget(self.detail, 2)
        layout.addLayout(body, 1)

        self.choice_row = QHBoxLayout()
        layout.addLayout(self.choice_row)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

        if offers:
            self.listing.setCurrentRow(0)

    def _show_offer(self, item: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        offer = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._clear_choice_buttons()
        if not offer:
            return
        ip = offer.get("ip", {})
        event = offer.get("event", {})
        self.detail.setPlainText(_offer_text(ip, event))
        for choice in event.get("choices", []):
            button = QPushButton(str(choice.get("text", "선택")))
            button.clicked.connect(lambda checked=False, selected=choice: self._choose(offer, selected))
            self.choice_buttons.append(button)
            self.choice_row.addWidget(button)

    def _choose(self, offer: dict[str, Any], choice: dict[str, Any]) -> None:
        ip_id = str(offer.get("ip", {}).get("id"))
        self._on_choice(ip_id, offer.get("event", {}), choice)

    def _clear_choice_buttons(self) -> None:
        while self.choice_buttons:
            button = self.choice_buttons.pop()
            self.choice_row.removeWidget(button)
            button.deleteLater()


def _offer_text(ip: dict[str, Any], event: dict[str, Any]) -> str:
    lines = [
        str(event.get("title") or "시리즈화 제안"),
        str(event.get("description") or ""),
        "",
        f"원작 IP: {ip.get('title') or '-'}",
        f"개봉 시기: {ip.get('release_year') or '-'}년 {ip.get('release_month') or '-'}월",
        f"흥행 규모: {int(ip.get('final_audience') or 0):,}명",
        f"IP 상태: {_ip_label(ip)}",
        "",
        "선택지",
    ]
    for choice in event.get("choices", []):
        lines.append(f"- {choice.get('text')}")
    return "\n".join(line for line in lines if line is not None)


def _ip_label(ip: dict[str, Any]) -> str:
    ip_value = int(ip.get("ip_value") or 0)
    franchise_power = int(ip.get("franchise_power") or 0)
    sequel_demand = int(ip.get("sequel_demand") or 0)
    if max(ip_value, franchise_power, sequel_demand) >= 80:
        return "강한 시리즈 후보"
    if max(ip_value, franchise_power, sequel_demand) >= 65:
        return "검토할 만한 IP"
    if max(ip_value, franchise_power, sequel_demand) >= 50:
        return "가능성은 있으나 신중한 IP"
    return "보존 가치 중심 IP"
