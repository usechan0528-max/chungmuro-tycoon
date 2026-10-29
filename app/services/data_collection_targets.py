from __future__ import annotations

from datetime import date


KOBIS_BOXOFFICE_START_YEAR = 2004
KMDB_KOREAN_MOVIE_START_YEAR = 1980
FOREIGN_EVENT_TARGET_COUNT = 100
ACTOR_TARGET_COUNT = 300
DIRECTOR_TARGET_COUNT = 150
CRITIC_TARGET_COUNT = 30
KOSIS_TARGET_FILE = "data/kosis_targets.json"

AWARD_SYSTEMS = [
    "청룡영화상",
    "백상예술대상",
    "대종상",
    "부산국제영화제",
    "칸영화제",
    "아카데미상",
]


def current_collection_year() -> int:
    return date.today().year
