from __future__ import annotations

from typing import Any


REPUTATION_LABELS = {
    "public_reputation": (
        "무명에 가까움",
        "아직 낯선 이름",
        "조금씩 알려지는 중",
        "대중 신뢰 형성 중",
        "대중성이 뚜렷함",
        "강한 흥행 브랜드",
        "시대적 대중 브랜드",
    ),
    "industry_reputation": (
        "업계 접점 거의 없음",
        "검증 전 단계",
        "일부 현장에서만 알려짐",
        "기본 신뢰 확보",
        "업계 신뢰가 탄탄함",
        "먼저 연락받는 이름",
        "업계 기준점",
    ),
    "critic_reputation": (
        "비평계 관심 낮음",
        "평론가 접점 희박",
        "호기심을 받는 단계",
        "평론가들이 지켜보는 이름",
        "비평 신뢰가 있는 편",
        "작품성으로 인정받음",
        "비평계 상징성 높음",
    ),
    "investor_reputation": (
        "투자 신뢰 낮음",
        "소액 검토 단계",
        "조건부 검토 대상",
        "실무 투자 검토 가능",
        "투자자가 신뢰하는 편",
        "큰돈을 맡길 수 있는 이름",
        "시장 신뢰가 매우 강함",
    ),
    "creative_reputation": (
        "창작진 신뢰 낮음",
        "함께 일한 기록 부족",
        "조심스러운 협업 가능",
        "창작진 신뢰 형성 중",
        "함께 일하고 싶은 이름",
        "창작자들이 먼저 찾음",
        "강한 창작 브랜드",
    ),
    "global_reputation": (
        "해외 인지도 거의 없음",
        "국내 중심 인지도",
        "해외 접점 초기",
        "해외 판권 시장에서 관찰 중",
        "해외 관심이 붙는 중",
        "글로벌 시장에서도 통하는 이름",
        "세계 시장급 브랜드",
    ),
}

NETWORK_LABELS = {
    "actor_network": (
        "배우 접점 거의 없음",
        "캐스팅 연락망이 얕음",
        "일부 배우 측과 접점 있음",
        "실무 미팅 가능",
        "캐스팅 루트가 탄탄함",
        "주요 배우에게 닿을 수 있음",
        "배우들이 먼저 반응함",
    ),
    "director_network": (
        "감독 접점 거의 없음",
        "연출자 네트워크 약함",
        "일부 감독과 접점 있음",
        "협업 미팅 가능",
        "연출자 관계망 탄탄함",
        "주요 감독과 직접 조율 가능",
        "감독들이 먼저 찾는 관계망",
    ),
    "production_network": (
        "현장 인맥 거의 없음",
        "현장 연락망이 얕음",
        "일부 스태프와 연결됨",
        "기본 현장 구성 가능",
        "현장 인맥이 탄탄함",
        "좋은 스태프를 빠르게 모을 수 있음",
        "현장 중심부와 연결됨",
    ),
    "investor_network": (
        "투자 접점 거의 없음",
        "소규모 투자 루트만 있음",
        "일부 투자자와 접점 있음",
        "투자 미팅 가능",
        "투자 라인이 안정적",
        "큰 투자자와 직접 조율 가능",
        "투자 시장 중심부와 연결됨",
    ),
    "distribution_network": (
        "배급 접점 거의 없음",
        "개봉 루트가 약함",
        "제한적 배급 접점 있음",
        "배급 협의 가능",
        "배급 라인이 탄탄함",
        "주요 배급 슬롯 협상 가능",
        "배급 시장 중심부와 연결됨",
    ),
    "press_network": (
        "언론 접점 거의 없음",
        "기사화 루트가 약함",
        "일부 기자와 접점 있음",
        "기본 홍보 가능",
        "언론 대응이 수월함",
        "주요 매체를 움직일 수 있음",
        "언론 노출력이 매우 강함",
    ),
    "critic_access": (
        "평론가 접점 거의 없음",
        "비평계 접근이 어려움",
        "일부 평론가와 접점 있음",
        "GV/시사회 제안 가능",
        "평론가 접근이 수월함",
        "비평 담론을 만들 수 있음",
        "비평계 중심부와 연결됨",
    ),
    "festival_network": (
        "영화제 접점 거의 없음",
        "출품 정보가 부족함",
        "일부 영화제 접점 있음",
        "영화제 루트 사용 가능",
        "영화제 인맥이 탄탄함",
        "프로그래머 접점이 강함",
        "영화제 전략의 중심부에 있음",
    ),
    "school_network": (
        "학교 인맥 거의 없음",
        "동문 접점이 약함",
        "일부 학교 루트 있음",
        "동문 도움 요청 가능",
        "학교 인맥이 탄탄함",
        "인력 추천이 잘 들어옴",
        "학교 네트워크 중심부",
    ),
    "regional_network": (
        "지역 접점 거의 없음",
        "지역 협조가 어려움",
        "일부 지역 접점 있음",
        "로케이션 협의 가능",
        "지역 협조망이 탄탄함",
        "지자체와 빠르게 조율 가능",
        "지역 촬영 네트워크가 강함",
    ),
}


