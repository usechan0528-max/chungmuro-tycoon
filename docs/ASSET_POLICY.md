# Asset Policy

ChungmuroTycoon 기본 배포본은 실제 인물 사진, 실제 영화 포스터, 회사/시상식 로고 이미지를 포함하지 않는다. UI는 이름, 경력, 공개 프로필 문장, 산업 지표, 이벤트 텍스트를 중심으로 구성하고, 이미지가 없는 경우 placeholder를 표시한다.

다만 사용자가 직접 확보한 합법적인 이미지 파일은 `assets/media/`에 넣어 로컬 미디어 패치처럼 사용할 수 있다. 이 패치는 게임 실행 구조에만 연결되며, 프로젝트가 실사 이미지를 기본 제공한다는 의미는 아니다.

## People

- 기본 배포본에는 배우, 감독, 평론가 사진을 넣지 않는다.
- 인물 이미지는 중립적인 silhouette placeholder를 기본값으로 사용한다.
- 사용자가 직접 확보한 인물 사진은 `assets/media/people/actors/`, `assets/media/people/directors/`, `assets/media/people/critics/`에 ID 기반 파일명으로 넣을 수 있다.
- 내부 스탯은 숫자로 노출하지 않고 공개 프로필 문장으로 표현한다.
- 실제 인물의 외모, 초상, 홍보 사진, 기사 사진은 저장소에 포함하지 않는다.

## Movies

- 기본 배포본에는 실제 영화 포스터를 사용하지 않는다.
- 실제 영화 데이터는 제목, 개봉일, 감독, 배우, 장르, 흥행 수치, 역사 이벤트 중심으로 표현한다.
- 사용자가 직접 확보한 포스터는 `assets/media/posters/historical/` 또는 `assets/media/posters/player/`에 ID 기반 파일명으로 넣을 수 있다.
- 플레이어 제작 영화 포스터도 같은 구조를 사용한다.

## Logos

- 기본 배포본에는 회사, 극장 체인, 시상식 로고를 포함하지 않는다.
- 사용자가 직접 확보한 로고는 `assets/media/logos/organizations/`와 `assets/media/logos/awards/`에 넣을 수 있다.

## Assets Folder

- `assets/portraits/`: silhouette placeholder 또는 UI용 중립 이미지 전용
- `assets/posters/`: 구형 placeholder 폴더. 신규 포스터 패치는 `assets/media/posters/`를 사용한다
- `assets/ui/`: 버튼, 아이콘, 프레임 등 저작권 이슈가 없는 자체 UI 자산 전용
- `assets/media/`: 사용자가 직접 제공하는 로컬 미디어 패치 폴더

## Media Patch Rules

자동 탐색 파일명은 `{entity_id}.{ext}`다. 예시는 다음과 같다.

```text
assets/media/people/actors/actor_song_kang_ho.jpg
assets/media/people/directors/director_bong_joon_ho.jpg
assets/media/posters/historical/film_2019_parasite.jpg
assets/media/logos/organizations/org_cgv.png
assets/media/logos/awards/award_cannes.png
```

파일명이 DB ID와 다르면 `assets/media/manifest.local.json`을 만들고 `assets/media/manifest.example.json` 형식으로 매핑한다. 지원 확장자는 `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`다.

PyInstaller onedir 빌드 후에는 `ChungmuroTycoon.exe` 옆의 `assets/media/` 폴더를 우선 탐색한다. 따라서 사용자는 exe를 다시 빌드하지 않고도 로컬 실사화 패치를 적용할 수 있다.

## Rationale

이 정책은 초상권, 저작권, 홍보 이미지 라이선스 문제를 피하면서도 FM/문명식 텍스트 전략 UI의 방향성을 유지하기 위한 기준이다. 실사화 패치는 사용자가 권리를 확인한 로컬 파일을 연결하는 선택 기능으로만 취급한다.
