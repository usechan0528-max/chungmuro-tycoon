from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
PEOPLE_DIR = ROOT_DIR / "data" / "seed" / "people"

ACTOR_GROUPS = [
    (
        "1980~1990년대 기반 배우",
        1980,
        [
            "안성기", "박중훈", "최민수", "문성근", "이덕화", "이경영", "신성일", "남궁원", "김희라", "전무송",
            "독고영재", "한석규", "송강호", "최민식", "설경구", "박신양", "김윤석", "정재영", "김상경", "감우성",
        ],
    ),
    (
        "1990~2000년대 남성 스타/주연급",
        1990,
        [
            "이병헌", "정우성", "장동건", "이정재", "유오성", "유지태", "차승원", "신하균", "황정민", "류승범",
            "조승우", "차태현", "임창정", "이성재", "박해일", "장혁", "권상우", "김주혁", "공유", "강동원",
        ],
    ),
    (
        "2000~2010년대 남성 배우",
        2000,
        [
            "하정우", "조인성", "현빈", "소지섭", "원빈", "류승룡", "오달수", "마동석", "이선균", "유해진",
            "조진웅", "김성균", "진구", "엄태웅", "김남길", "주지훈", "이제훈", "박정민", "강하늘", "김무열",
        ],
    ),
    (
        "2010~2020년대 남성 배우",
        2010,
        [
            "이희준", "곽도원", "진선규", "이성민", "조우진", "손석구", "구교환", "최우식", "류준열", "임시완",
            "유아인", "변요한", "김우빈", "김수현", "도경수", "박서준", "이도현", "정해인", "남주혁", "이준호",
        ],
    ),
    (
        "2010~2020년대 남성 조연/캐릭터 배우",
        2010,
        [
            "이동휘", "김대명", "위하준", "김동욱", "강기영", "허성태", "김영광", "이준혁", "김선호", "공명",
            "성동일", "정만식", "김의성", "박명훈", "박혁권", "고창석", "조희봉", "김병철", "배성우", "배성재",
        ],
    ),
    (
        "1980~2000년대 여성 배우",
        1980,
        [
            "강수연", "이미숙", "장미희", "윤정희", "원미경", "윤여정", "나문희", "김혜자", "고두심", "전도연",
            "심은하", "고소영", "이미연", "엄정화", "김혜수", "최진실", "이영애", "문소리", "장진영", "전지현",
        ],
    ),
    (
        "2000~2010년대 여성 배우",
        2000,
        [
            "손예진", "김하늘", "임수정", "수애", "김정은", "하지원", "공효진", "배두나", "염정아", "김민희",
            "김옥빈", "한효주", "한지민", "천우희", "한예리", "김고은", "박보영", "정유미", "라미란", "이정은",
        ],
    ),
    (
        "2010~2020년대 여성 배우",
        2010,
        [
            "김태리", "박소담", "전종서", "김다미", "고윤정", "정호연", "이유미", "김혜윤", "김세정", "김유정",
            "김소현", "문가영", "신혜선", "전여빈", "정은채", "고아성", "심은경", "김향기", "한소희", "노윤서",
        ],
    ),
    (
        "여성 조연/중견/신스틸러",
        1990,
        ["김해숙", "김선영", "장영남", "김서형", "전혜진", "염혜란", "박지영", "서영희", "문정희", "김수미"],
    ),
]

DIRECTOR_GROUPS = [
    ("보호 감독군", 1955, ["봉준호", "박찬욱", "이창동", "김기영", "최동훈"]),
    (
        "1980~1990년대 주요 감독",
        1980,
        ["임권택", "이장호", "배창호", "정지영", "하길종", "유현목", "이만희", "고영남", "이두용", "곽지균", "박철수", "장선우", "박광수", "강제규", "김의석"],
    ),
    (
        "1990~2000년대 주요 감독",
        1990,
        ["이명세", "김성수", "박종원", "여균동", "홍상수", "김지운", "송능한", "장진", "심형래", "강우석", "곽경택", "이준익", "장준환", "민규동", "허진호"],
    ),
    (
        "2000~2010년대 주요 감독",
        2000,
        ["임상수", "김기덕", "류승완", "윤제균", "나홍진", "김용화", "장훈", "이해영", "안병기", "김태용", "정윤철", "강형철", "윤종빈", "김한민", "한재림"],
    ),
    (
        "2010~2020년대 주요 감독",
        2010,
        ["연상호", "장재현", "양우석", "우민호", "김성훈", "김용훈", "이병헌", "변성현", "황동혁", "이원석", "조성희", "엄태화", "원신연", "김지훈", "이석훈"],
    ),
    (
        "2020년대 및 독립/신진 계열",
        2020,
        ["박훈정", "강윤성", "이상용", "홍원찬", "김보라", "윤가은", "정주리", "조현철", "유재선", "남동협", "김세휘", "이충현", "정범식", "조의석", "허명행"],
    ),
]

