from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import ssl
import time
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import BASE_DIR
from app.database import dumps_json, get_connection

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - requirements.txt provides python-dotenv.
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False


KMDB_MOVIE_SEARCH_ENDPOINT = "http://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp"
KOBIS_DAILY_BOXOFFICE_ENDPOINT = (
    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)
KOBIS_MOVIE_LIST_ENDPOINT = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"
KOBIS_MOVIE_INFO_ENDPOINT = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
KOSIS_STATISTICS_ENDPOINT = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
KOSIS_SEARCH_ENDPOINT = "https://kosis.kr/openapi/statisticsSearch.do"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

KOFIC_REPORT_MARKERS = (
    "KOFIC",
    "영화산업",
    "결산",
    "관객조사",
    "영화시장",
    "누계",
    "통계",
)
KOFIC_REPORT_EXTENSIONS = {".pdf", ".xls", ".xlsx", ".hwp", ""}

MARKET_YEARLY_METRIC_MAP = {
    "total_audience": ("total_admissions",),
    "korean_film_audience": ("korean_film_admissions",),
    "foreign_film_audience": ("foreign_film_admissions",),
    "total_revenue": ("total_boxoffice_sales",),
    "non_theatrical_market_size": ("non_theatrical_market_size",),
    "theater_count": ("theater_count",),
    "screen_count": ("screen_count",),
    "avg_production_cost": ("avg_production_cost",),
    "avg_total_cost": ("avg_total_cost",),
    "estimated_profit_rate": ("estimated_profit_rate",),
    "export_amount": ("export_amount",),
}

MARKET_YEARLY_INTEGER_FIELDS = {
    "total_audience",
    "korean_film_audience",
    "foreign_film_audience",
    "total_revenue",
    "non_theatrical_market_size",
    "theater_count",
    "screen_count",
    "avg_production_cost",
    "avg_total_cost",
}


class CollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollectionConfig:
    kmdb_api_key: str | None = None
    kobis_api_key: str | None = None
    kosis_api_key: str | None = None
    wikidata_sparql_endpoint: str = WIKIDATA_SPARQL_ENDPOINT

    @classmethod
    def from_env(cls) -> CollectionConfig:
        load_dotenv(BASE_DIR / ".env")
        return cls(
            kmdb_api_key=os.getenv("KMDB_API_KEY") or os.getenv("KMDB_SERVICE_KEY"),
            kobis_api_key=os.getenv("KOBIS_API_KEY"),
            kosis_api_key=os.getenv("KOSIS_API_KEY"),
            wikidata_sparql_endpoint=os.getenv("WIKIDATA_SPARQL_ENDPOINT") or WIKIDATA_SPARQL_ENDPOINT,
        )


def collect_kmdb_movies(
    query: str = "",
    year: int | None = None,
    list_count: int = 100,
    start_count: int = 0,
    korean_only: bool = False,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kmdb_api_key:
        raise CollectionError("KMDB_API_KEY 또는 KMDB_SERVICE_KEY 환경변수가 필요합니다.")

    params: dict[str, Any] = {
        "ServiceKey": config.kmdb_api_key,
        "collection": "kmdb_new2",
        "detail": "Y",
        "listCount": list_count,
        "startCount": start_count,
    }
    if query:
        params["query"] = query
    if year:
        params["releaseDts"] = f"{year}0101"
        params["releaseDte"] = f"{year}1231"

    with get_connection() as conn:
        run_id = _start_run(conn, "KMDb", "movie_search", params)
        try:
            payload, status_code, request_url = _request_json(KMDB_MOVIE_SEARCH_ENDPOINT, params)
            _store_response(conn, run_id, "KMDb", KMDB_MOVIE_SEARCH_ENDPOINT, request_url, status_code, payload)
            count = 0
            for item in _extract_kmdb_results(payload):
                if korean_only and not _is_korean_kmdb_movie(item):
                    continue
                movie = _normalize_kmdb_movie(item, request_url)
                if not movie["kmdb_id"]:
                    continue
                _upsert_kmdb_movie(conn, movie)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} KMDb movie rows collected")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def import_kmdb_json_dump(
    json_path: Path | str,
    *,
    korean_only: bool = True,
    from_year: int | None = 1980,
    to_year: int | None = None,
    limit: int | None = None,
) -> int:
    path = Path(json_path)
    if not path.exists():
        raise CollectionError(f"KMDb JSON file not found: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"KMDb JSON parse failed: {path}") from exc

    rows = _extract_kmdb_dump_rows(payload)
    params = {
        "path": str(path),
        "korean_only": korean_only,
        "from_year": from_year,
        "to_year": to_year,
        "limit": limit,
    }
    with get_connection() as conn:
        run_id = _start_run(conn, "KMDb", "local_json_import", params)
        try:
            count = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                movie = _normalize_kmdb_dump_movie(row, path)
                if not movie["kmdb_id"]:
                    continue
                if korean_only and not _is_korean_text(movie["nation"], movie["production_company"]):
                    continue
                match_year = movie["match_year"] or movie["prod_year"]
                if from_year is not None and (not match_year or match_year < from_year):
                    continue
                if to_year is not None and (not match_year or match_year > to_year):
                    continue
                _upsert_kmdb_movie(conn, movie)
                count += 1
                if limit is not None and count >= limit:
                    break
            _finish_run(conn, run_id, "completed", count, f"{count} KMDb local JSON rows imported")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kosis_statistics(
    *,
    target_id: str,
    org_id: str,
    tbl_id: str,
    prd_se: str = "Y",
    start_prd_de: str | None = None,
    end_prd_de: str | None = None,
    new_est_prd_cnt: int | None = None,
    params: dict[str, Any] | None = None,
    category: str | None = None,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kosis_api_key:
        raise CollectionError("KOSIS_API_KEY 환경변수가 필요합니다.")
    if not target_id:
        raise CollectionError("target_id가 필요합니다.")
    if not org_id or not tbl_id:
        raise CollectionError("KOSIS org_id와 tbl_id가 필요합니다.")
    if not start_prd_de and not new_est_prd_cnt:
        raise CollectionError("start_prd_de/end_prd_de 또는 new_est_prd_cnt가 필요합니다.")

    request_params: dict[str, Any] = {
        "method": "getList",
        "apiKey": config.kosis_api_key,
        "format": "json",
        "jsonVD": "Y",
        "prdSe": prd_se,
        "orgId": org_id,
        "tblId": tbl_id,
    }
    if start_prd_de:
        request_params["startPrdDe"] = start_prd_de
    if end_prd_de:
        request_params["endPrdDe"] = end_prd_de
    if new_est_prd_cnt:
        request_params["newEstPrdCnt"] = new_est_prd_cnt
    for key, value in (params or {}).items():
        if value not in (None, ""):
            request_params[key] = value

    with get_connection() as conn:
        run_id = _start_run(conn, "KOSIS", "statistics", {"target_id": target_id, **request_params})
        try:
            payload, status_code, request_url = _request_json(KOSIS_STATISTICS_ENDPOINT, request_params)
            _store_response(conn, run_id, "KOSIS", KOSIS_STATISTICS_ENDPOINT, request_url, status_code, payload)
            rows = _extract_kosis_rows(payload)
            count = 0
            for row in rows:
                _upsert_kosis_statistic(conn, target_id, category, row, request_url)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} KOSIS rows collected for {target_id}")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kosis_target(
    target_id: str,
    *,
    start_prd_de: str | None = None,
    end_prd_de: str | None = None,
    new_est_prd_cnt: int | None = None,
    targets_path: Path | str | None = None,
) -> int:
    target = _load_kosis_target(target_id, targets_path)
    if not target.get("orgId") or not target.get("tblId"):
        raise CollectionError(f"KOSIS target '{target_id}' has no orgId/tblId yet.")
    return collect_kosis_statistics(
        target_id=target_id,
        org_id=str(target["orgId"]),
        tbl_id=str(target["tblId"]),
        prd_se=str(target.get("prdSe", "Y")),
        start_prd_de=start_prd_de or target.get("startPrdDe"),
        end_prd_de=end_prd_de or target.get("endPrdDe"),
        new_est_prd_cnt=new_est_prd_cnt or target.get("newEstPrdCnt"),
        params=target.get("params", {}),
        category=target.get("category"),
    )


