from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money
from app.services.public_text_service import audience_reaction_text


class TheatricalRunScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_next_day: Callable[[], None],
        on_show_result: Callable[[], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.state = state
        project = state["project"]
        daily_results = state.get("daily_results", [])
        status = str(state.get("status", "active"))

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("극장 1차 시장 일일 보고")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        summary = QLabel(
            f"{project['title']} · {project['genre_name']} · {project['scale_name']}\n"
            f"상영 {state.get('current_day', 0)}/{state.get('max_days', 0)}일차 · "
            f"누적 관객 {int(state.get('cumulative_audience', 0)):,}명 · "
            f"누적 매출 {money(state.get('cumulative_revenue', 0))}"
        )
        summary.setObjectName("PanelText")
        layout.addWidget(summary)

        grid_box = QGroupBox("상영 지표")
        grid = QGridLayout(grid_box)
        forecast = state.get("forecast", {})
        rows = [
            ("예상 최종 관객", f"{int(forecast.get('final_audience', 0)):,}명"),
            ("티켓 평균가", money(forecast.get("average_ticket_price", 0))),
            ("관람등급", str(forecast.get("content_rating_name") or "등급 미정")),
            ("예상 손익분기점", f"{int(forecast.get('break_even_audience', 0)):,}명"),
            ("예상 관객 반응", audience_reaction_text(forecast.get("audience_score"))),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index // 2, (index % 2) * 2)
            grid.addWidget(QLabel(value), index // 2, (index % 2) * 2 + 1)
        layout.addWidget(grid_box)

        graph = DailyBoxOfficeGraph(
            daily_results=daily_results,
            max_days=int(state.get("max_days", 1) or 1),
        )
        layout.addWidget(graph)

        table = QTableWidget(len(daily_results), 6)
        table.setHorizontalHeaderLabels(["일차", "날짜", "일일 관객", "누적 관객", "일일 매출", "누적 매출"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row_index, row in enumerate(daily_results):
            values = [
                f"{int(row['day_number'])}일차",
                f"{int(row['year'])}.{int(row['month']):02d}.{int(row['day']):02d}",
                f"{int(row['daily_audience']):,}명",
                f"{int(row['cumulative_audience']):,}명",
                money(row["daily_revenue"]),
                money(row["cumulative_revenue"]),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_index, col_index, item)
        table.setMinimumHeight(180)
        layout.addWidget(table)

        if status == "completed":
            complete_label = QLabel("극장 1차 시장이 종료되었습니다. 최종 정산 보고서를 확인할 수 있습니다.")
            complete_label.setWordWrap(True)
            layout.addWidget(complete_label)
            result_button = QPushButton("1차 시장 결과 보기")
            result_button.clicked.connect(on_show_result)
            layout.addWidget(result_button)
        else:
            next_button = QPushButton("다음 상영일 진행")
            next_button.setMinimumHeight(40)
            next_button.clicked.connect(on_next_day)
            layout.addWidget(next_button)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)


class DailyBoxOfficeGraph(QWidget):
    def __init__(self, *, daily_results: list[dict[str, Any]], max_days: int) -> None:
        super().__init__()
        self.daily_results = daily_results
        self.max_days = max(1, max_days)
        self.setMinimumHeight(230)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        painter.fillRect(0, 0, width, height, QColor("#0f1317"))

        left = 54
        right = width - 20
        top = 24
        bottom = height - 34
        plot_width = max(1, right - left)
        plot_height = max(1, bottom - top)

        painter.setPen(QPen(QColor("#313944"), 1))
        painter.drawLine(left, bottom, right, bottom)
        painter.drawLine(left, top, left, bottom)

        if not self.daily_results:
            painter.setPen(QPen(QColor("#aeb7c2"), 1))
            painter.drawText(left + 12, top + 42, "상영일을 진행하면 일일 관객 그래프가 표시됩니다.")
            painter.end()
            return

        daily_values = [int(row.get("daily_audience", 0) or 0) for row in self.daily_results]
        cumulative_values = [int(row.get("cumulative_audience", 0) or 0) for row in self.daily_results]
        max_daily = max(max(daily_values), 1)
        max_cumulative = max(max(cumulative_values), 1)
        slot = plot_width / self.max_days
        bar_width = max(3, min(18, slot * 0.58))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#60758a"))
        for index, value in enumerate(daily_values):
            x = left + slot * index + (slot - bar_width) / 2
            bar_height = plot_height * (value / max_daily) * 0.88
            painter.drawRect(int(x), int(bottom - bar_height), int(bar_width), int(bar_height))

        points = []
        for index, value in enumerate(cumulative_values):
            x = left + slot * index + slot / 2
            y = bottom - plot_height * (value / max_cumulative) * 0.92
            points.append(QPointF(x, y))
        if len(points) >= 2:
            painter.setPen(QPen(QColor("#65d6c5"), 3))
            painter.drawPolyline(QPolygonF(points))
        elif points:
            painter.setPen(QPen(QColor("#65d6c5"), 6))
            painter.drawPoint(points[0])

        painter.setPen(QPen(QColor("#d7dde4"), 1))
        painter.drawText(left, height - 10, "일일 관객")
        painter.setPen(QPen(QColor("#65d6c5"), 2))
        painter.drawText(left + 80, height - 10, "누적 관객")
        painter.end()
