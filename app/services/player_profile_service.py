from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json
from app.services.game_state import money
from app.services.player_filmography_service import get_player_filmography_state


def get_player_profile() -> dict[str, Any]:
    with get_connection() as conn:
        player_row = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio_row = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        career_start = conn.execute(
            """
            SELECT year, month, day, metadata_json
            FROM calendar_events
            WHERE event_type = 'career_start'
            ORDER BY year, month, day, created_at
            LIMIT 1
            """
        ).fetchone()
    if not player_row:
        raise ValueError("플레이어 프로필을 만들 캐릭터가 없습니다.")

    player = dict(player_row)
    studio = dict(studio_row) if studio_row else {}
    stats = loads_json(player.get("stats_json"), {})
    reputation = loads_json(player.get("reputation_json"), {})
    network = loads_json(player.get("network_json"), {})
    current_year = int(player["current_year"])
    current_month = int(player["current_month"])
    start_year = int(career_start["year"]) if career_start else current_year
    current_age = int(player.get("age") or 0) + max(0, current_year - start_year)
    filmography_state = get_player_filmography_state()
    films = filmography_state.get("films", [])

    return {
        "id": "player",
        "name": str(player["name"]),
        "name_ko": str(player["name"]),
        "name_en": "",
        "type": "director",
        "age_text": _age_text(player.get("age"), current_age, current_year, current_month),
        "nationality": "대한민국",
        "status_text": _status_text(player, studio, start_year),
        "industry_reputation": _reputation_text(reputation, "industry_reputation", "업계"),
        "public_reputation": _reputation_text(reputation, "public_reputation", "대중"),
        "fame_text": _fame_text(reputation, studio, films),
        "potential_text": _potential_text(stats, films),
        "one_line": _one_line(stats, reputation, films),
        "current_ability_text": _current_ability_text(stats, reputation, network),
        "brand_text": _brand_text(reputation, network, films),
        "expected_fee": _expected_contract_text(stats, reputation, studio, films),
        "fee_title": "예상 연출/제작 계약 조건",
        "preference_title": "선호 프로젝트 및 협업 궁합",
        "preferred_roles": _preferred_projects_text(stats),
        "preferred_directors": _collaboration_fit_text(stats, network),
        "filmography": _filmography_entries(films),
        "awards": _award_entries(films),
        "career_intro": _career_intro(player, studio, stats, reputation, network, films, start_year, current_year),
    }


def _age_text(start_age: Any, current_age: int, current_year: int, current_month: int) -> str:
    if not isinstance(start_age, int):
        return f"{current_year}년 {current_month}월 기준 연령 정보 미정리"
    return f"시작 시 {start_age}세 · {current_year}년 {current_month}월 기준 {current_age}세 전후"


def _status_text(player: dict[str, Any], studio: dict[str, Any], start_year: int) -> str:
    career_year = max(1, int(player["current_year"]) - start_year + 1)
    studio_name = studio.get("studio_name") or f"{player['name']} 필름"
    return f"{studio_name} 대표 영화인 · 커리어 {career_year}년차"


def _reputation_text(reputation: dict[str, Any], key: str, label: str) -> str:
    value = int(reputation.get(key) or 0)
    if value >= 85:
        return f"{label}에서 이름만으로 강한 기대와 신뢰를 만드는 단계다."
    if value >= 68:
        return f"{label}에서 신뢰할 만한 창작자로 받아들여지고 있다."
    if value >= 50:
        return f"{label} 평판은 형성되고 있으나 작품마다 검증이 따라붙는다."
    if value >= 30:
        return f"{label}에서는 아직 가능성을 보는 단계에 가깝다."
    return f"{label} 평판은 아직 거의 검증되지 않았다."


def _fame_text(reputation: dict[str, Any], studio: dict[str, Any], films: list[dict[str, Any]]) -> str:
    average = _average(reputation, ("public_reputation", "industry_reputation", "creative_reputation", "critic_reputation"))
    fame = max(average, int(studio.get("fame") or 0))
    if films and any(_is_success(film) for film in films):
        fame += 8
    if fame >= 82:
        return "동시대 한국영화 산업에서 확실한 이름값을 가진 영화인으로 분류된다."
    if fame >= 64:
        return "업계와 관객 모두에게 어느 정도 이름이 각인된 상태다."
    if fame >= 45:
        return "아직 대표작과 다음 행보로 평가가 달라질 수 있는 단계다."
    return "아직은 소수의 관계자와 가까운 관객층에게만 알려진 상태다."


