# 업로드 및 검증 기록

2026-10-29, Asia/Seoul. 프로젝트 이름은 충무로 타이쿤입니다. 다운로드 폴더의 기존 소스 사본을 백업했으며 README 제목을 한글 이름으로 표시했습니다. Python 파일 134개의 구문과 JSON 파일의 구문을 확인했습니다.

기존 scripts/validate_seed_structure.py 검사는 `unexpected seed file: history/historical_domestic_releases.json`으로 종료 코드 1을 반환합니다. 시드 데이터의 예상 목록과 실제 파일 목록 사이에 차이가 있습니다. 이 백업에서는 게임 코드를 수정하지 않았습니다. 전체 플레이 루프와 Windows 실행은 재검증하지 않았습니다.

환경 비밀값, 실행 중 생성된 SQLite DB/세이브, 외부 수집 원문 data/imported 및 캐시는 제외하고, 실행에 필요한 seed JSON과 소스를 포함했습니다. API 키는 .env.example의 빈 항목에 사용자가 별도로 설정합니다.
