from __future__ import annotations

import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services import finance_rules
from app.services.game_state import clamp, money
from app.services.studio_reputation_service import apply_studio_reputation_delta


DEFAULT_INVESTOR_PROFIT_SHARE = finance_rules.DEFAULT_INVESTOR_PROFIT_SHARE
DEFAULT_RECOUPMENT_PRIORITY = finance_rules.DEFAULT_RECOUPMENT_PRIORITY


def get_finance_state() -> dict[str, Any]:
    with get_connection() as conn:
        _sync_studio_finance(conn)
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        loans = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE status = 'active'
            ORDER BY start_year, start_month, created_at
            """
        ).fetchall()
        contracts = conn.execute(
            """
            SELECT ic.*, p.title AS project_title
            FROM investment_contracts ic
            LEFT JOIN projects p ON p.id = ic.project_id
            WHERE ic.status IN ('active', 'recouping')
            ORDER BY signed_year, signed_month, created_at
            """
        ).fetchall()
        transactions = conn.execute(
            """
            SELECT *
            FROM finance_transactions
            ORDER BY created_at DESC, id DESC
            LIMIT 20
            """
        ).fetchall()
        cashflows = conn.execute(
            """
            SELECT cf.*, p.title AS project_title
            FROM project_cashflows cf
            LEFT JOIN projects p ON p.id = cf.project_id
            ORDER BY cf.status = 'paid', cf.planned_year, cf.planned_month, cf.planned_day, cf.created_at
            LIMIT 30
            """
        ).fetchall()
        conn.commit()
    if not studio:
        return {"available": False}

    studio_data = dict(studio)
    credit_limit = _effective_credit_limit(player, studio_data)
    loan_balance = int(studio_data.get("loan_balance") or studio_data.get("debt") or 0)
    project_capacity = project_financing_capacity(player, studio_data, credit_limit=credit_limit, loan_balance=loan_balance)
    return {
        "available": True,
        "studio": studio_data,
        "own_capital": int(studio_data.get("own_capital") or 0),
        "investment_capital": int(studio_data.get("investment_capital") or 0),
        "loan_capital": int(studio_data.get("loan_capital") or 0),
        "cash": int(studio_data.get("cash") or 0),
        "debt": int(studio_data.get("debt") or 0),
        "loan_balance": loan_balance,
        "credit_limit": credit_limit,
        "available_credit": max(0, credit_limit - loan_balance),
        "project_financing_capacity": project_capacity,
        "active_loans": [_loan_from_row(dict(row)) for row in loans],
        "investment_contracts": [_investment_contract_from_row(dict(row)) for row in contracts],
        "transactions": [_transaction_from_row(dict(row)) for row in transactions],
        "project_cashflows": [_project_cashflow_from_row(dict(row)) for row in cashflows],
        "monthly_debt_pressure": _monthly_debt_pressure([dict(row) for row in loans]),
        "overdue_interest": sum(int(row["accrued_interest"] or 0) for row in loans),
        "finance_summary": _finance_summary(studio_data, credit_limit, loan_balance),
    }


def borrow(amount: int, *, term_months: int = 12, purpose: str = "운영자금") -> dict[str, Any]:
    amount = max(0, int(amount))
    if amount <= 0:
        raise ValueError("대출 금액을 입력해야 합니다.")
    term_months = max(1, int(term_months or 12))
    with get_connection() as conn:
        _sync_studio_finance(conn)
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not player or not studio:
            raise ValueError("대출을 받을 게임 상태가 없습니다.")
        studio_data = dict(studio)
        credit_limit = _effective_credit_limit(player, studio_data)
        loan_balance = int(studio_data.get("loan_balance") or studio_data.get("debt") or 0)
        available_credit = max(0, credit_limit - loan_balance)
        if amount > available_credit:
            raise ValueError(f"현재 추가 대출 가능액은 {money(available_credit)}입니다.")

        rate = _loan_interest_rate(player, studio_data)
        due_year, due_month = _add_months(int(player["current_year"]), int(player["current_month"]), term_months)
        next_year, next_month = _add_months(int(player["current_year"]), int(player["current_month"]), 1)
        monthly_payment = _monthly_principal_payment(amount, term_months)
        loan_id = f"loan_{uuid.uuid4().hex[:10]}"
        own = int(studio_data.get("own_capital") or 0)
        investment = int(studio_data.get("investment_capital") or 0)
        loan_capital = int(studio_data.get("loan_capital") or 0) + amount
        new_loan_balance = loan_balance + amount
        new_cash = own + investment + loan_capital
        conn.execute(
            """
            INSERT INTO loans (
                id, lender_name, principal, remaining_principal,
                accrued_interest, annual_interest_rate, monthly_payment_amount,
                payments_made, delinquent_months, start_year, start_month,
                due_year, due_month, last_interest_year, last_interest_month,
                next_payment_year, next_payment_month, status, purpose, metadata_json
            ) VALUES (?, ?, ?, ?, 0, ?, ?, 0, 0, ?, ?, ?, ?, NULL, NULL, ?, ?, 'active', ?, ?)
            """,
            (
                loan_id,
                _lender_name(studio_data),
                amount,
                amount,
                rate,
                monthly_payment,
                player["current_year"],
                player["current_month"],
                due_year,
                due_month,
                next_year,
                next_month,
                purpose,
                dumps_json(
                    {
                        "termMonths": term_months,
                        "creditLimitAtBorrow": credit_limit,
                        "repaymentType": "monthly_principal_plus_interest",
                    }
                ),
            ),
        )
        conn.execute(
            """
            UPDATE studio_state
            SET loan_capital = ?, cash = ?, debt = ?, loan_balance = ?, credit_limit = ?
            WHERE id = 1
            """,
            (loan_capital, new_cash, new_loan_balance, new_loan_balance, credit_limit),
        )
        _record_transaction(
            conn,
            player,
            transaction_type="loan_draw",
            amount=amount,
            source="lender",
            target="loan_capital",
            loan_id=loan_id,
            description=f"{purpose} 명목으로 대출을 실행했다.",
            metadata={"annualInterestRate": rate, "termMonths": term_months},
        )
        conn.commit()
    return get_finance_state()


def repay_loan(amount: int) -> dict[str, Any]:
    amount = max(0, int(amount))
    if amount <= 0:
        raise ValueError("상환 금액을 입력해야 합니다.")
    with get_connection() as conn:
        _sync_studio_finance(conn)
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not player or not studio:
            raise ValueError("상환할 게임 상태가 없습니다.")
        studio_data = dict(studio)
        own_capital = int(studio_data.get("own_capital") or 0)
        loan_capital = int(studio_data.get("loan_capital") or 0)
        repayable_cash = own_capital + loan_capital
        if amount > repayable_cash:
            raise ValueError(f"상환에 쓸 수 있는 자기자본/대출금 잔액은 {money(repayable_cash)}입니다.")
        remaining_to_pay = amount
        paid = 0
        loans = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE status = 'active' AND remaining_principal > 0
            ORDER BY start_year, start_month, created_at
            """
        ).fetchall()
        for row in loans:
            if remaining_to_pay <= 0:
                break
            accrued_interest = int(row["accrued_interest"] or 0)
            interest_pay = min(accrued_interest, remaining_to_pay)
            remaining_to_pay -= interest_pay
            principal = int(row["remaining_principal"] or 0)
            principal_pay = min(principal, remaining_to_pay)
            remaining_to_pay -= principal_pay
            pay = interest_pay + principal_pay
            if pay <= 0:
                continue
            next_interest = accrued_interest - interest_pay
            next_remaining = principal - principal_pay
            conn.execute(
                """
                UPDATE loans
                SET accrued_interest = ?, remaining_principal = ?, status = ?
                WHERE id = ?
                """,
                (
                    next_interest,
                    next_remaining,
                    "repaid" if next_remaining <= 0 and next_interest <= 0 else "active",
                    row["id"],
                ),
            )
            paid += pay
        if paid <= 0:
            raise ValueError("상환할 활성 대출이 없습니다.")

        investment = int(studio_data.get("investment_capital") or 0)
        own_paid = min(own_capital, paid)
        loan_capital_paid = paid - own_paid
        new_own = own_capital - own_paid
        new_loan_capital = max(0, loan_capital - loan_capital_paid)
        new_loan_balance = _active_loan_balance(conn)
        new_cash = new_own + investment + new_loan_capital
        credit_limit = _effective_credit_limit(player, studio_data)
        conn.execute(
            """
            UPDATE studio_state
            SET own_capital = ?, loan_capital = ?, cash = ?,
                debt = ?, loan_balance = ?, credit_limit = ?
            WHERE id = 1
            """,
            (new_own, new_loan_capital, new_cash, new_loan_balance, new_loan_balance, credit_limit),
        )
        _record_transaction(
            conn,
            player,
            transaction_type="loan_repayment",
            amount=-paid,
            source="free_cash",
            target="lender",
            description="대출 원금을 상환했다.",
            metadata={"requestedAmount": amount},
        )
        conn.commit()
    return get_finance_state()


