from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.economic_service import adjust_labor_wage_to_year
from app.services.game_state import GameStateService, clamp, money


@dataclass(frozen=True)
class CrewWorkOption:
    id: str
    title: str
    role_label: str
    days: int
    base_daily_wage: int
    description: str
    learning_text: str
    network_text: str
    stats_delta: dict[str, int]
    network_delta: dict[str, int]


CREW_WORK_OPTIONS: tuple[CrewWorkOption, ...] = (
    CrewWorkOption(
        id="production_runner",
        title="제작부 현장 보조",
        role_label="제작부 막내",
        days=3,
        base_daily_wage=110_000,
        description="콜타임, 도시락, 장비 이동, 현장 연락을 따라다니며 제작 현장의 기본 호흡을 익힌다.",
        learning_text="현장 진행 감각과 제작부 언어가 익숙해진다.",
        network_text="제작부와 현장 스태프 쪽 연락처가 조금 생긴다.",
        stats_delta={"field_control": 2, "learning_ability": 1},
        network_delta={"production_network": 2, "director_network": 1},
    ),
    CrewWorkOption(
        id="camera_assistant",
        title="촬영 보조",
        role_label="촬영팀 보조",
        days=4,
        base_daily_wage=120_000,
        description="렌즈, 삼각대, 배터리, 데이터 백업을 돕고 카메라 팀의 움직임을 가까이서 본다.",
        learning_text="화면 구성과 촬영 동선에 대한 감이 조금 생긴다.",
        network_text="촬영팀과 조감독 라인에 얼굴을 알린다.",
        stats_delta={"directing_ability": 1, "field_control": 1, "artistic_sense": 1},
        network_delta={"production_network": 2, "director_network": 1},
    ),
    CrewWorkOption(
        id="lighting_assistant",
        title="조명 보조",
        role_label="조명팀 보조",
        days=4,
        base_daily_wage=130_000,
        description="스탠드, 케이블, 확산지, 안전 동선을 챙기며 장면의 톤이 만들어지는 과정을 배운다.",
        learning_text="빛과 현장 안전, 촬영 리듬에 대한 감각이 좋아진다.",
        network_text="조명팀과 촬영팀의 실무자들과 안면을 튼다.",
        stats_delta={"field_control": 2, "artistic_sense": 1},
        network_delta={"production_network": 2, "regional_network": 1},
    ),
    CrewWorkOption(
        id="sound_assistant",
        title="음향 보조",
        role_label="동시녹음 보조",
        days=3,
        base_daily_wage=120_000,
        description="붐 마이크, 무선 마이크, 현장 소음 체크를 보조하며 사운드가 장면을 살리는 방식을 배운다.",
        learning_text="대사 전달과 현장 소리의 중요성을 체감한다.",
        network_text="동시녹음과 후반 사운드 쪽 인맥이 생긴다.",
        stats_delta={"artistic_sense": 1, "field_control": 1, "learning_ability": 1},
        network_delta={"production_network": 1, "director_network": 1},
    ),
    CrewWorkOption(
        id="editing_assistant",
        title="편집 보조",
        role_label="편집실 보조",
        days=5,
        base_daily_wage=100_000,
        description="러프컷 정리, 파일 관리, 대사 싱크 확인을 돕고 영화가 후반에서 다시 쓰이는 과정을 본다.",
        learning_text="구조, 리듬, 장면 선택에 대한 감각이 쌓인다.",
        network_text="편집실과 감독 주변 실무자들에게 이름을 알린다.",
        stats_delta={"screenplay_sense": 1, "directing_ability": 1, "learning_ability": 1},
        network_delta={"production_network": 1, "director_network": 2},
    ),
    CrewWorkOption(
        id="marketing_part_time",
        title="시사회/홍보 아르바이트",
        role_label="홍보 보조",
        days=2,
        base_daily_wage=90_000,
        description="언론시사회 접수, 관객 동선 안내, 홍보물 배포를 맡으며 영화가 관객을 만나는 방식을 본다.",
        learning_text="홍보 문구와 관객 반응을 읽는 감각이 조금 생긴다.",
        network_text="홍보사, 기자, 배급 실무자와 마주칠 기회가 생긴다.",
        stats_delta={"marketing_sense": 2, "market_analysis": 1},
        network_delta={"press_network": 1, "distribution_network": 1},
    ),
    CrewWorkOption(
        id="festival_staff",
        title="영화제 스태프",
        role_label="영화제 운영 보조",
        days=4,
        base_daily_wage=70_000,
        description="상영관 운영, 게스트 응대, 관객 안내를 맡으며 독립영화와 영화제 생태계를 가까이서 본다.",
        learning_text="영화제 취향과 작품성 평가 기준을 어렴풋이 익힌다.",
        network_text="프로그래머, 평론가, 독립영화 관계자 쪽 접점이 생긴다.",
        stats_delta={"artistic_sense": 1, "market_analysis": 1, "learning_ability": 1},
        network_delta={"festival_network": 3, "critic_access": 1, "school_network": 1},
    ),
)


def get_crew_work_state() -> dict[str, Any]:
    with get_connection() as conn:
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        rows = conn.execute(
            """
            SELECT *
            FROM crew_work_history
            ORDER BY start_year DESC, start_month DESC, start_day DESC, created_at DESC
            LIMIT 20
            """
        ).fetchall()
    current_year = int(player["current_year"]) if player else 2020
    return {
        "currentYear": current_year,
        "options": [_public_option(option, current_year) for option in CREW_WORK_OPTIONS],
        "history": [_history_from_row(dict(row)) for row in rows],
        "intro": f"프로젝트를 직접 만들 돈이 부족할 때는 남의 현장에 들어가 시간을 팔고 감각을 얻을 수 있다. 일당은 {current_year}년 물가 기준으로 산정된다.",
    }


