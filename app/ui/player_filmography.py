from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money
from app.services.movie_detail_service import detail_text, get_movie_detail
from app.services.public_text_service import audience_reaction_text, critic_reaction_text


class PlayerFilmographyScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_movie_detail: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("플레이어 제작 필모그래피")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)
        layout.addWidget(self._summary_box(state.get("summary", {})))

        body = QHBoxLayout()
        listing = QListWidget()
        detail = QTextEdit()
        detail.setReadOnly(True)

        films = state.get("films", [])
        for film in films:
            item = QListWidgetItem(
                f"{film.get('releaseYear')}.{film.get('releaseMonth')} · "
                f"{film.get('title')} · {film.get('summary', {}).get('statusLabel', '개봉작')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, film)
            listing.addItem(item)
        if not films:
            listing.addItem("아직 개봉한 플레이어 제작 영화 없음")
            detail.setPlainText("영화를 개봉하면 이곳에 관객 수, 손익, 수상, 평론, 협업, 실패, 역주행, 시리즈 기록이 누적됩니다.")

        def show_detail(item: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
            film = item.data(Qt.ItemDataRole.UserRole) if item else None
            detail.setPlainText(self._film_detail(film) if film else "")

        listing.currentItemChanged.connect(show_detail)
        listing.itemDoubleClicked.connect(
            lambda item: on_movie_detail(str(item.data(Qt.ItemDataRole.UserRole).get("filmId")))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        body.addWidget(listing, 1)
        body.addWidget(detail, 3)
        layout.addLayout(body)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

        if films:
            listing.setCurrentRow(0)

    @staticmethod
    def _summary_box(summary: dict[str, Any]) -> QGroupBox:
        box = QGroupBox("제작사 누적 기록")
        grid = QGridLayout(box)
        values = [
            ("개봉작", f"{summary.get('filmCount', 0)}편"),
            ("누적 관객", f"{int(summary.get('totalAudience') or 0):,}명"),
            ("누적 손익", money(summary.get("totalProfit"))),
            ("수상/후보", f"{summary.get('awardCount', 0)}건"),
            ("실패작", f"{summary.get('failureCount', 0)}편"),
            ("역주행/재평가", f"{summary.get('reevaluationCount', 0)}편"),
            ("시리즈/IP", f"{summary.get('franchiseCount', 0)}편"),
        ]
        for index, (label, value) in enumerate(values):
            row = index // 4
            col = (index % 4) * 2
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(QLabel(value), row, col + 1)
        return box

    def _film_detail(self, film: dict[str, Any]) -> str:
        movie_detail = detail_text(get_movie_detail(str(film.get("filmId"))))
        sections = [
            movie_detail,
            self._collaboration_text(film.get("collaborations", [])),
            self._awards_text(film.get("awards", [])),
            self._reviews_text(film.get("reviews", [])),
            self._failure_text(film.get("failureRecord", {})),
            self._reevaluation_text(film.get("reevaluation", {})),
            self._franchise_text(film.get("franchise", {})),
        ]
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _basic_text(film: dict[str, Any]) -> str:
        return "\n".join(
            [
                film.get("title", ""),
                f"개봉: {film.get('releaseYear')}년 {film.get('releaseMonth')}월",
                f"장르/규모: {film.get('genreName') or film.get('genreId')} · {film.get('scaleName') or film.get('scaleId')}",
                f"관객 수: {int(film.get('audience') or 0):,}명",
                f"극장 매출: {money(film.get('grossRevenue'))}",
                f"손익: {money(film.get('profit'))}",
                f"손익분기 관객: {int(film.get('breakEvenAudience') or 0):,}명",
                f"관객 반응: {audience_reaction_text(film.get('audienceScore'))} · "
                f"평론가 반응: {critic_reaction_text(film.get('criticScore'))}",
            ]
        )

    @staticmethod
    def _collaboration_text(rows: list[dict[str, Any]]) -> str:
        lines = ["배우/감독 협업 기록"]
        if not rows:
            lines.append("기록된 협업 인물 없음")
            return "\n".join(lines)
        for row in rows:
            lines.append(f"- {row.get('role')} · {row.get('nameKo')} · {row.get('status')}")
        return "\n".join(lines)

    @staticmethod
    def _awards_text(rows: list[dict[str, Any]]) -> str:
        lines = ["수상 기록"]
        if not rows:
            lines.append("수상/후보 기록 없음")
            return "\n".join(lines)
        for row in rows:
            lines.append(f"- {row.get('year')} · {row.get('awardName')} · {row.get('category')} · {row.get('result')}")
        return "\n".join(lines)

    @staticmethod
    def _reviews_text(rows: list[dict[str, Any]]) -> str:
        lines = ["평론 반응"]
        if not rows:
            lines.append("기록된 평론 없음")
            return "\n".join(lines)
        for row in rows:
            quote = f" · {row.get('quote')}" if row.get("quote") else ""
            score = critic_reaction_text(row.get("score")) if row.get("score") is not None else "반응 미상"
            lines.append(f"- {row.get('criticName')} · {score}{quote}")
        return "\n".join(lines)

    @staticmethod
    def _failure_text(record: dict[str, Any]) -> str:
        lines = ["실패작 기록"]
        if not record.get("isFailure"):
            lines.append("실패작으로 분류되지 않음")
            return "\n".join(lines)
        lines.append(f"분류: {record.get('severity')}")
        lines.append("사유: " + ", ".join(record.get("reasons", [])))
        lines.append(f"손실 규모: {money(record.get('lossAmount'))}")
        return "\n".join(lines)

    @staticmethod
    def _reevaluation_text(data: dict[str, Any]) -> str:
        lines = ["역주행/재평가 기록"]
        events = data.get("events", [])
        metrics = data.get("metrics", [])
        if not events and not metrics:
            lines.append("아직 기록 없음")
            return "\n".join(lines)
        for event in events:
            lines.append(f"- {event.get('year')}.{event.get('month')} · {event.get('triggerType')} · {event.get('summary')}")
        for metric in metrics:
            lines.append(f"- {metric.get('year')}.{metric.get('month')} · {metric.get('summary')} · {metric.get('value')}")
        return "\n".join(lines)

    @staticmethod
    def _franchise_text(data: dict[str, Any]) -> str:
        lines = ["시리즈 기록"]
        ip = data.get("ip")
        entries = data.get("entries", [])
        if not ip and not entries:
            lines.append("시리즈/IP 기록 없음")
            return "\n".join(lines)
        if ip:
            lines.append(
                f"IP: {ip.get('title')} · 가치 {ip.get('ipValue')} · "
                f"프랜차이즈 파워 {ip.get('franchisePower')} · 후속 수요 {ip.get('sequelDemand')}"
            )
        for entry in entries:
            lines.append(
                f"- #{entry.get('sequenceNo')} · {entry.get('entryType')} · "
                f"{entry.get('year')}년 {entry.get('month')}월"
            )
        return "\n".join(lines)
