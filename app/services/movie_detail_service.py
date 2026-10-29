from __future__ import annotations

from datetime import date
from typing import Any

from app.database import get_connection, loads_json
from app.services.game_state import money
from app.services.public_text_service import audience_reaction_text, critic_reaction_text
from app.services.rating_service import rating_label
from app.services.version_service import get_project_versions, version_text


def get_movie_detail(movie_id: str) -> dict[str, Any]:
    movie_id = str(movie_id or "").strip()
    if not movie_id:
        return _unknown_detail(movie_id)
    with get_connection() as conn:
        detail = (
            _active_run_detail(conn, movie_id)
            or _completed_player_detail(conn, movie_id)
            or _market_release_detail(conn, movie_id)
            or _protected_history_detail(conn, movie_id)
            or _foreign_history_detail(conn, movie_id)
            or _kobis_detail(conn, movie_id)
            or _kmdb_detail(conn, movie_id)
            or _wikidata_movie_detail(conn, movie_id)
        )
    return detail or _unknown_detail(movie_id)


def detail_text(detail: dict[str, Any]) -> str:
    lines = [
        detail.get("title") or "작품 정보",
        f"구분: {detail.get('typeLabel') or '-'}",
        f"개봉: {detail.get('releaseLabel') or '미정'}",
        f"장르/규모: {detail.get('genreName') or '-'} · {detail.get('scaleName') or '-'}",
        f"관람등급: {detail.get('contentRatingName') or '등급 미정'}",
        f"제작비: {money(detail.get('productionBudget'))} · 마케팅비: {money(detail.get('marketingBudget'))} · 총비용: {money(detail.get('totalCost'))}",
        f"제작기간: {detail.get('productionPeriod') or '기록 없음'}",
        f"감독: {detail.get('directorText') or '기록 없음'}",
        f"출연진: {detail.get('castText') or '기록 없음'}",
        f"배급사: {detail.get('distributorText') or '기록 없음'}",
        f"로케이션/세트: {detail.get('locationText') or '기록 없음'}",
        f"판본: {detail.get('versionText') or '판본 기록 없음'}",
        f"관객 수: {_number(detail.get('audience'))}명 · 극장 매출: {money(detail.get('grossRevenue'))}",
        f"손익분기점: {_number(detail.get('breakEvenAudience'))}명 · 수익: {money(detail.get('profit'))}",
    ]
    if any(detail.get(key) is not None for key in ("ownCapitalUsed", "investmentUsed", "loanUsed", "investorRecoup")):
        lines.extend(
            [
                f"자기자본/투자본/대출 투입: {money(detail.get('ownCapitalUsed'))} · {money(detail.get('investmentUsed'))} · {money(detail.get('loanUsed'))}",
                f"투자자 회수/제작사 순유입: {money(detail.get('investorRecoup'))} · {money(detail.get('netStudioReceipts'))}",
            ]
        )
    rating_reasons = detail.get("contentRatingReasons") or []
    if rating_reasons:
        lines.append(f"심의 사유: {' '.join(str(reason) for reason in rating_reasons)}")
    lines.extend(
        [
            f"반응: {detail.get('scoreText') or '기록 없음'}",
            "",
            "대중 평가",
            detail.get("publicEvaluation") or "아직 충분한 관객 반응이 쌓이지 않았습니다.",
            "",
            "작품 설명",
            detail.get("description") or "아직 정리된 작품 설명이 없습니다.",
        ]
    )
    source = detail.get("sourceNote")
    if source:
        lines.extend(["", f"자료: {source}"])
    return "\n".join(lines)


