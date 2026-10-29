from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CastingScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, list[dict[str, Any]]] | None = None,
        on_attach: Callable[[str, str, dict[str, Any]], None] | None = None,
        on_update: Callable[[str, str, dict[str, Any]], None] | None = None,
        on_discover: Callable[[str, int], None] | None = None,
        on_confirm: Callable[[], None] | None = None,
        era_ui: dict[str, Any] | None = None,
        on_back: Callable[[], None],
        back_label: str = "대시보드로",
    ) -> None:
        super().__init__()
        self.state = state or {"actors": [], "directors": [], "current": []}
        self.on_attach = on_attach
        self.on_update = on_update
        self.on_discover = on_discover
        self.on_confirm = on_confirm
        self.era_ui = era_ui or self.state.get("era_ui") or {}
        self.default_actor_commitment = self.state.get("default_actor_commitment") or {}
        self._selected_contract: dict[str, Any] | None = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel("캐스팅")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        if self.era_ui:
            era_box = QGroupBox(str(self.era_ui.get("label") or "캐스팅 환경"))
            era_layout = QVBoxLayout(era_box)
            for line in (self.era_ui.get("castingLines") or [])[:3]:
                item = QLabel(f"- {line}")
                item.setWordWrap(True)
                era_layout.addWidget(item)
            layout.addWidget(era_box)

        workspace_tabs = QTabWidget()
        workspace_tabs.addTab(self._casting_workspace_tab(), "후보/제안")
        workspace_tabs.addTab(self._confirmed_cast_tab(), "확정 출연진")
        layout.addWidget(workspace_tabs)
        layout.addWidget(self._casting_confirmation_box())

        back_button = QPushButton(back_label)
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)

    def _casting_confirmation_box(self) -> QWidget:
        status = self.state.get("confirmation") or {}
        box = QGroupBox("공식 출연진 확정")
        layout = QVBoxLayout(box)
        summary = QLabel(str(status.get("summary") or "출연 계약이 모이면 공식 출연진으로 확정할 수 있습니다."))
        summary.setWordWrap(True)
        layout.addWidget(summary)
        counts = QLabel(
            f"계약된 배우 {int(status.get('actor_count', 0) or 0)}/{int(status.get('required_actor_count', 0) or 0)}"
            f" · 주연 {int(status.get('lead_actor_count', 0) or 0)}/{int(status.get('required_lead_actor_count', 0) or 0)}"
            f" · 답변 대기 {int(status.get('pending_count', 0) or 0)}"
        )
        counts.setWordWrap(True)
        counts.setObjectName("MutedText")
        layout.addWidget(counts)
        if status.get("is_confirmed"):
            label = QLabel("공식 출연진 확정 완료. 제작 발표회 진행 조건을 충족했습니다.")
            label.setWordWrap(True)
            layout.addWidget(label)
            return box
        confirm_button = QPushButton("현재 계약으로 출연진 확정")
        confirm_button.setMinimumHeight(36)
        confirm_button.setEnabled(bool(status.get("can_confirm")) and self.on_confirm is not None)
        if status.get("missing"):
            confirm_button.setToolTip("부족한 조건: " + ", ".join(str(item) for item in status.get("missing", [])))
        confirm_button.clicked.connect(lambda checked=False: self.on_confirm() if self.on_confirm else None)
        layout.addWidget(confirm_button)
        return box

    def _casting_workspace_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        candidate_tabs = QTabWidget()
        candidate_tabs.addTab(self._people_tab(self.state.get("actors", []), person_type="actor"), "배우 후보")
        candidate_tabs.addTab(self._people_tab(self.state.get("directors", []), person_type="director"), "감독 후보")
        layout.addWidget(candidate_tabs)

        pending_box = QGroupBox("보낸 제안")
        pending_layout = QVBoxLayout(pending_box)
        pending_hint = QLabel("아직 상대 측 답변을 기다리는 캐스팅 제안입니다. 답변일이 되면 팝업으로 알려줍니다.")
        pending_hint.setWordWrap(True)
        pending_layout.addWidget(pending_hint)
        pending_list = QListWidget()
        for row in self.state.get("pending_offers", []):
            pending_list.addItem(_pending_offer_line(row))
        if pending_list.count() == 0:
            pending_list.addItem("답변 대기 중인 캐스팅 제안이 없습니다.")
        pending_list.setMaximumHeight(150)
        pending_layout.addWidget(pending_list)
        layout.addWidget(pending_box)
        return tab

    def _confirmed_cast_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        cast_box = QGroupBox("확정 출연진")
        cast_layout = QVBoxLayout(cast_box)
        cast_hint = QLabel("상대가 수락해 실제 프로젝트에 붙은 인물만 표시됩니다.")
        cast_hint.setWordWrap(True)
        cast_layout.addWidget(cast_hint)
        current_list = QListWidget()
        principal_cast = [row for row in self.state.get("current", []) if not row.get("automatic_cast")]
        automatic_cast = [row for row in self.state.get("current", []) if row.get("automatic_cast")]
        for row in principal_cast:
            item = QListWidgetItem(
                f"{row.get('role_label', row.get('role', '-'))} · {row.get('name_ko', '-')} · "
                f"{row.get('contract_text', '계약 조건 미정')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            current_list.addItem(item)
        if current_list.count() == 0:
            current_list.addItem("아직 확정된 주요 캐스팅 계약이 없습니다.")
        cast_layout.addWidget(current_list, 1)
        auto_label = QLabel("단역/작은 조연 자동 충원")
        auto_label.setObjectName("MutedText")
        cast_layout.addWidget(auto_label)
        auto_list = QListWidget()
        for row in automatic_cast:
            auto_list.addItem(
                f"{row.get('role_label', row.get('role', '-'))} · {row.get('name_ko', '-')} · "
                f"{row.get('contract_text', '자동 충원')}"
            )
        if auto_list.count() == 0:
            auto_list.addItem("자동 충원된 단역/작은 조연이 없습니다.")
        auto_list.setMaximumHeight(140)
        cast_layout.addWidget(auto_list)
        layout.addWidget(cast_box, 1)

        edit_box = QGroupBox("선택 계약 수정")
        edit_layout = QVBoxLayout(edit_box)
        self.edit_hint = QLabel("확정 출연진을 선택하면 조건을 수정할 수 있습니다. 역할 변경은 새 제안으로 처리합니다.")
        self.edit_hint.setWordWrap(True)
        edit_layout.addWidget(self.edit_hint)

        edit_form = QFormLayout()
        self.edit_fee_input = QLineEdit()
        self.edit_fee_input.setPlaceholderText("예: 120000000")
        self.edit_commitment = QSpinBox()
        self.edit_commitment.setRange(0, 36)
        self.edit_commitment.setSuffix("개월")
        self.edit_sequel_option = QCheckBox("후속작 옵션")
        self.edit_promotion_obligation = QCheckBox("홍보 의무")
        self.edit_promotion_days = QSpinBox()
        self.edit_promotion_days.setRange(0, 60)
        self.edit_promotion_days.setSuffix("일")
        self.edit_deferred_fee = _money_spinbox(maximum=1_000_000)
        self.edit_running_guarantee = QCheckBox("러닝 개런티")
        self.edit_running_rate = QDoubleSpinBox()
        self.edit_running_rate.setRange(0.0, 20.0)
        self.edit_running_rate.setDecimals(1)
        self.edit_running_rate.setSingleStep(0.5)
        self.edit_running_rate.setSuffix("%")
        self.edit_running_trigger = QComboBox()
        _populate_running_trigger(self.edit_running_trigger)
        self.edit_bonus_audience = QSpinBox()
        self.edit_bonus_audience.setRange(0, 3000)
        self.edit_bonus_audience.setSuffix("만 명")
        self.edit_bonus_audience.setGroupSeparatorShown(True)
        self.edit_bonus_amount = _money_spinbox(maximum=1_000_000)
        self.edit_image_rights = QCheckBox("스틸컷/포스터/예고편 활용 동의")
        edit_form.addRow("계약금", self.edit_fee_input)
        edit_form.addRow("일정 구속", self.edit_commitment)
        edit_form.addRow("", self.edit_sequel_option)
        edit_form.addRow("", self.edit_promotion_obligation)
        edit_form.addRow("홍보 일정", self.edit_promotion_days)
        edit_form.addRow("이연 지급", self.edit_deferred_fee)
        edit_form.addRow("", self.edit_running_guarantee)
        edit_form.addRow("러닝 요율", self.edit_running_rate)
        edit_form.addRow("러닝 기준", self.edit_running_trigger)
        edit_form.addRow("보너스 관객", self.edit_bonus_audience)
        edit_form.addRow("흥행 보너스", self.edit_bonus_amount)
        edit_form.addRow("", self.edit_image_rights)
        edit_layout.addLayout(edit_form)

        self.update_button = QPushButton("선택 계약 수정")
        self.update_button.setMinimumHeight(36)
        self.update_button.clicked.connect(self._submit_contract_update)
        edit_layout.addWidget(self.update_button)
        layout.addWidget(edit_box, 1)

        self._set_edit_enabled(False)
        current_list.currentItemChanged.connect(lambda item, previous: self._load_contract_for_edit(item))
        if self.state.get("current"):
            current_list.setCurrentRow(0)
        return tab

    def _people_tab(self, people: list[dict[str, Any]], *, person_type: str) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        search_input = QLineEdit()
        search_input.setPlaceholderText("이름, 영문명, 한줄 평 검색")
        stage_filter = QComboBox()
        stage_filter.addItem("모든 활동 단계", "")
        for stage in sorted({str(person.get("career_stage_label") or "") for person in people if person.get("career_stage_label")}):
            stage_filter.addItem(stage, stage)
        listing = QListWidget()
        right = QVBoxLayout()
        detail = QTextEdit()
        detail.setReadOnly(True)

        def populate() -> None:
            listing.clear()
            query = search_input.text().strip().lower()
            stage = str(stage_filter.currentData() or "")
            matches = []
            for person in people:
                if stage and str(person.get("career_stage_label") or "") != stage:
                    continue
                haystack = " ".join(
                    str(person.get(key) or "")
                    for key in ("name_ko", "name_en", "one_line", "career_stage_label", "career_stage_text")
                ).lower()
                if query and query not in haystack:
                    continue
                matches.append(person)
            for person in matches:
                career_stage = person.get("career_stage_label")
                item = QListWidgetItem(f"{person['name_ko']} · {career_stage}" if career_stage else person["name_ko"])
                item.setData(Qt.ItemDataRole.UserRole, person)
                listing.addItem(item)
            if not matches:
                listing.addItem("조건에 맞는 후보 없음")
                detail.setPlainText("")
            elif listing.count():
                listing.setCurrentRow(0)

        for person in people:
            stage = person.get("career_stage_label")
            item = QListWidgetItem(f"{person['name_ko']} · {stage}" if stage else person["name_ko"])
            item.setData(Qt.ItemDataRole.UserRole, person)
            listing.addItem(item)
        if not people:
            listing.addItem("등록된 후보 없음")

        listing.currentItemChanged.connect(lambda item, previous: self._show_person(item, detail))
        search_input.textChanged.connect(lambda text: populate())
        stage_filter.currentIndexChanged.connect(lambda index: populate())
        left_layout.addWidget(search_input)
        left_layout.addWidget(stage_filter)
        left_layout.addWidget(listing, 1)
        layout.addWidget(left_panel, 1)
        right.addWidget(detail)
        role_combo = QComboBox()
        if person_type == "actor":
            role_combo.addItem("주연 배우", "lead_actor")
            role_combo.addItem("조연 배우", "supporting_actor")
            role_combo.addItem("특별출연", "cameo_actor")
        else:
            role_combo.addItem("감독", "director")
        fee_input = QLineEdit()
        fee_input.setPlaceholderText("예: 120000000")
        commitment = QSpinBox()
        commitment.setRange(0, 36)
        commitment.setSuffix("개월")
        if person_type == "actor":
            commitment.setValue(_default_actor_commitment_months(self.default_actor_commitment))
            commitment.setToolTip(
                "기본값은 프로젝트의 촬영 예정 기간을 월 단위로 올림한 뒤, "
                "준비와 추가 촬영 여지를 위해 1개월을 더한 값입니다."
            )
        sequel_option = QCheckBox("후속작 옵션")
        promotion_obligation = QCheckBox("홍보 의무")
        promotion_days = QSpinBox()
        promotion_days.setRange(0, 60)
        promotion_days.setSuffix("일")
        deferred_fee = _money_spinbox(maximum=1_000_000)
        running_guarantee = QCheckBox("러닝 개런티")
        running_rate = QDoubleSpinBox()
        running_rate.setRange(0.0, 20.0)
        running_rate.setDecimals(1)
        running_rate.setSingleStep(0.5)
        running_rate.setSuffix("%")
        running_trigger = QComboBox()
        _populate_running_trigger(running_trigger)
        bonus_audience = QSpinBox()
        bonus_audience.setRange(0, 3000)
        bonus_audience.setSuffix("만 명")
        bonus_audience.setGroupSeparatorShown(True)
        bonus_amount = _money_spinbox(maximum=1_000_000)
        image_rights = QCheckBox("스틸컷/포스터/예고편 활용 동의")
        if person_type != "actor":
            sequel_option.setEnabled(False)

        form = QFormLayout()
        form.addRow("역할", role_combo)
        form.addRow("계약금", fee_input)
        form.addRow("일정 구속", commitment)
        if person_type == "actor":
            default_note = QLabel(str(self.default_actor_commitment.get("label") or "촬영 예정 기간 + 1개월을 기본값으로 제안합니다."))
            default_note.setWordWrap(True)
            default_note.setObjectName("MutedText")
            form.addRow("", default_note)
        form.addRow("", sequel_option)
        form.addRow("", promotion_obligation)
        form.addRow("홍보 일정", promotion_days)
        form.addRow("이연 지급", deferred_fee)
        form.addRow("", running_guarantee)
        form.addRow("러닝 요율", running_rate)
        form.addRow("러닝 기준", running_trigger)
        form.addRow("보너스 관객", bonus_audience)
        form.addRow("흥행 보너스", bonus_amount)
        form.addRow("", image_rights)
        right.addLayout(form)
        if person_type == "actor":
            discovery_results = self.state.get("discovery_results", [])
            if discovery_results:
                right.addWidget(
                    self._discovery_results_cards(
                        discovery_results,
                        submit=lambda person, role: self._submit_person_contract(
                            person,
                            role,
                            fee_input.text() or _default_discovery_fee_text(role),
                            commitment.value(),
                            sequel_option.isChecked(),
                            promotion_obligation.isChecked(),
                            promotion_days.value(),
                            _contract_terms_payload(
                                deferred_fee.value(),
                                running_guarantee.isChecked(),
                                running_rate.value(),
                                str(running_trigger.currentData() or "break_even"),
                                bonus_audience.value(),
                                bonus_amount.value(),
                                image_rights.isChecked(),
                            ),
                        ),
                    )
                )
            right.addWidget(self._discovery_box())

        attach_button = QPushButton("협상 제안 보내기")
        attach_button.setMinimumHeight(36)
        attach_button.clicked.connect(
            lambda checked=False: self._submit_contract(
                listing.currentItem(),
                role_combo.currentData(),
                fee_input.text(),
                commitment.value(),
                sequel_option.isChecked(),
                promotion_obligation.isChecked(),
                promotion_days.value(),
                _contract_terms_payload(
                    deferred_fee.value(),
                    running_guarantee.isChecked(),
                    running_rate.value(),
                    str(running_trigger.currentData() or "break_even"),
                    bonus_audience.value(),
                    bonus_amount.value(),
                    image_rights.isChecked(),
                ),
            )
        )
        right.addWidget(attach_button)
        layout.addLayout(right, 2)
        populate()
        return tab

    def _discovery_results_cards(
        self,
        candidates: list[dict[str, Any]],
        *,
        submit: Callable[[dict[str, Any], str], None],
    ) -> QWidget:
        box = QGroupBox("최근 발굴 후보")
        outer = QVBoxLayout(box)
        hint = QLabel("카드의 배우 중 하나를 골라 현재 입력한 계약 조건으로 제안을 보냅니다. 답변은 며칠 뒤 도착합니다.")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(280)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, person in enumerate(candidates[:6]):
            card = self._candidate_card(person, submit=submit)
            row = index // 2
            column = index % 2
            grid.addWidget(card, row, column)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        return box

    def _candidate_card(
        self,
        person: dict[str, Any],
        *,
        submit: Callable[[dict[str, Any], str], None],
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("CandidateCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        name = QLabel(str(person.get("name_ko") or "-"))
        name.setObjectName("CardTitle")
        name.setWordWrap(True)
        layout.addWidget(name)
        lines = [
            str(person.get("career_stage_label") or "신인 후보"),
            str(person.get("one_line") or "아직 공개 평가가 충분하지 않은 후보."),
            str(person.get("current_ability_text") or ""),
            str(person.get("potential_text") or ""),
        ]
        for line in [item for item in lines if item][:4]:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)
        actions = QHBoxLayout()
        lead_button = QPushButton("주연 제안")
        lead_button.clicked.connect(lambda checked=False, row=person: submit(row, "lead_actor"))
        support_button = QPushButton("조연 제안")
        support_button.clicked.connect(lambda checked=False, row=person: submit(row, "supporting_actor"))
        cameo_button = QPushButton("특별출연")
        cameo_button.clicked.connect(lambda checked=False, row=person: submit(row, "cameo_actor"))
        actions.addWidget(lead_button)
        actions.addWidget(support_button)
        actions.addWidget(cameo_button)
        layout.addLayout(actions)
        return card

    def _discovery_box(self) -> QWidget:
        box = QGroupBox("신인 발굴")
        layout = QVBoxLayout(box)
        options = self.state.get("discovery_options", [])
        if not options:
            label = QLabel("현재 프로젝트 규모에서는 신인 발굴 옵션이 제한적입니다.")
            label.setWordWrap(True)
            layout.addWidget(label)
            return box
        hint = QLabel(
            str(
                self.era_ui.get("discoveryHint")
                or "독립/저예산 프로젝트에서는 발굴 예산을 들여 생성 배우 후보를 확보할 수 있습니다."
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        option_combo = QComboBox()
        for option in options:
            option_combo.addItem(
                f"{option['label']} · 권장 {int(option.get('recommended_budget', 0)) // 10000:,}만 원",
                option,
            )
        description = QLabel("")
        description.setWordWrap(True)
        budget_input = QSpinBox()
        budget_input.setRange(0, 200_000)
        budget_input.setSuffix("만 원")
        budget_input.setSingleStep(100)
        budget_input.setGroupSeparatorShown(True)

        def sync_option(index: int = 0) -> None:
            option = option_combo.itemData(index) or {}
            description.setText(option.get("description", ""))
            budget_input.setMinimum(max(0, int(option.get("min_budget", 0)) // 10000))
            budget_input.setValue(max(budget_input.minimum(), int(option.get("recommended_budget", 0)) // 10000))

        option_combo.currentIndexChanged.connect(sync_option)
        sync_option(option_combo.currentIndex())
        form = QFormLayout()
        form.addRow("방식", option_combo)
        form.addRow("발굴 예산", budget_input)
        layout.addLayout(form)
        layout.addWidget(description)
        discover_button = QPushButton("후보 찾기")
        discover_button.setMinimumHeight(34)
        discover_button.clicked.connect(
            lambda checked=False: self._submit_discovery(option_combo.currentData(), budget_input.value())
        )
        layout.addWidget(discover_button)
        return box

    def _submit_discovery(self, option: dict[str, Any] | None, budget_manwon: int) -> None:
        if not self.on_discover or not option:
            return
        self.on_discover(str(option["id"]), int(budget_manwon) * 10_000)

    def _submit_contract(
        self,
        item: QListWidgetItem | None,
        role: str,
        fee_text: str,
        commitment_months: int,
        sequel_option: bool,
        promotion_obligation: bool,
        promotion_days: int,
        contract_terms: dict[str, Any],
    ) -> None:
        if not self.on_attach:
            return
        person = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not person:
            return
        self._submit_person_contract(
            person,
            role,
            fee_text,
            commitment_months,
            sequel_option,
            promotion_obligation,
            promotion_days,
            contract_terms,
        )

    def _submit_person_contract(
        self,
        person: dict[str, Any],
        role: str,
        fee_text: str,
        commitment_months: int,
        sequel_option: bool,
        promotion_obligation: bool,
        promotion_days: int,
        contract_terms: dict[str, Any],
    ) -> None:
        if not self.on_attach:
            return
        fee = _parse_money(fee_text)
        self.on_attach(
            person["id"],
            role,
            {
                "contract_fee": fee,
                "commitment_months": commitment_months,
                "sequel_option": sequel_option,
                "promotion_obligation": promotion_obligation,
                "promotion_days": promotion_days,
                "contract_terms": contract_terms,
            },
        )

    def _load_contract_for_edit(self, item: QListWidgetItem | None) -> None:
        contract = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not contract:
            self._selected_contract = None
            self.edit_hint.setText("현재 계약을 선택하면 조건을 수정할 수 있습니다. 역할 변경은 새 계약으로 처리합니다.")
            self.edit_fee_input.clear()
            self.edit_commitment.setValue(0)
            self.edit_sequel_option.setChecked(False)
            self.edit_promotion_obligation.setChecked(False)
            self.edit_promotion_days.setValue(0)
            self._set_edit_terms({})
            self._set_edit_enabled(False)
            return
        self._selected_contract = dict(contract)
        self.edit_hint.setText(
            f"{contract.get('role_label', contract.get('role', '-'))} · {contract.get('name_ko', '-')} 계약을 수정합니다."
        )
        self._set_edit_enabled(True)
        self.edit_fee_input.setText(str(int(contract.get("contract_fee") or 0)))
        self.edit_commitment.setValue(int(contract.get("commitment_months") or 0))
        actor_contract = _is_actor_contract(contract)
        self.edit_sequel_option.setChecked(bool(contract.get("sequel_option")))
        self.edit_promotion_obligation.setChecked(bool(contract.get("promotion_obligation")))
        self.edit_promotion_days.setValue(int(contract.get("promotion_days") or 0))
        self._set_edit_terms(contract.get("contract_terms") or {})
        self.edit_sequel_option.setEnabled(actor_contract)

    def _set_edit_enabled(self, enabled: bool) -> None:
        for widget in (
            self.edit_fee_input,
            self.edit_commitment,
            self.edit_sequel_option,
            self.edit_promotion_obligation,
            self.edit_promotion_days,
            self.edit_deferred_fee,
            self.edit_running_guarantee,
            self.edit_running_rate,
            self.edit_running_trigger,
            self.edit_bonus_audience,
            self.edit_bonus_amount,
            self.edit_image_rights,
            self.update_button,
        ):
            widget.setEnabled(enabled)

    def _set_edit_terms(self, terms: dict[str, Any]) -> None:
        running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
        bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
        self.edit_deferred_fee.setValue(int(terms.get("deferredFee") or 0) // 10_000)
        self.edit_running_guarantee.setChecked(bool(running.get("enabled")))
        self.edit_running_rate.setValue(float(running.get("rate") or 0) * 100)
        _set_combo_data(self.edit_running_trigger, str(running.get("trigger") or "break_even"))
        self.edit_bonus_audience.setValue(int(bonus.get("audience") or 0) // 10_000)
        self.edit_bonus_amount.setValue(int(bonus.get("amount") or 0) // 10_000)
        self.edit_image_rights.setChecked(bool(terms.get("imageRights")))

    def _submit_contract_update(self) -> None:
        if not self.on_update or not self._selected_contract:
            return
        actor_contract = _is_actor_contract(self._selected_contract)
        self.on_update(
            str(self._selected_contract["person_id"]),
            str(self._selected_contract["role"]),
            {
                "contract_fee": _parse_money(self.edit_fee_input.text()),
                "commitment_months": self.edit_commitment.value(),
                "sequel_option": self.edit_sequel_option.isChecked() if actor_contract else False,
                "promotion_obligation": self.edit_promotion_obligation.isChecked(),
                "promotion_days": self.edit_promotion_days.value(),
                "contract_terms": _contract_terms_payload(
                    self.edit_deferred_fee.value(),
                    self.edit_running_guarantee.isChecked(),
                    self.edit_running_rate.value(),
                    str(self.edit_running_trigger.currentData() or "break_even"),
                    self.edit_bonus_audience.value(),
                    self.edit_bonus_amount.value(),
                    self.edit_image_rights.isChecked(),
                ),
            },
        )

    @staticmethod
    def _show_person(item: QListWidgetItem | None, detail: QTextEdit) -> None:
        person = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not person:
            detail.setPlainText("")
            return
        detail.setPlainText(
            "\n\n".join(
                [
                    person["name_ko"],
                    f"활동 단계: {person.get('career_stage_label', '정보 부족')}",
                    person.get("career_stage_text", ""),
                    person.get("one_line", ""),
                    person.get("current_ability_text", ""),
                    person.get("potential_text", ""),
                    person.get("fame_text", ""),
                    person.get("brand_text", ""),
                    f"계약 조건: {person.get('contract_text', '아직 계약 전')}",
                    f"현재 관계: {person.get('relationship_stage', '모르는 사이')}",
                    person.get("relationship_text", "아직 이름과 평판 이상으로 확인된 접점이 없다."),
                ]
            )
        )


def _parse_money(text: str) -> int:
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())
    return int(digits or 0)


def _default_actor_commitment_months(default_actor_commitment: dict[str, Any]) -> int:
    try:
        months = int(default_actor_commitment.get("months") or 0)
    except (TypeError, ValueError):
        months = 0
    return max(1, min(36, months or 2))


def _default_discovery_fee_text(role: str) -> str:
    return str(
        {
            "lead_actor": 20_000_000,
            "supporting_actor": 10_000_000,
            "cameo_actor": 5_000_000,
        }.get(role, 10_000_000)
    )


def _pending_offer_line(row: dict[str, Any]) -> str:
    return (
        f"{row.get('due_date_text', '-')} 답변 예정 · "
        f"{row.get('role_label', row.get('role', '-'))} · "
        f"{row.get('name_ko', '-')} · "
        f"{row.get('offer_text', '조건 미정')}"
    )


def _money_spinbox(*, maximum: int) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(0, maximum)
    widget.setSuffix("만 원")
    widget.setSingleStep(100)
    widget.setGroupSeparatorShown(True)
    return widget


def _populate_running_trigger(combo: QComboBox) -> None:
    combo.addItem("손익분기 이후", "break_even")
    combo.addItem("개봉 수익 기준", "release")
    combo.addItem("순이익 발생 시", "profit")


def _set_combo_data(combo: QComboBox, data: str) -> None:
    index = combo.findData(data)
    combo.setCurrentIndex(index if index >= 0 else 0)


def _contract_terms_payload(
    deferred_fee_manwon: int,
    running_enabled: bool,
    running_rate_percent: float,
    running_trigger: str,
    bonus_audience_man: int,
    bonus_amount_manwon: int,
    image_rights: bool,
) -> dict[str, Any]:
    return {
        "packageId": "custom",
        "deferredFee": int(deferred_fee_manwon) * 10_000,
        "runningGuarantee": {
            "enabled": bool(running_enabled),
            "rate": max(0.0, float(running_rate_percent or 0) / 100),
            "trigger": running_trigger,
        },
        "boxOfficeBonus": {
            "enabled": int(bonus_amount_manwon or 0) > 0,
            "audience": int(bonus_audience_man or 0) * 10_000,
            "amount": int(bonus_amount_manwon or 0) * 10_000,
        },
        "imageRights": bool(image_rights),
    }


def _is_actor_contract(contract: dict[str, Any]) -> bool:
    return contract.get("type") == "actor" or contract.get("role") in {"lead_actor", "supporting_actor", "cameo_actor", "actor"}
