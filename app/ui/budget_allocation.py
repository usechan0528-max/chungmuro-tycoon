from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QButtonGroup,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.budget_service import (
    ALLOCATION_LABELS,
    CONTINGENCY_CATEGORY,
    NON_CONTINGENCY_CATEGORIES,
    normalize_allocation_amounts,
    recommend_allocation_percentages,
)
from app.services.game_state import money
from app.services.location_service import location_impact_line, location_strategy_options


UNIT = 10_000


class BudgetAllocationScreen(QWidget):
    def __init__(
        self,
        *,
        references: dict[str, list[dict[str, Any]]],
        planning_data: dict[str, Any],
        on_submit: Callable[[dict[str, Any]], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.references = references
        self.planning_data = dict(planning_data)
        self._on_submit = on_submit
        self.amount_inputs: dict[str, QSpinBox] = {}
        self.era_ui = references.get("era_ui") or {}

        self.genre = self._find_reference("genres", str(planning_data["genre_id"]))
        self.scale = self._find_reference("scales", str(planning_data["scale_id"]))
        self.production_budget = int(planning_data["production_budget"])
        self.marketing_budget = int(planning_data["marketing_budget"])
        self.location_options = location_strategy_options(
            scale_id=str(planning_data["scale_id"]),
            genre_id=str(planning_data["genre_id"]),
        )
        for option in self.location_options:
            option["costImpact"] = int(self.production_budget * float(option.get("costRate", 0.0)))
            option["impactLine"] = location_impact_line(option)
        self.location_buttons: dict[int, str] = {}

        outer = QVBoxLayout(self)
        title = QLabel("제작비 배분 보고")
        title.setObjectName("ScreenTitle")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        summary = QGroupBox("프로젝트 요약")
        summary_grid = QGridLayout(summary)
        rows = [
            ("제목", str(planning_data["title"])),
            ("장르", self.genre.get("name", str(planning_data["genre_id"]))),
            ("규모", self.scale.get("name", str(planning_data["scale_id"]))),
            ("촬영 기간", f"{int(planning_data['shooting_duration_days']):,}일" if planning_data.get("shooting_duration_days") else "-"),
            ("순제작비", money(self.production_budget)),
            ("마케팅비", money(self.marketing_budget)),
        ]
        for row, (label, value) in enumerate(rows):
            summary_grid.addWidget(QLabel(label), row, 0)
            summary_grid.addWidget(QLabel(str(value)), row, 1)
        layout.addWidget(summary)

        if self.era_ui:
            era_box = QGroupBox("시대별 예산 감각")
            era_layout = QVBoxLayout(era_box)
            for line in (self.era_ui.get("budgetLines") or [])[:4]:
                item = QLabel(f"- {line}")
                item.setWordWrap(True)
                era_layout.addWidget(item)
            layout.addWidget(era_box)

        location_box = QGroupBox("로케이션/세트 전략")
        location_layout = QVBoxLayout(location_box)
        self.location_group = QButtonGroup(self)
        default_location = str(planning_data.get("location_strategy") or "real_location")
        for option in self.location_options:
            button = QRadioButton(str(option["name"]))
            button.setToolTip(str(option.get("description") or ""))
            button_id = len(self.location_buttons) + 1
            self.location_buttons[button_id] = str(option["id"])
            self.location_group.addButton(button, button_id)
            location_layout.addWidget(button)
            if option["id"] == default_location:
                button.setChecked(True)
        self.location_description = QLabel()
        self.location_description.setWordWrap(True)
        self.location_description.setObjectName("MutedText")
        location_layout.addWidget(self.location_description)
        self.location_group.idClicked.connect(self._update_location_description)
        layout.addWidget(location_box)
        checked_id = self.location_group.checkedId()
        if checked_id == -1 and self.location_buttons:
            first_button = self.location_group.button(next(iter(self.location_buttons)))
            if first_button:
                first_button.setChecked(True)
        self._update_location_description(self.location_group.checkedId())

        allocation_box = QGroupBox("항목별 순제작비 배분")
        allocation_grid = QGridLayout(allocation_box)
        allocation_grid.addWidget(QLabel("항목"), 0, 0)
        allocation_grid.addWidget(QLabel("안전 권장"), 0, 1)
        allocation_grid.addWidget(QLabel("배분 금액(만원)"), 0, 2)

        defaults = self._default_amounts()
        recommended_weights = recommend_allocation_percentages(self.genre)
        max_units = max(1, self.production_budget // UNIT)
        for row, (key, label) in enumerate(ALLOCATION_LABELS.items(), start=1):
            recommended = int(recommended_weights.get(key, 0) or 0)
            spin = QSpinBox()
            spin.setRange(0, max_units)
            spin.setSingleStep(100)
            spin.setSuffix("만 원")
            spin.setAccelerated(True)
            spin.setGroupSeparatorShown(True)
            spin.setValue(defaults.get(key, 0) // UNIT)
            if key == CONTINGENCY_CATEGORY:
                spin.setEnabled(False)
                spin.setToolTip("주요 항목 배분 후 남은 순제작비가 자동으로 예비비에 들어갑니다.")
            else:
                spin.setToolTip("만원 단위로 직접 입력할 수 있습니다.")
            spin.valueChanged.connect(self._update_remaining)
            self.amount_inputs[key] = spin
            allocation_grid.addWidget(QLabel(label), row, 0)
            allocation_grid.addWidget(QLabel(f"{recommended}%"), row, 1)
            allocation_grid.addWidget(spin, row, 2)

        self.remaining_label = QLabel()
        self.remaining_label.setObjectName("PanelText")
        layout.addWidget(allocation_box)
        hint = QLabel("각 항목 금액은 만원 단위로 직접 입력할 수 있습니다. 남은 순제작비는 자동으로 예비비에 배정됩니다.")
        hint.setWordWrap(True)
        hint.setObjectName("MutedText")
        layout.addWidget(hint)
        layout.addWidget(self.remaining_label)

        buttons = QHBoxLayout()
        back_button = QPushButton("이전")
        submit_button = QPushButton("제작 시작")
        back_button.clicked.connect(on_back)
        submit_button.clicked.connect(self._submit)
        buttons.addWidget(back_button)
        buttons.addWidget(submit_button)
        layout.addLayout(buttons)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._update_remaining()

    def _find_reference(self, key: str, reference_id: str) -> dict[str, Any]:
        for item in self.references.get(key, []):
            if item.get("id") == reference_id:
                return item
        return {"id": reference_id}

    def _default_amounts(self) -> dict[str, int]:
        budget_units = max(1, self.production_budget // UNIT)
        weights = recommend_allocation_percentages(self.genre)
        total_weight = sum(weights.values()) or len(weights)
        amounts: dict[str, int] = {}
        assigned_units = 0
        items = list(ALLOCATION_LABELS)
        for key in items[:-1]:
            amount_units = int(round(budget_units * weights.get(key, 0) / total_weight))
            amounts[key] = amount_units * UNIT
            assigned_units += amount_units
        amounts[items[-1]] = max(0, budget_units - assigned_units) * UNIT
        return amounts

    def _allocated_amount(self) -> int:
        return sum(spin.value() * UNIT for spin in self.amount_inputs.values())

    def _allocated_non_contingency_amount(self) -> int:
        return sum(
            self.amount_inputs[key].value() * UNIT
            for key in NON_CONTINGENCY_CATEGORIES
            if key in self.amount_inputs
        )

    def _update_remaining(self) -> None:
        non_contingency = self._allocated_non_contingency_amount()
        remaining = self.production_budget - non_contingency
        contingency_spin = self.amount_inputs.get(CONTINGENCY_CATEGORY)
        if contingency_spin:
            contingency_spin.blockSignals(True)
            contingency_spin.setValue(max(0, remaining) // UNIT)
            contingency_spin.blockSignals(False)
        if remaining >= 0:
            self.remaining_label.setText(
                f"자동 예비비: {money(remaining)} · 주요 항목 배분: {money(non_contingency)}"
            )
        else:
            self.remaining_label.setText(
                f"순제작비 초과: {money(abs(remaining))} · 주요 항목 배분을 줄여야 합니다."
            )
        if remaining < 0:
            self.remaining_label.setStyleSheet("color: #ff9f9f;")
        else:
            self.remaining_label.setStyleSheet("color: #d9dee5;")

    def _submit(self) -> None:
        self._update_remaining()
        allocated = self._allocated_amount()
        non_contingency = self._allocated_non_contingency_amount()
        if non_contingency <= 0:
            QMessageBox.warning(self, "배분 필요", "최소 한 항목 이상 제작비를 배분해야 합니다.")
            return
        if allocated > self.production_budget:
            QMessageBox.warning(self, "예산 초과", "배분 금액이 순제작비를 초과했습니다.")
            return

        allocation_amounts = {
            key: spin.value() * UNIT
            for key, spin in self.amount_inputs.items()
        }
        allocation = normalize_allocation_amounts(self.production_budget, allocation_amounts)
        payload = dict(self.planning_data)
        payload["allocation"] = allocation
        payload["allocation_amounts"] = allocation_amounts
        payload["location_strategy"] = self.location_buttons.get(self.location_group.checkedId(), "real_location")
        self._on_submit(payload)

    def _update_location_description(self, button_id: int) -> None:
        selected = self.location_buttons.get(button_id, "real_location")
        option = next((item for item in self.location_options if item["id"] == selected), None)
        if not option:
            self.location_description.setText("")
            return
        parts = [str(option.get("shortDescription") or ""), str(option.get("impactLine") or "")]
        if option.get("availabilityNote"):
            parts.append(str(option["availabilityNote"]))
        self.location_description.setText("\n".join(part for part in parts if part))
