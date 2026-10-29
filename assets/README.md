# Assets

기본 배포본은 실제 인물 사진, 실제 영화 포스터, 회사/시상식 로고 파일을 포함하지 않는다. 저작권과 초상권을 피하기 위해 화면은 텍스트와 placeholder를 기본값으로 사용한다.

사용자가 직접 확보한 이미지 파일은 `media/` 아래에 로컬 패치처럼 넣을 수 있다. 파일이 없으면 UI는 자동으로 placeholder를 유지한다.

## 자동 파일명 규칙

```text
media/people/actors/{actor_id}.jpg
media/people/directors/{director_id}.jpg
media/people/directors/player.jpg
media/people/critics/{critic_id}.jpg
media/posters/historical/{film_id}.jpg
media/posters/player/{film_id}.png
media/logos/organizations/{organization_id}.png
media/logos/awards/{award_id}.png
```

지원 확장자는 `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`다.

## manifest 사용

파일명을 ID와 다르게 두고 싶으면 `media/manifest.local.json`을 만들고 `media/manifest.example.json` 형식대로 매핑한다. `manifest.local.json`은 로컬 패치용이며 git에 포함하지 않는다.

## 기존 폴더

- `portraits/`: 중립 placeholder 또는 UI용 자체 자산
- `posters/`: 구형 placeholder 폴더. 신규 포스터 패치는 `media/posters/` 사용
- `ui/`: 자체 제작 UI 자산
