"""Qt user interface screens."""

from app.ui.annual_report import AnnualReportScreen
from app.ui.awards_screen import AwardProfileScreen, AwardsScreen
from app.ui.box_office_result import BoxOfficeResultScreen
from app.ui.budget_allocation import BudgetAllocationScreen
from app.ui.casting_screen import CastingScreen
from app.ui.character_creation import CharacterCreationScreen
from app.ui.crew_work_screen import CrewWorkScreen
from app.ui.dashboard import DashboardScreen
from app.ui.dialogue_event import DialogueEventScreen
from app.ui.film_planning import FilmPlanningScreen
from app.ui.finance_screen import FinanceScreen
from app.ui.history_timeline import HistoryTimelineScreen
from app.ui.industry_database import IndustryDatabaseScreen, OrganizationProfileScreen
from app.ui.marketing_screen import MarketingScreen
from app.ui.movie_detail import MovieDetailScreen
from app.ui.people_database import CriticProfileScreen, PeopleDatabaseScreen, PersonProfileScreen
from app.ui.player_filmography import PlayerFilmographyScreen
from app.ui.press_and_critics import PressAndCriticsScreen
from app.ui.production_progress import ProductionProgressScreen
from app.ui.release_strategy import ReleaseStrategyScreen
from app.ui.save_load import SaveLoadScreen
from app.ui.screen_registry import CORE_SCREEN_CLASSES, core_screen_names, validate_core_screens
from app.ui.start_screen import StartScreen
from app.ui.world_boxoffice import WorldBoxOfficeScreen

__all__ = [
    "StartScreen",
    "CharacterCreationScreen",
    "DashboardScreen",
    "CrewWorkScreen",
    "PeopleDatabaseScreen",
    "PersonProfileScreen",
    "CriticProfileScreen",
    "PlayerFilmographyScreen",
    "FinanceScreen",
    "FilmPlanningScreen",
    "BudgetAllocationScreen",
    "CastingScreen",
    "DialogueEventScreen",
    "ProductionProgressScreen",
    "MarketingScreen",
    "ReleaseStrategyScreen",
    "BoxOfficeResultScreen",
    "AnnualReportScreen",
    "AwardsScreen",
    "AwardProfileScreen",
    "PressAndCriticsScreen",
    "HistoryTimelineScreen",
    "IndustryDatabaseScreen",
    "OrganizationProfileScreen",
    "SaveLoadScreen",
    "WorldBoxOfficeScreen",
    "MovieDetailScreen",
    "CORE_SCREEN_CLASSES",
    "core_screen_names",
    "validate_core_screens",
]