def project_financing_capacity(
    player: Any,
    studio: dict[str, Any],
    *,
    credit_limit: int | None = None,
    loan_balance: int | None = None,
) -> int:
    studio_data = dict(studio)
    credit_limit = _effective_credit_limit(player, studio_data) if credit_limit is None else int(credit_limit)
    loan_balance = (
        int(studio_data.get("loan_balance") or studio_data.get("debt") or 0)
        if loan_balance is None
        else int(loan_balance)
    )
    return finance_rules.project_financing_capacity(
        _player_reputation(player),
        studio_data,
        credit_limit=credit_limit,
        loan_balance=loan_balance,
    )


def validate_project_financing_capacity(
    total_cost: int,
    player: Any,
    studio: Any,
) -> None:
    studio_data = dict(studio)
    capacity = project_financing_capacity(player, studio_data)
    total_cost = int(total_cost)
    if total_cost <= capacity:
        return
    raise ValueError(
        "현재 회사 재정으로는 이 프로젝트를 감당하기 어렵습니다. "
        f"현실적 감당 한도는 약 {money(capacity)}이고, 이 프로젝트 총비용은 {money(total_cost)}입니다. "
        "투자자를 먼저 확보하거나, 대출 여력을 늘리거나, 작은 규모의 작품부터 진행해야 합니다."
    )


