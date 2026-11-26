"""Bridge between the browser demo (web/app.js) and MJSCalc's own engine.

Runs inside Pyodide. Every function takes and returns plain JSON-friendly values
(numbers, strings, lists, dicts) so app.js can call it through ``toJs``. The
calculations are the desktop app's: ``mjscalc.engine.expression``, ``finance``,
``units`` and ``graph``, copied in unchanged by ``packaging/build_web.py``.
"""

from __future__ import annotations

import math
from datetime import date

from mjscalc.engine import finance, units
from mjscalc.engine import graph as gr
from mjscalc.engine.expression import (
    CONSTANT_DESCRIPTIONS, CONSTANTS, CalcError, Calculator, FUNCTION_DESCRIPTIONS,
    format_number,
)

# ------------------------------------------------------------------ Calculator

_calc = Calculator(angle_mode="deg")


def calc_eval(text: str, angle: str, mode: str, store: bool) -> dict:
    _calc.angle_mode = angle
    try:
        value = _calc.evaluate(text, store=store)
    except CalcError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "value": value, "shown": format_number(value, mode=mode)}


def fmt(value: float, mode: str = "auto", precision: int = 12) -> str:
    return format_number(value, precision, mode)


def calc_restore(entries: list) -> None:
    """Reload ans from the saved history (newest first)."""
    if entries:
        try:
            _calc.variables["ans"] = float(entries[0]["value"])
        except (KeyError, TypeError, ValueError, AttributeError):
            pass


def calc_catalog() -> dict:
    return {
        "constants": [[n, d, format_number(CONSTANTS[n], 8)]
                      for n, d in CONSTANT_DESCRIPTIONS.items()],
        "functions": sorted([[n, d] for n, d in FUNCTION_DESCRIPTIONS.items()],
                            key=lambda i: i[0].lower()),
        "descriptions": dict(FUNCTION_DESCRIPTIONS),
    }


# ------------------------------------------------------------------ Loans

def _money(x: float, sym: str = "$", decimals: int = 2) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}{sym}{abs(x):,.{decimals}f}"


def loan(p: dict) -> dict:
    """Same steps as LoanPage.recalc in the desktop app."""
    ppy = int(p["ppy"])
    months = int(p["term"]) * (12 if p["term_unit"] == "years" else 1)
    n = max(1, round(months / 12 * ppy))
    sym = p.get("currency", "$")
    try:
        if p["mode"] == "borrow":
            principal = max(0.0, finance.affordable_principal(
                float(p["budget"]), float(p["rate"]), n, ppy))
        else:
            principal = float(p["amount"]) - float(p["down"])
        y, m, d = (int(v) for v in p["start"].split("-"))
        r = finance.amortize(principal, float(p["rate"]), n, ppy,
                             extra_payment=float(p["extra"]), start=date(y, m, d))
    except (finance.FinanceError, ValueError, KeyError) as exc:
        return {"ok": False, "error": str(exc)}

    extra = float(p["extra"])
    saved = ""
    if extra > 0 and r.interest_saved > 0:
        yrs, rem = divmod(r.periods_saved, ppy)
        span = []
        if yrs:
            span.append(f"{yrs} year{'s' * (yrs != 1)}")
        if rem:
            span.append(f"{rem} payment{'s' * (rem != 1)}")
        saved = (f"✓ Extra payments save {_money(r.interest_saved, sym)} in interest and pay "
                 f"the loan off {' and '.join(span) or 'slightly'} early.")

    every = [[str(row.period), row.date.strftime("%b %d, %Y") if row.date else "",
              _money(row.principal, sym), _money(row.interest, sym), _money(row.extra, sym),
              _money(row.balance, sym)] for row in r.schedule]
    by_year: dict[int, list] = {}
    for row in r.schedule:
        by_year.setdefault(row.date.year, []).append(row)
    yearly = [[str(year), str(len(items)),
               _money(sum(i.principal for i in items), sym),
               _money(sum(i.interest for i in items), sym),
               _money(sum(i.extra for i in items), sym),
               _money(items[-1].balance, sym)] for year, items in by_year.items()]
    return {
        "ok": True,
        "payment": _money(r.payment + extra, sym),
        "interest": _money(r.total_interest, sym),
        "total": _money(r.total_paid, sym),
        "principal": _money(principal, sym),
        "payoff": r.payoff_date.strftime("%b %Y") if r.payoff_date else "—",
        "count": f"{r.n_periods:,}",
        "principal_value": principal,
        "interest_value": r.total_interest,
        "saved": saved,
        "yearly": yearly,
        "every": every,
    }


# ------------------------------------------------------------------ Converter

_conv_calc = Calculator()


def _read(text: str):
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return _conv_calc.evaluate(text, store=False)
    except CalcError:
        return None


def unit_catalog() -> dict:
    return {"categories": list(units.UNITS), "units": {c: list(u) for c, u in units.UNITS.items()},
            "bases": list(units.BASES.items())}


def convert(text: str, cat: str, src: str, dst: str) -> dict:
    """Same as ConverterPage._convert: the value in the other box, a formula line and
    every unit of the category."""
    v = _read(text)
    if v is None:
        return {"ok": False}
    try:
        out = units.convert(v, cat, src, dst)
    except ZeroDivisionError:
        return {"ok": False}
    one = None
    if cat not in ("Temperature", "Fuel economy") and v != 1:
        try:
            one = units.convert(1, cat, src, dst)
        except ZeroDivisionError:
            one = None
    formula = f"{format_number(v)} {src} = {format_number(out)} {dst}"
    if one is not None:
        formula += f"     ·     1 {src} = {format_number(one)} {dst}"
    rows = []
    for name in units.UNITS[cat]:
        try:
            rows.append([name, format_number(units.convert(v, cat, src, name))])
        except ZeroDivisionError:
            rows.append([name, "—"])
    return {"ok": True, "value": format_number(out, 10).replace(",", ""),
            "formula": formula, "rows": rows}


