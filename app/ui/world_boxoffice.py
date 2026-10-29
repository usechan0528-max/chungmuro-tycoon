from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money
from app.services.public_text_service import market_pressure_text


class WorldBoxOfficeScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_movie_detail: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        date = state.get("date", {})
        title = QLabel(
            f"시장 박스오피스 / 스크린 점유 · "
            f"{date.get('year')}년 {date.get('month')}월 {date.get('day')}일"
        )
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        summary = state.get("summary", {})
        summary_box = QGroupBox("현재 개봉작 순위 요약")
        grid = QGridLayout(summary_box)
        rows = [
            ("자료 모드", state.get("modeLabel", "-")),
            ("일일 관객", f"{_number(summary.get('totalDailyAudience'))}명"),
            ("일일 매출", money(summary.get("totalDailyRevenue"))),
            ("추정 총 스크린", f"{_number(summary.get('totalScreens'))}개"),
            ("한국영화 관객 비중", _percent(summary.get("domesticAudienceShare"))),
            ("외화 관객 비중", _percent(summary.get("foreignAudienceShare"))),
            ("한국영화 스크린 점유", _percent(summary.get("domesticScreenShare"))),
            ("외화 스크린 점유", _percent(summary.get("foreignScreenShare"))),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index // 4, (index % 4) * 2)
            grid.addWidget(QLabel(value), index // 4, (index % 4) * 2 + 1)
        layout.addWidget(summary_box)

        market = state.get("marketState") or {}
        market_label = QLabel(
            f"{market_pressure_text('theater_demand', market.get('theater_demand'))} · "
            f"{market_pressure_text('foreign_competition', market.get('foreign_competition'))} · "
            f"{market_pressure_text('ott_power', market.get('ott_power'))} · "
            f"스크린 기준: {summary.get('screenSource', '-')}"
        )
        market_label.setObjectName("PanelText")
        layout.addWidget(market_label)

        layout.addWidget(ScreenShareBars(rows=state.get("rows", [])))

        table = QTableWidget(len(state.get("rows", [])), 9)
        table.setHorizontalHeaderLabels(
            ["순위", "작품/구분", "구분", "일일 관객", "누적/예상 관객", "일일 매출", "스크린", "점유율", "자료"]
        )
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row_index, row in enumerate(state.get("rows", [])):
            values = [
                str(row.get("rank", row_index + 1)),
                str(row.get("title") or "-"),
                str(row.get("originLabel") or "-"),
                f"{_number(row.get('dailyAudience'))}명",
                f"{_number(row.get('cumulativeAudience'))}명",
                money(row.get("dailyRevenue")),
                f"{_number(row.get('screenCount'))}개",
                _percent(row.get("screenShare")),
                f"{row.get('source') or '-'} · {row.get('status') or '-'}",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if row.get("isPlayerFilm"):
                    item.setBackground(QColor("#173b35"))
                table.setItem(row_index, col_index, item)
        table.cellClicked.connect(
            lambda row, col: on_movie_detail(str(state.get("rows", [])[row].get("id")))
            if col == 1 and row < len(state.get("rows", [])) and state.get("rows", [])[row].get("id")
            else None
        )
        table.setMinimumHeight(260)
        layout.addWidget(table)

        notes = state.get("notes", [])
        notes_box = QTextEdit()
        notes_box.setReadOnly(True)
        notes_box.setMaximumHeight(120)
        notes_box.setPlainText(_notes_text(notes))
        layout.addWidget(notes_box)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)


class ScreenShareBars(QWidget):
    def __init__(self, *, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self.rows = rows[:8]
        self.setMinimumHeight(180)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        painter.fillRect(0, 0, width, height, QColor("#0f1317"))

        left = 170
        right = width - 28
        top = 18
        row_height = 18
        gap = 7
        bar_width = max(1, right - left)

        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.drawText(16, 14, "스크린 점유율")
        if not self.rows:
            painter.drawText(16, 60, "표시할 시장 데이터가 없습니다.")
            painter.end()
            return

        for index, row in enumerate(self.rows):
            y = top + index * (row_height + gap)
            share = max(0.0, min(1.0, float(row.get("screenShare") or 0)))
            title = str(row.get("title") or "-")
            if len(title) > 18:
                title = title[:17] + "..."
            color = QColor("#0f766e") if row.get("isPlayerFilm") else QColor("#64748b")
            painter.setPen(QPen(QColor("#cbd5e1"), 1))
            painter.drawText(16, y + 14, title)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1f2933"))
            painter.drawRect(left, y, bar_width, row_height)
            painter.setBrush(color)
            painter.drawRect(left, y, int(bar_width * share), row_height)
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawText(right - 62, y + 14, _percent(share))
        painter.end()


def _notes_text(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return "해당 월에 표시할 시장 뉴스가 없습니다."
    lines = ["시장 메모"]
    for note in notes:
        lines.append(f"- {note.get('title')}: {note.get('body') or note.get('source_type') or ''}")
    return "\n".join(lines)


def _number(value: Any) -> str:
    return f"{int(value or 0):,}"


def _percent(value: Any) -> str:
    if value is None:
        return "미집계"
    return f"{float(value) * 100:.1f}%"
