from __future__ import annotations

import math
from typing import Any


DEFAULT_INVESTOR_PROFIT_SHARE = 0.35
DEFAULT_RECOUPMENT_PRIORITY = "investor_first"


def effective_credit_limit(reputation: dict[str, Any], studio: dict[str, Any]) -> int:
    stored = int(studio.get("credit_limit") or 0)
    investor_reputation = int(reputation.get("investor_reputation") or 0)
    industry_reputation = int(reputation.get("industry_reputation") or 0)
    fame = int(studio.get("fame") or 0)
    own = int(studio.get("own_capital") or 0)
    calculated = (
        120_000_000
        + investor_reputation * 9_000_000
        + industry_reputation * 4_000_000
        + fame * 12_000_000
        + int(own * 0.25)
    )
    return max(stored, calculated)


def project_financing_capacity(
    reputation: dict[str, Any],
    studio: dict[str, Any],
    *,
    credit_limit: int,
    loan_balance: int,
) -> int:
    own = int(studio.get("own_capital") or 0)
    investment = int(studio.get("investment_capital") or 0)
    loan_capital = int(studio.get("loan_capital") or 0)
    available_credit = max(0, int(credit_limit) - int(loan_balance))
    investor_reputation = int(reputation.get("investor_reputation") or 0)
    industry_reputation = int(reputation.get("industry_reputation") or 0)
    fame = int(studio.get("fame") or 0)
    future_investment_capacity = max(
        250_000_000,
        investor_reputation * 65_000_000 + industry_reputation * 35_000_000 + fame * 90_000_000,
    )
    debt_penalty = min(int(loan_balance * 0.35), 5_000_000_000)
    return max(0, own + investment + loan_capital + available_credit + future_investment_capacity - debt_penalty)


def loan_interest_rate(reputation: dict[str, Any], studio: dict[str, Any], *, bridge: bool = False) -> float:
    investor_reputation = int(reputation.get("investor_reputation") or 0)
    base = 7.5 if bridge else 5.8
    discount = min(2.0, investor_reputation / 60)
    debt_pressure = min(2.5, int(studio.get("loan_balance") or studio.get("debt") or 0) / 1_000_000_000)
    return round(max(3.2, base - discount + debt_pressure), 2)


def monthly_principal_payment(amount: int, term_months: int) -> int:
    return int(math.ceil(max(0, int(amount)) / max(1, int(term_months or 1))))


def loan_interest_estimate(amount: int, annual_interest_rate: float, *, term_months: int) -> int:
    amount = max(0, int(amount))
    if amount <= 0:
        return 0
    return int(round(amount * (float(annual_interest_rate) / 100) * (max(1, term_months) / 12)))


def investment_contract_terms(
    reputation: dict[str, Any],
    *,
    total_cost: int,
    investment_amount: int,
    additional_amount: int = 0,
) -> dict[str, Any]:
    total_cost = max(1, int(total_cost or 0))
    investment_amount = max(0, int(investment_amount or 0))
    if investment_amount <= 0:
        return {
            "investorName": "",
            "equityPercent": 0.0,
            "profitShare": 0.0,
            "recoupmentPriority": DEFAULT_RECOUPMENT_PRIORITY,
            "recoupmentCap": 0,
            "summary": "투자 계약 없음",
        }
    investor_reputation = int(reputation.get("investor_reputation") or 0)
    equity = round(min(85.0, max(5.0, (investment_amount / total_cost) * 100)), 2)
    risk_premium = 0.08 if investor_reputation < 25 else 0.04 if investor_reputation < 55 else 0.02
    profit_share = round(min(0.8, max(0.12, (equity / 100) * 0.85 + risk_premium)), 3)
    recoupment_cap = int(investment_amount * (1.15 + risk_premium))
    investor_name = investor_name_for_contract(investment_amount, investor_reputation)
    return {
        "investorName": investor_name,
        "equityPercent": equity,
        "profitShare": profit_share,
        "recoupmentPriority": DEFAULT_RECOUPMENT_PRIORITY,
        "recoupmentCap": recoupment_cap,
        "additionalAmount": int(additional_amount or 0),
        "summary": (
            f"{investor_name}가 총비용 기준 약 {equity:.1f}% 지분으로 참여한다. "
            f"정산은 투자금 우선 회수 후 초과 수익의 {profit_share * 100:.1f}%를 투자자에게 배분한다."
        ),
    }


def investor_name_for_contract(amount: int, investor_reputation: int) -> str:
    if amount >= 5_000_000_000 or investor_reputation >= 60:
        return "메이저 투자배급사"
    if amount >= 1_000_000_000 or investor_reputation >= 35:
        return "중견 투자사"
    return "개인 투자자 조합"
