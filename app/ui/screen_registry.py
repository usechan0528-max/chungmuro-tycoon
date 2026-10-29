from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QWidget

from app.ui.awards_screen import AwardProfileScreen
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
from app.ui.people_database import PeopleDatabaseScreen
from app.ui.production_progress import ProductionProgressScreen
from app.ui.release_strategy import ReleaseStrategyScreen
from app.ui.save_load import SaveLoadScreen
from app.ui.start_screen import StartScreen


CORE_SCREEN_CLASSES: dict[str, type[QWidget]] = {
    "StartScreen": StartScreen,
    "CharacterCreationScreen": CharacterCreationScreen,
    "DashboardScreen": DashboardScreen,
    "CrewWorkScreen": CrewWorkScreen,
    "PeopleDatabaseScreen": PeopleDatabaseScreen,
    "FinanceScreen": FinanceScreen,
    "FilmPlanningScreen": FilmPlanningScreen,
    "BudgetAllocationScreen": BudgetAllocationScreen,
    "CastingScreen": CastingScreen,
    "DialogueEventScreen": DialogueEventScreen,
    "ProductionProgressScreen": ProductionProgressScreen,
    "ReleaseStrategyScreen": ReleaseStrategyScreen,
    "BoxOfficeResultScreen": BoxOfficeResultScreen,
    "HistoryTimelineScreen": HistoryTimelineScreen,
    "IndustryDatabaseScreen": IndustryDatabaseScreen,
    "OrganizationProfileScreen": OrganizationProfileScreen,
    "AwardProfileScreen": AwardProfileScreen,
    "SaveLoadScreen": SaveLoadScreen,
}


def core_screen_names() -> Sequence[str]:
    return tuple(CORE_SCREEN_CLASSES)


def validate_core_screens() -> None:
    missing = [name for name, screen_class in CORE_SCREEN_CLASSES.items() if not issubclass(screen_class, QWidget)]
    if missing:
        raise RuntimeError("Core UI screen classes are invalid: " + ", ".join(missing))
