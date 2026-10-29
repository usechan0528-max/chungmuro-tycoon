from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from app.services.budget_service import ALLOCATION_LABELS, recommend_allocation_percentages
from app.services.game_state import money
from app.services.progression_service import shooting_duration_bounds


BUDGET_UNIT = 10_000


class FilmCreationScreen(QWidget):
    def __init__(
        self,
        *,
        references: dict[str, list[dict[str, Any]]],
        on_submit: Callable[[dict[str, Any]], None],
        on_cancel: Callable[[], None],
        screen_title: str = "프로젝트 기획 보고",
        submit_label: str = "프로젝트 승인",
        include_allocation: bool = True,
        initial_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._on_submit = on_submit
        self.references = references
        self.include_allocation = include_allocation
        self.initial_data = dict(initial_data or {})
        self.allocation_inputs: dict[str, QSpinBox] = {}

        outer = QVBoxLayout(self)
        title = QLabel(screen_title)
        title.setObjectName("ScreenTitle")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        era_ui = references.get("era_ui") or {}
        if era_ui:
            era_box = QGroupBox(str(era_ui.get("planningTitle") or "기획 검토 포인트"))
            era_layout = QVBoxLayout(era_box)
            headline = QLabel(str(era_ui.get("headline") or "현재 시대의 제작 환경을 기준으로 기획을 검토합니다."))
            headline.setWordWrap(True)
            headline.setObjectName("PanelText")
            era_layout.addWidget(headline)
            for line in (era_ui.get("planningLines") or [])[:4]:
                item = QLabel(f"- {line}")
                item.setWordWrap(True)
                era_layout.addWidget(item)
            layout.addWidget(era_box)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setVerticalSpacing(12)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("작품 제목")
        self.genre_combo = QComboBox()
        self.scale_combo = QComboBox()
        for genre in references["genres"]:
            self.genre_combo.addItem(genre["name"], genre)
        for scale in references["scales"]:
            self.scale_combo.addItem(scale["name"], scale)

        self.production_budget = QSpinBox()
        self.production_budget.setRange(1, 5_000_000)
        self.production_budget.setSingleStep(100)
        self.production_budget.setSuffix("만 원")
        self.production_budget.setAccelerated(True)
        self.production_budget.setGroupSeparatorShown(True)
        self.production_budget.setToolTip("만원 단위로 직접 입력할 수 있습니다.")
        self.marketing_budget = QSpinBox()
        self.marketing_budget.setRange(0, 2_000_000)
        self.marketing_budget.setSingleStep(100)
        self.marketing_budget.setSuffix("만 원")
        self.marketing_budget.setAccelerated(True)
        self.marketing_budget.setGroupSeparatorShown(True)
        self.marketing_budget.setToolTip("만원 단위로 직접 입력할 수 있습니다.")
        self.scale_budget_note = QLabel("")
        self.scale_budget_note.setWordWrap(True)
        self.scale_budget_note.setObjectName("PanelText")
        self.scale_budget_note.setMinimumHeight(46)
        self.scale_budget_note.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.shooting_duration_days = QSpinBox()
        self.shooting_duration_days.setSuffix("일")
        self.shooting_duration_days.setSingleStep(1)
        self.shooting_duration_days.setGroupSeparatorShown(True)
        self.shooting_duration_note = QLabel("")
        self.shooting_duration_note.setWordWrap(True)
        self.shooting_duration_note.setObjectName("MutedText")

        form.addRow("제목", self.title_input)
        form.addRow("장르", self.genre_combo)
        form.addRow("규모", self.scale_combo)
        form.addRow("제작비", self.production_budget)
        form.addRow("마케팅비", self.marketing_budget)
        form.addRow("촬영 기간", self.shooting_duration_days)
        layout.addLayout(form)

        budget_note_box = QGroupBox("규모 예산 범위")
        budget_note_layout = QVBoxLayout(budget_note_box)
        budget_note_layout.addWidget(self.scale_budget_note)
        budget_note_layout.addWidget(self.shooting_duration_note)
        layout.addWidget(budget_note_box)

        if include_allocation:
            allocation_box = QGroupBox("장르별 제작비 배분")
            allocation_grid = QGridLayout(allocation_box)
            for index, (key, label) in enumerate(ALLOCATION_LABELS.items()):
                spin = QSpinBox()
                spin.setRange(0, 100)
                spin.setSuffix("%")
                self.allocation_inputs[key] = spin
                allocation_grid.addWidget(QLabel(label), index // 2, (index % 2) * 2)
                allocation_grid.addWidget(spin, index // 2, (index % 2) * 2 + 1)
            layout.addWidget(allocation_box)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("취소")
        submit_button = QPushButton(submit_label)
        cancel_button.clicked.connect(on_cancel)
        submit_button.clicked.connect(self._submit)
        buttons.addWidget(cancel_button)
        buttons.addWidget(submit_button)
        layout.addLayout(buttons)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.genre_combo.currentIndexChanged.connect(self._apply_genre_weights)
        self.scale_combo.currentIndexChanged.connect(self._apply_scale_budget)
        self._apply_genre_weights()
        self._apply_scale_budget()
        self._apply_initial_data(self.initial_data)

    def _apply_genre_weights(self) -> None:
        genre = self.genre_combo.currentData()
        if not genre or not self.allocation_inputs:
            return
        recommended = recommend_allocation_percentages(genre)
        for key, spin in self.allocation_inputs.items():
            spin.setValue(int(recommended.get(key, 0)))

    def _apply_scale_budget(self) -> None:
        scale = self.scale_combo.currentData()
        if not scale:
            return
        min_budget = int(scale["min_budget"])
        max_budget = int(scale.get("max_budget", min_budget))
        min_units = max(1, _money_to_units(min_budget))
        max_units = max(min_units, _money_to_units(max_budget))
        self.production_budget.setRange(min_units, max_units)
        self.production_budget.setValue(min_units)
        self.marketing_budget.setRange(0, max(1, int(max_units * 0.8)))
        self.marketing_budget.setValue(_money_to_units(max(0, int(min_budget * 0.25))))
        shooting_bounds = shooting_duration_bounds(str(scale.get("id") or ""))
        self.shooting_duration_days.setRange(shooting_bounds["min"], shooting_bounds["max"])
        self.shooting_duration_days.setValue(shooting_bounds["default"])
        self.shooting_duration_days.setToolTip(
            f"{scale.get('name', '현재 규모')} 기준 최소 {shooting_bounds['min']}일, 기본 {shooting_bounds['default']}일, 최대 {shooting_bounds['max']}일"
        )
        adjustment = scale.get("economic_adjustment") or {}
        if adjustment:
            self.scale_budget_note.setText(
                f"{scale.get('budget_year')}년 현재 제작 환경 기준 {money(min_budget)}~{money(max_budget)}"
            )
        else:
            self.scale_budget_note.setText(f"{money(min_budget)}~{money(max_budget)}")
        self.shooting_duration_note.setText(
            f"촬영 기간은 규모별 최소선 아래로 줄일 수 없습니다. 현재 규모 기준 기본 촬영은 {shooting_bounds['default']}일입니다."
        )

    def _apply_initial_data(self, data: dict[str, Any]) -> None:
        if not data:
            return
        if data.get("title"):
            self.title_input.setText(str(data["title"]))
        self._select_combo_by_id(self.genre_combo, data.get("genre_id"))
        self._select_combo_by_id(self.scale_combo, data.get("scale_id"))
        if data.get("production_budget") is not None:
            self.production_budget.setValue(_money_to_units(int(data["production_budget"])))
        if data.get("marketing_budget") is not None:
            self.marketing_budget.setValue(_money_to_units(int(data["marketing_budget"])))
        if data.get("shooting_duration_days") is not None:
            self.shooting_duration_days.setValue(int(data["shooting_duration_days"]))
        allocation = data.get("allocation")
        if isinstance(allocation, dict):
            for key, value in allocation.items():
                spin = self.allocation_inputs.get(str(key))
                if spin is not None:
                    spin.setValue(int(value or 0))

    @staticmethod
    def _select_combo_by_id(combo: QComboBox, item_id: Any) -> None:
        if not item_id:
            return
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("id") == item_id:
                combo.setCurrentIndex(index)
                return

    def _submit(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 필요", "작품 제목을 입력하세요.")
            return
        data = {
            "title": title,
            "genre_id": self.genre_combo.currentData()["id"],
            "scale_id": self.scale_combo.currentData()["id"],
            "production_budget": int(self.production_budget.value() * BUDGET_UNIT),
            "marketing_budget": int(self.marketing_budget.value() * BUDGET_UNIT),
            "shooting_duration_days": int(self.shooting_duration_days.value()),
        }
        if self.initial_data.get("franchise_context"):
            data["franchise_context"] = self.initial_data["franchise_context"]
        if self.allocation_inputs:
            data["allocation"] = {key: spin.value() for key, spin in self.allocation_inputs.items()}
        self._on_submit(data)


def _money_to_units(value: int) -> int:
    return max(0, int(round(int(value) / BUDGET_UNIT)))
