# Real Data Collection Plan

This project keeps official and curated source data in staging tables before it is promoted into game-facing seed or simulation tables.

## Priority

1. KMDb / 한국영상자료원 movie metadata, via local JSON dump first and Open API later
2. KOBIS Open API daily box office
3. KOBIS yearly total sales and audience counts for average ticket price
4. KOFIC Korean Actors 200 for major actor records
5. KMDb filmography and awards for career timelines
6. Manually curated awards: 청룡, 백상, 대종상, 부산국제영화제, 칸, 아카데미
7. Public critic directories, storing short summaries and tendency tags only
8. Manually curated real historical events
9. KOSIS CPI, population, household consumption, and culture indicators for market/economic modifiers
10. Wikidata SPARQL for supplemental QIDs, English labels, birth dates, occupations, and external identifiers

## Target Coverage

- KOBIS box office: 2004 through the current year
- KMDb movie metadata: Korean films from 1980 through the current year
- Foreign event curation: top 100 foreign films by Korean box office impact
- Actors: first target 300 people
- Directors: first target 150 people
- Critics: first target 30 people
- Awards: 청룡영화상, 백상예술대상, 대종상, 부산국제영화제, 칸영화제, 아카데미상
- KOSIS indicators: CPI, household consumption conditions, recession/boom modifiers, youth and regional population, culture consumption indicators

The machine-readable target snapshot lives in `data/collection_targets.json`.

## Official Sources

- KOBIS Open API: https://kobis.or.kr/kobisopenapi/homepg/apiservice/searchServiceInfo.do?serviceId=searchCode
- KOBIS statistics portal: https://kobis.or.kr/kobis/business/main/main.do
- KMDb Open API listing: https://www.data.go.kr/data/15148784/fileData.do
- KOFIC Korean Actors 200 announcement: https://www.koreanfilm.or.kr/eng/news/kofic_news.jsp?blbdComCd=601007&mode=VIEW&seq=1798
- KOSIS Open API: https://kosis.kr/openapi/devGuide/devGuide_0201List.do
- Wikidata SPARQL endpoint: https://query.wikidata.org/sparql

## Staging Tables

- `collection_runs`: one row per collection or import job
- `collection_api_responses`: redacted raw API responses for audit/debugging
- `staging_kmdb_movies`: KMDb movie metadata
- `staging_kobis_daily_boxoffice`: KOBIS daily box office rows
- `staging_kobis_movie_list`: KOBIS movie code list
- `staging_kobis_movie_details`: KOBIS movie detail rows
- `staging_kobis_yearly_boxoffice`: yearly movie aggregates from collected daily rows
- `staging_major_korean_movies`: major Korean film candidates collected from KOFIC/KOBIZ yearly box office pages
- `staging_kobis_yearly_totals`: yearly total sales/audience and derived average ticket price
- `staging_kofic_actors200`: curated actor roster data
- `staging_kofic_report_files`: local KOFIC settlement/statistics file inventory and extraction status
- `staging_kofic_industry_metrics`: candidate annual industry metrics extracted from local KOFIC reports
- `staging_kofic_report_events`: candidate market/history events extracted from local KOFIC reports
- `staging_award_records`: manually curated awards
- `staging_critic_profiles`: manually curated critic profiles
- `staging_history_events`: manually curated history events
- `staging_kosis_statistics`: raw KOSIS statistics rows
- `staging_kosis_indicator_series`: normalized KOSIS indicator series for game-economic use
- `staging_kosis_search_results`: KOSIS table search results for target curation
- `staging_wikidata_sparql_results`: supplemental Wikidata SPARQL rows for films and people
- `wikidata_movies`: normalized supplemental Wikidata film records for KMDb/KOBIS matching
- `wikidata_people`: normalized supplemental Wikidata person records for seed/KMDb matching
- `industry_yearly_reports`: generated annual industry report snapshots for simulation/UI use

## API Keys

Set keys in the shell before running collectors:

```bash
export KMDB_API_KEY="..."
export KOBIS_API_KEY="..."
export KOSIS_API_KEY="..."
```

