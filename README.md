# 충무로 타이쿤 (Chungmuro Tycoon)

ChungmuroTycoon은 한국 영화계를 배경으로 한 영화 제작자 시뮬레이션 게임이다.

플레이어는 감독, 배급사 사장, 대학생 중 하나로 시작해 실제 한국 영화사의 흐름 속에서 영화를 기획하고, 투자자를 설득하고, 배우를 캐스팅하고, 제작과 개봉을 거쳐 명성과 자본을 쌓아간다.

게임은 실제 역사 기반 이벤트와 유연한 대체역사 구조를 결합한다. 외화 대작, 티켓값, 일부 핵심 감독의 필모그래피는 실제 역사와 동일하게 반영되며, 플레이어의 선택에 따라 자신의 제작사와 작품의 역사는 달라질 수 있다.

UI 톤은 현실적 산업 시뮬레이션을 기준으로 한다. Football Manager와 Civilization 계열의 텍스트 전략 화면처럼 지표, 리스트, 보고 문장을 중심에 두며, 과장된 캐주얼 연출보다 건조한 제작사 운영 리포트에 가깝게 설계한다.
기본 배포본은 실제 인물 사진과 실제 영화 포스터를 포함하지 않는다. 다만 사용자가 직접 확보한 이미지 파일을 `assets/media/`에 넣으면 인물 사진, 영화 포스터, 회사/극장 로고, 시상식 로고를 로컬 미디어 패치처럼 표시할 수 있다.

## 1차 프로토타입 기능

- 새 게임 시작
- 캐릭터 생성
- 메인 대시보드
- 영화 프로젝트 생성
- 장르와 규모 선택
- 제작비와 마케팅비 입력
- 예산 배분
- 제작 중 이벤트 선택지
- 개봉 결과 계산
- 명성, 현금, 인맥 변화 반영
- 세이브/로드
- 진행하기 1회당 하루 진행
- 일일 진행 후 자동 저장
- 3개 이상 세이브 슬롯
- 플레이어 제작 필모그래피 기록
- 관객 수, 손익, 수상, 평론 반응, 배우/감독 협업 기록
- 실패작, 역주행/재평가, 시리즈/IP 기록
- 현재 게임 날짜 기준 시장 박스오피스와 스크린 점유율 조회

필수 화면 세트는 `StartScreen`, `CharacterCreationScreen`, `DashboardScreen`, `PeopleDatabaseScreen`, `FilmPlanningScreen`, `BudgetAllocationScreen`, `CastingScreen`, `DialogueEventScreen`, `ProductionProgressScreen`, `ReleaseStrategyScreen`, `BoxOfficeResultScreen`, `HistoryTimelineScreen`, `SaveLoadScreen`이다.

## 지원 환경

- 프로젝트명: ChungmuroTycoon
- 폴더명: `chungmuro_tycoon`
- 실행 파일명: `ChungmuroTycoon.exe`
- 운영체제: Windows
- Python: 3.11 또는 3.12
- 패키지 관리자: pip
- UI: PySide6
- DB: SQLite
- 패키징: PyInstaller

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 실행

```bash
python main.py
```

## 필수 루프 스모크 테스트

아래 명령은 현재 DB와 `saves/save_*.db`를 백업한 뒤, 새 게임부터 세이브까지의 최소 루프를 검증하고 원래 파일을 복구한다.

```bash
python scripts/smoke_play_loop.py
```

## DB 초기화

```bash
python scripts/init_db.py
python scripts/seed_db.py
```

## 실제 데이터 수집

KMDb/KOBIS/KOFIC/KOSIS 기반 실제 데이터는 먼저 staging 테이블에 넣고, 이후 검수된 데이터만 게임용 seed/역사 테이블로 승격한다.
API 키는 `.env`에 직접 입력하며 코드에 하드코딩하지 않는다.

```bash
copy .env.example .env
python scripts/import_seed.py
python scripts/fetch_kobis.py --help
python scripts/fetch_kmdb.py --help
python scripts/import_kmdb_json.py /Users/dldydcks/Downloads/kmdb_json.json
python scripts/import_kofic_reports.py --downloads /Users/dldydcks/Downloads
python scripts/fetch_kosis.py --help
python scripts/fetch_kosis.py cpi
python scripts/build_economic_adjustments.py
python scripts/fetch_wikidata.py --help
python scripts/build_ticket_prices.py --help
python scripts/build_annual_reports.py --all-available
python scripts/estimate_people_stats.py
```

