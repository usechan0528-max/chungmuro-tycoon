from __future__ import annotations

import re
from typing import Any

from app.database import get_connection, loads_json


TOP_ORG_TYPES = {"theater_chain", "distributor"}


def list_major_industry_organizations(
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM organizations
            WHERE org_type IN ('theater_chain', 'distributor')
              AND (? IS NULL OR available_from IS NULL OR available_from <= ?)
            ORDER BY org_type, power DESC, name_ko
            """,
            (until_year, until_year),
        ).fetchall()
    theaters: list[dict[str, Any]] = []
    distributors: list[dict[str, Any]] = []
    for row in rows:
        org = _public_org(dict(row))
        if org["orgType"] == "theater_chain" and len(theaters) < 3:
            theaters.append(org)
        elif org["orgType"] == "distributor" and len(distributors) < 3:
            distributors.append(org)
    return {
        "theaterChains": theaters,
        "distributors": distributors,
        "currentDate": {"year": until_year, "month": until_month},
    }


def get_organization_profile(
    org_id: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not row:
        return {
            "id": org_id,
            "nameKo": org_id,
            "nameEn": "",
            "orgType": "unknown",
            "typeLabel": "미등록 조직",
            "oneLine": "아직 등록되지 않은 산업 주체입니다.",
            "historyText": "조직 데이터가 연결되면 관련 역사와 산업 효과가 표시됩니다.",
            "events": [],
        }
    org = _public_org(dict(row))
    profile = org["publicProfile"]
    events = _related_industry_events(
        org,
        until_year=until_year,
        until_month=until_month,
    )
    return {
        **org,
        "typeLabel": _type_label(org["orgType"]),
        "oneLine": profile.get("oneLine") or _default_one_line(org),
        "brandText": profile.get("brandText") or "",
        "historyText": profile.get("historyText") or _history_from_events(events),
        "businessText": profile.get("businessText") or "",
        "playerImpactText": profile.get("playerImpactText") or "",
        "influenceText": _influence_text(int(org.get("power") or 0)),
        "strategyText": _strategy_text(org),
        "events": events,
    }


def resolve_organization_id(name: Any) -> str | None:
    normalized = _normalize_name(name)
    if not normalized:
        return None
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name_ko, name_en, public_profile_json
            FROM organizations
            """
        ).fetchall()
    for row in rows:
        data = dict(row)
        candidates = [data.get("id"), data.get("name_ko"), data.get("name_en")]
        profile = loads_json(data.get("public_profile_json"), {})
        candidates.extend(profile.get("aliases") or [])
        normalized_candidates = {_normalize_name(candidate) for candidate in candidates if candidate}
        if normalized in normalized_candidates:
            return str(data["id"])
    for row in rows:
        data = dict(row)
        profile = loads_json(data.get("public_profile_json"), {})
        candidates = [data.get("id"), data.get("name_ko"), data.get("name_en"), *(profile.get("aliases") or [])]
        if any(normalized in _normalize_name(candidate) or _normalize_name(candidate) in normalized for candidate in candidates if candidate):
            return str(data["id"])
    return None


def organization_profile_text(profile: dict[str, Any]) -> str:
    lines = [
        profile.get("nameKo") or "",
        f"구분: {profile.get('typeLabel') or '-'}",
        f"활동 시작: {profile.get('availableFrom') or '기록 없음'}년",
        f"시장 영향력: {profile.get('influenceText') or '-'}",
        "",
        "한줄 평가",
        profile.get("oneLine") or "",
        "",
        "브랜드 평판",
        profile.get("brandText") or "아직 정리된 브랜드 평판이 부족합니다.",
        "",
        "역사",
        profile.get("historyText") or "관련 역사 기록이 아직 충분하지 않습니다.",
        "",
        "사업 성향",
        profile.get("businessText") or profile.get("strategyText") or "아직 뚜렷한 사업 성향 정보가 부족합니다.",
        "",
        "플레이어에게 의미",
        profile.get("playerImpactText") or "프로젝트 성격과 시대 상황에 따라 협상 가치가 달라집니다.",
        "",
        "게임 내 확인된 주요 사건",
    ]
    events = profile.get("events") or []
    if not events:
        lines.append("아직 게임 내 시간 기준으로 확인된 관련 사건이 없습니다.")
    else:
        for event in events:
            when = _event_when(event)
            lines.append(f"- {when} · {event.get('title')} · {event.get('description') or event.get('type') or ''}")
    return "\n".join(lines)


def _public_org(row: dict[str, Any]) -> dict[str, Any]:
    row["orgType"] = row.pop("org_type")
    row["nameKo"] = row.pop("name_ko")
    row["nameEn"] = row.pop("name_en")
    row["availableFrom"] = row.pop("available_from")
    row["publicProfile"] = loads_json(row.pop("public_profile_json"), {})
    row["strategy"] = loads_json(row.pop("strategy_json"), {})
    row["reputation"] = loads_json(row.pop("reputation_json"), {})
    return row


