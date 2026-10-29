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


RESPONSE_LABELS = {
    "compete": "경쟁",
    "ride_trend": "편승",
    "adjust_release_timing": "개봉 시기 조정",
}


class HistoryTimelineScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_organization_profile: Callable[[str], None] | None = None,
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("역사 타임라인")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)
        current_date = state.get("current_date") or {}
        if current_date:
            current_date_text = (
                f"{current_date.get('year')}년 "
                f"{current_date.get('month')}월 "
                f"{current_date.get('day')}일"
            )
            subtitle = QLabel(
                f"현재 게임 날짜 기준: {current_date_text} · 아직 일어나지 않은 역사는 표시하지 않습니다."
            )
            subtitle.setWordWrap(True)
            subtitle.setObjectName("MutedText")
            layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._protected_films_tab(state.get("protected_films", [])), "주요 필모그래피")
        tabs.addTab(self._foreign_events_tab(state.get("foreign_events", [])), "외화 대작")
        tabs.addTab(self._events_tab(state.get("policy_events", [])), "정책·제도")
        tabs.addTab(self._events_tab(state.get("market_events", [])), "시장 변화")
        tabs.addTab(self._industry_events_tab(state.get("distribution_events", []), on_organization_profile), "배급")
        tabs.addTab(self._industry_events_tab(state.get("theater_events", []), on_organization_profile), "극장")
        tabs.addTab(self._industry_events_tab(state.get("premium_format_events", []), on_organization_profile), "특별관")
        tabs.addTab(self._ticket_prices_tab(state.get("ticket_prices", [])), "티켓값")
        tabs.addTab(self._events_tab(state.get("events", [])), "역사 이벤트")
        layout.addWidget(tabs)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    def _protected_films_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="표시할 주요 작품 기록 없음",
            label_fn=lambda row: (
                f"{row.get('release_year')}.{row.get('release_month')} · "
                f"{row.get('director_name') or '감독 미상'} · {row.get('title')}"
            ),
            detail_fn=self._protected_film_detail,
        )

    def _events_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 역사 이벤트 없음",
            label_fn=lambda row: f"{row.get('year')}.{row.get('month') or ''} · {row.get('title')}",
            detail_fn=lambda row: "\n\n".join(
                [
                    row.get("title", ""),
                    row.get("type", ""),
                    row.get("description") or "",
                    self._unlocks_text(row.get("unlocks") or []),
                ]
            ),
        )

    def _foreign_events_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="표시할 외화 대작 기록 없음",
            label_fn=lambda row: f"{row.get('year')}.{row.get('month') or ''} · {row.get('title_ko') or row.get('title')}",
            detail_fn=lambda row: "\n\n".join(
                [
                    f"{row.get('title_ko') or row.get('title', '')} / {row.get('title_en') or ''}".strip(),
                    f"영향 등급: {row.get('impact_grade') or '미정'}",
                    f"장르: {', '.join(row.get('genre') or [])}",
                    row.get("description") or "",
                    "플레이어 대응: 경쟁 / 편승 / 개봉 시기 조정",
                ]
            ),
        )

    def _industry_events_tab(
        self,
        rows: list[dict[str, Any]],
        on_organization_profile: Callable[[str], None] | None,
    ) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 산업 구조 이벤트 없음",
            label_fn=lambda row: f"{row.get('year')}.{row.get('month') or ''} · {row.get('title')}",
            detail_fn=lambda row: "\n\n".join(
                [
                    row.get("title", ""),
                    row.get("type", ""),
                    f"회사/체인: {row.get('company') or row.get('chain') or '미정'}",
                    f"지점/지역: {row.get('location') or '미정'}",
                    "포맷: " + ", ".join(row.get("format") or []) if row.get("format") else "",
                    "관련 회사: " + ", ".join(row.get("relatedCompanies") or []) if row.get("relatedCompanies") else "",
                    row.get("description") or "",
                    self._unlocks_text(row.get("unlocks") or []),
                ]
            ),
            open_fn=(
                (lambda row: on_organization_profile(str(row["organizationId"])))
                if on_organization_profile
                else None
            ),
        )

    def _ticket_prices_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        return self._detail_tab(
            rows,
            empty_label="등록된 티켓값 기록 없음",
            label_fn=lambda row: f"{row.get('year')} · 평균 {int(row.get('average_ticket_price') or 0):,}원",
            detail_fn=lambda row: "\n\n".join(
                [
                    f"{row.get('year')}년 티켓값",
                    f"평균 티켓값: {int(row.get('average_ticket_price') or 0):,}원",
                    f"체감 티켓값: {int(row.get('perceived_ticket_price') or 0):,}원",
                    f"자료 유형: {row.get('source_type')}",
                ]
            ),
        )

    def _detail_tab(
        self,
        rows: list[dict[str, Any]],
        *,
        empty_label: str,
        label_fn: Callable[[dict[str, Any]], str],
        detail_fn: Callable[[dict[str, Any]], str],
        open_fn: Callable[[dict[str, Any]], None] | None = None,
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
        if open_fn:
            listing.itemDoubleClicked.connect(
                lambda item: open_fn(item.data(Qt.ItemDataRole.UserRole))
                if item.data(Qt.ItemDataRole.UserRole)
                and item.data(Qt.ItemDataRole.UserRole).get("organizationId")
                else None
            )
        layout.addWidget(listing, 1)
        layout.addWidget(detail, 2)
        if listing.count() and rows:
            listing.setCurrentRow(0)
        return tab

    @staticmethod
    def _unlocks_text(unlocks: list[str]) -> str:
        if not unlocks:
            return ""
        return "해금: " + ", ".join(unlocks)

    @staticmethod
    def _protected_film_detail(row: dict[str, Any]) -> str:
        metadata = row.get("metadata", {})
        window = metadata.get("protectedWindow", {})
        responses = [
            RESPONSE_LABELS.get(response, response)
            for response in metadata.get("allowedPlayerResponses", [])
        ]
        lines = [
            row.get("title", ""),
            f"감독: {row.get('director_name') or metadata.get('directorName') or '감독 미상'}",
            f"개봉: {row.get('release_year')}년 {row.get('release_month')}월",
            "실제 개봉 기록",
        ]
        if window:
            lines.append(
                "주요 제작/개봉 일정: "
                f"{window.get('startYear')}년 {window.get('startMonth')}월 - "
                f"{window.get('endYear')}년 {window.get('endMonth')}월"
            )
        if responses:
            lines.append("플레이어 대응: " + " / ".join(responses))
        return "\n\n".join(lines)
