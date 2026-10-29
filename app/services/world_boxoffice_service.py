from __future__ import annotations

import math
from typing import Any

from app.database import get_connection, loads_json
from app.services.calendar_service import current_game_date
from app.services.market_service import market_state_dict


DOMESTIC_ORIGINS = {
    "domestic",
    "protected_domestic",
    "domestic_protected",
    "player",
    "player_created",
    "npc_generated",
    "historical_domestic",
}
FOREIGN_ORIGINS = {"foreign", "foreign_fixed", "historical_foreign_fixed"}
MARKET_RELEASE_ORIGINS = ("npc_generated", "historical_domestic", "protected_domestic", "foreign_fixed")
MARKET_RELEASE_ORDER = {
    "protected_domestic": 1,
    "historical_domestic": 2,
    "foreign_fixed": 3,
    "npc_generated": 4,
}

FALLBACK_TOTAL_SCREENS = (
    (1980, 760),
    (1990, 820),
    (1998, 1_050),
    (2003, 1_350),
    (2009, 2_000),
    (2015, 2_450),
    (2020, 3_000),
    (2026, 3_200),
    (2035, 3_350),
)

SCALE_SCREEN_BASE = {
    "scale_short": 12,
    "scale_independent": 45,
    "scale_low_budget_genre": 160,
    "scale_mid_commercial": 480,
    "scale_large_commercial": 850,
    "scale_tentpole": 1_150,
    "short_film": 12,
    "independent_film": 45,
    "low_budget_genre": 160,
    "mid_commercial": 480,
    "large_commercial": 850,
    "tentpole_blockbuster": 1_150,
}

SCALE_RUN_DAYS = {
    "scale_short": 7,
    "scale_independent": 14,
    "scale_low_budget_genre": 21,
    "scale_mid_commercial": 28,
    "scale_large_commercial": 35,
    "scale_tentpole": 42,
    "short_film": 7,
    "independent_film": 14,
    "low_budget_genre": 21,
    "mid_commercial": 28,
    "large_commercial": 35,
    "tentpole_blockbuster": 42,
}


def get_world_boxoffice_state() -> dict[str, Any]:
    year, month, day = current_game_date()
    target_date = f"{year:04d}{month:02d}{day:02d}"
    from app.services.historical_release_service import ensure_historical_releases_for_month
    from app.services.npc_activity_service import ensure_npc_releases_for_month

    ensure_historical_releases_for_month(year, month)
    ensure_npc_releases_for_month(year, month)
    with get_connection() as conn:
        total_screens, screen_source = _total_screens(conn, year)
        actual_rows = _load_kobis_daily_rows(conn, target_date, total_screens)
        player_rows = _load_player_release_rows(conn, year, month, day, total_screens)
        market_release_rows = _load_market_release_rows(conn, year, month, day, total_screens)
        annual_rows = []
        if not actual_rows and not player_rows and not market_release_rows:
            annual_rows = _load_annual_reference_rows(conn, year, total_screens)
        market_state = _load_market_state(conn, year, month)
        notes = _load_market_notes(conn, year, month)

    rows = _rank_rows(actual_rows + player_rows + market_release_rows + annual_rows, total_screens)
    if not rows:
        rows = _baseline_market_rows(year, market_state, total_screens)
        mode = "market_baseline"
    elif actual_rows:
        mode = "actual_daily"
    elif player_rows or market_release_rows:
        mode = "simulated_current_window"
    else:
        mode = "annual_reference"

    summary = _build_summary(rows, total_screens, screen_source, mode)
    return {
        "date": {"year": year, "month": month, "day": day, "targetDate": target_date},
        "mode": mode,
        "modeLabel": _mode_label(mode),
        "summary": summary,
        "rows": rows[:20],
        "marketState": market_state,
        "notes": notes,
    }


