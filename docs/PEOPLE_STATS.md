# People Stat Estimation

배우와 감독의 스탯은 직접 100점 만점으로 전부 입력하지 않는다. 1차 빌드는 `tier`, 유형 태그, 장르 태그, 활동 시기만 수동으로 두고, 서비스가 내부 스탯을 생성한다. 숫자는 내부 계산에만 쓰며 UI에는 구두 평가만 표시한다.

## Core Rule

```text
1단계: tier 기반 기본값
2단계: roleType/directorType, genreTags 보정
3단계: KOBIS staging 흥행/필모그래피 데이터 보정
4단계: 주요 인물 manualOverride 보정
5단계: current_year 기준 peakEras/나이/활동 시기 보정
```

`manualOverride: true`이고 `manualStats`가 있으면 해당 항목은 자동 산정보다 우선한다. 모든 인물을 수동 수치로 관리하지 않고, 송강호/최민식/전도연/봉준호/박찬욱/최동훈 같은 핵심 인물만 직접 보정한다.

## Actor Seed

배우 seed의 최소 구조:

```json
{
  "id": "actor_song_kang_ho",
  "nameKo": "송강호",
  "type": "actor",
  "birthYear": 1967,
  "availableFrom": 1996,
  "tier": "legend",
  "roleType": ["연기파", "국민배우", "영화제형", "글로벌형"],
  "peakEras": [{ "start": 2003, "end": 2019 }],
  "genreTags": ["drama", "crime_thriller", "black_comedy", "historical"],
  "manualOverride": true,
  "manualStats": {
    "acting": 98,
    "ticketPower": 92,
    "festivalPower": 95,
    "brandPower": 95,
    "globalRecognition": 92
  }
}
```

내부 스탯:

- `acting`: 연기력
- `ticketPower`: 티켓파워
- `festivalPower`: 영화제/시상식 영향력
- `brandPower`: 브랜드 평판
- `globalRecognition`: 해외 인지도
- `costLevel`: 출연료 부담
- `scheduleDifficulty`: 스케줄 난이도
- `growthPotential`: 성장 잠재력
- `genreFit`: 장르 적합도

## Director Seed

감독 seed의 최소 구조:

```json
{
  "id": "director_bong_joon_ho",
  "nameKo": "봉준호",
  "type": "director",
  "birthYear": 1969,
  "availableFrom": 2000,
  "tier": "global_auteur",
  "directorType": ["작가주의", "상업성", "글로벌", "장르혼합"],
  "peakEras": [{ "start": 2003, "end": 2019 }],
  "genreTags": ["crime_thriller", "black_comedy", "monster", "drama", "sf"],
  "protectionLevel": "legendaryProtected",
  "manualOverride": true
}
```

내부 스탯:

- `directing`: 연출력
- `screenplay`: 각본/구성력
- `commercialSense`: 상업 감각
- `auteurPower`: 작가주의
- `genreControl`: 장르 통제력
- `budgetControl`: 예산 관리력
- `festivalPower`: 영화제 파워
- `globalRecognition`: 해외 인지도
- `costLevel`: 연출료 부담
- `scheduleDifficulty`: 스케줄 난이도
- `growthPotential`: 성장 잠재력
- `genreFit`: 장르 적합도

## Era Adjustment

`peakEras`는 같은 인물이 연도에 따라 다르게 보이도록 한다. 전성기 전에는 현재 능력이 낮고 잠재력 설명이 강해지며, 전성기에는 현재 능력 보정이 붙고, 이후에는 명성은 남지만 일부 시장 효율과 스케줄 난이도가 달라진다.

```json
{
  "peakEras": [
    {
      "start": 2003,
      "end": 2019,
      "modifiers": {
        "acting": 1.08,
        "ticketPower": 1.12,
        "brandPower": 1.1
      }
    }
  ]
}
```

## UI Rule

UI는 다음 공개 문장만 표시한다.

- 한줄 평가
- 현재 능력 설명
- 잠재력 설명
- 명성 설명
- 브랜드 평판

내부 숫자, 산식, 가중치, 비용/스케줄 난이도 수치는 화면에 직접 표시하지 않는다.

## Commands

현재 DB의 staging 데이터를 이용해 인물 스탯을 다시 계산한다.

```bash
python3 scripts/estimate_people_stats.py
```

seed를 다시 적재할 때는 `scripts/seed_db.py`가 자동으로 스탯 추정을 함께 실행한다.