CRITICS = [
    ("이동진", 1990, ["대중영향형", "시네필형"]),
    ("정성일", 1988, ["시네필형", "작가주의형"]),
    ("박평식", 1988, ["엄격채점형", "한줄평영향형"]),
    ("김혜리", 1995, ["인터뷰심층형", "서사감수성형"]),
    ("허지웅", 2000, ["대중영향형", "논쟁촉발형"]),
    ("듀나", 1994, ["장르전문형", "SF감수성형"]),
    ("심영섭", 1995, ["심리분석형", "감정독해형"]),
    ("황진미", 2000, ["사회비평형", "젠더감수성형"]),
    ("유지나", 1990, ["시네필형", "사회비평형"]),
    ("이용철", 1998, ["장르분석형", "평론지형"]),
    ("전찬일", 1995, ["산업분석형", "영화제형"]),
    ("강유정", 2000, ["문학서사형", "대중영향형"]),
    ("송경원", 2008, ["시네필형", "장르분석형"]),
    ("김도훈", 2000, ["대중문화형", "장르친화형"]),
    ("이다혜", 2005, ["서사감수성형", "대중문화형"]),
    ("김소미", 2010, ["인터뷰심층형", "현장관찰형"]),
    ("남다은", 2010, ["시네필형", "작가주의형"]),
    ("장영엽", 2010, ["산업분석형", "인터뷰형"]),
    ("배동미", 2010, ["대중문화형", "서사감수성형"]),
    ("김철홍", 2010, ["장르분석형", "산업분석형"]),
]

ID_OVERRIDES = {
    "송강호": "song_kang_ho",
    "최민식": "choi_min_sik",
    "전도연": "jeon_do_yeon",
    "김혜수": "kim_hye_soo",
    "봉준호": "bong_joon_ho",
    "박찬욱": "park_chan_wook",
    "이창동": "lee_chang_dong",
    "김기영": "kim_ki_young",
    "최동훈": "choi_dong_hoon",
    "이동진": "lee_dongjin",
    "정성일": "jung_sungil",
    "박평식": "park_pyeongsik",
    "김혜리": "kim_hyeri",
    "허지웅": "heo_jiwoong",
    "듀나": "djuna",
    "심영섭": "shim_youngseop",
    "황진미": "hwang_jinmi",
    "유지나": "yoo_jina",
    "이용철": "lee_yongcheol",
    "전찬일": "jeon_chanil",
    "강유정": "kang_yujeong",
    "송경원": "song_kyungwon",
    "김도훈": "kim_dohoon",
    "이다혜": "lee_dahye",
    "김소미": "kim_somi",
    "남다은": "nam_daeun",
    "장영엽": "jang_youngyeop",
    "배동미": "bae_dongmi",
    "김철홍": "kim_cheolhong",
}

NAME_EN_OVERRIDES = {
    "송강호": "Song Kang-ho",
    "최민식": "Choi Min-sik",
    "전도연": "Jeon Do-yeon",
    "김혜수": "Kim Hye-soo",
    "봉준호": "Bong Joon-ho",
    "박찬욱": "Park Chan-wook",
    "이창동": "Lee Chang-dong",
    "김기영": "Kim Ki-young",
    "최동훈": "Choi Dong-hoon",
}

BIO_OVERRIDES = {
    "송강호": {"birthYear": 1967, "availableFrom": 1996, "protectionLevel": "protectedForSomeEvents"},
    "봉준호": {"birthYear": 1969, "availableFrom": 2000, "protectionLevel": "legendaryProtected", "historicalFilmographyLocked": True},
    "박찬욱": {"birthYear": 1963, "availableFrom": 1992, "protectionLevel": "legendaryProtected", "historicalFilmographyLocked": True},
    "이창동": {"birthYear": 1954, "availableFrom": 1997, "protectionLevel": "legendaryProtected", "historicalFilmographyLocked": True},
    "김기영": {"birthYear": 1919, "availableFrom": 1955, "protectionLevel": "legacyProtected", "historicalFilmographyLocked": True},
    "최동훈": {"birthYear": 1971, "availableFrom": 2004, "protectionLevel": "majorProtected", "historicalFilmographyLocked": True},
}

