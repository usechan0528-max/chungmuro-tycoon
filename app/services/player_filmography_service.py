from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json


def get_player_filmography_state() -> dict[str, Any]:
    refresh_player_filmography_records()
    records = list_player_filmography_records()
    return {
        "summary": _archive_summary(records),
        "films": records,
        "failures": [record for record in records if record.get("failureRecord", {}).get("isFailure")],
        "reevaluations": [
            record for record in records
            if record.get("reevaluation", {}).get("events") or record.get("reevaluation", {}).get("metrics")
        ],
        "franchises": [
            record for record in records
            if record.get("franchise", {}).get("ip") or record.get("franchise", {}).get("entries")
        ],
    }


def list_player_filmography_records() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, g.name AS genre_name, s.name AS scale_name
            FROM player_filmography_records r
            LEFT JOIN genres g ON g.id = r.genre_id
            LEFT JOIN project_scales s ON s.id = r.scale_id
            ORDER BY r.release_year DESC, r.release_month DESC, r.title
            """
        ).fetchall()
    return [_record_from_row(dict(row)) for row in rows]


def refresh_player_filmography_records() -> int:
    with get_connection() as conn:
        films = conn.execute(
            """
            SELECT film.*, box.gross_revenue AS box_gross_revenue,
                   box.profit, box.secondary_market_revenue,
                   box.break_even_audience AS box_break_even_audience,
                   movie.metadata_json, g.name AS genre_name, s.name AS scale_name
            FROM completed_films film
            LEFT JOIN movies_boxoffice box ON box.movie_id = film.id
            LEFT JOIN movies movie ON movie.id = film.id
            LEFT JOIN genres g ON g.id = film.genre_id
            LEFT JOIN project_scales s ON s.id = film.scale_id
            ORDER BY film.release_year, film.release_month, film.title
            """
        ).fetchall()
        count = 0
        for film_row in films:
            record = _build_record(conn, dict(film_row))
            _upsert_record(conn, record)
            count += 1
        conn.commit()
        return count


def refresh_player_filmography_record(film_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        film = conn.execute(
            """
            SELECT film.*, box.gross_revenue AS box_gross_revenue,
                   box.profit, box.secondary_market_revenue,
                   box.break_even_audience AS box_break_even_audience,
                   movie.metadata_json, g.name AS genre_name, s.name AS scale_name
            FROM completed_films film
            LEFT JOIN movies_boxoffice box ON box.movie_id = film.id
            LEFT JOIN movies movie ON movie.id = film.id
            LEFT JOIN genres g ON g.id = film.genre_id
            LEFT JOIN project_scales s ON s.id = film.scale_id
            WHERE film.id = ?
            """,
            (film_id,),
        ).fetchone()
        if not film:
            return None
        record = _build_record(conn, dict(film))
        _upsert_record(conn, record)
        conn.commit()
        return record


def _build_record(conn: Any, film: dict[str, Any]) -> dict[str, Any]:
    project_id = _project_id(film)
    collaborations = _collaborations(conn, project_id)
    awards = _awards(conn, film["id"])
    reviews = _reviews(conn, film["id"])
    reevaluation = _reevaluation(conn, film["id"])
    franchise = _franchise(conn, film["id"])
    profit = int(film.get("profit") if film.get("profit") is not None else 0)
    audience = int(film.get("final_audience") or 0)
    break_even = int(film.get("box_break_even_audience") or film.get("break_even_audience") or 0)
    failure_record = _failure_record(film, profit, audience, break_even)
    summary = {
        "releaseLabel": f"{film.get('release_year')}년 {film.get('release_month')}월",
        "genreName": film.get("genre_name"),
        "scaleName": film.get("scale_name"),
        "projectId": project_id,
        "hasAwards": bool(awards),
        "hasReviews": bool(reviews),
        "hasReevaluation": bool(reevaluation["events"] or reevaluation["metrics"]),
        "hasFranchise": bool(franchise["ip"] or franchise["entries"]),
        "statusLabel": _status_label(failure_record, awards, reevaluation, franchise),
    }
    return {
        "filmId": film["id"],
        "title": film["title"],
        "releaseYear": film.get("release_year"),
        "releaseMonth": film.get("release_month"),
        "genreId": film.get("genre_id"),
        "genreName": film.get("genre_name"),
        "scaleId": film.get("scale_id"),
        "scaleName": film.get("scale_name"),
        "audience": audience,
        "grossRevenue": int(film.get("box_gross_revenue") or film.get("gross_revenue") or 0),
        "profit": profit,
        "breakEvenAudience": break_even,
        "audienceScore": int(film.get("audience_score") or 0),
        "criticScore": int(film.get("critic_score") or 0),
        "awards": awards,
        "reviews": reviews,
        "collaborations": collaborations,
        "failureRecord": failure_record,
        "reevaluation": reevaluation,
        "franchise": franchise,
        "summary": summary,
    }


def _upsert_record(conn: Any, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO player_filmography_records (
            film_id, title, release_year, release_month, genre_id, scale_id,
            audience, gross_revenue, profit, break_even_audience,
            audience_score, critic_score, awards_json, reviews_json,
            collaborations_json, failure_record_json, reevaluation_json,
            franchise_json, summary_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            record["filmId"],
            record["title"],
            record["releaseYear"],
            record["releaseMonth"],
            record["genreId"],
            record["scaleId"],
            record["audience"],
            record["grossRevenue"],
            record["profit"],
            record["breakEvenAudience"],
            record["audienceScore"],
            record["criticScore"],
            dumps_json(record["awards"]),
            dumps_json(record["reviews"]),
            dumps_json(record["collaborations"]),
            dumps_json(record["failureRecord"]),
            dumps_json(record["reevaluation"]),
            dumps_json(record["franchise"]),
            dumps_json(record["summary"]),
        ),
    )


def _record_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "filmId": row["film_id"],
        "title": row["title"],
        "releaseYear": row.get("release_year"),
        "releaseMonth": row.get("release_month"),
        "genreId": row.get("genre_id"),
        "genreName": row.get("genre_name"),
        "scaleId": row.get("scale_id"),
        "scaleName": row.get("scale_name"),
        "audience": int(row.get("audience") or 0),
        "grossRevenue": int(row.get("gross_revenue") or 0),
        "profit": int(row.get("profit") or 0),
        "breakEvenAudience": int(row.get("break_even_audience") or 0),
        "audienceScore": int(row.get("audience_score") or 0),
        "criticScore": int(row.get("critic_score") or 0),
        "awards": loads_json(row.get("awards_json"), []),
        "reviews": loads_json(row.get("reviews_json"), []),
        "collaborations": loads_json(row.get("collaborations_json"), []),
        "failureRecord": loads_json(row.get("failure_record_json"), {}),
        "reevaluation": loads_json(row.get("reevaluation_json"), {"events": [], "metrics": []}),
        "franchise": loads_json(row.get("franchise_json"), {"ip": None, "entries": []}),
        "summary": loads_json(row.get("summary_json"), {}),
        "updatedAt": row.get("updated_at"),
    }


def _project_id(film: dict[str, Any]) -> str | None:
    metadata = loads_json(film.get("metadata_json"), {})
    return metadata.get("projectId") if isinstance(metadata, dict) else None


def _collaborations(conn: Any, project_id: str | None) -> list[dict[str, Any]]:
    if not project_id:
        return []
    rows = conn.execute(
        """
        SELECT pp.*, p.name_ko, p.name_en, p.type
        FROM project_people pp
        LEFT JOIN people p ON p.id = pp.person_id
        WHERE pp.project_id = ?
        ORDER BY pp.role, p.name_ko
        """,
        (project_id,),
    ).fetchall()
    collaborations = []
    for row in rows:
        data = dict(row)
        collaborations.append(
            {
                "personId": data.get("person_id"),
                "nameKo": data.get("name_ko") or data.get("person_id"),
                "nameEn": data.get("name_en"),
                "type": data.get("type"),
                "role": data.get("role"),
                "status": data.get("status"),
            }
        )
    return collaborations


def _awards(conn: Any, film_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ma.*, COALESCE(a.name, ma.award_id) AS award_name
        FROM movies_awards ma
        LEFT JOIN awards a ON a.id = ma.award_id
        WHERE ma.movie_id = ?
        ORDER BY ma.year, award_name, ma.category
        """,
        (film_id,),
    ).fetchall()
    return [
        {
            "awardId": row["award_id"],
            "awardName": row["award_name"],
            "year": row["year"],
            "category": row["category"],
            "result": row["result"],
        }
        for row in rows
    ]


