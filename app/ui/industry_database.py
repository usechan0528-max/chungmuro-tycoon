from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.organization_service import organization_profile_text
from app.ui.media_widgets import organization_logo_frame


class IndustryDatabaseScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_organization_profile: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("산업 데이터베이스")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(
            self._organization_list(state.get("theaterChains", []), on_organization_profile),
            "3대 영화관",
        )
        tabs.addTab(
            self._organization_list(state.get("distributors", []), on_organization_profile),
            "3대 배급사",
        )
        layout.addWidget(tabs)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    @staticmethod
    def _organization_list(
        rows: list[dict[str, Any]],
        on_organization_profile: Callable[[str], None],
    ) -> QListWidget:
        listing = QListWidget()
        for row in rows:
            profile = row.get("publicProfile") or {}
            item = QListWidgetItem(f"{row.get('nameKo')} · {profile.get('oneLine') or ''}")
            item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
            listing.addItem(item)
        if not rows:
            listing.addItem("현재 게임 시간 기준으로 표시할 산업 주체 없음")
        listing.itemClicked.connect(
            lambda item: on_organization_profile(str(item.data(Qt.ItemDataRole.UserRole)))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        return listing


class OrganizationProfileScreen(QWidget):
    def __init__(self, *, profile: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(str(profile.get("nameKo") or "조직 상세"))
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(organization_logo_frame(profile.get("id")), alignment=Qt.AlignmentFlag.AlignTop)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(organization_profile_text(profile))
        top_layout.addWidget(body, 1)
        layout.addWidget(top, 1)

        back_button = QPushButton("돌아가기")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)
