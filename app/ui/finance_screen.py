from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.game_state import money


class FinanceScreen(QWidget):
    def __init__(
        self,
        *,
        state: dict[str, Any],
        on_borrow: Callable[[int, int], None],
        on_repay: Callable[[int], None],
        on_back: Callable[[], None],
    ) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("재무/대출")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        summary = QLabel(state.get("finance_summary", "재무 상태를 불러오는 중입니다."))
        summary.setWordWrap(True)
        summary.setObjectName("PanelText")
        layout.addWidget(summary)

        grid_box = QGroupBox("자금 구조")
        grid = QGridLayout(grid_box)
        pressure = state.get("monthly_debt_pressure", {})
        rows = [
            ("자기자본", money(state.get("own_capital", 0))),
            ("투자본 잔액", money(state.get("investment_capital", 0))),
            ("대출금 미사용", money(state.get("loan_capital", 0))),
            ("가용 현금", money(state.get("cash", 0))),
            ("대출잔액", money(state.get("loan_balance", 0))),
            ("신용한도", money(state.get("credit_limit", 0))),
            ("추가 대출 가능", money(state.get("available_credit", 0))),
            ("현실적 단일 프로젝트 감당 한도", money(state.get("project_financing_capacity", 0))),
            ("다음 월 상환 압박", f"{money(pressure.get('nextDue', 0))} · {pressure.get('label', '대출 압박 없음')}"),
            ("미지급 이자", money(pressure.get("overdueInterest", 0))),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index, 0)
            grid.addWidget(QLabel(value), index, 1)
        layout.addWidget(grid_box)

        control_box = QGroupBox("대출 실행/상환")
        control_grid = QGridLayout(control_box)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(1)
        self.amount_input.setSuffix("억 원")
        max_reference = max(
            int(state.get("available_credit", 0) or 0),
            int(state.get("own_capital", 0) or 0),
            int(state.get("loan_capital", 0) or 0),
            int(state.get("loan_balance", 0) or 0),
        )
        self.amount_input.setRange(0.1, max(0.1, float(max_reference) / 100_000_000))
        self.amount_input.setSingleStep(0.5)
        self.amount_input.setValue(min(1.0, self.amount_input.maximum()))
        self.term_input = QSpinBox()
        self.term_input.setRange(1, 60)
        self.term_input.setSuffix("개월")
        self.term_input.setValue(12)
        borrow_button = QPushButton("대출 실행")
        repay_button = QPushButton("대출 상환")
        borrow_button.clicked.connect(lambda: on_borrow(_amount_to_won(self.amount_input.value()), self.term_input.value()))
        repay_button.clicked.connect(lambda: on_repay(_amount_to_won(self.amount_input.value())))
        if int(state.get("available_credit", 0) or 0) <= 0:
            borrow_button.setEnabled(False)
        if int(state.get("loan_balance", 0) or 0) <= 0 or (
            int(state.get("own_capital", 0) or 0) + int(state.get("loan_capital", 0) or 0)
        ) <= 0:
            repay_button.setEnabled(False)

        control_grid.addWidget(QLabel("금액"), 0, 0)
        control_grid.addWidget(self.amount_input, 0, 1)
        control_grid.addWidget(QLabel("기간"), 1, 0)
        control_grid.addWidget(self.term_input, 1, 1)
        control_grid.addWidget(borrow_button, 2, 0)
        control_grid.addWidget(repay_button, 2, 1)
        layout.addWidget(control_box)

        loans_box = QGroupBox("활성 대출")
        loans_layout = QVBoxLayout(loans_box)
        loans_list = QListWidget()
        for loan in state.get("active_loans", []):
            loans_list.addItem(
                f"{loan['lenderName']} · {money(loan['remainingPrincipal'])} · "
                f"미지급 이자 {money(loan.get('accruedInterest', 0))} · "
                f"다음 월 {money(loan.get('nextMonthlyDue', 0))} · "
                f"연 {loan['annualInterestRate']:.2f}% · 만기 {loan['due']} · {loan['purpose']}"
            )
        if not state.get("active_loans"):
            loans_list.addItem("활성 대출 없음")
        loans_layout.addWidget(loans_list)
        layout.addWidget(loans_box)

        contracts_box = QGroupBox("투자 계약")
        contracts_layout = QVBoxLayout(contracts_box)
        contracts_list = QListWidget()
        for contract in state.get("investment_contracts", []):
            contracts_list.addItem(
                f"{contract['projectTitle']} · {contract['investorName']} · "
                f"투자 {money(contract['investmentAmount'])} · "
                f"지분 {contract['equityPercent']:.1f}% · "
                f"초과수익 배분 {contract['profitShare'] * 100:.1f}%"
            )
        if not state.get("investment_contracts"):
            contracts_list.addItem("활성 투자 계약 없음")
        contracts_layout.addWidget(contracts_list)
        layout.addWidget(contracts_box)

        cashflow_box = QGroupBox("프로젝트 현금흐름/집행 일정")
        cashflow_layout = QVBoxLayout(cashflow_box)
        cashflow_list = QListWidget()
        for flow in state.get("project_cashflows", []):
            status = "집행" if flow.get("status") == "paid" else "예정"
            paid = f" · 집행일 {flow.get('paidDate')}" if flow.get("paidDate") and flow.get("paidDate") != "미정" else ""
            cashflow_list.addItem(
                f"{status} · {flow['date']} · {flow['projectTitle']} · "
                f"{money(flow['amount'])} · {flow['description']}{paid}"
            )
        if not state.get("project_cashflows"):
            cashflow_list.addItem("예정된 프로젝트 현금흐름 없음")
        cashflow_layout.addWidget(cashflow_list)
        layout.addWidget(cashflow_box)

        tx_box = QGroupBox("최근 자금 흐름")
        tx_layout = QVBoxLayout(tx_box)
        tx_list = QListWidget()
        for tx in state.get("transactions", []):
            tx_list.addItem(f"{tx['date']} · {tx['transactionType']} · {money(tx['amount'])} · {tx['description']}")
        if not state.get("transactions"):
            tx_list.addItem("기록된 자금 흐름 없음")
        tx_layout.addWidget(tx_list)
        layout.addWidget(tx_box)

        back_button = QPushButton("대시보드로")
        back_button.setMinimumHeight(40)
        back_button.clicked.connect(on_back)
        layout.addWidget(back_button)


def _amount_to_won(value: float) -> int:
    return int(round(value * 100_000_000))
