from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.character_service import get_character_option_groups


LEGACY_LABEL_FIELDS = {
    "origin": "background",
    "education": "education",
    "trait": "trait",
    "wealth": "wealth",
    "first_contact": "career",
}


ERA_INTRO_TEXT = {
    "era_1980s": (
        "낭만의 시대입니다. 전설적인 배우들과 감독이 나타난 시기죠. "
        "하지만 여러 제약이 많던 시기입니다. 해외 출국도 쉽지 않고, 국민 정서가 허락하지 않는 내용도 많습니다. "
        "또한 정부 기관은 당신의 각본을 항상 예의주시하고 있습니다."
    ),
    "era_1990s": (
        "외화가 본격적으로 들어오기 시작했습니다. 이젠 우물 안 싸움이 아닙니다. "
        "하지만 걱정하지 마세요. 또 다른 전설이 될 신예 감독과 배우들이 쏟아져 나오던 시기입니다. "
        "우리 영화가 외국 자본 영화와도 경쟁할 수 있음을 보여주기도 했죠. "
        "다만 경제 위기를 헤쳐 나갈 준비도 단단히 해야 할 것입니다."
    ),
    "era_2000s": (
        "감히 한국 영화의 르네상스라고 할 수 있습니다. "
        "특색 있고 재능 넘치는 감독들이 그 재능을 마음껏 꽃피우던 시기입니다. "
        "정말로 좋은 작품들이 엄청나게 쏟아지던 시기죠. "
        "흐름만 잘 탄다면 한국 영화의 유례없는 전성기를 여는 인물은 당신이 될지도 모르겠습니다."
    ),
    "era_2010s": (
        "충무로는 더 이상 한국만의 무대가 아닙니다. 국민들의 영화 소비력은 유례없게 높아졌고, "
        "막대한 자본이 영화시장에 투자되기 시작했습니다. 하지만 외국 자본도 이를 가만두지 않습니다. "
        "다양한 할리우드 AAA급 영화들이 한국에 적극적이고 공격적인 마케팅을 실행하고, 최초 개봉까지 노리는 황금기입니다. "
        "하지만 그 끝에는 피할 수 없는 사건이 있으니 대비를 단단히 해야 할 겁니다."
    ),
    "era_2020s": (
        "코로나 이후로 영화계는 완전히 바뀌었습니다. "
        "더 이상 예전 같은 투자도, 관객동원력도 없습니다. 이젠 극장 상영이 필수가 아닙니다. "
        "OTT도 새로운 돌파구가 될 수 있겠죠. 새로운 국면에 접어든 영화시장에서 당신의 능력을 보여주십시오."
    ),
    "era_future": (
        "실제 고정 역사 이후의 시간입니다. 외화 대작, 신인 배우와 감독, 극장 재편, OTT 투자, 장르 유행이 "
        "플레이어의 성과와 시장 변수에 따라 새롭게 생성됩니다."
    ),
}


ERA_IMPACT_TEXT = {
    "era_1980s": (
        "검열과 극장주 관계, 충무로 인맥이 강하게 작동합니다. "
        "대형 기술 영화보다 멜로, 문예영화, 사회극, 저예산 장르영화가 현실적인 출발점입니다."
    ),
    "era_1990s": (
        "비디오 시장과 대기업 투자 루트가 열리지만, IMF 전후 투자 위축과 외화 경쟁을 감수해야 합니다. "
        "기획영화와 신예 발굴이 큰 기회가 됩니다."
    ),
    "era_2000s": (
        "멀티플렉스와 대형 배급사가 흥행의 핵심이 됩니다. "
        "장르영화, 웰메이드 상업영화, 강한 감독 브랜드가 빠르게 성장할 수 있습니다."
    ),
    "era_2010s": (
        "천만 영화, SNS 입소문, 특별관, 프랜차이즈 전략이 열립니다. "
        "동시에 마케팅비와 외화 대작 압박, 2주차 낙폭 리스크가 커집니다."
    ),
    "era_2020s": (
        "OTT 계약, 제한 개봉, 숏폼·유튜브 마케팅이 중요해집니다. "
        "중간예산 극장영화는 위험하지만 저예산 고효율 장르와 강한 IP는 돌파구가 될 수 있습니다."
    ),
    "era_future": (
        "고정 역사 대신 자동 생성 시장이 작동합니다. "
        "플레이어가 성공시킨 장르와 인물이 미래 트렌드와 경쟁 구도를 바꿉니다."
    ),
}