def _reviews(conn: Any, film_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, c.name_ko AS critic_name
        FROM movies_reviews r
        LEFT JOIN critics c ON c.id = r.critic_id
        WHERE r.movie_id = ?
        ORDER BY r.id
        """,
        (film_id,),
    ).fetchall()
    return [
        {
            "criticId": row["critic_id"],
            "criticName": row["critic_name"] or row["critic_id"] or row["source_type"],
            "sourceType": row["source_type"],
            "score": row["score"],
            "quote": row["quote"],
        }
        for row in rows
    ]


def _reevaluation(conn: Any, film_id: str) -> dict[str, list[dict[str, Any]]]:
    events = conn.execute(
        """
        SELECT *
        FROM reevaluation_events
        WHERE film_id = ?
        ORDER BY year, month, id
        """,
        (film_id,),
    ).fetchall()
    metrics = conn.execute(
        """
        SELECT *
        FROM movies_post_release_metrics
        WHERE movie_id = ? AND (
            metric_type LIKE '%reevaluation%'
            OR metric_type LIKE '%cult%'
            OR metric_type LIKE '%rediscovery%'
            OR metric_type LIKE '%late%'
            OR metric_type IN ('online_buzz', 'secondary_market_revenue')
        )
        ORDER BY year, month, id
        """,
        (film_id,),
    ).fetchall()
    return {
        "events": [
            {
                "year": row["year"],
                "month": row["month"],
                "triggerType": row["trigger_type"],
                "buzzDelta": row["buzz_delta"],
                "reputationDelta": row["reputation_delta"],
                "summary": row["summary"],
            }
            for row in events
        ],
        "metrics": [
            {
                "metricType": row["metric_type"],
                "year": row["year"],
                "month": row["month"],
                "value": row["value"],
                "summary": row["summary"],
            }
            for row in metrics
        ],
    }


def _franchise(conn: Any, film_id: str) -> dict[str, Any]:
    ip = conn.execute(
        """
        SELECT *
        FROM intellectual_properties
        WHERE origin_film_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (film_id,),
    ).fetchone()
    entries = conn.execute(
        """
        SELECT *
        FROM ip_entries
        WHERE film_id = ? OR ip_id IN (
            SELECT id FROM intellectual_properties WHERE origin_film_id = ?
        )
        ORDER BY year, month, sequence_no
        """,
        (film_id, film_id),
    ).fetchall()
    return {
        "ip": _ip_record(dict(ip)) if ip else None,
        "entries": [
            {
                "ipId": row["ip_id"],
                "filmId": row["film_id"],
                "entryType": row["entry_type"],
                "sequenceNo": row["sequence_no"],
                "year": row["year"],
                "month": row["month"],
                "result": loads_json(row["result_json"], {}),
            }
            for row in entries
        ],
    }