def _potential_text(stats: dict[str, Any], films: list[dict[str, Any]]) -> str:
    learning = int(stats.get("learning_ability") or 50)
    creative = _average(stats, ("directing_ability", "screenplay_sense", "artistic_sense"))
    commercial = _average(stats, ("market_analysis", "commercial_sense", "marketing_sense", "fundraising_ability"))
    if learning >= 72 and len(films) <= 2:
        return "아직 확정된 이미지가 적어 장르와 협업을 잘 만나면 큰 폭으로 도약할 수 있다."
    if max(creative, commercial) >= 74:
        return "이미 강점이 보이는 축이 있으며, 다음 작품이 그 이미지를 굳힐 가능성이 높다."
    if films:
        return "잠재력은 작품 선택, 예산 규모, 협업 배우와 감독군에 따라 갈릴 것으로 보인다."
    return "아직 공개 검증 전이라 잠재력은 선택과 실패를 통해 드러날 것이다."


def _one_line(stats: dict[str, Any], reputation: dict[str, Any], films: list[dict[str, Any]]) -> str:
    if films and any(_is_success(film) for film in films):
        genre = _dominant_genre(films)
        if genre:
            return f"{genre}에서 자기 색을 드러내기 시작한 플레이어 영화인."
        return "첫 대표작을 통해 업계의 시선을 얻기 시작한 플레이어 영화인."
    strongest = _strongest_axis(stats)
    if strongest == "creative":
        return "각본과 연출의 방향성을 먼저 세우는 창작자형 영화인."
    if strongest == "commercial":
        return "시장 흐름과 손익 구조를 읽으며 프로젝트를 설계하는 제작자형 영화인."
    if strongest == "field":
        return "현장과 사람의 움직임을 바탕으로 영화를 굴리는 실무형 영화인."
    if int(reputation.get("critic_reputation") or 0) >= int(reputation.get("public_reputation") or 0) + 8:
        return "대중보다 평론과 창작자 네트워크에서 먼저 반응을 얻는 영화인."
    return "아직 자기 대표작을 만들어가는 중인 한국영화 플레이어."