class OptionSelector(QWidget):
    def __init__(self, group: dict[str, Any]) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.group = group
        self.options = list(group.get("options", []))
        self.current_option = self.options[0] if self.options else {}
        self._description_min_lines = int(group.get("descriptionMinLines", 4) or 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel(str(group.get("title", "")))
        title.setObjectName("SectionTitle")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(title)

        summary = QLabel(str(group.get("description", "")))
        summary.setWordWrap(True)
        summary.setObjectName("MutedText")
        summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(summary)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        columns = int(group.get("columns", 2) or 2)
        for index, option in enumerate(self.options):
            button = QPushButton(str(option["label"]))
            button.setObjectName("ChoiceTile")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setMinimumHeight(44)
            button.setMaximumHeight(44)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, item=option: self.select(item))
            self.button_group.addButton(button)
            grid.addWidget(button, index // columns, index % columns)
            if index == 0:
                button.setChecked(True)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setObjectName("MutedText")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.description_label.setMinimumHeight(self._base_description_height())
        layout.addWidget(self.description_label)
        if self.current_option:
            self.select(self.current_option)

    def select(self, option: dict[str, Any]) -> None:
        self.current_option = option
        description = str(option.get("description", ""))
        impact = str(option.get("impact", ""))
        lines = [description]
        if impact:
            lines.append(f"영향: {impact}")
        self.description_label.setText("\n".join(lines))
        self._refresh_description_height()
        QTimer.singleShot(0, self._refresh_description_height)
        self.updateGeometry()

    def value(self) -> str:
        return str(self.current_option.get("id", ""))

    def label(self) -> str:
        return str(self.current_option.get("label", ""))

    def _base_description_height(self) -> int:
        return self.fontMetrics().lineSpacing() * self._description_min_lines + 12

    def _refresh_description_height(self) -> None:
        text = self.description_label.text()
        width = max(120, self.description_label.width() - 8)
        rect = self.description_label.fontMetrics().boundingRect(
            0,
            0,
            width,
            2000,
            Qt.TextFlag.TextWordWrap,
            text,
        )
        self.description_label.setMinimumHeight(max(self._base_description_height(), rect.height() + 16))
        self.description_label.updateGeometry()


class CharacterCreationScreen(QWidget):
    def __init__(
        self,
        *,
        references: dict[str, list[dict[str, Any]]],
        on_submit: Callable[[dict[str, Any]], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_submit = on_submit
        self.option_selectors: dict[str, OptionSelector] = {}

        layout = QVBoxLayout(self)
        title = QLabel("캐릭터 생성")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "이제 시작은 직업군이 아니라 출신, 학력, 성향, 재산, 평판의 조합으로 결정됩니다."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("MutedText")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        identity_box = QGroupBox("기본 정보")
        form = QFormLayout(identity_box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("이름")
        self.gender_selector = OptionSelector(
            {
                "id": "gender",
                "title": "성별",
                "description": "능력치 우열은 없다. 시대별 기회와 사회적 시선 이벤트의 맥락으로만 쓰인다.",
                "columns": 4,
                "descriptionMinLines": 3,
                "options": [
                    {"id": "여성", "label": "여성", "description": "시대별 구조와 편견 이벤트가 일부 다르게 작동한다.", "impact": "능력치 변화 없음."},
                    {"id": "남성", "label": "남성", "description": "시대별 구조와 업계 관행 이벤트의 맥락으로 쓰인다.", "impact": "능력치 변화 없음."},
                    {"id": "논바이너리", "label": "논바이너리", "description": "정체성에 따른 서사 맥락을 남긴다.", "impact": "능력치 변화 없음."},
                    {"id": "비공개", "label": "비공개", "description": "프로필에 성별을 드러내지 않는다.", "impact": "능력치 변화 없음."},
                ],
            }
        )
        self.age_input = QSpinBox()
        self.age_input.setRange(18, 75)
        self.age_input.setValue(28)
        self.era_selector = OptionSelector(
            {
                "id": "era",
                "title": "시작 시대",
                "description": "검열, 멀티플렉스, OTT, 티켓값 부담 등 게임 규칙 자체를 바꾼다.",
                "columns": 3,
                "descriptionMinLines": 8,
                "options": [
                    {
                        "id": era["id"],
                        "label": era["name"],
                        "description": self._era_description(era),
                        "impact": self._era_impact(era),
                    }
                    for era in references["eras"]
                    if era.get("id") != "era_future"
                ],
            }
        )
        form.addRow("이름", self.name_input)
        form.addRow("성별", self.gender_selector)
        form.addRow("나이", self.age_input)
        form.addRow("시작 시대", self.era_selector)
        content_layout.addWidget(identity_box)

        for group in get_character_option_groups():
            selector = OptionSelector(group)
            self.option_selectors[str(group["id"])] = selector
            box = QGroupBox(str(group.get("title", "")))
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(selector)
            content_layout.addWidget(box)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("뒤로")
        submit_button = QPushButton("시작하기")
        cancel_button.clicked.connect(on_cancel)
        submit_button.clicked.connect(self._submit)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(submit_button)
        layout.addLayout(buttons)

    @staticmethod
    def _era_description(era: dict[str, Any]) -> str:
        return ERA_INTRO_TEXT.get(str(era.get("id")), str(era.get("description", "")))

    @staticmethod
    def _era_impact(era: dict[str, Any]) -> str:
        return ERA_IMPACT_TEXT.get(
            str(era.get("id")),
            "선택한 시대에 맞춰 시장 환경과 사용할 수 있는 전략이 달라집니다.",
        )

    def _submit(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 필요", "이름을 입력하세요.")
            return

        payload: dict[str, Any] = {
            "name": name,
            "gender": self.gender_selector.value(),
            "age": self.age_input.value(),
            "era_id": self.era_selector.value(),
            "position": "영화인",
        }
        for group_id, selector in self.option_selectors.items():
            payload[f"{group_id}_id"] = selector.value()
            payload[group_id] = selector.label()
            legacy_field = LEGACY_LABEL_FIELDS.get(group_id)
            if legacy_field:
                payload[legacy_field] = selector.label()
        self._on_submit(payload)
