from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.media_widgets import people_media_frame


class PeopleDatabaseScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_person_profile: Callable[[str], None],
        on_critic_profile: Callable[[str], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_person_profile = on_person_profile
        self._on_critic_profile = on_critic_profile
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("인물 DB")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._people_tab(state.get("actors", [])), "배우")
        tabs.addTab(self._people_tab(state.get("directors", [])), "감독")
        tabs.addTab(self._critics_tab(state.get("critics", [])), "평론가")
        layout.addWidget(tabs)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    def _people_tab(self, people: list[dict[str, Any]]) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        search_input = QLineEdit()
        search_input.setPlaceholderText("이름, 영문명, 한줄 평 검색")
        listing, listing_layout = _link_list_widget()
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        first_person = people[0] if people else {}
        silhouette = people_media_frame(first_person.get("id"), first_person.get("type"))
        detail = QTextEdit()
        detail.setReadOnly(True)
        links: list[tuple[QLabel, str]] = []

        for person in people:
            link = _person_link(person)
            link.linkActivated.connect(self._on_person_profile)
            listing_layout.addWidget(link)
            search_text = " ".join(
                str(person.get(key) or "")
                for key in ("name_ko", "name_en", "one_line", "career_stage_label", "relationship_stage")
            ).lower()
            links.append((link, search_text))
        if not people:
            listing_layout.addWidget(QLabel("조회 가능한 인물 없음"))

        def filter_links(text: str) -> None:
            query = text.strip().lower()
            for link, search_text in links:
                link.setVisible(not query or query in search_text)

        search_input.textChanged.connect(filter_links)
        left_layout.addWidget(search_input)
        left_layout.addWidget(listing, 1)
        layout.addWidget(left_panel, 1)
        detail_layout.addWidget(silhouette, alignment=Qt.AlignmentFlag.AlignLeft)
        detail_layout.addWidget(detail)
        layout.addWidget(detail_panel, 2)
        if people:
            self._show_person(people[0], detail)
        return tab

    def _critics_tab(self, critics: list[dict[str, Any]]) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        search_input = QLineEdit()
        search_input.setPlaceholderText("이름, 성향 설명 검색")
        listing, listing_layout = _link_list_widget()
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        first_critic = critics[0] if critics else {}
        silhouette = people_media_frame(first_critic.get("id"), "critic")
        detail = QTextEdit()
        detail.setReadOnly(True)
        links: list[tuple[QLabel, str]] = []

        for critic in critics:
            link = _critic_link(critic)
            link.linkActivated.connect(self._on_critic_profile)
            listing_layout.addWidget(link)
            search_text = " ".join(
                str(critic.get(key) or "")
                for key in ("name_ko", "public_description", "relationship_stage")
            ).lower()
            links.append((link, search_text))
        if not critics:
            listing_layout.addWidget(QLabel("조회 가능한 평론가 없음"))

        def filter_links(text: str) -> None:
            query = text.strip().lower()
            for link, search_text in links:
                link.setVisible(not query or query in search_text)

        search_input.textChanged.connect(filter_links)
        left_layout.addWidget(search_input)
        left_layout.addWidget(listing, 1)
        layout.addWidget(left_panel, 1)
        detail_layout.addWidget(silhouette, alignment=Qt.AlignmentFlag.AlignLeft)
        detail_layout.addWidget(detail)
        layout.addWidget(detail_panel, 2)
        if critics:
            self._show_critic(critics[0], detail)
        return tab

    @staticmethod
    def _person_label(person: dict[str, Any]) -> str:
        if person.get("name_en"):
            return f"{person['name_ko']} · {person['name_en']}"
        return person["name_ko"]

    @staticmethod
    def _show_person(person: dict[str, Any] | None, detail: QTextEdit) -> None:
        if not person:
            detail.setPlainText("")
            return
        detail.setPlainText(
            "\n\n".join(
                [
                    person["name_ko"],
                    person.get("one_line", ""),
                    f"현재 능력\n{person.get('current_ability_text', '')}",
                    f"활동 단계\n{person.get('career_stage_label', '정보 부족')}\n{person.get('career_stage_text', '')}",
                    f"잠재력\n{person.get('potential_text', '')}",
                    f"명성\n{person.get('fame_text', '')}",
                    f"브랜드 평판\n{person.get('brand_text', '')}",
                    f"현재 관계\n{person.get('relationship_stage', '모르는 사이')}",
                ]
            )
        )

    @staticmethod
    def _show_critic(critic: dict[str, Any] | None, detail: QTextEdit) -> None:
        if not critic:
            detail.setPlainText("")
            return
        detail.setPlainText(
            "\n\n".join(
                [
                    critic["name_ko"],
                    critic.get("public_description", ""),
                ]
            )
        )


