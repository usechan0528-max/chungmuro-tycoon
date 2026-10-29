from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.services.game_state import money
from app.services.dialogue_flow_service import (
    advance_dialogue_state,
    build_final_choice,
    current_dialogue_step,
    dialogue_progress_line,
    dialogue_score_line,
    initial_dialogue_state,
    is_multi_step_event,
)
from app.services.progression_service import STAGE_LABELS, can_calculate_release, stage_time_cost_days_for_project


class ProductionScreen(QWidget):
    def __init__(
        self,
        *,
        project: dict[str, Any],
        event: dict[str, Any] | None,
        operations: dict[str, Any] | None = None,
        on_choice: Callable[[dict[str, Any] | None, dict[str, Any]], None],
        on_advance_stage: Callable[[], None],
        on_release: Callable[[], None],
        on_cancel: Callable[[], None],
        on_casting: Callable[[], None] | None = None,
        era_ui: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        era_ui = era_ui or {}
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(str(era_ui.get("productionTitle") or "제작 진행 보고"))
        title.setObjectName("ScreenTitle")
        project_stats = project.get("stats") if isinstance(project.get("stats"), dict) else {}
        stage_days = stage_time_cost_days_for_project(project["stage"], project["scale_id"], project_stats)
        shooting_days = int(project_stats.get("shooting_duration", 0) or 0)
        shooting_line = f" · 촬영 계획 {shooting_days}일" if shooting_days else ""
        distribution = project.get("distribution") if isinstance(project.get("distribution"), dict) else {}
        distribution_label = distribution.get("label") or project_stats.get("distributor_name") or "배급사 미정"
        distribution_summary = distribution.get("summary") or project_stats.get("distribution_match_summary") or ""
        distribution_line = f"\n배급: {distribution_label}"
        if distribution_summary:
            distribution_line += f"\n{distribution_summary}"
        summary = QLabel(
            f"{project['title']} · {project['genre_name']} · {project['scale_name']}\n"
            f"제작비 {money(project['production_budget'])} · 마케팅비 {money(project['marketing_budget'])}\n"
            f"현재 단계: {STAGE_LABELS.get(project['stage'], project['stage'])} · "
            f"예상 소요 {stage_days}일{shooting_line}"
            f"{distribution_line}"
        )
        summary.setWordWrap(True)
        summary.setObjectName("PanelText")
        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addSpacing(12)

        if era_ui:
            era_box = QGroupBox(str(era_ui.get("label") or "시대별 제작 감각"))
            era_layout = QVBoxLayout(era_box)
            for line in (era_ui.get("productionLines") or [])[:4]:
                item = QLabel(f"- {line}")
                item.setWordWrap(True)
                era_layout.addWidget(item)
            layout.addWidget(era_box)
            layout.addSpacing(8)

        if operations:
            ops_summary = QLabel(operations.get("summary", "제작 운영 정보가 아직 정리되지 않았습니다."))
            ops_summary.setWordWrap(True)
            ops_summary.setObjectName("PanelText")
            layout.addWidget(ops_summary)
            layout.addWidget(_operations_box(operations))
            if on_casting:
                casting_button = QPushButton("캐스팅/계약 관리")
                casting_button.clicked.connect(on_casting)
                layout.addWidget(casting_button)
            layout.addSpacing(10)

        if event:
            event_title = QLabel(event["title"])
            event_title.setObjectName("SectionTitle")
            event_description = QLabel(event["description"])
            event_description.setWordWrap(True)
            layout.addWidget(event_title)
            layout.addWidget(event_description)
            layout.addSpacing(10)

            if is_multi_step_event(event):
                self._event = event
                self._on_choice = on_choice
                self._dialogue_state = initial_dialogue_state(event)
                self._dialogue_container = QWidget()
                self._dialogue_layout = QVBoxLayout(self._dialogue_container)
                layout.addWidget(self._dialogue_container)
                self._render_dialogue_step()
            else:
                for choice in event["choices"]:
                    button = QPushButton(_choice_button_text(choice, event))
                    button.setMinimumHeight(40)
                    button.setToolTip(_choice_hint(choice))
                    button.clicked.connect(
                        lambda checked=False, current_event=event, selected=choice: on_choice(current_event, selected)
                    )
                    layout.addWidget(button)
                    hint = QLabel(_choice_hint(choice))
                    hint.setWordWrap(True)
                    hint.setObjectName("MutedText")
                    layout.addWidget(hint)
        elif project["stage"] == "production_announcement" and int(project_stats.get("cast_confirmed", 0) or 0) <= 0:
            ready_label = QLabel("제작 발표회 전에는 공식 출연진 확정이 필요합니다. 캐스팅/계약 관리에서 출연 계약을 정리한 뒤 출연진을 확정하세요.")
            ready_label.setWordWrap(True)
            layout.addWidget(ready_label)
            if on_casting:
                casting_button = QPushButton("캐스팅/계약 관리")
                casting_button.clicked.connect(on_casting)
                layout.addWidget(casting_button)
        elif can_calculate_release(project["stage"]):
            ready_label = QLabel("제작 단계가 종료되었습니다. 이제 극장 1차 시장 상영을 시작할 수 있습니다.")
            ready_label.setWordWrap(True)
            layout.addWidget(ready_label)
            release_button = QPushButton("1차 시장 개봉")
            release_button.clicked.connect(on_release)
            layout.addWidget(release_button)
        else:
            stage_label = QLabel("이번 단계는 보고할 주요 변수 없이 진행 중입니다.")
            stage_label.setWordWrap(True)
            layout.addWidget(stage_label)
            advance_button = QPushButton("다음 제작 단계")
            advance_button.clicked.connect(on_advance_stage)
            layout.addWidget(advance_button)

        back_button = QPushButton("대시보드로")
        back_button.clicked.connect(on_cancel)
        layout.addStretch(1)
        layout.addWidget(back_button)

    def _render_dialogue_step(self) -> None:
        _clear_layout(self._dialogue_layout)
        event = self._event
        state = self._dialogue_state
        steps = event.get("steps") or []
        step = current_dialogue_step(event, state)
        if not step:
            self._on_choice(event, build_final_choice(event, state))
            return

        progress = QLabel(dialogue_progress_line(event, state))
        progress.setObjectName("MutedText")
        self._dialogue_layout.addWidget(progress)

        score = QLabel(dialogue_score_line(event, state))
        score.setWordWrap(True)
        score.setObjectName("MutedText")
        self._dialogue_layout.addWidget(score)

        if state.get("transcript"):
            history = QLabel(_dialogue_history_text(state["transcript"]))
            history.setWordWrap(True)
            history.setObjectName("PanelText")
            self._dialogue_layout.addWidget(history)

        npc_line = QLabel(str(step.get("npcLine") or step.get("question") or "상대가 당신의 답을 기다리고 있습니다."))
        npc_line.setWordWrap(True)
        npc_line.setObjectName("SectionTitle")
        self._dialogue_layout.addWidget(npc_line)

        for choice in step.get("choices", []):
            if not isinstance(choice, dict):
                continue
            button = QPushButton(_choice_button_text(choice, event))
            button.setMinimumHeight(40)
            button.setToolTip(_choice_hint(choice))
            button.clicked.connect(lambda checked=False, selected=choice: self._advance_dialogue(selected))
            self._dialogue_layout.addWidget(button)
            hint = QLabel(_choice_hint(choice))
            hint.setWordWrap(True)
            hint.setObjectName("MutedText")
            self._dialogue_layout.addWidget(hint)

        walk_out = _walk_out_choice(event)
        if walk_out:
            walk_button = QPushButton(_choice_button_text(walk_out, event))
            walk_button.setMinimumHeight(40)
            walk_button.clicked.connect(lambda checked=False, selected=walk_out: self._on_choice(event, selected))
            self._dialogue_layout.addWidget(walk_button)
            walk_hint = QLabel(_choice_hint(walk_out))
            walk_hint.setWordWrap(True)
            walk_hint.setObjectName("MutedText")
            self._dialogue_layout.addWidget(walk_hint)

    def _advance_dialogue(self, choice: dict[str, Any]) -> None:
        self._dialogue_state, completed = advance_dialogue_state(self._event, self._dialogue_state, choice)
        if completed:
            self._on_choice(self._event, build_final_choice(self._event, self._dialogue_state))
            return
        self._render_dialogue_step()


def _choice_hint(choice: dict[str, Any]) -> str:
    if choice.get("description"):
        return str(choice["description"])
    effects = choice.get("effects") or choice.get("effectsOnSuccess") or choice.get("effectsOnFailure") or {}
    if not isinstance(effects, dict):
        return "선택 후 내부 수치가 변한다. 결과는 장점과 부담을 함께 남길 수 있다."
    positive = _effect_categories(effects, positive=True)
    negative = _effect_categories(effects, positive=False)
    if positive and negative:
        return f"예상: {', '.join(positive[:2])}에 도움이 되지만 {', '.join(negative[:2])} 부담이 생길 수 있다."
    if positive:
        return f"예상: {', '.join(positive[:2])}에 도움이 된다. 다만 비용, 일정, 관계 중 하나의 부담이 뒤따를 수 있다."
    if negative:
        return f"예상: {', '.join(negative[:2])} 부담이 있다. 대신 작은 학습이나 관계 정리 효과가 남을 수 있다."
    return "예상: 겉으로 드러나는 변화는 작지만, 제작 기록에는 선택의 여파가 남는다."


def _choice_button_text(choice: dict[str, Any], event: dict[str, Any] | None) -> str:
    spoken = choice.get("spokenText") or choice.get("line")
    if spoken:
        return f"“{spoken}”"
    if _uses_dialogue_buttons(event, choice):
        return f"“{choice.get('text', '')}”"
    return str(choice.get("text", ""))


def _uses_dialogue_buttons(event: dict[str, Any] | None, choice: dict[str, Any]) -> bool:
    if not event or choice.get("id") == "walk_out":
        return False
    style = event.get("choiceStyle") or choice.get("choiceStyle")
    if style in {"dialogue", "spoken"}:
        return True
    if event.get("relationshipEvent"):
        return True
    return False


def _walk_out_choice(event: dict[str, Any]) -> dict[str, Any] | None:
    for choice in event.get("choices", []):
        if isinstance(choice, dict) and choice.get("id") == "walk_out":
            return choice
    return None


def _dialogue_history_text(transcript: list[dict[str, Any]]) -> str:
    lines = ["이전 문답"]
    for item in transcript[-3:]:
        choice = item.get("choiceText")
        response = item.get("response")
        if choice and response:
            lines.append(f"- {choice}: {response}")
        elif choice:
            lines.append(f"- {choice}")
    return "\n".join(lines)


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _operations_box(operations: dict[str, Any]) -> QGroupBox:
    box = QGroupBox("제작 운영")
    layout = QVBoxLayout(box)
    tabs = QTabWidget()
    scenario = operations.get("scenarioDevelopment", [])[:5]
    crew = operations.get("crew", [])[:5]
    contracts = operations.get("contracts", [])[:5]
    versions = operations.get("versions", [])[:4]
    locations = operations.get("locations", [])[:2]
    shooting = operations.get("shootingSchedule", [])[:4]
    cashflows = operations.get("cashflows", [])[:5]
    screenings = operations.get("testScreenings", [])[-2:]
    reshoots = operations.get("reshoots", [])[-2:]
    marketing_assets = operations.get("marketingAssets", [])[:4]
    marketing_reactions = operations.get("marketingReactions", [])[-3:]
    stage_greetings = operations.get("stageGreetings", [])[-3:]

    scenario_lines: list[str] = []
    for row in scenario:
        risk = f" · {row.get('riskNote')}" if row.get("riskNote") else ""
        scenario_lines.append(
            f"시나리오 · {row['stepName']} · {row['statusLabel']} · "
            f"{row.get('diagnosisText', '')}{risk}"
        )

    crew_lines: list[str] = []
    for row in crew:
        crew_lines.append(
            f"제작진 · {row['department']} · {row['roleName']} · "
            f"{_crew_status_text(row.get('filledStatus'))} · 예상 {money(row.get('estimatedFee', 0))}"
        )

    contract_lines: list[str] = []
    for row in contracts:
        contract_lines.append(
            f"계약 · {row['name']} · {row['summary']} · 계약금 {money(row.get('contractFee', 0))}"
        )
    for row in versions:
        selected = []
        if row.get("selectedForTheatrical"):
            selected.append("극장")
        if row.get("selectedForOtt"):
            selected.append("OTT")
        selected_text = f" · 선택: {', '.join(selected)}" if selected else ""
        contract_lines.append(
            f"판본 · {row['name']} · {row['statusLabel']} · {row['runtimeMinutes']}분{selected_text} · "
            f"{row.get('description', '')}"
        )

    logistics_lines: list[str] = []
    for row in locations:
        cost = f" · 추가 {money(row.get('costImpact', 0))}" if row.get("costImpact") else ""
        days = f" · 일정 +{row.get('durationDeltaDays')}일" if row.get("durationDeltaDays") else ""
        risk = f" · 허가 리스크 {row.get('permitRiskDelta'):+d}" if row.get("permitRiskDelta") else ""
        logistics_lines.append(f"로케이션 · {row['name']} · {row['locationType']}{cost}{days}{risk}")
    for row in shooting:
        logistics_lines.append(
            f"촬영표 · {row['date']} · {row['unitName']} · {row['plannedDays']}일 · {row['locationType']}"
        )
    for row in cashflows:
        status = "집행" if row.get("status") == "paid" else "예정"
        logistics_lines.append(f"현금흐름 · {status} · {row['date']} · {money(row['amount'])} · {row['description']}")

    feedback_lines: list[str] = []
    for row in screenings:
        feedback_lines.append(f"테스트 시사회 · {row['date']} · {row['scoreBand']} · {row['resultSummary']}")
    for row in reshoots:
        feedback_lines.append(f"재촬영 · {row['date']} · {row['plannedDays']}일 · {money(row['estimatedCost'])} · {row['reason']}")

    marketing_lines: list[str] = []
    for row in marketing_assets:
        date = row.get("releaseDate") or row.get("plannedDate") or "미정"
        status = "공개" if row.get("status") == "released" else "예정"
        buzz = f" · {_buzz_text(row.get('buzzScore'))}" if row.get("buzzScore") else ""
        marketing_lines.append(f"마케팅 소재 · {status} · {date} · {row['assetLabel']} · {row['channel']}{buzz}")
    for row in marketing_reactions:
        summary = row.get("onlineSummary") or row.get("audienceSummary") or row.get("pressSummary") or "반응 기록"
        marketing_lines.append(
            f"소재 반응 · {row['date']} · {row['assetLabel']} · {row['sentimentBand']} · "
            f"{_buzz_text(row.get('buzzScore'))} · {summary}"
        )
    for row in stage_greetings:
        marketing_lines.append(
            f"무대인사 · {row['date']} · {row['city']} {row['venue']} · "
            f"{money(row['estimatedCost'])} · {row['castScope']}"
        )
    tabs.addTab(_list_tab(scenario_lines, "시나리오 개발 기록 없음"), "시나리오")
    tabs.addTab(_list_tab(crew_lines, "제작진 구성 기록 없음"), "제작진")
    tabs.addTab(_list_tab(contract_lines, "계약/판본 기록 없음"), "계약/판본")
    tabs.addTab(_list_tab(logistics_lines, "촬영표와 현금흐름 기록 없음"), "일정/현금")
    tabs.addTab(_list_tab(feedback_lines, "시사회와 재촬영 기록 없음"), "시사/재촬영")
    tabs.addTab(_list_tab(marketing_lines, "마케팅 소재와 무대인사 기록 없음"), "마케팅")
    layout.addWidget(tabs)
    return box


def _list_tab(lines: list[str], empty_text: str) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    items = QListWidget()
    for line in lines:
        items.addItem(line)
    if not lines:
        items.addItem(empty_text)
    items.setMinimumHeight(165)
    layout.addWidget(items)
    return tab


def _crew_status_text(status: Any) -> str:
    labels = {
        "planned": "구성 예정",
        "lean": "축소 운영",
        "veteran": "베테랑 보강",
        "filled": "구성 완료",
        "delayed": "확정 지연",
    }
    return labels.get(str(status or ""), str(status or "구성 예정"))


def _buzz_text(value: Any) -> str:
    try:
        score = int(float(value or 0))
    except (TypeError, ValueError):
        score = 0
    if score >= 85:
        return "반응이 크게 폭발함"
    if score >= 65:
        return "온라인 반응이 강함"
    if score >= 45:
        return "관심이 붙는 중"
    if score >= 25:
        return "반응은 제한적"
    return "아직 조용함"


def _effect_categories(effects: dict[str, Any], *, positive: bool) -> list[str]:
    flat = _flatten_effects(effects)
    categories: list[str] = []
    quality_keys = {
        "scenario_quality", "directing_quality", "acting_quality", "casting_fit",
        "shooting_quality", "art_costume_prop_quality", "action_stunt_quality",
        "vfx_quality", "music_sound_quality", "editing_quality", "genre_satisfaction",
        "final_quality",
        "script_structure", "script_dialogue", "script_character_motivation",
        "script_pacing", "script_originality", "investor_package_readiness",
        "adaptation_rights_clarity",
    }
    market_keys = {
        "pre_release_interest", "reservation_rate", "word_of_mouth", "online_buzz",
        "rewatch_index", "fandom_index", "final_audience", "secondary_market_revenue",
    }
    reputation_keys = {
        "public_reputation", "industry_reputation", "critic_reputation",
        "investor_reputation", "creative_reputation", "global_reputation",
    }
    network_keys = {
        "actor_network", "director_network", "production_network", "investor_network",
        "distribution_network", "press_network", "critic_access", "festival_network",
        "school_network", "regional_network",
    }
    risk_keys = {
        "financial_risk", "production_shutdown_risk", "schedule_delay_risk",
        "budget_overrun_risk", "on_set_conflict_risk", "plagiarism_risk",
        "controversy_risk", "press_backlash_risk", "critic_backlash_risk",
        "audience_rejection_risk", "game_over_risk", "series_fatigue",
        "script_structure_issue", "script_dialogue_weakness",
        "character_motivation_issue", "script_pacing_issue",
        "investor_package_risk", "adaptation_rights_risk",
    }
    time_keys = {
        "production_duration", "pre_production_duration", "shooting_duration",
        "shooting_duration_delta_days", "post_production_duration", "marketing_duration", "release_timing", "delay_days",
    }
    if _has_direction(flat, {"cash", "investment_amount", "secondary_market_revenue"}, positive=positive):
        categories.append("자금")
    if _has_direction(flat, quality_keys, positive=positive):
        categories.append("완성도")
    if _has_direction(flat, market_keys, positive=positive):
        categories.append("흥행")
    if _has_direction(flat, reputation_keys, positive=positive):
        categories.append("명성")
    if _has_direction(flat, network_keys, positive=positive):
        categories.append("인맥")
    if positive and _has_direction(flat, risk_keys, positive=False):
        categories.append("위험 관리")
    if not positive and _has_direction(flat, risk_keys, positive=True):
        categories.append("리스크")
    if positive and _has_direction(flat, time_keys, positive=False):
        categories.append("일정")
    if not positive and _has_direction(flat, time_keys, positive=True):
        categories.append("일정")
    return _dedupe(categories)


def _flatten_effects(effects: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in effects.items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _has_direction(values: dict[str, Any], keys: set[str], *, positive: bool) -> bool:
    for key in keys:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if positive and value > 0:
            return True
        if not positive and value < 0:
            return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
