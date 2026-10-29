from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT_DIR / "data" / "seed"

PRIMARY_SEED_FILES = {
    "core": [
        "stats_100.json",
        "eras.json",
        "era_rules.json",
        "genres.json",
        "project_scales.json",
        "production_stages.json",
    ],
    "people": [
        "actors_major.json",
        "directors_major.json",
        "critics_major.json",
        "protected_people.json",
        "generated_people_rules.json",
    ],
        "history": [
            "domestic_events_1980s.json",
            "domestic_events_1990s.json",
            "domestic_events_2000s.json",
            "domestic_events_2010s.json",
            "domestic_events_2020s.json",
            "foreign_events_fixed.json",
            "policy_events.json",
            "market_events.json",
            "distribution_events.json",
            "theater_events.json",
            "premium_format_events.json",
            "ticket_prices.json",
            "protected_director_films.json",
            "award_events.json",
            "award_results_sample.json",
            "historical_reviews_sample.json",
    ],
    "production": [
        "production_events.json",
        "dialogue_events.json",
        "plagiarism_events.json",
        "franchise_events.json",
        "post_release_events.json",
    ],
}

SUPPLEMENTAL_SEED_FILES = {
    "production": [
        "production_choices_planning.json",
        "production_choices_funding.json",
        "production_choices_casting.json",
        "production_choices_shooting.json",
        "production_choices_postproduction.json",
        "production_choices_marketing.json",
        "production_choices_release.json",
    ],
}


CANONICAL_SEED_FILES = {
    folder: filenames + SUPPLEMENTAL_SEED_FILES.get(folder, [])
    for folder, filenames in PRIMARY_SEED_FILES.items()
}


def main() -> int:
    problems: list[str] = []
    for folder, filenames in CANONICAL_SEED_FILES.items():
        folder_path = SEED_DIR / folder
        if not folder_path.is_dir():
            problems.append(f"missing folder: {folder_path}")
            continue

        expected = set(filenames)
        actual = {path.name for path in folder_path.glob("*.json")}
        for missing in sorted(expected - actual):
            problems.append(f"missing seed file: {folder}/{missing}")
        for extra in sorted(actual - expected):
            problems.append(f"unexpected seed file: {folder}/{extra}")

        for filename in filenames:
            path = folder_path / filename
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"invalid json: {folder}/{filename}: {exc}")
                continue
            if folder == "core" and filename == "stats_100.json":
                problems.extend(_validate_stats_100(data))
            if folder == "core" and filename == "eras.json":
                problems.extend(_validate_eras(data))
            if folder == "core" and filename == "era_rules.json":
                problems.extend(_validate_era_rules(data))
            if folder == "core" and filename == "genres.json":
                problems.extend(_validate_genres(data))
            if folder == "core" and filename == "project_scales.json":
                problems.extend(_validate_project_scales(data))
            if folder == "people" and filename in {"actors_major.json", "directors_major.json"}:
                problems.extend(_validate_major_people(data, f"{folder}/{filename}"))
            if folder == "people" and filename == "critics_major.json":
                problems.extend(_validate_major_critics(data))
            if folder == "history" and filename == "protected_director_films.json":
                problems.extend(_validate_protected_director_films(data))
            if folder == "history" and filename == "foreign_events_fixed.json":
                problems.extend(_validate_foreign_events_fixed(data))
            if folder == "history" and filename == "ticket_prices.json":
                problems.extend(_validate_ticket_prices(data))
            if folder == "history" and filename.startswith("domestic_events_"):
                problems.extend(_validate_domestic_events(data, f"{folder}/{filename}"))
            if folder == "history" and filename in {"policy_events.json", "market_events.json"}:
                problems.extend(_validate_domestic_events(data, f"{folder}/{filename}"))
            if folder == "history" and filename in {
                "distribution_events.json",
                "theater_events.json",
                "premium_format_events.json",
            }:
                problems.extend(_validate_industry_events(data, f"{folder}/{filename}"))
            if folder == "production" and filename == "production_events.json":
                problems.extend(_validate_production_events(data, f"{folder}/{filename}"))
            if folder == "production" and filename == "plagiarism_events.json":
                problems.extend(_validate_production_events(data, f"{folder}/{filename}"))
            if folder == "production" and filename == "franchise_events.json":
                problems.extend(_validate_franchise_events(data))
            if folder == "production" and filename == "post_release_events.json":
                problems.extend(_validate_post_release_events(data))
            if folder == "production" and filename == "dialogue_events.json":
                problems.extend(_validate_dialogue_events(data))

    if problems:
        for problem in problems:
            print(problem)
        return 1

    print("seed structure ok")
    return 0