def reserve_project_financing(conn: Any, project_id: str, total_cost: int, player: Any, studio: Any) -> dict[str, Any]:
    _sync_studio_finance(conn)
    studio_data = dict(studio)
    current = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if current:
        studio_data = dict(current)
    total_cost = max(0, int(total_cost))
    validate_project_financing_capacity(total_cost, player, studio_data)
    investment_before = int(studio_data.get("investment_capital") or 0)
    own_before = int(studio_data.get("own_capital") or 0)
    loan_capital_before = int(studio_data.get("loan_capital") or 0)
    loan_before = int(studio_data.get("loan_balance") or studio_data.get("debt") or 0)
    credit_limit = _effective_credit_limit(player, studio_data)

    investment_used = min(investment_before, total_cost)
    remaining = total_cost - investment_used
    own_used = min(own_before, remaining)
    remaining -= own_used
    loan_capital_used = min(loan_capital_before, remaining)
    remaining -= loan_capital_used
    bridge_loan_used = max(0, remaining)
    loan_used = loan_capital_used + bridge_loan_used

    new_investment = investment_before - investment_used
    new_own = own_before - own_used
    new_loan_capital = loan_capital_before - loan_capital_used
    new_loan = loan_before + bridge_loan_used
    new_cash = new_own + new_investment + new_loan_capital
    conn.execute(
        """
        UPDATE studio_state
        SET own_capital = ?, investment_capital = ?, loan_capital = ?, cash = ?,
            debt = ?, loan_balance = ?, credit_limit = ?
        WHERE id = 1
        """,
        (new_own, new_investment, new_loan_capital, new_cash, new_loan, new_loan, credit_limit),
    )
    if bridge_loan_used:
        loan_id = f"loan_{uuid.uuid4().hex[:10]}"
        rate = _loan_interest_rate(player, studio_data, bridge=True)
        bridge_term_months = 18
        due_year, due_month = _add_months(int(player["current_year"]), int(player["current_month"]), bridge_term_months)
        next_year, next_month = _add_months(int(player["current_year"]), int(player["current_month"]), 1)
        monthly_payment = _monthly_principal_payment(bridge_loan_used, bridge_term_months)
        conn.execute(
            """
            INSERT INTO loans (
                id, lender_name, principal, remaining_principal,
                accrued_interest, annual_interest_rate, monthly_payment_amount,
                payments_made, delinquent_months, start_year, start_month,
                due_year, due_month, last_interest_year, last_interest_month,
                next_payment_year, next_payment_month, status, purpose, metadata_json
            ) VALUES (?, ?, ?, ?, 0, ?, ?, 0, 0, ?, ?, ?, ?, NULL, NULL, ?, ?, 'active', ?, ?)
            """,
            (
                loan_id,
                "브리지 금융",
                bridge_loan_used,
                bridge_loan_used,
                rate,
                monthly_payment,
                player["current_year"],
                player["current_month"],
                due_year,
                due_month,
                next_year,
                next_month,
                "프로젝트 제작비 부족분",
                dumps_json(
                    {
                        "projectId": project_id,
                        "autoBridgeLoan": True,
                        "creditLimitAtBorrow": credit_limit,
                        "termMonths": bridge_term_months,
                        "repaymentType": "monthly_principal_plus_interest",
                    }
                ),
            ),
        )
        _record_transaction(
            conn,
            player,
            transaction_type="bridge_loan",
            amount=bridge_loan_used,
            source="lender",
            target="project",
            project_id=project_id,
            loan_id=loan_id,
            description="프로젝트 부족분이 브리지 대출로 충당되었다.",
            metadata={"annualInterestRate": rate, "overCredit": new_loan > credit_limit},
        )
    if loan_capital_used:
        _record_transaction(
            conn,
            player,
            transaction_type="loan_capital_spent",
            amount=-loan_capital_used,
            source="loan_capital",
            target="project",
            project_id=project_id,
            description="대출금 미사용분을 프로젝트에 투입했다.",
        )
    if own_used:
        _record_transaction(
            conn,
            player,
            transaction_type="own_capital_spent",
            amount=-own_used,
            source="own_capital",
            target="project",
            project_id=project_id,
            description="자기자본을 프로젝트에 투입했다.",
        )
    if investment_used:
        _record_transaction(
            conn,
            player,
            transaction_type="investment_spent",
            amount=-investment_used,
            source="investment_capital",
            target="project",
            project_id=project_id,
            description="투자본을 프로젝트에 투입했다.",
        )
    contract_terms = _investment_contract_terms(
        player,
        total_cost=total_cost,
        investment_amount=investment_used,
    )
    loan_interest_estimate = _loan_interest_estimate(loan_used, player, studio_data, term_months=18)
    financing = {
        "totalCost": total_cost,
        "ownCapitalUsed": own_used,
        "investmentUsed": investment_used,
        "loanUsed": loan_used,
        "loanCapitalUsed": loan_capital_used,
        "bridgeLoanUsed": bridge_loan_used,
        "investorEquityPercent": contract_terms["equityPercent"],
        "investorProfitShare": contract_terms["profitShare"],
        "recoupmentPriority": contract_terms["recoupmentPriority"],
        "recoupmentCap": contract_terms["recoupmentCap"],
        "contractTerms": contract_terms,
        "loanInterestEstimate": loan_interest_estimate,
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO project_financing (
            project_id, total_cost, own_capital_used, investment_used,
            loan_used, investment_secured, investor_profit_share,
            investor_equity_percent, recoupment_priority, loan_interest_estimate,
            contract_terms_json, financing_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            project_id,
            total_cost,
            own_used,
            investment_used,
            loan_used,
            investment_used,
            financing["investorProfitShare"],
            financing["investorEquityPercent"],
            financing["recoupmentPriority"],
            financing["loanInterestEstimate"],
            dumps_json(contract_terms),
            dumps_json(financing),
        ),
    )
    if investment_used:
        _upsert_investment_contract(
            conn,
            project_id,
            player,
            investment_amount=investment_used,
            terms=contract_terms,
        )
    return financing


