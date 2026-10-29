# Core System Matrix

아래 시스템은 ChungmuroTycoon의 1차 핵심 시스템 목록이다. 전체 설계 기준은 `docs/GAME_SYSTEM_OVERVIEW.md`를 따른다.

상태 구분:

- `playable`: 현재 UI/서비스 흐름에서 직접 사용 가능
- `foundation`: DB와 서비스 기반이 있고, UI나 정교한 룰이 앞으로 필요
- `planned`: 아직 설계 문서 수준

| # | 시스템 | 상태 | 핵심 테이블 | 핵심 서비스 |
|---|---|---|---|---|
| 1 | 캐릭터 생성 | playable | `save_player_state`, `save_studio_state` | `character_service` |
| 2 | 시작 시대 선택 | playable | `core_eras`, `core_era_rules`, `save_market_state`, `history_ticket_prices` | `character_service`, `era_service`, `world_service` |
| 3 | 포지션 선택 | foundation | `save_player_state` | `character_service` |
| 4 | 명성 | foundation | `systems_reputation`, `save_player_state` | `reputation_service` |
| 5 | 인맥 | foundation | `systems_network`, `people_relationships`, `save_player_state` | `network_service` |
| 6 | 영화 제작 규모 | playable | `core_project_scales`, `production_projects` | `film_service` |
| 7 | 장르별 제작비 배분 | playable | `core_genres`, `production_budget_allocations` | `budget_service`, `film_service` |
| 8 | 대화형 선택지 | foundation | `production_dialogue_events`, `production_choices`, `production_stage_logs` | `dialogue_service`, `event_engine` |
| 9 | 제작 중간 이벤트 | playable | `core_production_stages`, `production_random_events` | `event_service` |
| 10 | 배우/감독 DB | foundation | `people`, `people_actor_profiles`, `people_director_profiles` | `people_service` |
| 11 | 배우/감독 현재 능력·잠재력 | foundation | `people_actor_profiles`, `people_director_profiles` | `people_service` |
| 12 | 배우/감독 구두 평가 표시 | foundation | `people_actor_profiles`, `people_director_profiles` | `people_service` |
| 13 | 실제 역사 이벤트 | foundation | `history_domestic_events`, `save_market_state`, `systems_press` | `history_service`, `world_service` |
| 14 | 외화 고정 이벤트 | foundation | `history_foreign_events`, `movies_historical` | `history_service`, `world_service` |
| 15 | 티켓값 고정 역사 | playable | `history_ticket_prices` | `boxoffice_service` |
| 16 | 시상식 이벤트 | foundation | `history_award_events`, `movies_awards` | `award_service`, `awards_service` |
| 17 | 언론 | foundation | `systems_press` | `press_service` |
| 18 | 평론가 | foundation | `people_critic_profiles`, `movies_reviews` | `critic_service` |
| 19 | 표절 위험 | foundation | `production_projects.stats_json`, `systems_plagiarism` | `plagiarism_service`, `risk_service` |
| 20 | 시리즈화 | foundation | `systems_franchise`, `movies_post_release_metrics` | `franchise_service` |
| 21 | 역주행/재평가 | foundation | `systems_post_release`, `movies_post_release_metrics` | `post_release_service`, `reevaluation_service` |
| 22 | 세이브/로드 | playable | 전체 SQLite DB | `save_service` |
| 23 | 미래 자동 생성 기반 | foundation | `systems_future_generation`, `save_generated_people`, `save_generated_films` | `future_generation_service` |
| 24 | 시대별 선택지 잠금 | foundation | `era_rules`, `core_era_rules`, `save_market_state` | `era_service` |
| 25 | 유연한 역사 모드 | foundation | `historical_events`, `save_event_flags`, `market_releases` | `history_service`, `world_service` |
| 26 | 보호 역사/보호 스케줄 | foundation | `history_protected_director_films`, `people_protected_schedules` | `history_service`, `casting_service` |
| 27 | 배급사/극장/특별관 사건 | foundation | `history_distribution_events`, `history_theater_events`, `history_premium_format_events` | `history_service`, `world_service` |
| 28 | 관객 평점/입소문 | playable | `movies_player_created`, `movies_post_release_metrics` | `boxoffice_service`, `post_release_service` |
| 29 | 마케팅 수단 | foundation | `production_projects`, `production_choices`, `systems_press` | `press_service`, `event_engine` |
| 30 | 개봉 전략 | foundation | `project_distribution`, `save_market_state`, `history_foreign_events` | `film_service`, `boxoffice_service` |
| 31 | 개봉 후 대응 | foundation | `movies_post_release_metrics`, `systems_post_release` | `post_release_service` |
| 32 | 2차 소비 시장 | foundation | `movies_post_release_metrics`, `history_ticket_prices` | `boxoffice_service`, `post_release_service` |
| 33 | 위험도/게임 오버 | foundation | `production_projects`, `systems_plagiarism`, `save_player_state` | `risk_service`, `game_state` |
| 34 | 실제 DB 수집 | foundation | `staging_*`, `history_ticket_prices`, `movies_historical` | `data_collection_service`, `fetch_kobis.py`, `fetch_kmdb.py`, `fetch_kosis.py` |
| 35 | 경제/인구/문화 지표 | foundation | `staging_kosis_statistics`, `staging_kosis_indicator_series` | `data_collection_service`, `economic_service`, `future_generation_service`, `boxoffice_service` |
| 36 | 연간 산업 결산 | foundation | `industry_yearly_reports`, `staging_kobis_yearly_boxoffice`, `staging_kofic_industry_metrics` | `annual_report_service`, `build_annual_reports.py` |
| 37 | 플레이어 제작 필모그래피 | playable | `player_filmography_records`, `completed_films`, `movies_boxoffice`, `movies_awards`, `movies_reviews`, `project_people`, `reevaluation_events`, `ip_entries` | `player_filmography_service`, `boxoffice_service` |

## 다음 구현 권장 순서

1. 배우/감독 캐스팅 화면: 10, 11, 12, 26번을 실제 선택 UI로 연결한다.
2. 투자사/배급사 협상 화면: 3, 4, 5, 8, 17, 30번의 효과가 강하게 드러난다.
3. 월 진행 시 역사 이벤트 피드: 13, 14, 17, 23, 25, 27번을 대시보드 뉴스로 표시한다.
4. 개봉 후 결과 탭 확장: 16, 18, 19, 20, 21, 28, 31, 32번을 결과 화면에서 보여준다.
5. 마케팅/개봉 전략 화면에 24번 시대별 선택지 잠금과 비효율 경고를 연결한다.
6. 연간 산업 결산을 미래 자동 생성과 장르 트렌드 변화의 기준 데이터로 연결한다.
7. 플레이어 필모그래피를 엔딩 리포트와 제작사 연혁 화면으로 확장한다.
