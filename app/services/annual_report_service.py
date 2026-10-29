from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.database import dumps_json, get_connection, loads_json


KOREA_MARKERS = ("한국", "대한민국", "south korea", "republic of korea", "korea")


def build_and_store_annual_report(year: int) -> dict[str, Any]:
    report = build_annual_report(year)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO industry_yearly_reports (
                year, top_boxoffice_json, korean_share_json, foreign_hits_json,
                actors_of_year_json, directors_of_year_json, award_highlights_json,
                production_company_rankings_json, distributor_share_json,
                genre_trends_json, source_summary_json, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                year,
                dumps_json(report["topBoxoffice"]),
                dumps_json(report["koreanFilmShare"]),
                dumps_json(report["foreignHits"]),
                dumps_json(report["actorsOfYear"]),
                dumps_json(report["directorsOfYear"]),
                dumps_json(report["awardHighlights"]),
                dumps_json(report["productionCompanyRankings"]),
                dumps_json(report["distributorShare"]),
                dumps_json(report["genreTrends"]),
                dumps_json(report["sourceSummary"]),
            ),
        )
        conn.commit()
    return report


def build_annual_report(year: int) -> dict[str, Any]:
    with get_connection() as conn:
        rows = _load_boxoffice_rows(conn, year)
        previous_rows = _load_boxoffice_rows(conn, year - 1)
        award_highlights = _load_award_highlights(conn, year)
        yearly_totals = _load_yearly_totals(conn, year)
        kofic_metrics = _load_kofic_metrics(conn, year)

    ranked_rows = sorted(rows, key=lambda row: row["audience"], reverse=True)
    top_boxoffice = [_public_movie_row(row, rank) for rank, row in enumerate(ranked_rows[:10], start=1)]
    foreign_hits = [
        _public_movie_row(row, rank)
        for rank, row in enumerate([item for item in ranked_rows if item["origin"] == "foreign"][:10], start=1)
    ]
    korean_share = _build_korean_share(ranked_rows, yearly_totals, kofic_metrics)
    actor_rankings = _rank_people(ranked_rows, "actors")
    director_rankings = _rank_people(ranked_rows, "directors")
    production_company_rankings = _rank_companies(ranked_rows, role="production")
    distributor_share = _rank_companies(ranked_rows, role="distribution")
    genre_trends = _build_genre_trends(ranked_rows, previous_rows)
    source_summary = _source_summary(rows, yearly_totals, award_highlights, kofic_metrics)

    return {
        "year": year,
        "topBoxoffice": top_boxoffice,
        "koreanFilmShare": korean_share,
        "foreignHits": foreign_hits,
        "actorsOfYear": actor_rankings,
        "directorsOfYear": director_rankings,
        "awardHighlights": award_highlights,
        "productionCompanyRankings": production_company_rankings,
        "distributorShare": distributor_share,
        "genreTrends": genre_trends,
        "sourceSummary": source_summary,
    }