def apply_project_investment_effect(conn: Any, project_id: str, player: Any, amount: int) -> None:
    amount = int(amount or 0)
    if amount == 0:
        return
    _sync_studio_finance(conn)
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return
    studio_data = dict(studio)
    existing = conn.execute("SELECT * FROM project_financing WHERE project_id = ?", (project_id,)).fetchone()
    remaining_amount = amount
    replaced_loan = 0
    replaced_own = 0
    if amount > 0 and existing:
        financing = dict(existing)
        loan_used = int(financing.get("loan_used") or 0)
        own_used = int(financing.get("own_capital_used") or 0)
        investment_used = int(financing.get("investment_used") or 0)
        if loan_used > 0:
            planned_replaced_loan = min(loan_used, remaining_amount)
            remaining_amount -= planned_replaced_loan
            loan_used -= planned_replaced_loan
            investment_used += planned_replaced_loan
            replaced_loan = _reduce_project_loans(conn, project_id, planned_replaced_loan)
            if replaced_loan < planned_replaced_loan:
                shortfall = planned_replaced_loan - replaced_loan
                remaining_amount += shortfall
                loan_used += shortfall
                investment_used -= shortfall
        if own_used > 0 and remaining_amount > 0:
            replaced_own = min(own_used, remaining_amount)
            remaining_amount -= replaced_own
            own_used -= replaced_own
            investment_used += replaced_own
        total_cost = int(financing.get("total_cost") or 0)
        contract_terms = _investment_contract_terms(
            player,
            total_cost=total_cost,
            investment_amount=investment_used,
            additional_amount=amount,
        )
        own_capital = int(studio_data.get("own_capital") or 0) + replaced_own
        loan_capital = int(studio_data.get("loan_capital") or 0)
        investment_capital = int(studio_data.get("investment_capital") or 0) + remaining_amount
        loan_balance = max(
            0,
            int(studio_data.get("loan_balance") or studio_data.get("debt") or 0) - replaced_loan,
        )
        conn.execute(
            """
            UPDATE studio_state
            SET own_capital = ?, investment_capital = ?, loan_capital = ?, cash = ?,
                debt = ?, loan_balance = ?
            WHERE id = 1
            """,
            (
                own_capital,
                investment_capital,
                loan_capital,
                own_capital + investment_capital + loan_capital,
                loan_balance,
                loan_balance,
            ),
        )
        conn.execute(
            """
            UPDATE project_financing
            SET own_capital_used = ?, investment_used = ?, loan_used = ?,
                investment_secured = investment_secured + ?,
                investor_profit_share = ?,
                investor_equity_percent = ?,
                recoupment_priority = ?,
                contract_terms_json = ?,
                financing_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ?
            """,
            (
                own_used,
                investment_used,
                loan_used,
                amount,
                contract_terms["profitShare"],
                contract_terms["equityPercent"],
                contract_terms["recoupmentPriority"],
                dumps_json(contract_terms),
                dumps_json(
                    {
                        **loads_json(existing["financing_json"], {}),
                        "latestInvestmentEffect": amount,
                        "replacedOwnCapital": replaced_own,
                        "replacedLoan": replaced_loan,
                        "excessInvestmentCapital": remaining_amount,
                        "investorEquityPercent": contract_terms["equityPercent"],
                        "investorProfitShare": contract_terms["profitShare"],
                        "contractTerms": contract_terms,
                    }
                ),
                project_id,
            ),
        )
        _upsert_investment_contract(
            conn,
            project_id,
            player,
            investment_amount=investment_used,
            terms=contract_terms,
            additional_amount=amount,
        )
    else:
        new_investment = max(0, int(studio_data.get("investment_capital") or 0) + amount)
        new_cash = int(studio_data.get("own_capital") or 0) + new_investment + int(studio_data.get("loan_capital") or 0)
        conn.execute(
            """
            UPDATE studio_state
            SET investment_capital = ?, cash = ?
            WHERE id = 1
            """,
            (new_investment, new_cash),
        )
        if existing:
            total_cost = int(existing["total_cost"] or 0)
            investment_used = int(existing["investment_used"] or 0) + max(0, amount)
            contract_terms = _investment_contract_terms(
                player,
                total_cost=total_cost,
                investment_amount=investment_used,
                additional_amount=amount,
            )
            conn.execute(
                """
                UPDATE project_financing
                SET investment_secured = investment_secured + ?,
                    investment_used = ?,
                    investor_profit_share = ?,
                    investor_equity_percent = ?,
                    recoupment_priority = ?,
                    contract_terms_json = ?,
                    financing_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ?
                """,
                (
                    amount,
                    investment_used,
                    contract_terms["profitShare"],
                    contract_terms["equityPercent"],
                    contract_terms["recoupmentPriority"],
                    dumps_json(contract_terms),
                    dumps_json(
                        {
                            **loads_json(existing["financing_json"], {}),
                            "latestInvestmentEffect": amount,
                            "investorEquityPercent": contract_terms["equityPercent"],
                            "investorProfitShare": contract_terms["profitShare"],
                            "contractTerms": contract_terms,
                        }
                    ),
                    project_id,
                ),
            )
            _upsert_investment_contract(
                conn,
                project_id,
                player,
                investment_amount=investment_used,
                terms=contract_terms,
                additional_amount=amount,
            )
    _record_transaction(
        conn,
        player,
        transaction_type="investment_secured" if amount > 0 else "investment_withdrawn",
        amount=amount,
        source="investor",
        target="investment_capital",
        project_id=project_id,
        description="프로젝트 투자 조건이 재무 상태에 반영되었다.",
        metadata={"replacedOwnCapital": replaced_own, "replacedLoan": replaced_loan},
    )


def settlement_financing(conn: Any, project_id: str, calculated: dict[str, Any]) -> dict[str, Any]:
    financing_row = conn.execute("SELECT * FROM project_financing WHERE project_id = ?", (project_id,)).fetchone()
    receipts = int(calculated.get("studio_revenue") or 0) + int(calculated.get("secondary_market_revenue") or 0)
    talent_backend_payout = int(calculated.get("talent_backend_payout") or 0)
    if not financing_row:
        calculated["net_studio_receipts"] = max(0, receipts - talent_backend_payout)
        calculated["investor_recoup"] = 0
        calculated["own_capital_used"] = int(calculated.get("total_cost") or 0)
        calculated["investment_used"] = 0
        calculated["loan_used"] = 0
        return calculated

    financing = dict(financing_row)
    own_used = int(financing.get("own_capital_used") or 0)
    investment_used = int(financing.get("investment_used") or 0)
    loan_used = int(financing.get("loan_used") or 0)
    contract_terms = loads_json(financing.get("contract_terms_json"), {}) or loads_json(financing.get("financing_json"), {}).get("contractTerms", {})
    profit_share = float(financing.get("investor_profit_share") or contract_terms.get("profitShare") or 0)
    equity_percent = float(financing.get("investor_equity_percent") or contract_terms.get("equityPercent") or 0)
    recoupment_cap = int(contract_terms.get("recoupmentCap") or 0)
    pre_financing_profit = int(calculated.get("profit") or 0)
    investor_recoup = min(receipts, investment_used)
    if pre_financing_profit > 0 and investment_used > 0:
        investor_recoup += int(pre_financing_profit * profit_share)
    if recoupment_cap > 0:
        investor_recoup = min(investor_recoup, recoupment_cap)
    investor_recoup = min(receipts, investor_recoup)
    net_studio_receipts = max(0, receipts - investor_recoup - talent_backend_payout)
    owner_profit = net_studio_receipts - own_used - loan_used

    calculated["project_profit_before_financing"] = pre_financing_profit
    calculated["investor_recoup"] = investor_recoup
    calculated["net_studio_receipts"] = net_studio_receipts
    calculated["talent_backend_payout"] = talent_backend_payout
    calculated["own_capital_used"] = own_used
    calculated["investment_used"] = investment_used
    calculated["loan_used"] = loan_used
    calculated["investor_equity_percent"] = equity_percent
    calculated["investor_profit_share"] = profit_share
    calculated["profit"] = owner_profit
    calculated["profit_margin"] = round(owner_profit / max(1, own_used + loan_used + investment_used), 4)
    conn.execute(
        """
        UPDATE project_financing
        SET investor_recouped = ?, financing_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ?
        """,
        (investor_recoup, dumps_json({**loads_json(financing.get("financing_json"), {}), "settled": calculated}), project_id),
    )
    conn.execute(
        """
        UPDATE investment_contracts
        SET recouped_amount = ?,
            status = ?,
            contract_terms_json = ?
        WHERE project_id = ? AND status IN ('active', 'recouping')
        """,
        (
            investor_recoup,
            "settled",
            dumps_json({**contract_terms, "settled": calculated}),
            project_id,
        ),
    )
    return calculated


