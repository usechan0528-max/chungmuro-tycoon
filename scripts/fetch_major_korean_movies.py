from __future__ import annotations

import argparse
import re
import ssl
import time
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen

from _fetch_common import load_project_env, log_fetch_error

from app.database import dumps_json, get_connection, initialize_database
from app.services.data_collection_service import normalize_title
from app.services.data_collection_targets import KOBIS_BOXOFFICE_START_YEAR, current_collection_year


KOBIZ_YEARLY_URL = "http://www.koreanfilm.or.kr/eng/news/boxOffice_Yearly.jsp"


class YearlyBoxOfficeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_td = False
        self.cells: list[str] = []
        self.text_parts: list[str] = []
        self.movie_code: str | None = None
        self.rows: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "tr":
            self.in_tr = True
            self.in_td = False
            self.cells = []
            self.text_parts = []
            self.movie_code = None
        if self.in_tr and tag == "td":
            self.in_td = True
            self.text_parts = []
        if self.in_tr and tag == "a":
            href = attr_map.get("href") or ""
            match = re.search(r"movieCd=([0-9A-Za-z]+)", href)
            if match and not self.movie_code:
                self.movie_code = match.group(1)

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_td:
            self.cells.append(_clean_cell("".join(self.text_parts)))
            self.in_td = False
            self.text_parts = []
        if tag == "tr" and self.in_tr:
            if self.movie_code and self.cells:
                self.rows.append((self.movie_code, self.cells))
            self.in_tr = False


def main() -> int:
    load_project_env()
    initialize_database()

    parser = argparse.ArgumentParser(description="Fetch major Korean film candidates from KOFIC/KOBIZ yearly box office.")
    parser.add_argument("--from-year", type=int, default=1980)
    parser.add_argument("--to-year", type=int, default=current_collection_year())
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        count = fetch_major_korean_movies(args.from_year, args.to_year, args.target, args.dry_run)
    except Exception as exc:
        log_fetch_error("fetch_major_korean_movies", exc)
        print(f"fetch failed: {exc}")
        return 1
    print(f"stored {count} major Korean movie candidates")
    return 0