def _validate_stats_100(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["core/stats_100.json must be a list"]
    if len(data) != 100:
        problems.append(f"core/stats_100.json must contain 100 stats, found {len(data)}")
    seen: set[str] = set()
    required = {"id", "nameKo", "category", "description"}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            problems.append(f"core/stats_100.json item {index} must be an object")
            continue
        missing = required - set(item)
        if missing:
            problems.append(f"core/stats_100.json item {index} missing: {', '.join(sorted(missing))}")
        stat_id = item.get("id")
        if not isinstance(stat_id, str) or not stat_id:
            problems.append(f"core/stats_100.json item {index} has invalid id")
            continue
        if stat_id in seen:
            problems.append(f"core/stats_100.json duplicate id: {stat_id}")
        seen.add(stat_id)
    return problems


def _validate_eras(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["core/eras.json must be a list"]
    required = {"id", "name", "startYear", "description", "marketModifiers", "unlockedSystems", "lockedSystems"}
    required_modifiers = {
        "theaterDemand",
        "ottPower",
        "foreignCompetition",
        "middleBudgetRisk",
        "specialFormatDemand",
        "onlineSpreadPower",
        "ticketPriceBurden",
    }
    for index, era in enumerate(data):
        if not isinstance(era, dict):
            problems.append(f"core/eras.json item {index} must be an object")
            continue
        missing = required - set(era)
        if missing:
            problems.append(f"core/eras.json item {index} missing: {', '.join(sorted(missing))}")
        modifiers = era.get("marketModifiers")
        if not isinstance(modifiers, dict):
            problems.append(f"core/eras.json item {index} marketModifiers must be an object")
            continue
        missing_modifiers = required_modifiers - set(modifiers)
        if missing_modifiers:
            problems.append(
                f"core/eras.json item {index} marketModifiers missing: {', '.join(sorted(missing_modifiers))}"
            )
    return problems


def _validate_era_rules(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["core/era_rules.json must be a list"]
    required = {
        "id",
        "name",
        "startYear",
        "marketRules",
        "productionRules",
        "distributionRules",
        "marketingRules",
        "secondaryMarketRules",
        "lockedSystems",
        "unlockedSystems",
        "lockedChoices",
        "strongChoices",
        "genreModifiers",
        "riskModifiers",
        "gameOverRisks",
    }
    required_market = {
        "theaterDemand",
        "ottPower",
        "foreignCompetition",
        "middleBudgetRisk",
        "specialFormatDemand",
        "onlineSpreadPower",
        "ticketPriceBurden",
        "majorDistributorPower",
        "screenAccessDifficulty",
    }
    for index, rule in enumerate(data):
        if not isinstance(rule, dict):
            problems.append(f"core/era_rules.json item {index} must be an object")
            continue
        missing = required - set(rule)
        if missing:
            problems.append(f"core/era_rules.json item {index} missing: {', '.join(sorted(missing))}")
        market = rule.get("marketRules")
        if not isinstance(market, dict):
            problems.append(f"core/era_rules.json item {index} marketRules must be an object")
        else:
            missing_market = required_market - set(market)
            if missing_market:
                problems.append(
                    f"core/era_rules.json item {index} marketRules missing: "
                    + ", ".join(sorted(missing_market))
                )
        for field in (
            "productionRules",
            "distributionRules",
            "marketingRules",
            "secondaryMarketRules",
            "genreModifiers",
            "riskModifiers",
        ):
            if not isinstance(rule.get(field), dict):
                problems.append(f"core/era_rules.json item {index} {field} must be an object")
        for field in ("lockedSystems", "unlockedSystems", "lockedChoices", "strongChoices", "gameOverRisks"):
            if not isinstance(rule.get(field), list):
                problems.append(f"core/era_rules.json item {index} {field} must be a list")
        if "inefficientChoices" in rule and not isinstance(rule["inefficientChoices"], list):
            problems.append(f"core/era_rules.json item {index} inefficientChoices must be a list")
        if "futureRules" in rule and not isinstance(rule["futureRules"], dict):
            problems.append(f"core/era_rules.json item {index} futureRules must be an object")
    return problems


def _validate_genres(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["core/genres.json must be a list"]
    required = {
        "id",
        "name",
        "description",
        "budgetWeights",
        "successFactors",
        "riskFactors",
        "franchiseFit",
        "secondaryMarketFit",
    }
    weight_keys = {
        "scenario",
        "directing",
        "actors",
        "shooting",
        "art",
        "stunt",
        "vfx",
        "sound",
        "editing",
        "contingency",
    }
    for index, genre in enumerate(data):
        if not isinstance(genre, dict):
            problems.append(f"core/genres.json item {index} must be an object")
            continue
        missing = required - set(genre)
        if missing:
            problems.append(f"core/genres.json item {index} missing: {', '.join(sorted(missing))}")
        weights = genre.get("budgetWeights")
        if not isinstance(weights, dict):
            problems.append(f"core/genres.json item {index} budgetWeights must be an object")
        else:
            missing_weights = weight_keys - set(weights)
            if missing_weights:
                problems.append(
                    f"core/genres.json item {index} budgetWeights missing: {', '.join(sorted(missing_weights))}"
                )
        for field in ("successFactors", "riskFactors"):
            if not isinstance(genre.get(field), list) or not genre.get(field):
                problems.append(f"core/genres.json item {index} {field} must be a non-empty list")
    return problems


def _validate_project_scales(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["core/project_scales.json must be a list"]
    required = {"id", "name", "minBudget", "maxBudget", "requiredStages", "eventCountRange", "failureImpact"}
    for index, scale in enumerate(data):
        if not isinstance(scale, dict):
            problems.append(f"core/project_scales.json item {index} must be an object")
            continue
        missing = required - set(scale)
        if missing:
            problems.append(f"core/project_scales.json item {index} missing: {', '.join(sorted(missing))}")
        stages = scale.get("requiredStages")
        if not isinstance(stages, list) or not stages:
            problems.append(f"core/project_scales.json item {index} requiredStages must be a non-empty list")
        event_range = scale.get("eventCountRange")
        if not isinstance(event_range, dict):
            problems.append(f"core/project_scales.json item {index} eventCountRange must be an object")
            continue
        if "min" not in event_range or "max" not in event_range:
            problems.append(f"core/project_scales.json item {index} eventCountRange must include min and max")
    return problems


def _validate_major_people(data: object, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return [f"{label} must be a list"]
    required = {
        "id",
        "nameKo",
        "nameEn",
        "type",
        "birthYear",
        "availableFrom",
        "status",
        "currentStats",
        "potentialStats",
        "genreFit",
        "tier",
        "genreTags",
        "peakEras",
        "manualOverride",
        "publicProfile",
    }
    public_fields = {"oneLine", "currentAbilityText", "potentialText", "fameText", "brandText"}
    for index, person in enumerate(data):
        if not isinstance(person, dict):
            problems.append(f"{label} item {index} must be an object")
            continue
        missing = required - set(person)
        if missing:
            problems.append(f"{label} item {index} missing: {', '.join(sorted(missing))}")
        if person.get("type") == "actor" and not isinstance(person.get("roleType"), list):
            problems.append(f"{label} item {index} roleType must be a list")
        if person.get("type") == "director" and not isinstance(person.get("directorType"), list):
            problems.append(f"{label} item {index} directorType must be a list")
        if not isinstance(person.get("genreTags"), list) or not person.get("genreTags"):
            problems.append(f"{label} item {index} genreTags must be a non-empty list")
        if not isinstance(person.get("peakEras"), list):
            problems.append(f"{label} item {index} peakEras must be a list")
        if person.get("manualOverride") is True and not isinstance(person.get("manualStats"), dict):
            problems.append(f"{label} item {index} manualStats must be an object when manualOverride is true")
        profile = person.get("publicProfile")
        if not isinstance(profile, dict):
            problems.append(f"{label} item {index} publicProfile must be an object")
            continue
        missing_profile = public_fields - set(profile)
        if missing_profile:
            problems.append(f"{label} item {index} publicProfile missing: {', '.join(sorted(missing_profile))}")
    return problems


def _validate_major_critics(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["people/critics_major.json must be a list"]
    required = {
        "id",
        "nameKo",
        "type",
        "availableFrom",
        "criticType",
        "influence",
        "tasteProfile",
        "scoringStyle",
        "publicDescription",
    }
    for index, critic in enumerate(data):
        if not isinstance(critic, dict):
            problems.append(f"people/critics_major.json item {index} must be an object")
            continue
        missing = required - set(critic)
        if missing:
            problems.append(f"people/critics_major.json item {index} missing: {', '.join(sorted(missing))}")
    return problems


def _validate_protected_director_films(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["history/protected_director_films.json must be a list"]

    expected_directors = {
        "director_bong_joon_ho",
        "director_park_chan_wook",
        "director_lee_chang_dong",
        "director_kim_ki_young",
        "director_choi_dong_hoon",
    }
    required_entry = {
        "directorId",
        "directorName",
        "protectionLevel",
        "historicalFilmographyLocked",
        "works",
    }
    required_work = {"filmId", "title", "year", "month", "protectionLevel"}
    seen_directors: set[str] = set()
    seen_films: set[str] = set()

    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            problems.append(f"history/protected_director_films.json item {index} must be an object")
            continue
        missing = required_entry - set(entry)
        if missing:
            problems.append(
                f"history/protected_director_films.json item {index} missing: {', '.join(sorted(missing))}"
            )
        if "name" in entry:
            problems.append(f"history/protected_director_films.json item {index} must use directorName, not name")
        director_id = entry.get("directorId")
        if isinstance(director_id, str):
            if director_id in seen_directors:
                problems.append(f"history/protected_director_films.json duplicate directorId: {director_id}")
            seen_directors.add(director_id)
        if entry.get("historicalFilmographyLocked") is not True:
            problems.append(
                f"history/protected_director_films.json item {index} historicalFilmographyLocked must be true"
            )
        works = entry.get("works")
        if not isinstance(works, list) or not works:
            problems.append(f"history/protected_director_films.json item {index} works must be a non-empty list")
            continue
        for work_index, work in enumerate(works):
            if not isinstance(work, dict):
                problems.append(
                    f"history/protected_director_films.json item {index} work {work_index} must be an object"
                )
                continue
            missing_work = required_work - set(work)
            if missing_work:
                problems.append(
                    "history/protected_director_films.json "
                    f"item {index} work {work_index} missing: {', '.join(sorted(missing_work))}"
                )
            film_id = work.get("filmId")
            if isinstance(film_id, str):
                if film_id in seen_films:
                    problems.append(f"history/protected_director_films.json duplicate filmId: {film_id}")
                seen_films.add(film_id)

    missing_directors = expected_directors - seen_directors
    if missing_directors:
        problems.append(
            "history/protected_director_films.json missing protected directors: "
            + ", ".join(sorted(missing_directors))
        )
    return problems


def _validate_foreign_events_fixed(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["history/foreign_events_fixed.json must be a list"]

    required = {
        "id",
        "titleKo",
        "titleEn",
        "year",
        "month",
        "impactGrade",
        "fixedLevel",
        "genre",
        "effects",
    }
    seen: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"history/foreign_events_fixed.json item {index} must be an object")
            continue
        missing = required - set(event)
        if missing:
            problems.append(f"history/foreign_events_fixed.json item {index} missing: {', '.join(sorted(missing))}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"history/foreign_events_fixed.json item {index} has invalid id")
        elif event_id in seen:
            problems.append(f"history/foreign_events_fixed.json duplicate id: {event_id}")
        else:
            seen.add(event_id)
        if not isinstance(event.get("genre"), list) or not event.get("genre"):
            problems.append(f"history/foreign_events_fixed.json item {index} genre must be a non-empty list")
        if not isinstance(event.get("effects"), dict) or not event.get("effects"):
            problems.append(f"history/foreign_events_fixed.json item {index} effects must be a non-empty object")
    return problems


def _validate_ticket_prices(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["history/ticket_prices.json must be a list"]

    required = {
        "year",
        "averageTicketPrice",
        "perceivedTicketPrice",
        "premiumFormatMultiplier",
        "audiencePriceSensitivity",
        "sourceType",
    }
    seen_years: set[int] = set()
    for index, ticket in enumerate(data):
        if not isinstance(ticket, dict):
            problems.append(f"history/ticket_prices.json item {index} must be an object")
            continue
        missing = required - set(ticket)
        if missing:
            problems.append(f"history/ticket_prices.json item {index} missing: {', '.join(sorted(missing))}")
        year = ticket.get("year")
        if not isinstance(year, int):
            problems.append(f"history/ticket_prices.json item {index} year must be an integer")
        elif year in seen_years:
            problems.append(f"history/ticket_prices.json duplicate year: {year}")
        else:
            seen_years.add(year)
        for field in ("averageTicketPrice", "perceivedTicketPrice", "audiencePriceSensitivity"):
            if field in ticket and not isinstance(ticket[field], int):
                problems.append(f"history/ticket_prices.json item {index} {field} must be an integer")
        if "premiumFormatMultiplier" in ticket and not isinstance(ticket["premiumFormatMultiplier"], int | float):
            problems.append(f"history/ticket_prices.json item {index} premiumFormatMultiplier must be numeric")
    return problems


def _validate_domestic_events(data: object, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return [f"{label} must be a list"]

    required = {"id", "year", "month", "title", "type", "fixedLevel", "description", "effects"}
    seen: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"{label} item {index} must be an object")
            continue
        missing = required - set(event)
        if missing:
            problems.append(f"{label} item {index} missing: {', '.join(sorted(missing))}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"{label} item {index} has invalid id")
        elif event_id in seen:
            problems.append(f"{label} duplicate id: {event_id}")
        else:
            seen.add(event_id)
        if not isinstance(event.get("effects"), dict) or not event.get("effects"):
            problems.append(f"{label} item {index} effects must be a non-empty object")
        if "unlocks" in event and not isinstance(event["unlocks"], list):
            problems.append(f"{label} item {index} unlocks must be a list")
    return problems


def _validate_industry_events(data: object, label: str) -> list[str]:
    problems = _validate_domestic_events(data, label)
    if not isinstance(data, list):
        return problems
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            continue
        if "company" in event and not isinstance(event["company"], str):
            problems.append(f"{label} item {index} company must be a string")
        if "chain" in event and not isinstance(event["chain"], str):
            problems.append(f"{label} item {index} chain must be a string")
        if "location" in event and not isinstance(event["location"], str):
            problems.append(f"{label} item {index} location must be a string")
        if "format" in event and not isinstance(event["format"], list):
            problems.append(f"{label} item {index} format must be a list")
        if "relatedCompanies" in event and not isinstance(event["relatedCompanies"], list):
            problems.append(f"{label} item {index} relatedCompanies must be a list")
    return problems


def _validate_production_events(data: object, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return [f"{label} must be a list"]

    required_event = {"id", "stage", "title", "description", "trigger", "choices"}
    required_choice = {"id", "text", "effects"}
    seen_events: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"{label} item {index} must be an object")
            continue
        missing = required_event - set(event)
        if missing:
            problems.append(f"{label} item {index} missing: {', '.join(sorted(missing))}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"{label} item {index} has invalid id")
        elif event_id in seen_events:
            problems.append(f"{label} duplicate id: {event_id}")
        else:
            seen_events.add(event_id)
        if not isinstance(event.get("trigger"), dict):
            problems.append(f"{label} item {index} trigger must be an object")
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            problems.append(f"{label} item {index} choices must be a non-empty list")
            continue
        seen_choices: set[str] = set()
        for choice_index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                problems.append(
                    f"{label} item {index} choice {choice_index} must be an object"
                )
                continue
            missing_choice = required_choice - set(choice)
            if missing_choice:
                problems.append(
                    f"{label} item {index} choice {choice_index} missing: {', '.join(sorted(missing_choice))}"
                )
            choice_id = choice.get("id")
            if isinstance(choice_id, str):
                if choice_id in seen_choices:
                    problems.append(
                        f"{label} item {index} duplicate choice id: {choice_id}"
                    )
                seen_choices.add(choice_id)
            if not isinstance(choice.get("effects"), dict):
                problems.append(
                    f"{label} item {index} choice {choice_index} effects must be an object"
                )
    return problems


def _validate_dialogue_events(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["production/dialogue_events.json must be a list"]

    required_event = {"id", "stage", "choices"}
    seen_events: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"production/dialogue_events.json item {index} must be an object")
            continue
        missing = required_event - set(event)
        if missing:
            problems.append(f"production/dialogue_events.json item {index} missing: {', '.join(sorted(missing))}")
        if "description" not in event and "npcLine" not in event:
            problems.append(f"production/dialogue_events.json item {index} must include description or npcLine")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"production/dialogue_events.json item {index} has invalid id")
        elif event_id in seen_events:
            problems.append(f"production/dialogue_events.json duplicate id: {event_id}")
        else:
            seen_events.add(event_id)
        if "npcTraits" in event and not isinstance(event["npcTraits"], list):
            problems.append(f"production/dialogue_events.json item {index} npcTraits must be a list")
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            problems.append(f"production/dialogue_events.json item {index} choices must be a non-empty list")
            continue
        seen_choices: set[str] = set()
        for choice_index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                problems.append(f"production/dialogue_events.json item {index} choice {choice_index} must be an object")
                continue
            if "id" not in choice or "text" not in choice:
                problems.append(f"production/dialogue_events.json item {index} choice {choice_index} missing id or text")
            choice_id = choice.get("id")
            if isinstance(choice_id, str):
                if choice_id in seen_choices:
                    problems.append(f"production/dialogue_events.json item {index} duplicate choice id: {choice_id}")
                seen_choices.add(choice_id)
            has_direct_effect = isinstance(choice.get("effects"), dict)
            has_check_effects = isinstance(choice.get("effectsOnSuccess"), dict) or isinstance(
                choice.get("effectsOnFailure"), dict
            )
            if not has_direct_effect and not has_check_effects:
                problems.append(
                    f"production/dialogue_events.json item {index} choice {choice_index} must include effects"
                )
            if "check" in choice:
                check = choice["check"]
                if not isinstance(check, dict) or "stat" not in check or "difficulty" not in check:
                    problems.append(
                        f"production/dialogue_events.json item {index} choice {choice_index} check must include stat and difficulty"
                    )
    return problems


def _validate_franchise_events(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["production/franchise_events.json must be a list"]

    required_event = {"id", "title", "description", "trigger", "choices"}
    required_choice = {"id", "text", "effects"}
    seen_events: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"production/franchise_events.json item {index} must be an object")
            continue
        missing = required_event - set(event)
        if missing:
            problems.append(f"production/franchise_events.json item {index} missing: {', '.join(sorted(missing))}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"production/franchise_events.json item {index} has invalid id")
        elif event_id in seen_events:
            problems.append(f"production/franchise_events.json duplicate id: {event_id}")
        else:
            seen_events.add(event_id)
        trigger = event.get("trigger")
        if not isinstance(trigger, dict):
            problems.append(f"production/franchise_events.json item {index} trigger must be an object")
        else:
            for field in ("minFinalAudience", "minIpValue"):
                if field in trigger and not isinstance(trigger[field], int):
                    problems.append(f"production/franchise_events.json item {index} trigger.{field} must be an integer")
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            problems.append(f"production/franchise_events.json item {index} choices must be a non-empty list")
            continue
        seen_choices: set[str] = set()
        for choice_index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                problems.append(f"production/franchise_events.json item {index} choice {choice_index} must be an object")
                continue
            missing_choice = required_choice - set(choice)
            if missing_choice:
                problems.append(
                    f"production/franchise_events.json item {index} choice {choice_index} missing: "
                    + ", ".join(sorted(missing_choice))
                )
            choice_id = choice.get("id")
            if isinstance(choice_id, str):
                if choice_id in seen_choices:
                    problems.append(f"production/franchise_events.json item {index} duplicate choice id: {choice_id}")
                seen_choices.add(choice_id)
            if not isinstance(choice.get("effects"), dict):
                problems.append(f"production/franchise_events.json item {index} choice {choice_index} effects must be an object")
    return problems


def _validate_post_release_events(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, list):
        return ["production/post_release_events.json must be a list"]

    required = {"id", "title", "description", "trigger", "effects"}
    seen: set[str] = set()
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            problems.append(f"production/post_release_events.json item {index} must be an object")
            continue
        missing = required - set(event)
        if missing:
            problems.append(f"production/post_release_events.json item {index} missing: {', '.join(sorted(missing))}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            problems.append(f"production/post_release_events.json item {index} has invalid id")
        elif event_id in seen:
            problems.append(f"production/post_release_events.json duplicate id: {event_id}")
        else:
            seen.add(event_id)
        if not isinstance(event.get("trigger"), dict):
            problems.append(f"production/post_release_events.json item {index} trigger must be an object")
        if not isinstance(event.get("effects"), dict) or not event.get("effects"):
            problems.append(f"production/post_release_events.json item {index} effects must be a non-empty object")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
