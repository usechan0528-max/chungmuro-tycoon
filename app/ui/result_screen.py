from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.services.game_state import money
from app.services.public_text_service import (
    compact_network_changes,
    compact_reputation_changes,
    audience_reaction_text,
    critic_reaction_text,
    drop_risk_text,
    overall_change_text,
    quality_band_text,
    word_of_mouth_text,
)


class ResultScreen(QWidget):
    def __init__(self, *, result: dict[str, Any], on_continue: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("개봉 정산 보고서")
        title.setObjectName("ScreenTitle")
        film_title = QLabel(result["title"])
        film_title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(film_title)

        grid = QGridLayout()
        net_receipts = result.get(
            "net_studio_receipts",
            int(result.get("studio_revenue", 0) or 0) + int(result.get("secondary_market_revenue", 0) or 0),
        )
        rows = [
            ("장르", result.get("genre_name", result.get("genre_id", "-"))),
            ("규모", result.get("scale_name", result.get("scale_id", "-"))),
            ("관람등급", result.get("content_rating_name", "등급 미정")),
            ("개봉 판본", result.get("release_version_name") or "극장판"),
            ("OTT/2차 판본", result.get("ott_version_name") or "미정"),
            ("순제작비", money(result.get("production_budget", 0))),
            ("마케팅비", money(result.get("marketing_budget", 0))),
            ("총비용", money(result.get("total_cost", 0))),
            ("자기자본 투입", money(result.get("own_capital_used", 0))),
            ("투자본 투입", money(result.get("investment_used", 0))),
            ("투자자 지분율", f"{float(result.get('investor_equity_percent', 0) or 0):.1f}%"),
            ("투자자 초과수익 배분", f"{float(result.get('investor_profit_share', 0) or 0) * 100:.1f}%"),
            ("대출 투입", money(result.get("loan_used", 0))),
            ("작품 완성도", quality_band_text(result.get("final_quality"))),
            ("개봉 첫 주 관객", f"{int(result.get('opening_week_audience', 0)):,}명"),
            ("최종 관객 수", f"{result['final_audience']:,}명"),
            ("극장 매출", money(result["gross_revenue"])),
            ("투자자 회수", money(result.get("investor_recoup", 0))),
            ("제작사 순유입", money(net_receipts)),
            ("극장 손익분기점", f"{int(result.get('theatrical_break_even_audience', result['break_even_audience'])):,}명"),
            ("순손익분기점", f"{result['break_even_audience']:,}명"),
            ("자기자본 기준 수익/손실", money(result["profit"])),
            ("관객 반응", audience_reaction_text(result.get("audience_score"))),
            ("평론가 반응", critic_reaction_text(result.get("critic_score"))),
            ("입소문", word_of_mouth_text(result.get("word_of_mouth"))),
            ("2주차 흐름", drop_risk_text(result.get("second_week_drop"))),
            ("명성 변화", overall_change_text(result.get("fame_delta", 0))),
            ("명성 세부 변화", compact_reputation_changes(result.get("reputation_deltas", {}))),
            ("인맥 변화", compact_network_changes(result.get("network_deltas", {}))),
            ("2차 시장 수익", money(result["secondary_market_revenue"])),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index, 0)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            grid.addWidget(value_label, index, 1)
        layout.addLayout(grid)

        summary = QLabel(result["result_summary"])
        summary.setWordWrap(True)
        summary.setObjectName("PanelText")
        layout.addWidget(summary)

        rating_reasons = result.get("content_rating_reasons") or []
        if rating_reasons:
            rating_note = QLabel("심의 사유: " + " ".join(str(reason) for reason in rating_reasons))
            rating_note.setWordWrap(True)
            rating_note.setObjectName("PanelText")
            layout.addWidget(rating_note)

        button = QPushButton("대시보드로 복귀")
        button.setMinimumHeight(40)
        button.clicked.connect(on_continue)
        layout.addSpacing(12)
        layout.addWidget(button)
