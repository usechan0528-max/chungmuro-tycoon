from __future__ import annotations

from collections.abc import Callable

from app.ui.screen_helpers import ModuleScreen


class MarketingScreen(ModuleScreen):
    def __init__(self, *, on_back: Callable[[], None]) -> None:
        super().__init__(
            title="마케팅",
            lines=[
                "제작 발표, 예고편, 언론 인터뷰, 온라인 버즈, 팬 이벤트.",
                "마케팅비와 시대별 온라인 확산력은 개봉 전 관심도와 예매율에 반영된다.",
            ],
            on_back=on_back,
        )