def add_settlement_to_own_capital(conn: Any, player: Any, project_id: str, calculated: dict[str, Any]) -> None:
    _sync_studio_finance(conn)
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return
    studio_data = dict(studio)
    receipts = int(calculated.get("net_studio_receipts") or 0)
    own_capital = int(studio_data.get("own_capital") or 0) + receipts
    investment = int(studio_data.get("investment_capital") or 0)
    loan_capital = int(studio_data.get("loan_capital") or 0)
    loan_balance = int(studio_data.get("loan_balance") or studio_data.get("debt") or 0)
    conn.execute(
        """
        UPDATE studio_state
        SET own_capital = ?, cash = ?, debt = ?, loan_balance = ?
        WHERE id = 1
        """,
        (own_capital, own_capital + investment + loan_capital, loan_balance, loan_balance),
    )
    _record_transaction(
        conn,
        player,
        transaction_type="settlement_receipts",
        amount=receipts,
        source="boxoffice_secondary_market",
        target="own_capital",
        project_id=project_id,
        description="투자자 회수분을 제외한 정산금이 자기자본에 반영되었다.",
        metadata={
            "investorRecoup": calculated.get("investor_recoup", 0),
            "projectProfitBeforeFinancing": calculated.get("project_profit_before_financing", 0),
        },
    )


def apply_studio_delta(conn: Any, studio: Any, studio_effects: dict[str, Any]) -> None:
    _sync_studio_finance(conn)
    current = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not current:
        return
    data = dict(current)
    own_delta = int(studio_effects.get("cash", 0) or 0) + int(studio_effects.get("own_capital", 0) or 0)
    investment_delta = int(studio_effects.get("investment_capital", 0) or 0)
    loan_capital_delta = int(studio_effects.get("loan_capital", 0) or 0)
    debt_delta = int(studio_effects.get("debt", 0) or 0) + int(studio_effects.get("loan_balance", 0) or 0)
    credit_limit_delta = int(studio_effects.get("credit_limit", 0) or 0)
    fame = clamp(int(data.get("fame") or 0) + int(studio_effects.get("fame", 0) or 0))
    own = max(0, int(data.get("own_capital") or 0) + own_delta)
    investment = max(0, int(data.get("investment_capital") or 0) + investment_delta)
    loan_capital = max(0, int(data.get("loan_capital") or 0) + loan_capital_delta)
    loan_balance = max(0, int(data.get("loan_balance") or data.get("debt") or 0) + debt_delta)
    credit_limit = max(0, int(data.get("credit_limit") or 0) + credit_limit_delta)
    conn.execute(
        """
        UPDATE studio_state
        SET fame = ?, own_capital = ?, investment_capital = ?, loan_capital = ?,
            cash = ?, debt = ?, loan_balance = ?, credit_limit = ?
        WHERE id = 1
        """,
        (fame, own, investment, loan_capital, own + investment + loan_capital, loan_balance, loan_balance, credit_limit),
    )
    reputation_effects = {
        key: studio_effects.get(key, 0)
        for key in (
            "field_reputation",
            "pay_reputation",
            "creative_freedom",
            "interference_reputation",
            "reputation_tags",
            "studio_reputation_tags",
        )
        if key in studio_effects
    }
    if reputation_effects:
        apply_studio_reputation_delta(conn, reputation_effects)


