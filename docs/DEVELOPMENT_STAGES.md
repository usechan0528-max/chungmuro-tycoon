# Development Stages

이 문서는 ChungmuroTycoon의 구현 순서를 고정하는 작업 기준표다. 각 단계는 작게 끝내는 데모가 아니라, 이후 대형 로컬 시뮬레이션으로 확장될 구조를 남기는 것을 목표로 한다.

상태 구분:

- `done`: 현재 코드에서 실행 또는 조회 가능
- `foundation`: DB, 서비스, 화면 껍데기가 있으며 세부 룰 확장이 필요
- `next`: 다음 구현 우선순위

| 단계 | 목표 | 상태 | 현재 기준 파일 |
|---|---|---|---|
| 1 | 프로젝트 구조와 DB 스키마 전체 생성 | done | `app/database.py`, `app/models/`, `docs/ARCHITECTURE.md` |
| 2 | seed JSON 기본 데이터 작성 | done | `data/seed/core/`, `data/seed/people/`, `data/seed/history/`, `data/seed/production/` |
| 3 | DB 초기화/시드 import 구현 | done | `scripts/init_db.py`, `scripts/seed_db.py`, `app/database.py` |
| 4 | 캐릭터 생성과 대시보드 구현 | done | `character_creation.py`, `dashboard.py`, `character_service.py`, `game_state.py` |
| 5 | 영화 기획/제작비 배분 구현 | done | `film_planning.py`, `film_service.py`, `budget_service.py` |
| 6 | 제작 단계 진행 구현 | done | `production_progress.py`, `progression_service.py`, `film_service.py` |
| 7 | 제작 중 이벤트 구현 | done | `event_service.py`, `event_engine.py`, `production_screen.py` |
| 8 | 개봉 결과 계산 구현 | done | `boxoffice_service.py`, `box_office_result.py` |
| 9 | 명성/인맥 변화 구현 | foundation | `reputation_service.py`, `network_service.py`, `boxoffice_service.py` |
| 10 | 배우/감독 DB 표시 구현 | done | `people_database.py`, `people_service.py` |
| 11 | 대화형 선택지 구현 | foundation | `dialogue_service.py`, `event_engine.py`, `dialogue_event.py` |
| 12 | 역사 이벤트 타임라인 표시 구현 | done | `history_service.py`, `history_timeline.py`, `world_service.py` |
| 13 | 시상식/언론/평론가 화면의 기본 구조 구현 | done | `awards_screen.py`, `press_and_critics.py`, `award_service.py`, `press_service.py`, `critic_service.py` |
| 14 | 세이브/로드 구현 | done | `save_service.py`, `save_load.py` |
| 15 | exe 빌드 | foundation | `scripts/build_exe.py`, `requirements.txt` |

## 다음 집중 작업

불변 조건: `python main.py` 실행이 깨지면 안 된다. 새 게임, 캐릭터 생성, 대시보드, 영화 기획, 제작 진행, 개봉 결과, 세이브 루프는 항상 유지한다. 기능이 완성되지 않은 시스템도 화면과 서비스 껍데기를 먼저 두되, 런타임 오류를 만들지 않는다.

1. `BudgetAllocationScreen`을 영화 기획 플로우에서 별도 단계로 분리한다.
2. `CastingScreen`을 `casting_service.py`와 연결해 실제 프로젝트 캐스팅을 가능하게 한다.
3. `DialogueEventScreen`을 투자/캐스팅/언론 협상용 화면으로 분리해 `dialogue_service.py`를 직접 사용하게 한다.
4. 마케팅/개봉 전략 화면에 `era_service.choice_state()`를 연결해 시대별 잠김, 강세, 비효율 경고를 표시한다.
5. 개봉 결과 화면에 표절, 평론, 언론, 시상식, 시리즈화, 재평가 결과 탭을 붙인다.
6. Windows 환경에서 `python scripts/build_exe.py`로 실제 `.exe` 산출물을 검증한다.

## 필수 검증 명령

```bash
python -m compileall app main.py scripts
python scripts/validate_seed_structure.py
python scripts/smoke_play_loop.py
```

## Windows 빌드 기준

- 프로젝트명은 `ChungmuroTycoon`, 폴더명은 `chungmuro_tycoon`, 실행 파일명은 `ChungmuroTycoon.exe`로 고정한다.
- Windows에서 Python 3.11 또는 3.12 가상환경을 사용한다.
- 패키지는 `pip install -r requirements.txt`로 설치한다.
- 실행 파일은 `python scripts/build_exe.py` 또는 `pyinstaller --onedir --windowed main.py --name ChungmuroTycoon`로 만든다.