def perform_crew_work(work_id: str) -> dict[str, Any]:
    option = _option_by_id(work_id)
    from app.services.calendar_service import add_calendar_event, current_game_date

    start = current_game_date()
    worked_days = 0
    state = GameStateService()
    interrupted_project_id: str | None = None
    for _ in range(option.days):
        interrupted_project_id = state._first_project_with_available_event()
        if interrupted_project_id:
            break
        state.advance_day()
        worked_days += 1
        interrupted_project_id = state._first_project_with_available_event()
        if interrupted_project_id:
            break

    if worked_days <= 0:
        return {
            "completed": False,
            "interruptedProjectId": interrupted_project_id,
            "summary": "진행 중인 프로젝트에 처리해야 할 제작 변수가 있어 현장 일거리를 시작하지 못했습니다.",
        }

    end = current_game_date()
    daily_wage = _daily_wage_for_year(option, start[0])
    total_pay = daily_wage * worked_days
    stats_delta = _scale_delta(option.stats_delta, worked_days, option.days)
    network_delta = _scale_delta(option.network_delta, worked_days, option.days)

    with get_connection() as conn:
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        if not player:
            raise ValueError("플레이어 상태가 없습니다.")
        stats = loads_json(player["stats_json"], {})
        network = loads_json(player["network_json"], {})
        for key, delta in stats_delta.items():
            stats[key] = clamp(float(stats.get(key, 45)) + delta)
        for key, delta in network_delta.items():
            network[key] = clamp(float(network.get(key, 5)) + delta)

        from app.services.finance_service import add_own_capital_income

        add_own_capital_income(
            conn,
            player,
            amount=total_pay,
            source="crew_work",
            description=f"{option.title} 일당 수입",
            metadata={"workId": option.id, "daysWorked": worked_days, "dailyWage": daily_wage},
        )
        conn.execute(
            "UPDATE player_state SET stats_json = ?, network_json = ? WHERE id = 1",
            (dumps_json(stats), dumps_json(network)),
        )
        conn.execute(
            """
            INSERT INTO crew_work_history (
                id, work_type, title, start_year, start_month, start_day,
                end_year, end_month, end_day, days_worked, daily_wage, total_pay,
                stats_delta_json, network_delta_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"crew_work_{uuid.uuid4().hex[:10]}",
                option.id,
                option.title,
                start[0],
                start[1],
                start[2],
                end[0],
                end[1],
                end[2],
                worked_days,
                daily_wage,
                total_pay,
                dumps_json(stats_delta),
                dumps_json(network_delta),
                _result_summary(option, worked_days, total_pay, bool(interrupted_project_id)),
            ),
        )
        conn.commit()

    add_calendar_event(
        title=f"{option.title} 참여",
        event_type="crew_work",
        start=start,
        end=end,
        description=f"{option.role_label}로 {worked_days}일 동안 현장에 참여했다.",
        metadata={"workId": option.id, "daysWorked": worked_days, "totalPay": total_pay},
    )
    return {
        "completed": worked_days == option.days,
        "interruptedProjectId": interrupted_project_id,
        "title": option.title,
        "daysWorked": worked_days,
        "totalPay": total_pay,
        "summary": _result_summary(option, worked_days, total_pay, bool(interrupted_project_id)),
        "knowledgeText": option.learning_text,
        "networkText": option.network_text,
    }


def _public_option(option: CrewWorkOption, year: int) -> dict[str, Any]:
    daily_wage = _daily_wage_for_year(option, year)
    return {
        "id": option.id,
        "title": option.title,
        "roleLabel": option.role_label,
        "days": option.days,
        "dailyWage": daily_wage,
        "totalPay": daily_wage * option.days,
        "wageBasis": f"{year}년 물가 기준",
        "description": option.description,
        "learningText": option.learning_text,
        "networkText": option.network_text,
    }


def _daily_wage_for_year(option: CrewWorkOption, year: int) -> int:
    return max(10_000, adjust_labor_wage_to_year(option.base_daily_wage, to_year=year))


def _option_by_id(work_id: str) -> CrewWorkOption:
    for option in CREW_WORK_OPTIONS:
        if option.id == work_id:
            return option
    raise ValueError("선택한 현장 일거리를 찾을 수 없습니다.")


def _scale_delta(values: dict[str, int], worked_days: int, planned_days: int) -> dict[str, int]:
    ratio = max(0.0, min(1.0, worked_days / max(1, planned_days)))
    return {key: max(1, round(value * ratio)) for key, value in values.items() if round(value * ratio) != 0}


def _result_summary(option: CrewWorkOption, worked_days: int, total_pay: int, interrupted: bool) -> str:
    base = f"{option.role_label}로 {worked_days}일 일하며 {money(total_pay)}을 벌었습니다."
    if interrupted:
        return base + " 진행 중인 프로젝트 변수 때문에 예정된 일정을 끝까지 채우지는 못했습니다."
    return base + " 현장의 말투와 리듬이 조금 더 익숙해졌습니다."


def _history_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row["title"],
        "period": f"{row['start_year']}.{row['start_month']}.{row['start_day']}~{row['end_year']}.{row['end_month']}.{row['end_day']}",
        "daysWorked": int(row.get("days_worked") or 0),
        "totalPay": int(row.get("total_pay") or 0),
        "summary": row.get("summary") or "",
    }