def add_own_capital_income(
    conn: Any,
    player: Any,
    *,
    amount: int,
    source: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    amount = max(0, int(amount))
    if amount <= 0:
        return
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return
    apply_studio_delta(conn, studio, {"own_capital": amount})
    _record_transaction(
        conn,
        player,
        transaction_type="side_job_income",
        amount=amount,
        source=source,
        target="own_capital",
        description=description,
        metadata=metadata or {},
    )


def process_monthly_finance(year: int, month: int) -> dict[str, Any]:
    with get_connection() as conn:
        _sync_studio_finance(conn)
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        loans = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE status = 'active'
            ORDER BY start_year, start_month, created_at
            """
        ).fetchall()
        summary = {
            "interestAccrued": 0,
            "principalDue": 0,
            "paid": 0,
            "shortfall": 0,
            "affectedLoans": 0,
        }
        for loan in loans:
            if int(loan["last_interest_year"] or 0) == int(year) and int(loan["last_interest_month"] or 0) == int(month):
                continue
            principal = int(loan["remaining_principal"] or 0)
            if principal <= 0 and int(loan["accrued_interest"] or 0) <= 0:
                conn.execute("UPDATE loans SET status = 'repaid' WHERE id = ?", (loan["id"],))
                continue
            monthly_interest = int(round(principal * (float(loan["annual_interest_rate"] or 0) / 100) / 12))
            scheduled_principal = _scheduled_principal_due(dict(loan), year, month)
            accrued_before = int(loan["accrued_interest"] or 0)
            due = accrued_before + monthly_interest + scheduled_principal
            paid = _pay_debt_service_from_cash(conn, due)
            interest_due = accrued_before + monthly_interest
            interest_paid = min(interest_due, paid)
            principal_paid = min(scheduled_principal, max(0, paid - interest_paid))
            next_interest = max(0, interest_due - interest_paid)
            next_principal = max(0, principal - principal_paid)
            shortfall = max(0, due - paid)
            next_year, next_month = _add_months(year, month, 1)
            delinquent = int(loan["delinquent_months"] or 0)
            if shortfall > 0:
                delinquent += 1
            else:
                delinquent = max(0, delinquent - 1)
            conn.execute(
                """
                UPDATE loans
                SET accrued_interest = ?, remaining_principal = ?,
                    payments_made = payments_made + 1,
                    delinquent_months = ?,
                    last_interest_year = ?, last_interest_month = ?,
                    next_payment_year = ?, next_payment_month = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    next_interest,
                    next_principal,
                    delinquent,
                    year,
                    month,
                    next_year,
                    next_month,
                    "repaid" if next_interest <= 0 and next_principal <= 0 else "active",
                    loan["id"],
                ),
            )
            summary["interestAccrued"] += monthly_interest
            summary["principalDue"] += scheduled_principal
            summary["paid"] += paid
            summary["shortfall"] += shortfall
            summary["affectedLoans"] += 1
            if paid > 0:
                _record_transaction(
                    conn,
                    player,
                    transaction_type="monthly_debt_service",
                    amount=-paid,
                    source="free_cash",
                    target="lender",
                    loan_id=loan["id"],
                    description="월별 대출 이자와 예정 원금 상환이 처리되었다.",
                    metadata={
                        "interestDue": interest_due,
                        "interestPaid": interest_paid,
                        "principalDue": scheduled_principal,
                        "principalPaid": principal_paid,
                    },
                )
            if shortfall > 0:
                _record_transaction(
                    conn,
                    player,
                    transaction_type="debt_service_shortfall",
                    amount=shortfall,
                    source="unpaid_debt_service",
                    target="accrued_interest",
                    loan_id=loan["id"],
                    description="월별 상환액을 모두 내지 못해 미지급 이자가 남았다.",
                    metadata={
                        "interestAccrued": monthly_interest,
                        "scheduledPrincipal": scheduled_principal,
                        "paid": paid,
                        "delinquentMonths": delinquent,
                    },
                )
        if summary["shortfall"] > 0:
            _apply_debt_pressure_effects(conn, player, summary["shortfall"])
        _sync_debt_balance_from_loans(conn)
        conn.commit()
    return summary


def _reduce_project_loans(conn: Any, project_id: str, amount: int) -> int:
    remaining = max(0, int(amount))
    reduced = 0
    if remaining <= 0:
        return 0
    rows = conn.execute(
        """
        SELECT *
        FROM loans
        WHERE status = 'active' AND remaining_principal > 0
        ORDER BY start_year, start_month, created_at
        """
    ).fetchall()
    for row in rows:
        if remaining <= 0:
            break
        metadata = loads_json(row["metadata_json"], {})
        if metadata.get("projectId") != project_id or not metadata.get("autoBridgeLoan"):
            continue
        pay = _pay_loan_row(conn, row, remaining)
        remaining -= pay
        reduced += pay
    for row in rows:
        if remaining <= 0:
            break
        metadata = loads_json(row["metadata_json"], {})
        if metadata.get("projectId") == project_id and metadata.get("autoBridgeLoan"):
            continue
        pay = _pay_loan_row(conn, row, remaining)
        remaining -= pay
        reduced += pay
    return reduced


def _pay_loan_row(conn: Any, row: Any, amount: int) -> int:
    principal = int(row["remaining_principal"] or 0)
    pay = min(principal, int(amount))
    next_remaining = principal - pay
    conn.execute(
        """
        UPDATE loans
        SET remaining_principal = ?, status = ?
        WHERE id = ?
        """,
        (next_remaining, "repaid" if next_remaining <= 0 else "active", row["id"]),
    )
    return pay


def _scheduled_principal_due(loan: dict[str, Any], year: int, month: int) -> int:
    principal = int(loan.get("remaining_principal") or 0)
    if principal <= 0:
        return 0
    due_year = loan.get("due_year")
    due_month = loan.get("due_month")
    if due_year and due_month and (int(year), int(month)) >= (int(due_year), int(due_month)):
        return principal
    monthly = int(loan.get("monthly_payment_amount") or 0)
    if monthly <= 0:
        metadata = loads_json(loan.get("metadata_json"), {})
        monthly = _monthly_principal_payment(int(loan.get("principal") or principal), int(metadata.get("termMonths") or 12))
    return min(principal, monthly)


def _pay_debt_service_from_cash(conn: Any, amount: int) -> int:
    amount = max(0, int(amount))
    if amount <= 0:
        return 0
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return 0
    data = dict(studio)
    own = int(data.get("own_capital") or 0)
    investment = int(data.get("investment_capital") or 0)
    loan_capital = int(data.get("loan_capital") or 0)
    paid_from_own = min(own, amount)
    remaining = amount - paid_from_own
    paid_from_loan_capital = min(loan_capital, remaining)
    paid = paid_from_own + paid_from_loan_capital
    if paid <= 0:
        return 0
    own -= paid_from_own
    loan_capital -= paid_from_loan_capital
    conn.execute(
        """
        UPDATE studio_state
        SET own_capital = ?, loan_capital = ?, cash = ?
        WHERE id = 1
        """,
        (own, loan_capital, own + investment + loan_capital),
    )
    return paid