PUBLIC_PROFILE_OVERRIDES = {
    "송강호": {
        "oneLine": "연기력과 대중 신뢰를 동시에 갖춘 한국영화 대표 배우.",
        "currentAbilityText": "상업영화와 작가주의 영화 모두에서 강한 존재감을 발휘한다.",
        "potentialText": "이미 완성형 배우에 가깝다. 작품 선택과 시대 흐름이 중요하다.",
        "fameText": "한국 영화계를 대표하는 배우로 평가된다.",
        "brandText": "관객과 평론가 모두에게 신뢰가 높으며, 해외 시장에서도 인지도가 높다.",
    },
    "봉준호": {
        "oneLine": "작가주의와 상업성을 동시에 성립시킨 글로벌 한국영화 대표 감독.",
        "currentAbilityText": "장르적 재미와 사회적 메시지를 결합하는 능력이 뛰어나다.",
        "potentialText": "이미 세계적 브랜드를 형성한 감독이다.",
        "fameText": "한국영화를 세계 시장에 각인시킨 감독으로 평가된다.",
        "brandText": "이름만으로도 해외 영화제와 투자자의 관심을 끌 수 있다.",
    },
}

ACTOR_TIER_OVERRIDES = {
    "안성기": "legend",
    "송강호": "legend",
    "최민식": "legend",
    "전도연": "legend",
    "윤여정": "legend",
    "강수연": "legend",
    "한석규": "top_star",
    "설경구": "top_star",
    "이병헌": "top_star",
    "정우성": "top_star",
    "장동건": "top_star",
    "이정재": "top_star",
    "황정민": "top_star",
    "하정우": "top_star",
    "마동석": "top_star",
    "김혜수": "top_star",
    "전지현": "top_star",
    "손예진": "top_star",
    "김태리": "top_star",
    "최민수": "a_list",
    "문성근": "a_list",
    "박중훈": "a_list",
    "김윤석": "a_list",
    "정재영": "a_list",
    "박해일": "a_list",
    "조승우": "a_list",
    "공유": "a_list",
    "강동원": "a_list",
    "류승룡": "a_list",
    "유해진": "a_list",
    "조진웅": "a_list",
    "원빈": "a_list",
    "현빈": "a_list",
    "김민희": "a_list",
    "배두나": "a_list",
    "공효진": "a_list",
    "천우희": "a_list",
    "김고은": "a_list",
    "라미란": "character_actor",
    "이정은": "character_actor",
    "김해숙": "veteran",
    "김수미": "veteran",
}

ACTOR_ROLE_OVERRIDES = {
    "송강호": ["연기파", "국민배우", "영화제형", "글로벌형"],
    "최민식": ["연기파", "강렬한캐릭터", "영화제형", "글로벌형"],
    "전도연": ["연기파", "영화제형", "글로벌형"],
    "이병헌": ["연기파", "티켓파워형", "글로벌형"],
    "황정민": ["연기파", "국민배우", "티켓파워형"],
    "하정우": ["연기파", "티켓파워형", "장르형"],
    "마동석": ["티켓파워형", "범죄액션형", "글로벌형", "팬덤형"],
    "김혜수": ["연기파", "국민배우", "브랜드형"],
    "전지현": ["티켓파워형", "팬덤형", "글로벌형"],
    "윤여정": ["연기파", "영화제형", "글로벌형", "veteran"],
    "김태리": ["연기파", "성장형", "영화제형"],
}

ACTOR_GENRE_OVERRIDES = {
    "송강호": ["drama", "crime_thriller", "black_comedy", "historical"],
    "최민식": ["crime_thriller", "drama", "historical", "noir"],
    "전도연": ["drama", "romance_melodrama", "social_true_story", "indie_art"],
    "이병헌": ["action", "crime_thriller", "drama", "historical"],
    "황정민": ["crime_thriller", "action", "drama", "comedy"],
    "하정우": ["crime_thriller", "drama", "action", "black_comedy"],
    "마동석": ["action", "crime_thriller", "comedy"],
    "김혜수": ["crime_thriller", "drama", "comedy", "period_historical"],
    "전지현": ["romance_melodrama", "action", "comedy", "fantasy"],
    "윤여정": ["drama", "family_human_drama", "indie_art"],
    "김태리": ["period_historical", "drama", "sf_disaster_monster", "romance_melodrama"],
}

