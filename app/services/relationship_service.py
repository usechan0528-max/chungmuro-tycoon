from __future__ import annotations

from typing import Any


RELATIONSHIP_STAGE_ORDER = [
    "enemy",
    "strained",
    "unknown",
    "awkward",
    "acquaintance",
    "close",
    "partner",
]

RELATIONSHIP_STAGES: dict[str, dict[str, str]] = {
    "enemy": {
        "label": "원수 지간",
        "description": "서로의 이름이 협업 리스크로 언급될 만큼 관계가 크게 틀어져 있다.",
    },
    "strained": {
        "label": "껄끄러운 사이",
        "description": "같은 자리에 앉을 수는 있지만, 조건 조율과 현장 신뢰에 마찰이 생기기 쉽다.",
    },
    "unknown": {
        "label": "모르는 사이",
        "description": "아직 이름과 평판 이상으로 확인된 접점이 없다.",
    },
    "awkward": {
        "label": "어색한 사이",
        "description": "안면은 있지만 서로의 방식과 온도를 아직 잘 모른다.",
    },
    "acquaintance": {
        "label": "아는 사이",
        "description": "연락이 닿고 가벼운 제안이나 미팅은 현실적으로 시도할 수 있다.",
    },
    "close": {
        "label": "친한 사이",
        "description": "작품 이야기와 조건 조율을 비교적 편하게 나눌 수 있는 관계다.",
    },
    "partner": {
        "label": "파트너",
        "description": "서로의 작업 방식과 리듬을 이해하는 장기 협업 후보로 평가된다.",
    },
    "persona": {
        "label": "페르소나",
        "description": "감독과 배우가 서로의 영화적 언어를 공유하는 핵심 조합으로 평가된다.",
    },
}


def relationship_snapshot(
    trust: int | float | None,
    awareness: int | float | None,
    *,
    persona_candidate: bool = False,
) -> dict[str, Any]:
    trust_value = _clamp_int(trust, -100, 100)
    awareness_value = _clamp_int(awareness, 0, 100)
    stage_id = relationship_stage_id(
        trust_value,
        awareness_value,
        persona_candidate=persona_candidate,
    )
    stage = RELATIONSHIP_STAGES[stage_id]
    return {
        "trust": trust_value,
        "awareness": awareness_value,
        "stage_id": stage_id,
        "label": stage["label"],
        "description": stage["description"],
    }


def relationship_stage_id(
    trust: int,
    awareness: int,
    *,
    persona_candidate: bool = False,
) -> str:
    if trust <= -61:
        return "enemy"
    if trust <= -21:
        return "strained"
    if trust >= 75:
        return "persona" if persona_candidate else "partner"
    if trust >= 45:
        return "close"
    if trust >= 20:
        return "acquaintance"
    if awareness <= 0:
        return "unknown"
    return "awkward"


def get_relationship_snapshot(
    conn: Any,
    target_id: str,
    target_type: str | None,
    *,
    persona_candidate: bool = False,
) -> dict[str, Any]:
    row = _find_relationship_row(conn, target_id, target_type)
    if not row:
        return relationship_snapshot(0, 0, persona_candidate=persona_candidate)
    return relationship_snapshot(
        row["trust"],
        row["awareness"],
        persona_candidate=persona_candidate,
    )


def adjust_relationship(
    conn: Any,
    target_id: str,
    target_type: str | None,
    *,
    trust_delta: int = 0,
    awareness_delta: int = 0,
    last_contact_year: int | None = None,
    persona_candidate: bool = False,
) -> dict[str, Any]:
    normalized_type = target_type or "person"
    row = _find_player_relationship_row(conn, target_id, normalized_type)
    base_row = row or _find_relationship_row(conn, target_id, normalized_type)
    if row:
        new_trust = _clamp_int(int(row["trust"] or 0) + trust_delta, -100, 100)
        new_awareness = _clamp_int(int(row["awareness"] or 0) + awareness_delta, 0, 100)
        conn.execute(
            """
            UPDATE relationships
            SET trust = ?, awareness = ?, last_contact_year = COALESCE(?, last_contact_year)
            WHERE id = ?
            """,
            (new_trust, new_awareness, last_contact_year, row["id"]),
        )
    else:
        base_trust = int(base_row["trust"] or 0) if base_row else 0
        base_awareness = int(base_row["awareness"] or 0) if base_row else 0
        new_trust = _clamp_int(base_trust + trust_delta, -100, 100)
        new_awareness = _clamp_int(base_awareness + awareness_delta, 0, 100)
        conn.execute(
            """
            INSERT INTO relationships (
                target_id, target_type, trust, awareness, last_contact_year
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (target_id, normalized_type, new_trust, new_awareness, last_contact_year),
        )
    return relationship_snapshot(new_trust, new_awareness, persona_candidate=persona_candidate)


def relationship_delta_sentence(before: dict[str, Any], after: dict[str, Any]) -> str:
    if before.get("stage_id") == after.get("stage_id"):
        return f"관계는 여전히 {after['label']}에 가깝다."
    return f"관계가 {before['label']}에서 {after['label']}로 바뀌었다."


def _find_relationship_row(conn: Any, target_id: str, target_type: str | None) -> Any:
    normalized_type = target_type or "person"
    row = conn.execute(
        """
        SELECT id, target_id, target_type, trust, awareness, last_contact_year
        FROM relationships
        WHERE target_id = ? AND target_type = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (target_id, normalized_type),
    ).fetchone()
    if row:
        return row
    return conn.execute(
        """
        SELECT id, target_id, target_type, trust, awareness, last_contact_year
        FROM people_relationships
        WHERE target_id = ? AND target_type = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (target_id, normalized_type),
    ).fetchone()


def _find_player_relationship_row(conn: Any, target_id: str, target_type: str | None) -> Any:
    normalized_type = target_type or "person"
    return conn.execute(
        """
        SELECT id, target_id, target_type, trust, awareness, last_contact_year
        FROM relationships
        WHERE target_id = ? AND target_type = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (target_id, normalized_type),
    ).fetchone()


def _clamp_int(value: int | float | None, minimum: int, maximum: int) -> int:
    try:
        numeric = int(round(float(value if value is not None else 0)))
    except (TypeError, ValueError):
        numeric = 0
    return max(minimum, min(maximum, numeric))