def search_kosis_statistics(
    search_name: str,
    *,
    org_id: str | None = None,
    result_count: int = 20,
    start_count: int = 1,
    sort: str = "RANK",
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kosis_api_key:
        raise CollectionError("KOSIS_API_KEY 환경변수가 필요합니다.")
    if not search_name:
        raise CollectionError("검색어가 필요합니다.")
    params: dict[str, Any] = {
        "method": "getList",
        "apiKey": config.kosis_api_key,
        "format": "json",
        "content": "json",
        "searchNm": search_name,
        "sort": sort,
        "startCount": start_count,
        "resultCount": result_count,
    }
    if org_id:
        params["orgId"] = org_id

    with get_connection() as conn:
        run_id = _start_run(conn, "KOSIS", "statistics_search", params)
        try:
            payload, status_code, request_url = _request_json(KOSIS_SEARCH_ENDPOINT, params)
            _store_response(conn, run_id, "KOSIS", KOSIS_SEARCH_ENDPOINT, request_url, status_code, payload)
            rows = _extract_kosis_rows(payload)
            count = 0
            for row in rows:
                _upsert_kosis_search_result(conn, search_name, row)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} KOSIS search rows collected")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kobis_daily_boxoffice(
    target_date: str,
    rep_nation_code: str | None = None,
    movie_type_code: str | None = None,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kobis_api_key:
        raise CollectionError("KOBIS_API_KEY 환경변수가 필요합니다.")
    if not re.fullmatch(r"\d{8}", target_date):
        raise CollectionError("target_date는 YYYYMMDD 형식이어야 합니다.")

    params: dict[str, Any] = {"key": config.kobis_api_key, "targetDt": target_date}
    if rep_nation_code:
        params["repNationCd"] = rep_nation_code
    if movie_type_code:
        params["movieTypeCd"] = movie_type_code

    with get_connection() as conn:
        run_id = _start_run(conn, "KOBIS", "daily_boxoffice", params)
        try:
            payload, status_code, request_url = _request_json(KOBIS_DAILY_BOXOFFICE_ENDPOINT, params)
            _store_response(conn, run_id, "KOBIS", KOBIS_DAILY_BOXOFFICE_ENDPOINT, request_url, status_code, payload)
            rows = payload.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
            count = 0
            for item in rows:
                _upsert_kobis_daily_boxoffice(conn, target_date, item)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} KOBIS daily rows collected")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kobis_movie_list(
    year: int | None = None,
    movie_name: str | None = None,
    current_page: int = 1,
    item_per_page: int = 100,
    open_start_date: str | None = None,
    open_end_date: str | None = None,
    rep_nation_code: str | None = None,
    movie_type_code: str | None = None,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kobis_api_key:
        raise CollectionError("KOBIS_API_KEY 환경변수가 필요합니다.")

    params: dict[str, Any] = {
        "key": config.kobis_api_key,
        "curPage": current_page,
        "itemPerPage": item_per_page,
    }
    if year:
        params["prdtStartYear"] = year
        params["prdtEndYear"] = year
    if movie_name:
        params["movieNm"] = movie_name
    if open_start_date:
        params["openStartDt"] = open_start_date
    if open_end_date:
        params["openEndDt"] = open_end_date
    if rep_nation_code:
        params["repNationCd"] = rep_nation_code
    if movie_type_code:
        params["movieTypeCd"] = movie_type_code

    with get_connection() as conn:
        run_id = _start_run(conn, "KOBIS", "movie_list", params)
        try:
            payload, status_code, request_url = _request_json(KOBIS_MOVIE_LIST_ENDPOINT, params)
            _store_response(conn, run_id, "KOBIS", KOBIS_MOVIE_LIST_ENDPOINT, request_url, status_code, payload)
            rows = payload.get("movieListResult", {}).get("movieList", [])
            count = 0
            for item in rows:
                _upsert_kobis_movie_list(conn, item)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} KOBIS movie list rows collected")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kobis_movie_info(
    movie_code: str,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    if not config.kobis_api_key:
        raise CollectionError("KOBIS_API_KEY 환경변수가 필요합니다.")
    if not movie_code:
        raise CollectionError("movie_code가 필요합니다.")

    params = {"key": config.kobis_api_key, "movieCd": movie_code}
    with get_connection() as conn:
        run_id = _start_run(conn, "KOBIS", "movie_info", params)
        try:
            payload, status_code, request_url = _request_json(KOBIS_MOVIE_INFO_ENDPOINT, params)
            _store_response(conn, run_id, "KOBIS", KOBIS_MOVIE_INFO_ENDPOINT, request_url, status_code, payload)
            movie_info = payload.get("movieInfoResult", {}).get("movieInfo")
            if not isinstance(movie_info, dict):
                raise CollectionError(f"KOBIS movie info not found: {movie_code}")
            _upsert_kobis_movie_detail(conn, movie_info)
            _finish_run(conn, run_id, "completed", 1, f"KOBIS movie info collected: {movie_code}")
            conn.commit()
            return 1
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def collect_kobis_movie_details_from_staging(
    limit: int = 100,
    missing_only: bool = True,
    config: CollectionConfig | None = None,
) -> int:
    query = """
        SELECT movie_code FROM staging_kobis_movie_list
        UNION
        SELECT movie_code FROM staging_kobis_daily_boxoffice
        ORDER BY movie_code
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(query, (limit,)).fetchall()
        existing = set()
        if missing_only:
            existing = {
                row["movie_code"]
                for row in conn.execute("SELECT movie_code FROM staging_kobis_movie_details").fetchall()
            }
    count = 0
    for row in rows:
        movie_code = row["movie_code"]
        if missing_only and movie_code in existing:
            continue
        count += collect_kobis_movie_info(movie_code, config=config)
    return count


def aggregate_kobis_yearly_boxoffice(year: int) -> int:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ? AS year,
                movie_code,
                movie_name,
                MAX(open_date) AS open_date,
                SUM(sales_amount) AS sales_amount,
                SUM(audience_count) AS audience_count,
                MAX(screen_count) AS screen_count,
                SUM(show_count) AS show_count,
                COUNT(*) AS days_count,
                MIN(target_date) AS first_seen_date,
                MAX(target_date) AS last_seen_date
            FROM staging_kobis_daily_boxoffice
            WHERE target_date BETWEEN ? AND ?
            GROUP BY movie_code, movie_name
            ORDER BY audience_count DESC
            """,
            (year, f"{year}0101", f"{year}1231"),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO staging_kobis_yearly_boxoffice (
                    year, movie_code, movie_name, normalized_title, open_date,
                    sales_amount, audience_count, screen_count, show_count,
                    days_count, first_seen_date, last_seen_date, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["year"]),
                    row["movie_code"],
                    row["movie_name"],
                    normalize_title(row["movie_name"]),
                    row["open_date"],
                    int(row["sales_amount"] or 0),
                    int(row["audience_count"] or 0),
                    int(row["screen_count"] or 0),
                    int(row["show_count"] or 0),
                    int(row["days_count"] or 0),
                    row["first_seen_date"],
                    row["last_seen_date"],
                    dumps_json(dict(row)),
                ),
            )
        conn.commit()
        return len(rows)


def import_kobis_yearly_totals_csv(csv_path: Path | str) -> int:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    with get_connection() as conn:
        run_id = _start_run(conn, "KOBIS", "yearly_totals_csv", {"path": str(path)})
        count = 0
        try:
            for row in rows:
                year = _required_int(row, "year")
                total_sales = _required_int(row, "total_sales", "totalSales", "총매출액")
                total_audience = _required_int(row, "total_audience", "totalAudience", "총관객수")
                if total_audience <= 0:
                    raise CollectionError(f"{year} total_audience must be positive")
                average_ticket_price = round(total_sales / total_audience)
                source_type = row.get("source_type") or row.get("sourceType") or "kobis_derived"
                raw_json = dumps_json(row)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO staging_kobis_yearly_totals (
                        year, total_sales, total_audience, average_ticket_price,
                        source_type, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (year, total_sales, total_audience, average_ticket_price, source_type, raw_json),
                )
                for table in ("ticket_prices", "history_ticket_prices"):
                    conn.execute(
                        f"""
                        INSERT OR REPLACE INTO {table} (
                            year, average_ticket_price, perceived_ticket_price,
                            premium_format_multiplier, audience_price_sensitivity,
                            source_type
                        ) VALUES (?, ?, ?, 1.0, 50, ?)
                        """,
                        (year, average_ticket_price, average_ticket_price, source_type),
                    )
                _upsert_market_yearly_stats_from_sources(conn, year)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} yearly ticket price rows imported")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", count, str(exc))
            conn.commit()
            raise


def build_ticket_prices_from_yearly_totals(year: int | None = None) -> int:
    with get_connection() as conn:
        params: list[Any] = []
        query = """
            SELECT year, total_sales, total_audience, source_type, raw_json
            FROM staging_kobis_yearly_totals
        """
        if year:
            query += " WHERE year = ?"
            params.append(year)
        query += " ORDER BY year"
        rows = conn.execute(query, params).fetchall()
        count = 0
        for row in rows:
            total_audience = int(row["total_audience"] or 0)
            if total_audience <= 0:
                continue
            average_ticket_price = round(int(row["total_sales"] or 0) / total_audience)
            _upsert_ticket_price(conn, int(row["year"]), average_ticket_price, row["source_type"] or "kobis_derived")
            _upsert_market_yearly_stats_from_sources(conn, int(row["year"]))
            count += 1
        conn.commit()
        return count


