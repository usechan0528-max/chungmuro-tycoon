from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json


SOURCE_LABELS = {
    "historical": "산업",
    "protected_history": "개봉",
    "foreign_fixed": "외화",
    "press": "언론",
    "future": "미래 시장",
    "market": "시장",
    "policy": "정책",
    "distribution": "배급",
    "theater": "극장",
    "premium_format": "특별관",
    "finance": "재무",
    "npc_release": "개봉",
}

HISTORICAL_POPUP_SOURCES = (
    "historical",
    "protected_history",
    "foreign_fixed",
    "policy",
    "market",
    "distribution",
    "theater",
    "premium_format",
)


def list_news_feed(
    *,
    limit: int = 12,
    until_year: int | None = None,
    until_month: int | None = None,
    until_day: int | None = None,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if until_year is None or until_month is None or until_day is None:
            player = conn.execute(
                "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
            ).fetchone()
            if player:
                until_year = int(player["current_year"])
                until_month = int(player["current_month"])
                until_day = int(player["current_day"] or 1)

        params: list[Any] = []
        where = ""
        if until_year is not None and until_month is not None and until_day is not None:
            where = """
                WHERE year < ?
                   OR (year = ? AND month < ?)
                   OR (year = ? AND month = ? AND COALESCE(day, 1) <= ?)
            """
            params = [until_year, until_year, until_month, until_year, until_month, until_day]

        rows = conn.execute(
            f"""
            SELECT id, year, month, COALESCE(day, 1) AS day, title, body,
                   source_type, target_type, target_id,
                   COALESCE(importance, 50) AS importance,
                   reaction_json, popup_seen, effects_json
            FROM news_items
            {where}
            ORDER BY year DESC, month DESC, COALESCE(day, 1) DESC,
                     COALESCE(importance, 50) DESC, id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

    feed: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        effects = loads_json(item.get("effects_json"), {})
        reactions = loads_json(item.get("reaction_json"), [])
        if not isinstance(reactions, list) or not reactions:
            reactions = build_reactions(item, effects)
        item["effects"] = effects
        item["reactions"] = reactions
        item["source_label"] = SOURCE_LABELS.get(str(item.get("source_type")), str(item.get("source_type") or "소식"))
        feed.append(item)
    return feed


def create_news_item(
    *,
    year: int,
    month: int,
    day: int = 1,
    title: str,
    body: str = "",
    source_type: str = "market",
    target_type: str | None = None,
    target_id: str | None = None,
    effects: dict[str, Any] | None = None,
    importance: int = 50,
    reactions: list[dict[str, str]] | None = None,
) -> None:
    effects = effects or {}
    reactions = reactions or build_reactions(
        {
            "title": title,
            "body": body,
            "source_type": source_type,
            "target_type": target_type,
        },
        effects,
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO news_items (
                year, month, day, title, body, source_type, target_type,
                target_id, importance, reaction_json, effects_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                year,
                month,
                day,
                title,
                body,
                source_type,
                target_type,
                target_id,
                importance,
                dumps_json(reactions),
                dumps_json(effects),
            ),
        )
        conn.commit()


def list_pending_history_popups(limit: int = 12) -> list[dict[str, Any]]:
    with get_connection() as conn:
        player = conn.execute(
            "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
        ).fetchone()
        if not player:
            return []
        year = int(player["current_year"])
        month = int(player["current_month"])
        day = int(player["current_day"] or 1)
        placeholders = ", ".join("?" for _ in HISTORICAL_POPUP_SOURCES)
        rows = conn.execute(
            f"""
            SELECT id, year, month, COALESCE(day, 1) AS day, title, body,
                   source_type, target_type, target_id,
                   COALESCE(importance, 50) AS importance,
                   reaction_json, popup_seen, effects_json
            FROM news_items
            WHERE COALESCE(popup_seen, 0) = 0
              AND source_type IN ({placeholders})
              AND (
                    year < ?
                 OR (year = ? AND month < ?)
                 OR (year = ? AND month = ? AND COALESCE(day, 1) <= ?)
              )
            ORDER BY year, month, COALESCE(day, 1), COALESCE(importance, 50) DESC, id
            LIMIT ?
            """,
            (*HISTORICAL_POPUP_SOURCES, year, year, month, year, month, day, int(limit)),
        ).fetchall()

    popups: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        effects = loads_json(item.get("effects_json"), {})
        reactions = loads_json(item.get("reaction_json"), [])
        if not isinstance(reactions, list) or not reactions:
            reactions = build_reactions(item, effects)
        item["effects"] = effects
        item["reactions"] = reactions
        item["source_label"] = SOURCE_LABELS.get(str(item.get("source_type")), str(item.get("source_type") or "역사"))
        popups.append(item)
    return popups


def mark_history_popups_seen(news_ids: list[int]) -> None:
    ids = [int(news_id) for news_id in news_ids if news_id is not None]
    if not ids:
        return
    placeholders = ", ".join("?" for _ in ids)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE news_items SET popup_seen = 1 WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()


def build_reactions(news: dict[str, Any], effects: Any) -> list[dict[str, str]]:
    flattened = _flatten_numeric_effects(effects)
    source = str(news.get("source_type") or "")
    title = str(news.get("title") or "")
    body = str(news.get("body") or "")
    text = f"{title} {body}"

    reactions: list[dict[str, str]] = []
    positive_total = sum(value for value in flattened.values() if value > 0)
    negative_total = sum(abs(value) for value in flattened.values() if value < 0)

    if source == "foreign_fixed" or "외화" in title:
        reactions.extend(
            [
                {
                    "group": "극장가",
                    "tone": "긴장",
                    "text": "극장 관계자들은 특별관과 대형 스크린이 외화 쪽으로 먼저 묶일 가능성을 보고 있다.",
                },
                {
                    "group": "제작자들",
                    "tone": "경계",
                    "text": "비슷한 장르의 한국영화는 개봉 시기와 마케팅 문구를 다시 점검해야 한다는 분위기다.",
                },
            ]
        )
    elif source == "protected_history" or "주요 한국영화" in title:
        reactions.extend(
            [
                {
                    "group": "관객",
                    "tone": "관심",
                    "text": "영화 팬들은 새 한국영화가 시장 분위기를 바꿀 수 있을지 지켜보는 중이다.",
                },
                {
                    "group": "업계",
                    "tone": "분석",
                    "text": "동시기 개봉작들은 관객층이 겹치는지, 편승할 수 있는 홍보 포인트가 있는지 계산하고 있다.",
                },
            ]
        )
    elif source == "press":
        if any(key in text for key in ("돌파", "호평", "흥행", "관심")) and negative_total <= positive_total:
            reactions.extend(
                [
                    {
                        "group": "관객",
                        "tone": "긍정",
                        "text": "개봉 후 반응을 보고 극장으로 움직이겠다는 관객이 조금씩 늘고 있다.",
                    },
                    {
                        "group": "투자자",
                        "tone": "안도",
                        "text": "투자자들은 손실 방어 가능성과 차기작 협상력을 함께 보고 있다.",
                    },
                ]
            )
        else:
            reactions.extend(
                [
                    {
                        "group": "관객",
                        "tone": "유보",
                        "text": "관객들은 후기와 주변 반응을 더 확인한 뒤 예매하겠다는 쪽으로 기운다.",
                    },
                    {
                        "group": "투자자",
                        "tone": "불안",
                        "text": "투자 쪽에서는 남은 상영 기간과 2차 시장 회수 가능성을 따지는 분위기다.",
                    },
                ]
            )

    if _has_positive(flattened, ("public_reputation", "theater_demand", "korean_film_trust", "online_buzz")):
        reactions.append(
            {
                "group": "관객",
                "tone": "긍정",
                "text": "한국영화 쪽에 다시 기대를 걸어볼 만하다는 반응이 나온다.",
            }
        )
    if _has_positive(flattened, ("investment_access", "investor_reputation", "blockbuster_confidence")):
        reactions.append(
            {
                "group": "투자자",
                "tone": "관망",
                "text": "투자사들은 비슷한 기획의 제안서를 조금 더 적극적으로 검토하려는 분위기다.",
            }
        )
    if _has_positive(flattened, ("critic_reputation", "festival_strategy_value", "festival_network", "auteur_commercial_hybrid_value")):
        reactions.append(
            {
                "group": "평론가",
                "tone": "호의",
                "text": "평론가와 영화제 관계자들은 작품성 있는 장르영화의 가능성을 다시 언급하고 있다.",
            }
        )
    if _has_positive(flattened, ("ott_power", "global_streaming_sale", "secondary_market_revenue")):
        reactions.append(
            {
                "group": "플랫폼",
                "tone": "탐색",
                "text": "OTT와 2차 시장 관계자들은 극장 이후의 수익 창구를 더 중요하게 보고 있다.",
            }
        )
    if _has_negative_or_risk(
        flattened,
        (
            "foreign_competition",
            "screen_access_difficulty",
            "middle_budget_risk",
            "ticket_price_burden",
            "press_backlash_risk",
            "controversy_risk",
            "distribution_difficulty",
        ),
    ):
        reactions.append(
            {
                "group": "제작자들",
                "tone": "우려",
                "text": "현장에서는 작은 작품과 중간 규모 영화가 버티기 더 어려워질 수 있다는 말이 돈다.",
            }
        )

    if "코로나" in text or "극장 위기" in text:
        reactions.append(
            {
                "group": "관객",
                "tone": "위축",
                "text": "극장 방문을 미루거나 플랫폼 공개를 기다리겠다는 반응이 눈에 띄게 늘었다.",
            }
        )
    if "시상" in text or "수상" in text or "칸" in text or "아카데미" in text:
        reactions.append(
            {
                "group": "업계",
                "tone": "고무",
                "text": "해외 평가가 투자와 캐스팅 협상에도 영향을 줄 수 있다는 기대가 커진다.",
            }
        )

    if not reactions:
        reactions = [
            {
                "group": "관객",
                "tone": "관망",
                "text": "아직은 큰 움직임보다 주변 반응을 지켜보겠다는 분위기다.",
            },
            {
                "group": "업계",
                "tone": "분석",
                "text": "업계는 이 소식이 다음 개봉 일정과 투자 판단에 어떤 영향을 줄지 계산하고 있다.",
            },
        ]

    return _dedupe_reactions(reactions)[:4]


def _flatten_numeric_effects(value: Any, prefix: str = "") -> dict[str, float]:
    flattened: dict[str, float] = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_key = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_numeric_effects(nested, nested_key))
    elif isinstance(value, (int, float)):
        flattened[prefix] = float(value)
    return flattened


def _has_positive(effects: dict[str, float], keys: tuple[str, ...]) -> bool:
    return any(value > 0 and any(key in effect_key for key in keys) for effect_key, value in effects.items())


def _has_negative_or_risk(effects: dict[str, float], keys: tuple[str, ...]) -> bool:
    return any(
        (value > 0 and ("risk" in effect_key or "difficulty" in effect_key or "burden" in effect_key))
        or (value < 0 and any(key in effect_key for key in keys))
        or (value > 0 and any(key in effect_key for key in keys))
        for effect_key, value in effects.items()
    )


def _dedupe_reactions(reactions: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for reaction in reactions:
        key = (reaction.get("group", ""), reaction.get("text", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(reaction)
    return unique