ACTOR_MANUAL_STATS = {
    "송강호": {"acting": 98, "ticketPower": 92, "festivalPower": 95, "brandPower": 95, "globalRecognition": 92, "costLevel": 95, "scheduleDifficulty": 85, "growthPotential": 60},
    "최민식": {"acting": 98, "ticketPower": 88, "festivalPower": 90, "brandPower": 90, "globalRecognition": 82, "costLevel": 90, "scheduleDifficulty": 82, "growthPotential": 55},
    "전도연": {"acting": 98, "ticketPower": 75, "festivalPower": 98, "brandPower": 90, "globalRecognition": 88, "costLevel": 88, "scheduleDifficulty": 80, "growthPotential": 55},
    "이병헌": {"acting": 92, "ticketPower": 90, "festivalPower": 78, "brandPower": 94, "globalRecognition": 90, "costLevel": 94, "scheduleDifficulty": 88, "growthPotential": 60},
    "황정민": {"acting": 94, "ticketPower": 92, "festivalPower": 82, "brandPower": 92, "globalRecognition": 75, "costLevel": 92, "scheduleDifficulty": 85, "growthPotential": 58},
    "하정우": {"acting": 88, "ticketPower": 90, "festivalPower": 75, "brandPower": 88, "globalRecognition": 70, "costLevel": 88, "scheduleDifficulty": 82, "growthPotential": 60},
    "마동석": {"acting": 78, "ticketPower": 90, "festivalPower": 55, "brandPower": 92, "globalRecognition": 85, "costLevel": 90, "scheduleDifficulty": 86, "growthPotential": 62},
    "김혜수": {"acting": 90, "ticketPower": 82, "festivalPower": 75, "brandPower": 94, "globalRecognition": 68, "costLevel": 88, "scheduleDifficulty": 80, "growthPotential": 55},
    "전지현": {"acting": 78, "ticketPower": 90, "festivalPower": 55, "brandPower": 96, "globalRecognition": 82, "costLevel": 92, "scheduleDifficulty": 86, "growthPotential": 58},
    "윤여정": {"acting": 96, "ticketPower": 65, "festivalPower": 100, "brandPower": 90, "globalRecognition": 100, "costLevel": 82, "scheduleDifficulty": 72, "growthPotential": 35},
    "김태리": {"acting": 88, "ticketPower": 78, "festivalPower": 80, "brandPower": 88, "globalRecognition": 75, "costLevel": 80, "scheduleDifficulty": 78, "growthPotential": 78},
}

DIRECTOR_TIER_OVERRIDES = {
    "봉준호": "global_auteur",
    "박찬욱": "global_auteur",
    "이창동": "legend",
    "김기영": "legend",
    "최동훈": "commercial_master",
    "임권택": "legend",
    "홍상수": "auteur",
    "김지운": "genre_master",
    "류승완": "commercial_master",
    "윤제균": "commercial_master",
    "나홍진": "genre_master",
    "김한민": "commercial_master",
    "장재현": "genre_master",
    "김기덕": "auteur",
    "강제규": "commercial_master",
    "강우석": "commercial_master",
    "이준익": "commercial_master",
    "연상호": "genre_master",
    "김용화": "commercial_master",
}

DIRECTOR_TYPE_OVERRIDES = {
    "봉준호": ["작가주의", "상업성", "글로벌", "장르혼합"],
    "박찬욱": ["작가주의", "글로벌", "장르혼합", "미장센"],
    "이창동": ["작가주의", "문학성", "영화제형"],
    "김기영": ["작가주의", "장르혼합", "컬트"],
    "최동훈": ["상업성", "앙상블", "케이퍼", "범죄오락"],
    "류승완": ["상업성", "액션전문", "범죄스릴러"],
    "김지운": ["장르혼합", "범죄스릴러", "미장센"],
    "나홍진": ["범죄스릴러", "작가주의", "장르통제"],
    "홍상수": ["작가주의", "독립영화", "영화제형"],
    "윤제균": ["상업성", "대중오락"],
    "김한민": ["상업성", "사극", "대형제작"],
    "장재현": ["오컬트", "범죄스릴러", "장르통제"],
}

DIRECTOR_GENRE_OVERRIDES = {
    "봉준호": ["crime_thriller", "black_comedy", "monster", "drama", "sf"],
    "박찬욱": ["crime_thriller", "noir", "romance_melodrama", "period_historical"],
    "이창동": ["drama", "social_true_story", "indie_art"],
    "김기영": ["horror_occult", "melodrama", "crime_thriller", "cult"],
    "최동훈": ["crime_thriller", "comedy", "period_historical", "fantasy"],
    "류승완": ["action", "crime_thriller", "comedy"],
    "김지운": ["crime_thriller", "horror_occult", "action", "sf_disaster_monster"],
    "나홍진": ["crime_thriller", "horror_occult", "drama"],
    "홍상수": ["indie_art", "drama", "romance_melodrama"],
    "윤제균": ["comedy", "family_human_drama", "sf_disaster_monster"],
    "김한민": ["period_historical", "action", "war"],
    "장재현": ["horror_occult", "crime_thriller", "mystery"],
}

