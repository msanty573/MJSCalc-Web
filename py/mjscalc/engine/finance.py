"""Loan and financial math.

Conventions
-----------
* Rates are given as *annual percentages* (e.g. ``6.5`` for 6.5 %) in the
  public helpers, and converted to a periodic decimal internally.
* The time-value-of-money (TVM) functions use the standard cash-flow sign
  convention used by financial calculators: money you receive is positive,
  money you pay out is negative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date


class FinanceError(ValueError):
    pass


# --------------------------------------------------------------------------
# Loans
# --------------------------------------------------------------------------

def periodic_payment(principal: float, annual_rate_pct: float, n_periods: int,
                     periods_per_year: int = 12) -> float:
    """Level payment that pays off ``principal`` in ``n_periods``."""
    if principal <= 0:
        raise FinanceError("Loan amount must be greater than zero")
    if n_periods <= 0:
        raise FinanceError("Term must be greater than zero")
    if annual_rate_pct < 0:
        raise FinanceError("Interest rate cannot be negative")
    r = annual_rate_pct / 100 / periods_per_year
    if r == 0:
        return principal / n_periods
    return principal * r / (1 - (1 + r) ** -n_periods)


@dataclass
class AmortizationRow:
    period: int
    date: date | None
    payment: float
    principal: float
    interest: float
    extra: float
    balance: float


@dataclass
class LoanResult:
    payment: float                 # scheduled payment (excluding extra)
    n_periods: int                 # actual number of payments made
    total_paid: float
    total_interest: float
    schedule: list[AmortizationRow] = field(default_factory=list)
    baseline_interest: float = 0.0  # interest without extra payments
    baseline_periods: int = 0

    @property
    def interest_saved(self) -> float:
        return max(0.0, self.baseline_interest - self.total_interest)

    @property
    def periods_saved(self) -> int:
        return max(0, self.baseline_periods - self.n_periods)

    @property
    def payoff_date(self) -> date | None:
        return self.schedule[-1].date if self.schedule else None


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    days_in_month = [31, 29 if _leap(year) else 28, 31, 30, 31, 30,
                     31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, days_in_month))


def _leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _period_date(start: date | None, k: int, periods_per_year: int) -> date | None:
    if start is None:
        return None
    if 12 % periods_per_year == 0:
        return _add_months(start, k * (12 // periods_per_year))
    from datetime import timedelta
    if 52 % periods_per_year == 0:  # weekly / bi-weekly
        return start + timedelta(weeks=k * (52 // periods_per_year))
    return start + timedelta(days=round(k * 365.25 / periods_per_year))


def amortize(principal: float, annual_rate_pct: float, n_periods: int,
             periods_per_year: int = 12, extra_payment: float = 0.0,
             start: date | None = None, lump_sums: dict[int, float] | None = None,
             ) -> LoanResult:
    """Full amortization schedule, with optional extra payments.

    ``extra_payment`` is added to every payment; ``lump_sums`` maps a period
    number (1-based) to a one-time additional payment.
    """
    if extra_payment < 0:
        raise FinanceError("Extra payment cannot be negative")
    pmt = periodic_payment(principal, annual_rate_pct, n_periods, periods_per_year)
    r = annual_rate_pct / 100 / periods_per_year
    lump_sums = lump_sums or {}

    rows: list[AmortizationRow] = []
    balance = principal
    total_interest = 0.0
    k = 0
    while balance > 0.005 and k < n_periods:
        k += 1
        interest = balance * r
        scheduled_principal = min(pmt - interest, balance)
        extra = min(extra_payment + lump_sums.get(k, 0.0), balance - scheduled_principal)
        principal_paid = scheduled_principal + extra
        balance -= principal_paid
        if balance < 0.005:
            balance = 0.0
        total_interest += interest
        rows.append(AmortizationRow(
            period=k, date=_period_date(start, k - 1, periods_per_year),
            payment=interest + scheduled_principal, principal=scheduled_principal,
            interest=interest, extra=extra, balance=balance,
        ))

    baseline_interest = pmt * n_periods - principal
    return LoanResult(
        payment=pmt,
        n_periods=len(rows),
        total_paid=principal + total_interest,
        total_interest=total_interest,
        schedule=rows,
        baseline_interest=baseline_interest,
        baseline_periods=n_periods,
    )


def affordable_principal(payment: float, annual_rate_pct: float, n_periods: int,
                         periods_per_year: int = 12) -> float:
    """How much can be borrowed for a given payment."""
    r = annual_rate_pct / 100 / periods_per_year
    if r == 0:
        return payment * n_periods
    return payment * (1 - (1 + r) ** -n_periods) / r


# --------------------------------------------------------------------------
# Time value of money
# --------------------------------------------------------------------------

def _tvm_residual(n: float, i: float, pv: float, pmt: float, fv: float,
                  begin: bool) -> float:
    """pv*(1+i)^n + pmt*(1+i*b)*((1+i)^n - 1)/i + fv  (should equal 0)."""
    b = 1.0 if begin else 0.0
    if i == 0:
        return pv + pmt * n + fv
    g = (1 + i) ** n
    return pv * g + pmt * (1 + i * b) * (g - 1) / i + fv


def solve_tvm(*, n: float | None = None, rate_pct: float | None = None,
              pv: float | None = None, pmt: float | None = None,
              fv: float | None = None, periods_per_year: int = 12,
              begin: bool = False) -> dict[str, float]:
    """Solve for exactly one missing TVM variable.

    ``n`` is the number of periods; ``rate_pct`` is the *annual* rate in
    percent (compounded ``periods_per_year`` times per year).
    Returns all five values.
    """
    values = {"n": n, "rate_pct": rate_pct, "pv": pv, "pmt": pmt, "fv": fv}
    missing = [k for k, v in values.items() if v is None]
    if len(missing) != 1:
        raise FinanceError("Leave exactly one field blank to solve for it")
    target = missing[0]
    b = 1.0 if begin else 0.0

    if target != "rate_pct":
        i = rate_pct / 100 / periods_per_year
    if target == "fv":
        fv = -_tvm_residual(n, i, pv, pmt, 0.0, begin)
    elif target == "pv":
        g = (1 + i) ** n
        annuity = n if i == 0 else (1 + i * b) * (g - 1) / i
        pv = -(pmt * annuity + fv) / g
    elif target == "pmt":
        g = (1 + i) ** n
        annuity = n if i == 0 else (1 + i * b) * (g - 1) / i
        if annuity == 0:
            raise FinanceError("Number of periods must be greater than zero")
        pmt = -(pv * g + fv) / annuity
    elif target == "n":
        if i == 0:
            if pmt == 0:
                raise FinanceError("No solution: payment and rate are both zero")
            n = -(pv + fv) / pmt
        else:
            c = pmt * (1 + i * b) / i
            num, den = c - fv, pv + c
            if den == 0 or num / den <= 0:
                raise FinanceError("No solution — check the signs of PV, PMT and FV")
            n = math.log(num / den) / math.log(1 + i)
    elif target == "rate_pct":
        i = _solve_rate(n, pv, pmt, fv, begin)
        rate_pct = i * periods_per_year * 100

    return {"n": n, "rate_pct": rate_pct, "pv": pv, "pmt": pmt, "fv": fv}


def _solve_rate(n: float, pv: float, pmt: float, fv: float, begin: bool) -> float:
    if n <= 0:
        raise FinanceError("Number of periods must be greater than zero")
    f = lambda i: _tvm_residual(n, i, pv, pmt, fv, begin)  # noqa: E731
    # Scan for a sign change, then bisect — robust for all sign conventions.
    grid = [-0.99, -0.5, -0.1, -0.01, -1e-6, 1e-6, 0.001, 0.005, 0.01, 0.02,
            0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    prev_x, prev_y = None, None
    for x in grid:
        try:
            y = f(x)
        except OverflowError:
            continue
        if y == 0:
            return x
        if prev_y is not None and (prev_y < 0) != (y < 0):
            return _bisect(f, prev_x, x)
        prev_x, prev_y = x, y
    raise FinanceError("Could not find an interest rate — check the signs of PV, PMT and FV")


def _bisect(f, lo: float, hi: float, tol: float = 1e-12, iters: int = 300) -> float:
    flo = f(lo)
    for _ in range(iters):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < tol or (hi - lo) / 2 < tol:
            return mid
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


# --------------------------------------------------------------------------
# Investments & cash flows
# --------------------------------------------------------------------------

@dataclass
class GrowthRow:
    year: int
    contributions: float  # cumulative, including initial deposit
    interest: float       # cumulative interest earned
    balance: float


def investment_growth(initial: float, annual_rate_pct: float, years: int,
                      contribution: float = 0.0, contributions_per_year: int = 12,
                      compounds_per_year: int = 12, contribution_growth_pct: float = 0.0,
                      ) -> list[GrowthRow]:
    """Year-by-year growth of a savings / investment account.

    Contributions are made at the end of each contribution period; the
    contribution amount can grow each year (e.g. with salary raises).
    """
    if years <= 0:
        raise FinanceError("Years must be greater than zero")
    # Effective rate per contribution period, from the compounding frequency.
    eff_annual = (1 + annual_rate_pct / 100 / compounds_per_year) ** compounds_per_year - 1
    r = (1 + eff_annual) ** (1 / contributions_per_year) - 1
    balance = initial
    paid_in = initial
    rows = []
    c = contribution
    for year in range(1, years + 1):
        for _ in range(contributions_per_year):
            balance = balance * (1 + r) + c
            paid_in += c
        rows.append(GrowthRow(year, paid_in, balance - paid_in, balance))
        c *= 1 + contribution_growth_pct / 100
    return rows


def npv(rate_pct: float, cash_flows: list[float]) -> float:
    """Net present value; ``cash_flows[0]`` occurs now (t = 0)."""
    r = rate_pct / 100
    return sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list[float]) -> float:
    """Internal rate of return, in percent."""
    if not any(cf < 0 for cf in cash_flows) or not any(cf > 0 for cf in cash_flows):
        raise FinanceError("Cash flows need at least one negative and one positive value")
    f = lambda r: sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows))  # noqa: E731
    grid = [-0.99, -0.9, -0.5, -0.2, -0.05, 0.0, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 100]
    prev = None
    for x in grid:
        y = f(x)
        if y == 0:
            return x * 100
        if prev is not None and (prev[1] < 0) != (y < 0):
            return _bisect(f, prev[0], x) * 100
        prev = (x, y)
    raise FinanceError("Could not find an IRR for these cash flows")


def payback_period(cash_flows: list[float]) -> float | None:
    """Periods until cumulative cash flow turns non-negative (interpolated)."""
    cumulative = 0.0
    for t, cf in enumerate(cash_flows):
        prev = cumulative
        cumulative += cf
        if cumulative >= 0 and t > 0 and prev < 0:
            return t - 1 + (-prev / cf if cf else 0)
    return None


def effective_annual_rate(nominal_pct: float, compounds_per_year: int) -> float:
    return ((1 + nominal_pct / 100 / compounds_per_year) ** compounds_per_year - 1) * 100


def rule_of_72(rate_pct: float) -> float:
    """Exact years to double at the given annual rate (compounded annually)."""
    if rate_pct <= 0:
        raise FinanceError("Rate must be positive")
    return math.log(2) / math.log(1 + rate_pct / 100)
