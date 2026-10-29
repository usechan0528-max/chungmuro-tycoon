from __future__ import annotations

from copy import deepcopy
from typing import Any


EFFECT_SECTIONS = {"stats", "reputation", "network", "studio", "playerStats", "flags"}
NEGOTIATION_ACTIONS = {"push", "package", "concede", "accept"}


def is_multi_step_event(event: dict[str, Any] | None) -> bool:
    return bool(
        event
        and (
            (isinstance(event.get("steps"), list) and event.get("steps"))
            or _has_negotiation(event)
        )
    )


def initial_dialogue_state(event: dict[str, Any]) -> dict[str, Any]:
    state = {
        "step_index": 0,
        "scores": {},
        "effects": {},
        "transcript": [],
    }
    if not event.get("steps") and _has_negotiation(event):
        _ensure_negotiation_state(event, state)
    return state


def current_dialogue_step(event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    steps = event.get("steps") or []
    index = int(state.get("step_index", 0) or 0)
    if index < 0 or index >= len(steps):
        if _has_negotiation(event):
            _ensure_negotiation_state(event, state)
            return _negotiation_step(event, state)
        return None
    step = steps[index]
    return step if isinstance(step, dict) else None


def dialogue_progress_line(event: dict[str, Any], state: dict[str, Any]) -> str:
    step = current_dialogue_step(event, state)
    if step and step.get("_phase") == "negotiation":
        negotiation = state.get("negotiation") or {}
        round_index = int(negotiation.get("round_index", 0) or 0) + 1
        round_limit = int(negotiation.get("round_limit", 1) or 1)
        return f"가격 협상 {round_index}/{round_limit}"
    steps = event.get("steps") or []
    return f"문답 {int(state.get('step_index', 0)) + 1}/{len(steps)}"


def advance_dialogue_state(
    event: dict[str, Any],
    state: dict[str, Any],
    choice: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    updated = deepcopy(state)
    step = current_dialogue_step(event, updated) or {}
    if step.get("_phase") == "negotiation":
        _merge_effects(updated.setdefault("effects", {}), choice.get("effects", {}))
        _merge_scores(updated.setdefault("scores", {}), choice.get("scoreEffects", choice.get("scores", {})))
        _advance_negotiation(event, updated, choice)
        updated.setdefault("transcript", []).append(
            {
                "stepId": step.get("id"),
                "npcLine": step.get("npcLine") or "",
                "choiceText": _spoken_choice_text(choice),
                "response": choice.get("resultText") or _negotiation_choice_response(event, updated, choice),
            }
        )
        negotiation = updated.get("negotiation") or {}
        return updated, negotiation.get("status") in {"accepted", "stalled"}

    _merge_effects(updated.setdefault("effects", {}), choice.get("effects", {}))
    _merge_scores(updated.setdefault("scores", {}), choice.get("scoreEffects", choice.get("scores", {})))
    updated.setdefault("transcript", []).append(
            {
                "stepId": step.get("id"),
                "npcLine": step.get("npcLine") or step.get("question") or "",
                "choiceText": _spoken_choice_text(choice),
                "response": choice.get("resultText") or choice.get("successText") or "",
            }
        )
    updated["step_index"] = int(updated.get("step_index", 0) or 0) + 1
    scripted_done = updated["step_index"] >= len(event.get("steps") or [])
    if scripted_done and _has_negotiation(event):
        _ensure_negotiation_state(event, updated)
        return updated, False
    return updated, scripted_done


def build_final_choice(event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    outcome = _select_outcome(event, state)
    effects = deepcopy(state.get("effects", {}))
    _merge_effects(effects, outcome.get("effects", {}))
    negotiation_effects, negotiation_text = _negotiation_final_effects(event, state)
    _merge_effects(effects, negotiation_effects)
    result_text = outcome.get("resultText") or "대화의 누적 결과가 프로젝트에 반영되었습니다."
    if negotiation_text:
        result_text = f"{result_text}\n\n{negotiation_text}"
    transcript = _transcript_summary(state.get("transcript", []))
    if transcript:
        result_text = f"{result_text}\n\n대화 흐름:\n{transcript}"
    return {
        "id": f"{event.get('id', 'dialogue')}_multi_result",
        "text": "대화 결과를 받아들인다",
        "resultText": result_text,
        "effects": effects,
        "disableAutoTradeoff": bool(outcome.get("disableAutoTradeoff")),
    }


def dialogue_score_line(event: dict[str, Any], state: dict[str, Any]) -> str:
    scores = state.get("scores") or {}
    negotiation = _negotiation_mood_line(event, state)
    if not scores:
        return negotiation or "대화 분위기: 아직 상대의 속내를 읽기 어렵습니다."
    cues = _dialogue_cues(scores)
    if not cues:
        base = "대화 분위기: 뚜렷하게 기울지는 않았지만, 상대는 답변의 결을 살피고 있습니다."
        return f"{base} {negotiation}" if negotiation else base
    base = "대화 분위기: " + " ".join(cues[:3])
    return f"{base} {negotiation}" if negotiation else base


def _has_negotiation(event: dict[str, Any] | None) -> bool:
    negotiation = event.get("negotiation") if isinstance(event, dict) else None
    return isinstance(negotiation, dict) and bool(negotiation.get("enabled", True))


def _ensure_negotiation_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    if not _has_negotiation(event) or isinstance(state.get("negotiation"), dict):
        return
    config = event.get("negotiation") or {}
    initial_amount = int(config.get("initialAmount", config.get("startAmount", 0)) or 0)
    state["negotiation"] = {
        "round_index": 0,
        "round_limit": _negotiation_round_limit(config, state.get("scores", {})),
        "current_amount": _clamp_amount(config, initial_amount),
        "accepted_amount": None,
        "status": "active",
        "last_action": None,
    }


def _negotiation_round_limit(config: dict[str, Any], scores: dict[str, Any]) -> int:
    minimum = int(config.get("minRounds", 1) or 1)
    maximum = int(config.get("maxRounds", 4) or 4)
    rounds = int(config.get("baseRounds", 2) or 2)
    positive_keys = ("trust", "confidence", "interest", "global", "domestic", "prestige", "ip", "fit")
    tense_keys = ("heat", "risk", "control", "imageRisk", "cost")
    positive_pressure = sum(_score(scores, key) for key in positive_keys)
    tense_pressure = sum(max(0.0, _score(scores, key)) for key in tense_keys)
    weak_pressure = sum(min(0.0, _score(scores, key)) for key in positive_keys)
    if positive_pressure >= 8:
        rounds += 1
    if tense_pressure >= 8:
        rounds += 1
    if weak_pressure <= -5:
        rounds -= 1
    return max(minimum, min(maximum, rounds))


def _negotiation_step(event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    negotiation = state.get("negotiation") or {}
    if negotiation.get("status") in {"accepted", "stalled"}:
        return None
    config = event.get("negotiation") or {}
    current_amount = int(negotiation.get("current_amount", 0) or 0)
    price_label = str(config.get("priceLabel") or "현재 제안")
    topic = str(config.get("topic") or "계약 조건")
    npc_line = str(
        config.get("npcLine")
        or f"상대는 {topic}을 두고 다시 계산기를 두드립니다. {price_label}: {_amount_text(current_amount)}"
    )
    return {
        "id": f"{event.get('id', 'dialogue')}_negotiation",
        "_phase": "negotiation",
        "npcLine": npc_line,
        "choices": _negotiation_choices(config, current_amount),
    }


def _negotiation_choices(config: dict[str, Any], current_amount: int) -> list[dict[str, Any]]:
    topic = str(config.get("topic") or "조건")
    step_amount = _step_amount(config)
    return [
        {
            "id": "negotiation_push_higher",
            "text": "더 높은 조건을 요구한다",
            "spokenText": "조건을 조금 더 맞춰주시면, 저희도 이 프로젝트를 확실히 키우겠습니다.",
            "description": "금액은 올라갈 수 있지만 상대의 피로와 결렬 위험도 함께 커진다.",
            "resultText": f"{topic}을 더 밀어붙였습니다. 상대는 즉답 대신 다음 조건을 다시 꺼냅니다.",
            "negotiationAction": "push",
            "amountDelta": step_amount,
            "scoreEffects": {"money": 3, "trust": -1, "risk": 2, "heat": 1},
        },
        {
            "id": "negotiation_package_terms",
            "text": "권리와 일정 조건을 묶어 역제안한다",
            "spokenText": "금액만 보지 말고 공개 창구와 홍보 조건까지 같이 묶어보시죠.",
            "description": "금액만 올리기보다 창구, 홍보, 일정, 권리 범위를 조합해 타협점을 찾는다.",
            "resultText": "금액과 비금전 조건을 함께 묶자 상대도 조금 더 계산해볼 여지를 보입니다.",
            "negotiationAction": "package",
            "amountDelta": int(step_amount * 0.6),
            "scoreEffects": {"money": 1, "trust": 1, "control": -1},
        },
        {
            "id": "negotiation_concede_close",
            "text": "일부 양보하고 타결을 압박한다",
            "spokenText": "이 정도면 서로 잃을 것 없이 마무리할 수 있습니다.",
            "description": "최고 조건은 아니지만 협상을 빠르게 닫아 일정과 관계를 지킨다.",
            "resultText": "당신이 일부 조건을 접자 상대도 서류를 정리할 준비를 합니다.",
            "negotiationAction": "concede",
            "amountDelta": int(step_amount * 0.25),
            "scoreEffects": {"money": 1, "trust": 2, "risk": -1},
        },
        {
            "id": "negotiation_accept_current",
            "text": "현재 조건을 수락한다",
            "spokenText": "좋습니다. 그 조건으로 가겠습니다.",
            "description": "추가 협상 여지는 줄지만 결렬 위험을 낮추고 바로 합의한다.",
            "resultText": "당신은 현재 조건으로 악수를 청했습니다.",
            "negotiationAction": "accept",
            "amountDelta": 0,
            "scoreEffects": {"trust": 1, "risk": -2},
        },
    ]


def _advance_negotiation(event: dict[str, Any], state: dict[str, Any], choice: dict[str, Any]) -> None:
    _ensure_negotiation_state(event, state)
    negotiation = state.get("negotiation") or {}
    config = event.get("negotiation") or {}
    action = str(choice.get("negotiationAction") or "")
    if action not in NEGOTIATION_ACTIONS:
        action = "package"

    current_amount = int(negotiation.get("current_amount", 0) or 0)
    next_amount = _clamp_amount(config, current_amount + int(choice.get("amountDelta", 0) or 0))
    negotiation["current_amount"] = next_amount
    negotiation["last_action"] = action

    if action == "accept":
        negotiation["status"] = "accepted"
        negotiation["accepted_amount"] = current_amount
        return
    if action == "concede" and _should_close_after_concession(state):
        negotiation["status"] = "accepted"
        negotiation["accepted_amount"] = next_amount
        return

    negotiation["round_index"] = int(negotiation.get("round_index", 0) or 0) + 1
    if negotiation["round_index"] >= int(negotiation.get("round_limit", 1) or 1):
        if _should_auto_accept(state):
            negotiation["status"] = "accepted"
            negotiation["accepted_amount"] = next_amount
        else:
            negotiation["status"] = "stalled"
            negotiation["accepted_amount"] = None


def _should_close_after_concession(state: dict[str, Any]) -> bool:
    scores = state.get("scores") or {}
    return _score(scores, "trust") + _score(scores, "interest") + _score(scores, "fit") >= 5


def _should_auto_accept(state: dict[str, Any]) -> bool:
    scores = state.get("scores") or {}
    positive = (
        _score(scores, "trust")
        + _score(scores, "confidence")
        + _score(scores, "interest")
        + _score(scores, "global")
        + _score(scores, "domestic")
        + _score(scores, "ip")
    )
    risk = max(0.0, _score(scores, "risk")) + max(0.0, _score(scores, "heat"))
    return positive - risk >= 4


def _negotiation_final_effects(event: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not _has_negotiation(event):
        return {}, ""
    negotiation = state.get("negotiation") or {}
    config = event.get("negotiation") or {}
    status = negotiation.get("status")
    if status == "accepted":
        amount = int(negotiation.get("accepted_amount") or negotiation.get("current_amount") or 0)
        effect_key = str(config.get("effectKey") or "")
        amount_sign = int(config.get("amountSign", 1) or 1)
        effects = deepcopy(config.get("effectsOnAgreement", {}))
        if effect_key and amount:
            _merge_effects(effects, {effect_key: amount * amount_sign})
        text = str(
            config.get("acceptedText")
            or f"가격 협상은 {_amount_text(amount)} 조건에서 타결되었습니다."
        )
        return effects, text
    if status == "stalled":
        effects = deepcopy(config.get("effectsOnStall", {"delay_days": 3, "schedule_delay_risk": 2}))
        text = str(config.get("stalledText") or "가격 협상은 결론 없이 보류되었고, 일정과 관계에 부담이 남았습니다.")
        return effects, text
    return {}, ""


def _negotiation_mood_line(event: dict[str, Any], state: dict[str, Any]) -> str:
    negotiation = state.get("negotiation")
    if not isinstance(negotiation, dict) or negotiation.get("status") != "active":
        return ""
    config = event.get("negotiation") or {}
    current_amount = int(negotiation.get("current_amount", 0) or 0)
    topic = str(config.get("topic") or "조건")
    if int(negotiation.get("round_index", 0) or 0) == 0:
        return f"가격 협상: {topic}을 두고 첫 제안이 오가는 중입니다."
    return f"가격 협상: 현재 논의는 {_amount_text(current_amount)} 부근에서 다시 흔들리고 있습니다."


def _negotiation_choice_response(event: dict[str, Any], state: dict[str, Any], choice: dict[str, Any]) -> str:
    negotiation = state.get("negotiation") or {}
    status = negotiation.get("status")
    if status == "accepted":
        amount = int(negotiation.get("accepted_amount") or 0)
        return f"상대는 {_amount_text(amount)} 조건으로 합의할 수 있다는 신호를 보냈습니다."
    if status == "stalled":
        return "상대는 더 이상 양보하기 어렵다며 답을 미뤘습니다."
    amount = int(negotiation.get("current_amount", 0) or 0)
    return f"다음 역제안의 기준점은 {_amount_text(amount)} 쪽으로 움직였습니다."


def _step_amount(config: dict[str, Any]) -> int:
    return max(1, int(config.get("stepAmount", 100000000) or 100000000))


def _clamp_amount(config: dict[str, Any], amount: int) -> int:
    minimum = int(config.get("minAmount", -500000000) or -500000000)
    maximum = int(config.get("maxAmount", 1000000000) or 1000000000)
    return max(minimum, min(maximum, int(amount)))


def _amount_text(amount: int | float) -> str:
    value = int(amount)
    sign = "+" if value > 0 else ""
    abs_value = abs(value)
    if abs_value >= 100000000:
        amount_text = f"{abs_value / 100000000:.1f}억 원"
    elif abs_value >= 10000:
        amount_text = f"{abs_value / 10000:.0f}만 원"
    else:
        amount_text = f"{abs_value:,}원"
    return f"{sign}{amount_text}" if value >= 0 else f"-{amount_text}"


def _select_outcome(event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    outcomes = event.get("finalOutcomes") or []
    default_outcome: dict[str, Any] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        if outcome.get("default"):
            default_outcome = outcome
            continue
        if _conditions_match(outcome.get("conditions", {}), state.get("scores", {})):
            return outcome
    return default_outcome or {
        "id": "mixed_result",
        "resultText": "대화는 뚜렷한 결론 없이 끝났지만, 남은 감정과 조건이 프로젝트에 반영되었습니다.",
        "effects": {"schedule_delay_risk": 2},
    }


def _conditions_match(conditions: Any, scores: dict[str, Any]) -> bool:
    if not isinstance(conditions, dict):
        return False
    for key, threshold in (conditions.get("minScores") or {}).items():
        if float(scores.get(key, 0) or 0) < float(threshold):
            return False
    for key, threshold in (conditions.get("maxScores") or {}).items():
        if float(scores.get(key, 0) or 0) > float(threshold):
            return False
    return True


def _merge_scores(target: dict[str, Any], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        target[key] = float(target.get(key, 0) or 0) + float(value or 0)


def _merge_effects(target: dict[str, Any], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        if key in EFFECT_SECTIONS and isinstance(value, dict):
            section = target.setdefault(key, {})
            if isinstance(section, dict):
                _merge_effects(section, value)
            else:
                target[key] = deepcopy(value)
            continue
        if isinstance(value, dict):
            target[key] = deepcopy(value)
            continue
        if _is_number(value) and _is_number(target.get(key)):
            target[key] = target[key] + value
        else:
            target[key] = deepcopy(value)


def _transcript_summary(transcript: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in transcript[-4:]:
        choice = item.get("choiceText")
        response = item.get("response")
        if choice and response:
            lines.append(f"- {choice} / {response}")
        elif choice:
            lines.append(f"- {choice}")
    return "\n".join(lines)


def _spoken_choice_text(choice: dict[str, Any]) -> str:
    spoken = choice.get("spokenText") or choice.get("line")
    if spoken:
        return f"“{spoken}”"
    return str(choice.get("text", ""))


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _dialogue_cues(scores: dict[str, Any]) -> list[str]:
    cues: list[str] = []
    confidence = _score(scores, "confidence")
    trust = _score(scores, "trust")
    heat = _score(scores, "heat")
    control = _score(scores, "control")
    creative = _score(scores, "creative")
    interest = _score(scores, "interest")
    image_risk = _score(scores, "imageRisk")
    cost = _score(scores, "cost")
    performance = _score(scores, "performance")
    fit = _score(scores, "fit")
    risk = _score(scores, "risk")
    team = _score(scores, "team")
    global_reach = _score(scores, "global")
    theatrical = _score(scores, "theatrical")
    money = _score(scores, "money")
    prestige = _score(scores, "prestige")
    reach = _score(scores, "reach")
    domestic = _score(scores, "domestic")
    promo = _score(scores, "promo")
    ip = _score(scores, "ip")
    brand = _score(scores, "brand")

    if confidence >= 4:
        cues.append("상대가 계산의 현실성을 어느 정도 받아들이는 눈치입니다.")
    elif confidence <= -2:
        cues.append("상대는 근거가 아직 빈약하다고 느끼는 듯합니다.")
    if trust >= 3:
        cues.append("대화의 신뢰가 조금씩 쌓이고 있습니다.")
    elif trust <= -2:
        cues.append("상대가 말의 빈틈을 조심스럽게 경계합니다.")
    if heat >= 4:
        cues.append("관심은 뜨겁지만, 그만큼 조건도 강해질 수 있습니다.")
    elif heat <= -2:
        cues.append("상대의 흥미가 빠르게 식는 분위기입니다.")
    if control >= 3:
        cues.append("상대는 주도권을 자기 쪽으로 가져오려 합니다.")
    elif control <= -2:
        cues.append("조건 조율의 여지는 아직 남아 보입니다.")
    if creative >= 3:
        cues.append("창작 방향에 대한 존중이 조금 생긴 듯합니다.")
    elif creative <= -2:
        cues.append("창작 자율성에는 압박이 걸릴 조짐입니다.")
    if interest >= 4:
        cues.append("상대가 프로젝트 자체에는 분명한 흥미를 보입니다.")
    elif interest <= -2:
        cues.append("상대의 관심을 붙잡기 어려워지고 있습니다.")
    if image_risk >= 2:
        cues.append("이미지 손상에 대한 우려가 표정에 남아 있습니다.")
    elif image_risk <= -2:
        cues.append("이미지 부담은 조금 누그러진 듯합니다.")
    if cost >= 3:
        cues.append("조건과 비용 부담이 슬슬 커지는 흐름입니다.")
    elif cost <= -2:
        cues.append("조건을 가볍게 만들 여지가 보입니다.")
    if performance >= 4:
        cues.append("방 안의 시선이 배우의 가능성 쪽으로 기울고 있습니다.")
    elif performance <= -2:
        cues.append("연기 반응은 아직 확신을 주지 못합니다.")
    if fit >= 3:
        cues.append("배역과 사람의 궁합이 조금씩 보이기 시작합니다.")
    elif fit <= -2:
        cues.append("배역과의 거리가 생각보다 커 보입니다.")
    if risk >= 3:
        cues.append("기용 리스크가 마음 한구석에 걸립니다.")
    elif risk <= -2:
        cues.append("위험 부담은 비교적 관리 가능해 보입니다.")
    if team >= 3:
        cues.append("방 안의 공기가 협업 쪽으로 조금 따뜻해졌습니다.")
    elif team <= -2:
        cues.append("팀 안의 확신은 아직 모이지 않았습니다.")
    if global_reach >= 3:
        cues.append("상대는 해외 공개 가능성에 눈길을 주고 있습니다.")
    elif global_reach <= -2:
        cues.append("글로벌 확장성에 대해서는 아직 확신이 약해 보입니다.")
    if theatrical >= 3:
        cues.append("극장 창구를 지키는 방향으로 대화가 흘러갑니다.")
    elif theatrical <= -2:
        cues.append("플랫폼 중심 조건 때문에 극장 창구가 약해질 수 있어 보입니다.")
    if money >= 3:
        cues.append("계약 안정성과 선판매 조건은 조금 좋아지는 분위기입니다.")
    elif money <= -2:
        cues.append("계약 규모는 생각보다 작아질 조짐입니다.")
    if prestige >= 3:
        cues.append("프리미엄 브랜드와 작품의 결이 맞는다는 반응이 나옵니다.")
    elif prestige <= -2:
        cues.append("플랫폼 브랜드와의 궁합에는 의문이 남아 있습니다.")
    if reach >= 3:
        cues.append("관객 도달 범위를 넓히려는 의지는 살아 있습니다.")
    elif reach <= -2:
        cues.append("공개 범위가 기대만큼 넓어지지는 않을 듯합니다.")
    if domestic >= 3:
        cues.append("국내 가입자와 화제성을 움직일 수 있다는 판단이 보입니다.")
    elif domestic <= -2:
        cues.append("국내 플랫폼에서의 파급력은 아직 크게 보지 않는 눈치입니다.")
    if promo >= 3:
        cues.append("플랫폼 프로모션 지원 가능성이 살아납니다.")
    elif promo <= -2:
        cues.append("플랫폼이 크게 밀어주는 그림은 약해지는 분위기입니다.")
    if ip >= 3:
        cues.append("세계관과 IP 확장 가능성을 긍정적으로 보는 듯합니다.")
    elif ip <= -2:
        cues.append("IP로 오래 끌고 갈 힘에는 아직 물음표가 붙어 있습니다.")
    if brand >= 3:
        cues.append("브랜드 안정성에 대한 우려가 조금 누그러졌습니다.")
    elif brand <= -2:
        cues.append("브랜드 리스크를 걱정하는 기색이 남아 있습니다.")
    return cues


def _score(scores: dict[str, Any], key: str) -> float:
    value = scores.get(key, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
