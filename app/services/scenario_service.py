from __future__ import annotations

from typing import Any

from app.services.game_state import clamp


SCRIPT_STEP_LABELS = {
    "first_draft": "초고",
    "rewrite": "개고",
    "table_reading": "테이블 리딩",
    "investor_package": "투자사용 패키지",
    "adaptation_rights": "각색권 계약",
}

SCRIPT_STEP_STATUS_LABELS = {
    "planned": "예정",
    "in_progress": "진행 중",
    "optional": "검토",
    "completed": "완료",
}


def enrich_script_development_stats(
    stats: dict[str, Any],
    *,
    genre_id: str,
    scale_id: str,
    allocation: dict[str, int],
    franchise_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add hidden script-development dimensions to project stats.

    The UI must not display these values directly. They only drive event
    probabilities, qualitative diagnosis lines, and later formula tuning.
    """

    genre_id = _canonical_genre_id(genre_id)
    scenario = _num(stats.get("scenario_quality"), 50)
    directing = _num(stats.get("directing_quality"), 50)
    allocation_total = max(1, sum(max(0, int(value or 0)) for value in allocation.values()))
    scenario_share = max(0, int(allocation.get("scenario", 0) or 0)) / allocation_total * 100
    scale_pressure = _scale_pressure(scale_id)
    genre_complexity = _genre_complexity(genre_id)
    ip_bonus = 7 if franchise_context else 0

    structure = clamp(scenario + scenario_share * 0.35 - genre_complexity * 0.25 - scale_pressure * 0.15)
    dialogue = clamp(scenario + _dialogue_genre_modifier(genre_id) - scale_pressure * 0.1)
    character = clamp((scenario * 0.65) + (directing * 0.25) + _character_genre_modifier(genre_id) - genre_complexity * 0.15)
    pacing = clamp((scenario * 0.55) + (_num(stats.get("editing_quality"), 50) * 0.35) - scale_pressure * 0.18)
    originality = clamp(55 + _originality_genre_modifier(genre_id) - _num(stats.get("plagiarism_risk"), 0) * 0.45)
    investor_ready = clamp(
        _num(stats.get("pre_release_interest"), 35) * 0.35
        + structure * 0.25
        + _num(stats.get("genre_satisfaction"), 50) * 0.2
        + _num(stats.get("market_analysis"), 45) * 0.2
    )
    rights_clarity = clamp(72 + ip_bonus - _num(stats.get("plagiarism_risk"), 0) * 0.35 - genre_complexity * 0.12)

    stats.update(
        {
            "script_structure": int(structure),
            "script_dialogue": int(dialogue),
            "script_character_motivation": int(character),
            "script_pacing": int(pacing),
            "script_originality": int(originality),
            "investor_package_readiness": int(investor_ready),
            "adaptation_rights_clarity": int(rights_clarity),
            "script_structure_issue": int(100 - structure),
            "script_dialogue_weakness": int(100 - dialogue),
            "character_motivation_issue": int(100 - character),
            "script_pacing_issue": int(100 - pacing),
            "investor_package_risk": int(100 - investor_ready),
            "adaptation_rights_risk": int(100 - rights_clarity),
        }
    )
    stats["scenario_public_diagnosis"] = build_script_public_snapshot(stats, genre_id=genre_id)
    return stats


def scenario_development_plan(
    *,
    stats: dict[str, Any],
    genre_id: str,
    scale_id: str,
    franchise_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    genre_id = _canonical_genre_id(genre_id)
    snapshot = build_script_public_snapshot(stats, genre_id=genre_id)
    original_or_ip = bool(franchise_context) or scale_id == "scale_tentpole" or genre_id in {"fantasy", "animation", "sf_disaster_monster", "social_true_story"}
    return [
        {
            "stepId": "first_draft",
            "stepName": SCRIPT_STEP_LABELS["first_draft"],
            "sequence": 10,
            "stageCandidates": ["planning", "development", "ip_development", "funding_simple"],
            "durationDays": _duration_for_step("first_draft", scale_id),
            "status": "in_progress",
            "diagnosis": snapshot["structure"],
            "riskNote": snapshot["primaryWeakness"],
            "suggestedAction": "로그라인, 3막 구조, 주인공의 결핍을 먼저 고정한다.",
            "metrics": _metrics(stats),
        },
        {
            "stepId": "rewrite",
            "stepName": SCRIPT_STEP_LABELS["rewrite"],
            "sequence": 20,
            "stageCandidates": ["screenplay_development", "planning", "development"],
            "durationDays": _duration_for_step("rewrite", scale_id),
            "status": "planned",
            "diagnosis": snapshot["rewrite"],
            "riskNote": snapshot["secondaryWeakness"],
            "suggestedAction": "장면의 기능을 점검하고 인물 선택의 이유를 한 번 더 다진다.",
            "metrics": _metrics(stats),
        },
        {
            "stepId": "table_reading",
            "stepName": SCRIPT_STEP_LABELS["table_reading"],
            "sequence": 30,
            "stageCandidates": ["casting", "casting_simple", "star_casting", "pre_production"],
            "durationDays": _duration_for_step("table_reading", scale_id),
            "status": "planned",
            "diagnosis": snapshot["dialogue"],
            "riskNote": snapshot["character"],
            "suggestedAction": "배우의 입으로 들었을 때 어색한 대사와 감정 전환을 확인한다.",
            "metrics": _metrics(stats),
        },
        {
            "stepId": "investor_package",
            "stepName": SCRIPT_STEP_LABELS["investor_package"],
            "sequence": 40,
            "stageCandidates": ["fundraising", "large_fundraising", "small_investment", "distribution_predeal"],
            "durationDays": _duration_for_step("investor_package", scale_id),
            "status": "planned",
            "diagnosis": snapshot["investor"],
            "riskNote": snapshot["packageRisk"],
            "suggestedAction": "로그라인, 타깃 관객, 비교작, 제작비 회수 구조를 한 문서로 묶는다.",
            "metrics": _metrics(stats),
        },
        {
            "stepId": "adaptation_rights",
            "stepName": SCRIPT_STEP_LABELS["adaptation_rights"],
            "sequence": 50,
            "stageCandidates": ["ip_development", "planning", "screenplay_development"],
            "durationDays": _duration_for_step("adaptation_rights", scale_id),
            "status": "planned" if original_or_ip else "optional",
            "diagnosis": snapshot["rights"],
            "riskNote": snapshot["rightsRisk"],
            "suggestedAction": "원작, 기사, 실화, 캐릭터 설정의 권리 관계를 제작 착수 전에 정리한다.",
            "metrics": _metrics(stats),
        },
    ]


def build_script_public_snapshot(stats: dict[str, Any], *, genre_id: str = "") -> dict[str, str]:
    genre_id = _canonical_genre_id(genre_id)
    structure = _num(stats.get("script_structure", stats.get("scenario_quality", 50)), 50)
    dialogue = _num(stats.get("script_dialogue", stats.get("scenario_quality", 50)), 50)
    character = _num(stats.get("script_character_motivation", stats.get("scenario_quality", 50)), 50)
    pacing = _num(stats.get("script_pacing", stats.get("editing_quality", 50)), 50)
    originality = _num(stats.get("script_originality", 55), 55)
    investor_ready = _num(stats.get("investor_package_readiness", 50), 50)
    rights = _num(stats.get("adaptation_rights_clarity", 65), 65)

    return {
        "oneLine": _combined_line(structure, dialogue, character, pacing, originality),
        "structure": _structure_text(structure, pacing),
        "rewrite": _rewrite_text(structure, character, originality),
        "dialogue": _dialogue_text(dialogue, character, genre_id),
        "character": _character_text(character),
        "investor": _investor_text(investor_ready),
        "rights": _rights_text(rights),
        "primaryWeakness": _primary_weakness(structure, dialogue, character, pacing, originality),
        "secondaryWeakness": _secondary_weakness(structure, dialogue, character, pacing, originality),
        "packageRisk": _package_risk_text(investor_ready),
        "rightsRisk": _rights_risk_text(rights),
    }


def status_label(status: str | None) -> str:
    return SCRIPT_STEP_STATUS_LABELS.get(str(status or "planned"), str(status or "예정"))


def _metrics(stats: dict[str, Any]) -> dict[str, int]:
    return {
        "structure": int(_num(stats.get("script_structure"), 50)),
        "dialogue": int(_num(stats.get("script_dialogue"), 50)),
        "characterMotivation": int(_num(stats.get("script_character_motivation"), 50)),
        "pacing": int(_num(stats.get("script_pacing"), 50)),
        "originality": int(_num(stats.get("script_originality"), 50)),
        "investorPackage": int(_num(stats.get("investor_package_readiness"), 50)),
        "rightsClarity": int(_num(stats.get("adaptation_rights_clarity"), 50)),
    }


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _canonical_genre_id(genre_id: str) -> str:
    aliases = {
        "genre_crime_thriller": "crime_thriller",
        "genre_action": "action",
        "genre_horror_occult": "horror_occult",
        "genre_romance_melodrama": "romance_melodrama",
        "genre_comedy": "comedy",
        "genre_family_human_drama": "family_human_drama",
        "genre_period_historical": "historical_period",
        "genre_historical_period": "historical_period",
        "genre_social_true_story": "social_true_story",
        "genre_indie_art": "indie_art",
        "genre_sf_disaster_monster": "sf_disaster_monster",
        "genre_fantasy": "fantasy",
        "genre_animation": "animation",
    }
    return aliases.get(genre_id, genre_id.removeprefix("genre_"))


def _scale_pressure(scale_id: str) -> int:
    return {
        "scale_short": 8,
        "scale_independent": 18,
        "scale_low_budget_genre": 26,
        "scale_mid_commercial": 34,
        "scale_large_commercial": 46,
        "scale_tentpole": 58,
    }.get(scale_id, 28)


def _genre_complexity(genre_id: str) -> int:
    return {
        "crime_thriller": 32,
        "social_true_story": 42,
        "historical_period": 40,
        "sf_disaster_monster": 45,
        "fantasy": 48,
        "animation": 36,
        "indie_art": 38,
        "horror_occult": 30,
        "comedy": 28,
        "action": 25,
        "romance_melodrama": 26,
        "family_human_drama": 30,
    }.get(genre_id, 30)


def _dialogue_genre_modifier(genre_id: str) -> int:
    return {
        "romance_melodrama": 8,
        "comedy": 9,
        "family_human_drama": 6,
        "indie_art": 5,
        "social_true_story": 3,
        "action": -4,
        "sf_disaster_monster": -3,
        "fantasy": -2,
    }.get(genre_id, 0)


def _character_genre_modifier(genre_id: str) -> int:
    return {
        "romance_melodrama": 8,
        "family_human_drama": 8,
        "social_true_story": 6,
        "indie_art": 5,
        "crime_thriller": 3,
        "action": -2,
        "sf_disaster_monster": -2,
    }.get(genre_id, 0)


def _originality_genre_modifier(genre_id: str) -> int:
    return {
        "horror_occult": 6,
        "indie_art": 8,
        "sf_disaster_monster": 4,
        "fantasy": 4,
        "crime_thriller": -2,
        "romance_melodrama": -4,
        "action": -3,
        "comedy": -2,
    }.get(genre_id, 0)


def _duration_for_step(step_id: str, scale_id: str) -> int:
    base = {
        "first_draft": 14,
        "rewrite": 21,
        "table_reading": 3,
        "investor_package": 5,
        "adaptation_rights": 7,
    }.get(step_id, 7)
    multiplier = {
        "scale_short": 0.5,
        "scale_independent": 0.8,
        "scale_low_budget_genre": 1.0,
        "scale_mid_commercial": 1.25,
        "scale_large_commercial": 1.55,
        "scale_tentpole": 2.2,
    }.get(scale_id, 1.0)
    return max(1, int(round(base * multiplier)))


def _combined_line(structure: float, dialogue: float, character: float, pacing: float, originality: float) -> str:
    if structure >= 68 and dialogue < 56:
        return "구조는 비교적 탄탄하지만 대사가 아직 기능적으로 느껴진다."
    if character < 55:
        return "장면의 방향은 보이지만 캐릭터가 왜 움직이는지가 흐릿하다."
    if pacing < 55:
        return "좋은 장면은 있으나 중반 리듬이 늘어질 가능성이 있다."
    if originality < 50:
        return "장르 관습을 잘 따르지만 익숙한 설정의 그림자가 남아 있다."
    if min(structure, dialogue, character, pacing) >= 70:
        return "뼈대, 대사, 인물 동기가 고르게 맞물리는 편이다."
    return "좋은 씨앗은 있지만 어느 축을 먼저 고칠지 결정해야 한다."


def _structure_text(structure: float, pacing: float) -> str:
    if structure >= 75 and pacing >= 65:
        return "사건 배치와 상승 곡선이 선명해 초고의 뼈대가 안정적으로 보인다."
    if structure >= 65:
        return "큰 구조는 잡혔지만 중반부의 연결과 장면 전환을 더 다듬어야 한다."
    if structure >= 50:
        return "시작점은 매력적이나 2막의 목표와 장애물이 아직 흐릿하다."
    return "장편으로 버티기에는 사건의 인과와 중심 갈등이 충분히 서지 않았다."


def _rewrite_text(structure: float, character: float, originality: float) -> str:
    if min(structure, character, originality) >= 70:
        return "개고에서는 큰 수술보다 장면별 밀도와 반복되는 정보를 줄이는 쪽이 좋아 보인다."
    if character < 55:
        return "개고의 핵심은 캐릭터의 선택 이유를 장면마다 더 또렷하게 심는 것이다."
    if originality < 52:
        return "개고 단계에서 익숙한 설정을 비틀 구체적인 장면이 필요하다."
    return "개고로 구조와 감정선을 정리하면 제작 패키지로 넘어갈 수 있다."


def _dialogue_text(dialogue: float, character: float, genre_id: str) -> str:
    if dialogue >= 75 and character >= 65:
        return "테이블 리딩에서 대사가 배우 입에 잘 붙을 가능성이 높다."
    if dialogue < 52:
        return "대사가 정보를 전달하는 쪽에 치우쳐 배우가 살릴 여지가 아직 좁다."
    if character < 55:
        return "대사는 나쁘지 않지만 인물이 그 말을 해야 하는 이유가 약하게 들릴 수 있다."
    if genre_id == "comedy":
        return "코미디 타이밍은 보이지만 리딩에서 박자와 말맛을 다시 확인해야 한다."
    return "대사와 감정선은 무난하지만 배우 리딩을 거치며 살아나는지 봐야 한다."


def _character_text(character: float) -> str:
    if character >= 75:
        return "주요 인물의 욕망과 결핍이 장면 선택으로 이어지는 편이다."
    if character >= 60:
        return "캐릭터의 방향은 보이지만 몇몇 결정의 이유가 더 필요하다."
    return "캐릭터 동기가 흐려 장면이 기능적으로만 흘러갈 위험이 있다."


def _investor_text(investor_ready: float) -> str:
    if investor_ready >= 75:
        return "투자자에게 설명할 로그라인, 타깃 관객, 회수 구조가 꽤 선명하다."
    if investor_ready >= 60:
        return "패키지의 방향은 보이나 비교작과 손익 구조 설명을 더 보강해야 한다."
    return "투자사용 문서로는 아직 장점보다 불확실성이 먼저 보일 수 있다."


def _rights_text(rights: float) -> str:
    if rights >= 75:
        return "원작·실화·레퍼런스 권리 관계가 비교적 깨끗하게 정리된 편이다."
    if rights >= 60:
        return "큰 문제는 없어 보이나 원작권, 기사 인용, 실제 인물 동의는 확인이 필요하다."
    return "각색권과 유사성 검토를 미루면 제작 후반에 더 큰 비용으로 돌아올 수 있다."


def _primary_weakness(structure: float, dialogue: float, character: float, pacing: float, originality: float) -> str:
    values = {
        "structure": structure,
        "dialogue": dialogue,
        "character": character,
        "pacing": pacing,
        "originality": originality,
    }
    weakest = min(values, key=values.get)
    return {
        "structure": "구조의 약점이 먼저 보인다. 사건의 원인과 결과를 더 단단히 묶어야 한다.",
        "dialogue": "대사가 설명적으로 들릴 위험이 있다. 말맛과 침묵의 자리를 찾아야 한다.",
        "character": "캐릭터 동기가 약하다. 선택의 이유가 장면 안에 보여야 한다.",
        "pacing": "중반 리듬이 늘어질 수 있다. 장면의 기능을 냉정하게 덜어낼 필요가 있다.",
        "originality": "기존 작품과 닮아 보이는 지점이 있다. 한 장면이라도 자기만의 해법이 필요하다.",
    }[weakest]


def _secondary_weakness(structure: float, dialogue: float, character: float, pacing: float, originality: float) -> str:
    ordered = sorted(
        {
            "structure": structure,
            "dialogue": dialogue,
            "character": character,
            "pacing": pacing,
            "originality": originality,
        }.items(),
        key=lambda item: item[1],
    )
    if len(ordered) < 2:
        return _primary_weakness(structure, dialogue, character, pacing, originality)
    second = ordered[1][0]
    return {
        "structure": "개고 때 구조 보강을 놓치면 후반부에서 다시 흔들릴 수 있다.",
        "dialogue": "테이블 리딩 전까지 대사의 숨 쉴 자리를 더 만들어야 한다.",
        "character": "감정선은 보이지만 인물의 욕망을 더 일찍 보여줄 필요가 있다.",
        "pacing": "삭제할 장면과 압축할 장면을 구분해야 한다.",
        "originality": "장르 관습을 빌리되 한두 개의 낯선 선택이 필요하다.",
    }[second]


def _package_risk_text(investor_ready: float) -> str:
    if investor_ready >= 70:
        return "투자 미팅에서 작품의 핵심 경쟁력을 짧게 설명할 수 있다."
    if investor_ready >= 55:
        return "투자자는 흥미를 보일 수 있지만 회수 구조 질문이 길어질 가능성이 높다."
    return "패키지 없이 미팅에 들어가면 작품성보다 위험이 먼저 보일 수 있다."


def _rights_risk_text(rights: float) -> str:
    if rights >= 70:
        return "권리 리스크는 낮아 보이지만 계약서 확인은 별도로 필요하다."
    if rights >= 55:
        return "권리 관계는 회색지대가 있다. 법무 검토와 원작자 확인이 안전하다."
    return "각색권을 정리하지 않으면 표절·권리 논란이 제작 후반에 터질 수 있다."
