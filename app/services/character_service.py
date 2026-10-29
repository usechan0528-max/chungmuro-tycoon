from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.database import dumps_json, get_connection, reset_runtime_data


NEUTRAL_POSITION = "영화인"

BASE_CASH = 300_000_000
BASE_DEBT = 0
BASE_STUDIO_FAME = 5

BASE_PLAYER_STATS = {
    "directing_ability": 45,
    "screenplay_sense": 45,
    "market_analysis": 45,
    "fundraising_ability": 45,
    "distribution_negotiation": 45,
    "marketing_sense": 45,
    "field_control": 45,
    "artistic_sense": 45,
    "commercial_sense": 45,
    "learning_ability": 50,
    "financial_risk": 18,
    "plagiarism_risk": 8,
    "press_backlash_risk": 8,
}

BASE_REPUTATION = {
    "public_reputation": 7,
    "industry_reputation": 8,
    "critic_reputation": 6,
    "investor_reputation": 6,
    "creative_reputation": 8,
    "global_reputation": 2,
}

BASE_NETWORK = {
    "actor_network": 6,
    "director_network": 6,
    "production_network": 8,
    "investor_network": 5,
    "distribution_network": 5,
    "press_network": 5,
    "critic_access": 4,
    "festival_network": 5,
    "school_network": 5,
    "regional_network": 5,
}

LEGACY_POSITION_EFFECTS = {
    "감독": {
        "stats": {
            "directing_ability": 12,
            "screenplay_sense": 10,
            "field_control": 7,
            "artistic_sense": 10,
            "fundraising_ability": -3,
            "commercial_sense": 1,
        },
        "reputation": {"creative_reputation": 6, "industry_reputation": 3},
        "network": {"director_network": 6, "production_network": 4},
    },
    "배급사 사장": {
        "cashMultiplier": 1.4,
        "stats": {
            "market_analysis": 12,
            "fundraising_ability": 9,
            "distribution_negotiation": 12,
            "marketing_sense": 8,
            "field_control": 1,
            "artistic_sense": -4,
        },
        "reputation": {"investor_reputation": 7, "industry_reputation": 3},
        "network": {"investor_network": 8, "distribution_network": 10},
        "studioFame": 3,
    },
    "대학생": {
        "cashMultiplier": 0.55,
        "stats": {
            "learning_ability": 16,
            "screenplay_sense": 3,
            "directing_ability": -3,
            "fundraising_ability": -8,
            "commercial_sense": -5,
        },
        "reputation": {"industry_reputation": -2, "creative_reputation": -1},
        "network": {"school_network": 12},
        "studioFame": -2,
    },
}