DIRECTOR_MANUAL_STATS = {
    "봉준호": {"directing": 98, "screenplay": 96, "commercialSense": 90, "auteurPower": 98, "genreControl": 95, "budgetControl": 82, "festivalPower": 100, "globalRecognition": 100, "costLevel": 95, "scheduleDifficulty": 92, "growthPotential": 55},
    "박찬욱": {"directing": 96, "screenplay": 90, "commercialSense": 78, "auteurPower": 100, "genreControl": 94, "budgetControl": 75, "festivalPower": 95, "globalRecognition": 98, "costLevel": 92, "scheduleDifficulty": 90, "growthPotential": 50},
    "이창동": {"directing": 96, "screenplay": 95, "commercialSense": 45, "auteurPower": 100, "genreControl": 86, "budgetControl": 70, "festivalPower": 96, "globalRecognition": 90, "costLevel": 80, "scheduleDifficulty": 75, "growthPotential": 40},
    "김기영": {"directing": 94, "screenplay": 85, "commercialSense": 50, "auteurPower": 98, "genreControl": 90, "budgetControl": 70, "festivalPower": 85, "globalRecognition": 70, "costLevel": 60, "scheduleDifficulty": 50, "growthPotential": 20},
    "최동훈": {"directing": 86, "screenplay": 80, "commercialSense": 100, "auteurPower": 60, "genreControl": 88, "budgetControl": 78, "festivalPower": 55, "globalRecognition": 60, "costLevel": 88, "scheduleDifficulty": 80, "growthPotential": 50},
    "류승완": {"directing": 86, "screenplay": 78, "commercialSense": 92, "auteurPower": 65, "genreControl": 90, "budgetControl": 85, "festivalPower": 60, "globalRecognition": 65, "costLevel": 82, "scheduleDifficulty": 78, "growthPotential": 55},
    "김지운": {"directing": 90, "screenplay": 82, "commercialSense": 82, "auteurPower": 88, "genreControl": 92, "budgetControl": 75, "festivalPower": 75, "globalRecognition": 75, "costLevel": 82, "scheduleDifficulty": 78, "growthPotential": 55},
    "나홍진": {"directing": 92, "screenplay": 86, "commercialSense": 80, "auteurPower": 88, "genreControl": 94, "budgetControl": 70, "festivalPower": 82, "globalRecognition": 78, "costLevel": 82, "scheduleDifficulty": 82, "growthPotential": 60},
    "홍상수": {"directing": 86, "screenplay": 88, "commercialSense": 35, "auteurPower": 95, "genreControl": 78, "budgetControl": 85, "festivalPower": 90, "globalRecognition": 80, "costLevel": 60, "scheduleDifficulty": 60, "growthPotential": 35},
    "윤제균": {"directing": 78, "screenplay": 65, "commercialSense": 96, "auteurPower": 40, "genreControl": 75, "budgetControl": 88, "festivalPower": 40, "globalRecognition": 55, "costLevel": 82, "scheduleDifficulty": 75, "growthPotential": 45},
    "김한민": {"directing": 80, "screenplay": 70, "commercialSense": 94, "auteurPower": 45, "genreControl": 80, "budgetControl": 86, "festivalPower": 45, "globalRecognition": 55, "costLevel": 80, "scheduleDifficulty": 76, "growthPotential": 45},
    "장재현": {"directing": 84, "screenplay": 82, "commercialSense": 82, "auteurPower": 72, "genreControl": 92, "budgetControl": 76, "festivalPower": 65, "globalRecognition": 55, "costLevel": 72, "scheduleDifficulty": 70, "growthPotential": 72},
}

