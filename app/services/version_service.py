from __future__ import annotations

import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp


VERSION_LABELS = {
    "theatrical_cut": "극장판",
    "director_cut": "감독판",
    "ott_cut": "OTT판",
}

VERSION_STATUS_LABELS = {
    "planned": "준비 중",
    "selected": "선택됨",
    "released": "공개됨",
    "held": "보류",
}

BASE_RUNTIME_BY_SCALE = {
    "scale_short": 18,
    "scale_independent": 92,
    "scale_low_budget_genre": 100,
    "scale_mid_commercial": 112,
    "scale_large_commercial": 125,
    "scale_tentpole": 138,
    "short_film": 18,
    "independent_film": 92,
    "low_budget_genre": 100,
    "mid_commercial": 112,
    "large_commercial": 125,
    "tentpole_blockbuster": 138,
}


def initialize_project_versions(conn: Any, project_id: str, scale_id: str, genre_id: str) -> None:
    existing = conn.execute(
        "SELECT COUNT(*) AS count FROM project_versions WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if int(existing["count"] or 0) > 0:
        return
    base_runtime = BASE_RUNTIME_BY_SCALE.get(scale_id, 105)
    templates = (
        {
            "version_type": "theatrical_cut",
            "name": "극장판",
            "status": "selected",
            "runtime_minutes": base_runtime,
            "quality_delta": 0,
            "audience_delta": 3,
            "critic_delta": 0,
            "secondary_market_delta": 0,
            "selected_for_theatrical": 1,
            "selected_for_ott": 0,
            "description": "개봉 첫 주 관객과 상영 회차를 의식해 리듬을 다듬은 판본.",
        },
        {
            "version_type": "director_cut",
            "name": "감독판",
            "status": "planned",
            "runtime_minutes": base_runtime + 12,
            "quality_delta": 3,
            "audience_delta": -3,
            "critic_delta": 5,
            "secondary_market_delta": 2,
            "selected_for_theatrical": 0,
            "selected_for_ott": 0,
            "description": "감독의 의도와 인물 감정선을 더 오래 남기는 판본.",
        },
        {
            "version_type": "ott_cut",
            "name": "OTT판",
            "status": "planned",
            "runtime_minutes": base_runtime + (6 if scale_id != "scale_short" else 0),
            "quality_delta": 1,
            "audience_delta": -2,
            "critic_delta": 1,
            "secondary_market_delta": 9,
            "selected_for_theatrical": 0,
            "selected_for_ott": 1 if _ott_friendly_scale(scale_id, genre_id) else 0,
            "description": "극장 이후 플랫폼 시청 지속성과 알고리즘 추천을 의식한 판본.",
        },
    )
    for template in templates:
        conn.execute(
            """
            INSERT INTO project_versions (
                id, project_id, version_type, name, status, runtime_minutes,
                quality_delta, audience_delta, critic_delta, secondary_market_delta,
                selected_for_theatrical, selected_for_ott, description, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"version_{uuid.uuid4().hex[:10]}",
                project_id,
                template["version_type"],
                template["name"],
                template["status"],
                template["runtime_minutes"],
                template["quality_delta"],
                template["audience_delta"],
                template["critic_delta"],
                template["secondary_market_delta"],
                template["selected_for_theatrical"],
                template["selected_for_ott"],
                template["description"],
                dumps_json({"genreId": genre_id, "scaleId": scale_id}),
            ),
        )


def get_project_versions(project_id: str, conn: Any | None = None) -> list[dict[str, Any]]:
    def _load(active_conn: Any) -> list[dict[str, Any]]:
        rows = active_conn.execute(
            """
            SELECT *
            FROM project_versions
            WHERE project_id = ?
            ORDER BY
                CASE version_type
                    WHEN 'theatrical_cut' THEN 1
                    WHEN 'director_cut' THEN 2
                    WHEN 'ott_cut' THEN 3
                    ELSE 9
                END
            """,
            (project_id,),
        ).fetchall()
        return [_version_from_row(dict(row)) for row in rows]

    if conn is not None:
        return _load(conn)
    with get_connection() as active_conn:
        return _load(active_conn)


def apply_version_effects(conn: Any, project_id: str, effects: dict[str, Any]) -> None:
    if not effects:
        return
    selected_theatrical = effects.get("selectTheatrical") or effects.get("selectedTheatrical")
    selected_ott = effects.get("selectOtt") or effects.get("selectedOtt")
    if selected_theatrical:
        _select_version(conn, project_id, str(selected_theatrical), target="theatrical")
    if selected_ott:
        _select_version(conn, project_id, str(selected_ott), target="ott")
    adjustments = effects.get("adjustments") or {}
    if isinstance(adjustments, dict):
        for version_type, values in adjustments.items():
            if isinstance(values, dict):
                _adjust_version(conn, project_id, str(version_type), values)


def apply_release_version_modifiers(
    conn: Any,
    project_id: str,
    stats: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    versions = get_project_versions(project_id, conn=conn)
    if not versions:
        return dict(stats), {}
    theatrical = next((item for item in versions if item.get("selectedForTheatrical")), None)
    ott = next((item for item in versions if item.get("selectedForOtt")), None)
    adjusted = dict(stats)
    if theatrical:
        _apply_theatrical_modifiers(adjusted, theatrical)
    if ott:
        _apply_ott_modifiers(adjusted, ott)
    profile = {
        "theatrical": theatrical,
        "ott": ott,
        "summary": _version_summary(theatrical, ott),
    }
    adjusted["release_version_profile"] = profile
    adjusted["release_version_name"] = theatrical.get("name") if theatrical else ""
    adjusted["ott_version_name"] = ott.get("name") if ott else ""
    return adjusted, profile


def record_released_versions(conn: Any, project_id: str, film_id: str, final_result: dict[str, Any]) -> None:
    versions = get_project_versions(project_id, conn=conn)
    for version in versions:
        status = "released" if version.get("selectedForTheatrical") or version.get("selectedForOtt") else version.get("status")
        metrics = loads_json(version.get("metricsJson"), {})
        metrics.update(
            {
                "filmId": film_id,
                "finalAudience": final_result.get("final_audience"),
                "profit": final_result.get("profit"),
                "releasedAsTheatrical": bool(version.get("selectedForTheatrical")),
                "releasedAsOtt": bool(version.get("selectedForOtt")),
            }
        )
        conn.execute(
            """
            UPDATE project_versions
            SET film_id = ?, status = ?, metrics_json = ?
            WHERE id = ?
            """,
            (film_id, status, dumps_json(metrics), version["id"]),
        )


def version_text(versions: list[dict[str, Any]]) -> str:
    if not versions:
        return "판본 기록 없음"
    parts = []
    for version in versions:
        targets = []
        if version.get("selectedForTheatrical"):
            targets.append("극장")
        if version.get("selectedForOtt"):
            targets.append("OTT")
        target_text = f" · 선택: {', '.join(targets)}" if targets else ""
        parts.append(
            f"{version['name']}({version['statusLabel']}, {version['runtimeMinutes']}분{target_text})"
        )
    return " / ".join(parts)


def _select_version(conn: Any, project_id: str, version_type: str, *, target: str) -> None:
    column = "selected_for_theatrical" if target == "theatrical" else "selected_for_ott"
    conn.execute(f"UPDATE project_versions SET {column} = 0 WHERE project_id = ?", (project_id,))
    conn.execute(
        f"""
        UPDATE project_versions
        SET {column} = 1,
            status = CASE WHEN status = 'planned' THEN 'selected' ELSE status END
        WHERE project_id = ? AND version_type = ?
        """,
        (project_id, version_type),
    )


def _adjust_version(conn: Any, project_id: str, version_type: str, values: dict[str, Any]) -> None:
    fields = []
    params: list[Any] = []
    field_map = {
        "qualityDelta": "quality_delta",
        "audienceDelta": "audience_delta",
        "criticDelta": "critic_delta",
        "secondaryMarketDelta": "secondary_market_delta",
        "runtimeMinutes": "runtime_minutes",
        "status": "status",
        "description": "description",
    }
    for source_key, column in field_map.items():
        if source_key in values:
            fields.append(f"{column} = ?")
            params.append(values[source_key])
    if not fields:
        return
    params.extend([project_id, version_type])
    conn.execute(
        f"UPDATE project_versions SET {', '.join(fields)} WHERE project_id = ? AND version_type = ?",
        params,
    )


def _apply_theatrical_modifiers(stats: dict[str, Any], version: dict[str, Any]) -> None:
    quality = int(version.get("qualityDelta", 0) or 0)
    audience = int(version.get("audienceDelta", 0) or 0)
    critic = int(version.get("criticDelta", 0) or 0)
    stats["directing_quality"] = clamp(float(stats.get("directing_quality", 50)) + quality * 0.45)
    stats["editing_quality"] = clamp(float(stats.get("editing_quality", 50)) + quality * 0.55)
    stats["artistic_sense"] = clamp(float(stats.get("artistic_sense", 50)) + critic * 0.8)
    stats["pre_release_interest"] = clamp(float(stats.get("pre_release_interest", 50)) + audience)
    stats["genre_satisfaction"] = clamp(float(stats.get("genre_satisfaction", 50)) + audience * 0.25)
    stats["audience_rejection_risk"] = clamp(float(stats.get("audience_rejection_risk", 20)) - audience * 0.45)
    stats["critic_backlash_risk"] = clamp(float(stats.get("critic_backlash_risk", 20)) - critic * 0.35)


def _apply_ott_modifiers(stats: dict[str, Any], version: dict[str, Any]) -> None:
    secondary = int(version.get("secondaryMarketDelta", 0) or 0)
    audience = int(version.get("audienceDelta", 0) or 0)
    stats["secondary_market_fit"] = clamp(float(stats.get("secondary_market_fit", 50)) + secondary)
    stats["online_buzz"] = clamp(float(stats.get("online_buzz", 40)) + max(0, secondary // 3))
    if audience < 0:
        stats["theatrical_ott_cannibalization"] = abs(audience)


def _version_from_row(row: dict[str, Any]) -> dict[str, Any]:
    version_type = str(row.get("version_type") or "")
    status = str(row.get("status") or "planned")
    return {
        "id": row.get("id"),
        "projectId": row.get("project_id"),
        "filmId": row.get("film_id"),
        "versionType": version_type,
        "name": row.get("name") or VERSION_LABELS.get(version_type, version_type),
        "status": status,
        "statusLabel": VERSION_STATUS_LABELS.get(status, status),
        "runtimeMinutes": int(row.get("runtime_minutes") or 0),
        "qualityDelta": int(row.get("quality_delta") or 0),
        "audienceDelta": int(row.get("audience_delta") or 0),
        "criticDelta": int(row.get("critic_delta") or 0),
        "secondaryMarketDelta": int(row.get("secondary_market_delta") or 0),
        "selectedForTheatrical": bool(row.get("selected_for_theatrical")),
        "selectedForOtt": bool(row.get("selected_for_ott")),
        "description": row.get("description") or "",
        "metricsJson": row.get("metrics_json"),
    }


def _version_summary(theatrical: dict[str, Any] | None, ott: dict[str, Any] | None) -> str:
    if theatrical and ott:
        if theatrical["versionType"] == ott["versionType"]:
            return f"{theatrical['name']}을 극장과 OTT의 기준 판본으로 삼았다."
        return f"극장은 {theatrical['name']}, 2차 시장은 {ott['name']} 중심으로 운영한다."
    if theatrical:
        return f"{theatrical['name']}을 개봉 기준 판본으로 삼았다."
    if ott:
        return f"{ott['name']}을 플랫폼 공개 기준 판본으로 준비했다."
    return "판본 전략이 아직 확정되지 않았다."


def _ott_friendly_scale(scale_id: str, genre_id: str) -> bool:
    return scale_id in {
        "scale_independent",
        "scale_low_budget_genre",
        "independent_film",
        "low_budget_genre",
    } or genre_id in {
        "genre_horror_occult",
        "genre_romance_melodrama",
        "genre_indie_art",
        "horror_occult",
        "romance_melodrama",
        "indie_art",
    }
