"""Graphing: compile y = f(x) once to fast Python, then sample and analyze it.

Expressions use the same parser as the calculator, so everything it accepts
works here. Single letters other than x and e are parameters (a, b, c…), so
``a*x^2 + b*x + c`` gives three sliders; in this context they override the
physical constants of the same name. Juxtaposed letters are split the way
people write them: ``2ax`` is 2·a·x and ``sinx`` is sin(x).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from . import expression as ex

_RESERVED = {"x", "e"}
_LONG_NAMES = sorted([*ex.FUNCTIONS, "pi", "tau", "phi", "ans"], key=len, reverse=True)


# Numbers (kept whole, so 1e9 and 2.5E-3 stay numbers) or names (split into letters).
_NAME_OR_NUMBER = re.compile(r"((?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|[A-Za-z_][A-Za-z_0-9]*")


class GraphError(ValueError):
    pass


def _split_name(name: str) -> list[str]:
    """'axsin' -> ['a', 'x', 'sin']; known function/constant names stay whole."""
    if name in ex.FUNCTIONS or name in ("pi", "tau", "phi") or len(name) == 1:
        return [name]
    out, i = [], 0
    while i < len(name):
        match = next((n for n in _LONG_NAMES if name.startswith(n, i)), None)
        if match:
            out.append(match)
            i += len(match)
        else:
            out.append(name[i])
            i += 1
    return out


def prepare(text: str) -> str:
    """Strip 'y =' / 'f(x) =' and split run-together letters."""
    text = text.strip()
    text = re.sub(r"^\s*(?:y|f\s*\(\s*x\s*\)|[a-z]\s*\(\s*x\s*\))\s*=\s*", "", text)
    for sym, rep in ex._SYMBOLS.items():
        text = text.replace(sym, rep)
    return _NAME_OR_NUMBER.sub(
        lambda m: m.group(0) if m.group(1) else " ".join(_split_name(m.group(0))), text)


def parameters(text: str) -> list[str]:
    """Parameter letters used in an expression, in order of appearance."""
    seen = []
    for tok in ex.tokenize(prepare(text)):
        if tok.kind == "name" and len(tok.value) == 1 and tok.value not in _RESERVED \
                and tok.value not in ex.FUNCTIONS and tok.value not in seen:
            seen.append(tok.value)
    return seen


@dataclass
class Compiled:
    text: str
    params: list[str]
    fn: Callable[[float, dict], float]

    def __call__(self, x: float, params: dict | None = None) -> float:
        try:
            y = self.fn(x, params or {})
            return y if isinstance(y, float) and math.isfinite(y) else math.nan
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return math.nan


def compile_expr(text: str, angle_mode: str = "rad") -> Compiled:
    if not text.strip():
        raise GraphError("Empty")
    try:
        params = parameters(text)
        tree = ex.Parser(prepare(text), {"x", *params}).parse()
    except ex.CalcError as exc:
        raise GraphError(str(exc)) from None
    src = _py(tree, set(params), angle_mode)
    env = {"__builtins__": {}, "_f": ex.FUNCTIONS, "_pow": _pow, "_fact": _fact,
           "_rad": math.radians, "_deg": math.degrees, "float": float}
    fn = eval(f"lambda x, p: float({src})", env)  # noqa: S307 - source built from our AST
    return Compiled(text, params, fn)


def _py(node, params: set[str], mode: str) -> str:
    if isinstance(node, ex.Num):
        return repr(node.value)
    if isinstance(node, ex.Var):
        if node.name == "x":
            return "x"
        if node.name in params:
            return f"p.get({node.name!r}, 1.0)"
        return repr(ex.CONSTANTS[node.name])
    if isinstance(node, ex.Unary):
        return f"(-{_py(node.operand, params, mode)})"
    if isinstance(node, ex.Percent):
        return f"({_py(node.operand, params, mode)} / 100)"
    if isinstance(node, ex.Factorial):
        return f"_fact({_py(node.operand, params, mode)})"
    if isinstance(node, ex.Binary):
        a, b = _py(node.left, params, mode), _py(node.right, params, mode)
        if node.op == "^":
            return f"_pow({a}, {b})"
        return f"({a} {node.op} {b})"
    if isinstance(node, ex.Call):
        args = [_py(a, params, mode) for a in node.args]
        if mode == "deg" and node.name in ex._TRIG_IN:
            args[0] = f"_rad({args[0]})"
        call = f"_f[{node.name!r}]({', '.join(args)})"
        if mode == "deg" and node.name in ex._TRIG_OUT:
            call = f"_deg({call})"
        return call
    raise GraphError("Unsupported expression")


def _pow(a: float, b: float) -> float:
    if a < 0 and b != int(b):
        inv = 1 / b
        if abs(inv - round(inv)) < 1e-9 and round(inv) % 2 == 1:   # odd roots
            return -((-a) ** b)
        return math.nan
    return math.pow(a, b)


def _fact(a: float) -> float:
    if a < 0 or (a != int(a) and a > 170):
        return math.nan
    return float(math.factorial(int(a))) if a == int(a) else math.gamma(a + 1)


# --------------------------------------------------------------------------
# Sampling and analysis
# --------------------------------------------------------------------------

def sample(f: Callable[[float], float], x0: float, x1: float, n: int) -> list[tuple[float, float]]:
    step = (x1 - x0) / max(1, n - 1)
    return [(x0 + i * step, f(x0 + i * step)) for i in range(n)]


def slope(f: Callable[[float], float], x: float, h: float = 1e-5) -> float:
    """Numerical derivative f′(x) (central difference); nan at a jump or corner."""
    h = max(abs(h), 1e-9)
    y0, y1, y2 = f(x), f(x - h), f(x + h)
    if math.isnan(y0) or math.isnan(y1) or math.isnan(y2):
        return math.nan
    left, right = (y0 - y1) / h, (y2 - y0) / h
    d = (left + right) / 2
    if abs(left - right) > 0.01 * max(1.0, abs(d)) + 50 * h * max(1.0, abs(d)):
        return math.nan                       # the two sides disagree: no single slope
    return d


def _bisect(f, a: float, b: float, fa: float, iters: int = 80) -> float:
    for _ in range(iters):
        m = (a + b) / 2
        fm = f(m)
        if math.isnan(fm):
            return math.nan
        if fm == 0:
            return m
        if (fm < 0) == (fa < 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2


def roots(f, x0: float, x1: float, n: int = 600) -> list[float]:
    pts = sample(f, x0, x1, n)
    out: list[float] = []
    for (a, fa), (b, fb) in zip(pts, pts[1:]):
        if math.isnan(fa) or math.isnan(fb):
            continue
        if fa == 0:
            out.append(a)
        elif (fa < 0) != (fb < 0):
            r = _bisect(f, a, b, fa)
            # A sign change across an asymptote (tan, 1/x) is not a root.
            if not math.isnan(r) and abs(f(r)) <= 1e-6 * max(1.0, abs(fa), abs(fb)):
                out.append(r)
    # Touching roots like x² at 0 don't change sign: find them as extrema at y≈0.
    span = (x1 - x0)
    for x, y, _ in extrema(f, x0, x1, n):
        if abs(y) < 1e-9 * max(1.0, span) and not any(abs(x - r) < span * 1e-6 for r in out):
            out.append(x)
    return _dedupe(sorted(out), (x1 - x0) * 1e-7)


def extrema(f, x0: float, x1: float, n: int = 600) -> list[tuple[float, float, str]]:
    """Local maxima/minima: (x, y, 'max' | 'min')."""
    pts = sample(f, x0, x1, n)
    out = []
    for (a, fa), (m, fm), (b, fb) in zip(pts, pts[1:], pts[2:]):
        if math.isnan(fa) or math.isnan(fm) or math.isnan(fb):
            continue
        kind = "max" if fm > fa and fm >= fb else "min" if fm < fa and fm <= fb else None
        if not kind:
            continue
        x = _golden(f, a, b, kind)
        y = f(x)
        if math.isnan(y):
            continue
        # Reject the tip of an asymptote spike: a true extremum is no further
        # from its neighbours than the curve's own variation suggests.
        if abs(y - fm) > 10 * (abs(fa - fm) + abs(fb - fm)) + 1e-12:
            continue
        out.append((x, y, kind))
    return [e for i, e in enumerate(out)
            if not any(abs(e[0] - o[0]) < (x1 - x0) * 1e-7 for o in out[:i])]


def _golden(f, a: float, b: float, kind: str, iters: int = 80) -> float:
    sign = -1 if kind == "max" else 1
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = sign * f(c), sign * f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = sign * f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = sign * f(d)
    return (a + b) / 2


def intersections(f, g, x0: float, x1: float, n: int = 600) -> list[tuple[float, float]]:
    diff = lambda x: f(x) - g(x)  # noqa: E731
    return [(x, f(x)) for x in roots(diff, x0, x1, n) if not math.isnan(f(x))]


def _dedupe(xs: list[float], tol: float) -> list[float]:
    out: list[float] = []
    for x in xs:
        if not out or abs(x - out[-1]) > tol:
            out.append(x)
    return out


def nice_step(span: float, target: int = 8) -> float:
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