def _ip_record(ip: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": ip["id"],
        "title": ip["title"],
        "ipType": ip["ip_type"],
        "ipValue": ip["ip_value"],
        "franchisePower": ip["franchise_power"],
        "sequelDemand": ip["sequel_demand"],
        "cultPotential": ip["cult_potential"],
        "reevaluationPotential": ip["reevaluation_potential"],
        "status": ip["status"],
    }


def _failure_record(film: dict[str, Any], profit: int, audience: int, break_even: int) -> dict[str, Any]:
    reasons = []
    if profit < 0:
        reasons.append("손익 적자")
    if break_even and audience < break_even:
        reasons.append("손익분기 관객 미달")
    if int(film.get("audience_score") or 0) < 45:
        reasons.append("관객 반응 부진")
    if int(film.get("critic_score") or 0) < 45:
        reasons.append("평론 반응 부진")
    severity = "none"
    if len(reasons) >= 3 or profit <= -2_000_000_000:
        severity = "major"
    elif reasons:
        severity = "normal"
    return {
        "isFailure": bool(reasons),
        "severity": severity,
        "reasons": reasons,
        "lossAmount": abs(profit) if profit < 0 else 0,
    }


def _status_label(
    failure_record: dict[str, Any],
    awards: list[dict[str, Any]],
    reevaluation: dict[str, list[dict[str, Any]]],
    franchise: dict[str, Any],
) -> str:
    if franchise.get("ip"):
        return "시리즈/IP 후보"
    if reevaluation.get("events") or reevaluation.get("metrics"):
        return "역주행/재평가 기록"
    if awards:
        return "수상/후보 기록"
    if failure_record.get("isFailure"):
        return "실패작 기록"
    return "개봉작"


def _archive_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_audience = sum(record.get("audience", 0) for record in records)
    total_profit = sum(record.get("profit", 0) for record in records)
    award_count = sum(len(record.get("awards", [])) for record in records)
    return {
        "filmCount": len(records),
        "totalAudience": total_audience,
        "totalProfit": total_profit,
        "awardCount": award_count,
        "failureCount": sum(1 for record in records if record.get("failureRecord", {}).get("isFailure")),
        "reevaluationCount": sum(
            1 for record in records
            if record.get("reevaluation", {}).get("events") or record.get("reevaluation", {}).get("metrics")
        ),
        "franchiseCount": sum(1 for record in records if record.get("franchise", {}).get("ip")),
    }
