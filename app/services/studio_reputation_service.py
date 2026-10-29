from __future__ import annotations

from typing import Any

from app.database import dumps_json, loads_json


DEFAULT_STUDIO_REPUTATION = {
    "field_reputation": 50,
    "pay_reputation": 50,
    "creative_freedom": 50,
    "interference_reputation": 50,
}


def clamp_reputation(value: Any, minimum: int = 0, maximum: int = 100) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = 50
    return max(minimum, min(maximum, numeric))


def describe_studio_reputation(
    studio: dict[str, Any] | None,
    player_reputation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not studio:
        return _profile(
            primary="아직 평판이 굳지 않은 신생 회사",
            secondary="업계가 지켜보는 단계",
            summary="아직 반복된 현장 기록이 없어 사람들은 첫 작품과 첫 계약을 보고 판단하려 합니다.",
            signals=["평판을 만들 여지가 크다."],
        )

    field = _studio_value(studio, "field_reputation")
    pay = _studio_value(studio, "pay_reputation")
    freedom = _studio_value(studio, "creative_freedom")
    interference = _studio_value(studio, "interference_reputation")
    fame = clamp_reputation(studio.get("fame", 0), 0, 100)
    tags = loads_json(studio.get("reputation_tags_json"), [])
    player_reputation = player_reputation or {}
    creative_rep = clamp_reputation(player_reputation.get("creative_reputation", 10), 0, 100)
    investor_rep = clamp_reputation(player_reputation.get("investor_reputation", 10), 0, 100)

    primary = _primary_label(field, pay, freedom, interference, fame)
    secondary = _secondary_label(field, pay, freedom, interference, creative_rep, investor_rep)
    summary = " ".join(
        [
            _field_sentence(field),
            _pay_sentence(pay),
            _creative_sentence(freedom, interference),
        ]
    )
    signals = _signals(field, pay, freedom, interference, fame, tags)
    return _profile(
        primary=primary,
        secondary=secondary,
        summary=summary,
        signals=signals,
        values={
            "fieldReputation": field,
            "payReputation": pay,
            "creativeFreedom": freedom,
            "interferenceReputation": interference,
        },
    )


def apply_studio_reputation_delta(conn: Any, deltas: dict[str, Any]) -> None:
    row = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not row:
        return
    data = dict(row)
    updated = {
        key: clamp_reputation(_studio_value(data, key) + int(deltas.get(key, 0) or 0))
        for key in DEFAULT_STUDIO_REPUTATION
    }
    tags = loads_json(data.get("reputation_tags_json"), [])
    new_tags = deltas.get("reputation_tags") or deltas.get("studio_reputation_tags") or []
    if isinstance(new_tags, str):
        new_tags = [new_tags]
    if isinstance(new_tags, list):
        for tag in new_tags:
            if tag and tag not in tags:
                tags.append(str(tag))
    preview = dict(data)
    preview.update(updated)
    summary = describe_studio_reputation(preview).get("summary", "")
    conn.execute(
        """
        UPDATE studio_state
        SET field_reputation = ?, pay_reputation = ?, creative_freedom = ?,
            interference_reputation = ?, reputation_tags_json = ?, reputation_summary = ?
        WHERE id = 1
        """,
        (
            updated["field_reputation"],
            updated["pay_reputation"],
            updated["creative_freedom"],
            updated["interference_reputation"],
            dumps_json(tags),
            summary,
        ),
    )


def _studio_value(studio: dict[str, Any], key: str) -> int:
    fallback = DEFAULT_STUDIO_REPUTATION[key]
    return clamp_reputation(studio.get(key, fallback), 0, 100)


def _primary_label(field: int, pay: int, freedom: int, interference: int, fame: int) -> str:
    if fame <= 12 and 42 <= field <= 58 and 42 <= pay <= 58 and 42 <= freedom <= 58:
        return "아직 평판이 굳지 않은 신생 회사"
    if pay >= 72 and interference >= 66:
        return "돈은 잘 주지만 창작 간섭이 심한 회사"
    if field >= 72 and freedom >= 62 and interference <= 45:
        return "현장이 좋은 회사"
    if pay >= 72 and field >= 58:
        return "정산과 약속이 깔끔한 회사"
    if freedom >= 72 and interference <= 48:
        return "창작자에게 맡기는 회사"
    if interference >= 76:
        return "창작 간섭이 심한 회사"
    if field <= 34:
        return "현장 운영이 거친 회사"
    if pay <= 34:
        return "정산이 불안한 회사"
    if field >= 65 and pay >= 65:
        return "기본기가 탄탄한 제작사"
    return "색깔을 만들어가는 제작사"


def _secondary_label(
    field: int,
    pay: int,
    freedom: int,
    interference: int,
    creative_rep: int,
    investor_rep: int,
) -> str:
    if investor_rep >= 60 and creative_rep <= 35:
        return "투자자는 믿지만 창작자는 경계하는 편"
    if field >= 70 and pay >= 70:
        return "스태프가 다시 일하고 싶어 하는 편"
    if freedom >= 70 and interference <= 45:
        return "감독에게 재량을 주는 편"
    if pay >= 70 and field <= 45:
        return "돈은 빠르지만 현장은 빡빡한 편"
    if interference >= 70:
        return "회의실의 목소리가 큰 편"
    if field <= 40:
        return "현장 피로도가 먼저 언급되는 편"
    return "아직 업계 별칭은 유동적"


def _field_sentence(value: int) -> str:
    if value >= 75:
        return "촬영장은 준비가 잘 되어 있고, 스태프 사이에서 일하기 편한 곳이라는 말이 돈다."
    if value >= 60:
        return "현장 운영은 대체로 안정적이라는 평가가 많다."
    if value >= 40:
        return "현장 운영은 무난하지만 작품마다 편차가 있다는 인식이 있다."
    return "현장 운영이 거칠고 피로도가 높다는 말이 조금씩 쌓이고 있다."


def _pay_sentence(value: int) -> str:
    if value >= 75:
        return "계약금과 정산 약속을 잘 지키는 회사로 받아들여진다."
    if value >= 60:
        return "돈 문제에서는 비교적 예측 가능한 회사로 보인다."
    if value >= 40:
        return "정산 신뢰는 아직 보통 수준이라 조건을 꼼꼼히 보는 사람이 많다."
    return "출연료와 스태프 비용 지급을 두고 조심스러운 시선이 생기고 있다."


def _creative_sentence(freedom: int, interference: int) -> str:
    if freedom >= 70 and interference <= 45:
        return "창작진에게 재량을 주는 편이라 감독과 배우가 제안을 꺼내기 쉽다."
    if interference >= 72:
        return "다만 중요한 순간마다 제작사의 개입이 강하다는 인상이 남아 있다."
    if freedom <= 38:
        return "창작진은 이 회사와 일할 때 결정권의 범위를 먼저 확인하려 한다."
    return "창작 자유와 제작 관리 사이에서 아직 뚜렷한 색깔을 잡아가는 중이다."


def _signals(
    field: int,
    pay: int,
    freedom: int,
    interference: int,
    fame: int,
    tags: list[Any],
) -> list[str]:
    signals: list[str] = []
    if field >= 70:
        signals.append("현장 스태프 재협업 가능성이 높아 보인다.")
    if pay >= 70:
        signals.append("계약 조건을 신뢰하는 배우와 스태프가 늘어난다.")
    if freedom >= 70:
        signals.append("작가주의 감독이나 신인 감독에게 매력적인 제안이 될 수 있다.")
    if interference >= 70:
        signals.append("창작진은 계약 전 최종 편집권과 수정 권한을 확인하려 한다.")
    if field <= 35:
        signals.append("현장 갈등 이벤트의 여지가 커진다.")
    if pay <= 35:
        signals.append("일부 배우와 스태프가 선지급 조건을 요구할 수 있다.")
    if fame >= 70:
        signals.append("평판 하나하나가 기사와 투자 심리에 더 크게 반영된다.")
    for tag in tags[:3]:
        signals.append(str(tag))
    if not signals:
        signals.append("아직은 다음 작품의 선택이 회사 이미지를 크게 바꿀 수 있다.")
    return signals[:5]


def _profile(
    *,
    primary: str,
    secondary: str,
    summary: str,
    signals: list[str],
    values: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "primaryLabel": primary,
        "secondaryLabel": secondary,
        "summary": summary,
        "signals": signals,
        "values": values or dict(DEFAULT_STUDIO_REPUTATION),
    }