def _sync_debt_balance_from_loans(conn: Any) -> None:
    balance = _active_loan_balance(conn)
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return
    data = dict(studio)
    own = int(data.get("own_capital") or 0)
    investment = int(data.get("investment_capital") or 0)
    loan_capital = int(data.get("loan_capital") or 0)
    conn.execute(
        """
        UPDATE studio_state
        SET debt = ?, loan_balance = ?, cash = ?
        WHERE id = 1
        """,
        (balance, balance, own + investment + loan_capital),
    )


def _active_loan_balance(conn: Any) -> int:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(remaining_principal), 0) AS principal,
            COALESCE(SUM(accrued_interest), 0) AS interest
        FROM loans
        WHERE status = 'active'
        """
    ).fetchone()
    if not row:
        return 0
    return int(row["principal"] or 0) + int(row["interest"] or 0)


def _apply_debt_pressure_effects(conn: Any, player: Any, shortfall: int) -> None:
    if not player:
        return
    stats = loads_json(player["stats_json"], {})
    reputation = loads_json(player["reputation_json"], {})
    pressure = max(1, min(8, int(shortfall) // 50_000_000 + 1))
    stats["financial_risk"] = clamp(float(stats.get("financial_risk", 0)) + pressure)
    stats["game_over_risk"] = clamp(float(stats.get("game_over_risk", 0)) + max(1, pressure // 2))
    reputation["investor_reputation"] = clamp(float(reputation.get("investor_reputation", 10)) - max(1, pressure // 2))
    conn.execute(
        """
        UPDATE player_state
        SET stats_json = ?, reputation_json = ?
        WHERE id = 1
        """,
        (dumps_json(stats), dumps_json(reputation)),
    )


def _sync_studio_finance(conn: Any) -> None:
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    if not studio:
        return
    data = dict(studio)
    own = int(data.get("own_capital") or 0)
    investment = int(data.get("investment_capital") or 0)
    loan_capital = int(data.get("loan_capital") or 0)
    cash = int(data.get("cash") or 0)
    debt = int(data.get("debt") or 0)
    loan = int(data.get("loan_balance") or 0)
    if own == 0 and investment == 0 and loan_capital == 0 and cash > 0:
        own = cash
    if loan == 0 and debt > 0:
        loan = debt
    conn.execute(
        """
        UPDATE studio_state
        SET own_capital = ?, investment_capital = ?, loan_capital = ?, cash = ?,
            debt = ?, loan_balance = ?
        WHERE id = 1
        """,
        (own, investment, loan_capital, own + investment + loan_capital, loan, loan),
    )


def _player_reputation(player: Any) -> dict[str, Any]:
    return loads_json(player["reputation_json"], {}) if player else {}


def _effective_credit_limit(player: Any, studio: dict[str, Any]) -> int:
    return finance_rules.effective_credit_limit(_player_reputation(player), studio)


def _loan_interest_rate(player: Any, studio: dict[str, Any], *, bridge: bool = False) -> float:
    return finance_rules.loan_interest_rate(_player_reputation(player), studio, bridge=bridge)


def _monthly_principal_payment(amount: int, term_months: int) -> int:
    return finance_rules.monthly_principal_payment(amount, term_months)


def _loan_interest_estimate(amount: int, player: Any, studio: dict[str, Any], *, term_months: int) -> int:
    rate = _loan_interest_rate(player, studio, bridge=True)
    return finance_rules.loan_interest_estimate(amount, rate, term_months=term_months)


def _investment_contract_terms(
    player: Any,
    *,
    total_cost: int,
    investment_amount: int,
    additional_amount: int = 0,
) -> dict[str, Any]:
    return finance_rules.investment_contract_terms(
        _player_reputation(player),
        total_cost=total_cost,
        investment_amount=investment_amount,
        additional_amount=additional_amount,
    )


def _upsert_investment_contract(
    conn: Any,
    project_id: str,
    player: Any,
    *,
    investment_amount: int,
    terms: dict[str, Any],
    additional_amount: int = 0,
) -> None:
    existing = conn.execute(
        """
        SELECT *
        FROM investment_contracts
        WHERE project_id = ? AND status IN ('active', 'recouping')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE investment_contracts
            SET investor_name = ?, investment_amount = ?, equity_percent = ?,
                profit_share = ?, recoupment_priority = ?, recoupment_cap = ?,
                contract_terms_json = ?
            WHERE id = ?
            """,
            (
                terms.get("investorName"),
                int(investment_amount),
                float(terms.get("equityPercent") or 0),
                float(terms.get("profitShare") or 0),
                terms.get("recoupmentPriority") or DEFAULT_RECOUPMENT_PRIORITY,
                int(terms.get("recoupmentCap") or 0),
                dumps_json(terms),
                existing["id"],
            ),
        )
        return
    conn.execute(
        """
        INSERT INTO investment_contracts (
            id, project_id, investor_name, investment_amount,
            equity_percent, profit_share, recoupment_priority,
            recoupment_cap, status, signed_year, signed_month,
            signed_day, contract_terms_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            f"invest_{uuid.uuid4().hex[:10]}",
            project_id,
            terms.get("investorName"),
            int(investment_amount),
            float(terms.get("equityPercent") or 0),
            float(terms.get("profitShare") or 0),
            terms.get("recoupmentPriority") or DEFAULT_RECOUPMENT_PRIORITY,
            int(terms.get("recoupmentCap") or 0),
            player["current_year"] if player else None,
            player["current_month"] if player else None,
            player["current_day"] if player and "current_day" in player.keys() else 1,
            dumps_json({**terms, "additionalAmount": int(additional_amount or 0)}),
        ),
    )


def _lender_name(studio: dict[str, Any]) -> str:
    if int(studio.get("fame") or 0) >= 50:
        return "메이저 금융권"
    return "제작금융 대출"


