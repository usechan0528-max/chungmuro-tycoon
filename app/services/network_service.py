from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp


def apply_network_deltas(deltas: dict[str, int | float]) -> dict[str, Any]:
    with get_connection() as conn:
        player = conn.execute("SELECT network_json FROM player_state WHERE id = 1").fetchone()
        if not player:
            return {}
        network = loads_json(player["network_json"], {})
        for key, delta in deltas.items():
            network[key] = clamp(float(network.get(key, 10)) + float(delta))
        conn.execute("UPDATE player_state SET network_json = ? WHERE id = 1", (dumps_json(network),))
        conn.commit()
    return network


def describe_network(network: dict[str, Any]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM network_definitions ORDER BY id").fetchall()
    for row in rows:
        value = int(network.get(row["id"], 0))
        if value >= 70:
            descriptions[row["id"]] = row["high_text"] or row["name_ko"]
        elif value >= 35:
            descriptions[row["id"]] = row["mid_text"] or row["name_ko"]
        else:
            descriptions[row["id"]] = row["low_text"] or row["name_ko"]
    return descriptions

