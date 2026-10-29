from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME
from app.services import save_service
from app.services.award_service import get_award_profile
from app.services.boxoffice_service import (
    advance_theatrical_day,
    get_theatrical_run_state,
    release_project,
    start_theatrical_run,
)
from app.services.character_service import create_new_character
from app.services.crew_work_service import get_crew_work_state
from app.services.crew_work_service import perform_crew_work as perform_crew_work_service
from app.services.casting_service import (
    casting_confirmation_status,
    confirm_project_casting,
    default_actor_commitment_for_project,
    discover_generated_actor_candidates,
    get_casting_discovery_options,
    get_project_casting,
    list_pending_casting_offers,
    list_unseen_casting_responses,
    list_casting_candidates,
    mark_casting_responses_seen,
    submit_casting_offer,
    update_casting_contract,
)
from app.services.event_service import get_event_for_project
from app.services.finance_service import borrow as borrow_money_service
from app.services.finance_service import get_finance_state, repay_loan
from app.services.film_service import advance_project_stage as advance_project_stage_service
from app.services.film_service import apply_event_choice, create_project, get_project
from app.services.era_ui_service import era_ui_profile
from app.services.franchise_service import apply_franchise_choice, list_franchise_offers
from app.services.game_state import GameStateService
from app.services.movie_detail_service import get_movie_detail
from app.services.organization_service import get_organization_profile
from app.services.player_profile_service import get_player_profile
from app.services.production_management_service import get_project_operations_state
from app.ui.annual_report import AnnualReportScreen
from app.ui.awards_screen import AwardProfileScreen, AwardsScreen
from app.ui.box_office_result import BoxOfficeResultScreen
from app.ui.budget_allocation import BudgetAllocationScreen
from app.ui.casting_screen import CastingScreen
from app.ui.character_creation import CharacterCreationScreen
from app.ui.crew_work_screen import CrewWorkScreen
from app.ui.dashboard import DashboardScreen
from app.ui.film_planning import FilmPlanningScreen
from app.ui.finance_screen import FinanceScreen
from app.ui.franchise_screen import FranchiseScreen
from app.ui.history_timeline import HistoryTimelineScreen
from app.ui.industry_database import IndustryDatabaseScreen, OrganizationProfileScreen
from app.services.people_service import get_critic_profile, get_person_profile
from app.ui.movie_detail import MovieDetailScreen
from app.ui.people_database import CriticProfileScreen, PeopleDatabaseScreen, PersonProfileScreen
from app.ui.player_filmography import PlayerFilmographyScreen
from app.ui.press_and_critics import PressAndCriticsScreen
from app.ui.production_progress import ProductionProgressScreen
from app.ui.save_load import SaveLoadScreen
from app.ui.start_screen import StartScreen
from app.ui.theatrical_run import TheatricalRunScreen
from app.ui.theme import REPORT_STYLE_SHEET
from app.ui.world_boxoffice import WorldBoxOfficeScreen