def reputation_level_text(key: str, value: Any) -> str:
    return _level_text(REPUTATION_LABELS.get(key), value, default="평판 형성 중")


def network_level_text(key: str, value: Any) -> str:
    return _level_text(NETWORK_LABELS.get(key), value, default="관계망 형성 중")


def fame_level_text(value: Any) -> str:
    labels = (
        "아직 이름값은 거의 없음",
        "작은 제작사로 인식됨",
        "업계에서 조금씩 알려짐",
        "기본적인 회사 신뢰 확보",
        "눈여겨보는 제작사",
        "강한 제작사 브랜드",
        "업계 대표 제작사급",
    )
    return _level_text(labels, value, default="평판 형성 중")


def reputation_delta_text(key: str, delta: Any) -> str:
    return _delta_text(delta, positive="신뢰 상승", negative="신뢰 하락")


def network_delta_text(key: str, delta: Any) -> str:
    return _delta_text(delta, positive="관계망 확대", negative="관계 냉각")


def compact_reputation_changes(deltas: dict[str, Any]) -> str:
    labels = {
        "public_reputation": "대중",
        "industry_reputation": "업계",
        "critic_reputation": "평론",
        "investor_reputation": "투자",
        "creative_reputation": "창작",
        "global_reputation": "해외",
    }
    return _compact_changes(deltas, labels, reputation_delta_text)


def compact_network_changes(deltas: dict[str, Any]) -> str:
    labels = {
        "actor_network": "배우",
        "director_network": "감독",
        "production_network": "제작",
        "investor_network": "투자",
        "distribution_network": "배급",
        "press_network": "언론",
        "critic_access": "평론",
        "festival_network": "영화제",
        "school_network": "학교",
        "regional_network": "지역",
    }
    return _compact_changes(deltas, labels, network_delta_text)


def overall_change_text(delta: Any) -> str:
    value = _number(delta)
    if value >= 8:
        return "제작사 이름값이 크게 올라갔다"
    if value >= 3:
        return "제작사 평판이 좋아졌다"
    if value >= 1:
        return "제작사 평판에 작은 도움이 됐다"
    if value <= -8:
        return "제작사 평판에 큰 타격이 생겼다"
    if value <= -3:
        return "제작사 평판이 나빠졌다"
    if value <= -1:
        return "제작사 평판에 작은 흠집이 생겼다"
    return "제작사 평판은 크게 변하지 않았다"


def quality_band_text(value: Any) -> str:
    labels = (
        "완성도 검증이 필요한 상태",
        "부분적으로 거친 완성도",
        "기본기는 갖췄지만 아쉬움이 남는 완성도",
        "상업 개봉에 무리 없는 안정적인 완성도",
        "강점이 분명한 완성도",
        "업계에서도 주목할 만한 완성도",
        "시대 대표작 후보로 거론될 만한 완성도",
    )
    return _level_text(labels, value, default="완성도 판단 보류")


def audience_reaction_text(value: Any) -> str:
    labels = (
        "관객 반응이 차갑다",
        "관객 만족을 설득하기 어렵다",
        "호불호가 뚜렷하다",
        "기본적인 만족도는 확보했다",
        "관객 반응이 호의적이다",
        "입소문을 기대할 만한 반응이다",
        "관객이 적극적으로 밀어주는 분위기다",
    )
    return _level_text(labels, value, default="관객 반응 판단 보류")


def critic_reaction_text(value: Any) -> str:
    labels = (
        "평론가 반응이 냉담하다",
        "비평적으로 설득력이 약하다",
        "일부 장점은 있으나 평가가 갈린다",
        "평론가들이 기본기는 인정한다",
        "비평적으로 좋은 평가를 받을 만하다",
        "작품성으로 주목받을 가능성이 높다",
        "비평 담론을 만들 수 있는 작품이다",
    )
    return _level_text(labels, value, default="평론 반응 판단 보류")


