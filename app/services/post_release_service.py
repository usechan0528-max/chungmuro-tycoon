from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp


IP_EFFECT_KEYS = {"ip_value", "franchise_power", "world_expansion", "character_popularity", "sequel_demand"}


def list_post_release_metrics(movie_id: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM movies_post_release_metrics"
    params: list[str] = []
    if movie_id:
        query += " WHERE movie_id = ?"
        params.append(movie_id)
    query += " ORDER BY year DESC, month DESC, id DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    metrics: list[dict[str, Any]] = []
    for row in rows:
        metric = dict(row)
        metric["effects"] = loads_json(metric.pop("effects_json"), {})
        metrics.append(metric)
    return metrics


def apply_post_release_events_for_month(year: int, month: int) -> list[str]:
    applied: list[str] = []
    with get_connection() as conn:
        events = _load_post_release_events(conn)
        if not events:
            return applied
        films = conn.execute(
            """
            SELECT * FROM completed_films
            ORDER BY release_year, release_month, id
            """
        ).fetchall()
        for film_row in films:
            film = dict(film_row)
            context = _post_release_context(conn, film, year, month)
            for event in events:
                event_key = f"post_release_applied_{event['id']}_{film['id']}"
                already_applied = conn.execute(
                    "SELECT 1 FROM save_event_flags WHERE key = ?",
                    (event_key,),
                ).fetchone()
                if already_applied or not _trigger_matches(event.get("trigger", {}), context):
                    continue
                _apply_post_release_event(conn, film, context, event, year, month)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO save_event_flags (
                        key, value_json, updated_year, updated_month
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (event_key, dumps_json({"applied": True}), year, month),
                )
                applied.append(f"{film['id']}:{event['id']}")
        conn.commit()
    return applied


def _load_post_release_events(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM simulation_events
        WHERE category = 'post_release'
        ORDER BY weight DESC, id
        """
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        choice_data = loads_json(row["choices_json"], {})
        effects = choice_data.get("effects", {}) if isinstance(choice_data, dict) else {}
        events.append(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "trigger": loads_json(row["trigger_json"], {}),
                "effects": effects,
            }
        )
    return events


def _post_release_context(conn: Any, film: dict[str, Any], year: int, month: int) -> dict[str, Any]:
    metrics = {
        row["metric_type"]: int(row["value"] or 0)
        for row in conn.execute(
            "SELECT metric_type, value FROM movies_post_release_metrics WHERE movie_id = ?",
            (film["id"],),
        ).fetchall()
    }
    ip = conn.execute(
        "SELECT * FROM intellectual_properties WHERE origin_film_id = ? ORDER BY id LIMIT 1",
        (film["id"],),
    ).fetchone()
    months_after_release = max(
        0,
        (year - int(film["release_year"] or year)) * 12 + (month - int(film["release_month"] or month)),
    )
    context = {
        "film_id": film["id"],
        "final_audience": int(film["final_audience"] or 0),
        "years_after_release": months_after_release // 12,
        "cult_potential": int(metrics.get("cult_potential", metrics.get("franchise_seed", 0))),
        "meme_potential": int(metrics.get("meme_potential", 0)),
        "secondary_market_fit": int(metrics.get("secondary_market_fit", 0)),
        "available_on_ott": bool(metrics.get("available_on_ott", 0)),
        "ip": dict(ip) if ip else None,
    }
    return context


def _trigger_matches(trigger: dict[str, Any], context: dict[str, Any]) -> bool:
    if context["years_after_release"] < int(trigger.get("minYearsAfterRelease", 0) or 0):
        return False
    if context["cult_potential"] < int(trigger.get("minCultPotential", 0) or 0):
        return False
    if context["meme_potential"] < int(trigger.get("minMemePotential", 0) or 0):
        return False
    if context["secondary_market_fit"] < int(trigger.get("minSecondaryMarketFit", 0) or 0):
        return False
    if trigger.get("availableOnOtt") is True and not context["available_on_ott"]:
        return False
    return True


def _apply_post_release_event(
    conn: Any,
    film: dict[str, Any],
    context: dict[str, Any],
    event: dict[str, Any],
    year: int,
    month: int,
) -> None:
    effects = event.get("effects", {})
    player = conn.execute("SELECT reputation_json FROM player_state WHERE id = 1").fetchone()
    reputation = loads_json(player["reputation_json"], {}) if player else {}
    metric_value = 0
    ip_effects: dict[str, int] = {}
    for key, value in effects.items():
        amount = int(value)
        if key == "public_reputation":
            reputation[key] = clamp(int(reputation.get(key, 0) or 0) + amount)
        elif key == "secondary_market_revenue":
            _add_secondary_market_revenue(conn, film["id"], amount, year, month)
            metric_value += amount
        elif key in IP_EFFECT_KEYS:
            ip_effects[key] = amount
            _apply_ip_effect(conn, context.get("ip"), key, amount)
        else:
            _upsert_metric(conn, film["id"], key, year, month, amount, event["title"], {event["id"]: amount})
            metric_value += amount
    if player:
        conn.execute(
            "UPDATE player_state SET reputation_json = ? WHERE id = 1",
            (dumps_json(reputation),),
        )
    conn.execute(
        """
        INSERT INTO reevaluation_events (
            film_id, year, month, trigger_type, buzz_delta,
            reputation_delta, summary, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            film["id"],
            year,
            month,
            event["id"],
            int(effects.get("online_buzz", 0) or 0),
            int(effects.get("public_reputation", 0) or 0),
            event["description"],
            dumps_json(effects),
        ),
    )
    conn.execute(
        """
        INSERT INTO systems_post_release (
            movie_id, event_type, year, month, summary, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (film["id"], event["id"], year, month, event["description"], dumps_json(effects)),
    )
    conn.execute(
        """
        INSERT INTO movies_post_release_metrics (
            movie_id, metric_type, year, month, value, summary, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            film["id"],
            event["id"],
            year,
            month,
            metric_value,
            event["title"],
            dumps_json({"effects": effects, "ipEffects": ip_effects}),
        ),
    )
    conn.execute(
        """
        INSERT INTO news_items (
            year, month, title, body, source_type, target_type, target_id, effects_json
        ) VALUES (?, ?, ?, ?, 'post_release', 'film', ?, ?)
        """,
        (year, month, event["title"], event["description"], film["id"], dumps_json(effects)),
    )


def _upsert_metric(
    conn: Any,
    movie_id: str,
    metric_type: str,
    year: int,
    month: int,
    delta: int,
    summary: str,
    effects: dict[str, Any],
) -> None:
    latest = conn.execute(
        """
        SELECT value FROM movies_post_release_metrics
        WHERE movie_id = ? AND metric_type = ?
        ORDER BY year DESC, month DESC, id DESC
        LIMIT 1
        """,
        (movie_id, metric_type),
    ).fetchone()
    value = int(latest["value"] or 0) + delta if latest else delta
    conn.execute(
        """
        INSERT INTO movies_post_release_metrics (
            movie_id, metric_type, year, month, value, summary, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (movie_id, metric_type, year, month, value, summary, dumps_json(effects)),
    )


def _add_secondary_market_revenue(conn: Any, movie_id: str, amount: int, year: int, month: int) -> None:
    row = conn.execute(
        "SELECT secondary_market_revenue FROM movies_boxoffice WHERE movie_id = ?",
        (movie_id,),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE movies_boxoffice
            SET secondary_market_revenue = secondary_market_revenue + ?,
                profit = profit + ?
            WHERE movie_id = ?
            """,
            (amount, amount, movie_id),
        )
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if studio:
        from app.services.finance_service import apply_studio_delta

        apply_studio_delta(conn, studio, {"cash": amount})
    _upsert_metric(
        conn,
        movie_id,
        "secondary_market_revenue",
        year,
        month,
        amount,
        "2차 시장 추가 수익",
        {"secondary_market_revenue": amount},
    )


def _apply_ip_effect(conn: Any, ip: dict[str, Any] | None, key: str, amount: int) -> None:
    if not ip:
        return
    current = conn.execute(
        "SELECT * FROM intellectual_properties WHERE id = ?",
        (ip["id"],),
    ).fetchone()
    if current:
        ip = dict(current)
    metadata = loads_json(ip.get("metadata_json"), {})
    if key == "ip_value":
        conn.execute(
            "UPDATE intellectual_properties SET ip_value = ? WHERE id = ?",
            (clamp(int(ip.get("ip_value") or 0) + amount), ip["id"]),
        )
        conn.execute(
            "UPDATE systems_franchise SET ip_value = ? WHERE id = ?",
            (clamp(int(ip.get("ip_value") or 0) + amount), ip["id"]),
        )
    else:
        metadata[key] = clamp(int(metadata.get(key, 0) or 0) + amount)
        conn.execute(
            "UPDATE intellectual_properties SET metadata_json = ? WHERE id = ?",
            (dumps_json(metadata), ip["id"]),
        )
        conn.execute(
            "UPDATE systems_franchise SET metadata_json = ? WHERE id = ?",
            (dumps_json(metadata), ip["id"]),
        )