def _load_kobis_daily_rows(conn: Any, target_date: str, total_screens: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT b.*, d.nations_json, d.genres_json, d.companies_json
        FROM staging_kobis_daily_boxoffice b
        LEFT JOIN staging_kobis_movie_details d ON d.movie_code = b.movie_code
        WHERE b.target_date = ?
        ORDER BY b.rank ASC, b.audience_count DESC
        LIMIT 20
        """,
        (target_date,),
    ).fetchall()
    entries = []
    for row in rows:
        data = dict(row)
        nations = _json_list(data.get("nations_json"))
        country_text = " ".join(_names_from_items(nations))
        origin = "domestic" if _looks_korean(country_text) else "foreign" if country_text else "unknown"
        screen_count = int(data.get("screen_count") or 0)
        entries.append(
            {
                "id": data["movie_code"],
                "title": data["movie_name"],
                "origin": origin,
                "originLabel": _origin_label(origin),
                "dailyAudience": int(data.get("audience_count") or 0),
                "cumulativeAudience": int(data.get("audience_accumulated") or 0),
                "dailyRevenue": int(data.get("sales_amount") or 0),
                "cumulativeRevenue": int(data.get("sales_accumulated") or 0),
                "screenCount": screen_count,
                "screenShare": _ratio(screen_count, total_screens),
                "source": "KOBIS 일일 박스오피스",
                "status": "일일 집계",
            }
        )
    return entries


def _load_player_release_rows(conn: Any, year: int, month: int, day: int, total_screens: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, p.title, p.scale_id, p.genre_id, g.name AS genre_name
        FROM theatrical_runs r
        JOIN projects p ON p.id = r.project_id
        LEFT JOIN genres g ON g.id = p.genre_id
        WHERE r.status = 'active'
        ORDER BY r.created_at DESC
        """
    ).fetchall()
    entries = []
    for row in rows:
        data = dict(row)
        forecast = loads_json(data.get("forecast_json"), {})
        daily_plan = loads_json(data.get("daily_plan_json"), [])
        daily = conn.execute(
            """
            SELECT *
            FROM theatrical_daily_results
            WHERE run_id = ?
            ORDER BY day_number DESC
            LIMIT 1
            """,
            (data["id"],),
        ).fetchone()
        if daily:
            daily_data = dict(daily)
            daily_audience = int(daily_data.get("daily_audience") or 0)
            cumulative_audience = int(daily_data.get("cumulative_audience") or 0)
            daily_revenue = int(daily_data.get("daily_revenue") or 0)
            cumulative_revenue = int(daily_data.get("cumulative_revenue") or 0)
            status = f"{int(daily_data.get('day_number') or 0)}일차 집계"
        else:
            daily_audience = int(daily_plan[0]) if daily_plan else 0
            cumulative_audience = 0
            ticket_price = int(forecast.get("average_ticket_price", 0) or 0)
            daily_revenue = daily_audience * ticket_price
            cumulative_revenue = 0
            status = "개봉일 집계 전"
        screen_count = _estimate_screen_count(
            expected_audience=int(forecast.get("final_audience", 0) or 0),
            scale_id=str(data.get("scale_id") or ""),
            origin="player",
            total_screens=total_screens,
        )
        entries.append(
            {
                "id": data["id"],
                "title": data["title"],
                "origin": "player",
                "originLabel": "내 영화",
                "dailyAudience": daily_audience,
                "cumulativeAudience": cumulative_audience,
                "dailyRevenue": daily_revenue,
                "cumulativeRevenue": cumulative_revenue,
                "screenCount": screen_count,
                "screenShare": _ratio(screen_count, total_screens),
                "source": "플레이어 1차 시장",
                "status": status,
                "genreName": data.get("genre_name"),
                "isPlayerFilm": True,
            }
        )
    return entries


