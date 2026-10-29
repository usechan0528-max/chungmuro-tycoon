from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp
from app.services.organization_service import resolve_organization_id


LOW_SCOPE_SCALES = {"short", "short_film", "independent", "independent_film", "low_budget_genre"}
COMMERCIAL_SCALES = {"mid_commercial", "large_commercial", "tentpole_blockbuster"}


def ensure_project_distributor_match(
    project_id: str,
    *,
    conn: Any | None = None,
    project: dict[str, Any] | None = None,
    player: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if conn is None:
        with get_connection() as own_conn:
            state = _ensure_project_distributor_match(
                own_conn,
                project_id,
                project=project,
                player=player,
                stats=stats,
            )
            own_conn.commit()
            return state
    return _ensure_project_distributor_match(conn, project_id, project=project, player=player, stats=stats)


def get_project_distribution_state(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        return _project_distribution_state(conn, project_id)


def resolve_distribution_company_id(name: Any) -> str | None:
    return resolve_organization_id(name)


def _ensure_project_distributor_match(
    conn: Any,
    project_id: str,
    *,
    project: dict[str, Any] | None,
    player: dict[str, Any] | None,
    stats: dict[str, Any] | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT pd.*, o.name_ko
        FROM project_distribution pd
        LEFT JOIN organizations o ON o.id = pd.distributor_id
        WHERE pd.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row and row["distributor_id"]:
        return _distribution_state_from_row(dict(row))

    project_data = project or _load_project_context(conn, project_id)
    if not project_data:
        raise ValueError("배급사를 매칭할 프로젝트를 찾을 수 없습니다.")
    player_data = player or conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
    current_year = int(
        (player_data["current_year"] if player_data else None)
        or project_data.get("created_year")
        or 1980
    )
    project_stats = stats if stats is not None else loads_json(project_data.get("stats_json"), {})
    genre = _load_genre(conn, str(project_data["genre_id"]))
    scale = _load_scale(conn, str(project_data["scale_id"]))
    candidates = _available_distributor_candidates(
        conn,
        current_year=current_year,
        project=project_data,
        genre=genre,
        scale=scale,
        player=player_data,
    )
    if not candidates:
        state = {
            "status": "unmatched",
            "label": "배급사 미정",
            "summary": "현재 게임 내 시간 기준으로 협상 가능한 배급사가 아직 충분히 등장하지 않았습니다.",
            "distributorId": None,
            "distributorName": None,
        }
        _write_project_distribution(conn, project_id, state, project_stats)
        return state

    best = max(candidates, key=lambda item: (item["score"], item["screenPower"], item["nameKo"]))
    deal_type = _deal_type_for(best, scale)
    summary = _match_summary(best, genre, scale)
    terms = {
        "status": "matched_auto",
        "matchScore": best["score"],
        "matchReasons": best["reasons"],
        "matchedAtYear": current_year,
        "dealType": deal_type,
        "summary": summary,
        "riskText": _risk_text(best, scale),
        "preferredScales": best["strategy"].get("preferredScales") or [],
        "preferredGenres": best["strategy"].get("preferredGenres") or [],
    }
    state = {
        "status": "matched",
        "label": f"{best['nameKo']} · {deal_type}",
        "summary": summary,
        "distributorId": best["id"],
        "distributorName": best["nameKo"],
        "dealType": deal_type,
        "marketingCommitment": best["marketingCommitment"],
        "screenPower": best["screenPower"],
        "terms": terms,
    }
    _write_project_distribution(conn, project_id, state, project_stats)
    return state


def _load_project_context(conn: Any, project_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.*, g.name AS genre_name, s.name AS scale_name
        FROM projects p
        JOIN genres g ON g.id = p.genre_id
        JOIN project_scales s ON s.id = p.scale_id
        WHERE p.id = ?
        """,
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def _load_genre(conn: Any, genre_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone()
    return dict(row) if row else {"id": genre_id, "name": genre_id}


def _load_scale(conn: Any, scale_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM project_scales WHERE id = ?", (scale_id,)).fetchone()
    return dict(row) if row else {"id": scale_id, "name": scale_id}


def _available_distributor_candidates(
    conn: Any,
    *,
    current_year: int,
    project: dict[str, Any],
    genre: dict[str, Any],
    scale: dict[str, Any],
    player: Any,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM organizations
        WHERE org_type = 'distributor'
          AND (available_from IS NULL OR available_from <= ?)
        """,
        (current_year,),
    ).fetchall()
    return [
        _score_distributor(dict(row), project=project, genre=genre, scale=scale, player=player)
        for row in rows
    ]


def _score_distributor(
    row: dict[str, Any],
    *,
    project: dict[str, Any],
    genre: dict[str, Any],
    scale: dict[str, Any],
    player: Any,
) -> dict[str, Any]:
    strategy = loads_json(row.get("strategy_json"), {})
    reputation = loads_json(row.get("reputation_json"), {})
    profile = loads_json(row.get("public_profile_json"), {})
    power = int(row.get("power") or 50)
    screen_power = int(strategy.get("screenPower") or reputation.get("distribution_network") or power)
    marketing_power = int(strategy.get("marketingPower") or power * 0.75)
    scale_id = _canonical_value(project.get("scale_id") or scale.get("id"))
    genre_id = _canonical_value(project.get("genre_id") or genre.get("id"))
    preferred_scales = {_canonical_value(value) for value in strategy.get("preferredScales", [])}
    preferred_genres = {_canonical_value(value) for value in strategy.get("preferredGenres", [])}

    score = power * 0.45 + screen_power * 0.25 + marketing_power * 0.15
    reasons: list[str] = []
    if scale_id in preferred_scales:
        score += 22
        reasons.append("제작 규모 선호가 맞음")
    elif scale_id in LOW_SCOPE_SCALES:
        if power <= 72:
            score += 20
            reasons.append("저예산·신인 프로젝트 대응력이 좋음")
        elif power >= 85:
            score -= 18
            reasons.append("메이저 배급사라 작은 프로젝트에는 보수적")
    elif scale_id in COMMERCIAL_SCALES:
        if power >= 82:
            score += 12
            reasons.append("상업영화 개봉망이 강함")
        else:
            score -= 8
            reasons.append("대형 개봉망은 제한적")

    if genre_id in preferred_genres:
        score += 18
        reasons.append("장르 선호가 맞음")
    elif not preferred_genres and genre_id in {"crime_thriller", "action", "horror_occult", "comedy"}:
        score += 5
        reasons.append("콘셉트가 선명한 장르영화")

    player_network = _player_distribution_network(player)
    score += player_network * 0.08
    if player_network >= 55:
        reasons.append("플레이어의 배급 인맥이 협상을 돕는다")

    if int(project.get("marketing_budget") or 0) > 0 and marketing_power >= 78:
        score += 5
        reasons.append("마케팅 집행력과 궁합이 좋음")

    return {
        "id": str(row["id"]),
        "nameKo": str(row["name_ko"]),
        "nameEn": row.get("name_en"),
        "power": power,
        "screenPower": clamp(screen_power),
        "marketingCommitment": int(max(0, marketing_power) * 10_000_000),
        "score": round(score, 2),
        "strategy": strategy,
        "reputation": reputation,
        "profile": profile,
        "reasons": reasons or ["기본 배급망과 시장 영향력 기준"],
    }


def _write_project_distribution(
    conn: Any,
    project_id: str,
    state: dict[str, Any],
    stats: dict[str, Any],
) -> None:
    terms = state.get("terms") or {
        "status": state.get("status"),
        "summary": state.get("summary"),
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO project_distribution (
            project_id, distributor_id, deal_type, marketing_commitment,
            screen_power, terms_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            state.get("distributorId"),
            state.get("dealType"),
            int(state.get("marketingCommitment") or 0),
            int(state.get("screenPower") or 0),
            dumps_json(terms),
        ),
    )
    stats["distribution_match_status"] = state.get("status")
    stats["distributor_id"] = state.get("distributorId")
    stats["distributor_name"] = state.get("distributorName")
    stats["distribution_deal_type"] = state.get("dealType")
    stats["distribution_match_summary"] = state.get("summary")
    stats["screen_power"] = int(state.get("screenPower") or 0)
    stats["distribution_marketing_commitment"] = int(state.get("marketingCommitment") or 0)
    if state.get("status") == "matched":
        stats["pre_release_interest"] = clamp(float(stats.get("pre_release_interest", 0)) + 3)
        stats["financial_risk"] = clamp(float(stats.get("financial_risk", 0)) - 4)
    payload = dumps_json(stats)
    conn.execute("UPDATE projects SET stats_json = ? WHERE id = ?", (payload, project_id))
    conn.execute("UPDATE production_projects SET stats_json = ? WHERE id = ?", (payload, project_id))


def _project_distribution_state(conn: Any, project_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT pd.*, o.name_ko
        FROM project_distribution pd
        LEFT JOIN organizations o ON o.id = pd.distributor_id
        WHERE pd.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row:
        return _distribution_state_from_row(dict(row))
    project = _load_project_context(conn, project_id)
    if project:
        stats = loads_json(project.get("stats_json"), {})
        if stats.get("distribution_match_status"):
            return {
                "status": stats.get("distribution_match_status"),
                "label": stats.get("distributor_name") or "배급사 미정",
                "summary": stats.get("distribution_match_summary") or "",
                "distributorId": stats.get("distributor_id"),
                "distributorName": stats.get("distributor_name"),
            }
    return {
        "status": "unmatched",
        "label": "배급사 미정",
        "summary": "아직 배급 매칭 정보가 없습니다.",
        "distributorId": None,
        "distributorName": None,
    }


def _distribution_state_from_row(row: dict[str, Any]) -> dict[str, Any]:
    terms = loads_json(row.get("terms_json"), {})
    distributor_name = row.get("name_ko") or terms.get("distributorName")
    label = "배급사 미정"
    if distributor_name:
        label = str(distributor_name)
        if row.get("deal_type"):
            label = f"{label} · {row['deal_type']}"
    return {
        "status": "matched" if row.get("distributor_id") else terms.get("status", "unmatched"),
        "label": label,
        "summary": terms.get("summary") or "",
        "distributorId": row.get("distributor_id"),
        "distributorName": distributor_name,
        "dealType": row.get("deal_type"),
        "marketingCommitment": int(row.get("marketing_commitment") or 0),
        "screenPower": int(row.get("screen_power") or 0),
        "terms": terms,
    }


def _deal_type_for(candidate: dict[str, Any], scale: dict[str, Any]) -> str:
    scale_id = _canonical_value(scale.get("id"))
    if scale_id in {"short", "short_film", "independent", "independent_film"}:
        return "제한 개봉·영화제 연계"
    if scale_id == "low_budget_genre":
        return "저예산 장르 개봉 협의"
    if scale_id == "mid_commercial":
        return "전국 개봉 우선 협의"
    if scale_id in {"large_commercial", "tentpole_blockbuster"}:
        return "메이저 와이드릴리즈 패키지"
    if int(candidate.get("power") or 0) >= 85:
        return "메이저 배급 협의"
    return "배급 협의"


def _match_summary(candidate: dict[str, Any], genre: dict[str, Any], scale: dict[str, Any]) -> str:
    genre_name = genre.get("name") or genre.get("id") or "이 장르"
    scale_name = scale.get("name") or scale.get("id") or "이 규모"
    reason = ", ".join(candidate.get("reasons") or [])
    return (
        f"{candidate['nameKo']}이(가) {scale_name}·{genre_name} 프로젝트의 1차 배급 파트너로 매칭되었습니다. "
        f"근거: {reason}."
    )


def _risk_text(candidate: dict[str, Any], scale: dict[str, Any]) -> str:
    scale_id = _canonical_value(scale.get("id"))
    if int(candidate.get("power") or 0) >= 85 and scale_id in COMMERCIAL_SCALES:
        return "개봉 규모와 마케팅은 강해지지만 성과 압박과 개봉 슬롯 경쟁도 커집니다."
    if scale_id in LOW_SCOPE_SCALES:
        return "상영망은 제한적일 수 있지만 조건 조정과 입소문 전략을 쓰기 쉽습니다."
    return "배급 조건은 프로젝트 완성도와 캐스팅, 개봉 시기에 따라 다시 흔들릴 수 있습니다."


def _player_distribution_network(player: Any) -> float:
    if not player:
        return 0.0
    try:
        network = loads_json(player["network_json"], {})
    except (KeyError, TypeError):
        network = loads_json(getattr(player, "network_json", None), {})
    return float(network.get("distribution_network", 0) or 0)


def _canonical_value(value: Any) -> str:
    text = str(value or "").strip()
    for prefix in ("scale_", "genre_"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text