class PersonProfileScreen(QWidget):
    def __init__(
        self,
        *,
        profile: dict[str, Any],
        on_back: Callable[[], None],
        back_label: str = "인물 DB로",
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(profile["name"])
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        body = QScrollArea()
        body.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.addWidget(people_media_frame(profile.get("id"), profile.get("type")), alignment=Qt.AlignmentFlag.AlignTop)
        top_layout.addWidget(_panel("\n".join(_profile_meta_lines(profile))), 1)
        content_layout.addWidget(top)

        content_layout.addWidget(_section("배우 한줄 평" if profile.get("type") == "actor" else "감독 한줄 평", profile["one_line"]))
        content_layout.addWidget(_section("현재 관계", _relationship_block(profile)))
        content_layout.addWidget(_section("평판과 명성", _reputation_block(profile)))
        content_layout.addWidget(_section(profile.get("fee_title", "예상 계약 조건"), profile["expected_fee"]))
        content_layout.addWidget(_section(profile.get("preference_title", "선호 협업"), _preference_block(profile)))
        content_layout.addWidget(_section("필모그래피", _list_block(profile.get("filmography"), "아직 연결된 필모그래피가 부족하다.")))
        content_layout.addWidget(_section("수상내역", _list_block(profile.get("awards"), "아직 연결된 수상 데이터가 부족하다.")))
        content_layout.addWidget(_section("커리어 소개", profile["career_intro"]))
        body.setWidget(content)
        layout.addWidget(body, 1)

        back_button = QPushButton(back_label)
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)


class CriticProfileScreen(QWidget):
    def __init__(self, *, profile: dict[str, Any], on_back: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(profile["name"])
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        body = QScrollArea()
        body.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.addWidget(people_media_frame(profile.get("id"), "critic"), alignment=Qt.AlignmentFlag.AlignTop)
        top_layout.addWidget(_panel("\n".join(_critic_meta_lines(profile))), 1)
        content_layout.addWidget(top)

        content_layout.addWidget(_section("평론가 한줄 평", profile["one_line"]))
        content_layout.addWidget(_section("현재 관계", _relationship_block(profile)))
        content_layout.addWidget(_section("영향력", profile["influence_text"]))
        content_layout.addWidget(_section("취향과 평가 기준", profile["taste_text"]))
        content_layout.addWidget(_section("평점/리뷰 스타일", profile["scoring_text"]))
        content_layout.addWidget(_section("선호 작품 경향", profile["preferred_films"]))
        content_layout.addWidget(_section("리뷰 기록", _list_block(profile.get("review_history"), "아직 연결된 리뷰 기록이 부족하다.")))
        content_layout.addWidget(_section("커리어 소개", profile["career_intro"]))
        body.setWidget(content)
        layout.addWidget(body, 1)

        back_button = QPushButton("인물 DB로")
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)


def _link_list_widget() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    scroll.setWidget(container)
    return scroll, layout


def _person_link(person: dict[str, Any]) -> QLabel:
    label = QLabel(f'<a href="{escape(person["id"])}">{escape(PeopleDatabaseScreen._person_label(person))}</a>')
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
    label.setOpenExternalLinks(False)
    label.setToolTip("프로필 보기")
    return label


def _critic_link(critic: dict[str, Any]) -> QLabel:
    label = QLabel(f'<a href="{escape(critic["id"])}">{escape(critic["name_ko"])}</a>')
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
    label.setOpenExternalLinks(False)
    label.setToolTip("평론가 프로필 보기")
    return label


def _panel(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("PanelText")
    return label


def _section(title: str, text: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    heading = QLabel(title)
    heading.setObjectName("SectionTitle")
    body = _panel(text)
    layout.addWidget(heading)
    layout.addWidget(body)
    return widget


def _profile_meta_lines(profile: dict[str, Any]) -> list[str]:
    return [
        f"이름: {profile['name']}",
        f"나이: {profile['age_text']}",
        f"국적: {profile['nationality']}",
        f"활동 상태: {profile['status_text']}",
        f"활동 단계: {profile.get('career_stage_label', '정보 부족')}",
        f"인맥 단계: {profile.get('relationship_stage', '모르는 사이')}",
    ]


def _critic_meta_lines(profile: dict[str, Any]) -> list[str]:
    return [
        f"이름: {profile['name']}",
        f"나이: {profile['age_text']}",
        f"국적: {profile['nationality']}",
        f"활동 상태: {profile['status_text']}",
        f"인맥 단계: {profile.get('relationship_stage', '모르는 사이')}",
    ]


def _relationship_block(profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            profile.get("relationship_stage", "모르는 사이"),
            profile.get("relationship_text", "아직 이름과 평판 이상으로 확인된 접점이 없다."),
        ]
    )


def _reputation_block(profile: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"업계 평판\n{profile['industry_reputation']}",
            f"대중 평판\n{profile['public_reputation']}",
            f"활동 단계\n{profile.get('career_stage_text', '활동 단계 정보가 부족하다.')}",
            f"명성\n{profile['fame_text']}",
            f"잠재력\n{profile['potential_text']}",
            f"브랜드 평판\n{profile['brand_text']}",
        ]
    )


def _preference_block(profile: dict[str, Any]) -> str:
    if profile.get("type") == "director":
        return "\n\n".join(
            [
                f"선호 프로젝트\n{profile['preferred_roles']}",
                f"협업 궁합\n{profile['preferred_directors']}",
            ]
        )
    return "\n\n".join(
        [
            f"선호 배역\n{profile['preferred_roles']}",
            f"선호 감독\n{profile['preferred_directors']}",
        ]
    )


def _list_block(items: list[str] | None, empty_text: str) -> str:
    if not items:
        return empty_text
    return "\n".join(f"- {item}" for item in items)
