from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json
from app.services.awards_service import consider_film_for_awards

RESULT_LABELS = {
    "winner": "수상",
    "nominee": "후보",
    "historical": "기록",
}


def list_awards(*, until_year: int | None = None) -> list[dict[str, Any]]:
    where = "WHERE founded_year IS NULL OR founded_year <= ?" if until_year is not None else ""
    params = [int(until_year)] if until_year is not None else []
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM awards {where} ORDER BY founded_year, name",
            params,
        ).fetchall()
    awards: list[dict[str, Any]] = []
    for row in rows:
        award = _award_from_row(dict(row))
        awards.append(award)
    return awards


def list_award_results(
    *,
    include_player_results: bool = True,
    until_year: int | None = None,
    until_month: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    historical_clause, historical_params = _occurred_clause("year", "month", until_year, until_month)
    player_clause, player_params = _occurred_clause("year", None, until_year, None)
    with get_connection() as conn:
        historical = conn.execute(
            f"""
            SELECT * FROM history_award_results
            {historical_clause}
            ORDER BY year DESC, award_id, category
            """,
            historical_params,
        ).fetchall()
        player = []
        if include_player_results:
            player = conn.execute(
                f"""
                SELECT * FROM movies_awards
                {player_clause}
                ORDER BY year DESC, award_id, category
                """,
                player_params,
            ).fetchall()
    return {
        "historical": [dict(row) for row in historical],
        "player": [dict(row) for row in player],
    }


def get_award_profile(
    award_id: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> dict[str, Any]:
    with get_connection() as conn:
        award_row = conn.execute("SELECT * FROM awards WHERE id = ?", (award_id,)).fetchone()
        if not award_row:
            return {
                "id": award_id,
                "name": award_id,
                "country": "",
                "foundedYear": None,
                "categories": [],
                "publicProfile": {},
                "statureText": "아직 등록되지 않은 시상식입니다.",
                "characterText": "시상식 데이터가 연결되면 위상과 성격이 표시됩니다.",
                "results": [],
                "playerResults": [],
            }
        award = _award_from_row(dict(award_row))
        historical_clause, historical_params = _occurred_clause("r.year", "r.month", until_year, until_month)
        historical_where = "WHERE r.award_id = ?"
        if historical_clause:
            historical_where += " AND " + historical_clause.removeprefix("WHERE ")
        historical_rows = conn.execute(
            f"""
            SELECT r.*
            FROM history_award_results r
            {historical_where}
            ORDER BY r.year, COALESCE(r.month, 12), r.category, r.result
            """,
            [award_id, *historical_params],
        ).fetchall()
        player_clause, player_params = _occurred_clause("ma.year", None, until_year, None)
        player_where = "WHERE ma.award_id = ?"
        if player_clause:
            player_where += " AND " + player_clause.removeprefix("WHERE ")
        player_rows = conn.execute(
            f"""
            SELECT ma.*, COALESCE(cf.title, ma.movie_id) AS work_title
            FROM movies_awards ma
            LEFT JOIN completed_films cf ON cf.id = ma.movie_id
            {player_where}
            ORDER BY ma.year, ma.category, ma.result
            """,
            [award_id, *player_params],
        ).fetchall()
    profile = award.get("publicProfile") or {}
    return {
        **award,
        "typeLabel": _type_label(award),
        "oneLine": profile.get("oneLine") or _default_one_line(award),
        "statureText": profile.get("statureText") or _stature_text(int(award.get("prestige") or 50)),
        "characterText": profile.get("characterText") or _character_text(award),
        "playerImpactText": profile.get("playerImpactText") or _player_impact_text(award),
        "results": [_award_result_from_row(dict(row)) for row in historical_rows],
        "playerResults": [_player_award_result_from_row(dict(row)) for row in player_rows],
        "currentDate": {"year": until_year, "month": until_month},
    }


def award_profile_text(profile: dict[str, Any]) -> str:
    categories = ", ".join(profile.get("categories") or [])
    lines = [
        str(profile.get("name") or profile.get("id") or "시상식"),
        f"구분: {profile.get('typeLabel') or '-'}",
        f"시작: {profile.get('foundedYear') or '기록 없음'}년",
        f"국가/권역: {profile.get('country') or '-'}",
        "",
        "한줄 평가",
        profile.get("oneLine") or "",
        "",
        "위상",
        profile.get("statureText") or "",
        "",
        "성격",
        profile.get("characterText") or "",
        "",
        "주요 부문",
        categories or "등록된 부문 없음",
        "",
        "플레이어에게 의미",
        profile.get("playerImpactText") or "",
        "",
        "게임 내 시간 기준 역대 수상 기록",
    ]
    results = profile.get("results") or []
    if not results:
        lines.append("아직 DB에 정리된 수상 결과가 없습니다.")
    else:
        for result in results:
            lines.append(_award_result_line(result))
    player_results = profile.get("playerResults") or []
    lines.extend(["", "플레이어 작품 기록"])
    if not player_results:
        lines.append("아직 이 시상식에 오른 플레이어 작품이 없습니다.")
    else:
        for result in player_results:
            lines.append(_award_result_line(result))
    return "\n".join(lines)


def _award_from_row(row: dict[str, Any]) -> dict[str, Any]:
    row["foundedYear"] = row.pop("founded_year", None)
    row["categories"] = loads_json(row.pop("categories_json", None), [])
    row["publicProfile"] = loads_json(row.pop("public_profile_json", None), {})
    return row


def _award_result_from_row(row: dict[str, Any]) -> dict[str, Any]:
    row["awardId"] = row.pop("award_id", None)
    row["movieId"] = row.pop("movie_id", None)
    row["fixedLevel"] = row.pop("fixed_level", None)
    row["winnerName"] = row.pop("winner_name", None)
    row["workTitle"] = row.pop("work_title", None)
    row["personName"] = row.pop("person_name", None)
    row["sourceNote"] = row.pop("source_note", None)
    row["effects"] = loads_json(row.pop("effects_json", None), {})
    return row


def _player_award_result_from_row(row: dict[str, Any]) -> dict[str, Any]:
    row["awardId"] = row.pop("award_id", None)
    row["movieId"] = row.pop("movie_id", None)
    row["workTitle"] = row.get("work_title") or row.get("movieId")
    row["winnerName"] = row["workTitle"]
    row["effects"] = loads_json(row.pop("effects_json", None), {})
    return row


def _occurred_clause(
    year_column: str,
    month_column: str | None,
    until_year: int | None,
    until_month: int | None,
) -> tuple[str, list[int]]:
    if until_year is None:
        return "", []
    if month_column:
        month = int(until_month or 12)
        return (
            f"WHERE ({year_column} < ? OR ({year_column} = ? AND COALESCE({month_column}, 12) <= ?))",
            [int(until_year), int(until_year), month],
        )
    return f"WHERE {year_column} <= ?", [int(until_year)]


def _type_label(award: dict[str, Any]) -> str:
    if award.get("country") == "KR":
        if "영화제" in str(award.get("name") or ""):
            return "국내 국제영화제"
        return "국내 영화상"
    if award.get("id") in {"award_cannes", "award_venice"}:
        return "해외 국제영화제"
    return "해외 시상식"


def _stature_text(prestige: int) -> str:
    if prestige >= 95:
        return "세계 영화계의 최상위 권위로, 수상 자체가 국제 배급과 평론 지형을 바꾼다."
    if prestige >= 85:
        return "영화제와 산업 양쪽에서 강한 영향력을 가진 핵심 시상식이다."
    if prestige >= 75:
        return "국내 주요 시상식으로 대중과 업계 평판에 확실한 영향을 준다."
    return "특정 권역과 평단, 산업 기록에서 의미 있는 위상을 가진다."


def _character_text(award: dict[str, Any]) -> str:
    name = str(award.get("name") or "")
    if "평론가" in name:
        return "흥행보다 영화적 완성도와 비평적 의미를 중시한다."
    if "부산" in name:
        return "신인, 독립, 아시아 영화 네트워크와 해외 세일즈에 강하다."
    if award.get("country") == "KR":
        return "국내 관객 반응, 산업 평가, 배우·감독 브랜드를 함께 반영한다."
    return "국제 평론, 캠페인, 영화제 네트워크, 해외 시장의 반응이 함께 작동한다."


def _player_impact_text(award: dict[str, Any]) -> str:
    if int(award.get("prestige") or 0) >= 95:
        return "수상 시 해외 명성, 판권 가치, 글로벌 플랫폼 협상력이 크게 오른다."
    if award.get("country") == "KR":
        return "후보와 수상 기록은 차기작 투자, 배우 섭외, 언론 노출에 직접적인 도움이 된다."
    return "영화제 네트워크와 해외 평판을 넓히는 데 도움이 된다."


def _default_one_line(award: dict[str, Any]) -> str:
    return f"{award.get('name')}은 게임 내 수상과 명성 변화를 담당하는 시상식이다."


def _award_result_line(result: dict[str, Any]) -> str:
    when = str(result.get("year") or "연도 미상")
    if result.get("month"):
        when += f".{int(result['month'])}"
    winner = result.get("winnerName") or result.get("workTitle") or result.get("movieId") or "수상자 미상"
    work = result.get("workTitle")
    if work and work != winner:
        winner = f"{winner} ({work})"
    return f"- {when} · {result.get('category') or '-'} · {winner} · {_result_label(result.get('result'))}"


def _result_label(result: Any) -> str:
    return RESULT_LABELS.get(str(result or ""), str(result or "-"))