수집 우선순위와 API 키 설정은 `docs/DATA_COLLECTION.md`를 기준으로 한다.
현재 1차 실제 DB 수집 범위는 KOBIS 박스오피스 2004년~현재, KMDb 한국영화 1980년~현재, 외화 이벤트 100편, 배우 300명, 감독 150명, 평론가 30명, 주요 시상식 6개 축으로 고정한다.
KOSIS는 소비자물가지수, 가계 소비 여건, 경기 침체/호황, 청년·지역 인구, 문화소비 지표를 staging으로 수집해 제작비 체감 보정, 티켓값 부담, 극장 수요, 미래 자동 생성 경제 변수에 사용한다.
KOFIC 한국영화산업 결산 PDF/XLS/HWP는 `scripts/import_kofic_reports.py`로 파일 메타데이터, 추출 텍스트 경로, 산업 지표 후보, 등장 이벤트 후보를 staging에 저장한다. 추출 텍스트는 `data/imported/` 아래 로컬 산출물로만 보관한다.
PDF/XLS/HWP 로컬 보고서 추출을 직접 실행할 환경에는 `pip install -r requirements-data.txt`를 추가로 설치하면 된다.
Wikidata SPARQL은 한국 영화와 영화계 인물의 QID, 영문명, 생년, 직업, 외부 식별자를 보강하는 보조 출처로 사용하며 원본 응답은 `staging_wikidata_sparql_results`, 매칭용 정규화 결과는 `wikidata_movies`와 `wikidata_people`에 저장한다. KOBIS/KMDb와 충돌할 경우 KOBIS/KMDb를 우선한다.
주요 한국 영화 500편 후보는 `scripts/fetch_major_korean_movies.py`로 `staging_major_korean_movies`에 수집한다.
연간 결산은 `scripts/build_annual_reports.py`로 생성하며, 박스오피스 TOP 10, 한국영화 점유율, 외화 흥행작, 올해의 배우/감독, 주요 시상식, 제작사·배급사·장르 트렌드를 `industry_yearly_reports`에 저장한다.
배우/감독 내부 스탯은 `scripts/estimate_people_stats.py`로 tier/태그 기본값, 실제 staging 데이터, 시대별 전성기, 주요 인물 수동 오버라이드를 결합해 산정한다.

## exe 빌드

```bash
pyinstaller --onedir --windowed main.py --name ChungmuroTycoon
```

또는:

```bash
python scripts/build_exe.py
```

Windows 빌드 결과의 실행 파일 경로는 `dist\ChungmuroTycoon\ChungmuroTycoon.exe`다.

## 프로젝트 구조

```text
chungmuro_tycoon/
  main.py
  requirements.txt
  README.md
  app/
    config.py
    database.py
    models/
    services/
    ui/
  data/
    game.db
    seed/
  scripts/
  saves/
  assets/
```

## 개발 메모

- UI와 게임 로직은 분리되어 있다.
- SQLite 접근은 `app/database.py`와 `app/services/`를 통해 처리한다.
- 배우와 감독의 내부 수치는 DB에 저장할 수 있지만, UI에서는 공개 프로필 문장 중심으로 보여주는 구조를 유지한다.
- 이벤트와 선택지는 seed JSON에서 DB로 적재되고, 런타임에서는 범용 `simulation_events`와 `event_history` 구조로 처리한다.
- `data/game.db`는 고정 마스터 DB로 사용한다. 시드 데이터, 실제 역사, 기준 규칙, 수집 데이터는 여기에 적재한다.
- `saves/save_001.db`는 기본 플레이어 진행 데이터 DB다. 새 게임은 마스터 DB를 슬롯 1로 복제한 뒤 해당 세이브 DB에서 진행한다.
- 세이브 슬롯은 `saves/save_001.db`, `saves/save_002.db`, `saves/save_003.db` 형식으로 관리한다.
- 세이브 DB는 플레이어/제작사 상태, 현재 날짜, 프로젝트, 완성작, 명성, 인맥, 관계도, 역사 이벤트 flag, 미래 생성 인물/영화를 보존한다.
- 수동 저장은 슬롯을 선택할 수 있고, 진행하기로 하루가 지난 뒤에는 현재 활성 슬롯에 자동 저장한다.
- 장기 확장 구조는 `docs/ARCHITECTURE.md`를 기준으로 한다.
- 전체 게임 시스템 기준은 `docs/GAME_SYSTEM_OVERVIEW.md`를 기준으로 한다.
- seed 폴더 구조는 `docs/SEED_STRUCTURE.md`를 기준으로 한다.
- UI 톤과 화면 문장 원칙은 `docs/UI_DIRECTION.md`를 기준으로 한다.
- 실제 이미지 번들링과 로컬 미디어 패치 원칙은 `docs/ASSET_POLICY.md`를 기준으로 한다.
- 배우/감독 스탯 산정 원칙은 `docs/PEOPLE_STATS.md`를 기준으로 한다.
- 15단계 개발 순서는 `docs/DEVELOPMENT_STAGES.md`를 기준으로 한다.

## 로컬 미디어 패치

저작권과 초상권 문제 때문에 게임은 실사 이미지 파일을 기본 제공하지 않는다. 사용자가 직접 확보한 파일을 아래처럼 넣으면 해당 ID 화면에서 자동으로 표시된다.

```text
assets/media/people/actors/actor_song_kang_ho.jpg
assets/media/people/directors/director_bong_joon_ho.jpg
assets/media/people/directors/player.jpg
assets/media/people/critics/critic_lee_dongjin.jpg
assets/media/posters/historical/film_2019_parasite.jpg
assets/media/posters/player/player_my_movie.png
assets/media/logos/organizations/org_cgv.png
assets/media/logos/awards/award_cannes.png
```

파일명이 DB ID와 다르면 `assets/media/manifest.local.json`을 만들고 `assets/media/manifest.example.json` 형식대로 매핑하면 된다. exe 빌드 후에는 `ChungmuroTycoon.exe` 옆의 `assets/media/` 폴더에 같은 구조로 넣으면 로컬 패치처럼 동작한다.