def _load_market_release_rows(
    conn: Any,
    year: int,
    month: int,
    day: int,
    total_screens: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, g.name AS genre_name, s.name AS scale_name
        FROM market_releases r
        LEFT JOIN genres g ON g.id = r.genre_id
        LEFT JOIN project_scales s ON s.id = r.scale_id
        WHERE r.origin IN ({})
          AND r.release_year = ?
          AND r.release_month = ?
        ORDER BY r.expected_audience DESC, r.title
        """.format(",".join("?" for _ in MARKET_RELEASE_ORIGINS)),
        (*MARKET_RELEASE_ORIGINS, year, month),
    ).fetchall()
    if not rows:
        return []

    from app.services.ticket_price_service import get_ticket_price_for_year

    ticket_price = int(get_ticket_price_for_year(year).get("average_ticket_price") or 0)
    entries: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        entry = _market_release_entry(data, day=day, ticket_price=ticket_price, total_screens=total_screens)
        if not entry:
            continue
        entries.append(entry)
    return sorted(
        entries,
        key=lambda row: (MARKET_RELEASE_ORDER.get(str(row.get("origin")), 99), -int(row.get("dailyAudience") or 0)),
    )


def _market_release_entry(
    data: dict[str, Any],
    *,
    day: int,
    ticket_price: int,
    total_screens: int,
) -> dict[str, Any] | None:
    metadata = loads_json(data.get("effects_json"), {})
    scale_id = str(data.get("scale_id") or "")
    day_number = day - int(metadata.get("releaseDay") or 1) + 1
    run_days = int(metadata.get("runDays") or SCALE_RUN_DAYS.get(scale_id, 28))
    if day_number < 1 or day_number > run_days:
        return None

    expected = int(data.get("actual_audience") or data.get("expected_audience") or metadata.get("expectedAudience") or 0)
    daily_audience, cumulative_audience = _simulated_window_numbers(expected, scale_id, day_number)
    origin = str(data.get("origin") or "")
    estimate_origin = "foreign" if origin == "foreign_fixed" else "domestic"
    screen_count = _estimate_screen_count(expected, scale_id, estimate_origin, total_screens)
    return {
        "id": data["id"],
        "title": data["title"],
        "origin": origin,
        "originLabel": _origin_label(origin),
        "dailyAudience": daily_audience,
        "cumulativeAudience": cumulative_audience,
        "dailyRevenue": daily_audience * ticket_price,
        "cumulativeRevenue": cumulative_audience * ticket_price,
        "screenCount": screen_count,
        "screenShare": _ratio(screen_count, total_screens),
        "source": _market_release_source(origin),
        "status": _market_release_status(origin, metadata),
        "genreName": data.get("genre_name") or metadata.get("genreName"),
        "scaleName": data.get("scale_name") or metadata.get("scaleName"),
    }


def _market_release_source(origin: str) -> str:
    if origin == "npc_generated":
        return "게임 내 경쟁작"
    if origin == "historical_domestic":
        return "한국영화 역사 개봉"
    if origin == "protected_domestic":
        return "주요 필모그래피 개봉"
    if origin == "foreign_fixed":
        return "외화 고정 개봉"
    return "시장 개봉"


def _market_release_status(origin: str, metadata: dict[str, Any]) -> str:
    if origin == "foreign_fixed":
        return f"{metadata.get('impactGrade') or metadata.get('impact_grade') or '-'}급 시장 충격"
    director = metadata.get("directorName") or "감독 미상"
    actors = metadata.get("actorNames") or []
    actor_text = ", ".join(str(name) for name in actors[:2]) if actors else "출연진 미공개"
    if origin == "historical_domestic":
        return f"{director} · 역사적 흥행작"
    if origin == "protected_domestic":
        return f"{director} 필모그래피"
    return f"{director} · {actor_text}"


def _load_annual_reference_rows(conn: Any, year: int, total_screens: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM staging_kobis_yearly_boxoffice
        WHERE year = ?
        ORDER BY audience_count DESC
        LIMIT 12
        """,
        (year,),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            """
            SELECT c.*, m.gross_revenue AS boxoffice_revenue
            FROM completed_films c
            LEFT JOIN movies_boxoffice m ON m.movie_id = c.id
            WHERE c.release_year = ?
            ORDER BY c.final_audience DESC
            LIMIT 8
            """,
            (year,),
        ).fetchall()
        return [_completed_film_reference(dict(row), total_screens) for row in rows]
    return [_yearly_reference(dict(row), total_screens) for row in rows]