def _current_ability_text(stats: dict[str, Any], reputation: dict[str, Any], network: dict[str, Any]) -> str:
    axes = sorted(
        [
            ("창작 판단", _average(stats, ("directing_ability", "screenplay_sense", "artistic_sense"))),
            ("상업 판단", _average(stats, ("market_analysis", "commercial_sense", "marketing_sense"))),
            ("자본 조달", _average(stats, ("fundraising_ability", "distribution_negotiation"))),
            ("현장 운영", _average(stats, ("field_control", "production_network"))),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    primary = axes[0][0]
    secondary = axes[1][0]
    if axes[0][1] >= 70:
        lead = f"{primary}이 뚜렷한 강점으로 보이며, {secondary}도 프로젝트 방향에 영향을 줄 수 있다."
    elif axes[0][1] >= 55:
        lead = f"{primary} 쪽에서 가능성이 보이지만 아직 작품마다 편차가 생길 수 있다."
    else:
        lead = "아직 특정 역량이 확실한 브랜드로 굳지는 않았다."
    relationship = _relationship_sentence(reputation, network)
    return f"{lead} {relationship}"


def _brand_text(reputation: dict[str, Any], network: dict[str, Any], films: list[dict[str, Any]]) -> str:
    if films and any(_is_success(film) for film in films):
        return "최근 작품 기록 덕분에 다음 프로젝트 발표 때 업계가 이전보다 더 빠르게 반응할 가능성이 있다."
    if _average(reputation, ("investor_reputation", "industry_reputation")) >= 62:
        return "투자자와 업계 관계자에게는 일정 수준의 신뢰를 줄 수 있지만, 관객에게는 아직 작품 자체의 설득이 더 중요하다."
    if _average(network, ("actor_network", "director_network", "production_network")) >= 62:
        return "공개 브랜드보다 현장 관계망에서 먼저 힘을 얻는 타입이다."
    return "브랜드 평판은 아직 초기 단계라 제목, 장르, 협업진이 발표 효과를 대신해야 한다."


def _expected_contract_text(
    stats: dict[str, Any],
    reputation: dict[str, Any],
    studio: dict[str, Any],
    films: list[dict[str, Any]],
) -> str:
    if not films:
        return "아직 검증된 장편 흥행 기록이 부족해 독립/저예산 프로젝트 중심으로 조건이 형성될 가능성이 높다."
    if any(_is_major_success(film) for film in films):
        return "대표작 성과가 있어 다음 작품에서는 연출권, 제작 지분, 배급 조건을 함께 협상할 수 있는 위치에 가깝다."
    if _average(reputation, ("investor_reputation", "creative_reputation")) >= 60:
        return "중간 규모 프로젝트에서 조건부 투자와 창작 권한을 함께 요구해볼 만한 단계다."
    cash_text = money(studio.get("cash"))
    return f"현재 제작사 현금 여력은 {cash_text} 수준이며, 외부 투자와 배급 선계약이 계약 조건을 좌우할 가능성이 크다."


def _preferred_projects_text(stats: dict[str, Any]) -> str:
    preferences: list[str] = []
    if _average(stats, ("screenplay_sense", "artistic_sense", "critic_reputation")) >= 58:
        preferences.append("각본과 연출 톤이 분명한 작가주의/드라마 프로젝트")
    if _average(stats, ("market_analysis", "commercial_sense", "marketing_sense")) >= 58:
        preferences.append("관객층과 개봉 전략이 선명한 상업 프로젝트")
    if int(stats.get("distribution_negotiation") or 0) >= 58:
        preferences.append("배급사와 개봉 전략을 초반부터 설계하는 프로젝트")
    if int(stats.get("field_control") or 0) >= 58:
        preferences.append("현장 변수와 배우 앙상블을 조율해야 하는 프로젝트")
    if not preferences:
        preferences.append("작은 규모에서 실패 비용을 낮추며 색을 확인할 수 있는 프로젝트")
    return "\n".join(f"- {item}" for item in preferences[:4])


def _collaboration_fit_text(stats: dict[str, Any], network: dict[str, Any]) -> str:
    fits: list[str] = []
    if int(network.get("actor_network") or 0) >= 55:
        fits.append("배우와 충분히 대화하며 캐릭터를 만들어가는 협업")
    if int(network.get("investor_network") or 0) >= 55:
        fits.append("투자자에게 손익 구조를 설명하고 조건을 조율하는 협업")
    if int(network.get("festival_network") or 0) >= 55:
        fits.append("영화제와 평론 반응을 염두에 둔 협업")
    if int(stats.get("learning_ability") or 0) >= 65:
        fits.append("경험 많은 스태프에게 빠르게 배우며 성장하는 현장")
    if not fits:
        fits.append("아직은 궁합이 검증된 파트너를 만들어가는 단계")
    return "\n".join(f"- {item}" for item in fits[:4])


def _filmography_entries(films: list[dict[str, Any]]) -> list[str]:
    entries: list[str] = []
    for film in films[:10]:
        release = _release_label(film)
        genre = film.get("genreName") or "장르 미정"
        status = (film.get("summary") or {}).get("statusLabel") or _film_status_text(film)
        entries.append(f"{release} <{film.get('title')}> · {genre} · {status}")
    return entries


def _award_entries(films: list[dict[str, Any]]) -> list[str]:
    entries: list[str] = []
    for film in films:
        for award in film.get("awards") or []:
            if isinstance(award, dict):
                label = " · ".join(
                    str(award.get(key))
                    for key in ("year", "awardName", "category", "resultLabel")
                    if award.get(key)
                )
                if label:
                    entries.append(f"<{film.get('title')}> · {label}")
            elif isinstance(award, str):
                entries.append(f"<{film.get('title')}> · {award}")
    return entries[:10]


def _career_intro(
    player: dict[str, Any],
    studio: dict[str, Any],
    stats: dict[str, Any],
    reputation: dict[str, Any],
    network: dict[str, Any],
    films: list[dict[str, Any]],
    start_year: int,
    current_year: int,
) -> str:
    summary = stats.get("character_summary") or "자기 방식으로 영화계에 진입한 영화인"
    intro = f"{player['name']}은/는 {start_year}년에 {summary}으로 커리어를 시작했다."
    if films:
        best = _best_film(films)
        if best:
            intro += f" 현재까지 가장 강하게 남은 기록은 <{best.get('title')}>이며, 이 작품은 커리어 평가의 기준점이 되고 있다."
        intro += f" 지금까지 완성한 장편 기록은 {len(films)}편이며, 작품 선택을 통해 자신의 브랜드를 쌓아가는 중이다."
    else:
        intro += " 아직 개봉작은 없지만 첫 프로젝트의 장르와 규모가 향후 평판을 결정할 가능성이 크다."
    intro += " " + _career_direction_sentence(stats, reputation, network)
    if studio.get("studio_name"):
        intro += f" 현재 활동 기반은 {studio['studio_name']}이다."
    return intro


def _release_label(film: dict[str, Any]) -> str:
    year = film.get("releaseYear") or "연도 미상"
    month = film.get("releaseMonth")
    return f"{year}년 {month}월" if month else f"{year}년"


def _film_status_text(film: dict[str, Any]) -> str:
    if _is_major_success(film):
        return "대표작급 흥행 기록"
    if _is_success(film):
        return "긍정적 성과"
    if (film.get("failureRecord") or {}).get("isFailure"):
        return "실패 기록"
    return "커리어 기록"


def _career_direction_sentence(stats: dict[str, Any], reputation: dict[str, Any], network: dict[str, Any]) -> str:
    if _strongest_axis(stats) == "creative":
        return "커리어의 무게중심은 흥행 공식보다 작품의 톤과 창작자 신뢰 쪽에 가깝다."
    if _strongest_axis(stats) == "commercial":
        return "커리어의 무게중심은 시장 판단, 투자 설득, 관객 접근성 쪽에 가깝다."
    if _average(network, ("actor_network", "production_network", "director_network")) >= 62:
        return "공개 명성보다 함께 일한 사람들의 신뢰가 먼저 쌓이는 흐름이다."
    if _average(reputation, ("public_reputation", "critic_reputation")) < 42:
        return "아직 평판이 굳지 않아 다음 작품의 반응이 매우 중요하다."
    return "현재는 작품성, 상업성, 관계망 사이에서 자기 노선을 만들어가는 단계다."


def _relationship_sentence(reputation: dict[str, Any], network: dict[str, Any]) -> str:
    if _average(network, ("actor_network", "production_network", "director_network")) >= 65:
        return "현장과 창작자 관계망이 비교적 탄탄해 협업 제안의 문턱이 낮다."
    if _average(reputation, ("investor_reputation", "industry_reputation")) >= 65:
        return "투자자와 업계의 신뢰를 바탕으로 프로젝트를 설명하는 힘이 있다."
    if _average(network, ("press_network", "critic_access", "festival_network")) >= 60:
        return "언론, 평론, 영화제 쪽 반응을 활용하는 데 비교적 유리하다."
    return "다만 아직 핵심 파트너와 반복 협업 기록은 더 쌓아야 한다."


def _best_film(films: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not films:
        return None
    return max(
        films,
        key=lambda film: (
            int(film.get("audience") or 0) // 10000
            + max(0, int(film.get("profit") or 0)) // 10000000
            + len(film.get("awards") or []) * 20
        ),
    )


def _dominant_genre(films: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for film in films:
        genre = film.get("genreName")
        if genre:
            counts[str(genre)] = counts.get(str(genre), 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def _is_success(film: dict[str, Any]) -> bool:
    failure = film.get("failureRecord") or {}
    break_even = int(film.get("breakEvenAudience") or 0)
    return not failure.get("isFailure") and (
        int(film.get("profit") or 0) > 0
        or (break_even > 0 and int(film.get("audience") or 0) >= break_even)
    )


def _is_major_success(film: dict[str, Any]) -> bool:
    return int(film.get("audience") or 0) >= 2_000_000 or int(film.get("profit") or 0) >= 1_000_000_000 or bool(film.get("awards"))


def _strongest_axis(stats: dict[str, Any]) -> str:
    axes = {
        "creative": _average(stats, ("directing_ability", "screenplay_sense", "artistic_sense")),
        "commercial": _average(stats, ("market_analysis", "fundraising_ability", "distribution_negotiation", "marketing_sense", "commercial_sense")),
        "field": _average(stats, ("field_control", "learning_ability")),
    }
    return max(axes.items(), key=lambda item: item[1])[0]


def _average(values: dict[str, Any], keys: tuple[str, ...]) -> int:
    found = [float(values[key]) for key in keys if isinstance(values.get(key), (int, float))]
    if not found:
        return 0
    return int(round(sum(found) / len(found)))