CHARACTER_OPTION_GROUPS: list[dict[str, Any]] = [
    {
        "id": "origin",
        "title": "출신",
        "description": "어디에서 영화계로 들어왔는지 정한다. 초기 인맥과 세계관이 크게 달라진다.",
        "columns": 2,
        "options": [
            {
                "id": "chungmuro_floor",
                "label": "충무로 현장 주변",
                "description": "촬영장과 제작부의 언어에 익숙하다. 현장 문제를 몸으로 먼저 이해한다.",
                "impact": "현장 장악력, 제작 인맥 상승. 투자·언론 쪽은 약하게 시작.",
                "effects": {
                    "stats": {"field_control": 9, "directing_ability": 4, "market_analysis": -2},
                    "network": {"production_network": 10, "actor_network": 3, "investor_network": -2},
                    "reputation": {"industry_reputation": 3},
                },
            },
            {
                "id": "regional_theater",
                "label": "지역 극장가/비디오가게",
                "description": "관객이 어떤 영화를 집어 드는지 오래 봐 왔다. 지방 흥행 감각이 있다.",
                "impact": "시장 분석, 지역 인맥, 2차 시장 감각 상승.",
                "effects": {
                    "stats": {"market_analysis": 8, "commercial_sense": 5, "secondary_market_fit": 5},
                    "network": {"regional_network": 10, "distribution_network": 3},
                },
            },
            {
                "id": "arts_family",
                "label": "예술계 집안",
                "description": "미술, 연극, 문학 쪽 언어에 친숙하다. 작품성의 기준이 높다.",
                "impact": "예술성, 평론가 접근도, 영화제 인맥 상승. 초기 자본 압박 소폭 상승.",
                "effects": {
                    "stats": {"artistic_sense": 10, "screenplay_sense": 4, "financial_risk": 3},
                    "network": {"critic_access": 5, "festival_network": 6},
                    "reputation": {"critic_reputation": 3, "creative_reputation": 2},
                },
            },
            {
                "id": "working_class",
                "label": "생활형 서민 출신",
                "description": "돈의 무게와 관객의 생활 감각을 안다. 허세보다 생존 계산이 빠르다.",
                "impact": "상업 감각, 재무 리스크 관리 상승. 초기 현금은 낮게 시작.",
                "effects": {
                    "cashMultiplier": 0.75,
                    "stats": {"commercial_sense": 8, "financial_risk": -4, "field_control": 3},
                    "reputation": {"public_reputation": 2},
                },
            },
            {
                "id": "corporate_finance",
                "label": "대기업/금융권 주변",
                "description": "기획서, 숫자, 투자자의 언어에 익숙하다. 대신 창작자와 거리가 있을 수 있다.",
                "impact": "투자 유치, 배급 협상, 투자 인맥 상승. 창작자 명성은 낮게 시작.",
                "effects": {
                    "cashMultiplier": 1.25,
                    "stats": {"fundraising_ability": 10, "distribution_negotiation": 7, "market_analysis": 6, "artistic_sense": -4},
                    "network": {"investor_network": 9, "distribution_network": 5, "director_network": -2},
                    "reputation": {"investor_reputation": 4, "creative_reputation": -2},
                },
            },
            {
                "id": "press_publishing",
                "label": "언론/출판 주변",
                "description": "기사의 문법과 이야기의 포장 방식을 안다. 말 한 줄의 파급력을 이해한다.",
                "impact": "언론 인맥, 시나리오 감각, 마케팅 감각 상승. 언론 역풍도 더 잘 탄다.",
                "effects": {
                    "stats": {"screenplay_sense": 5, "marketing_sense": 7, "press_backlash_risk": 3},
                    "network": {"press_network": 10, "critic_access": 3},
                    "reputation": {"public_reputation": 2},
                },
            },
            {
                "id": "overseas_returnee",
                "label": "해외 체류/유학 경험",
                "description": "해외 영화제와 장르 문법에 익숙하다. 국내 현장 관행에는 시간이 필요하다.",
                "impact": "해외 명성, 영화제 인맥, 예술성 상승. 국내 제작 인맥은 약하게 시작.",
                "effects": {
                    "stats": {"artistic_sense": 6, "market_analysis": 4},
                    "network": {"festival_network": 8, "production_network": -3, "regional_network": -2},
                    "reputation": {"global_reputation": 5, "critic_reputation": 2},
                },
            },
            {
                "id": "outsider",
                "label": "영화계 밖에서 진입",
                "description": "인맥은 부족하지만 업계 관성에 덜 묶인다. 기묘한 선택을 할 여지가 많다.",
                "impact": "학습력, 독창성 상승. 대부분의 업계 인맥은 낮게 시작.",
                "effects": {
                    "stats": {"learning_ability": 10, "screenplay_sense": 3, "fundraising_ability": -5},
                    "network": {"actor_network": -2, "director_network": -2, "production_network": -3, "investor_network": -3},
                    "reputation": {"industry_reputation": -2},
                },
            },
        ],
    },
    {
        "id": "education",
        "title": "학력 및 전공",
        "description": "훈련받은 언어를 정한다. 같은 출신이어도 어떤 문제를 먼저 보는지가 달라진다.",
        "columns": 2,
        "options": [
            {
                "id": "film_directing",
                "label": "영화연출/영상학",
                "description": "장면, 콘티, 현장 흐름을 체계적으로 배웠다.",
                "impact": "연출력, 현장 장악력 상승.",
                "effects": {"stats": {"directing_ability": 9, "field_control": 4}, "network": {"school_network": 4}},
            },
            {
                "id": "screenwriting",
                "label": "시나리오/문예창작",
                "description": "인물과 구조를 오래 붙잡고 생각하는 훈련을 했다.",
                "impact": "시나리오 감각, 평론가 명성 상승.",
                "effects": {"stats": {"screenplay_sense": 10, "plagiarism_risk": -2}, "reputation": {"critic_reputation": 2}},
            },
            {
                "id": "business_marketing",
                "label": "경영/마케팅",
                "description": "영화를 상품, 관객, 비용 구조로 읽는 데 익숙하다.",
                "impact": "시장 분석, 마케팅, 투자 유치 상승.",
                "effects": {"stats": {"market_analysis": 8, "marketing_sense": 7, "fundraising_ability": 4}},
            },
            {
                "id": "theater_acting",
                "label": "연극/연기",
                "description": "배우의 언어를 알고 리허설과 감정선을 중시한다.",
                "impact": "배우 인맥, 캐스팅 적합도, 연출력 상승.",
                "effects": {"stats": {"directing_ability": 4, "casting_fit": 5}, "network": {"actor_network": 8}},
            },
            {
                "id": "art_design",
                "label": "미술/디자인",
                "description": "공간, 색, 의상, 포스터의 힘을 먼저 본다.",
                "impact": "예술성, 마케팅 감각, 미술 완성도 감각 상승.",
                "effects": {"stats": {"artistic_sense": 8, "marketing_sense": 3, "art_costume_prop_quality": 4}},
            },
            {
                "id": "engineering_vfx",
                "label": "공학/VFX",
                "description": "기술적 구현과 제작 파이프라인에 강하다.",
                "impact": "시장 분석, VFX 감각, 예산 관리 상승.",
                "effects": {"stats": {"market_analysis": 4, "vfx_quality": 5, "budget_overrun_risk": -3}},
            },
            {
                "id": "social_history",
                "label": "사회학/역사",
                "description": "소재의 맥락과 사회적 파장을 민감하게 읽는다.",
                "impact": "시나리오 감각, 예술성 상승. 논란 리스크도 같이 오른다.",
                "effects": {"stats": {"screenplay_sense": 5, "artistic_sense": 5, "controversy_risk": 4}, "reputation": {"critic_reputation": 2}},
            },
            {
                "id": "self_taught",
                "label": "비전공 독학",
                "description": "정규 교육은 없지만 빠르게 배우고 편견 없이 흡수한다.",
                "impact": "학습력 상승. 초기 업계 신뢰는 낮음.",
                "effects": {"stats": {"learning_ability": 12, "field_control": -2}, "reputation": {"industry_reputation": -2}, "network": {"school_network": -4}},
            },
        ],
    },
    {
        "id": "trait",
        "title": "성향",
        "description": "선택지 판정과 이벤트 대응의 기본 결을 만든다.",
        "columns": 2,
        "options": [
            {
                "id": "perfectionist",
                "label": "완벽주의",
                "description": "완성도를 위해 오래 붙잡는다. 좋은 영화가 나오지만 일정은 자주 흔들린다.",
                "impact": "연출/편집 감각 상승, 일정 지연 리스크 상승.",
                "effects": {"stats": {"directing_ability": 5, "artistic_sense": 5, "editing_quality": 3, "schedule_delay_risk": 5}},
            },
            {
                "id": "field_leader",
                "label": "현장형 리더",
                "description": "현장에서 빠르게 판단하고 사람을 움직인다.",
                "impact": "현장 장악력, 제작 인맥 상승.",
                "effects": {"stats": {"field_control": 10, "schedule_delay_risk": -3}, "network": {"production_network": 4}},
            },
            {
                "id": "relationship_builder",
                "label": "관계중심",
                "description": "사람을 설득하고 오래 관리하는 데 강하다.",
                "impact": "배우/투자/언론 인맥 상승, 강한 대립 선택은 약함.",
                "effects": {"network": {"actor_network": 5, "investor_network": 4, "press_network": 4}, "stats": {"field_control": 2}},
            },
            {
                "id": "numbers_strategist",
                "label": "숫자형 전략가",
                "description": "관객, 비용, 리스크를 표로 본다. 감정적 설득은 약할 수 있다.",
                "impact": "시장 분석, 투자 유치, 배급 협상 상승.",
                "effects": {"stats": {"market_analysis": 10, "fundraising_ability": 5, "distribution_negotiation": 5, "artistic_sense": -2}},
            },
            {
                "id": "auteur",
                "label": "작가주의",
                "description": "한 편의 영화가 자기 세계를 가져야 한다고 믿는다.",
                "impact": "예술성, 평론가 명성 상승. 투자자 명성은 낮게 시작.",
                "effects": {"stats": {"artistic_sense": 10, "screenplay_sense": 4, "commercial_sense": -4}, "reputation": {"critic_reputation": 4, "investor_reputation": -2}},
            },
            {
                "id": "popular_entertainer",
                "label": "대중오락 지향",
                "description": "관객이 돈을 내고 즐길 순간을 먼저 떠올린다.",
                "impact": "상업 감각, 마케팅 감각 상승. 평론가 명성은 낮게 시작.",
                "effects": {"stats": {"commercial_sense": 10, "marketing_sense": 5, "artistic_sense": -2}, "reputation": {"critic_reputation": -1, "investor_reputation": 2}},
            },
            {
                "id": "gambler",
                "label": "승부사",
                "description": "큰 판을 겁내지 않는다. 성공하면 빨리 올라가지만 실패도 크다.",
                "impact": "투자 유치, 사전 관심도 상승. 게임오버 리스크도 상승.",
                "effects": {"stats": {"fundraising_ability": 6, "commercial_sense": 4, "game_over_risk": 5}, "reputation": {"public_reputation": 2}},
            },
            {
                "id": "careful_manager",
                "label": "신중한 관리자",
                "description": "작게 잃고 오래 살아남는 판단을 선호한다.",
                "impact": "재무 리스크 감소, 배급 협상 상승. 폭발력은 낮음.",
                "effects": {"stats": {"financial_risk": -6, "distribution_negotiation": 4, "pre_release_interest": -2}},
            },
        ],
    },
    {
        "id": "reputation_seed",
        "title": "초기 명성",
        "description": "시작 전에 업계가 당신을 얼마나 알고 있는지 정한다.",
        "columns": 2,
        "options": [
            {
                "id": "unknown",
                "label": "완전 무명",
                "description": "아무도 모른다. 대신 기대도, 선입견도 없다.",
                "impact": "명성 낮음, 리스크 낮음, 학습력 소폭 상승.",
                "effects": {"stats": {"learning_ability": 3, "press_backlash_risk": -2}},
            },
            {
                "id": "short_film_buzz",
                "label": "단편 화제",
                "description": "작은 영화제나 학교 상영에서 이름이 한 번 돌았다.",
                "impact": "창작자/평론가 명성, 영화제 인맥 상승.",
                "effects": {"reputation": {"creative_reputation": 4, "critic_reputation": 3}, "network": {"festival_network": 4, "school_network": 3}},
            },
            {
                "id": "field_reliable",
                "label": "현장 평판 있음",
                "description": "스태프들 사이에서 약속을 지키는 사람으로 알려져 있다.",
                "impact": "업계 명성, 제작 인맥 상승. 큰 화제성은 없음.",
                "effects": {"reputation": {"industry_reputation": 5}, "network": {"production_network": 5}, "stats": {"schedule_delay_risk": -2}},
            },
            {
                "id": "press_familiar",
                "label": "언론에 익숙함",
                "description": "기자와 인터뷰 경험이 있고 얼굴을 아는 사람이 있다.",
                "impact": "대중 명성, 언론 인맥 상승. 말실수 리스크도 소폭 상승.",
                "effects": {"reputation": {"public_reputation": 5}, "network": {"press_network": 6}, "stats": {"press_backlash_risk": 3}},
            },
            {
                "id": "investor_known",
                "label": "투자자에게 알려짐",
                "description": "작은 기획서나 실무 경험으로 투자자 몇 명이 이름을 안다.",
                "impact": "투자자 명성, 투자 인맥 상승.",
                "effects": {"reputation": {"investor_reputation": 6}, "network": {"investor_network": 6}, "stats": {"fundraising_ability": 2}},
            },
            {
                "id": "minor_bad_blood",
                "label": "작은 미운털",
                "description": "전작이나 현장에서 작은 갈등이 있었다. 불리하지만 드라마는 있다.",
                "impact": "업계/투자자 명성 하락, 창작자 명성 소폭 상승.",
                "effects": {"reputation": {"industry_reputation": -4, "investor_reputation": -3, "creative_reputation": 2}, "stats": {"press_backlash_risk": 4}},
            },
        ],
    },
    {
        "id": "wealth",
        "title": "재산",
        "description": "시작 현금과 실패 내성을 정한다. 돈은 자유도이자 압박이다.",
        "columns": 2,
        "options": [
            {
                "id": "empty_hands",
                "label": "빈손",
                "description": "당장 쓸 돈이 거의 없다. 작게 시작해야 하지만 실패 비용도 낮다.",
                "impact": "현금 2천만 원. 학습력 상승, 투자 유치 난이도 상승.",
                "effects": {"cash": 20_000_000, "stats": {"learning_ability": 4, "fundraising_ability": -4, "financial_risk": 5}},
            },
            {
                "id": "thin_savings",
                "label": "빠듯한 저축",
                "description": "단편과 초저예산 기획은 가능하지만 오래 버티기는 어렵다.",
                "impact": "현금 1억 원. 재무 리스크 소폭 상승.",
                "effects": {"cash": 100_000_000, "stats": {"financial_risk": 3}},
            },
            {
                "id": "normal",
                "label": "보통",
                "description": "독립영화 또는 작은 장르영화를 준비할 수 있는 현실적인 출발점이다.",
                "impact": "현금 3억 원. 균형형.",
                "effects": {"cash": 300_000_000},
            },
            {
                "id": "family_capital",
                "label": "가족/지인 자본",
                "description": "초기 자본은 넉넉하지만 실패하면 사적 관계의 압박도 커진다.",
                "impact": "현금 10억 원, 투자자 명성 상승, 게임오버 리스크 소폭 상승.",
                "effects": {"cash": 1_000_000_000, "reputation": {"investor_reputation": 2}, "stats": {"game_over_risk": 3}},
            },
            {
                "id": "investment_promise",
                "label": "투자 검토 약속",
                "description": "돈이 확정된 건 아니지만 초기 미팅을 잡을 수 있는 사람이 있다.",
                "impact": "현금 5억 원, 투자 인맥과 투자 유치력 상승.",
                "effects": {"cash": 500_000_000, "stats": {"fundraising_ability": 5}, "network": {"investor_network": 6}},
            },
            {
                "id": "debt_backed",
                "label": "빚으로 마련한 자본",
                "description": "돈은 있지만 마음이 편하지 않다. 빠르게 결과를 내야 한다.",
                "impact": "현금 8억 원, 부채 4억 원, 재무 리스크 상승.",
                "effects": {"cash": 800_000_000, "debt": 400_000_000, "stats": {"financial_risk": 12, "commercial_sense": 3}},
            },
            {
                "id": "capitalist",
                "label": "자본가",
                "description": "영화계 경험은 부족해도 자기 돈으로 큰 판을 열 수 있다. 대신 업계는 당신을 창작자보다 자금줄로 먼저 본다.",
                "impact": "선택 시대 기준 대형 상업영화 1편을 시작할 수 있는 자기자본 확보. 투자/배급 인맥 상승, 창작자 신뢰와 현장 리스크는 부담.",
                "effects": {
                    "largeFilmCapital": True,
                    "studioFame": 8,
                    "stats": {
                        "market_analysis": 6,
                        "fundraising_ability": 8,
                        "distribution_negotiation": 6,
                        "commercial_sense": 5,
                        "field_control": -4,
                        "financial_risk": -8,
                        "game_over_risk": 6,
                    },
                    "reputation": {
                        "investor_reputation": 10,
                        "industry_reputation": 4,
                        "creative_reputation": -3,
                    },
                    "network": {
                        "investor_network": 12,
                        "distribution_network": 8,
                        "press_network": 4,
                        "production_network": -2,
                    },
                },
            },
        ],
    },
    {
        "id": "first_contact",
        "title": "첫 업계 접점",
        "description": "처음 누구를 통해 영화계 문을 열었는지 정한다.",
        "columns": 2,
        "options": [
            {
                "id": "festival_volunteer",
                "label": "영화제 자원활동",
                "description": "프로그래머와 독립영화 사람들을 가까이서 봤다.",
                "impact": "영화제 인맥, 평론가 접근도 상승.",
                "effects": {"network": {"festival_network": 7, "critic_access": 2}, "reputation": {"critic_reputation": 1}},
            },
            {
                "id": "theater_part_timer",
                "label": "극장 아르바이트",
                "description": "관객이 언제 웃고 언제 나가는지 직접 봤다.",
                "impact": "시장 분석, 지역 인맥, 상업 감각 상승.",
                "effects": {"stats": {"market_analysis": 5, "commercial_sense": 4}, "network": {"regional_network": 4}},
            },
            {
                "id": "ad_mv_set",
                "label": "광고/뮤직비디오 현장",
                "description": "짧은 시간 안에 이미지를 뽑아내는 현장에 익숙하다.",
                "impact": "마케팅 감각, 촬영 감각, 현장 장악력 상승.",
                "effects": {"stats": {"marketing_sense": 5, "shooting_quality": 3, "field_control": 3}, "network": {"production_network": 3}},
            },
            {
                "id": "online_cinephile",
                "label": "온라인 영화 커뮤니티",
                "description": "말 많은 관객과 시네필의 반응을 먼저 읽는다.",
                "impact": "온라인 화제성 감각, 평론가 접근도 상승. 언론 역풍 리스크도 상승.",
                "effects": {"stats": {"online_buzz": 4, "market_analysis": 3, "press_backlash_risk": 3}, "network": {"critic_access": 2}},
            },
            {
                "id": "short_film_crew",
                "label": "단편 제작 크루",
                "description": "적은 돈으로 어떻게든 찍는 법을 배웠다.",
                "impact": "제작 인맥, 연출력, 학습력 상승.",
                "effects": {"stats": {"directing_ability": 4, "learning_ability": 4, "financial_risk": -2}, "network": {"production_network": 5, "school_network": 3}},
            },
            {
                "id": "location_assistant",
                "label": "로케이션 보조",
                "description": "장소 섭외와 지역 관계의 중요성을 몸으로 배웠다.",
                "impact": "지역 인맥, 제작 인맥, 일정 리스크 관리 상승.",
                "effects": {"network": {"regional_network": 7, "production_network": 3}, "stats": {"schedule_delay_risk": -3}},
            },
        ],
    },
    {
        "id": "obsession",
        "title": "창작 집착",
        "description": "영화를 만들 때 끝까지 포기하지 못하는 한 가지다.",
        "columns": 2,
        "options": [
            {
                "id": "actor_face",
                "label": "배우의 얼굴",
                "description": "좋은 얼굴과 순간이 영화를 살린다고 믿는다.",
                "impact": "배우 인맥, 캐스팅 적합도, 연기 품질 감각 상승.",
                "effects": {"network": {"actor_network": 5}, "stats": {"casting_fit": 5, "acting_quality": 3}},
            },
            {
                "id": "genre_pleasure",
                "label": "장르 쾌감",
                "description": "관객이 원하는 장르적 보상을 정확히 주고 싶어 한다.",
                "impact": "장르 만족도, 상업 감각 상승.",
                "effects": {"stats": {"genre_satisfaction": 5, "commercial_sense": 5}},
            },
            {
                "id": "social_message",
                "label": "사회적 메시지",
                "description": "영화가 시대와 부딪혀야 한다고 믿는다.",
                "impact": "평론가 명성, 예술성 상승. 논란 리스크 상승.",
                "effects": {"stats": {"artistic_sense": 5, "controversy_risk": 5}, "reputation": {"critic_reputation": 3}},
            },
            {
                "id": "visual_space",
                "label": "미술과 공간",
                "description": "장면의 설득력은 공간에서 시작된다고 본다.",
                "impact": "미술/의상/소품 품질, 예술성 상승.",
                "effects": {"stats": {"art_costume_prop_quality": 6, "artistic_sense": 4}},
            },
            {
                "id": "sound_rhythm",
                "label": "사운드와 리듬",
                "description": "편집 리듬과 소리의 힘을 중요하게 본다.",
                "impact": "음악/음향, 편집 감각 상승.",
                "effects": {"stats": {"music_sound_quality": 5, "editing_quality": 5}},
            },
            {
                "id": "ip_world",
                "label": "IP와 세계관",
                "description": "한 편으로 끝나지 않는 세계를 만들고 싶어 한다.",
                "impact": "IP 가치, 프랜차이즈 감각, 시장 분석 상승.",
                "effects": {"stats": {"ip_value": 5, "world_expansion": 5, "market_analysis": 3}},
            },
        ],
    },
    {
        "id": "weakness",
        "title": "약점",
        "description": "불리한 점을 하나 정한다. 약점은 이벤트를 더 입체적으로 만든다.",
        "columns": 2,
        "options": [
            {
                "id": "bad_with_money",
                "label": "돈 계산에 약함",
                "description": "작품 이야기는 잘하지만 정산표 앞에서 판단이 느리다.",
                "impact": "시장/투자 능력 하락, 재무 리스크 상승.",
                "effects": {"stats": {"market_analysis": -5, "fundraising_ability": -4, "financial_risk": 8}},
            },
            {
                "id": "awkward_relationships",
                "label": "관계에 서툼",
                "description": "진심은 있지만 말이 늦거나 직설적이다.",
                "impact": "인맥 전반 하락, 창작자 명성 소폭 상승.",
                "effects": {"network": {"actor_network": -3, "investor_network": -3, "press_network": -3}, "reputation": {"creative_reputation": 1}},
            },
            {
                "id": "overwork",
                "label": "과로 성향",
                "description": "버티는 힘은 있지만 오래 가면 판단이 흐려질 수 있다.",
                "impact": "현장 장악력 상승, 일정/갈등 리스크 상승.",
                "effects": {"stats": {"field_control": 3, "schedule_delay_risk": 4, "on_set_conflict_risk": 4}},
            },
            {
                "id": "perfection_delay",
                "label": "완성도 강박",
                "description": "작은 흠도 못 지나친다. 후반작업이 길어지기 쉽다.",
                "impact": "예술성 상승, 일정 지연과 예산 초과 리스크 상승.",
                "effects": {"stats": {"artistic_sense": 3, "schedule_delay_risk": 6, "budget_overrun_risk": 5}},
            },
            {
                "id": "press_anxiety",
                "label": "언론 앞 긴장",
                "description": "카메라와 기자 질문 앞에서 말이 꼬인다.",
                "impact": "언론 인맥과 마케팅 감각 하락, 언론 역풍 리스크 상승.",
                "effects": {"stats": {"marketing_sense": -3, "press_backlash_risk": 6}, "network": {"press_network": -4}},
            },
            {
                "id": "safe_choice",
                "label": "안전한 선택에 갇힘",
                "description": "리스크를 너무 피하다가 작품의 인상이 약해질 수 있다.",
                "impact": "재무 리스크 하락, 예술성과 사전 관심도 하락.",
                "effects": {"stats": {"financial_risk": -5, "artistic_sense": -4, "pre_release_interest": -3}},
            },
        ],
    },
]