def build_ticket_prices_from_daily_boxoffice(year: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(sales_amount) AS total_sales,
                SUM(audience_count) AS total_audience
            FROM staging_kobis_daily_boxoffice
            WHERE target_date BETWEEN ? AND ?
            """,
            (f"{year}0101", f"{year}1231"),
        ).fetchone()
        total_sales = int(row["total_sales"] or 0) if row else 0
        total_audience = int(row["total_audience"] or 0) if row else 0
        if total_audience <= 0:
            return 0
        average_ticket_price = round(total_sales / total_audience)
        raw_json = dumps_json({"note": "Derived from collected KOBIS daily rows; complete only if all rows were collected."})
        conn.execute(
            """
            INSERT OR REPLACE INTO staging_kobis_yearly_totals (
                year, total_sales, total_audience, average_ticket_price,
                source_type, raw_json
            ) VALUES (?, ?, ?, ?, 'kobis_daily_derived_partial', ?)
            """,
            (year, total_sales, total_audience, average_ticket_price, raw_json),
        )
        _upsert_ticket_price(conn, year, average_ticket_price, "kobis_daily_derived_partial")
        conn.commit()
        return 1


def import_kofic_actors200_csv(csv_path: Path | str) -> int:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    with get_connection() as conn:
        run_id = _start_run(conn, "KOFIC", "actors200_csv", {"path": str(path)})
        count = 0
        try:
            for row in rows:
                name_ko = row.get("name_ko") or row.get("nameKo") or row.get("배우명")
                if not name_ko:
                    raise CollectionError("actors200 CSV에는 name_ko/nameKo/배우명 중 하나가 필요합니다.")
                name_en = row.get("name_en") or row.get("nameEn") or row.get("영문명")
                actor_id = row.get("id") or _actor_id(name_ko, name_en)
                works = _split_list(row.get("representative_works") or row.get("representativeWorks") or row.get("대표작"))
                tags = _split_list(row.get("global_tags") or row.get("globalTags") or row.get("해외인지도태그"))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO staging_kofic_actors200 (
                        id, name_ko, name_en, representative_works_json,
                        introduction, global_tags_json, source_url, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        actor_id,
                        name_ko,
                        name_en,
                        dumps_json(works),
                        row.get("introduction") or row.get("소개문"),
                        dumps_json(tags),
                        row.get("source_url") or row.get("sourceUrl") or row.get("출처"),
                        dumps_json(row),
                    ),
                )
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} Actors 200 rows imported")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", count, str(exc))
            conn.commit()
            raise


def import_kofic_report_directory(
    downloads_dir: Path | str,
    *,
    output_dir: Path | str | None = None,
    year_from: int = 2000,
    year_to: int = 2026,
    limit: int | None = None,
    promote_events: bool = False,
) -> int:
    """Import local KOFIC settlement/statistics files into auditable staging tables.

    Full extracted report text is written to data/imported by default and ignored by git.
    Staging rows keep only short snippets, candidate metrics, and candidate events.
    """

    root = Path(downloads_dir)
    if not root.exists():
        raise CollectionError(f"KOFIC report directory not found: {root}")
    text_dir = Path(output_dir) if output_dir else BASE_DIR / "data" / "imported" / "kofic_text"
    files = _discover_kofic_report_files(root, year_from, year_to)
    if limit is not None:
        files = files[:limit]

    with get_connection() as conn:
        run_id = _start_run(
            conn,
            "KOFIC",
            "local_report_import",
            {
                "downloads_dir": str(root),
                "output_dir": str(text_dir),
                "year_from": year_from,
                "year_to": year_to,
                "limit": limit,
                "promote_events": promote_events,
            },
        )
        file_count = 0
        metric_count = 0
        event_count = 0
        try:
            for path in files:
                report_year = _infer_year_from_name(path.name)
                file_id = _kofic_report_file_id(path)
                extracted = _extract_kofic_report_text(path, text_dir, file_id, report_year)
                conn.execute("DELETE FROM staging_kofic_industry_metrics WHERE source_file_id = ?", (file_id,))
                conn.execute("DELETE FROM staging_kofic_report_events WHERE source_file_id = ?", (file_id,))
                _upsert_kofic_report_file(conn, path, file_id, report_year, extracted)
                file_count += 1

                text = extracted.get("text") or ""
                if report_year and text:
                    for metric in _extract_kofic_metric_candidates(text, report_year, file_id):
                        _upsert_kofic_metric_candidate(conn, metric)
                        metric_count += 1
                    for event in _extract_kofic_event_candidates(text, report_year, file_id):
                        _upsert_kofic_report_event(conn, event)
                        if promote_events:
                            _promote_kofic_report_event(conn, event)
                        event_count += 1

            market_stat_count = _promote_market_yearly_stats(conn, year_from=year_from, year_to=year_to)
            _finish_run(
                conn,
                run_id,
                "completed",
                file_count,
                f"{file_count} KOFIC report files indexed, {metric_count} metric candidates, "
                f"{event_count} event candidates, {market_stat_count} market yearly stats promoted",
            )
            conn.commit()
            return file_count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", file_count, str(exc))
            conn.commit()
            raise


def promote_market_yearly_stats(year_from: int | None = None, year_to: int | None = None) -> int:
    with get_connection() as conn:
        count = _promote_market_yearly_stats(conn, year_from=year_from, year_to=year_to)
        conn.commit()
        return count


def _promote_market_yearly_stats(
    conn: Any,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
) -> int:
    years = _market_years_from_sources(conn, year_from=year_from, year_to=year_to)
    count = 0
    for year in years:
        if _upsert_market_yearly_stats_from_sources(conn, year):
            count += 1
    return count


def _market_years_from_sources(
    conn: Any,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[int]:
    years: set[int] = set()
    for table, column in (
        ("staging_kobis_yearly_totals", "year"),
        ("staging_kofic_industry_metrics", "report_year"),
        ("market_yearly_stats", "year"),
    ):
        rows = conn.execute(f"SELECT DISTINCT {column} AS year FROM {table} WHERE {column} IS NOT NULL").fetchall()
        years.update(int(row["year"]) for row in rows)
    if year_from is not None:
        years = {year for year in years if year >= year_from}
    if year_to is not None:
        years = {year for year in years if year <= year_to}
    return sorted(years)


def _upsert_market_yearly_stats_from_sources(conn: Any, year: int) -> bool:
    current_row = conn.execute("SELECT * FROM market_yearly_stats WHERE year = ?", (year,)).fetchone()
    values = dict(current_row) if current_row else {"year": year}
    for field in MARKET_YEARLY_METRIC_MAP:
        values.setdefault(field, None)
    values.setdefault("source_file", None)

    kobis_row = conn.execute("SELECT * FROM staging_kobis_yearly_totals WHERE year = ?", (year,)).fetchone()
    if kobis_row:
        values["total_audience"] = _prefer_value(values.get("total_audience"), kobis_row["total_audience"])
        values["total_revenue"] = _prefer_value(values.get("total_revenue"), kobis_row["total_sales"])

    best_metrics = _best_market_metrics(conn, year)
    for field, metric_ids in MARKET_YEARLY_METRIC_MAP.items():
        metric = _first_metric(best_metrics, metric_ids)
        if metric and metric.get("value") is not None:
            values[field] = _market_metric_value(field, float(metric["value"]))

    source_file = _market_source_file(conn, year, best_metrics)
    if source_file:
        values["source_file"] = source_file
    elif kobis_row and not values.get("source_file"):
        values["source_file"] = "staging_kobis_yearly_totals"

    has_payload = any(values.get(field) is not None for field in MARKET_YEARLY_METRIC_MAP)
    if not has_payload:
        return False

    conn.execute(
        """
        INSERT OR REPLACE INTO market_yearly_stats (
            year, total_audience, korean_film_audience, foreign_film_audience,
            total_revenue, non_theatrical_market_size, theater_count, screen_count,
            avg_production_cost, avg_total_cost, estimated_profit_rate,
            export_amount, source_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            year,
            values.get("total_audience"),
            values.get("korean_film_audience"),
            values.get("foreign_film_audience"),
            values.get("total_revenue"),
            values.get("non_theatrical_market_size"),
            values.get("theater_count"),
            values.get("screen_count"),
            values.get("avg_production_cost"),
            values.get("avg_total_cost"),
            values.get("estimated_profit_rate"),
            values.get("export_amount"),
            values.get("source_file"),
        ),
    )
    return True


def _prefer_value(current: Any, candidate: Any) -> Any:
    return candidate if candidate is not None else current


def _best_market_metrics(conn: Any, year: int) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM staging_kofic_industry_metrics
        WHERE report_year = ? AND value IS NOT NULL
        ORDER BY confidence DESC, collected_at DESC
        """,
        (year,),
    ).fetchall()
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        metric = dict(row)
        best.setdefault(str(metric["metric_id"]), metric)
    return best


def _first_metric(
    metrics: dict[str, dict[str, Any]],
    metric_ids: tuple[str, ...],
) -> dict[str, Any] | None:
    for metric_id in metric_ids:
        if metric_id in metrics:
            return metrics[metric_id]
    return None


def _market_metric_value(field: str, value: float) -> int | float:
    if field in MARKET_YEARLY_INTEGER_FIELDS:
        return int(round(value))
    return value


def _market_source_file(conn: Any, year: int, metrics: dict[str, dict[str, Any]]) -> str | None:
    source_ids = {
        str(metric["source_file_id"])
        for metric in metrics.values()
        if metric.get("source_file_id")
    }
    if not source_ids:
        return None
    placeholders = ", ".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT file_name
        FROM staging_kofic_report_files
        WHERE id IN ({placeholders}) AND report_year = ?
        ORDER BY file_name
        """,
        (*sorted(source_ids), year),
    ).fetchall()
    names = [row["file_name"] for row in rows if row["file_name"]]
    return "; ".join(names[:5]) if names else "; ".join(sorted(source_ids)[:5])


def collect_wikidata_target(
    target_id: str,
    *,
    limit: int = 100,
    config: CollectionConfig | None = None,
) -> int:
    target = _get_wikidata_target_query(target_id, limit)
    return collect_wikidata_sparql(
        target_id,
        target["query"],
        entity_type=target["entity_type"],
        config=config,
    )


def collect_wikidata_sparql(
    target_id: str,
    query: str,
    *,
    entity_type: str | None = None,
    config: CollectionConfig | None = None,
) -> int:
    config = config or CollectionConfig.from_env()
    params = {"query": query, "format": "json"}
    endpoint = config.wikidata_sparql_endpoint or WIKIDATA_SPARQL_ENDPOINT
    with get_connection() as conn:
        run_id = _start_run(
            conn,
            "Wikidata",
            "sparql",
            {"target_id": target_id, "entity_type": entity_type, "endpoint": endpoint},
        )
        try:
            payload, status_code, request_url = _request_json(endpoint, params)
            _store_response(conn, run_id, "Wikidata", endpoint, request_url, status_code, payload)
            rows = _extract_wikidata_bindings(payload)
            conn.execute("DELETE FROM staging_wikidata_sparql_results WHERE target_id = ?", (target_id,))
            count = 0
            for row in rows:
                normalized = _normalize_wikidata_binding(target_id, entity_type, row, request_url)
                _upsert_wikidata_result(conn, normalized)
                _upsert_wikidata_canonical(conn, normalized)
                count += 1
            _finish_run(conn, run_id, "completed", count, f"{count} Wikidata SPARQL rows collected")
            conn.commit()
            return count
        except Exception as exc:
            _finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise


def _request_json(endpoint: str, params: dict[str, Any]) -> tuple[Any, int, str]:
    public_params = {key: value for key, value in params.items() if value not in (None, "")}
    request_url = f"{endpoint}?{urlencode(public_params)}"
    request = Request(request_url, headers={"User-Agent": "ChungmuroTycoonDataCollector/0.1"})
    raw = ""
    status_code = 0
    last_error: Exception | None = None
    timeout = 60 if "query.wikidata.org" in endpoint else 20
    for attempt in range(3):
        try:
            with _open_request(request, timeout=timeout) as response:
                status_code = getattr(response, "status", 200)
                raw = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            raise CollectionError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}") from exc
        except TimeoutError as exc:
            last_error = exc
        except URLError as exc:
            last_error = exc
        except OSError as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    else:
        if isinstance(last_error, URLError):
            raise CollectionError(f"Network error: {last_error.reason}") from last_error
        raise CollectionError(f"Network timeout: {last_error}") from last_error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"JSON response expected from {endpoint}") from exc
    return payload, int(status_code), _redact_url(request_url)


def _open_request(request: Request, timeout: int = 20) -> Any:
    try:
        return urlopen(request, timeout=timeout)
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc.reason):
            raise
        context = _certifi_ssl_context()
        if not context:
            raise
        return urlopen(request, timeout=timeout, context=context)


def _certifi_ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _start_run(conn: Any, source: str, job_type: str, params: dict[str, Any]) -> int:
    safe_params = _redact_mapping(params)
    cursor = conn.execute(
        """
        INSERT INTO collection_runs (source, job_type, params_json)
        VALUES (?, ?, ?)
        """,
        (source, job_type, dumps_json(safe_params)),
    )
    return int(cursor.lastrowid)


def _finish_run(conn: Any, run_id: int, status: str, rows_collected: int, message: str) -> None:
    conn.execute(
        """
        UPDATE collection_runs
        SET status = ?, finished_at = CURRENT_TIMESTAMP,
            rows_collected = ?, message = ?
        WHERE id = ?
        """,
        (status, rows_collected, message, run_id),
    )


