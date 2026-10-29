from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from app.services.award_service import RESULT_LABELS, award_profile_text
from app.ui.media_widgets import award_logo_frame


class AwardsScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_award_profile: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.award_names = {award["id"]: award["name"] for award in state.get("awards", [])}

        layout = QVBoxLayout(self)
        title = QLabel("시상식")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)
        current_date = state.get("current_date") or {}
        if current_date:
            subtitle = QLabel(
                f"현재 게임 날짜 기준: {current_date.get('year')}년 {current_date.get('month')}월 · "
                "아직 일어나지 않은 수상 결과는 표시하지 않습니다."
            )
            subtitle.setWordWrap(True)
            subtitle.setObjectName("MutedText")
            layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._awards_tab(state.get("awards", []), on_award_profile), "시상식")
        tabs.addTab(self._results_tab(state.get("historical_results", [])), "역사 결과")
        tabs.addTab(self._results_tab(state.get("player_results", [])), "플레이어 작품")
        layout.addWidget(tabs)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    def _awards_tab(
        self,
        awards: list[dict[str, Any]],
        on_award_profile: Callable[[str], None],
    ) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        listing = QListWidget()
        for award in awards:
            founded = f"{award['foundedYear']}년 시작" if award.get("foundedYear") else "시작 연도 미상"
            profile = award.get("publicProfile") or {}
            label = f"{award['name']} · {founded}"
            if profile.get("oneLine"):
                label += f" · {profile['oneLine']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, award.get("id"))
            listing.addItem(item)
        if not awards:
            listing.addItem("등록된 시상식 없음")
        listing.itemClicked.connect(
            lambda item: on_award_profile(str(item.data(Qt.ItemDataRole.UserRole)))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        layout.addWidget(listing)
        return tab

    def _results_tab(self, results: list[dict[str, Any]]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        listing = QListWidget()
        for result in results:
            award_id = result.get("award_id") or result.get("awardId")
            award_name = self.award_names.get(award_id, award_id or "시상식")
            movie = result.get("winner_name") or result.get("winnerName") or result.get("work_title") or result.get("workTitle") or result.get("movie_id") or result.get("movieId") or "수상자 미상"
            when = str(result.get("year") or "연도 미상")
            if result.get("month"):
                when += f".{int(result['month'])}"
            listing.addItem(
                f"{when} · {award_name} · {result.get('category')} · "
                f"{RESULT_LABELS.get(str(result.get('result') or ''), result.get('result') or '-')} · {movie}"
            )
        if not results:
            listing.addItem("기록된 결과 없음")
        layout.addWidget(listing)
        return tab


class AwardProfileScreen(QWidget):
    def __init__(self, *, profile: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(str(profile.get("name") or "시상식 상세"))
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(award_logo_frame(profile.get("id")), alignment=Qt.AlignmentFlag.AlignTop)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(award_profile_text(profile))
        top_layout.addWidget(body, 1)
        layout.addWidget(top, 1)

        back_button = QPushButton("돌아가기")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)
