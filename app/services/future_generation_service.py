from __future__ import annotations

import random
import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json


def generate_for_month(year: int, month: int) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    with get_connection() as conn:
        rules = conn.execute(
            """
            SELECT * FROM future_generation_rules
            WHERE starts_year IS NULL OR starts_year <= ?
            ORDER BY weight DESC, id
            """,
            (year,),
        ).fetchall()
        for rule in rules:
            if random.randint(1, 100) > max(5, min(100, int(rule["weight"]))):
                continue
            data = _generate_entity_data(rule, year, month)
            entity_id = f"gen_{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO generated_entities (
                    id, entity_type, name, generated_year, generated_month,
                    source_rule_id, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    rule["target_type"],
                    data["name"],
                    year,
                    month,
                    rule["id"],
                    dumps_json(data),
                ),
            )
            if rule["target_type"] == "person":
                conn.execute(
                    """
                    INSERT INTO save_generated_people (
                        id, person_type, name, generated_year, generated_month,
                        source_rule_id, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_id,
                        data.get("ruleType", "person"),
                        data["name"],
                        year,
                        month,
                        rule["id"],
                        dumps_json(data),
                    ),
                )
            elif rule["target_type"] == "film":
                conn.execute(
                    """
                    INSERT INTO save_generated_films (
                        id, title, generated_year, generated_month,
                        source_rule_id, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (entity_id, data["name"], year, month, rule["id"], dumps_json(data)),
                )
            generated.append({"id": entity_id, **data})
        conn.commit()
    return generated


def _generate_entity_data(rule: Any, year: int, month: int) -> dict[str, Any]:
    rule_data = loads_json(rule["rule_json"], {})
    target_type = rule["target_type"]
    name_pool = rule_data.get("namePool") or ["새로운 이름"]
    name = f"{random.choice(name_pool)} {year % 100:02d}-{month:02d}"
    return {
        "name": name,
        "targetType": target_type,
        "ruleType": rule_data.get("type", target_type),
        "generatedAt": {"year": year, "month": month},
    }
