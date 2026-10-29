# Seed Data

이 폴더의 JSON 파일은 정적 기준 데이터를 담는다. 현재 기준 구조는 `core`, `people`, `history`, `production` 하위 폴더다.

- 새 시대, 장르, 규모, 인물, 조직, 이벤트는 도메인별 하위 폴더의 JSON에 추가한 뒤 `python3 scripts/seed_db.py`로 DB에 반영한다.
- 플레이 중 생성되는 프로젝트, 관계, 시장 상태, 이벤트 기록은 seed가 아니라 런타임 DB 테이블에 저장한다.
- `production/production_events.json`과 `production/production_choices_*.json`은 제작 이벤트 원본이며, seed 과정에서 `production_dialogue_events`, `production_random_events`, `production_choices`에도 적재된다.
- `production/dialogue_events.json`은 협상/대화 전용 이벤트 원본이며, `dialogue_service.py`에서 조회한다.

## Canonical Structure

```text
core/
  stats_100.json
  eras.json
  genres.json
  project_scales.json
  production_stages.json

people/
  actors_major.json
  directors_major.json
  critics_major.json
  protected_people.json
  generated_people_rules.json
  actors_seed_list.txt
  directors_seed_list.txt
  critics_seed_list.txt

history/
  domestic_events_1980s.json
  domestic_events_1990s.json
  domestic_events_2000s.json
  domestic_events_2010s.json
  domestic_events_2020s.json
  foreign_events_fixed.json
  ticket_prices.json
  protected_director_films.json
  award_events.json
  historical_reviews_sample.json

production/
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

`people/*_seed_list.txt` 파일은 DB에 직접 적재되는 JSON seed가 아니라, 실제 수집 데이터에서 주요 배우 300명, 감독 150명, 평론가 30명 목표를 채우기 위한 큐레이션 작업 목록이다. `python3 scripts/build_people_seed_lists.py`로 현재 staging DB 기준 목록을 다시 만들 수 있다.

## Canonical Table Prefixes

- `core_*`: 시대, 장르, 규모, 스탯, 제작 단계 같은 기준 규칙
- `people_*`: 배우, 감독, 평론가, 관계, 경력, 보호 일정
- `movies_*`: 실제 영화, 플레이어 영화, 흥행, 리뷰, 시상식, 사후 지표
- `history_*`: 국내/외화 역사 이벤트, 티켓값, 보호 필모그래피, 시상식 역사
- `production_*`: 진행 중 프로젝트, 예산, 대화/랜덤 이벤트, 단계 로그
- `systems_*`: 명성, 인맥, 언론, 평론, 표절, 프랜차이즈, 사후 반응, 미래 생성
- `save_*`: 현재 플레이 세이브 상태와 자동 생성 결과