def word_of_mouth_text(value: Any) -> str:
    labels = (
        "입소문 동력이 거의 없다",
        "초반 관심이 쉽게 식을 수 있다",
        "제한적인 추천은 기대할 수 있다",
        "관객 추천이 천천히 붙을 수 있다",
        "입소문이 흥행을 보탤 분위기다",
        "장기 흥행을 기대할 만한 입소문이다",
        "역주행까지 노릴 수 있는 확산력이다",
    )
    return _level_text(labels, value, default="입소문 판단 보류")


def drop_risk_text(value: Any) -> str:
    number = _number(value)
    if number >= 70:
        return "2주차 급락 위험이 매우 크다"
    if number >= 55:
        return "2주차 낙폭을 강하게 경계해야 한다"
    if number >= 40:
        return "일반적인 낙폭 범위에 가깝다"
    if number >= 25:
        return "관객 유지력이 괜찮은 편이다"
    return "장기 상영 여지가 있다"


def market_pressure_text(key: str, value: Any) -> str:
    labels = {
        "theater_demand": (
            "극장 수요 매우 약함",
            "극장 수요 약함",
            "극장 수요 회복 전",
            "극장 수요 보통",
            "극장 수요 양호",
            "극장 수요 강함",
            "극장 수요 과열",
        ),
        "foreign_competition": (
            "외화 압박 낮음",
            "외화 압박 약함",
            "외화 경쟁 관찰 필요",
            "외화 경쟁 보통",
            "외화 압박 높음",
            "외화 대작 압박 강함",
            "외화가 시장을 장악하는 분위기",
        ),
        "ott_power": (
            "OTT 영향 거의 없음",
            "OTT는 아직 주변 시장",
            "OTT 가능성 관찰 단계",
            "OTT가 보조 시장으로 작동",
            "OTT 계약 가치가 커지는 중",
            "OTT가 핵심 회수 루트",
            "OTT 중심 시장",
        ),
        "screen_access_difficulty": (
            "스크린 확보 수월",
            "스크린 확보 비교적 수월",
            "스크린 경쟁 관찰 필요",
            "스크린 확보 보통",
            "스크린 확보 까다로움",
            "스크린 확보 압박 큼",
            "스크린 확보가 흥행의 최대 장벽",
        ),
        "ticket_price_burden": (
            "티켓값 부담 낮음",
            "티켓값 부담 약함",
            "가격 민감도 관찰 필요",
            "티켓값 부담 보통",
            "티켓값 부담 높음",
            "관객이 극장 선택에 신중함",
            "티켓값이 흥행 장벽으로 작동",
        ),
        "special_format_demand": (
            "특별관 수요 거의 없음",
            "특별관 효과 제한적",
            "특별관 가능성 관찰 단계",
            "특별관 수요 보통",
            "특별관 전략 유효",
            "특별관 선점 중요",
            "특별관이 흥행 핵심",
        ),
    }
    return _level_text(labels.get(key), value, default="시장 상태 판단 보류")


def _compact_changes(deltas: dict[str, Any], labels: dict[str, str], formatter) -> str:
    if not deltas:
        return "눈에 띄는 변화 없음"
    parts: list[str] = []
    for key, label in labels.items():
        if key in deltas:
            parts.append(f"{label}: {formatter(key, deltas[key])}")
    return " · ".join(parts) if parts else "눈에 띄는 변화 없음"


def _level_text(labels: tuple[str, ...] | None, value: Any, *, default: str) -> str:
    if not labels:
        return default
    number = _number(value)
    if number >= 90:
        index = 6
    elif number >= 75:
        index = 5
    elif number >= 60:
        index = 4
    elif number >= 45:
        index = 3
    elif number >= 30:
        index = 2
    elif number >= 15:
        index = 1
    else:
        index = 0
    return labels[index]


def _delta_text(delta: Any, *, positive: str, negative: str) -> str:
    value = _number(delta)
    if value >= 8:
        return f"{positive} 큼"
    if value >= 3:
        return positive
    if value >= 1:
        return f"{positive} 조짐"
    if value <= -8:
        return f"{negative} 큼"
    if value <= -3:
        return negative
    if value <= -1:
        return f"{negative} 조짐"
    return "변화 미미"


def _number(value: Any) -> int:
    try:
        return int(round(float(value if value is not None else 0)))
    except (TypeError, ValueError):
        return 0