def _yearly_reference(row: dict[str, Any], total_screens: int) -> dict[str, Any]:
    audience = int(row.get("audience_count") or 0)
    sales = int(row.get("sales_amount") or 0)
    screen_count = int(row.get("screen_count") or 0)
    if not screen_count:
        screen_count = _estimate_screen_count(audience, "", "unknown", total_screens)
    return {
        "id": row.get("movie_code"),
        "title": row.get("movie_name"),
        "origin": "unknown",
        "originLabel": "연간",
        "dailyAudience": max(0, audience // 45),
        "cumulativeAudience": audience,
        "dailyRevenue": max(0, sales // 45),
        "cumulativeRevenue": sales,
        "screenCount": screen_count,
        "screenShare": _ratio(screen_count, total_screens),
        "source": "연간 박스오피스 참고",
        "status": "연간 누적 기준",
    }


def _completed_film_reference(row: dict[str, Any], total_screens: int) -> dict[str, Any]:
    audience = int(row.get("final_audience") or 0)
    revenue = int(row.get("gross_revenue") or row.get("boxoffice_revenue") or 0)
    screen_count = _estimate_screen_count(audience, str(row.get("scale_id") or ""), "player", total_screens)
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "origin": "player",
        "originLabel": "내 영화",
        "dailyAudience": max(0, audience // 35),
        "cumulativeAudience": audience,
        "dailyRevenue": max(0, revenue // 35),
        "cumulativeRevenue": revenue,
        "screenCount": screen_count,
        "screenShare": _ratio(screen_count, total_screens),
        "source": "플레이어 연간 누적",
        "status": "종영작 참고",
        "isPlayerFilm": True,
    }


def _baseline_market_rows(year: int, market_state: dict[str, Any], total_screens: int) -> list[dict[str, Any]]:
    theater_demand = int(market_state.get("theater_demand") or _fallback_theater_demand(year))
    foreign_competition = int(market_state.get("foreign_competition") or 50)
    domestic_daily = max(8_000, theater_demand * 1_100)
    foreign_daily = max(5_000, foreign_competition * 1_250)
    indie_daily = max(900, int(domestic_daily * 0.08))
    rows = [
        ("market_domestic", "동시기 한국 상업영화 묶음", "domestic", domestic_daily, int(total_screens * 0.34), "시장 기준선"),
        ("market_foreign", "동시기 외화 경쟁작 묶음", "foreign", foreign_daily, int(total_screens * 0.38), "시장 기준선"),
        ("market_indie", "독립·예술영화 개봉권", "domestic", indie_daily, int(total_screens * 0.08), "시장 기준선"),
    ]
    ranked = []
    for row_id, title, origin, daily_audience, screen_count, source in rows:
        ranked.append(
            {
                "id": row_id,
                "title": title,
                "origin": origin,
                "originLabel": _origin_label(origin),
                "dailyAudience": daily_audience,
                "cumulativeAudience": 0,
                "dailyRevenue": 0,
                "cumulativeRevenue": 0,
                "screenCount": screen_count,
                "screenShare": _ratio(screen_count, total_screens),
                "source": source,
                "status": "추정 시장 구간",
            }
        )
    return _rank_rows(ranked, total_screens)


def _load_market_state(conn: Any, year: int, month: int) -> dict[str, Any]:
    data = market_state_dict(conn, year, month)
    data["source"] = "market_state"
    return data


def _load_market_notes(conn: Any, year: int, month: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT title, body, source_type, target_type, target_id
        FROM news_items
        WHERE year = ? AND month = ?
        ORDER BY id DESC
        LIMIT 8
        """,
        (year, month),
    ).fetchall()
    notes = [dict(row) for row in rows]
    if notes:
        return notes
    foreign = conn.execute(
        """
        SELECT title, description, 'foreign_fixed' AS source_type, id AS target_id
        FROM history_foreign_events
        WHERE year = ? AND (month IS NULL OR month = ?)
        ORDER BY title
        LIMIT 5
        """,
        (year, month),
    ).fetchall()
    protected = conn.execute(
        """
        SELECT title, '주요 한국영화 개봉 예정' AS description,
               'protected_history' AS source_type, id AS target_id
        FROM history_protected_director_films
        WHERE release_year = ? AND release_month = ?
        ORDER BY title
        LIMIT 5
        """,
        (year, month),
    ).fetchall()
    return [
        {
            "title": row["title"],
            "body": row["description"],
            "source_type": row["source_type"],
            "target_type": "film",
            "target_id": row["target_id"],
        }
        for row in [*foreign, *protected]
    ][:8]


def _total_screens(conn: Any, year: int) -> tuple[int, str]:
    row = conn.execute(
        """
        SELECT screen_count, source_file
        FROM market_yearly_stats
        WHERE year <= ? AND screen_count IS NOT NULL
        ORDER BY year DESC
        LIMIT 1
        """,
        (year,),
    ).fetchone()
    if row and int(row["screen_count"] or 0) > 0:
        return int(row["screen_count"]), str(row["source_file"] or "market_yearly_stats")
    for threshold, count in reversed(FALLBACK_TOTAL_SCREENS):
        if year >= threshold:
            return count, "시대별 추정"
    return FALLBACK_TOTAL_SCREENS[0][1], "시대별 추정"


def _rank_rows(rows: list[dict[str, Any]], total_screens: int) -> list[dict[str, Any]]:
    rows = sorted(
        rows,
        key=lambda row: (int(row.get("dailyAudience") or 0), int(row.get("cumulativeAudience") or 0)),
        reverse=True,
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        screen_count = int(row.get("screenCount") or 0)
        row["screenShare"] = _ratio(screen_count, total_screens)
    return rows


def _build_summary(
    rows: list[dict[str, Any]],
    total_screens: int,
    screen_source: str,
    mode: str,
) -> dict[str, Any]:
    total_daily_audience = sum(int(row.get("dailyAudience") or 0) for row in rows)
    total_daily_revenue = sum(int(row.get("dailyRevenue") or 0) for row in rows)
    allocated_screens = sum(int(row.get("screenCount") or 0) for row in rows)
    domestic_audience = sum(
        int(row.get("dailyAudience") or 0)
        for row in rows
        if str(row.get("origin")) in DOMESTIC_ORIGINS
    )
    foreign_audience = sum(
        int(row.get("dailyAudience") or 0)
        for row in rows
        if str(row.get("origin")) in FOREIGN_ORIGINS
    )
    domestic_screens = sum(
        int(row.get("screenCount") or 0)
        for row in rows
        if str(row.get("origin")) in DOMESTIC_ORIGINS
    )
    foreign_screens = sum(
        int(row.get("screenCount") or 0)
        for row in rows
        if str(row.get("origin")) in FOREIGN_ORIGINS
    )
    return {
        "totalDailyAudience": total_daily_audience,
        "totalDailyRevenue": total_daily_revenue,
        "totalScreens": total_screens,
        "allocatedScreens": allocated_screens,
        "screenSource": screen_source,
        "domesticAudienceShare": _ratio(domestic_audience, total_daily_audience),
        "foreignAudienceShare": _ratio(foreign_audience, total_daily_audience),
        "domesticScreenShare": _ratio(domestic_screens, total_screens),
        "foreignScreenShare": _ratio(foreign_screens, total_screens),
        "rowCount": len(rows),
        "mode": mode,
    }


def _simulated_window_numbers(expected_audience: int, scale_id: str, current_day: int) -> tuple[int, int]:
    expected_audience = max(0, int(expected_audience))
    max_days = SCALE_RUN_DAYS.get(scale_id, 35)
    day_number = max(1, min(int(current_day), max_days))
    plan = _daily_audience_plan(expected_audience, max_days)
    daily = int(plan[day_number - 1]) if day_number - 1 < len(plan) else 0
    cumulative = int(sum(plan[:day_number]))
    return daily, cumulative


def _daily_audience_plan(final_audience: int, max_days: int) -> list[int]:
    final_audience = max(0, int(final_audience))
    max_days = max(1, int(max_days))
    if final_audience <= 0:
        return [0 for _ in range(max_days)]
    weights = []
    for day_number in range(1, max_days + 1):
        weekday = (day_number - 1) % 7
        decay = math.exp(-0.105 * (day_number - 1))
        weekend_bonus = 1.35 if weekday in {4, 5, 6} else 1.0
        opening_bonus = 1.55 if day_number <= 3 else 1.0
        weights.append(decay * weekend_bonus * opening_bonus)
    total_weight = sum(weights) or 1.0
    plan = [int(final_audience * weight / total_weight) for weight in weights]
    if plan:
        plan[0] += final_audience - sum(plan)
    return plan


def _estimate_screen_count(expected_audience: int, scale_id: str, origin: str, total_screens: int) -> int:
    expected_audience = max(0, int(expected_audience))
    base = SCALE_SCREEN_BASE.get(scale_id, 220)
    audience_bonus = int(min(620, math.sqrt(max(expected_audience, 1)) * 0.16))
    origin_bonus = 120 if origin in FOREIGN_ORIGINS or origin == "foreign" else 60 if origin == "player" else 0
    count = base + audience_bonus + origin_bonus
    cap_ratio = 0.55 if origin in FOREIGN_ORIGINS or origin == "foreign" else 0.48
    return max(1, min(int(total_screens * cap_ratio), count))


def _json_list(value: Any) -> list[Any]:
    parsed = loads_json(value, [])
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _names_from_items(items: list[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = (
                item.get("nameKo")
                or item.get("nationNm")
                or item.get("name")
                or item.get("label")
                or ""
            )
        else:
            name = ""
        if name and name not in names:
            names.append(str(name))
    return names


def _looks_korean(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in ("한국", "대한민국", "south korea", "republic of korea", "korea"))


def _origin_label(origin: str) -> str:
    if origin == "player":
        return "내 영화"
    if origin in DOMESTIC_ORIGINS:
        return "한국영화"
    if origin in FOREIGN_ORIGINS:
        return "외화"
    return "미분류"


def _mode_label(mode: str) -> str:
    return {
        "actual_daily": "실제 일일 데이터",
        "simulated_current_window": "현재 개봉작 경쟁",
        "annual_reference": "연간 누적 참고",
        "market_baseline": "시장 기준선",
    }.get(mode, mode)


def _fallback_theater_demand(year: int) -> int:
    if year < 1990:
        return 45
    if year < 2000:
        return 55
    if year < 2010:
        return 80
    if year < 2020:
        return 90
    return 55


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    denominator = float(denominator or 0)
    if denominator <= 0:
        return None
    return round(float(numerator or 0) / denominator, 4)
