# ChungmuroTycoon Architecture

이 프로젝트는 작은 데모가 아니라 한국 영화계 시뮬레이션을 장기적으로 확장하기 위한 로컬 싱글플레이 게임 구조를 목표로 한다. 전체 게임 시스템의 상위 기준은 `docs/GAME_SYSTEM_OVERVIEW.md`를 따른다.

현재 UI는 1차 플레이 흐름만 제공하지만, DB와 서비스는 다음 시스템을 담을 수 있도록 분리한다.

## 실행 환경

- 프로젝트명: ChungmuroTycoon
- 폴더명: `chungmuro_tycoon`
- 실행 파일명: `ChungmuroTycoon.exe`
- 운영체제: Windows
- Python: 3.11 또는 3.12
- 패키지 관리자: pip
- UI: PySide6
- DB: SQLite
- 패키징: PyInstaller

## 설계 원칙

- UI는 화면 전환과 입력만 담당한다.
- 게임 규칙, 계산식, 상태 변화는 `app/services/`에 둔다.
- 정적 기준 데이터는 `data/seed/core`, `data/seed/people`, `data/seed/history`, `data/seed/production`에서 관리하고 DB로 적재한다.
- 플레이 중 변하는 값은 런타임 테이블에 기록한다.
- 모든 선택지는 이벤트 엔진을 통해 처리하고 `event_history`에 남긴다.
- 숫자 스탯은 내부 계산용이며, 인물 평가는 공개 프로필 문장으로 표현한다.
- 기본 플레이 루프는 항상 실행 가능해야 한다: 새 게임, 캐릭터 생성, 대시보드, 영화 기획, 제작 진행, 개봉 결과, 세이브.
- UI는 현실적 산업 시뮬레이션 톤을 따른다. Football Manager/Civilization식 텍스트 전략 화면처럼 지표, 목록, 리포트 문장을 우선하고 캐주얼한 보상 연출은 피한다.
- 기본 배포본의 assets 정책은 실제 인물 사진과 실제 영화 포스터를 포함하지 않는 것이다. 인물 이미지는 silhouette placeholder를 기본값으로 사용하고, 영화는 제목과 텍스트 데이터 중심으로 표시한다. 사용자가 직접 확보한 파일은 `assets/media/` 로컬 패치 구조로 연결할 수 있다.

## DB 계층

현재 DB의 canonical prefix는 다음을 기준으로 한다.

- `core_*`: 기준 규칙
- `people_*`: 인물과 관계
- `movies_*`: 영화와 개봉 후 결과
- `history_*`: 고정/보호 역사
- `production_*`: 제작 중 프로젝트와 이벤트
- `systems_*`: 명성, 인맥, 언론, 평론, 표절, 프랜차이즈, 미래 생성
- `save_*`: 플레이어 진행 상태. 실제 런타임에서는 선택된 `saves/save_###.db` 안에서 갱신한다.

기준 데이터:

- `core_eras`: 시대별 시장 기본값
- `core_era_rules`: 시대별 선택지 잠금, 강한 선택지, 장르/리스크 보정
- `core_genres`: 장르별 예산/완성도 가중치
- `core_project_scales`: 규모별 예산 범위와 리스크
- `people`: 배우, 감독, 스태프 후보
- `people_critic_profiles`: 평론가 성향
- `organizations`: 투자사, 배급사, OTT, 제작사
- `core_production_stages`: 제작 단계 정의
- `production_random_events`: 범용 이벤트 정의
- `history_domestic_events`, `history_policy_events`, `history_market_events`, `history_distribution_events`, `history_theater_events`, `history_premium_format_events`, `history_foreign_events`: 고정/반고정 역사 이벤트
- `history_ticket_prices`: 연도별 티켓 가격
- `history_protected_director_films`: 보호 감독의 실제 고정 필모그래피
- `market_releases`, `movies_historical`: 월별 역사/외화 고정 릴리즈 기록
- `industry_yearly_reports`: 연간 박스오피스, 한국영화 점유율, 외화 흥행작, 올해의 배우/감독, 시상식, 제작사/배급사/장르 트렌드 결산

플레이 상태:

- `save_player_state`: 플레이어 상태, 현재 연도/월/일, 플레이어 능력, 명성, 인맥
- `save_studio_state`: 제작사 자본, 부채, 명성
- `save_market_state`: 월별 극장/OTT/외화 경쟁 상태와 적용된 시대 규칙
- `production_projects`: 진행 중 프로젝트
- `production_budget_allocations`: 프로젝트별 예산 배분
- `people_career_timeline`: 프로젝트에 붙은 배우/감독/스태프
- `movies_player_created`: 완성 및 개봉된 플레이어 영화
- `player_filmography_records`: 플레이어 제작 영화별 관객 수, 손익, 수상, 평론, 협업, 실패, 역주행, 시리즈 기록 아카이브
- `people_relationships`: 개인/조직 관계도
- `production_stage_logs`: 선택지와 효과 기록
- `save_event_flags`: 장기 플래그와 대체역사 상태
- `systems_press`, `movies_reviews`, `history_award_events`, `movies_awards`: 언론, 평론, 시상식 확장 지점
- `core_stats`, `systems_reputation`, `systems_network`: 시스템/수치 카탈로그
- `systems_franchise`, `movies_post_release_metrics`: 시리즈화와 IP 확장
- `systems_plagiarism`: 표절/논란 리스크
- `systems_post_release`: 역주행과 재평가
- `systems_future_generation`, `save_generated_people`, `save_generated_films`: 미래 자동 생성 기반

세이브 DB 필수 범위:

- 플레이어 상태: `player_state`, `save_player_state`
- 제작사 상태: `studio_state`, `save_studio_state`
- 현재 연도/월: `player_state`, `save_player_state`, `market_state`, `save_market_state`
- 진행 중 프로젝트: `projects`, `production_projects`, `project_budget_allocations`, `production_budget_allocations`, `project_people`, `project_distribution`, `production_stage_logs`
- 완성 영화 목록: `completed_films`, `movies_player_created`, `player_filmography_records`, `movies_boxoffice`, `movies_reviews`, `movies_awards`, `movies_post_release_metrics`
- 명성: `player_state.reputation_json`, `save_player_state.reputation_json`
- 인맥: `player_state.network_json`, `save_player_state.network_json`
- 관계도: `relationships`, `people_relationships`
- 발생한 역사 이벤트 flag: `save_event_flags`, `event_history`, `story_flags`
- 생성된 미래 인물/영화: `generated_entities`, `save_generated_people`, `save_generated_films`

## 고정 역사

- 봉준호, 박찬욱, 이창동, 김기영, 최동훈의 주요 필모그래피는 `history_protected_director_films`에 둔다.
- 보호 작품은 진행하기로 날짜가 넘어가다가 해당 월에 진입할 때 `market_releases`, `movies_historical`, `movies`에 기록되며 플레이어가 취소할 수 없다.
- 보호 기간 중 핵심 인물은 장기 구속 계약을 할 수 없다.
- 플레이어는 보호 작품과 외화 고정 이벤트에 대해 경쟁, 편승, 개봉 시기 조정으로만 대응한다.
- 보호 감독 규칙:
  - 보호 감독: 봉준호, 박찬욱, 이창동, 김기영, 최동훈
  - 이들의 주요 필모그래피는 실제 역사와 동일하게 발생한다.
  - 플레이어가 보호작의 제작과 개봉을 막을 수 없다.
  - 핵심 제작 기간에는 보호 감독 및 보호 스케줄에 묶인 핵심 인물의 장기 캐스팅 방해가 차단된다.
- 외화 고정 이벤트는 `history_foreign_events`에 연도/월 단위로 둔다.
- 정책·제도 사건은 `history_policy_events`, 극장·OTT·관객 변화 사건은 `history_market_events`에 둔다.
- 배급사 등장/성장/쇠퇴는 `history_distribution_events`, 극장 체인과 주요 지점은 `history_theater_events`, IMAX/4DX/ScreenX/Dolby Cinema 같은 특별관 사건은 `history_premium_format_events`에 둔다.
- 모든 역사 사건 seed는 공통 `historical_events`에도 함께 적재되어 월 진행 시 시장 수치와 해금 플래그에 반영된다.
- 월이 넘어갈 때 외화 고정 이벤트는 `market_releases`, `movies_historical`, `movies`에 `foreign_fixed` 릴리즈로 기록된다.
- 티켓값은 `history_ticket_prices`와 `ticket_prices`에 연도 단위로 보존한다.
- 개봉 계산은 현재 연도 이하의 가장 가까운 티켓값 기록을 사용한다.