DISPLAY_PRESETS = (
    ("1280 x 720", (1280, 720)),
    ("1600 x 900", (1600, 900)),
    ("1920 x 1080", (1920, 1080)),
)
SCREEN_CONTENT_MAX_WIDTH = 1440


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 720)
        self.setMinimumSize(1060, 640)
        self.game_state = GameStateService()
        self.active_save_slot = 1
        self.discovery_actor_ids_by_project: dict[str, list[str]] = {}
        self.stack = QStackedWidget()
        self.stack.setObjectName("AppStack")
        self.setCentralWidget(self.stack)
        self.setStyleSheet(REPORT_STYLE_SHEET)
        self._install_shortcuts()
        self.show_start()

    def show_start(self) -> None:
        self._set_screen(
            StartScreen(
                can_load=save_service.has_any_save(),
                on_new_game=self.show_character_creation,
                on_load=self.load_and_show_dashboard,
                on_view_db=self.show_database_dialog,
                on_display_settings=self.show_display_settings_dialog,
                on_quit=self.close,
            )
        )

    def show_main_screen(self) -> None:
        if self.game_state.get_dashboard_state().get("player"):
            self.show_dashboard()
        else:
            self.show_start()

    def show_character_creation(self) -> None:
        self._set_screen(
            CharacterCreationScreen(
                references=self.game_state.get_reference_data(),
                on_submit=self.start_new_game,
                on_cancel=self.show_start,
            )
        )

    def start_new_game(self, data: dict[str, Any]) -> None:
        try:
            self.active_save_slot = 1
            save_service.start_new_runtime(slot=self.active_save_slot)
            create_new_character(data)
            save_service.save_game(slot=self.active_save_slot)
            self.show_dashboard()
        except Exception as exc:
            QMessageBox.critical(self, "새 게임 실패", str(exc))

    def show_dashboard(self) -> None:
        state = self.game_state.get_dashboard_state()
        if not state["player"]:
            self.show_start()
            return
        self._set_screen(
            DashboardScreen(
                state=state,
                on_new_film=self.show_film_creation,
                on_advance_day=self.advance_day,
                on_advance_to_next_schedule=self.advance_to_next_schedule,
                on_theatrical_run=self.show_theatrical_market,
                on_world_boxoffice=self.show_world_boxoffice,
                on_movie_detail=lambda movie_id: self.show_movie_detail(movie_id, self.show_dashboard),
                on_industry_database=self.show_industry_database,
                on_people_database=self.show_people_database,
                on_finance=self.show_finance,
                on_crew_work=self.show_crew_work,
                on_franchise=self.show_franchise,
                on_player_profile=self.show_player_profile,
                on_player_filmography=self.show_player_filmography,
                on_history_timeline=self.show_history_timeline,
                on_annual_report=self.show_annual_report,
                on_press_and_critics=self.show_press_and_critics,
                on_awards=self.show_awards,
                on_display_settings=self.show_display_settings_dialog,
                on_save_load=self.show_save_load,
                on_save=self.save_game,
                on_load=self.load_and_show_dashboard,
                on_quit=self.close,
            )
        )

    def show_crew_work(self) -> None:
        self._set_screen(
            CrewWorkScreen(
                state=get_crew_work_state(),
                on_select_work=self.perform_crew_work,
                on_back=self.show_dashboard,
            )
        )

    def perform_crew_work(self, work_id: str) -> None:
        try:
            result = perform_crew_work_service(work_id)
            save_service.save_game(slot=self.active_save_slot)
            self._show_pending_history_popups()
            QMessageBox.information(self, "현장 일거리", result.get("summary", "현장 경험이 반영되었습니다."))
            interrupted_project_id = result.get("interruptedProjectId")
            if interrupted_project_id:
                self.show_production(str(interrupted_project_id))
                return
            self.show_crew_work()
        except Exception as exc:
            QMessageBox.critical(self, "현장 일거리 실패", str(exc))

    def show_finance(self) -> None:
        self._set_screen(
            FinanceScreen(
                state=get_finance_state(),
                on_borrow=self.borrow_money,
                on_repay=self.repay_money,
                on_back=self.show_dashboard,
            )
        )

    def borrow_money(self, amount: int, term_months: int) -> None:
        try:
            borrow_money_service(amount, term_months=term_months)
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(self, "대출 실행", "대출금이 가용 현금에 반영되었습니다.")
            self.show_finance()
        except Exception as exc:
            QMessageBox.critical(self, "대출 실패", str(exc))

    def repay_money(self, amount: int) -> None:
        try:
            repay_loan(amount)
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(self, "상환 완료", "대출 원금 상환이 반영되었습니다.")
            self.show_finance()
        except Exception as exc:
            QMessageBox.critical(self, "상환 실패", str(exc))

    def show_film_creation(self, initial_data: dict[str, Any] | None = None) -> None:
        self._set_screen(
            FilmPlanningScreen(
                references=self.game_state.get_reference_data(),
                on_submit=self.show_budget_allocation,
                on_cancel=self.show_dashboard,
                initial_data=initial_data,
            )
        )

    def show_budget_allocation(self, planning_data: dict[str, Any]) -> None:
        self._set_screen(
            BudgetAllocationScreen(
                references=self.game_state.get_reference_data(),
                planning_data=planning_data,
                on_submit=self.start_project,
                on_back=self.show_film_creation,
            )
        )

    def start_project(self, data: dict[str, Any]) -> None:
        try:
            project_id = create_project(**data)
            self.show_production(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "프로젝트 생성 실패", str(exc))

    def show_production(self, project_id: str) -> None:
        project = get_project(project_id)
        if not project:
            QMessageBox.warning(self, "프로젝트 없음", "진행 중인 프로젝트를 찾을 수 없습니다.")
            self.show_dashboard()
            return
        event = get_event_for_project(project_id)
        operations = get_project_operations_state(project_id)
        self._set_screen(
            ProductionProgressScreen(
                project=project,
                event=event,
                operations=operations,
                era_ui=self._current_era_ui(),
                on_choice=lambda current_event, choice: self.resolve_production_choice(project_id, current_event, choice),
                on_advance_stage=lambda: self.advance_project_stage(project_id),
                on_release=lambda: self.start_theatrical_market(project_id),
                on_casting=lambda: self.show_casting(project_id),
                on_cancel=self.show_dashboard,
            )
        )

    def show_casting(self, project_id: str) -> None:
        try:
            actors = list_casting_candidates("actor")
            discovery_ids = self.discovery_actor_ids_by_project.get(project_id, [])
            discovery_results = [
                actor for actor in actors if actor.get("id") in set(discovery_ids)
            ]
            self._set_screen(
                CastingScreen(
                    state={
                        "actors": actors,
                        "directors": list_casting_candidates("director"),
                        "current": get_project_casting(project_id),
                        "pending_offers": list_pending_casting_offers(project_id),
                        "confirmation": casting_confirmation_status(project_id),
                        "discovery_options": get_casting_discovery_options(project_id),
                        "discovery_results": discovery_results,
                        "default_actor_commitment": default_actor_commitment_for_project(project_id),
                        "era_ui": self._current_era_ui(),
                    },
                    on_attach=lambda person_id, role, options: self.resolve_casting_contract(
                        project_id,
                        person_id,
                        role,
                        options,
                    ),
                    on_update=lambda person_id, role, options: self.resolve_casting_contract_update(
                        project_id,
                        person_id,
                        role,
                        options,
                    ),
                    on_discover=lambda option_id, budget: self.resolve_actor_discovery(project_id, option_id, budget),
                    on_confirm=lambda: self.resolve_casting_confirmation(project_id),
                    era_ui=self._current_era_ui(),
                    on_back=lambda: self.show_production(project_id),
                    back_label="제작 화면으로",
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "캐스팅 조회 실패", str(exc))
            self.show_production(project_id)

    def resolve_casting_contract(
        self,
        project_id: str,
        person_id: str,
        role: str,
        options: dict[str, Any],
    ) -> None:
        try:
            result = submit_casting_offer(
                project_id,
                person_id,
                role,
                contract_fee=int(options.get("contract_fee", 0) or 0),
                commitment_months=int(options.get("commitment_months", 0) or 0),
                sequel_option=bool(options.get("sequel_option")),
                promotion_obligation=bool(options.get("promotion_obligation")),
                promotion_days=int(options.get("promotion_days", 0) or 0),
                contract_terms=options.get("contract_terms") or {},
            )
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(self, "캐스팅 제안 발송", str(result.get("result_text") or "상대 측에 캐스팅 제안을 보냈습니다."))
            self.show_casting(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "캐스팅 계약 실패", str(exc))

    def resolve_casting_contract_update(
        self,
        project_id: str,
        person_id: str,
        role: str,
        options: dict[str, Any],
    ) -> None:
        try:
            update_casting_contract(
                project_id,
                person_id,
                role,
                contract_fee=int(options.get("contract_fee", 0) or 0),
                commitment_months=int(options.get("commitment_months", 0) or 0),
                sequel_option=bool(options.get("sequel_option")),
                promotion_obligation=bool(options.get("promotion_obligation")),
                promotion_days=int(options.get("promotion_days", 0) or 0),
                contract_terms=options.get("contract_terms") or {},
            )
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(self, "계약 수정", "수정된 계약 조건이 프로젝트에 반영되었습니다.")
            self.show_casting(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "계약 수정 실패", str(exc))

    def resolve_casting_confirmation(self, project_id: str) -> None:
        try:
            status = confirm_project_casting(project_id)
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(self, "출연진 확정", str(status.get("summary") or "공식 출연진을 확정했습니다."))
            self.show_casting(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "출연진 확정 실패", str(exc))

    def resolve_actor_discovery(self, project_id: str, option_id: str, budget: int) -> None:
        try:
            generated = discover_generated_actor_candidates(project_id, option_id, budget)
            self.discovery_actor_ids_by_project[project_id] = [str(actor["id"]) for actor in generated]
            save_service.save_game(slot=self.active_save_slot)
            names = ", ".join(actor["nameKo"] for actor in generated[:6])
            QMessageBox.information(
                self,
                "신인 발굴",
                f"새 후보 {len(generated)}명이 카드 후보로 정리되었습니다.\n{names}",
            )
            self.show_casting(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "신인 발굴 실패", str(exc))

    def resolve_production_choice(
        self,
        project_id: str,
        event: dict[str, Any] | None,
        choice: dict[str, Any],
    ) -> None:
        try:
            result = apply_event_choice(project_id, choice, event)
            QMessageBox.information(
                self,
                "선택 결과",
                result.get("outcome_summary", "선택의 결과가 내부 상태에 반영되었습니다."),
            )
            self._show_pending_casting_response_popups()
            self.show_production(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "이벤트 처리 실패", str(exc))

    def advance_project_stage(self, project_id: str) -> None:
        try:
            advance_project_stage_service(project_id)
            self._show_pending_casting_response_popups()
            save_service.save_game(slot=self.active_save_slot)
            self._show_pending_history_popups()
            self.show_production(project_id)
        except Exception as exc:
            QMessageBox.critical(self, "단계 진행 실패", str(exc))

    def show_result(self, project_id: str) -> None:
        try:
            result = release_project(project_id)
            self._show_pending_casting_response_popups()
            self._set_screen(BoxOfficeResultScreen(result=result, on_continue=self.show_dashboard))
        except Exception as exc:
            QMessageBox.critical(self, "개봉 계산 실패", str(exc))
            self.show_dashboard()

    def start_theatrical_market(self, project_id: str) -> None:
        try:
            state = start_theatrical_run(project_id)
            self._show_pending_casting_response_popups()
            save_service.save_game(slot=self.active_save_slot)
            self._show_theatrical_run_state(state)
        except Exception as exc:
            QMessageBox.critical(self, "1차 시장 시작 실패", str(exc))
            self.show_dashboard()

    def show_theatrical_market(self, run_id: str) -> None:
        try:
            self._show_theatrical_run_state(get_theatrical_run_state(run_id))
        except Exception as exc:
            QMessageBox.critical(self, "1차 시장 조회 실패", str(exc))
            self.show_dashboard()

    def advance_theatrical_market_day(self, run_id: str) -> None:
        try:
            state = advance_theatrical_day(run_id)
            self._show_pending_casting_response_popups()
            save_service.save_game(slot=self.active_save_slot)
            self._show_pending_history_popups()
            self._show_theatrical_run_state(state)
        except Exception as exc:
            QMessageBox.critical(self, "상영일 진행 실패", str(exc))

    def show_theatrical_market_result(self, run_id: str) -> None:
        try:
            state = get_theatrical_run_state(run_id)
            if state.get("status") != "completed":
                QMessageBox.information(self, "정산 대기", "극장 1차 시장이 아직 종료되지 않았습니다.")
                self._show_theatrical_run_state(state)
                return
            result = state.get("final_result") or {}
            self._set_screen(BoxOfficeResultScreen(result=result, on_continue=self.show_dashboard))
        except Exception as exc:
            QMessageBox.critical(self, "정산 보고 실패", str(exc))
            self.show_dashboard()

    def _show_theatrical_run_state(self, state: dict[str, Any]) -> None:
        run_id = str(state["id"])
        self._set_screen(
            TheatricalRunScreen(
                state=state,
                on_next_day=lambda: self.advance_theatrical_market_day(run_id),
                on_show_result=lambda: self.show_theatrical_market_result(run_id),
                on_back=self.show_dashboard,
            )
        )

    def show_people_database(self) -> None:
        self._set_screen(
            PeopleDatabaseScreen(
                state=self.game_state.get_people_database_state(),
                on_person_profile=self.show_person_profile,
                on_critic_profile=self.show_critic_profile,
                on_back=self.show_dashboard,
            )
        )

    def show_person_profile(self, person_id: str) -> None:
        try:
            player = self.game_state.get_dashboard_state().get("player") or {}
            year = int(player.get("current_year") or 2026)
            month = int(player.get("current_month") or 12)
            self._set_screen(
                PersonProfileScreen(
                    profile=get_person_profile(person_id, year, month),
                    on_back=self.show_people_database,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "프로필 조회 실패", str(exc))

    def _current_era_ui(self) -> dict[str, Any]:
        player = self.game_state.get_dashboard_state().get("player") or {}
        return era_ui_profile(int(player.get("current_year") or 2026))

    def show_critic_profile(self, critic_id: str) -> None:
        try:
            self._set_screen(
                CriticProfileScreen(
                    profile=get_critic_profile(critic_id),
                    on_back=self.show_people_database,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "평론가 프로필 조회 실패", str(exc))

    def show_player_profile(self) -> None:
        try:
            self._set_screen(
                PersonProfileScreen(
                    profile=get_player_profile(),
                    on_back=self.show_dashboard,
                    back_label="대시보드로",
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "내 프로필 조회 실패", str(exc))

    def show_player_filmography(self) -> None:
        self._set_screen(
            PlayerFilmographyScreen(
                state=self.game_state.get_player_filmography_state(),
                on_movie_detail=lambda movie_id: self.show_movie_detail(movie_id, self.show_player_filmography),
                on_back=self.show_dashboard,
            )
        )

    def show_franchise(self) -> None:
        self._set_screen(
            FranchiseScreen(
                offers=list_franchise_offers(),
                on_choice=self.resolve_franchise_choice,
                on_back=self.show_dashboard,
            )
        )

    def resolve_franchise_choice(self, ip_id: str, event: dict[str, Any], choice: dict[str, Any]) -> None:
        try:
            result = apply_franchise_choice(ip_id, event, choice)
            save_service.save_game(slot=self.active_save_slot)
            QMessageBox.information(
                self,
                "시리즈/IP 결정",
                result.get("outcome_summary", "시리즈/IP 결정이 반영되었습니다."),
            )
            project_seed = result.get("project_seed")
            if project_seed:
                self.show_film_creation(project_seed)
                return
            self.show_franchise()
        except Exception as exc:
            QMessageBox.critical(self, "시리즈화 실패", str(exc))

    def show_history_timeline(self) -> None:
        self._set_screen(
            HistoryTimelineScreen(
                state=self.game_state.get_history_timeline_state(),
                on_organization_profile=lambda org_id: self.show_organization_profile(org_id, self.show_history_timeline),
                on_back=self.show_dashboard,
            )
        )

    def show_annual_report(self) -> None:
        self._set_screen(
            AnnualReportScreen(
                state=self.game_state.get_annual_report_state(),
                on_back=self.show_dashboard,
            )
        )

    def show_world_boxoffice(self) -> None:
        self._set_screen(
            WorldBoxOfficeScreen(
                state=self.game_state.get_world_boxoffice_state(),
                on_movie_detail=lambda movie_id: self.show_movie_detail(movie_id, self.show_world_boxoffice),
                on_back=self.show_dashboard,
            )
        )

    def show_industry_database(self) -> None:
        self._set_screen(
            IndustryDatabaseScreen(
                state=self.game_state.get_industry_database_state(),
                on_organization_profile=lambda org_id: self.show_organization_profile(org_id, self.show_industry_database),
                on_back=self.show_dashboard,
            )
        )

    def show_organization_profile(self, org_id: str, on_back: Any | None = None) -> None:
        try:
            player = self.game_state.get_dashboard_state().get("player") or {}
            year = int(player.get("current_year") or 1980)
            month = int(player.get("current_month") or 1)
            self._set_screen(
                OrganizationProfileScreen(
                    profile=get_organization_profile(org_id, until_year=year, until_month=month),
                    on_back=on_back or self.show_industry_database,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "산업 주체 상세 조회 실패", str(exc))

    def show_movie_detail(self, movie_id: str, on_back: Any | None = None) -> None:
        try:
            self._set_screen(
                MovieDetailScreen(
                    detail=get_movie_detail(movie_id),
                    on_back=on_back or self.show_dashboard,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "영화 상세 조회 실패", str(exc))

    def show_press_and_critics(self) -> None:
        self._set_screen(
            PressAndCriticsScreen(
                state=self.game_state.get_press_and_critics_state(),
                on_back=self.show_dashboard,
            )
        )

    def show_awards(self) -> None:
        self._set_screen(
            AwardsScreen(
                state=self.game_state.get_awards_state(),
                on_award_profile=lambda award_id: self.show_award_profile(award_id, self.show_awards),
                on_back=self.show_dashboard,
            )
        )

    def show_award_profile(self, award_id: str, on_back: Any | None = None) -> None:
        try:
            player = self.game_state.get_dashboard_state().get("player") or {}
            year = int(player.get("current_year") or 1980)
            month = int(player.get("current_month") or 1)
            self._set_screen(
                AwardProfileScreen(
                    profile=get_award_profile(award_id, until_year=year, until_month=month),
                    on_back=on_back or self.show_awards,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "시상식 상세 조회 실패", str(exc))

    def show_save_load(self) -> None:
        self._set_screen(
            SaveLoadScreen(
                slots=save_service.list_save_slots(),
                on_save_slot=lambda slot: self.save_game(slot=slot, refresh_save_screen=True),
                on_load_slot=self.load_and_show_dashboard,
                on_back=self.show_dashboard,
            )
        )

    def save_game(self, slot: int | None = None, *, refresh_save_screen: bool = False) -> None:
        selected_slot = slot or self.active_save_slot
        try:
            path = save_service.save_game(slot=selected_slot)
            self.active_save_slot = selected_slot
            QMessageBox.information(self, "저장 완료", f"슬롯 {selected_slot:03d}에 저장했습니다.\n{path}")
            if refresh_save_screen:
                self.show_save_load()
        except Exception as exc:
            QMessageBox.critical(self, "저장 실패", str(exc))

    def load_and_show_dashboard(self, slot: int | None = None) -> None:
        try:
            selected_slot = slot or save_service.latest_save_slot()
            if selected_slot is None:
                raise FileNotFoundError("저장 파일이 없습니다.")
            save_service.load_game(slot=selected_slot)
            self.active_save_slot = selected_slot
            self.show_dashboard()
        except FileNotFoundError:
            QMessageBox.warning(self, "불러오기 실패", "저장 파일이 없습니다.")
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))

    def advance_day(self) -> None:
        try:
            self.game_state.advance_day()
            self._show_pending_casting_response_popups()
            save_service.save_game(slot=self.active_save_slot)
            self._show_pending_history_popups()
            self.show_dashboard()
        except Exception as exc:
            QMessageBox.critical(self, "진행 실패", str(exc))

    def advance_to_next_schedule(self) -> None:
        try:
            result = self.game_state.advance_to_next_schedule_or_project_event()
            self._show_pending_casting_response_popups()
            save_service.save_game(slot=self.active_save_slot)
            self._show_pending_history_popups()
            days = int(result.get("days", 0))
            if result.get("reason") == "project_event":
                if days > 0:
                    QMessageBox.information(self, "제작 이벤트 발생", f"{days}일이 지난 뒤 제작 변수가 발생했습니다.")
                self.show_production(str(result["project_id"]))
                return
            if result.get("reason") == "calendar_event":
                QMessageBox.information(self, "일정 진행", f"{days}일이 지나 다음 일정 날짜에 도착했습니다.")
            else:
                QMessageBox.information(self, "일정 진행", "예정된 일정이 없어 하루를 진행했습니다.")
            self.show_dashboard()
        except Exception as exc:
            QMessageBox.critical(self, "일정 진행 실패", str(exc))

    def _show_pending_casting_response_popups(self) -> None:
        responses = list_unseen_casting_responses(limit=12)
        if not responses:
            return
        accepted = [item for item in responses if item.get("accepted")]
        rejected = [item for item in responses if item.get("accepted") is False]
        dialog = QDialog(self)
        dialog.setWindowTitle("캐스팅 답변 도착")
        dialog.resize(660, 460)
        layout = QVBoxLayout(dialog)

        header = QLabel("상대 측에서 캐스팅 제안에 대한 답변을 보내왔습니다.")
        header.setObjectName("ScreenTitle")
        layout.addWidget(header)

        summary = QLabel(f"수락 {len(accepted)}건 · 보류/거절 {len(rejected)}건")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        detail = QTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(_format_casting_response_popup_text(responses))
        layout.addWidget(detail)

        button = QPushButton("확인")
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)
        dialog.exec()
        mark_casting_responses_seen([str(item["id"]) for item in responses])

    def _show_pending_history_popups(self) -> None:
        from app.services.news_service import list_pending_history_popups, mark_history_popups_seen

        popups = list_pending_history_popups(limit=12)
        if not popups:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("역사적 사건 발생")
        dialog.resize(640, 440)
        layout = QVBoxLayout(dialog)

        header = QLabel("게임 세계에 역사적 사건이 발생했습니다.")
        header.setObjectName("ScreenTitle")
        layout.addWidget(header)

        detail = QTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(_format_history_popup_text(popups))
        layout.addWidget(detail)

        button = QPushButton("확인")
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)
        dialog.exec()
        mark_history_popups_seen([int(item["id"]) for item in popups])

    def show_database_dialog(self) -> None:
        counts = self.game_state.get_database_counts()
        dialog = QDialog(self)
        dialog.setWindowTitle("DB 보기")
        layout = QVBoxLayout(dialog)
        title = QLabel("SQLite 데이터 현황")
        title.setObjectName("SectionTitle")
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(f"{table}: {count}" for table, count in counts.items()))
        close_button = QPushButton("닫기")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addWidget(close_button)
        dialog.resize(420, 360)
        dialog.exec()

    def show_display_settings_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("화면 설정")
        layout = QVBoxLayout(dialog)

        title = QLabel("화면 크기")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        description = QLabel("창 크기를 고르거나 전체 화면으로 전환합니다. F11은 전체 화면 전환, Esc는 창 모드 복귀입니다.")
        description.setWordWrap(True)
        layout.addWidget(description)

        combo = QComboBox()
        for label, size in DISPLAY_PRESETS:
            combo.addItem(label, size)
        layout.addWidget(combo)

        apply_button = QPushButton("선택한 해상도 적용")
        fullscreen_button = QPushButton("전체 화면")
        window_button = QPushButton("창 모드")
        close_button = QPushButton("닫기")

        apply_button.clicked.connect(lambda: self._apply_window_size(combo.currentData()))
        fullscreen_button.clicked.connect(self.showFullScreen)
        window_button.clicked.connect(self._return_to_windowed_mode)
        close_button.clicked.connect(dialog.accept)

        row = QHBoxLayout()
        row.addWidget(apply_button)
        row.addWidget(fullscreen_button)
        row.addWidget(window_button)
        layout.addLayout(row)
        layout.addWidget(close_button)
        dialog.resize(460, 220)
        dialog.exec()

    def _install_shortcuts(self) -> None:
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self._toggle_fullscreen)
        self.exit_fullscreen_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.exit_fullscreen_shortcut.activated.connect(self._return_to_windowed_mode)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self._return_to_windowed_mode()
        else:
            self.showFullScreen()

    def _return_to_windowed_mode(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        self._center_on_screen()

    def _apply_window_size(self, size: tuple[int, int] | None) -> None:
        if not size:
            return
        self.showNormal()
        width, height = size
        self.resize(int(width), int(height))
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _set_screen(self, widget: QWidget) -> None:
        shell = self._wrap_screen(widget)
        self.stack.addWidget(shell)
        self.stack.setCurrentWidget(shell)
        while self.stack.count() > 4:
            old_widget = self.stack.widget(0)
            self.stack.removeWidget(old_widget)
            old_widget.deleteLater()

    def _wrap_screen(self, widget: QWidget) -> QWidget:
        shell = QWidget()
        shell.setObjectName("ScreenShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        if not isinstance(widget, (StartScreen, DashboardScreen)):
            shell_layout.addWidget(self._global_navigation_bar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        viewport = QWidget()
        viewport.setObjectName("ScreenViewport")
        viewport_layout = QHBoxLayout(viewport)
        viewport_layout.setContentsMargins(24, 14, 24, 18)
        viewport_layout.setSpacing(0)
        viewport_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        content = QWidget()
        content.setObjectName("ScreenContent")
        content.setMaximumWidth(SCREEN_CONTENT_MAX_WIDTH)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(widget)

        viewport_layout.addWidget(content, 1, Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(viewport)
        shell_layout.addWidget(scroll)
        return shell

    def _global_navigation_bar(self) -> QWidget:
        nav = QFrame()
        nav.setObjectName("GlobalNav")
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(10)

        title = QLabel("ChungmuroTycoon")
        title.setObjectName("NavTitle")
        main_button = QPushButton("메인 화면")
        main_button.setObjectName("NavButton")
        main_button.setMinimumWidth(116)
        main_button.clicked.connect(self.show_main_screen)

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(main_button)
        return nav


def _format_history_popup_text(items: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for item in items:
        day = int(item.get("day") or 1)
        date = f"{int(item.get('year'))}.{int(item.get('month')):02d}.{day:02d}"
        source = item.get("source_label") or item.get("source_type") or "역사"
        lines = [
            f"{date} · {source}",
            str(item.get("title") or ""),
        ]
        body = str(item.get("body") or "").strip()
        if body:
            lines.append(body)
        reactions = item.get("reactions") or []
        if reactions:
            lines.append("사람들 반응")
            lines.extend(
                f"- {reaction.get('group', '반응')} · {reaction.get('tone', '관망')}: {reaction.get('text', '')}"
                for reaction in reactions
            )
        sections.append("\n".join(line for line in lines if line))
    return "\n\n".join(sections)


def _format_casting_response_popup_text(items: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for item in items:
        status = "수락" if item.get("accepted") else "보류/거절"
        lines = [
            f"{item.get('responded_date_text') or '-'} · {status}",
            f"{item.get('project_title', '-')} · {item.get('role_label', '-')}",
            f"{item.get('name_ko', '-')} 측 답변",
        ]
        result_text = str(item.get("result_text") or "").strip()
        if result_text:
            lines.append(result_text)
        sections.append("\n".join(line for line in lines if line))
    return "\n\n".join(sections)