def _related_industry_events(
    org: dict[str, Any],
    *,
    until_year: int | None,
    until_month: int | None,
) -> list[dict[str, Any]]:
    aliases = _aliases_for(org)
    tables = [
        ("history_distribution_events", "배급"),
        ("history_theater_events", "극장"),
        ("history_premium_format_events", "특별관"),
    ]
    events: list[dict[str, Any]] = []
    with get_connection() as conn:
        for table, category in tables:
            clauses: list[str] = []
            params: list[int] = []
            if until_year is not None:
                month = int(until_month or 12)
                clauses.append("(year < ? OR (year = ? AND COALESCE(month, 12) <= ?))")
                params.extend([int(until_year), int(until_year), month])
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"""
                SELECT *
                FROM {table}
                {where}
                ORDER BY year, month, title
                """,
                params,
            ).fetchall()
            for row in rows:
                event = _event_from_row(dict(row), category)
                if _event_matches(event, aliases):
                    events.append(event)
    events.sort(key=lambda item: (int(item.get("year") or 0), int(item.get("month") or 12), str(item.get("title") or "")))
    return _dedupe_events(events)


def _event_from_row(row: dict[str, Any], category: str) -> dict[str, Any]:
    row["categoryLabel"] = category
    row["format"] = loads_json(row.pop("format_json", None), [])
    row["relatedCompanies"] = loads_json(row.pop("related_companies_json", None), [])
    row["effects"] = loads_json(row.pop("effects_json", None), {})
    row["unlocks"] = loads_json(row.pop("unlocks_json", None), [])
    return row


def _event_matches(event: dict[str, Any], aliases: set[str]) -> bool:
    candidates = [
        event.get("company"),
        event.get("chain"),
        *(event.get("relatedCompanies") or []),
    ]
    normalized_candidates = _normalized_event_candidates(candidates)
    if aliases & normalized_candidates:
        return True
    return False


def _normalized_event_candidates(candidates: list[Any]) -> set[str]:
    names: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        raw = str(candidate)
        parts = [raw, *re.split(r"[/,·&]| and ", raw, flags=re.IGNORECASE)]
        for part in parts:
            normalized = _normalize_name(part)
            if normalized:
                names.add(normalized)
    return names


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, int, str]] = set()
    deduped: list[dict[str, Any]] = []
    for event in events:
        key = (
            int(event.get("year") or 0),
            int(event.get("month") or 0),
            str(event.get("title") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def _aliases_for(org: dict[str, Any]) -> set[str]:
    profile = org.get("publicProfile") or {}
    values = [org.get("id"), org.get("nameKo"), org.get("nameEn"), *(profile.get("aliases") or [])]
    return {_normalize_name(value) for value in values if _normalize_name(value)}


def _history_from_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    first = events[0]
    latest = events[-1]
    return (
        f"{_event_when(first)}의 '{first.get('title')}' 사건을 시작으로 "
        f"{_event_when(latest)}의 '{latest.get('title')}'까지 게임 내 산업 변화에 영향을 주고 있습니다."
    )


def _strategy_text(org: dict[str, Any]) -> str:
    strategy = org.get("strategy") or {}
    parts: list[str] = []
    if strategy.get("preferredReleaseTypes"):
        parts.append("선호 개봉 방식: " + ", ".join(strategy["preferredReleaseTypes"]))
    if strategy.get("preferredScales"):
        parts.append("선호 규모: " + ", ".join(strategy["preferredScales"]))
    if strategy.get("preferredGenres"):
        parts.append("선호 장르: " + ", ".join(strategy["preferredGenres"]))
    return "\n".join(parts)


def _influence_text(power: int) -> str:
    if power >= 90:
        return "시대별 개봉 전략을 좌우할 정도의 핵심 영향력을 가진다."
    if power >= 80:
        return "메이저 개봉과 협상에서 강한 영향력을 가진다."
    if power >= 65:
        return "특정 장르와 개봉 규모에서 의미 있는 영향력을 가진다."
    return "제한적이지만 조건이 맞으면 협상 카드가 될 수 있다."


def _default_one_line(org: dict[str, Any]) -> str:
    if org["orgType"] == "theater_chain":
        return "한국 영화 상영 시장에 영향을 주는 극장 체인."
    if org["orgType"] == "distributor":
        return "한국 영화 투자·배급 시장에 영향을 주는 배급사."
    return "한국 영화산업에 등록된 조직."


def _type_label(org_type: str) -> str:
    return {
        "theater_chain": "극장 체인",
        "distributor": "배급사",
        "investor": "투자사",
        "ott": "OTT 플랫폼",
    }.get(org_type, org_type)


def _event_when(event: dict[str, Any]) -> str:
    year = event.get("year")
    month = event.get("month")
    if month:
        return f"{year}년 {month}월"
    return f"{year}년"


def _normalize_name(value: Any) -> str:
    return (
        str(value or "")
        .lower()
        .replace(" ", "")
        .replace("·", "")
        .replace("/", "")
        .replace("-", "")
        .strip()
    )