def _add_months(year: int, month: int, delta_months: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta_months
    return index // 12, index % 12 + 1


def _record_transaction(
    conn: Any,
    player: Any,
    *,
    transaction_type: str,
    amount: int,
    source: str | None = None,
    target: str | None = None,
    project_id: str | None = None,
    loan_id: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO finance_transactions (
            year, month, day, transaction_type, amount, source, target,
            project_id, loan_id, description, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            player["current_year"] if player else None,
            player["current_month"] if player else None,
            player["current_day"] if player and "current_day" in player.keys() else 1,
            transaction_type,
            int(amount),
            source,
            target,
            project_id,
            loan_id,
            description,
            dumps_json(metadata or {}),
        ),
    )


def _loan_from_row(row: dict[str, Any]) -> dict[str, Any]:
    remaining_principal = int(row.get("remaining_principal") or 0)
    accrued_interest = int(row.get("accrued_interest") or 0)
    monthly_due = _scheduled_principal_due(row, int(row.get("next_payment_year") or row.get("due_year") or 0), int(row.get("next_payment_month") or row.get("due_month") or 1))
    monthly_interest = int(round(remaining_principal * (float(row.get("annual_interest_rate") or 0) / 100) / 12))
    return {
        "id": row["id"],
        "lenderName": row.get("lender_name") or "대출기관",
        "principal": int(row.get("principal") or 0),
        "remainingPrincipal": remaining_principal,
        "accruedInterest": accrued_interest,
        "annualInterestRate": float(row.get("annual_interest_rate") or 0),
        "monthlyPaymentAmount": int(row.get("monthly_payment_amount") or 0),
        "nextMonthlyDue": accrued_interest + monthly_interest + monthly_due,
        "delinquentMonths": int(row.get("delinquent_months") or 0),
        "start": f"{row.get('start_year')}년 {row.get('start_month')}월",
        "due": f"{row.get('due_year')}년 {row.get('due_month')}월" if row.get("due_year") else "만기 미정",
        "nextPayment": (
            f"{row.get('next_payment_year')}년 {row.get('next_payment_month')}월"
            if row.get("next_payment_year") and row.get("next_payment_month")
            else "다음 월"
        ),
        "purpose": row.get("purpose") or "",
        "status": row.get("status") or "active",
    }


def _investment_contract_from_row(row: dict[str, Any]) -> dict[str, Any]:
    terms = loads_json(row.get("contract_terms_json"), {})
    return {
        "id": row["id"],
        "projectId": row.get("project_id"),
        "projectTitle": row.get("project_title") or row.get("project_id") or "프로젝트",
        "investorName": row.get("investor_name") or terms.get("investorName") or "투자자",
        "investmentAmount": int(row.get("investment_amount") or 0),
        "equityPercent": float(row.get("equity_percent") or 0),
        "profitShare": float(row.get("profit_share") or 0),
        "recoupmentPriority": row.get("recoupment_priority") or DEFAULT_RECOUPMENT_PRIORITY,
        "recoupmentCap": int(row.get("recoupment_cap") or 0),
        "recoupedAmount": int(row.get("recouped_amount") or 0),
        "status": row.get("status") or "active",
        "summary": terms.get("summary") or "투자금 우선 회수 후 계약 지분에 따라 수익을 배분한다.",
    }


def _monthly_debt_pressure(loans: list[dict[str, Any]]) -> dict[str, Any]:
    next_due = 0
    overdue_interest = 0
    delinquent = 0
    for loan in loans:
        row = _loan_from_row(loan)
        next_due += int(row["nextMonthlyDue"])
        overdue_interest += int(row["accruedInterest"])
        delinquent += int(row["delinquentMonths"])
    if delinquent >= 3:
        label = "위험"
    elif overdue_interest > 0:
        label = "주의"
    elif next_due > 0:
        label = "정상 상환 중"
    else:
        label = "대출 압박 없음"
    return {
        "nextDue": next_due,
        "overdueInterest": overdue_interest,
        "delinquentMonths": delinquent,
        "label": label,
    }


def _transaction_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": f"{row.get('year') or '-'}년 {row.get('month') or '-'}월 {row.get('day') or 1}일",
        "transactionType": row.get("transaction_type"),
        "amount": int(row.get("amount") or 0),
        "description": row.get("description") or "",
        "projectId": row.get("project_id"),
        "loanId": row.get("loan_id"),
    }


def _project_cashflow_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectTitle": row.get("project_title") or row.get("project_id") or "프로젝트",
        "date": _date_label(row.get("planned_year"), row.get("planned_month"), row.get("planned_day")),
        "paidDate": _date_label(row.get("paid_year"), row.get("paid_month"), row.get("paid_day")),
        "stage": row.get("planned_stage") or "-",
        "amount": int(row.get("amount") or 0),
        "source": row.get("source") or "-",
        "target": row.get("target") or "-",
        "cashflowType": row.get("cashflow_type") or "-",
        "status": row.get("status") or "planned",
        "description": row.get("description") or "",
    }


def _date_label(year: Any, month: Any, day: Any) -> str:
    if not year or not month:
        return "미정"
    day_value = int(day or 1)
    return f"{int(year)}.{int(month):02d}.{day_value:02d}"


def _finance_summary(studio: dict[str, Any], credit_limit: int, loan_balance: int) -> str:
    own = int(studio.get("own_capital") or 0)
    investment = int(studio.get("investment_capital") or 0)
    loan_capital = int(studio.get("loan_capital") or 0)
    available_credit = max(0, credit_limit - loan_balance)
    if loan_balance > credit_limit:
        return "대출잔액이 신용한도를 넘어섰다. 다음 작품보다 상환과 리스크 관리가 먼저다."
    if loan_capital > own and loan_capital > investment:
        return "가용 현금 중 대출금 비중이 높다. 제작 실패 시 부채 압박이 빠르게 커질 수 있다."
    if investment > own:
        return "현재 제작 여력은 자기자본보다 투자본에 더 크게 의존하고 있다."
    if available_credit >= own:
        return "추가 차입 여지는 있지만, 실패 시 부채 압박이 커질 수 있다."
    return "자기자본 중심으로 비교적 안정적으로 움직일 수 있는 상태다."