def get_character_option_groups() -> list[dict[str, Any]]:
    return deepcopy(CHARACTER_OPTION_GROUPS)


def create_new_character(data: dict[str, Any]) -> None:
    reset_runtime_data()
    era_id = data["era_id"]

    selections = _resolve_selections(data)
    build = _build_initial_state(selections, data)
    position = str(data.get("position") or NEUTRAL_POSITION)
    if position in LEGACY_POSITION_EFFECTS:
        _apply_option_effects(build, LEGACY_POSITION_EFFECTS[position])
    else:
        position = NEUTRAL_POSITION

    with get_connection() as conn:
        era = conn.execute("SELECT * FROM eras WHERE id = ?", (era_id,)).fetchone()
        if not era:
            raise ValueError("선택한 시대를 찾을 수 없습니다.")
        _apply_large_film_capital_if_needed(conn, build, selections, int(era["start_year"]))

        selection_labels = {
            category_id: option["label"]
            for category_id, option in selections.items()
        }
        build["stats"].update(
            {
                "origin": selection_labels.get("origin"),
                "origin_id": selections.get("origin", {}).get("id"),
                "education": selection_labels.get("education"),
                "education_id": selections.get("education", {}).get("id"),
                "trait": selection_labels.get("trait"),
                "trait_id": selections.get("trait", {}).get("id"),
                "reputation_seed": selection_labels.get("reputation_seed"),
                "wealth": selection_labels.get("wealth"),
                "first_contact": selection_labels.get("first_contact"),
                "obsession": selection_labels.get("obsession"),
                "weakness": selection_labels.get("weakness"),
                "character_summary": _character_summary(selection_labels),
            }
        )

        name = data["name"].strip()
        age = int(data.get("age") or 25)
        cash = max(0, int(build["cash"]))
        debt = max(0, int(build["debt"]))
        fame = _clamp(build["studio_fame"])

        conn.execute(
            """
            INSERT INTO player_state (
                id, name, gender, age, current_year, current_month, current_day, position,
                cash, debt, stats_json, reputation_json, network_json
            ) VALUES (1, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                data.get("gender"),
                age,
                era["start_year"],
                position,
                cash,
                debt,
                dumps_json(build["stats"]),
                dumps_json(build["reputation"]),
                dumps_json(build["network"]),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_player_state (
                id, name, gender, age, current_year, current_month, current_day, position,
                cash, debt, stats_json, reputation_json, network_json
            ) VALUES (1, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                data.get("gender"),
                age,
                era["start_year"],
                position,
                cash,
                debt,
                dumps_json(build["stats"]),
                dumps_json(build["reputation"]),
                dumps_json(build["network"]),
            ),
        )
        credit_limit = _initial_credit_limit(build["reputation"], fame, debt)

        conn.execute(
            """
            INSERT INTO studio_state (
                id, studio_name, fame, cash, debt,
                own_capital, investment_capital, loan_capital, loan_balance, credit_limit
            )
            VALUES (1, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (f"{name} 필름", fame, cash, debt, cash, debt, credit_limit),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_studio_state (
                id, studio_name, fame, cash, debt,
                own_capital, investment_capital, loan_capital, loan_balance, credit_limit
            )
            VALUES (1, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (f"{name} 필름", fame, cash, debt, cash, debt, credit_limit),
        )
        conn.commit()

    from app.services.ticket_price_service import ensure_ticket_price_history
    from app.services.historical_release_service import (
        backfill_historical_releases_until,
        ensure_historical_releases_for_month,
    )
    from app.services.market_service import ensure_market_state_for_month
    from app.services.npc_activity_service import ensure_npc_releases_for_month
    from app.services.world_bootstrap_service import bootstrap_world_history_for_start

    start_year = int(era["start_year"])
    ensure_ticket_price_history(1980, max(2035, start_year + 20))
    ensure_market_state_for_month(start_year, 1, refresh=True)
    bootstrap_world_history_for_start(start_year, 1)
    backfill_historical_releases_until(start_year, 1)
    ensure_historical_releases_for_month(start_year, 1)
    ensure_npc_releases_for_month(start_year, 1)

    from app.services.calendar_service import add_calendar_event

    add_calendar_event(
        title=f"{name} 필름 출범",
        event_type="career_start",
        description=f"{era['name']}에 {selection_labels.get('origin', '영화계 밖')} 출신 영화인으로 커리어를 시작했다.",
        metadata={
            "eraId": era_id,
            "position": position,
            "selections": {
                category_id: option["id"]
                for category_id, option in selections.items()
            },
        },
    )


def _resolve_selections(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selections: dict[str, dict[str, Any]] = {}
    legacy_field_map = {
        "wealth": "wealth",
        "background": "origin",
        "education": "education",
        "trait": "trait",
        "career": "first_contact",
    }
    for group in CHARACTER_OPTION_GROUPS:
        group_id = group["id"]
        raw_id = data.get(f"{group_id}_id") or data.get(group_id)
        legacy_label = None
        for field, mapped_group in legacy_field_map.items():
            if mapped_group == group_id:
                legacy_label = data.get(field)
                break
        selections[group_id] = _find_option(group, raw_id=raw_id, legacy_label=legacy_label)
    return selections


def _find_option(group: dict[str, Any], *, raw_id: Any, legacy_label: Any) -> dict[str, Any]:
    options = group["options"]
    if raw_id:
        for option in options:
            if option["id"] == raw_id or option["label"] == raw_id:
                return option
    if legacy_label:
        for option in options:
            if option["label"] == legacy_label:
                return option
        mapped = _legacy_label_to_option_id(group["id"], str(legacy_label))
        if mapped:
            for option in options:
                if option["id"] == mapped:
                    return option
    return options[0]


def _legacy_label_to_option_id(group_id: str, label: str) -> str | None:
    legacy_map = {
        "wealth": {
            "빈손": "empty_hands",
            "보통": "normal",
            "든든한 투자 약속": "investment_promise",
            "가족 자본": "family_capital",
        },
        "origin": {
            "서울 충무로권": "chungmuro_floor",
            "지역 극장가": "regional_theater",
            "예술계 집안": "arts_family",
            "자수성가": "working_class",
            "해외 유학파": "overseas_returnee",
        },
        "education": {
            "영화 연출": "film_directing",
            "시나리오": "screenwriting",
            "경영/마케팅": "business_marketing",
            "연극영화": "theater_acting",
            "비전공": "self_taught",
        },
        "trait": {
            "완벽주의": "perfectionist",
            "승부사": "gambler",
            "관계중심": "relationship_builder",
            "작가주의": "auteur",
            "상업감각": "popular_entertainer",
        },
        "first_contact": {
            "현장 스태프": "short_film_crew",
            "영화 동아리": "short_film_crew",
            "광고/뮤직비디오": "ad_mv_set",
            "언론/홍보": "online_cinephile",
            "무경력": "theater_part_timer",
        },
    }
    return legacy_map.get(group_id, {}).get(label)


def _build_initial_state(
    selections: dict[str, dict[str, Any]],
    data: dict[str, Any],
) -> dict[str, Any]:
    build = {
        "cash": BASE_CASH,
        "debt": BASE_DEBT,
        "studio_fame": BASE_STUDIO_FAME,
        "stats": dict(BASE_PLAYER_STATS),
        "reputation": dict(BASE_REPUTATION),
        "network": dict(BASE_NETWORK),
    }
    for group_id in (
        "origin",
        "education",
        "trait",
        "reputation_seed",
        "wealth",
        "first_contact",
        "obsession",
        "weakness",
    ):
        _apply_option_effects(build, selections[group_id].get("effects", {}))
    age = int(data.get("age") or 25)
    if age <= 24:
        _apply_option_effects(build, {"stats": {"learning_ability": 4, "fundraising_ability": -2}, "reputation": {"industry_reputation": -1}})
    elif age >= 45:
        _apply_option_effects(build, {"stats": {"field_control": 3, "learning_ability": -2}, "network": {"production_network": 2}})
    return build


def _apply_option_effects(build: dict[str, Any], effects: dict[str, Any]) -> None:
    if not effects:
        return
    if "cash" in effects:
        build["cash"] = int(effects["cash"])
    if "cashDelta" in effects:
        build["cash"] += int(effects["cashDelta"])
    if "cashMultiplier" in effects:
        build["cash"] = int(build["cash"] * float(effects["cashMultiplier"]))
    if "debt" in effects:
        build["debt"] += int(effects["debt"])
    if "studioFame" in effects:
        build["studio_fame"] += int(effects["studioFame"])
    for section in ("stats", "reputation", "network"):
        values = effects.get(section, {})
        if not isinstance(values, dict):
            continue
        for key, delta in values.items():
            build[section][key] = _clamp(float(build[section].get(key, 50)) + float(delta))


def _character_summary(selection_labels: dict[str, str]) -> str:
    return (
        f"{selection_labels.get('origin', '무명')} 출신, "
        f"{selection_labels.get('education', '비전공')} 기반, "
        f"{selection_labels.get('trait', '균형형')} 성향의 영화인"
    )


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _initial_credit_limit(reputation: dict[str, Any], fame: int, debt: int) -> int:
    investor_reputation = int(reputation.get("investor_reputation") or 0)
    industry_reputation = int(reputation.get("industry_reputation") or 0)
    base = 150_000_000
    reputation_limit = (investor_reputation * 8_000_000) + (industry_reputation * 4_000_000)
    fame_limit = int(fame) * 12_000_000
    return max(50_000_000, int(base + reputation_limit + fame_limit - int(debt or 0) * 0.25))


def _apply_large_film_capital_if_needed(
    conn: Any,
    build: dict[str, Any],
    selections: dict[str, dict[str, Any]],
    start_year: int,
) -> None:
    wealth = selections.get("wealth") or {}
    effects = wealth.get("effects") if isinstance(wealth.get("effects"), dict) else {}
    if not effects.get("largeFilmCapital"):
        return
    scale = conn.execute("SELECT * FROM project_scales WHERE id = 'scale_large_commercial'").fetchone()
    if not scale:
        fallback_cash = 12_000_000_000
        build["cash"] = max(int(build["cash"]), fallback_cash)
        build["stats"]["capitalist_budget_basis"] = "대형 상업영화 기준 스케일 데이터 없음: 120억 원으로 보정"
        return

    from app.services.economic_service import adjusted_scale_budget

    adjusted = adjusted_scale_budget(dict(scale), start_year)
    minimum_production_budget = int(adjusted["min_budget"])
    target_cash = _round_starting_capital(minimum_production_budget * 1.5)
    build["cash"] = max(int(build["cash"]), target_cash)
    build["stats"]["capitalist_budget_basis"] = (
        f"{start_year}년 기준 대형 상업영화 최소 순제작비와 마케팅/예비비를 감안한 자기자본"
    )
    build["stats"]["capitalist_large_film_budget"] = target_cash


def _round_starting_capital(value: float) -> int:
    unit = 10_000_000
    return int(round(float(value) / unit) * unit)