def list_annual_reports() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM industry_yearly_reports
            ORDER BY year DESC
            """
        ).fetchall()
    reports = []
    for row in rows:
        report = _stored_report(dict(row))
        reports.append(_with_report_summary(report))
    return reports


def get_annual_report(year: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM industry_yearly_reports WHERE year = ?",
            (year,),
        ).fetchone()
    return _stored_report(dict(row)) if row else None


def list_report_source_years() -> list[int]:
    years: set[int] = set()
    with get_connection() as conn:
        for table, column in (
            ("staging_kobis_yearly_boxoffice", "year"),
            ("staging_major_korean_movies", "representative_year"),
            ("staging_kobis_yearly_totals", "year"),
            ("staging_kofic_industry_metrics", "report_year"),
            ("history_award_results", "year"),
            ("staging_award_records", "event_year"),
        ):
            for row in conn.execute(f"SELECT DISTINCT {column} AS year FROM {table} WHERE {column} IS NOT NULL"):
                years.add(int(row["year"]))
    return sorted(years)


def _stored_report(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "year": int(row["year"]),
        "topBoxoffice": loads_json(row.get("top_boxoffice_json"), []),
        "koreanFilmShare": loads_json(row.get("korean_share_json"), {}),
        "foreignHits": loads_json(row.get("foreign_hits_json"), []),
        "actorsOfYear": loads_json(row.get("actors_of_year_json"), []),
        "directorsOfYear": loads_json(row.get("directors_of_year_json"), []),
        "awardHighlights": loads_json(row.get("award_highlights_json"), []),
        "productionCompanyRankings": loads_json(row.get("production_company_rankings_json"), []),
        "distributorShare": loads_json(row.get("distributor_share_json"), []),
        "genreTrends": loads_json(row.get("genre_trends_json"), []),
        "sourceSummary": loads_json(row.get("source_summary_json"), {}),
        "generatedAt": row.get("generated_at"),
    }


def _with_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    top = report.get("topBoxoffice") or []
    actors = report.get("actorsOfYear") or []
    directors = report.get("directorsOfYear") or []
    share = report.get("koreanFilmShare") or {}
    report["summary"] = {
        "topFilm": top[0]["title"] if top else None,
        "actorOfYear": actors[0]["name"] if actors else None,
        "directorOfYear": directors[0]["name"] if directors else None,
        "koreanAudienceShare": share.get("audienceShare"),
    }
    return report


def _load_boxoffice_rows(conn: Any, year: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT y.*, d.movie_name_en, d.nations_json, d.genres_json,
               d.directors_json, d.actors_json, d.companies_json,
               m.country AS major_country, m.distributor AS major_distributor
        FROM staging_kobis_yearly_boxoffice y
        LEFT JOIN staging_kobis_movie_details d ON d.movie_code = y.movie_code
        LEFT JOIN staging_major_korean_movies m ON (
            m.source_movie_code = y.movie_code
            OR (m.normalized_title = y.normalized_title AND m.representative_year = y.year)
        )
        WHERE y.year = ?
        ORDER BY y.audience_count DESC
        """,
        (year,),
    ).fetchall()
    parsed = [_parse_boxoffice_row(dict(row)) for row in rows]
    if parsed:
        return parsed

    fallback = conn.execute(
        """
        SELECT *
        FROM staging_major_korean_movies
        WHERE representative_year = ?
        ORDER BY max_annual_audience DESC
        """,
        (year,),
    ).fetchall()
    return [_parse_major_movie_row(dict(row), year) for row in fallback]


def _parse_boxoffice_row(row: dict[str, Any]) -> dict[str, Any]:
    nations = _json_list(row.get("nations_json"))
    genres = _json_list(row.get("genres_json"))
    directors = _json_list(row.get("directors_json"))
    actors = _json_list(row.get("actors_json"))
    companies = _json_list(row.get("companies_json"))
    distributor = _first_company_name(companies, ("배급", "distribution")) or row.get("major_distributor")
    country_text = " ".join(_names_from_items(nations) + [row.get("major_country") or ""])
    return {
        "movieCode": row.get("movie_code"),
        "title": row.get("movie_name") or row.get("movie_name_ko"),
        "titleEn": row.get("movie_name_en"),
        "year": int(row["year"]),
        "openDate": row.get("open_date"),
        "sales": int(row.get("sales_amount") or 0),
        "audience": int(row.get("audience_count") or 0),
        "screenCount": int(row.get("screen_count") or 0),
        "showCount": int(row.get("show_count") or 0),
        "origin": "domestic" if _looks_korean(country_text) else "foreign" if country_text else "unknown",
        "countries": _names_from_items(nations) or ([row["major_country"]] if row.get("major_country") else []),
        "genres": _names_from_items(genres, preferred_keys=("genreNm", "genreName", "name")),
        "directors": _people_from_items(directors),
        "actors": _people_from_items(actors),
        "companies": _companies_from_items(companies),
        "distributor": distributor,
        "source": "kobis_yearly_boxoffice",
    }


