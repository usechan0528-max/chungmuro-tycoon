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
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money
from app.services.public_text_service import fame_level_text, network_level_text, reputation_level_text
from app.services.progression_service import STAGE_LABELS


class DashboardScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_new_film: Callable[[], None],
        on_advance_day: Callable[[], None],
        on_advance_to_next_schedule: Callable[[], None],
        on_theatrical_run: Callable[[str], None],
        on_world_boxoffice: Callable[[], None],
        on_movie_detail: Callable[[str], None],
        on_industry_database: Callable[[], None],
        on_people_database: Callable[[], None],
        on_finance: Callable[[], None],
        on_crew_work: Callable[[], None],
        on_franchise: Callable[[], None],
        on_player_profile: Callable[[], None],
        on_player_filmography: Callable[[], None],
        on_history_timeline: Callable[[], None],
        on_annual_report: Callable[[], None],
        on_press_and_critics: Callable[[], None],
        on_awards: Callable[[], None],
        on_display_settings: Callable[[], None],
        on_save_load: Callable[[], None],
        on_save: Callable[[], None],
        on_load: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__()
        self.state = state
        player = state["player"]
        studio = state["studio"]
        finance = state.get("finance") or {}
        studio_profile = (studio or {}).get("reputation_profile") or {}

        layout = QVBoxLayout(self)
        header = QLabel(
            f"{player['current_year']}년 {player['current_month']}월 {player.get('current_day', 1)}일"
            f" · {player['name']} · {player['position']}"
        )
        header.setObjectName("ScreenTitle")
        layout.addWidget(header)

        era_ui = state.get("era_ui") or {}
        if era_ui:
            era_box = QGroupBox(str(era_ui.get("dashboardTitle") or "오늘의 산업 감각"))
            era_layout = QVBoxLayout(era_box)
            era_headline = QLabel(str(era_ui.get("headline") or "현재 시대의 산업 환경을 바탕으로 운영 판단을 조정합니다."))
            era_headline.setWordWrap(True)
            era_headline.setObjectName("PanelText")
            era_layout.addWidget(era_headline)
            for line in (era_ui.get("dashboardLines") or [])[:4]:
                item = QLabel(f"- {line}")
                item.setWordWrap(True)
                era_layout.addWidget(item)
            layout.addWidget(era_box)

        metrics = QGroupBox("일일 운영 지표")
        grid = QGridLayout(metrics)
        reputation = player.get("reputation", {})
        network = player.get("network", {})
        pressure = finance.get("monthly_debt_pressure", {})
        values = [
            ("제작사", studio["studio_name"]),
            ("자기자본", money(finance.get("own_capital", studio["cash"]))),
            ("투자본 잔액", money(finance.get("investment_capital", 0))),
            ("대출금 미사용", money(finance.get("loan_capital", 0))),
            ("가용 현금", money(finance.get("cash", studio["cash"]))),
            ("대출잔액", money(finance.get("loan_balance", studio["debt"]))),
            ("추가 대출 가능", money(finance.get("available_credit", 0))),
            ("단일 프로젝트 감당 한도", money(finance.get("project_financing_capacity", 0))),
            ("다음 월 상환 압박", f"{money(pressure.get('nextDue', 0))} · {pressure.get('label', '대출 압박 없음')}"),
            ("제작사 명성", fame_level_text(studio["fame"])),
            ("제작사 평판", studio_profile.get("primaryLabel", "평판 형성 중")),
            ("업계 별칭", studio_profile.get("secondaryLabel", "아직 업계 별칭은 유동적")),
            ("대중 명성", reputation_level_text("public_reputation", reputation.get("public_reputation", 0))),
            ("업계 명성", reputation_level_text("industry_reputation", reputation.get("industry_reputation", 0))),
            ("투자자 명성", reputation_level_text("investor_reputation", reputation.get("investor_reputation", 0))),
            ("창작자 명성", reputation_level_text("creative_reputation", reputation.get("creative_reputation", 0))),
            ("배우 인맥", network_level_text("actor_network", network.get("actor_network", 0))),
            ("제작 인맥", network_level_text("production_network", network.get("production_network", 0))),
            ("투자 인맥", network_level_text("investor_network", network.get("investor_network", 0))),
            ("배급 인맥", network_level_text("distribution_network", network.get("distribution_network", 0))),
        ]
        for index, (label, value) in enumerate(values):
            row = index // 2
            col = (index % 2) * 2
            grid.addWidget(QLabel(label), row, col)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            grid.addWidget(value_label, row, col + 1)
        layout.addWidget(metrics)

        reputation_box = QGroupBox("제작사 평판")
        reputation_layout = QVBoxLayout(reputation_box)
        reputation_title = QLabel(
            f"{studio_profile.get('primaryLabel', '평판 형성 중')} · "
            f"{studio_profile.get('secondaryLabel', '아직 업계 별칭은 유동적')}"
        )
        reputation_title.setObjectName("SectionTitle")
        reputation_layout.addWidget(reputation_title)
        reputation_summary = QLabel(
            studio_profile.get(
                "summary",
                "아직 반복된 현장 기록이 없어 사람들은 다음 작품과 계약 태도를 지켜보고 있습니다.",
            )
        )
        reputation_summary.setWordWrap(True)
        reputation_layout.addWidget(reputation_summary)
        for signal in (studio_profile.get("signals") or [])[:4]:
            signal_label = QLabel(f"- {signal}")
            signal_label.setWordWrap(True)
            reputation_layout.addWidget(signal_label)
        layout.addWidget(reputation_box)

        news_box = QGroupBox("뉴스피드")
        news_layout = QVBoxLayout(news_box)
        news_list = QListWidget()
        for news in state.get("news_feed", []):
            news_list.addItem(_news_line(news))
        if not state.get("news_feed"):
            news_list.addItem("아직 들어온 소식 없음")
        news_layout.addWidget(news_list)
        layout.addWidget(news_box)

        release_box = QGroupBox("내 개봉작 근황")
        release_layout = QVBoxLayout(release_box)
        release_list = QListWidget()
        active_runs = state.get("theatrical_runs", [])
        for run in active_runs:
            current_day = int(run.get("current_day", 0) or 0)
            max_days = int(run.get("max_days", 0) or 0)
            daily_audience = int(run.get("latest_daily_audience", 0) or 0)
            cumulative_audience = int(run.get("cumulative_audience", 0) or 0)
            projected_audience = int(run.get("projected_final_audience", 0) or 0)
            break_even = int(run.get("break_even_audience", 0) or 0)
            if current_day > 0:
                headline = (
                    f"{run['title']} · {current_day}/{max_days}일차 · "
                    f"오늘 {daily_audience:,}명 · 누적 {cumulative_audience:,}명 · "
                    f"{run.get('pace_label', '상영 중')}"
                )
            else:
                headline = f"{run['title']} · 개봉 대기 · 예상 {projected_audience:,}명"
            item = QListWidgetItem(headline)
            item.setData(Qt.ItemDataRole.UserRole, run.get("id"))
            item.setToolTip(
                f"장르: {run.get('genre_name', '-')}\n"
                f"규모: {run.get('scale_name', '-')}\n"
                f"최근 집계일: {run.get('latest_date', '-')}\n"
                f"누적 매출: {money(run.get('cumulative_revenue', 0))}\n"
                f"예상 최종 관객: {int(run.get('forecast_final_audience', 0) or 0):,}명\n"
                f"현재 페이스 예상: {projected_audience:,}명\n"
                f"손익분기점: {break_even:,}명"
            )
            release_list.addItem(item)
        if not active_runs:
            release_list.addItem("현재 상영 중인 내 작품 없음")
        release_list.itemClicked.connect(
            lambda item: on_theatrical_run(str(item.data(Qt.ItemDataRole.UserRole)))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        release_layout.addWidget(release_list)
        layout.addWidget(release_box)

        calendar_box = QGroupBox("이번 달 제작 달력")
        calendar_layout = QVBoxLayout(calendar_box)
        calendar_list = QListWidget()
        for event in state.get("calendar_events", []):
            calendar_list.addItem(_calendar_line(event))
        if not state.get("calendar_events"):
            calendar_list.addItem("등록된 일정 없음")
        calendar_layout.addWidget(calendar_list)
        layout.addWidget(calendar_box)

        lists = QGridLayout()
        active_box = QGroupBox("진행 중 프로젝트")
        active_layout = QVBoxLayout(active_box)
        active_list = QListWidget()
        for project in state["projects"]:
            active_list.addItem(
                f"{project['title']} · {project['genre_name']} · {project['scale_name']} · "
                f"{STAGE_LABELS.get(project['stage'], project['stage'])}"
            )
        if not state["projects"]:
            active_list.addItem("진행 중인 프로젝트 없음")
        active_layout.addWidget(active_list)
        for run in state.get("theatrical_runs", []):
            active_list.addItem(
                f"[1차 시장] {run['title']} · {run.get('genre_name') or '-'} · "
                f"{int(run.get('current_day', 0) or 0)}/{int(run.get('max_days', 0) or 0)}일차"
            )

        completed_box = QGroupBox("개봉 결과 기록")
        completed_layout = QVBoxLayout(completed_box)
        completed_list = QListWidget()
        for film in state["completed_films"]:
            item = QListWidgetItem(
                f"{film['title']} · {film['final_audience']:,}명 · 관객 {film['audience_score']} · 평론 {film['critic_score']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, film["id"])
            completed_list.addItem(item)
        if not state["completed_films"]:
            completed_list.addItem("개봉작 없음")
        completed_list.itemClicked.connect(
            lambda item: on_movie_detail(str(item.data(Qt.ItemDataRole.UserRole)))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        completed_layout.addWidget(completed_list)
        lists.addWidget(active_box, 0, 0)
        lists.addWidget(completed_box, 0, 1)
        layout.addLayout(lists)

        action_groups = QGridLayout()
        new_film_button = QPushButton("신규 프로젝트 기획")
        next_day_button = QPushButton("진행하기")
        next_schedule_button = QPushButton("다음 일정으로")
        theatrical_button = QPushButton("상영 중 프로젝트")
        world_boxoffice_button = QPushButton("시장 박스오피스")
        industry_button = QPushButton("산업 데이터베이스")
        people_button = QPushButton("인물 데이터베이스")
        finance_button = QPushButton("재무/대출")
        crew_work_button = QPushButton("현장 일거리")
        franchise_button = QPushButton("시리즈/IP")
        player_profile_button = QPushButton("내 프로필")
        filmography_button = QPushButton("제작 필모그래피")
        history_button = QPushButton("역사 타임라인")
        annual_report_button = QPushButton("연간 산업 리포트")
        press_button = QPushButton("언론/평론 리포트")
        awards_button = QPushButton("시상식 기록")
        display_button = QPushButton("화면 설정")
        save_load_button = QPushButton("세이브/로드")
        save_button = QPushButton("저장")
        load_button = QPushButton("불러오기")
        quit_button = QPushButton("종료")
        new_film_button.clicked.connect(on_new_film)
        next_day_button.clicked.connect(on_advance_day)
        next_schedule_button.clicked.connect(on_advance_to_next_schedule)
        if state.get("theatrical_runs"):
            theatrical_button.clicked.connect(lambda: on_theatrical_run(str(state["theatrical_runs"][0]["id"])))
        else:
            theatrical_button.setEnabled(False)
        world_boxoffice_button.clicked.connect(on_world_boxoffice)
        industry_button.clicked.connect(on_industry_database)
        people_button.clicked.connect(on_people_database)
        finance_button.clicked.connect(on_finance)
        crew_work_button.clicked.connect(on_crew_work)
        franchise_button.clicked.connect(on_franchise)
        player_profile_button.clicked.connect(on_player_profile)
        filmography_button.clicked.connect(on_player_filmography)
        history_button.clicked.connect(on_history_timeline)
        annual_report_button.clicked.connect(on_annual_report)
        press_button.clicked.connect(on_press_and_critics)
        awards_button.clicked.connect(on_awards)
        display_button.clicked.connect(on_display_settings)
        save_load_button.clicked.connect(on_save_load)
        save_button.clicked.connect(on_save)
        load_button.clicked.connect(on_load)
        quit_button.clicked.connect(on_quit)
        action_groups.addWidget(
            _button_group(
                "진행",
                [
                    next_day_button,
                    next_schedule_button,
                    theatrical_button,
                    world_boxoffice_button,
                ],
            ),
            0,
            0,
        )
        action_groups.addWidget(
            _button_group(
                "제작/자금",
                [
                    new_film_button,
                    finance_button,
                    crew_work_button,
                    franchise_button,
                ],
            ),
            0,
            1,
        )
        action_groups.addWidget(
            _button_group(
                "인물/산업",
                [
                    people_button,
                    industry_button,
                    press_button,
                    awards_button,
                ],
            ),
            1,
            0,
        )
        action_groups.addWidget(
            _button_group(
                "기록/시스템",
                [
                    player_profile_button,
                    filmography_button,
                    history_button,
                    annual_report_button,
                    display_button,
                    save_load_button,
                    save_button,
                    load_button,
                    quit_button,
                ],
                columns=3,
            ),
            1,
            1,
        )
        action_groups.setColumnStretch(0, 1)
        action_groups.setColumnStretch(1, 1)
        layout.addLayout(action_groups)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)


def _calendar_line(event: dict[str, Any]) -> str:
    start = f"{event['month']}/{event['day']}"
    end_month = event.get("end_month") or event["month"]
    end_day = event.get("end_day") or event["day"]
    if int(end_month) == int(event["month"]) and int(end_day) == int(event["day"]):
        date_text = start
    else:
        date_text = f"{start}~{end_month}/{end_day}"
    type_label = {
        "career_start": "커리어",
        "project_created": "기획",
        "planned_stage": "예정",
        "planned_release": "개봉 예정",
        "stage_progress": "진행",
        "production": "이벤트",
        "dialogue": "대화",
        "release_result": "개봉",
        "theatrical_release_start": "개봉",
        "first_market_complete": "정산",
        "crew_work": "현장",
    }.get(str(event.get("event_type")), str(event.get("event_type") or "일정"))
    return f"{date_text} · {type_label} · {event['title']}"


def _news_line(news: dict[str, Any]) -> str:
    day = int(news.get("day") or 1)
    date_text = f"{int(news.get('year'))}.{int(news.get('month')):02d}.{day:02d}"
    source = news.get("source_label") or news.get("source_type") or "소식"
    reaction = _news_reaction_preview(news)
    if reaction:
        return f"{date_text} · {source} · {news.get('title', '')} — {reaction}"
    return f"{date_text} · {source} · {news.get('title', '')}"


def _news_reaction_preview(news: dict[str, Any]) -> str:
    reactions = news.get("reactions") or []
    if not reactions:
        return ""
    first = reactions[0]
    return f"{first.get('group', '반응')}: {first.get('text', '')}"


def _button_group(title: str, buttons: list[QPushButton], *, columns: int = 2) -> QGroupBox:
    box = QGroupBox(title)
    grid = QGridLayout(box)
    for index, button in enumerate(buttons):
        button.setMinimumHeight(36)
        grid.addWidget(button, index // columns, index % columns)
    for column in range(columns):
        grid.setColumnStretch(column, 1)
    return box