FAMILY_NAMES = {
    "강": ("kang", "Kang"), "고": ("go", "Go"), "공": ("gong", "Gong"), "곽": ("kwak", "Kwak"),
    "권": ("kwon", "Kwon"), "김": ("kim", "Kim"), "나": ("na", "Na"), "남": ("nam", "Nam"),
    "문": ("moon", "Moon"), "민": ("min", "Min"), "박": ("park", "Park"), "배": ("bae", "Bae"),
    "변": ("byun", "Byun"), "봉": ("bong", "Bong"), "서": ("seo", "Seo"), "성": ("sung", "Sung"),
    "손": ("son", "Son"), "송": ("song", "Song"), "신": ("shin", "Shin"), "심": ("shim", "Shim"),
    "안": ("ahn", "Ahn"), "양": ("yang", "Yang"), "엄": ("um", "Um"), "여": ("yeo", "Yeo"),
    "연": ("yeon", "Yeon"), "염": ("yeom", "Yeom"), "오": ("oh", "Oh"), "우": ("woo", "Woo"),
    "원": ("won", "Won"), "유": ("yoo", "Yoo"), "윤": ("yoon", "Yoon"), "이": ("lee", "Lee"),
    "임": ("lim", "Lim"), "장": ("jang", "Jang"), "전": ("jeon", "Jeon"), "정": ("jung", "Jung"),
    "조": ("cho", "Cho"), "주": ("ju", "Ju"), "차": ("cha", "Cha"), "천": ("chun", "Chun"),
    "최": ("choi", "Choi"), "하": ("ha", "Ha"), "한": ("han", "Han"), "허": ("heo", "Heo"),
    "현": ("hyun", "Hyun"), "홍": ("hong", "Hong"), "황": ("hwang", "Hwang"), "류": ("ryu", "Ryu"),
}

COMPOUND_FAMILY_NAMES = {
    "남궁": ("namgung", "Namgung"),
    "독고": ("dokgo", "Dokgo"),
}

CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
JONG = ["", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lk", "lm", "lb", "ls", "lt", "lp", "lh", "m", "p", "ps", "t", "t", "ng", "t", "t", "k", "t", "p", "h"]


def main() -> int:
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    actors = [_person_record("actor", name, group, available_from) for group, available_from, names in ACTOR_GROUPS for name in names]
    directors = [
        _person_record("director", name, group, available_from)
        for group, available_from, names in DIRECTOR_GROUPS
        for name in names
    ]
    critics = [_critic_record(name, available_from, tags) for name, available_from, tags in CRITICS]

    _write_json("actors_major.json", actors)
    _write_json("directors_major.json", directors)
    _write_json("critics_major.json", critics)
    print(f"actors_major.json: {len(actors)} records")
    print(f"directors_major.json: {len(directors)} records")
    print(f"critics_major.json: {len(critics)} records")
    return 0


def _person_record(person_type: str, name: str, cohort: str, default_available_from: int) -> dict[str, Any]:
    slug = ID_OVERRIDES.get(name, _slug_for_name(name))
    bio = BIO_OVERRIDES.get(name, {})
    public_profile = PUBLIC_PROFILE_OVERRIDES.get(name) or _public_profile(person_type, cohort)
    available_from = bio.get("availableFrom", default_available_from)
    tier = _tier_for_person(person_type, name, cohort)
    tags = _type_tags_for_person(person_type, name, cohort)
    genre_tags = _genre_tags_for_person(person_type, name, cohort)
    manual_stats = _manual_stats_for_person(person_type, name)
    record = {
        "id": f"{person_type}_{slug}",
        "nameKo": name,
        "nameEn": NAME_EN_OVERRIDES.get(name, _name_en(name)),
        "type": person_type,
        "birthYear": bio.get("birthYear"),
        "availableFrom": available_from,
        "status": bio.get("status", "active"),
        "protectionLevel": bio.get("protectionLevel", "none"),
        "tier": tier,
        "currentStats": _placeholder_stats(person_type, default_available_from),
        "potentialStats": _placeholder_potential(person_type, default_available_from),
        "genreFit": {},
        "peakEras": _peak_eras(name, person_type, available_from),
        "genreTags": genre_tags,
        "manualOverride": bool(manual_stats),
        "manualStats": manual_stats,
        "statEstimationNotes": "1차 빌드 자동 산정의 기초 명단. tier/type tags/genreTags를 바탕으로 자동 산정하고 주요 인물만 manualStats를 우선 적용한다.",
        "publicProfile": public_profile,
    }
    if person_type == "actor":
        record["roleType"] = tags
        record["globalTag"] = "글로벌형" in tags or name in ACTOR_MANUAL_STATS
        record["protectedEventRelated"] = bool(bio.get("protectionLevel") not in {None, "none"})
    else:
        record["directorType"] = tags
    if bio.get("historicalFilmographyLocked"):
        record["historicalFilmographyLocked"] = True
    return record


def _critic_record(name: str, available_from: int, critic_type: list[str]) -> dict[str, Any]:
    slug = ID_OVERRIDES.get(name, _slug_for_name(name).replace("_", ""))
    return {
        "id": f"critic_{slug}",
        "nameKo": name,
        "type": "critic",
        "availableFrom": available_from,
        "criticType": critic_type,
        "influence": {
            "public": 70,
            "cinephile": 72,
            "awards": 55,
            "online": 68,
        },
        "tasteProfile": {
            "narrative": 70,
            "directing": 70,
            "emotion": 68,
            "genreCraft": 68,
            "auteurism": 66,
            "commercialEntertainment": 62,
            "socialMeaning": 66,
            "technicalCraft": 64,
        },
        "scoringStyle": {
            "strictness": 70,
            "oneLineImpact": 70,
            "reviewDepth": 72,
        },
        "publicDescription": f"{', '.join(critic_type)} 성향을 가진 평론가.",
    }


def _placeholder_stats(person_type: str, available_from: int) -> dict[str, int]:
    if person_type == "actor":
        return {
            "acting_quality": 62,
            "casting_fit": 60,
            "public_reputation": 56 if available_from >= 2010 else 64,
        }
    return {
        "directing_quality": 62,
        "screenplay_sense": 60,
        "field_control": 58,
        "artistic_sense": 58,
        "commercial_sense": 56,
    }


def _placeholder_potential(person_type: str, available_from: int) -> dict[str, int]:
    if person_type == "actor":
        return {
            "acting_quality": 70,
            "casting_fit": 68,
            "public_reputation": 66 if available_from >= 2010 else 70,
        }
    return {
        "directing_quality": 70,
        "screenplay_sense": 68,
        "field_control": 66,
        "artistic_sense": 68,
        "commercial_sense": 66,
    }


def _peak_eras(name: str, person_type: str, available_from: int) -> list[dict[str, Any]]:
    explicit = {
        "송강호": [{"start": 2003, "end": 2019, "modifiers": {"acting": 1.08, "ticketPower": 1.12, "brandPower": 1.10}}],
        "최민식": [{"start": 1999, "end": 2014, "modifiers": {"acting": 1.08, "ticketPower": 1.12, "brandPower": 1.08}}],
        "전도연": [{"start": 1997, "end": 2015, "modifiers": {"acting": 1.10, "festivalPower": 1.12, "brandPower": 1.08}}],
        "김혜수": [{"start": 1995, "end": 2016, "modifiers": {"acting": 1.06, "brandPower": 1.12, "ticketPower": 1.06}}],
        "봉준호": [{"start": 2003, "end": 2019, "modifiers": {"directing": 1.12, "commercialSense": 1.10, "auteurPower": 1.14, "globalRecognition": 1.20}}],
        "박찬욱": [{"start": 2000, "end": 2022, "modifiers": {"directing": 1.10, "auteurPower": 1.14, "festivalPower": 1.12, "globalRecognition": 1.12}}],
        "이창동": [{"start": 1997, "end": 2018, "modifiers": {"directing": 1.10, "screenplay": 1.12, "auteurPower": 1.14, "festivalPower": 1.10}}],
        "김기영": [{"start": 1960, "end": 1975, "modifiers": {"directing": 1.10, "auteurPower": 1.14, "genreControl": 1.10}}],
        "최동훈": [{"start": 2006, "end": 2015, "modifiers": {"commercialSense": 1.14, "genreControl": 1.10, "budgetControl": 1.08}}],
    }
    if name in explicit:
        return explicit[name]
    start = available_from + (4 if person_type == "actor" else 3)
    return [
        {
            "start": start,
            "end": start + 12,
            "modifiers": {
                "acting" if person_type == "actor" else "directing": 1.04,
                "brandPower" if person_type == "actor" else "commercialSense": 1.03,
            },
        }
    ]


def _manual_stats_for_person(person_type: str, name: str) -> dict[str, int]:
    if person_type == "actor":
        return ACTOR_MANUAL_STATS.get(name, {})
    return DIRECTOR_MANUAL_STATS.get(name, {})


def _tier_for_person(person_type: str, name: str, cohort: str) -> str:
    if person_type == "actor":
        if name in ACTOR_TIER_OVERRIDES:
            return ACTOR_TIER_OVERRIDES[name]
        if "조연" in cohort or "신스틸러" in cohort:
            return "character_actor"
        if "2010~2020년대" in cohort:
            return "rising"
        if "1980~1990년대" in cohort or "1980~2000년대" in cohort:
            return "veteran"
        return "solid_lead"
    if name in DIRECTOR_TIER_OVERRIDES:
        return DIRECTOR_TIER_OVERRIDES[name]
    if "독립/신진" in cohort:
        return "rising_director"
    if "1980~1990년대" in cohort:
        return "veteran"
    if "2010~2020년대" in cohort:
        return "solid_commercial"
    return "genre_master"


def _type_tags_for_person(person_type: str, name: str, cohort: str) -> list[str]:
    if person_type == "actor":
        if name in ACTOR_ROLE_OVERRIDES:
            return ACTOR_ROLE_OVERRIDES[name]
        tags = ["연기파"]
        if "조연" in cohort or "신스틸러" in cohort:
            tags.extend(["신스틸러", "캐릭터형"])
        elif "2010~2020년대" in cohort:
            tags.extend(["성장형", "팬덤형"])
        elif "스타" in cohort or "주연급" in cohort:
            tags.extend(["티켓파워형", "상업영화"])
        else:
            tags.append("상업영화")
        return tags
    if name in DIRECTOR_TYPE_OVERRIDES:
        return DIRECTOR_TYPE_OVERRIDES[name]
    tags = ["장르혼합"]
    if "독립/신진" in cohort:
        tags.extend(["독립영화", "성장형"])
    elif "1980~1990년대" in cohort:
        tags.extend(["작가주의", "산업기반"])
    elif "상업" in cohort or "2000~2010년대" in cohort or "2010~2020년대" in cohort:
        tags.append("상업성")
    return tags


def _genre_tags_for_person(person_type: str, name: str, cohort: str) -> list[str]:
    if person_type == "actor":
        if name in ACTOR_GENRE_OVERRIDES:
            return ACTOR_GENRE_OVERRIDES[name]
        if "조연" in cohort or "신스틸러" in cohort:
            return ["crime_thriller", "comedy", "family_human_drama"]
        if "여성" in cohort:
            return ["drama", "romance_melodrama", "family_human_drama"]
        if "남성" in cohort:
            return ["crime_thriller", "action", "drama"]
        return ["drama", "family_human_drama", "crime_thriller"]
    if name in DIRECTOR_GENRE_OVERRIDES:
        return DIRECTOR_GENRE_OVERRIDES[name]
    if "독립/신진" in cohort:
        return ["indie_art", "drama", "social_true_story"]
    if "1980~1990년대" in cohort:
        return ["drama", "period_historical", "social_true_story"]
    if "2010~2020년대" in cohort:
        return ["crime_thriller", "action", "comedy"]
    return ["crime_thriller", "drama", "comedy"]


def _public_profile(person_type: str, cohort: str) -> dict[str, str]:
    if person_type == "actor":
        return {
            "oneLine": f"{cohort} 흐름에서 한국영화 캐스팅 축을 형성한 배우.",
            "currentAbilityText": "상업영화, 장르영화, 드라마 안에서 작품의 톤을 지탱할 수 있는 배우로 분류된다.",
            "potentialText": "초기 DB에서는 세부 잠재력보다 시대별 대표성과 캐스팅 활용도를 우선 반영한다.",
            "fameText": "해당 시기 한국영화 관객과 업계에 이름이 알려진 배우로 취급한다.",
            "brandText": "대표작의 인상과 대중 인지도가 캐스팅 기대치를 만든다.",
        }
    return {
        "oneLine": f"{cohort} 흐름에서 한국영화 제작 지형에 영향을 준 감독.",
        "currentAbilityText": "연출 성향과 산업적 위치는 후속 큐레이션에서 장르별로 세분화한다.",
        "potentialText": "작품 규모, 투자 환경, 시대 흐름에 따라 흥행성과 평단 반응이 달라질 수 있다.",
        "fameText": "한국영화사와 산업 흐름 안에서 의미 있는 이름으로 취급한다.",
        "brandText": "대표작, 장르 성향, 현장 평판이 감독 브랜드를 구성한다.",
    }


def _slug_for_name(name: str) -> str:
    family_slug, _, given = _split_name(name)
    given_parts = [_romanize_syllable(char) for char in given]
    return "_".join([family_slug, *[part for part in given_parts if part]])


def _name_en(name: str) -> str:
    _, family_en, given = _split_name(name)
    given_parts = [_romanize_syllable(char).capitalize() for char in given]
    return f"{family_en} {'-'.join(given_parts)}"


def _split_name(name: str) -> tuple[str, str, str]:
    for family, romanized in COMPOUND_FAMILY_NAMES.items():
        if name.startswith(family):
            return romanized[0], romanized[1], name[len(family):]
    family = name[0]
    romanized = FAMILY_NAMES.get(family, (_romanize_syllable(family), _romanize_syllable(family).capitalize()))
    return romanized[0], romanized[1], name[1:]


def _romanize_syllable(char: str) -> str:
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return char.lower()
    cho = code // 588
    jung = (code % 588) // 28
    jong = code % 28
    return f"{CHO[cho]}{JUNG[jung]}{JONG[jong]}"


def _write_json(filename: str, data: list[dict[str, Any]]) -> None:
    (PEOPLE_DIR / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