The collectors also read `.env` through `python-dotenv`.

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
KOBIS_API_KEY=
KMDB_API_KEY=
KOSIS_API_KEY=
```

`KMDB_SERVICE_KEY` is also accepted for KMDb. API keys must never be hard-coded into scripts.

If a required API key is missing, `fetch_kobis.py` or `fetch_kmdb.py` skips the live API request and initializes the database from bundled sample seed JSON instead.

KOSIS uses `KOSIS_API_KEY` from `.env`. Do not commit real keys.

Wikidata does not require an API key. `WIKIDATA_SPARQL_ENDPOINT` can be overridden in `.env`, and defaults to `https://query.wikidata.org/sparql`.

## Commands

Initialize from bundled sample seed data without API keys:

```bash
python3 scripts/import_seed.py
```

Collect KOBIS daily box office:

```bash
python3 scripts/fetch_kobis.py daily --date 20240101
python3 scripts/fetch_kobis.py daily --from-date 20240101 --to-date 20240107 --rep-nation-code K
```

Collect KOBIS yearly data by fetching daily rows and aggregating them into yearly staging rows:

```bash
python3 scripts/fetch_kobis.py yearly --year 2024
python3 scripts/fetch_kobis.py yearly-range --from-year 2004 --to-year 2026 --dry-run
python3 scripts/fetch_kobis.py yearly-range --from-year 2004 --to-year 2026
python3 scripts/fetch_kobis.py aggregate-yearly --year 2024
```

Collect KOBIS movie codes and details:

```bash
python3 scripts/fetch_kobis.py movie-list --year 2024 --page-start 1 --page-end 5
python3 scripts/fetch_kobis.py movie-list-range --from-year 2004 --to-year 2026 --page-start 1 --page-end 5 --dry-run
python3 scripts/fetch_kobis.py movie-info --movie-code 20236641
python3 scripts/fetch_kobis.py details-from-staging --limit 100
python3 scripts/fetch_kobis.py details-from-major --limit 500
```

Search and collect KOSIS economic/population/culture indicators:

```bash
python3 scripts/fetch_kosis.py search --keyword "소비자물가지수" --org-id 101 --result-count 20
python3 scripts/fetch_kosis.py target cpi_city_monthly --start 202001 --end 202412
python3 scripts/fetch_kosis.py data --target-id cpi_city_monthly --category price --org-id 101 --tbl-id DT_1J22003 --prd-se M --start 202001 --end 202412 --param itmId=T --param objL1=ALL
```

KOSIS target definitions live in `data/kosis_targets.json`. CPI is the first configured target; population, household consumption, business-cycle, and culture-consumption targets are tracked there as `target_search_required` until their exact KOSIS table IDs and classification parameters are curated.

Collect supplemental Wikidata records:

```bash
python3 scripts/fetch_wikidata.py target korean-films --limit 100
python3 scripts/fetch_wikidata.py target korean-film-people --limit 100
python3 scripts/collect_real_data.py wikidata-target korean-films --limit 50
```

Wikidata is not treated as the source of truth for Korean box office, release strategy, or historical market events. Use it to enrich KMDb/KOBIS/person seed records with stable QIDs, English labels, birth dates, occupations, and external IDs. If Wikidata conflicts with KOBIS or KMDb, KOBIS/KMDb wins.

The raw SPARQL response rows are stored in `staging_wikidata_sparql_results`. Matching-oriented normalized rows are also written to `wikidata_movies` and `wikidata_people`.

The Wikidata staging mapper currently stores these game-facing fields when available:

- Film: QID, Korean title, English title, normalized Korean title, normalized English title, release date, year, directors, actors, genres, countries, awards, IMDb ID, Wikipedia URL
- Person: QID, Korean name, English name, normalized Korean name, normalized English name, birth date, birth year, death date, death year, occupations, person-work relationships, IMDb ID, Wikipedia URL

Director, actor, genre, country, award, occupation, and person-work relationship values are stored as JSON lists with Wikidata QIDs and labels where possible.

Collect 500 major Korean film candidates:

```bash
python3 scripts/fetch_major_korean_movies.py --from-year 1980 --to-year 2026 --target 500
```

Build curation worklists for the first large people database pass:

```bash
python3 scripts/build_people_seed_lists.py
```

This writes `data/seed/people/actors_seed_list.txt`, `directors_seed_list.txt`, and `critics_seed_list.txt`. Actor and director lists are ranked from `staging_major_korean_movies` joined with KOBIS movie details. The critic list uses currently seeded critic profiles and leaves unverified target slots marked for public-source curation.

Estimate actor and director internal stats from collected staging data:

```bash
python3 scripts/estimate_people_stats.py
```

The estimator combines KOBIS staging data, seed-level manual adjustments, genre fit, prime-era modifiers, and balance caps. It does not expose numeric stats in the UI.

Collect KMDb movie metadata from the Open API:

```bash
python3 scripts/fetch_kmdb.py --query "박찬욱" --list-count 20
python3 scripts/fetch_kmdb.py --year 2003 --list-count 100
python3 scripts/fetch_kmdb.py --default-korean-range --max-pages 5
python3 scripts/fetch_kmdb.py --from-kobis --limit 100
```

Import a local KMDb JSON dump when API access is not available:

```bash
python3 scripts/import_kmdb_json.py /Users/dldydcks/Downloads/kmdb_json.json
python3 scripts/fetch_kmdb.py --from-json /Users/dldydcks/Downloads/kmdb_json.json
python3 scripts/collect_real_data.py kmdb-json /Users/dldydcks/Downloads/kmdb_json.json
```

Local JSON import defaults to Korean films from 1980 onward and stores rows in `staging_kmdb_movies`, the same staging table used by the API collector. Use `--include-non-korean`, `--from-year`, `--to-year`, or `--limit` for controlled imports.

Import local KOFIC Korean film industry settlement/statistics reports:

```bash
python3 scripts/import_kofic_reports.py --downloads /Users/dldydcks/Downloads
python3 scripts/collect_real_data.py kofic-reports --downloads /Users/dldydcks/Downloads
```

The importer indexes PDF/XLS/HWP files whose names look like KOFIC settlement, market, audience, or cumulative statistics reports. PDF text is extracted when `pypdf` is available. Excel text is extracted when `pandas` plus the required workbook engine is available. HWP body text is extracted on a best-effort basis when `olefile` is available. Extracted full text is written under `data/imported/kofic_text/`, which is git-ignored; the database stores only short snippets, metric candidates, and event candidates.

Install optional local-report extraction dependencies when using a plain project virtualenv:

```bash
pip install -r requirements-data.txt
```

HWP extraction is a best-effort parser for HWP 5 body text streams. If a legacy HWP file uses an unsupported structure, the importer still stores its file metadata and extraction status.

Event candidates stay in `staging_kofic_report_events` by default. Use `--promote-events` only after manual review, because the first pass is intentionally conservative and source-snippet based.

Import KOBIS yearly totals and derive ticket prices:

```bash
python3 scripts/build_ticket_prices.py --csv data/imports/kobis_yearly_totals.csv
python3 scripts/build_ticket_prices.py --year 2024
```

CSV columns for yearly totals:

```csv
year,total_sales,total_audience,source_type
2024,1234567890000,123456789,kobis_derived
```

`build_ticket_prices.py --from-daily --year 2024` can derive a temporary value from collected daily rows, but it is only complete when the collected daily rows cover the full year and source scope.

Build yearly industry report snapshots:

```bash
python3 scripts/build_annual_reports.py --year 2024
python3 scripts/build_annual_reports.py --from-year 2004 --to-year 2025
python3 scripts/build_annual_reports.py --all-available
python3 scripts/collect_real_data.py annual-reports --all-available
```

Annual reports combine available staging/canonical rows into these game-facing sections: yearly box office top 10, Korean film share, foreign hits, actor/director of the year, major awards, production company rankings, distributor share, and genre trend movement. KOBIS/KMDb/KOFIC rows remain the preferred sources; Wikidata is only supplemental matching context.

Import Korean Actors 200 curation CSV:

```bash
python3 scripts/collect_real_data.py actors200-csv data/imports/kofic_actors200.csv
```

CSV columns:

```csv
id,name_ko,name_en,representative_works,introduction,global_tags,source_url
actor_song_kang_ho,송강호,Song Kang-ho,"살인의 추억; 괴물; 기생충",요약 소개문,"festival; global",https://...
```

## Promotion Rule

Collectors only write staging tables. A later transform step should promote curated rows into:

- `movies_historical`, `movies_boxoffice`, `history_ticket_prices`
- `people`, `people_actor_profiles`, `people_director_profiles`
- `people_career_timeline`, `history_award_results`, `movies_awards`
- `industry_yearly_reports`

Critic reviews should not store copied full review text. Store source URL, short quote when legally acceptable, summary, and tendency tags.