def _parse_major_movie_row(row: dict[str, Any], year: int) -> dict[str, Any]:
    return {
        "movieCode": row.get("source_movie_code"),
        "title": row.get("title"),
        "titleEn": None,
        "year": year,
        "openDate": row.get("release_date"),
        "sales": _gross_text_to_int(row.get("max_annual_gross_text")),
        "audience": int(row.get("max_annual_audience") or 0),
        "screenCount": int(row.get("max_annual_screens") or 0),
        "showCount": 0,
        "origin": "domestic" if _looks_korean(row.get("country")) else "unknown",
        "countries": [row.get("country")] if row.get("country") else [],
        "genres": [],
        "directors": [],
        "actors": [],
        "companies": [],
        "distributor": row.get("distributor"),
        "source": row.get("source", "staging_major_korean_movies"),
    }


def _load_yearly_totals(conn: Any, year: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM staging_kobis_yearly_totals WHERE year = ?",
        (year,),
    ).fetchone()
    if row:
        return dict(row)
    market_row = conn.execute(
        """
        SELECT year, total_revenue AS total_sales, total_audience, source_file AS source_type
        FROM market_yearly_stats
        WHERE year = ?
        """,
        (year,),
    ).fetchone()
    return dict(market_row) if market_row else None


def _load_kofic_metrics(conn: Any, year: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM staging_kofic_industry_metrics
        WHERE report_year = ?
        ORDER BY confidence DESC, metric_category, metric_id
        """,
        (year,),
    ).fetchall()
    return [dict(row) for row in rows]


def _load_award_highlights(conn: Any, year: int) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    rows = conn.execute(
        """
        SELECT r.*, COALESCE(a.name, r.award_id) AS award_name
        FROM history_award_results r
        LEFT JOIN awards a ON a.id = r.award_id
        WHERE r.year = ?
        ORDER BY award_name, category
        """,
        (year,),
    ).fetchall()
    for row in rows:
        data = dict(row)
        highlights.append(
            {
                "award": data.get("award_name"),
                "category": data.get("category"),
                "result": data.get("result"),
                "movieId": data.get("movie_id"),
                "personName": None,
                "source": "history_award_results",
            }
        )

    staged = conn.execute(
        """
        SELECT *
        FROM staging_award_records
        WHERE event_year = ?
        ORDER BY award_name, category, result_type
        """,
        (year,),
    ).fetchall()
    for row in staged:
        data = dict(row)
        highlights.append(
            {
                "award": data.get("award_name"),
                "category": data.get("category"),
                "result": data.get("result_type"),
                "movieTitle": data.get("movie_title"),
                "personName": data.get("person_name"),
                "source": "staging_award_records",
            }
        )

    events = conn.execute(
        """
        SELECT *
        FROM historical_events
        WHERE year = ? AND type LIKE 'award%'
        ORDER BY month, title
        """,
        (year,),
    ).fetchall()
    for row in events:
        data = dict(row)
        highlights.append(
            {
                "award": data.get("title"),
                "category": data.get("type"),
                "result": data.get("fixed_level"),
                "movieTitle": None,
                "personName": None,
                "source": "historical_events",
            }
        )
    return highlights[:30]


def _build_korean_share(
    rows: list[dict[str, Any]],
    yearly_totals: dict[str, Any] | None,
    kofic_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    domestic_audience = sum(row["audience"] for row in rows if row["origin"] == "domestic")
    domestic_sales = sum(row["sales"] for row in rows if row["origin"] == "domestic")
    foreign_audience = sum(row["audience"] for row in rows if row["origin"] == "foreign")
    foreign_sales = sum(row["sales"] for row in rows if row["origin"] == "foreign")
    covered_audience = sum(row["audience"] for row in rows)
    covered_sales = sum(row["sales"] for row in rows)
    total_audience = int(yearly_totals["total_audience"]) if yearly_totals else covered_audience
    total_sales = int(yearly_totals["total_sales"]) if yearly_totals else covered_sales

    metric_hint = _find_share_metric(kofic_metrics)
    audience_share = _ratio(domestic_audience, total_audience)
    sales_share = _ratio(domestic_sales, total_sales)
    if metric_hint is not None and audience_share is None:
        audience_share = metric_hint

    return {
        "domesticAudience": domestic_audience,
        "foreignAudience": foreign_audience,
        "totalAudience": total_audience,
        "coveredAudience": covered_audience,
        "domesticSales": domestic_sales,
        "foreignSales": foreign_sales,
        "totalSales": total_sales,
        "coveredSales": covered_sales,
        "audienceShare": audience_share,
        "salesShare": sales_share,
        "source": "kobis_yearly_totals" if yearly_totals else "kobis_yearly_boxoffice_rows",
        "metricHint": metric_hint,
    }


def _rank_people(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for row in rows:
        for person in row.get(key, []):
            name = person.get("nameKo") or person.get("nameEn") or person.get("name")
            if not name:
                continue
            person_key = person.get("id") or name
            bucket = scores.setdefault(
                person_key,
                {
                    "id": person.get("id"),
                    "name": name,
                    "nameEn": person.get("nameEn"),
                    "audienceScore": 0,
                    "works": [],
                },
            )
            bucket["audienceScore"] += row["audience"]
            bucket["works"].append({"title": row["title"], "audience": row["audience"]})
    ranked = sorted(scores.values(), key=lambda item: item["audienceScore"], reverse=True)
    for rank, item in enumerate(ranked[:10], start=1):
        item["rank"] = rank
        item["works"] = sorted(item["works"], key=lambda work: work["audience"], reverse=True)[:5]
    return ranked[:10]


def _rank_companies(rows: list[dict[str, Any]], *, role: str) -> list[dict[str, Any]]:
    role_markers = ("제작", "production") if role == "production" else ("배급", "distribution")
    scores: dict[str, dict[str, Any]] = {}
    for row in rows:
        companies = [
            company for company in row.get("companies", [])
            if _company_matches_role(company, role_markers)
        ]
        if role == "distribution" and not companies and row.get("distributor"):
            companies = [{"name": row["distributor"], "roles": ["배급"]}]
        for company in companies:
            name = company.get("name")
            if not name:
                continue
            bucket = scores.setdefault(name, {"name": name, "audience": 0, "sales": 0, "works": []})
            bucket["audience"] += row["audience"]
            bucket["sales"] += row["sales"]
            bucket["works"].append({"title": row["title"], "audience": row["audience"]})
    ranked = sorted(scores.values(), key=lambda item: (item["audience"], item["sales"]), reverse=True)
    total_audience = sum(item["audience"] for item in ranked)
    for rank, item in enumerate(ranked[:10], start=1):
        item["rank"] = rank
        item["audienceShare"] = _ratio(item["audience"], total_audience)
        item["works"] = sorted(item["works"], key=lambda work: work["audience"], reverse=True)[:5]
    return ranked[:10]


def _build_genre_trends(
    rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current = _genre_stats(rows)
    previous = _genre_stats(previous_rows)
    total = sum(item["audience"] for item in current.values())
    previous_total = sum(item["audience"] for item in previous.values())
    trends = []
    for genre, item in current.items():
        current_share = _ratio(item["audience"], total) or 0
        previous_share = _ratio(previous.get(genre, {}).get("audience", 0), previous_total) or 0
        trends.append(
            {
                "genre": genre,
                "audience": item["audience"],
                "filmCount": item["filmCount"],
                "audienceShare": current_share,
                "previousAudienceShare": previous_share,
                "shareDelta": round(current_share - previous_share, 4),
            }
        )
    return sorted(trends, key=lambda item: (item["shareDelta"], item["audience"]), reverse=True)[:10]


def _genre_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"audience": 0, "filmCount": 0})
    for row in rows:
        genres = row.get("genres") or ["장르 미상"]
        for genre in genres:
            stats[genre]["audience"] += row["audience"]
            stats[genre]["filmCount"] += 1
    return dict(stats)


def _source_summary(
    rows: list[dict[str, Any]],
    yearly_totals: dict[str, Any] | None,
    award_highlights: list[dict[str, Any]],
    kofic_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    sources = sorted({row.get("source") for row in rows if row.get("source")})
    has_partial_sources = bool(rows or yearly_totals or award_highlights or kofic_metrics)
    return {
        "boxofficeRows": len(rows),
        "sources": sources,
        "hasYearlyTotals": yearly_totals is not None,
        "awardRows": len(award_highlights),
        "koficMetricRows": len(kofic_metrics),
        "precision": "high" if rows and yearly_totals else "partial" if has_partial_sources else "empty",
    }


def _public_movie_row(row: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "movieCode": row.get("movieCode"),
        "title": row.get("title"),
        "titleEn": row.get("titleEn"),
        "openDate": row.get("openDate"),
        "origin": row.get("origin"),
        "audience": row.get("audience", 0),
        "sales": row.get("sales", 0),
        "screenCount": row.get("screenCount", 0),
        "distributor": row.get("distributor"),
        "genres": row.get("genres", []),
    }


def _json_list(value: Any) -> list[Any]:
    parsed = loads_json(value, [])
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _names_from_items(items: list[Any], preferred_keys: tuple[str, ...] = ()) -> list[str]:
    keys = preferred_keys + (
        "nameKo",
        "name_ko",
        "peopleNm",
        "companyNm",
        "nationNm",
        "genreNm",
        "name",
        "label",
    )
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = next((str(item[key]) for key in keys if item.get(key)), "")
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def _people_from_items(items: list[Any]) -> list[dict[str, str | None]]:
    people = []
    for item in items:
        if isinstance(item, str):
            people.append({"id": None, "nameKo": item, "nameEn": None, "name": item})
            continue
        if not isinstance(item, dict):
            continue
        name_ko = item.get("peopleNm") or item.get("nameKo") or item.get("name_ko") or item.get("name")
        name_en = item.get("peopleNmEn") or item.get("nameEn") or item.get("name_en")
        if name_ko or name_en:
            people.append(
                {
                    "id": item.get("peopleCd") or item.get("id") or item.get("qid"),
                    "nameKo": name_ko,
                    "nameEn": name_en,
                    "name": name_ko or name_en,
                }
            )
    return people


def _companies_from_items(items: list[Any]) -> list[dict[str, Any]]:
    companies = []
    for item in items:
        if isinstance(item, str):
            companies.append({"name": item, "roles": []})
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("companyNm") or item.get("nameKo") or item.get("name")
        if not name:
            continue
        roles = item.get("companyPartNames") or item.get("roles") or item.get("role") or []
        if isinstance(roles, str):
            roles = [part.strip() for part in roles.replace("/", ",").split(",") if part.strip()]
        companies.append({"name": name, "roles": roles, "id": item.get("companyCd") or item.get("id")})
    return companies


def _first_company_name(companies: list[Any], role_markers: tuple[str, ...]) -> str | None:
    for company in _companies_from_items(companies):
        if _company_matches_role(company, role_markers):
            return str(company.get("name"))
    return None


def _company_matches_role(company: dict[str, Any], role_markers: tuple[str, ...]) -> bool:
    role_text = " ".join(str(role).lower() for role in company.get("roles", []))
    return any(marker.lower() in role_text for marker in role_markers)


def _looks_korean(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in KOREA_MARKERS)


def _gross_text_to_int(value: Any) -> int:
    text = str(value or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits or 0)


def _ratio(value: float | int, total: float | int) -> float | None:
    if not total:
        return None
    return round(float(value) / float(total), 4)


def _find_share_metric(metrics: list[dict[str, Any]]) -> float | None:
    for metric in metrics:
        text = f"{metric.get('metric_id')} {metric.get('metric_name')} {metric.get('scope')}".lower()
        if ("점유" in text or "share" in text) and ("한국" in text or "korean" in text):
            value = metric.get("value")
            if value is None:
                continue
            number = float(value)
            return round(number / 100, 4) if number > 1 else round(number, 4)
    return None