def _active_run_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.*, p.title, p.genre_id, p.scale_id, p.production_budget,
               p.marketing_budget, p.stats_json, g.name AS genre_name,
               s.name AS scale_name
        FROM theatrical_runs r
        JOIN projects p ON p.id = r.project_id
        LEFT JOIN genres g ON g.id = p.genre_id
        LEFT JOIN project_scales s ON s.id = p.scale_id
        WHERE r.id = ? OR r.film_id = ? OR r.project_id = ?
        ORDER BY r.created_at DESC
        LIMIT 1
        """,
        (movie_id, movie_id, movie_id),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    forecast = loads_json(data.get("forecast_json"), {})
    final_result = loads_json(data.get("final_result_json"), {})
    latest = conn.execute(
        """
        SELECT *
        FROM theatrical_daily_results
        WHERE run_id = ?
        ORDER BY day_number DESC
        LIMIT 1
        """,
        (data["id"],),
    ).fetchone()
    cumulative_audience = int(latest["cumulative_audience"] or 0) if latest else 0
    cumulative_revenue = int(latest["cumulative_revenue"] or 0) if latest else 0
    total_cost = int(forecast.get("total_cost") or final_result.get("total_cost") or 0)
    if total_cost <= 0:
        total_cost = int(data.get("production_budget") or 0) + int(data.get("marketing_budget") or 0)
    project_id = str(data["project_id"])
    return {
        "id": data.get("film_id") or data["id"],
        "title": data["title"],
        "typeLabel": "상영 중인 플레이어 영화",
        "releaseLabel": f"{data['release_year']}년 {data['release_month']}월 {data['release_day']}일",
        "genreName": data.get("genre_name"),
        "scaleName": data.get("scale_name"),
        "contentRating": forecast.get("content_rating") or final_result.get("content_rating"),
        "contentRatingName": forecast.get("content_rating_name")
        or final_result.get("content_rating_name")
        or rating_label(forecast.get("content_rating") or final_result.get("content_rating")),
        "contentRatingReasons": forecast.get("content_rating_reasons") or final_result.get("content_rating_reasons") or [],
        "productionBudget": int(data.get("production_budget") or 0),
        "marketingBudget": int(data.get("marketing_budget") or 0),
        "totalCost": total_cost,
        "productionPeriod": _production_period(conn, project_id),
        "directorText": _project_people_text(conn, project_id, {"director", "main_director"}),
        "castText": _project_people_text(conn, project_id, {"lead_actor", "supporting_actor", "cameo_actor", "actor"}),
        "distributorText": _project_distributor_text(conn, project_id),
        "locationText": _project_location_text(conn, project_id),
        "versionText": version_text(get_project_versions(project_id, conn=conn)),
        "audience": cumulative_audience,
        "grossRevenue": cumulative_revenue,
        "breakEvenAudience": int(forecast.get("break_even_audience") or final_result.get("break_even_audience") or 0),
        "profit": final_result.get("profit"),
        "ownCapitalUsed": final_result.get("own_capital_used"),
        "investmentUsed": final_result.get("investment_used"),
        "loanUsed": final_result.get("loan_used"),
        "investorRecoup": final_result.get("investor_recoup"),
        "netStudioReceipts": final_result.get("net_studio_receipts"),
        "scoreText": _score_text(forecast.get("audience_score"), forecast.get("critic_score")),
        "publicEvaluation": _public_evaluation(
            audience=cumulative_audience,
            break_even=int(forecast.get("break_even_audience") or 0),
            profit=final_result.get("profit"),
            audience_score=forecast.get("audience_score"),
        ),
        "description": "극장 1차 시장이 진행 중인 작품입니다. 일일 관객 수와 수익은 상영일이 지날수록 누적됩니다.",
        "sourceNote": "플레이어 상영 기록",
    }


def _completed_player_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT c.*, g.name AS genre_name, s.name AS scale_name,
               m.metadata_json, box.studio_revenue, box.secondary_market_revenue,
               box.profit, box.metrics_json
        FROM completed_films c
        LEFT JOIN genres g ON g.id = c.genre_id
        LEFT JOIN project_scales s ON s.id = c.scale_id
        LEFT JOIN movies m ON m.id = c.id
        LEFT JOIN movies_boxoffice box ON box.movie_id = c.id
        WHERE c.id = ?
        """,
        (movie_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    metadata = loads_json(data.get("metadata_json"), {})
    metrics = loads_json(data.get("metrics_json"), {})
    project_id = metadata.get("projectId")
    content_rating = data.get("content_rating") or metrics.get("content_rating")
    return {
        "id": data["id"],
        "title": data["title"],
        "typeLabel": "플레이어 제작 영화",
        "releaseLabel": _year_month(data.get("release_year"), data.get("release_month")),
        "genreName": data.get("genre_name"),
        "scaleName": data.get("scale_name"),
        "contentRating": content_rating,
        "contentRatingName": metrics.get("content_rating_name") or rating_label(content_rating),
        "contentRatingReasons": loads_json(data.get("rating_reason_json"), metrics.get("content_rating_reasons", [])),
        "productionBudget": int(data.get("production_budget") or 0),
        "marketingBudget": int(data.get("marketing_budget") or 0),
        "totalCost": int(data.get("total_cost") or 0),
        "productionPeriod": _production_period(conn, project_id),
        "directorText": _project_people_text(conn, project_id, {"director", "main_director"}) if project_id else "",
        "castText": _project_people_text(conn, project_id, {"lead_actor", "supporting_actor", "cameo_actor", "actor"}) if project_id else "",
        "distributorText": _project_distributor_text(conn, project_id) if project_id else "",
        "locationText": _project_location_text(conn, project_id) if project_id else "",
        "versionText": version_text(get_project_versions(project_id, conn=conn)) if project_id else "",
        "audience": int(data.get("final_audience") or 0),
        "grossRevenue": int(data.get("gross_revenue") or 0),
        "breakEvenAudience": int(data.get("break_even_audience") or 0),
        "profit": int(data.get("profit") or metrics.get("profit") or 0),
        "ownCapitalUsed": metrics.get("own_capital_used"),
        "investmentUsed": metrics.get("investment_used"),
        "loanUsed": metrics.get("loan_used"),
        "investorRecoup": metrics.get("investor_recoup"),
        "netStudioReceipts": metrics.get("net_studio_receipts"),
        "scoreText": _score_text(data.get("audience_score"), data.get("critic_score")),
        "publicEvaluation": _public_evaluation(
            audience=int(data.get("final_audience") or 0),
            break_even=int(data.get("break_even_audience") or 0),
            profit=int(data.get("profit") or metrics.get("profit") or 0),
            audience_score=data.get("audience_score"),
        ),
        "description": data.get("result_summary") or metrics.get("result_summary"),
        "sourceNote": "플레이어 개봉/정산 기록",
    }


def _protected_history_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT f.*, p.name_ko AS director_name, g.name AS genre_name,
               s.name AS scale_name
        FROM history_protected_director_films f
        LEFT JOIN people p ON p.id = f.director_id
        LEFT JOIN genres g ON g.id = json_extract(f.metadata_json, '$.genreId')
        LEFT JOIN project_scales s ON s.id = json_extract(f.metadata_json, '$.scaleId')
        WHERE f.id = ?
        """,
        (movie_id,),
    ).fetchone()
    if not row:
        historical = conn.execute(
            """
            SELECT mh.*, g.name AS genre_name, s.name AS scale_name
            FROM movies_historical mh
            LEFT JOIN genres g ON g.id = mh.genre_id
            LEFT JOIN project_scales s ON s.id = mh.scale_id
            WHERE mh.id = ?
            """,
            (movie_id,),
        ).fetchone()
        if not historical:
            return None
        data = dict(historical)
        effects = loads_json(data.get("effects_json"), {})
        return {
            "id": data["id"],
            "title": data["title"],
            "typeLabel": "한국영화 개봉 기록",
            "releaseLabel": _year_month(data.get("release_year"), data.get("release_month")),
            "genreName": data.get("genre_name") or data.get("genre_id"),
            "scaleName": data.get("scale_name") or data.get("scale_id"),
            "audience": int(data.get("actual_audience") or data.get("expected_audience") or 0),
            "description": effects.get("description") or "게임 내 시간 기준으로 이미 발생한 한국영화 개봉 기록입니다.",
            "sourceNote": "한국영화 역사 데이터",
        }
    data = dict(row)
    metadata = loads_json(data.get("metadata_json"), {})
    cast = _names_from_any(metadata.get("actors") or metadata.get("cast") or metadata.get("actorNames"))
    return {
        "id": data["id"],
        "title": data["title"],
        "typeLabel": "한국영화 개봉 기록",
        "releaseLabel": _year_month(data.get("release_year"), data.get("release_month")),
        "genreName": data.get("genre_name") or metadata.get("genreName") or metadata.get("genreId"),
        "scaleName": data.get("scale_name") or metadata.get("scaleName") or metadata.get("scaleId"),
        "productionBudget": _optional_int(metadata.get("productionBudget")),
        "marketingBudget": _optional_int(metadata.get("marketingBudget")),
        "totalCost": _optional_int(metadata.get("totalCost")),
        "directorText": data.get("director_name") or metadata.get("directorName"),
        "castText": ", ".join(cast[:8]),
        "distributorText": metadata.get("distributor") or metadata.get("distributionCompany"),
        "audience": _optional_int(metadata.get("actualAudience") or metadata.get("expectedAudience")),
        "grossRevenue": _optional_int(metadata.get("grossRevenue")),
        "breakEvenAudience": _optional_int(metadata.get("breakEvenAudience")),
        "profit": _optional_int(metadata.get("profit")),
        "scoreText": _score_text(metadata.get("audienceScore"), metadata.get("criticScore")),
        "publicEvaluation": metadata.get("publicEvaluation") or "게임 내 시간 기준으로 이미 발생한 주요 한국영화 기록입니다.",
        "description": metadata.get("description") or metadata.get("summary") or "게임 내 역사 데이터에 등록된 작품입니다.",
        "sourceNote": "한국영화 역사 데이터",
    }


def _foreign_history_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM history_foreign_events WHERE id = ?", (movie_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    effects = loads_json(data.get("effects_json"), {})
    return {
        "id": data["id"],
        "title": data.get("title_ko") or data.get("title") or data.get("title_en"),
        "typeLabel": "외화 대작 개봉 기록",
        "releaseLabel": _year_month(data.get("year"), data.get("month")),
        "genreName": ", ".join(_names_from_any(loads_json(data.get("genre_json"), []))),
        "audience": _optional_int(effects.get("expected_audience")),
        "publicEvaluation": f"{data.get('impact_grade') or '-'}급 시장 충격으로 동시기 개봉작의 스크린 확보와 관객 기대치에 영향을 줍니다.",
        "description": data.get("description") or "실제 개봉 시기에 맞춰 등장하는 외화 대작입니다.",
        "sourceNote": "외화 고정 이벤트 데이터",
    }


def _market_release_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.*, g.name AS genre_name, s.name AS scale_name
        FROM market_releases r
        LEFT JOIN genres g ON g.id = r.genre_id
        LEFT JOIN project_scales s ON s.id = r.scale_id
        WHERE r.id = ?
        """,
        (movie_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    metadata = loads_json(data.get("effects_json"), {})
    origin = str(data.get("origin") or "")
    release_day = metadata.get("releaseDay")
    if release_day:
        release_label = f"{data.get('release_year')}년 {data.get('release_month')}월 {release_day}일"
    else:
        release_label = _year_month(data.get("release_year"), data.get("release_month"))
    return {
        "id": data["id"],
        "title": data["title"],
        "typeLabel": _market_release_type_label(origin),
        "releaseLabel": release_label,
        "genreName": data.get("genre_name") or metadata.get("genreName"),
        "scaleName": data.get("scale_name") or metadata.get("scaleName"),
        "productionPeriod": f"극장 상영 {metadata.get('runDays') or '기록'}일 창",
        "directorText": metadata.get("directorName"),
        "castText": ", ".join(_names_from_any(metadata.get("actorNames") or [])),
        "distributorText": metadata.get("distributionCompany") or metadata.get("productionCompany"),
        "audience": _optional_int(data.get("actual_audience") or data.get("expected_audience")),
        "publicEvaluation": (
            f"시장 예측은 {metadata.get('audienceBand') or '집계 중'}입니다. "
            f"{_market_release_public_context(origin)}"
        ),
        "description": metadata.get("description") or "게임 내 감독과 배우가 자동 활동으로 만든 경쟁작입니다.",
        "sourceNote": metadata.get("sourceNote") or "게임 내 시장 생성 데이터",
    }


def _market_release_type_label(origin: str) -> str:
    if origin == "historical_domestic":
        return "한국영화 역사 개봉작"
    if origin == "protected_domestic":
        return "주요 필모그래피 개봉작"
    if origin == "foreign_fixed":
        return "외화 대작 개봉 기록"
    return "게임 내 경쟁작"


def _market_release_public_context(origin: str) -> str:
    if origin in {"historical_domestic", "protected_domestic"}:
        return "게임 내 역사 흐름에 따라 실제로 극장 시장에 등장한 작품입니다."
    if origin == "foreign_fixed":
        return "실제 한국 개봉 시기에 맞춰 스크린과 관객 관심을 압박하는 외화 대작입니다."
    return "플레이어 작품과 같은 달의 스크린, 관객 관심, 입소문을 두고 경쟁합니다."


def _kobis_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    detail = conn.execute(
        """
        SELECT *
        FROM staging_kobis_movie_details
        WHERE movie_code = ?
        """,
        (movie_id,),
    ).fetchone()
    yearly = conn.execute(
        """
        SELECT *
        FROM staging_kobis_yearly_boxoffice
        WHERE movie_code = ?
        ORDER BY audience_count DESC
        LIMIT 1
        """,
        (movie_id,),
    ).fetchone()
    listing = None
    if not detail:
        listing = conn.execute(
            "SELECT * FROM staging_kobis_movie_list WHERE movie_code = ?",
            (movie_id,),
        ).fetchone()
    if not detail and not listing and not yearly:
        return None
    data = dict(detail or listing or {})
    yearly_data = dict(yearly or {})
    companies = loads_json(data.get("companies_json"), [])
    return {
        "id": movie_id,
        "title": data.get("movie_name_ko") or yearly_data.get("movie_name") or movie_id,
        "typeLabel": "KOBIS 영화 정보",
        "releaseLabel": data.get("open_date") or yearly_data.get("open_date") or "미정",
        "genreName": _join_names(loads_json(data.get("genres_json"), [])) or data.get("representative_genre") or data.get("genre_alt"),
        "scaleName": "실제 영화",
        "directorText": _join_names(loads_json(data.get("directors_json"), [])),
        "castText": _join_names(_first_n(loads_json(data.get("actors_json"), []), 8)),
        "distributorText": _company_by_role(companies, ("배급", "distribution")),
        "audience": _optional_int(yearly_data.get("audience_count")),
        "grossRevenue": _optional_int(yearly_data.get("sales_amount")),
        "publicEvaluation": _public_evaluation(
            audience=int(yearly_data.get("audience_count") or 0),
            break_even=0,
            profit=None,
            audience_score=None,
        ),
        "description": "KOBIS에서 수집한 실제 영화 기본 정보와 박스오피스 참고 기록입니다.",
        "sourceNote": "KOBIS 수집 데이터",
    }


def _kmdb_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM staging_kmdb_movies WHERE kmdb_id = ?", (movie_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    return {
        "id": data["kmdb_id"],
        "title": data.get("title_ko") or data.get("title_en") or data["kmdb_id"],
        "typeLabel": "KMDb 영화 정보",
        "releaseLabel": data.get("release_date") or str(data.get("prod_year") or ""),
        "genreName": data.get("genre"),
        "scaleName": "실제 영화",
        "directorText": ", ".join(_names_from_any(loads_json(data.get("director_names_json"), []))),
        "castText": ", ".join(_names_from_any(loads_json(data.get("actor_names_json"), []))[:8]),
        "distributorText": data.get("distribution_company"),
        "description": data.get("plot") or "KMDb에서 수집한 영화 기본 정보입니다.",
        "sourceNote": "KMDb 수집 데이터",
    }


def _wikidata_movie_detail(conn: Any, movie_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM wikidata_movies WHERE qid = ?", (movie_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    return {
        "id": data["qid"],
        "title": data.get("title_ko") or data.get("title_en") or data["qid"],
        "typeLabel": "Wikidata 보조 정보",
        "releaseLabel": data.get("release_date") or str(data.get("year") or ""),
        "genreName": _join_names(loads_json(data.get("genre_json"), [])),
        "scaleName": "실제 영화",
        "directorText": _join_names(loads_json(data.get("director_json"), [])),
        "castText": _join_names(_first_n(loads_json(data.get("actor_json"), []), 8)),
        "description": "Wikidata에서 가져온 보조 영화 정보입니다. KOBIS/KMDb와 충돌하면 공식 수집 데이터를 우선합니다.",
        "sourceNote": "Wikidata 보조 데이터",
    }


def _project_people_text(conn: Any, project_id: str | None, roles: set[str]) -> str:
    if not project_id:
        return ""
    rows = conn.execute(
        """
        SELECT pp.role, p.name_ko, pp.person_id
        FROM project_people pp
        LEFT JOIN people p ON p.id = pp.person_id
        WHERE pp.project_id = ? AND pp.role IN ({})
        ORDER BY pp.role, p.name_ko
        """.format(",".join("?" for _ in roles)),
        (project_id, *sorted(roles)),
    ).fetchall()
    return ", ".join(str(row["name_ko"] or row["person_id"]) for row in rows)


def _project_distributor_text(conn: Any, project_id: str | None) -> str:
    if not project_id:
        return ""
    row = conn.execute(
        """
        SELECT pd.*, o.name_ko
        FROM project_distribution pd
        LEFT JOIN organizations o ON o.id = pd.distributor_id
        WHERE pd.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if not row:
        return ""
    data = dict(row)
    base = data.get("name_ko") or data.get("distributor_id") or "배급사 미정"
    deal = f" · {data.get('deal_type')}" if data.get("deal_type") else ""
    return f"{base}{deal}"


def _project_location_text(conn: Any, project_id: str | None) -> str:
    if not project_id:
        return ""
    rows = conn.execute(
        """
        SELECT location_name, location_type, cost_impact, duration_delta_days
        FROM project_location_plans
        WHERE project_id = ?
        ORDER BY created_at, id
        """,
        (project_id,),
    ).fetchall()
    if not rows:
        return ""
    parts = []
    for row in rows:
        extra = []
        if int(row["cost_impact"] or 0):
            extra.append(f"추가 {money(row['cost_impact'])}")
        if int(row["duration_delta_days"] or 0):
            extra.append(f"일정 +{int(row['duration_delta_days'])}일")
        suffix = f" ({', '.join(extra)})" if extra else ""
        parts.append(f"{row['location_name']} · {row['location_type']}{suffix}")
    return ", ".join(parts)


def _production_period(conn: Any, project_id: str | None) -> str:
    if not project_id:
        return ""
    rows = conn.execute(
        """
        SELECT year, month, day, end_year, end_month, end_day
        FROM calendar_events
        WHERE project_id = ?
        ORDER BY year, month, day
        """,
        (project_id,),
    ).fetchall()
    if not rows:
        return ""
    starts = []
    ends = []
    for row in rows:
        starts.append(_date_or_none(row["year"], row["month"], row["day"]))
        ends.append(_date_or_none(row["end_year"] or row["year"], row["end_month"] or row["month"], row["end_day"] or row["day"]))
    starts = [item for item in starts if item]
    ends = [item for item in ends if item]
    if not starts or not ends:
        return ""
    start = min(starts)
    end = max(ends)
    days = max(0, (end - start).days)
    return f"{start.year}.{start.month:02d}.{start.day:02d} ~ {end.year}.{end.month:02d}.{end.day:02d} · {days}일"


def _date_or_none(year: Any, month: Any, day: Any) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def _score_text(audience_score: Any, critic_score: Any) -> str:
    parts = []
    if audience_score is not None:
        parts.append(audience_reaction_text(audience_score))
    if critic_score is not None:
        parts.append(critic_reaction_text(critic_score))
    return " · ".join(parts)


def _public_evaluation(
    *,
    audience: int,
    break_even: int,
    profit: Any,
    audience_score: Any,
) -> str:
    score = int(float(audience_score)) if audience_score is not None else None
    profit_value = int(profit) if profit is not None else None
    if score is not None and score >= 80 and (profit_value is None or profit_value >= 0):
        return "관객 만족도가 높고 흥행 흐름도 안정적인 편입니다."
    if profit_value is not None and profit_value > 0 and (not break_even or audience >= break_even):
        return "손익분기점을 넘기며 제작사에 실질적인 회수 성과를 남겼습니다."
    if break_even and audience and audience < break_even:
        return "관객 반응과 별개로 손익분기점에는 미치지 못한 기록입니다."
    if score is not None and score < 50:
        return "관객 반응이 엇갈리며 장기 흥행에는 부담이 있는 편입니다."
    if audience >= 5_000_000:
        return "동시대 시장에서 강한 대중적 존재감을 만든 작품입니다."
    if audience > 0:
        return "제한된 시장 반응을 확인할 수 있는 작품입니다."
    return "아직 충분한 공개 성과가 집계되지 않았습니다."


def _company_by_role(companies: list[Any], role_markers: tuple[str, ...]) -> str:
    for item in companies:
        if not isinstance(item, dict):
            continue
        roles = " ".join(str(value) for value in item.values())
        if any(marker.lower() in roles.lower() for marker in role_markers):
            name = item.get("companyNm") or item.get("nameKo") or item.get("name") or item.get("companyCd")
            if name:
                return str(name)
    return ""


def _join_names(items: list[Any]) -> str:
    return ", ".join(_names_from_any(items))


def _first_n(value: Any, count: int) -> list[Any]:
    if isinstance(value, list):
        return value[:count]
    if isinstance(value, dict):
        return [value]
    if value:
        return [value]
    return []


def _names_from_any(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        name = (
            value.get("nameKo")
            or value.get("name_ko")
            or value.get("name")
            or value.get("peopleNm")
            or value.get("directorNm")
            or value.get("actorNm")
            or value.get("label")
            or value.get("title")
        )
        return [str(name)] if name else []
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            for name in _names_from_any(item):
                if name and name not in names:
                    names.append(name)
        return names
    return []


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _number(value: Any) -> str:
    if value is None:
        return "미집계"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _year_month(year: Any, month: Any) -> str:
    if not year:
        return "미정"
    if month:
        return f"{int(year)}년 {int(month)}월"
    return f"{int(year)}년"


def _unknown_detail(movie_id: str) -> dict[str, Any]:
    return {
        "id": movie_id,
        "title": movie_id or "작품 정보 없음",
        "typeLabel": "미등록 작품",
        "description": "아직 이 작품에 연결된 상세 데이터가 없습니다.",
        "publicEvaluation": "데이터가 연결되면 관객 수, 손익, 제작 정보가 표시됩니다.",
    }