def base_convert(text: str, base: int) -> dict:
    try:
        n = units.parse_int(text, base) if text.strip() else None
    except ValueError:
        return {"ok": False, "info": "Not a valid number in this base"}
    if n is None:
        return {"ok": True, "values": {str(b): "" for b in units.BASES.values()}, "info": ""}
    bits = max(1, n.bit_length())
    info = (f"{bits} bit{'s' * (bits != 1)} · fits in "
            f"{next(w for w in (8, 16, 32, 64, 128, 1 << 20) if bits <= w)}-bit unsigned"
            if n >= 0 else "Negative number")
    return {"ok": True, "values": {str(b): units.format_int(n, b) for b in units.BASES.values()},
            "info": info}


# ------------------------------------------------------------------ Graph

_compiled: dict[str, gr.Compiled] = {}


def _get(text: str, angle: str) -> gr.Compiled:
    key = f"{angle}|{text}"
    c = _compiled.get(key)
    if c is None:
        c = gr.compile_expr(text, angle)
        if len(_compiled) > 200:
            _compiled.clear()
        _compiled[key] = c
    return c


def graph_check(texts: list, angle: str) -> list:
    """For each function: {"ok", "error", "params"}."""
    out = []
    for t in texts:
        if not (t or "").strip():
            out.append({"ok": False, "error": "", "params": []})
            continue
        try:
            c = _get(t, angle)
            out.append({"ok": True, "error": "", "params": list(c.params)})
        except gr.GraphError as exc:
            out.append({"ok": False, "error": str(exc), "params": []})
    return out


def _nan_to_none(y: float):
    return None if math.isnan(y) else y


def graph_sample(texts: list, angle: str, params: dict, x0: float, x1: float, n: int) -> list:
    """y values at n+1 evenly spaced x for each function (None where undefined)."""
    out = []
    for t in texts:
        try:
            c = _get(t, angle)
        except gr.GraphError:
            out.append([])
            continue
        step = (x1 - x0) / n
        out.append([_nan_to_none(c(x0 + i * step, params)) for i in range(n + 1)])
    return out


def graph_eval(texts: list, angle: str, params: dict, x: float) -> list:
    """Each function's value and slope at x (for tracing)."""
    out = []
    for t in texts:
        try:
            c = _get(t, angle)
        except gr.GraphError:
            out.append(None)
            continue
        f = lambda v, c=c: c(v, params)  # noqa: E731
        y = f(x)
        out.append(None if math.isnan(y) else [y, _nan_to_none(gr.slope(f, x))])
    return out


def graph_points(curves: list, angle: str, params: dict, x0: float, x1: float,
                 y0: float, y1: float) -> list:
    """Roots, peaks, low points and crossings in view, like GraphPage._find_points.
    curves: [[slot, text], ...]"""
    live = []
    for slot, text in curves:
        try:
            c = _get(text, angle)
        except gr.GraphError:
            continue
        live.append((int(slot), lambda v, c=c: c(v, params)))
    sub = "₁₂₃₄₅₆"
    name = lambda s: f"f{sub[s]}"  # noqa: E731
    pts = []
    for slot, f in live:
        for x in gr.roots(f, x0, x1):
            pts.append([x, 0.0, "root", [slot], f"{name(slot)} crosses zero"])
        for x, y, kind in gr.extrema(f, x0, x1):
            word = "Peak" if kind == "max" else "Low point"
            pts.append([x, y, kind, [slot], f"{word} of {name(slot)}"])
    for i, (sa, fa) in enumerate(live):
        for sb, fb in live[i + 1:]:
            for x, y in gr.intersections(fa, fb, x0, x1):
                pts.append([x, y, "intersection", [sa, sb], f"{name(sa)} meets {name(sb)}"])
    pts = [p for p in pts if y0 <= p[1] <= y1][:60]
    pts.sort(key=lambda p: p[0])
    for p in pts:
        p.append(f"({_num(p[0])}, {_num(p[1])})")
    return pts


def _num(v: float) -> str:
    return format_number(0.0 if abs(v) < 1e-12 else v, 6)


def graph_table(texts: list, angle: str, params: dict, x0: float, x1: float,
                step_text: str) -> list:
    try:
        step = abs(float(step_text.replace(",", "")))
    except ValueError:
        step = 0
    if step <= 0:
        return []
    start = math.ceil(x0 / step) * step
    fns = []
    for t in texts:
        try:
            c = _get(t, angle)
            fns.append(lambda v, c=c: c(v, params))
        except gr.GraphError:
            fns.append(None)
    rows, x = [], start
    while x <= x1 + step * 1e-9 and len(rows) < 500:
        cells = [_num(round(x, 12))]
        for f in fns:
            y = f(x) if f else math.nan
            cells.append("undefined" if math.isnan(y) else _num(y))
        rows.append(cells)
        x = start + len(rows) * step
    return rows


def nice_step(span: float) -> float:
    return gr.nice_step(span)


def fit_y(texts: list, angle: str, params: dict, x0: float, x1: float):
    ys = []
    for t in texts:
        try:
            c = _get(t, angle)
        except gr.GraphError:
            continue
        for _, y in gr.sample(lambda v, c=c: c(v, params), x0, x1, 400):
            if not math.isnan(y):
                ys.append(y)
    if not ys:
        return None
    ys.sort()
    lo, hi = ys[int(len(ys) * 0.02)], ys[int(len(ys) * 0.98) - 1]   # ignore spikes
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.1
    return [lo - pad, hi + pad]