def fetch_major_korean_movies(from_year: int, to_year: int, target: int, dry_run: bool = False) -> int:
    if from_year > to_year:
        raise ValueError("--from-year는 --to-year보다 클 수 없습니다.")
    effective_from_year = max(from_year, KOBIS_BOXOFFICE_START_YEAR)
    if from_year < KOBIS_BOXOFFICE_START_YEAR:
        print(
            f"KOBIS/KOBIZ box office coverage starts in {KOBIS_BOXOFFICE_START_YEAR}; "
            f"{from_year}-{KOBIS_BOXOFFICE_START_YEAR - 1} requires KMDb/manual curation."
        )
    planned_years = list(range(effective_from_year, to_year + 1))
    if dry_run:
        print(f"planned {len(planned_years)} KOBIZ yearly pages, target {target} unique Korean films")
        return 0

    candidates: dict[str, dict[str, Any]] = {}
    for year in planned_years:
        for row in _fetch_yearly_korean_rows(year):
            key = row["movie_code"] or f"{normalize_title(row['title'])}_{row['release_date']}"
            current = candidates.get(key)
            if current is None or row["audience"] > current["max_annual_audience"]:
                candidates[key] = {
                    "source": "kobiz_yearly_boxoffice",
                    "source_movie_code": row["movie_code"],
                    "title": row["title"],
                    "normalized_title": normalize_title(row["title"]),
                    "representative_year": _year_from_release(row["release_date"], year),
                    "first_seen_year": year if current is None else min(current["first_seen_year"], year),
                    "last_seen_year": year if current is None else max(current["last_seen_year"], year),
                    "release_date": row["release_date"],
                    "country": row["country"],
                    "distributor": row["distributor"],
                    "max_annual_rank": row["rank"],
                    "max_annual_audience": row["audience"],
                    "max_annual_gross_text": row["gross"],
                    "max_annual_screens": row["screens"],
                    "source_url": row["source_url"],
                    "raw": {"yearlyRows": [row]},
                }
            else:
                current["first_seen_year"] = min(current["first_seen_year"], year)
                current["last_seen_year"] = max(current["last_seen_year"], year)
                current["raw"]["yearlyRows"].append(row)

    selected = sorted(
        candidates.values(),
        key=lambda item: (int(item["max_annual_audience"] or 0), int(item["representative_year"] or 0)),
        reverse=True,
    )[:target]
    with get_connection() as conn:
        conn.execute("DELETE FROM staging_major_korean_movies WHERE source = 'kobiz_yearly_boxoffice'")
        for movie in selected:
            conn.execute(
                """
                INSERT OR REPLACE INTO staging_major_korean_movies (
                    id, source, source_movie_code, title, normalized_title,
                    representative_year, first_seen_year, last_seen_year,
                    release_date, country, distributor, max_annual_rank,
                    max_annual_audience, max_annual_gross_text,
                    max_annual_screens, source_url, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"korean_major_{movie['source_movie_code'] or movie['normalized_title']}",
                    movie["source"],
                    movie["source_movie_code"],
                    movie["title"],
                    movie["normalized_title"],
                    movie["representative_year"],
                    movie["first_seen_year"],
                    movie["last_seen_year"],
                    movie["release_date"],
                    movie["country"],
                    movie["distributor"],
                    movie["max_annual_rank"],
                    movie["max_annual_audience"],
                    movie["max_annual_gross_text"],
                    movie["max_annual_screens"],
                    movie["source_url"],
                    dumps_json(movie["raw"]),
                ),
            )
        conn.commit()
    return len(selected)


def _fetch_yearly_korean_rows(year: int) -> list[dict[str, Any]]:
    url = (
        f"{KOBIZ_YEARLY_URL}?category=N&country=ALL&mode=BOXOFFICE_YEAR&selectDt={year}"
    )
    html = _read_url(url)
    parser = YearlyBoxOfficeParser()
    parser.feed(html)
    rows: list[dict[str, Any]] = []
    for movie_code, cells in parser.rows:
        parsed = _parse_yearly_cells(year, movie_code, cells, url)
        if parsed and parsed["country"] == "South Korea":
            rows.append(parsed)
    return rows


def _read_url(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            request = Request(url, headers={"User-Agent": "ChungmuroTycoonDataCollector/0.1"})
            with urlopen(request, timeout=60, context=ssl._create_unverified_context()) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1.5 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"Unable to read URL: {url}")


def _parse_yearly_cells(year: int, movie_code: str, cells: list[str], source_url: str) -> dict[str, Any] | None:
    data_cells = [cell for cell in cells if cell]
    if len(data_cells) < 6:
        return None
    rank = _to_int(data_cells[0])
    title_blob = data_cells[1]
    release_date = data_cells[2]
    gross = data_cells[3]
    audience = _to_int(data_cells[4])
    screens = _to_int(data_cells[5])
    title, country, distributor = _split_title_country_distributor(title_blob)
    if not title:
        return None
    return {
        "year": year,
        "movie_code": movie_code,
        "rank": rank,
        "title": title,
        "country": country,
        "distributor": distributor,
        "release_date": release_date,
        "gross": gross,
        "audience": audience,
        "screens": screens,
        "source_url": source_url,
    }


def _split_title_country_distributor(text: str) -> tuple[str, str, str]:
    marker = "South Korea"
    if marker in text:
        title, rest = text.split(marker, 1)
        distributor = rest.strip()
        if distributor.startswith("(") and distributor.endswith(")"):
            distributor = distributor[1:-1].strip()
        return title.strip(), marker, distributor
    return text.strip(), "", ""


def _year_from_release(release_date: str, fallback: int) -> int:
    match = re.search(r"(19|20)\d{2}", release_date)
    return int(match.group(0)) if match else fallback


def _clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _to_int(value: str) -> int:
    text = re.sub(r"[^0-9]", "", value or "")
    return int(text or 0)


if __name__ == "__main__":
    raise SystemExit(main())