## 시대 규칙

- 시대 규칙은 `data/seed/core/era_rules.json`에서 관리하고 `era_rules`, `core_era_rules`에 적재한다.
- 각 시대는 시장 규칙, 제작 규칙, 배급 규칙, 마케팅 규칙, 2차 시장 규칙, 잠긴 선택지, 강한 선택지, 비효율 선택지, 장르 보정, 리스크 보정, 게임 오버 위험을 가진다.
- 캐릭터 생성과 월 진행은 현재 연도에 맞는 시대 규칙을 `save_market_state.modifiers_json`에 함께 저장한다.
- `era_service.py`는 현재 연도의 시대 규칙 조회, 시장 보정 병합, 선택지 잠금/강세/비효율 판정을 담당한다.
- 개봉 계산은 장르와 시대 규칙의 `genreModifiers`를 결합해 같은 장르라도 시대별 흥행 감각이 달라지도록 한다.
- 2030년 이후는 `era_future`와 `futureRules`를 사용해 실제 고정 역사 이후의 시장 변수를 자동 생성하는 기반으로 둔다.

## 이벤트 구조

이벤트는 `simulation_events`를 기본으로 한다.

```json
{
  "id": "event_fundraising_pitch_room",
  "category": "production",
  "stage": "fundraising",
  "scope": "project",
  "title": "첫 투자 미팅",
  "trigger": {
    "minBudget": 3000000,
    "genreIds": ["genre_crime_thriller"]
  },
  "choices": [
    {
      "id": "show_market_plan",
      "text": "시장 분석과 손익 구조를 먼저 제시한다",
      "effects": {
        "stats": {},
        "reputation": {},
        "network": {},
        "studio": {},
        "flags": {}
      }
    }
  ]
}
```

`app/services/event_engine.py`가 이벤트 선택과 효과 적용을 담당한다. UI는 이벤트 내용을 보여주고 선택지를 넘길 뿐이다.

## 필수 화면 세트

1차 빌드의 필수 PySide6 화면은 `app/ui/screen_registry.py`의 `CORE_SCREEN_CLASSES`로 고정한다.

- `StartScreen`
- `CharacterCreationScreen`
- `DashboardScreen`
- `PeopleDatabaseScreen`
- `FilmPlanningScreen`
- `BudgetAllocationScreen`
- `CastingScreen`
- `DialogueEventScreen`
- `ProductionProgressScreen`
- `ReleaseStrategyScreen`
- `BoxOfficeResultScreen`
- `HistoryTimelineScreen`
- `SaveLoadScreen`

이 목록은 smoke test에서 검증한다. 추가 화면은 만들 수 있지만, 위 핵심 화면 세트는 삭제하거나 이름을 바꾸지 않는다.

## 서비스 계층

