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

from app.services.game_state import money


class AnnualReportScreen(QWidget):
    def __init__(self, *, state: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("연간 산업 리포트")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        body = QHBoxLayout()
        listing = QListWidget()
        detail = QTextEdit()
        detail.setReadOnly(True)

        reports = state.get("reports", [])
        for report in reports:
            summary = report.get("summary", {})
            item = QListWidgetItem(
                f"{report.get('year')} · "
                f"{summary.get('topFilm') or '박스오피스 미집계'}"
            )
            item.setData(Qt.ItemDataRole.UserRole, report)
            listing.addItem(item)
        if not reports:
            listing.addItem("생성된 연간 리포트 없음")
            detail.setPlainText(self._empty_text(state))

        def show_detail(item: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
            report = item.data(Qt.ItemDataRole.UserRole) if item else None
            detail.setPlainText(self._report_text(report) if report else self._empty_text(state))

        listing.currentItemChanged.connect(show_detail)
        body.addWidget(listing, 1)
        body.addWidget(detail, 3)
        layout.addLayout(body)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

        if reports:
            listing.setCurrentRow(0)

    @staticmethod
    def _empty_text(state: dict[str, Any]) -> str:
        years = state.get("source_years", [])
        if years:
            return "원천 데이터가 감지된 연도: " + ", ".join(str(year) for year in years[-10:])
        return "아직 연간 결산에 사용할 원천 데이터가 없습니다."

    def _report_text(self, report: dict[str, Any]) -> str:
        year = report.get("year")
        share = report.get("koreanFilmShare") or {}
        summary = report.get("sourceSummary") or {}
        sections = [
            f"{year}년 한국 영화산업 결산",
            self._share_text(share),
            self._movie_ranking("연간 박스오피스 TOP 10", report.get("topBoxoffice") or []),
            self._movie_ranking("외화 흥행작", report.get("foreignHits") or []),
            self._people_ranking("올해의 배우", report.get("actorsOfYear") or []),
            self._people_ranking("올해의 감독", report.get("directorsOfYear") or []),
            self._awards_text(report.get("awardHighlights") or []),
            self._company_ranking("제작사 순위", report.get("productionCompanyRankings") or []),
            self._company_ranking("배급사 점유율", report.get("distributorShare") or []),
            self._genre_text(report.get("genreTrends") or []),
            f"자료 상태: {summary.get('precision', 'unknown')} · 박스오피스 행 {summary.get('boxofficeRows', 0)}개",
        ]
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _share_text(share: dict[str, Any]) -> str:
        return "\n".join(
            [
                "한국영화 점유율",
                f"관객 기준: {_percent(share.get('audienceShare'))}",
                f"매출 기준: {_percent(share.get('salesShare'))}",
                f"한국영화 관객: {_number(share.get('domesticAudience'))}명",
                f"전체 관객: {_number(share.get('totalAudience'))}명",
                f"자료 기준: {share.get('source', '미정')}",
            ]
        )

    @staticmethod
    def _movie_ranking(title: str, rows: list[dict[str, Any]]) -> str:
        lines = [title]
        if not rows:
            lines.append("집계된 항목 없음")
            return "\n".join(lines)
        for row in rows:
            lines.append(
                f"{row.get('rank')}. {row.get('title')} · "
                f"{_number(row.get('audience'))}명 · {money(row.get('sales'))} · "
                f"{row.get('distributor') or '배급사 미상'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _people_ranking(title: str, rows: list[dict[str, Any]]) -> str:
        lines = [title]
        if not rows:
            lines.append("집계된 항목 없음")
            return "\n".join(lines)
        for row in rows[:5]:
            works = ", ".join(work.get("title", "") for work in row.get("works", [])[:3])
            lines.append(
                f"{row.get('rank')}. {row.get('name')} · "
                f"연간 관객 기여 {_number(row.get('audienceScore'))}명"
                + (f" · {works}" if works else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _awards_text(rows: list[dict[str, Any]]) -> str:
        lines = ["주요 시상식 수상"]
        if not rows:
            lines.append("집계된 항목 없음")
            return "\n".join(lines)
        for row in rows[:12]:
            target = row.get("movieTitle") or row.get("movieId") or row.get("personName") or ""
            lines.append(
                f"- {row.get('award')} · {row.get('category') or '부문 미상'} · "
                f"{row.get('result') or '결과'}"
                + (f" · {target}" if target else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _company_ranking(title: str, rows: list[dict[str, Any]]) -> str:
        lines = [title]
        if not rows:
            lines.append("집계된 항목 없음")
            return "\n".join(lines)
        for row in rows[:8]:
            lines.append(
                f"{row.get('rank')}. {row.get('name')} · "
                f"{_number(row.get('audience'))}명 · 점유 {_percent(row.get('audienceShare'))}"
            )
        return "\n".join(lines)

    @staticmethod
    def _genre_text(rows: list[dict[str, Any]]) -> str:
        lines = ["장르 트렌드 변화"]
        if not rows:
            lines.append("집계된 항목 없음")
            return "\n".join(lines)
        for row in rows[:8]:
            delta = row.get("shareDelta")
            delta_text = "변화 미상" if delta is None else f"{float(delta) * 100:+.1f}%p"
            lines.append(
                f"- {row.get('genre')} · 관객 {_number(row.get('audience'))}명 · "
                f"비중 {_percent(row.get('audienceShare'))} · 전년 대비 {delta_text}"
            )
        return "\n".join(lines)


def _number(value: Any) -> str:
    return f"{int(value or 0):,}"


def _percent(value: Any) -> str:
    if value is None:
        return "미집계"
    return f"{float(value) * 100:.1f}%"
