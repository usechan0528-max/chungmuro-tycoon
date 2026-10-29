from __future__ import annotations

from collections.abc import Callable

from app.ui.screen_helpers import ModuleScreen


class ReleaseStrategyScreen(ModuleScreen):
    def __init__(self, *, on_back: Callable[[], None]) -> None:
        super().__init__(
            title="배급/개봉 전략",
            lines=[
                "개봉 월, 외화 대작과의 충돌, 특수관 전략, 제한 개봉과 와이드 릴리즈.",
                "이미 발표된 대형 경쟁작은 경쟁, 편승, 시기 조정으로 대응한다.",
            ],
            on_back=on_back,
        )
