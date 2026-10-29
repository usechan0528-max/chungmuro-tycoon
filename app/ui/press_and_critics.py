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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PressAndCriticsScreen(QWidget):
    def __init__(self, *, state: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("언론/평론")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._press_tab(state.get("press", [])), "언론")
        tabs.addTab(self._reviews_tab(state.get("reviews", [])), "리뷰")
        tabs.addTab(self._critics_tab(state.get("critics", [])), "평론가")
        layout.addWidget(tabs)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    def _press_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 기사 없음",
            label_fn=lambda row: (
                f"{row.get('year')}.{int(row.get('month') or 1):02d}.{int(row.get('day') or 1):02d} · "
                f"{row.get('title')}"
            ),
            detail_fn=_press_detail,
        )

    def _reviews_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 리뷰 없음",
            label_fn=lambda row: f"{row.get('critic_name') or '평론'} · {row.get('movie_id')}",
            detail_fn=lambda row: "\n\n".join(
                [
                    row.get("critic_name") or "평론",
                    row.get("quote") or "",
                    f"평점 {row.get('score')}" if row.get("score") is not None else "",
                ]
            ),
        )

    def _critics_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 평론가 없음",
            label_fn=lambda row: row.get("name_ko", "평론가"),
            detail_fn=lambda row: "\n\n".join([row.get("name_ko", "평론가"), row.get("public_description") or ""]),
        )

    def _detail_tab(
        self,
        rows: list[dict[str, Any]],
        *,
        empty_label: str,
        label_fn: Callable[[dict[str, Any]], str],
        detail_fn: Callable[[dict[str, Any]], str],
    ) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        listing = QListWidget()
        detail = QTextEdit()
        detail.setReadOnly(True)
        for row in rows:
            item = QListWidgetItem(label_fn(row))
            item.setData(Qt.ItemDataRole.UserRole, row)
            listing.addItem(item)
        if not rows:
            listing.addItem(empty_label)

        def show_detail(item: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
            row = item.data(Qt.ItemDataRole.UserRole) if item else None
            detail.setPlainText(detail_fn(row) if row else "")

        listing.currentItemChanged.connect(show_detail)
        layout.addWidget(listing, 1)
        layout.addWidget(detail, 2)
        if listing.count() and rows:
            listing.setCurrentRow(0)
        return tab


def _press_detail(row: dict[str, Any]) -> str:
    parts = [
        row.get("title", ""),
        row.get("body") or "",
    ]
    reactions = row.get("reactions") or []
    if reactions:
        parts.append("사람들 반응")
        parts.extend(
            f"- {reaction.get('group', '반응')} · {reaction.get('tone', '관망')}: {reaction.get('text', '')}"
            for reaction in reactions
        )
    return "\n\n".join(part for part in parts if part)
