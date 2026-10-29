from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ui.film_creation import FilmCreationScreen


class FilmPlanningScreen(FilmCreationScreen):
    def __init__(
        self,
        *,
        references: dict[str, list[dict[str, Any]]],
        on_submit: Callable[[dict[str, Any]], None],
        on_cancel: Callable[[], None],
        initial_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            references=references,
            on_submit=on_submit,
            on_cancel=on_cancel,
            screen_title="프로젝트 기획 보고",
            submit_label="예산 배분으로",
            include_allocation=False,
            initial_data=initial_data,
        )