- `character_service.py`: 새 게임 생성, 초기 플레이어/시장 상태
- `film_service.py`: 프로젝트 생성과 제작 단계 진행
- `budget_service.py`: 장르별 제작비 배분 계산과 저장
- `casting_service.py`: 배우/감독 후보 조회와 프로젝트 합류
- `event_engine.py`: 범용 이벤트 선택/적용/기록
- `event_service.py`: 현재는 제작 이벤트 접근 래퍼
- `dialogue_service.py`: 투자, 캐스팅, 언론 협상형 대화 이벤트 접근 래퍼
- `boxoffice_service.py`: 개봉 결과 계산
- `game_state.py`: 대시보드 상태와 일일 진행, 월 경계 이벤트 적용
- `save_service.py`: DB 파일 기반 세이브/로드
- `progression_service.py`: 제작 단계 순서와 표시명
- `people_service.py`: 배우/감독 공개 평가와 프로젝트 합류
- `reputation_service.py`, `network_service.py`: 명성/인맥 수치와 구두 평가
- `history_service.py`: 역사 이벤트, 보호 필모그래피, 월별 역사 적용
- `world_service.py`: 역사 이벤트 적용의 내부 구현
- `press_service.py`, `critic_service.py`: 언론 기사와 평론 리뷰
- `award_service.py`: 시상식 목록과 후보/수상 기록
- `awards_service.py`: 시상식 판정의 내부 구현
- `plagiarism_service.py`: 표절/논란 케이스 조회와 평가 진입점
- `risk_service.py`: 표절/논란 평가의 내부 구현
- `franchise_service.py`: IP와 시리즈화 후보
- `post_release_service.py`: 역주행/재평가 등 개봉 후 지표 조회
- `reevaluation_service.py`: 역주행/재평가 후보 생성의 내부 구현
- `future_generation_service.py`: 미래 인물/사건 생성 기반
- `people_stat_service.py`: 실제 데이터 기반 인물 스탯 자동 산정, 시대별 전성기 보정, 공개 문장 생성
- `economic_service.py`: KOSIS CPI/경제/인구/문화 지표를 제작비 체감, 티켓값 부담, 극장 수요, 미래 경제 변수로 변환
- `annual_report_service.py`: KOBIS/KMDb/KOFIC/Wikidata staging 데이터를 연도별 산업 결산 리포트로 집계
- `player_filmography_service.py`: 플레이어 제작 영화의 장기 필모그래피와 커리어 기록 집계

## 인물 스탯 산정

- 배우/감독 스탯은 tier 기본값, 유형 태그, 장르 태그, 실제 데이터 보정, 주요 인물 수동 오버라이드를 결합한다.
- 현재 능력치와 잠재 능력치는 분리한다.
- `peakEras`로 같은 인물도 연도에 따라 다른 현재 능력을 갖게 한다. 기존 `primeEras`도 호환 입력으로 처리한다.
- KOBIS staging 데이터가 있을 때는 흥행작 수, 평균 관객 수, 주요 출연/연출 작품, 장르 다양성, 최근 흐름을 반영한다.
- 수상, 후보, 평론가 호평, 해외 영화제 성과는 이후 KMDb/수동 큐레이션 데이터가 들어오면 같은 서비스에 추가한다.
- UI에는 내부 숫자를 보여주지 않고 공개 프로필 문장만 표시한다.
- 자세한 기준은 `docs/PEOPLE_STATS.md`를 따른다.

## 세이브 정책

- `data/game.db`는 고정 마스터 DB다. 시드 데이터, 고정 역사, 기준 규칙, API/파일 수집 데이터는 이 DB를 기준으로 관리한다.
- 기본 플레이어 진행 DB는 `saves/save_001.db`다.
- 새 게임 시작 시 `data/game.db`를 선택 슬롯으로 복제하고, 이후 런타임 DB 포인터는 해당 `saves/save_###.db`를 바라본다.
- 불러오기는 `data/game.db`를 덮어쓰지 않고 선택된 세이브 DB를 활성 런타임 DB로 지정한다.
- 최소 세이브 슬롯은 3개이며 `save_001.db`, `save_002.db`, `save_003.db` 형식을 사용한다.
- 수동 저장은 슬롯 선택이 가능하다.
- 새 게임 시작 시 기본 슬롯 1에 저장한다.
- 진행하기로 하루가 지난 뒤 현재 활성 슬롯에 자동 저장한다.
- 시작 화면의 불러오기는 가장 최근 수정된 세이브 슬롯을 사용한다.

## 확장 우선순위

1. 캐스팅 화면: `people`과 `project_people` 연결
2. 투자/배급 계약: `organizations`와 `project_distribution` 연결
3. 월별 시장 시뮬레이션: `market_state`, `market_releases`, `historical_events`
4. 평론/관객 반응: `film_reviews`, `news_items`
5. 시상식: `awards`, `award_results`
6. 연간 산업 결산: `industry_yearly_reports`
7. 플레이어 제작사 필모그래피: `player_filmography_records`
8. IP/시리즈/세계관: `story_flags`와 별도 IP 테이블 추가
