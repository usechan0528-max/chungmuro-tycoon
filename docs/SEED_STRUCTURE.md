# Seed Structure

Seed data is organized by simulation domain. The nested files are the primary source of truth; root-level seed files remain as compatibility fallbacks while the codebase migrates fully to canonical table names.

## Primary Seed Set

The first large build treats these 26 files as the primary data road map.

```text
1. core/stats_100.json
2. core/eras.json
3. core/era_rules.json
4. core/genres.json
5. core/project_scales.json
6. core/production_stages.json

7. people/actors_major.json
8. people/directors_major.json
9. people/critics_major.json
10. people/protected_people.json
11. people/generated_people_rules.json

12. history/protected_director_films.json
13. history/domestic_events_1980s.json
14. history/domestic_events_1990s.json
15. history/domestic_events_2000s.json
16. history/domestic_events_2010s.json
17. history/domestic_events_2020s.json
18. history/foreign_events_fixed.json
19. history/ticket_prices.json
20. history/award_events.json
21. history/historical_reviews_sample.json

22. production/production_events.json
23. production/dialogue_events.json
24. production/plagiarism_events.json
25. production/franchise_events.json
26. production/post_release_events.json
```

Stage-specific `production_choices_*.json` files are supplemental production event seeds. They remain loaded by the database importer, but the 25 files above are the main content pass.

## Folder Layout

```text
data/seed/core/
  stats_100.json
  eras.json
  era_rules.json
  genres.json
  project_scales.json
  production_stages.json

data/seed/people/
  actors_major.json
  directors_major.json
  critics_major.json
  protected_people.json
  generated_people_rules.json

data/seed/history/
  domestic_events_1980s.json
  domestic_events_1990s.json
  domestic_events_2000s.json
  domestic_events_2010s.json
  domestic_events_2020s.json
  policy_events.json
  market_events.json
  distribution_events.json
  theater_events.json
  premium_format_events.json
  foreign_events_fixed.json
  ticket_prices.json
  protected_director_films.json
  award_events.json
  historical_reviews_sample.json

data/seed/production/
  production_choices_planning.json
  production_choices_funding.json
  production_choices_casting.json
  production_choices_shooting.json
  production_choices_postproduction.json
  production_choices_marketing.json
  production_choices_release.json
  dialogue_events.json
  production_events.json
  plagiarism_events.json
  franchise_events.json
  post_release_events.json
```

## Loader Rules

- `app/database.py` reads nested seed files first.
- If a nested file is missing, the loader falls back to the older root-level seed file where one exists.
- Stage-specific production choice files are combined with `production/production_events.json`; duplicate event IDs are harmless because DB inserts use upsert semantics.
- `production/dialogue_events.json` is loaded as dialogue-category events and can be accessed through `dialogue_service.py`.
- Empty files use `[]` so future content can be added without changing loader code.
- `scripts/validate_seed_structure.py` verifies the canonical nested structure and JSON validity.

## Genre Schema

`core/genres.json` stores genre data used by production, release, review, IP, and risk systems.

Required fields:

- `name`: 장르명
- `description`: 설명
- `eraFit`: 시대별 적합도
- `budgetWeights`: 예산 권장 비율
- `successFactors`: 흥행/평가 성공을 견인하는 내부 스탯 ID 목록
- `riskFactors`: 장르가 민감하게 반응하는 리스크 스탯 ID 목록
- `profile.boxofficeWeight`: 흥행 가중치
- `profile.criticWeight`: 평론가 가중치
- `profile.audienceWeight`: 관객 평점 가중치
- `majorRisks`: 주요 리스크
- `franchiseFit`: 시리즈화 적합도
- `secondaryMarketFit`: 2차 시장 적합도
- `profile.plagiarismSensitivity`: 표절 위험 민감도

## Stats Schema

`core/stats_100.json` stores exactly 100 stat definitions. Each item is an object:

```json
{
  "id": "scenario_quality",
  "nameKo": "시나리오 완성도",
  "category": "production_quality",
  "description": "영화의 이야기 구조, 대사, 개연성."
}
```

## Era Schema

`core/eras.json` stores market modifiers and system availability for each start era.

Required fields:

- `marketModifiers.theaterDemand`
- `marketModifiers.ottPower`
- `marketModifiers.foreignCompetition`
- `marketModifiers.middleBudgetRisk`
- `marketModifiers.specialFormatDemand`
- `marketModifiers.onlineSpreadPower`
- `marketModifiers.ticketPriceBurden`
- `unlockedSystems`
- `lockedSystems`

## Era Rule Schema

`core/era_rules.json` stores the rules that make each era behave like a different game mode.

Required fields:

- `id`
- `name`
- `startYear`
- `endYear`
- `summary`
- `marketRules`
- `productionRules`
- `distributionRules`
- `marketingRules`
- `secondaryMarketRules`
- `lockedSystems`
- `unlockedSystems`
- `lockedChoices`
- `strongChoices`
- `genreModifiers`
- `riskModifiers`
- `gameOverRisks`

Optional fields:

- `inefficientChoices`: choices that are possible but weak in the era
- `futureRules`: future-generation rules for the post-historical era

Runtime services copy the current rule into `save_market_state.modifiers_json`, so later UI and services can check era locks without rereading raw seed JSON.

## Project Scale Schema

`core/project_scales.json` stores the production flow for each film scale.

Required fields:

- `minBudget`
- `maxBudget`
- `requiredStages`: ordered stage IDs for the scale
- `eventCountRange.min`
- `eventCountRange.max`
- `failureImpact`

## People Schema

`people/actors_major.json` and `people/directors_major.json` store major public figures and fictional seed people.

Required public fields:

- `id`
- `nameKo`
- `nameEn`
- `type`
- `birthYear`
- `availableFrom`
- `currentStats`
- `potentialStats`
- `genreFit`
- `publicProfile.oneLine`
- `publicProfile.currentAbilityText`
- `publicProfile.potentialText`
- `publicProfile.fameText`
- `publicProfile.brandText`

Optional protection field:

- `protectionLevel`: use only when an individual seed needs a direct protection marker. Long-term protected schedules should live in `people/protected_people.json`.
- `historicalFilmographyLocked`: use for protected real-world directors whose major filmography cannot be cancelled by the player.

Internal stats can be numeric, but actor/director UI must show only the public profile text fields.

## Critic Schema

`people/critics_major.json` stores major critics and seed critic profiles.

Required fields:

- `id`
- `nameKo`
- `type`
- `availableFrom`
- `criticType`
- `influence`
- `tasteProfile`
- `scoringStyle`
- `publicDescription`

## Protected Director Filmography Schema

`history/protected_director_films.json` stores the fixed filmographies that the player cannot cancel.

Required director fields:

- `directorId`
- `directorName`
- `protectionLevel`
- `historicalFilmographyLocked`
- `works`

Required work fields:

- `filmId`
- `title`
- `year`
- `month`
- `protectionLevel`

The five protected director entries are Bong Joon-ho, Park Chan-wook, Lee Chang-dong, Kim Ki-young, and Choi Dong-hoon. Work entries may include optional simulation metadata such as genre, scale, expected audience, market impact, protected windows, and allowed player responses.

## Fixed Foreign Event Schema

`history/foreign_events_fixed.json` stores fixed foreign blockbuster events that occur on historical dates.

Required fields:

- `id`
- `titleKo`
- `titleEn`
- `year`
- `month`
- `impactGrade`
- `fixedLevel`
- `genre`
- `effects`

Effects may use camelCase seed keys such as `foreignCompetition`, `specialFormatDemand`, and `vfxExpectation`. The import/runtime layer normalizes these into internal market fields or modifier keys.

## Ticket Price Schema

`history/ticket_prices.json` stores fixed yearly ticket price records used by box office calculation.

Required fields:

- `year`
- `averageTicketPrice`
- `perceivedTicketPrice`
- `premiumFormatMultiplier`
- `audiencePriceSensitivity`
- `sourceType`

The box office service uses the nearest record at or before the release year. If no earlier record exists yet, it falls back to the earliest available ticket price record.

## Domestic History Event Schema

`history/domestic_events_1980s.json` through `history/domestic_events_2020s.json` store fixed or semi-fixed Korean industry events.

Required fields:

- `id`
- `year`
- `month`
- `title`
- `type`
- `fixedLevel`
- `description`
- `effects`

Optional `unlocks` entries are stored as long-term event flags. Effects may use camelCase seed keys such as `theaterDemand`, `distributionPower`, and `firstWeekImportance`; the runtime layer normalizes these into internal market fields or modifier keys.

## Production Event Schema

`production/production_events.json` and `production/plagiarism_events.json` store project-scoped production events.

Required event fields:

- `id`
- `stage`
- `title`
- `description`
- `trigger`
- `choices`

Required choice fields:

- `id`
- `text`
- `effects`

Choice entries may include `resultText`. When present, the UI outcome uses that sentence instead of exposing numeric effects. Effects can be nested under `stats`, `reputation`, `network`, or `studio`, or written as flat stat keys; the runtime normalizes flat effects before applying them.

Plagiarism events may use `trigger.minPlagiarismRisk` or `trigger.maxPlagiarismRisk` to read the current project's internal `plagiarism_risk`.

## Dialogue Event Schema

`production/dialogue_events.json` stores negotiation-style dialogue events.

Required event fields:

- `id`
- `stage`
- `choices`
- `description` or `npcLine`

Optional NPC fields:

- `npcType`
- `npcTraits`
- `npcLine`

Choice entries may use deterministic checks:

- `check.stat`
- `check.difficulty`
- `successText`
- `failureText`
- `effectsOnSuccess`
- `effectsOnFailure`

The dialogue service applies success or failure effects internally and returns only the matching result sentence for UI display. `walk_out` choices may be marked with `fixedChoice`.

## Franchise Event Schema

`production/franchise_events.json` stores post-release IP expansion events.

Required event fields:

- `id`
- `title`
- `description`
- `trigger`
- `choices`

Required choice fields:

- `id`
- `text`
- `effects`

Supported trigger fields include `minFinalAudience` and `minIpValue`. Franchise effects update IP columns such as `ip_value`, `franchise_power`, and `sequel_demand`, while expansion-specific values such as `world_expansion`, `character_popularity`, and `series_fatigue` are stored in IP metadata and post-release metrics.

## Post-Release Event Schema

`production/post_release_events.json` stores sleeper-hit, rediscovery, and reevaluation events that can happen after release.

Required fields:

- `id`
- `title`
- `description`
- `trigger`
- `effects`

Supported trigger fields include `minYearsAfterRelease`, `minCultPotential`, `minMemePotential`, `availableOnOtt`, and `minSecondaryMarketFit`. Effects can update post-release metrics, public reputation, secondary market revenue, and IP value.