def _store_response(
    conn: Any,
    run_id: int,
    source: str,
    endpoint: str,
    request_url: str,
    status_code: int,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO collection_api_responses (
            run_id, source, endpoint, request_url, status_code, response_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, source, endpoint, request_url, status_code, dumps_json(payload)),
    )


def _get_wikidata_target_query(target_id: str, limit: int) -> dict[str, str]:
    limit = max(1, min(int(limit), 500))
    prefix = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
"""
    if target_id == "korean-films":
        query = f"""
{prefix}
SELECT ?item ?labelKo ?labelEn ?descriptionKo ?descriptionEn ?releaseDate
       (SAMPLE(?koArticleRaw) AS ?koArticle)
       (SAMPLE(?enArticleRaw) AS ?enArticle)
       (GROUP_CONCAT(DISTINCT ?directorToken; separator="|") AS ?directors)
       (GROUP_CONCAT(DISTINCT ?actorToken; separator="|") AS ?actors)
       (GROUP_CONCAT(DISTINCT ?genreToken; separator="|") AS ?genres)
       (GROUP_CONCAT(DISTINCT ?countryToken; separator="|") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?awardToken; separator="|") AS ?awards)
       (SAMPLE(?imdb) AS ?imdbId)
WHERE {{
  {{
    SELECT ?item ?releaseDate WHERE {{
      ?item wdt:P31/wdt:P279* wd:Q11424;
            wdt:P495 wd:Q884;
            wdt:P577 ?releaseDate.
      FILTER(YEAR(?releaseDate) >= 1980 && ?releaseDate <= NOW())
    }}
    ORDER BY DESC(?releaseDate)
    LIMIT {limit}
  }}
  OPTIONAL {{ ?item wdt:P57 ?director.
             ?director rdfs:label ?directorLabel FILTER(LANG(?directorLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?director), "entity/"), "::", STR(?directorLabel)) AS ?directorToken) }}
  OPTIONAL {{ ?item wdt:P161 ?actor.
             ?actor rdfs:label ?actorLabel FILTER(LANG(?actorLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?actor), "entity/"), "::", STR(?actorLabel)) AS ?actorToken) }}
  OPTIONAL {{ ?item wdt:P136 ?genre.
             ?genre rdfs:label ?genreLabel FILTER(LANG(?genreLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?genre), "entity/"), "::", STR(?genreLabel)) AS ?genreToken) }}
  OPTIONAL {{ ?item wdt:P495 ?country.
             ?country rdfs:label ?countryLabel FILTER(LANG(?countryLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?country), "entity/"), "::", STR(?countryLabel)) AS ?countryToken) }}
  OPTIONAL {{ ?item wdt:P166 ?award.
             ?award rdfs:label ?awardLabel FILTER(LANG(?awardLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?award), "entity/"), "::", STR(?awardLabel)) AS ?awardToken) }}
  OPTIONAL {{ ?item wdt:P345 ?imdb. }}
  OPTIONAL {{ ?koArticleRaw schema:about ?item; schema:isPartOf <https://ko.wikipedia.org/>. }}
  OPTIONAL {{ ?enArticleRaw schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}
  OPTIONAL {{ ?item rdfs:label ?labelKo FILTER(LANG(?labelKo)="ko") }}
  OPTIONAL {{ ?item rdfs:label ?labelEn FILTER(LANG(?labelEn)="en") }}
  OPTIONAL {{ ?item schema:description ?descriptionKo FILTER(LANG(?descriptionKo)="ko") }}
  OPTIONAL {{ ?item schema:description ?descriptionEn FILTER(LANG(?descriptionEn)="en") }}
}}
GROUP BY ?item ?labelKo ?labelEn ?descriptionKo ?descriptionEn ?releaseDate
ORDER BY DESC(?releaseDate)
LIMIT {limit}
"""
        return {"entity_type": "film", "query": query}
    if target_id == "korean-film-people":
        query = f"""
{prefix}
SELECT ?item ?labelKo ?labelEn ?descriptionKo ?descriptionEn ?birthDate ?deathDate
       (SAMPLE(?koArticleRaw) AS ?koArticle)
       (SAMPLE(?enArticleRaw) AS ?enArticle)
       (GROUP_CONCAT(DISTINCT ?occupationToken; separator="|") AS ?occupations)
       (GROUP_CONCAT(DISTINCT ?workToken; separator="|") AS ?workRelationships)
       (SAMPLE(?imdb) AS ?imdbId)
WHERE {{
  VALUES ?occupation {{ wd:Q33999 wd:Q10800557 wd:Q2526255 wd:Q28389 wd:Q3282637 }}
  {{
    SELECT DISTINCT ?item ?birthDate ?deathDate WHERE {{
      VALUES ?occupation {{ wd:Q33999 wd:Q10800557 wd:Q2526255 wd:Q28389 wd:Q3282637 }}
      ?item wdt:P31 wd:Q5;
            wdt:P27 wd:Q884;
            wdt:P106 ?occupation.
      OPTIONAL {{ ?item wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?item wdt:P570 ?deathDate. }}
    }}
    ORDER BY ?item
    LIMIT {limit}
  }}
  OPTIONAL {{ ?item wdt:P106 ?occupation. }}
  OPTIONAL {{ ?item wdt:P569 ?birthDate. }}
  OPTIONAL {{ ?item wdt:P570 ?deathDate. }}
  OPTIONAL {{ ?item wdt:P345 ?imdb. }}
  OPTIONAL {{ ?occupation rdfs:label ?occupationLabel FILTER(LANG(?occupationLabel) IN ("ko", "en"))
             BIND(CONCAT(STRAFTER(STR(?occupation), "entity/"), "::", STR(?occupationLabel)) AS ?occupationToken) }}
  OPTIONAL {{ ?directedWork wdt:P57 ?item.
             ?directedWork rdfs:label ?directedWorkLabel FILTER(LANG(?directedWorkLabel) IN ("ko", "en"))
             BIND(CONCAT("director::", STRAFTER(STR(?directedWork), "entity/"), "::", STR(?directedWorkLabel)) AS ?workToken) }}
  OPTIONAL {{ ?actedWork wdt:P161 ?item.
             ?actedWork rdfs:label ?actedWorkLabel FILTER(LANG(?actedWorkLabel) IN ("ko", "en"))
             BIND(CONCAT("actor::", STRAFTER(STR(?actedWork), "entity/"), "::", STR(?actedWorkLabel)) AS ?workToken) }}
  OPTIONAL {{ ?writtenWork wdt:P58 ?item.
             ?writtenWork rdfs:label ?writtenWorkLabel FILTER(LANG(?writtenWorkLabel) IN ("ko", "en"))
             BIND(CONCAT("screenwriter::", STRAFTER(STR(?writtenWork), "entity/"), "::", STR(?writtenWorkLabel)) AS ?workToken) }}
  OPTIONAL {{ ?producedWork wdt:P162 ?item.
             ?producedWork rdfs:label ?producedWorkLabel FILTER(LANG(?producedWorkLabel) IN ("ko", "en"))
             BIND(CONCAT("producer::", STRAFTER(STR(?producedWork), "entity/"), "::", STR(?producedWorkLabel)) AS ?workToken) }}
  OPTIONAL {{ ?koArticleRaw schema:about ?item; schema:isPartOf <https://ko.wikipedia.org/>. }}
  OPTIONAL {{ ?enArticleRaw schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}
  OPTIONAL {{ ?item rdfs:label ?labelKo FILTER(LANG(?labelKo)="ko") }}
  OPTIONAL {{ ?item rdfs:label ?labelEn FILTER(LANG(?labelEn)="en") }}
  OPTIONAL {{ ?item schema:description ?descriptionKo FILTER(LANG(?descriptionKo)="ko") }}
  OPTIONAL {{ ?item schema:description ?descriptionEn FILTER(LANG(?descriptionEn)="en") }}
}}
GROUP BY ?item ?labelKo ?labelEn ?descriptionKo ?descriptionEn ?birthDate ?deathDate
ORDER BY ?labelKo
LIMIT {limit}
"""
        return {"entity_type": "person", "query": query}
    raise CollectionError(f"Unknown Wikidata target: {target_id}")


def _extract_wikidata_bindings(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise CollectionError("Wikidata SPARQL response must be a JSON object.")
    bindings = payload.get("results", {}).get("bindings")
    if not isinstance(bindings, list):
        raise CollectionError("Wikidata SPARQL bindings were not found in the response.")
    return [row for row in bindings if isinstance(row, dict)]


def _normalize_wikidata_binding(
    target_id: str,
    entity_type: str | None,
    binding: dict[str, Any],
    source_url: str,
) -> dict[str, Any]:
    qid = _wikidata_qid(_binding_value(binding, "item"))
    release_date = _binding_value(binding, "releaseDate")
    birth_date = _binding_value(binding, "birthDate")
    death_date = _binding_value(binding, "deathDate")
    date_value = (
        release_date
        or birth_date
        or _binding_value(binding, "date")
    )
    imdb_id = _binding_value(binding, "imdbId")
    wikipedia_url = _binding_value(binding, "koArticle") or _binding_value(binding, "enArticle")
    external_ids = {
        key: _binding_value(binding, key)
        for key in ("imdbId", "tmdbId", "viafId")
        if _binding_value(binding, key)
    }
    directors = _split_entity_tokens(_binding_value(binding, "directors"))
    actors = _split_entity_tokens(_binding_value(binding, "actors"))
    genres = _split_entity_tokens(_binding_value(binding, "genres"))
    countries = _split_entity_tokens(_binding_value(binding, "countries"))
    awards = _split_entity_tokens(_binding_value(binding, "awards"))
    work_relationships = _split_work_relationship_tokens(_binding_value(binding, "workRelationships"))
    linked_entities = {
        "directors": directors,
        "actors": actors,
        "genres": genres,
        "countries": countries,
        "awards": awards,
        "workRelationships": work_relationships,
    }
    occupations = _split_entity_tokens(_binding_value(binding, "occupations"))
    row_id = _stable_id("wikidata", target_id, qid or dumps_json(binding)[:120])
    return {
        "id": row_id,
        "target_id": target_id,
        "entity_type": entity_type,
        "qid": qid,
        "label_ko": _binding_value(binding, "labelKo") or _binding_value(binding, "itemLabel"),
        "label_en": _binding_value(binding, "labelEn"),
        "title_ko": _binding_value(binding, "labelKo") or _binding_value(binding, "itemLabel"),
        "title_en": _binding_value(binding, "labelEn"),
        "name_ko": _binding_value(binding, "labelKo") or _binding_value(binding, "itemLabel"),
        "name_en": _binding_value(binding, "labelEn"),
        "description_ko": _binding_value(binding, "descriptionKo"),
        "description_en": _binding_value(binding, "descriptionEn"),
        "date_value": date_value,
        "year": _year_from_date(date_value),
        "release_date": release_date,
        "birth_date": birth_date,
        "death_date": death_date,
        "imdb_id": imdb_id,
        "wikipedia_url": wikipedia_url,
        "director_json": directors,
        "actor_json": actors,
        "genre_json": genres,
        "country_json": countries,
        "awards_json": awards,
        "work_relationships_json": work_relationships,
        "occupation_json": occupations,
        "external_ids_json": external_ids,
        "linked_entities_json": linked_entities,
        "raw_json": binding,
        "source_url": source_url,
    }


def _upsert_wikidata_result(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_wikidata_sparql_results (
            id, target_id, entity_type, qid, label_ko, label_en,
            description_ko, description_en, date_value, year,
            release_date, birth_date, death_date, imdb_id, wikipedia_url,
            director_json, actor_json, genre_json, country_json, awards_json,
            work_relationships_json,
            occupation_json, external_ids_json, linked_entities_json,
            raw_json, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["target_id"],
            row["entity_type"],
            row["qid"],
            row["label_ko"],
            row["label_en"],
            row["description_ko"],
            row["description_en"],
            row["date_value"],
            row["year"],
            row["release_date"],
            row["birth_date"],
            row["death_date"],
            row["imdb_id"],
            row["wikipedia_url"],
            dumps_json(row["director_json"]),
            dumps_json(row["actor_json"]),
            dumps_json(row["genre_json"]),
            dumps_json(row["country_json"]),
            dumps_json(row["awards_json"]),
            dumps_json(row["work_relationships_json"]),
            dumps_json(row["occupation_json"]),
            dumps_json(row["external_ids_json"]),
            dumps_json(row["linked_entities_json"]),
            dumps_json(row["raw_json"]),
            row["source_url"],
        ),
    )


def _upsert_wikidata_canonical(conn: Any, row: dict[str, Any]) -> None:
    if row.get("entity_type") == "film":
        _upsert_wikidata_movie(conn, row)
    elif row.get("entity_type") == "person":
        _upsert_wikidata_person(conn, row)


def _upsert_wikidata_movie(conn: Any, row: dict[str, Any]) -> None:
    qid = row.get("qid")
    if not qid:
        return
    title_ko = row.get("title_ko")
    title_en = row.get("title_en")
    conn.execute(
        """
        INSERT OR REPLACE INTO wikidata_movies (
            qid, title_ko, title_en, normalized_title_ko, normalized_title_en,
            release_date, year, director_json, actor_json, genre_json,
            country_json, awards_json, imdb_id, wikipedia_url, match_status,
            source_priority, raw_json, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qid,
            title_ko,
            title_en,
            normalize_title(title_ko),
            normalize_title(title_en),
            row.get("release_date"),
            row.get("year"),
            dumps_json(row.get("director_json", [])),
            dumps_json(row.get("actor_json", [])),
            dumps_json(row.get("genre_json", [])),
            dumps_json(row.get("country_json", [])),
            dumps_json(row.get("awards_json", [])),
            row.get("imdb_id"),
            row.get("wikipedia_url"),
            "unmatched",
            "supplemental_wikidata",
            dumps_json(row.get("raw_json")),
            row.get("source_url"),
        ),
    )


def _upsert_wikidata_person(conn: Any, row: dict[str, Any]) -> None:
    qid = row.get("qid")
    if not qid:
        return
    name_ko = row.get("name_ko")
    name_en = row.get("name_en")
    conn.execute(
        """
        INSERT OR REPLACE INTO wikidata_people (
            qid, name_ko, name_en, normalized_name_ko, normalized_name_en,
            birth_date, birth_year, death_date, death_year, occupation_json,
            work_relationships_json, imdb_id, wikipedia_url, match_status,
            source_priority, raw_json, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qid,
            name_ko,
            name_en,
            normalize_title(name_ko),
            normalize_title(name_en),
            row.get("birth_date"),
            _year_from_date(row.get("birth_date")),
            row.get("death_date"),
            _year_from_date(row.get("death_date")),
            dumps_json(row.get("occupation_json", [])),
            dumps_json(row.get("work_relationships_json", [])),
            row.get("imdb_id"),
            row.get("wikipedia_url"),
            "unmatched",
            "supplemental_wikidata",
            dumps_json(row.get("raw_json")),
            row.get("source_url"),
        ),
    )


def _binding_value(binding: dict[str, Any], key: str) -> str | None:
    cell = binding.get(key)
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    return str(value) if value not in (None, "") else None


def _wikidata_qid(uri: str | None) -> str | None:
    if not uri:
        return None
    match = re.search(r"/(Q[0-9]+)$", uri)
    return match.group(1) if match else None


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _split_entity_tokens(value: str | None) -> list[dict[str, str | None]]:
    entities: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for token in _split_pipe(value):
        qid: str | None = None
        label = token
        if "::" in token:
            qid_part, label_part = token.split("::", 1)
            qid = qid_part or None
            label = label_part
        key = (qid, label)
        if key in seen:
            continue
        seen.add(key)
        entities.append({"qid": qid, "label": label})
    return entities


def _split_work_relationship_tokens(value: str | None) -> list[dict[str, str | None]]:
    relationships: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for token in _split_pipe(value):
        role: str | None = None
        qid: str | None = None
        title = token
        parts = token.split("::", 2)
        if len(parts) == 3:
            role, qid, title = parts
        elif len(parts) == 2:
            qid, title = parts
        key = (role, qid, title)
        if key in seen:
            continue
        seen.add(key)
        relationships.append({"role": role, "qid": qid, "title": title})
    return relationships


def _year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"([12][0-9]{3})", value)
    return int(match.group(1)) if match else None


def _discover_kofic_report_files(root: Path, year_from: int, year_to: int) -> list[Path]:
    paths: list[Path] = []
    for path in root.iterdir():
        if not path.is_file():
            continue
        name = unicodedata.normalize("NFC", path.name)
        suffix = path.suffix.lower()
        year = _infer_year_from_name(name)
        if year is None or year < year_from or year > year_to:
            continue
        if suffix not in KOFIC_REPORT_EXTENSIONS:
            continue
        if not any(marker in name for marker in KOFIC_REPORT_MARKERS):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: (_infer_year_from_name(item.name) or 9999, unicodedata.normalize("NFC", item.name)))


def _infer_year_from_name(name: str) -> int | None:
    normalized = unicodedata.normalize("NFC", name)
    year_labels = [int(match.group(1)) for match in re.finditer(r"(19[8-9][0-9]|20[0-2][0-9])\s*년", normalized)]
    if year_labels:
        return year_labels[-1]
    match = re.search(r"(19[8-9][0-9]|20[0-2][0-9])", normalized)
    if not match:
        return None
    return int(match.group(1))


def _kofic_report_file_id(path: Path) -> str:
    return f"kofic_report_{_sha1_file(path)[:16]}"


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_kofic_report_text(
    path: Path,
    output_dir: Path,
    file_id: str,
    report_year: int | None,
) -> dict[str, Any]:
    suffix = _detect_kofic_report_extension(path)
    text = ""
    page_count = None
    sheet_count = None
    status = "unsupported_file_type"
    notes = ""

    if suffix == ".pdf":
        text, page_count, status, notes = _extract_pdf_report_text(path)
    elif suffix in {".xls", ".xlsx"}:
        text, sheet_count, status, notes = _extract_excel_report_text(path)
    elif suffix == ".hwp":
        text, page_count, status, notes = _extract_hwp_report_text(path)

    text_path = None
    if text.strip():
        output_dir.mkdir(parents=True, exist_ok=True)
        text_file = output_dir / f"{report_year or 'unknown'}_{file_id}.txt"
        text_file.write_text(text, encoding="utf-8")
        text_path = str(text_file)

    return {
        "text": text,
        "page_count": page_count,
        "sheet_count": sheet_count,
        "extract_status": status,
        "extracted_text_path": text_path,
        "notes": notes,
    }


def _extract_pdf_report_text(path: Path) -> tuple[str, int | None, str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", None, "missing_pdf_dependency", "Install optional dependency pypdf to extract PDF report text."

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return "", len(reader.pages), "pdf_encrypted", "PDF is encrypted and could not be decrypted."
        chunks: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:  # pragma: no cover - depends on source PDF internals.
                page_text = f"[page_extract_error: {type(exc).__name__}]"
            if page_text.strip():
                chunks.append(f"\n\n[PAGE {page_number}]\n{page_text}")
        status = "extracted" if chunks else "no_text_extracted"
        return "\n".join(chunks), len(reader.pages), status, ""
    except Exception as exc:
        return "", None, "pdf_extract_failed", f"{type(exc).__name__}: {exc}"


def _extract_excel_report_text(path: Path) -> tuple[str, int | None, str, str]:
    try:
        import pandas as pd
    except ImportError:
        return "", None, "missing_excel_dependency", "Install optional dependency pandas to extract spreadsheet report text."

    try:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    except ImportError as exc:
        return "", None, "missing_excel_dependency", str(exc)
    except Exception as exc:
        return "", None, "excel_extract_failed", f"{type(exc).__name__}: {exc}"

    chunks: list[str] = []
    for sheet_name, frame in sheets.items():
        frame = frame.fillna("")
        chunks.append(f"\n\n[SHEET {sheet_name}]\n{frame.to_csv(index=False)}")
    return "\n".join(chunks), len(sheets), "extracted", ""


def _extract_hwp_report_text(path: Path) -> tuple[str, int | None, str, str]:
    try:
        import olefile
    except ImportError:
        return "", None, "missing_hwp_dependency", "Install optional dependency olefile to extract HWP text."

    try:
        with olefile.OleFileIO(str(path)) as ole:
            if not ole.exists("FileHeader") or not ole.exists("BodyText"):
                return "", None, "hwp_extract_failed", "HWP FileHeader or BodyText storage not found."
            header = ole.openstream("FileHeader").read()
            compressed = bool(int.from_bytes(header[36:40], "little") & 1) if len(header) >= 40 else False
            section_names = sorted(
                (
                    entry[1]
                    for entry in ole.listdir(streams=True)
                    if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section")
                ),
                key=lambda value: int(re.sub(r"\D", "", value) or 0),
            )
            chunks: list[str] = []
            for section_name in section_names:
                data = ole.openstream(["BodyText", section_name]).read()
                if compressed:
                    try:
                        data = zlib.decompress(data, -15)
                    except zlib.error:
                        data = zlib.decompress(data)
                section_text = _extract_hwp_text_records(data)
                if section_text.strip():
                    chunks.append(f"\n\n[HWP {section_name}]\n{section_text}")
            status = "extracted" if chunks else "no_text_extracted"
            return "\n".join(chunks), None, status, ""
    except Exception as exc:
        return "", None, "hwp_extract_failed", f"{type(exc).__name__}: {exc}"


def _extract_hwp_text_records(data: bytes) -> str:
    offset = 0
    chunks: list[str] = []
    while offset + 4 <= len(data):
        header = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > len(data):
                break
            size = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4
        payload = data[offset : offset + size]
        offset += size
        if tag_id == 67 and payload:
            text = payload.decode("utf-16le", errors="ignore")
            text = text.replace("\x00", "").strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _upsert_kofic_report_file(
    conn: Any,
    path: Path,
    file_id: str,
    report_year: int | None,
    extracted: dict[str, Any],
) -> None:
    stat = path.stat()
    sha1 = _sha1_file(path)
    raw = {
        "source_kind": "local_kofic_report",
        "path": str(path),
        "normalized_name": unicodedata.normalize("NFC", path.name),
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kofic_report_files (
            id, report_year, title, file_path, file_name, file_type, file_size,
            sha1, page_count, sheet_count, extract_status, extracted_text_path,
            notes, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            report_year,
            _report_title_from_file_name(path.name),
            str(path),
            path.name,
            _detect_kofic_report_extension(path).lstrip(".") or "unknown",
            stat.st_size,
            sha1,
            extracted.get("page_count"),
            extracted.get("sheet_count"),
            extracted.get("extract_status"),
            extracted.get("extracted_text_path"),
            extracted.get("notes"),
            dumps_json(raw),
        ),
    )


def _report_title_from_file_name(name: str) -> str:
    normalized = unicodedata.normalize("NFC", name)
    return re.sub(r"\.[^.]+$", "", normalized)


def _detect_kofic_report_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix:
        return suffix
    try:
        head = path.read_bytes()[:16]
    except OSError:
        return ""
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return ".hwp"
    if head.startswith(b"PK"):
        return ".xlsx"
    return ""


def _extract_kofic_metric_candidates(text: str, report_year: int, file_id: str) -> list[dict[str, Any]]:
    metric_rules = (
        ("total_boxoffice_sales", "극장 매출", "market", "원", "전국", ("극장 매출", "총매출", "매출액")),
        ("total_admissions", "총 관객 수", "market", "명", "전국", ("총 관객", "전체 관객", "관객 수")),
        ("korean_film_admissions", "한국영화 관객 수", "market", "명", "한국영화", ("한국영화 관객", "한국 영화 관객")),
        ("foreign_film_admissions", "외국영화 관객 수", "market", "명", "외국영화", ("외국영화 관객", "외화 관객")),
        ("korean_film_market_share", "한국영화 점유율", "market_share", "%", "한국영화", ("한국영화 점유율", "한국 영화 점유율")),
        ("average_ticket_price", "평균 관람요금", "ticket_price", "원", "전국", ("평균 관람요금", "평균 티켓", "평균 입장권")),
        ("non_theatrical_market_size", "비극장 시장 규모", "secondary_market", "원", "전국", ("극장 외 시장", "비극장 시장", "부가시장", "디지털 온라인 시장", "온라인 시장")),
        ("theater_count", "극장 수", "theater", "개", "전국", ("극장 수", "영화관 수", "상영관 수")),
        ("screen_count", "스크린 수", "theater", "개", "전국", ("스크린 수", "상영관 수")),
        ("avg_production_cost", "평균 순제작비", "production_cost", "원", "한국영화", ("평균 순제작비", "순제작비 평균", "평균 제작비")),
        ("avg_total_cost", "평균 총제작비", "production_cost", "원", "한국영화", ("평균 총제작비", "총제작비 평균", "평균 총 제작비", "평균 총비용")),
        ("estimated_profit_rate", "추정 수익률", "profitability", "%", "한국영화", ("추정 수익률", "투자수익률", "수익률", "손익률")),
        ("export_amount", "수출액", "export", "USD", "한국영화", ("수출액", "해외 수출", "완성작 수출", "한국영화 수출")),
        ("release_count", "개봉 편수", "release", "편", "전국", ("개봉 편수", "개봉작 수")),
    )
    rows: list[dict[str, Any]] = []
    for metric_id, name, category, unit, scope, keywords in metric_rules:
        found = _find_keyword_snippet(text, keywords)
        if not found:
            continue
        snippet, keyword = found
        value = _extract_number_after_keyword(snippet, keyword)
        confidence = 0.48 if value is not None else 0.34
        row_id = _stable_id("kofic_metric", file_id, metric_id, snippet[:80])
        rows.append(
            {
                "id": row_id,
                "report_year": report_year,
                "metric_id": metric_id,
                "metric_name": name,
                "metric_category": category,
                "value": value,
                "unit": unit,
                "scope": scope,
                "confidence": confidence,
                "source_file_id": file_id,
                "source_page": _infer_page_from_snippet(text, snippet),
                "source_text": snippet,
                "raw_json": {"matched_keyword": keyword},
            }
        )
    return rows


def _extract_kofic_event_candidates(text: str, report_year: int, file_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        slug: str,
        keywords: tuple[str, ...],
        title: str,
        event_type: str,
        description: str,
        effects: dict[str, int],
        *,
        fixed_level: str = "semiFixed",
        confidence: float = 0.55,
        month: int | None = None,
        required: bool = True,
    ) -> None:
        found = _find_keyword_snippet(text, keywords)
        if required and not found:
            return
        snippet = found[0] if found else ""
        rows.append(
            {
                "id": _stable_id("kofic_event", str(report_year), slug, file_id),
                "report_year": report_year,
                "month": month,
                "event_type": event_type,
                "title": title,
                "fixed_level": fixed_level,
                "description": description,
                "effects_json": effects,
                "confidence": confidence,
                "source_file_id": file_id,
                "source_text": snippet,
                "raw_json": {"slug": slug, "matched_keywords": list(keywords)},
            }
        )

    if report_year == 2020:
        add(
            "covid_theater_crisis",
            ("코로나", "팬데믹"),
            "코로나19 이후 극장 시장 급락",
            "market_crisis",
            "KOFIC 결산 자료에서 코로나19 이후 극장 관객과 매출 충격을 시장 변수로 반영할 후보 사건.",
            {"theater_demand": -60, "ott_power": 35, "release_delay_cost": 25, "production_shutdown_risk": 20},
            fixed_level="absoluteFixed",
            confidence=0.9,
            month=3,
        )
    if report_year >= 2020:
        add(
            "ott_market_growth",
            ("OTT", "온라인동영상", "스트리밍"),
            f"{report_year}년 OTT 영향력 확대",
            "market_structure",
            "극장 중심 수익 구조와 플랫폼 판매/공개 전략의 비중 변화를 반영할 후보 사건.",
            {"ott_power": 15, "global_streaming_value": 10, "theater_demand": -5},
            confidence=0.66,
        )
    if report_year >= 2020:
        add(
            "ticket_price_burden",
            ("관람요금", "티켓값", "티켓 가격", "평균 입장권"),
            f"{report_year}년 티켓값 부담 심화",
            "market_price",
            "평균 관람요금과 체감 가격 부담을 티켓값 부담 및 2주차 낙폭 변수에 연결할 후보 사건.",
            {"ticket_price_burden": 10, "audience_price_sensitivity": 8, "second_week_drop_risk": 5},
            confidence=0.58,
        )
    if report_year >= 2009:
        add(
            "premium_format_market",
            ("특수관", "IMAX", "4DX", "ScreenX", "프리미엄"),
            f"{report_year}년 특별관/프리미엄 관람 비중 변화",
            "premium_format",
            "특별관 수요, 대형 외화 압박, 프리미엄 객단가를 조정할 후보 사건.",
            {"special_format_demand": 10, "premium_ticket_revenue": 8, "vfx_expectation": 5},
            confidence=0.57,
        )
    add(
        "korean_film_market_slump",
        ("한국영화 부진", "한국 영화 부진", "한국영화 위기", "한국영화 점유율", "한국 영화 점유율"),
        f"{report_year}년 한국영화 시장 점유율 변화",
        "domestic_market",
        "한국영화 신뢰도와 장르 투자 심리, 중간예산 위험을 조정할 후보 사건.",
        {"korean_film_trust": -8, "middle_budget_risk": 8, "investor_confidence": -5},
        confidence=0.52,
    )
    add(
        "market_recovery_signal",
        ("극장 회복", "관객 회복", "매출 회복", "회복세"),
        f"{report_year}년 극장 시장 회복 신호",
        "market_recovery",
        "전년 대비 관객과 매출 회복을 극장 수요 및 투자 심리 회복에 반영할 후보 사건.",
        {"theater_demand": 10, "investment_access": 5, "korean_film_trust": 5},
        confidence=0.52,
    )
    add(
        "middle_budget_risk",
        ("중간예산", "중급 규모", "허리 영화"),
        f"{report_year}년 중간예산 영화 리스크",
        "market_risk",
        "중간예산 오리지널 극장영화의 손익분기점과 배급 위험을 높이는 후보 사건.",
        {"middle_budget_risk": 12, "financial_risk": 6, "screen_access_difficulty": 5},
        confidence=0.58,
    )
    if report_year >= 2023:
        add(
            "japanese_animation_boxoffice",
            ("일본 애니메이션", "일본 애니", "애니메이션 흥행"),
            f"{report_year}년 일본 애니메이션 극장 흥행 강화",
            "foreign_competition",
            "수입 애니메이션과 팬덤형 N차 관람 수요를 외화 경쟁력과 애니메이션 시장 변수에 반영할 후보 사건.",
            {"foreign_competition": 8, "animation_trend": 10, "rewatch_index": 6},
            confidence=0.62,
        )
    add(
        "franchise_series_power",
        ("프랜차이즈", "시리즈", "범죄도시"),
        f"{report_year}년 프랜차이즈/시리즈 영화 영향",
        "franchise",
        "시리즈 흥행과 피로도를 IP 가치, 프랜차이즈 파워, 반복 소비 변수에 연결할 후보 사건.",
        {"franchise_power": 8, "sequel_demand": 6, "series_fatigue": 4},
        confidence=0.54,
    )
    return _dedupe_kofic_events(rows)


def _find_keyword_snippet(text: str, keywords: tuple[str, ...], radius: int = 260) -> tuple[str, str] | None:
    for keyword in keywords:
        index = text.find(keyword)
        if index < 0:
            continue
        start = max(0, index - radius)
        end = min(len(text), index + radius)
        return _clean_text(text[start:end]), keyword
    return None


def _infer_page_from_snippet(text: str, snippet: str) -> int | None:
    if not snippet:
        return None
    index = text.find(snippet[:40])
    if index < 0:
        return None
    page_markers = list(re.finditer(r"\[PAGE\s+([0-9]+)\]", text[:index]))
    if not page_markers:
        return None
    return int(page_markers[-1].group(1))


def _extract_number_after_keyword(snippet: str, keyword: str) -> float | None:
    index = snippet.find(keyword)
    probe = snippet[index:] if index >= 0 else snippet
    match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(조|억|만|천)?", probe)
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    multiplier = {
        "조": 1_000_000_000_000,
        "억": 100_000_000,
        "만": 10_000,
        "천": 1_000,
    }.get(match.group(2), 1)
    return value * multiplier


def _upsert_kofic_metric_candidate(conn: Any, metric: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kofic_industry_metrics (
            id, report_year, metric_id, metric_name, metric_category, value,
            unit, scope, confidence, source_file_id, source_page, source_text, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric["id"],
            metric["report_year"],
            metric["metric_id"],
            metric["metric_name"],
            metric["metric_category"],
            metric["value"],
            metric["unit"],
            metric["scope"],
            metric["confidence"],
            metric["source_file_id"],
            metric["source_page"],
            metric["source_text"],
            dumps_json(metric["raw_json"]),
        ),
    )


def _upsert_kofic_report_event(conn: Any, event: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kofic_report_events (
            id, report_year, month, event_type, title, fixed_level, description,
            effects_json, confidence, source_file_id, source_text, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["id"],
            event["report_year"],
            event["month"],
            event["event_type"],
            event["title"],
            event["fixed_level"],
            event["description"],
            dumps_json(event["effects_json"]),
            event["confidence"],
            event["source_file_id"],
            event["source_text"],
            dumps_json(event["raw_json"]),
        ),
    )


def _promote_kofic_report_event(conn: Any, event: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO history_market_events (
            id, year, month, title, type, fixed_level, description, effects_json, unlocks_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["id"].replace("kofic_event_", "event_kofic_"),
            event["report_year"],
            event["month"],
            event["title"],
            event["event_type"],
            event["fixed_level"],
            event["description"],
            dumps_json(event["effects_json"]),
            dumps_json([]),
        ),
    )


def _dedupe_kofic_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        deduped.append(row)
    return deduped


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _extract_kmdb_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for block in _as_list(payload.get("Data") or payload.get("data")):
        if isinstance(block, dict):
            results.extend(item for item in _as_list(block.get("Result") or block.get("result")) if isinstance(item, dict))
    if not results and isinstance(payload.get("Result"), list):
        results.extend(item for item in payload["Result"] if isinstance(item, dict))
    return results


def _normalize_kmdb_movie(item: dict[str, Any], source_url: str) -> dict[str, Any]:
    plots = item.get("plots")
    plot_text = ""
    if isinstance(plots, dict):
        for plot in _as_list(plots.get("plot")):
            if isinstance(plot, dict) and plot.get("plotText"):
                plot_text = _clean_text(plot.get("plotText"))
                break
    directors = _extract_names(item.get("directors"), "director", ("directorNm", "directorEnNm", "name"))
    actors = _extract_names(item.get("actors"), "actor", ("actorNm", "actorEnNm", "name"))
    return {
        "kmdb_id": _clean_text(item.get("DOCID") or item.get("docid") or item.get("movieId") or ""),
        "title_ko": _clean_text(item.get("title") or item.get("titleKo") or ""),
        "normalized_title": normalize_title(item.get("title") or item.get("titleKo") or ""),
        "title_en": _clean_text(item.get("titleEng") or item.get("titleEn") or ""),
        "prod_year": _to_int(item.get("prodYear")),
        "match_year": _match_year(item.get("repRlsDate") or item.get("releaseDate"), item.get("prodYear")),
        "release_date": _clean_text(item.get("repRlsDate") or item.get("releaseDate") or ""),
        "nation": _clean_text(item.get("nation") or item.get("repNationNm") or item.get("nationAlt") or ""),
        "director_names": directors,
        "actor_names": actors,
        "production_company": _clean_text(item.get("company") or item.get("prodCompany") or ""),
        "distribution_company": _clean_text(item.get("distribution") or item.get("distributor") or ""),
        "genre": _clean_text(item.get("genre") or ""),
        "runtime": _to_int(item.get("runtime")),
        "rating": _clean_text(item.get("rating") or ""),
        "plot": plot_text,
        "keywords": _split_list(item.get("keywords")),
        "awards": {"Awards1": item.get("Awards1"), "Awards2": item.get("Awards2")},
        "raw": item,
        "source_url": source_url,
    }


def _extract_kmdb_dump_rows(payload: Any) -> list[Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, dict) and isinstance(payload.get("Data"), list):
        return payload["Data"]
    if isinstance(payload, list):
        return payload
    raise CollectionError("KMDb JSON dump must be a list or an object with a data list.")


def _normalize_kmdb_dump_movie(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    kmdb_id = _clean_text(f"{row.get('COLUMN1') or ''}{row.get('COLUMN2') or ''}")
    release_date = _clean_text(row.get("COLUMN20") or "")
    prod_year = _to_int(row.get("COLUMN10"))
    return {
        "kmdb_id": kmdb_id,
        "title_ko": _clean_text(row.get("COLUMN3") or ""),
        "normalized_title": normalize_title(row.get("COLUMN3") or ""),
        "title_en": _clean_text(row.get("COLUMN4") or ""),
        "prod_year": prod_year,
        "match_year": _match_year(release_date, prod_year),
        "release_date": release_date,
        "nation": _clean_text(row.get("COLUMN9") or ""),
        "director_names": _split_people_names(row.get("COLUMN12")),
        "actor_names": _split_people_names(row.get("COLUMN15") or row.get("COLUMN13")),
        "production_company": _clean_text(row.get("COLUMN11") or ""),
        "distribution_company": "",
        "genre": _clean_text(row.get("COLUMN8") or ""),
        "runtime": _to_int(row.get("COLUMN21")),
        "rating": _clean_text(row.get("COLUMN19") or ""),
        "plot": _clean_text(row.get("COLUMN23") or ""),
        "keywords": _split_list(row.get("COLUMN22")),
        "awards": {},
        "raw": {"format": "kmdb_column_dump", "row": row},
        "source_url": f"file://{source_path}#{kmdb_id}",
    }


def _is_korean_kmdb_movie(item: dict[str, Any]) -> bool:
    text = " ".join(
        _clean_text(item.get(key))
        for key in ("nation", "repNationNm", "nationAlt", "prodCompany")
        if item.get(key)
    )
    return _is_korean_text(text)


def _is_korean_text(*values: Any) -> bool:
    text = " ".join(_clean_text(value) for value in values if value)
    return any(token in text for token in ("한국", "대한민국", "Korea", "South Korea"))


def _upsert_kmdb_movie(conn: Any, movie: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kmdb_movies (
            kmdb_id, title_ko, normalized_title, title_en,
            prod_year, match_year, release_date, nation,
            director_names_json, actor_names_json, production_company,
            distribution_company, genre, runtime, rating, plot,
            keywords_json, awards_json, raw_json, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            movie["kmdb_id"],
            movie["title_ko"],
            movie["normalized_title"],
            movie["title_en"],
            movie["prod_year"],
            movie["match_year"],
            movie["release_date"],
            movie["nation"],
            dumps_json(movie["director_names"]),
            dumps_json(movie["actor_names"]),
            movie["production_company"],
            movie["distribution_company"],
            movie["genre"],
            movie["runtime"],
            movie["rating"],
            movie["plot"],
            dumps_json(movie["keywords"]),
            dumps_json(movie["awards"]),
            dumps_json(movie["raw"]),
            movie["source_url"],
        ),
    )


def _upsert_kobis_daily_boxoffice(conn: Any, target_date: str, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kobis_daily_boxoffice (
            target_date, movie_code, movie_name, open_date, rank,
            rank_change, rank_old_and_new, sales_amount, sales_accumulated,
            audience_count, audience_accumulated, screen_count, show_count,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target_date,
            item.get("movieCd"),
            item.get("movieNm"),
            item.get("openDt"),
            _to_int(item.get("rank")),
            _to_int(item.get("rankInten")),
            item.get("rankOldAndNew"),
            _to_int(item.get("salesAmt")),
            _to_int(item.get("salesAcc")),
            _to_int(item.get("audiCnt")),
            _to_int(item.get("audiAcc")),
            _to_int(item.get("scrnCnt")),
            _to_int(item.get("showCnt")),
            dumps_json(item),
        ),
    )


def _upsert_kobis_movie_list(conn: Any, item: dict[str, Any]) -> None:
    movie_name = _clean_text(item.get("movieNm"))
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kobis_movie_list (
            movie_code, movie_name_ko, normalized_title, movie_name_en,
            production_year, open_date, type_name, production_status,
            nation_alt, genre_alt, representative_nation,
            representative_genre, directors_json, companies_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.get("movieCd"),
            movie_name,
            normalize_title(movie_name),
            _clean_text(item.get("movieNmEn")),
            _to_int(item.get("prdtYear")),
            _clean_text(item.get("openDt")),
            _clean_text(item.get("typeNm")),
            _clean_text(item.get("prdtStatNm")),
            _clean_text(item.get("nationAlt")),
            _clean_text(item.get("genreAlt")),
            _clean_text(item.get("repNationNm")),
            _clean_text(item.get("repGenreNm")),
            dumps_json(_extract_names(item.get("directors"), "director", ("peopleNm", "peopleNmEn", "name"))),
            dumps_json(_as_list(item.get("companys"))),
            dumps_json(item),
        ),
    )


def _upsert_kobis_movie_detail(conn: Any, item: dict[str, Any]) -> None:
    movie_name = _clean_text(item.get("movieNm"))
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kobis_movie_details (
            movie_code, movie_name_ko, normalized_title, movie_name_en,
            original_title, show_time, production_year, open_date,
            production_status, type_name, nations_json, genres_json,
            directors_json, actors_json, companies_json, audits_json,
            staffs_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.get("movieCd"),
            movie_name,
            normalize_title(movie_name),
            _clean_text(item.get("movieNmEn")),
            _clean_text(item.get("movieNmOg")),
            _to_int(item.get("showTm")),
            _to_int(item.get("prdtYear")),
            _clean_text(item.get("openDt")),
            _clean_text(item.get("prdtStatNm")),
            _clean_text(item.get("typeNm")),
            dumps_json(_as_list(item.get("nations"))),
            dumps_json(_as_list(item.get("genres"))),
            dumps_json(_extract_names(item.get("directors"), "director", ("peopleNm", "peopleNmEn", "name"))),
            dumps_json(_extract_names(item.get("actors"), "actor", ("peopleNm", "peopleNmEn", "name"))),
            dumps_json(_as_list(item.get("companys"))),
            dumps_json(_as_list(item.get("audits"))),
            dumps_json(_as_list(item.get("staffs"))),
            dumps_json(item),
        ),
    )


def _upsert_ticket_price(conn: Any, year: int, average_ticket_price: int, source_type: str) -> None:
    for table in ("ticket_prices", "history_ticket_prices"):
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {table} (
                year, average_ticket_price, perceived_ticket_price,
                premium_format_multiplier, audience_price_sensitivity,
                source_type
            ) VALUES (?, ?, ?, 1.0, 50, ?)
            """,
            (year, average_ticket_price, average_ticket_price, source_type),
        )


def _extract_kosis_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        if payload.get("err"):
            raise CollectionError(str(payload.get("err")))
        for key in ("data", "Data", "result", "Result", "rows"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
        if {"TBL_ID", "PRD_DE", "DT"} & set(payload):
            return [payload]
    raise CollectionError("KOSIS JSON rows were not found in the response.")


def _upsert_kosis_statistic(
    conn: Any,
    target_id: str,
    category: str | None,
    row: dict[str, Any],
    source_url: str,
) -> None:
    stat_id = _kosis_row_id(target_id, row)
    value_numeric = _to_float(row.get("DT"))
    c_values = [_kosis_dimension(row, index) for index in range(1, 9)]
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kosis_statistics (
            id, target_id, org_id, tbl_id, tbl_nm, stat_id, stat_nm,
            item_id, item_name, unit_name, prd_se, prd_de,
            value_text, value_numeric,
            c1_id, c1_name, c2_id, c2_name, c3_id, c3_name, c4_id, c4_name,
            c5_id, c5_name, c6_id, c6_name, c7_id, c7_name, c8_id, c8_name,
            raw_json, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stat_id,
            target_id,
            _clean_text(row.get("ORG_ID")),
            _clean_text(row.get("TBL_ID")),
            _clean_text(row.get("TBL_NM")),
            _clean_text(row.get("STAT_ID")),
            _clean_text(row.get("STAT_NM")),
            _clean_text(row.get("ITM_ID")),
            _clean_text(row.get("ITM_NM")),
            _clean_text(row.get("UNIT_NM")),
            _clean_text(row.get("PRD_SE")),
            _clean_text(row.get("PRD_DE")),
            _clean_text(row.get("DT")),
            value_numeric,
            c_values[0][0],
            c_values[0][1],
            c_values[1][0],
            c_values[1][1],
            c_values[2][0],
            c_values[2][1],
            c_values[3][0],
            c_values[3][1],
            c_values[4][0],
            c_values[4][1],
            c_values[5][0],
            c_values[5][1],
            c_values[6][0],
            c_values[6][1],
            c_values[7][0],
            c_values[7][1],
            dumps_json(row),
            source_url,
        ),
    )
    _upsert_kosis_indicator_series(conn, target_id, category, row, value_numeric)


def _upsert_kosis_indicator_series(
    conn: Any,
    target_id: str,
    category: str | None,
    row: dict[str, Any],
    value_numeric: float | None,
) -> None:
    period = _clean_text(row.get("PRD_DE"))
    year, month = _period_parts(period, row.get("PRD_SE"))
    region_code = _clean_text(row.get("C1"))
    region_name = _clean_text(row.get("C1_NM"))
    series_id = _hash_id(
        "kosis_series",
        target_id,
        period,
        region_code,
        _clean_text(row.get("ITM_ID")),
        _clean_text(row.get("TBL_ID")),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kosis_indicator_series (
            id, indicator_id, indicator_name, category, year, month, period,
            region_code, region_name, item_id, item_name, value, unit_name,
            source_org_id, source_tbl_id, source_tbl_name, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            series_id,
            target_id,
            _clean_text(row.get("ITM_NM")),
            category,
            year,
            month,
            period,
            region_code,
            region_name,
            _clean_text(row.get("ITM_ID")),
            _clean_text(row.get("ITM_NM")),
            value_numeric,
            _clean_text(row.get("UNIT_NM")),
            _clean_text(row.get("ORG_ID")),
            _clean_text(row.get("TBL_ID")),
            _clean_text(row.get("TBL_NM")),
            dumps_json(row),
        ),
    )


def _upsert_kosis_search_result(conn: Any, search_name: str, row: dict[str, Any]) -> None:
    result_id = _hash_id(
        "kosis_search",
        search_name,
        _clean_text(row.get("ORG_ID")),
        _clean_text(row.get("TBL_ID")),
        _clean_text(row.get("STAT_ID")),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO staging_kosis_search_results (
            id, search_name, org_id, org_name, tbl_id, tbl_name,
            stat_id, stat_name, period_start, period_end,
            table_path, contents, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result_id,
            search_name,
            _clean_text(row.get("ORG_ID")),
            _clean_text(row.get("ORG_NM")),
            _clean_text(row.get("TBL_ID")),
            _clean_text(row.get("TBL_NM")),
            _clean_text(row.get("STAT_ID")),
            _clean_text(row.get("STAT_NM")),
            _clean_text(row.get("STRT_PRD_DE")),
            _clean_text(row.get("END_PRD_DE")),
            _clean_text(row.get("MT_ATITLE") or row.get("FULL_PATH_ID")),
            _clean_text(row.get("CONTENTS")),
            dumps_json(row),
        ),
    )


def _kosis_row_id(target_id: str, row: dict[str, Any]) -> str:
    parts = [
        "kosis",
        target_id,
        _clean_text(row.get("ORG_ID")),
        _clean_text(row.get("TBL_ID")),
        _clean_text(row.get("ITM_ID")),
        _clean_text(row.get("PRD_SE")),
        _clean_text(row.get("PRD_DE")),
    ]
    for index in range(1, 9):
        parts.append(_clean_text(row.get(f"C{index}")))
    return _hash_id(*parts)


def _kosis_dimension(row: dict[str, Any], index: int) -> tuple[str, str]:
    return _clean_text(row.get(f"C{index}")), _clean_text(row.get(f"C{index}_NM"))


def _period_parts(period: str, prd_se: Any) -> tuple[int | None, int | None]:
    digits = re.sub(r"[^0-9]", "", period)
    year = int(digits[:4]) if len(digits) >= 4 else None
    month = None
    if _clean_text(prd_se).upper() == "M" and len(digits) >= 6:
        month = int(digits[4:6])
    return year, month


def _load_kosis_target(target_id: str, targets_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(targets_path) if targets_path else BASE_DIR / "data" / "kosis_targets.json"
    if not path.exists():
        raise CollectionError(f"KOSIS target file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"KOSIS target file parse failed: {path}") from exc
    targets = payload.get("targets") if isinstance(payload, dict) else payload
    for target in _as_list(targets):
        if isinstance(target, dict) and target.get("id") == target_id:
            return target
    raise CollectionError(f"KOSIS target not found: {target_id}")


def _extract_names(value: Any, container_key: str, name_keys: tuple[str, ...]) -> list[str]:
    if isinstance(value, dict):
        items = _as_list(value.get(container_key))
    else:
        items = _as_list(value)
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in name_keys:
                name = _clean_text(item.get(key))
                if name:
                    names.append(name)
                    break
        elif item:
            names.append(_clean_text(str(item)))
    return [name for name in names if name]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(str(value))
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;/|]", text) if part.strip()]


def _split_people_names(value: Any) -> list[str]:
    names: list[str] = []
    values = value if isinstance(value, list) else [value]
    for raw_value in values:
        text = re.sub(r"\([^)]*\)", "", _clean_text(raw_value))
        for name in _split_list(text):
            cleaned = name.strip()
            if cleaned:
                names.append(cleaned)
    return names


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"!\w+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(value: Any) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^0-9a-z가-힣]", "", text)
    return text


def _match_year(release_date: Any, production_year: Any) -> int:
    release_text = re.sub(r"[^0-9]", "", str(release_date or ""))
    if len(release_text) >= 4:
        return int(release_text[:4])
    return _to_int(production_year)


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    text = re.sub(r"[^0-9-]", "", str(value))
    return int(text or 0)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = re.sub(r"[^0-9.\-]", "", str(value))
    if text in ("", "-", ".", "-."):
        return None
    return float(text)


def _hash_id(*parts: Any) -> str:
    raw = "|".join(_clean_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _required_int(row: dict[str, str], *keys: str) -> int:
    for key in keys:
        if row.get(key):
            return _to_int(row[key])
    raise CollectionError(f"CSV field required: {'/'.join(keys)}")


def _actor_id(name_ko: str, name_en: str | None) -> str:
    if name_en:
        slug = re.sub(r"[^a-z0-9]+", "_", name_en.lower()).strip("_")
        if slug:
            return f"actor_{slug}"
    digest = hashlib.sha1(name_ko.encode("utf-8")).hexdigest()[:10]
    return f"actor_kofic_{digest}"


def _redact_mapping(params: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(params)
    for key in list(redacted):
        if key.lower() in {"key", "servicekey", "api_key", "apikey"}:
            redacted[key] = "***"
    return redacted


def _redact_url(url: str) -> str:
    return re.sub(r"((?:apiKey|key|ServiceKey)=)[^&]+", r"\1***", url, flags=re.IGNORECASE)
