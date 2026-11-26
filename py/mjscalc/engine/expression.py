"""Safe math expression evaluator.

A small Pratt parser that understands the notation people actually type:

* ``2^3``, ``2**3``         exponentiation (right associative, ``-2^2 == -4``)
* ``2pi``, ``3(4+1)``      implicit multiplication
* ``5!``                    factorial
* ``50%``, ``200 + 10%``   percent (``a ± b%`` means ``a ± a*b/100``)
* ``12% of 250``            "of" means multiply (= 30)
* ``×``, ``÷``, ``−``, ``π``, ``√``  typographic symbols from the keypad
* ``sin``, ``log``, ``nCr`` ... see ``FUNCTIONS``

Nothing is passed to Python's ``eval``; only whitelisted names are callable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable


class CalcError(Exception):
    """Raised for any user-facing evaluation problem."""


# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------

_SYMBOLS = {
    "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "π": " pi ",
    "√": " sqrt ", "∛": " cbrt ", "²": "^2", "³": "^3", "τ": " tau ", "φ": " phi ",
}

_TOKEN_RE = re.compile(
    r"""
    (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op>\*\*|[-+*/^%!(),])
  | (?P<ws>\s+)
    """,
    re.VERBOSE,
)


_OF_RE = re.compile(r"\bof\b", re.IGNORECASE)


@dataclass
class Token:
    kind: str  # num, name, op, end
    value: str
    pos: int


def tokenize(text: str) -> list[Token]:
    for sym, rep in _SYMBOLS.items():
        text = text.replace(sym, rep)
    text = _OF_RE.sub("*", text)          # 12% of 250 -> 12% * 250 = 30
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise CalcError(f"Unexpected character '{text[pos]}'")
        kind = m.lastgroup
        if kind != "ws":
            value = m.group(kind)
            if value == "**":
                value = "^"
            tokens.append(Token(kind, value, pos))
        pos = m.end()
    tokens.append(Token("end", "", pos))
    return tokens


# --------------------------------------------------------------------------
# Built-in functions and constants
# --------------------------------------------------------------------------

def _factorial(x: float) -> float:
    if x < 0:
        raise CalcError("Factorial of a negative number")
    if x == int(x):
        if x > 170:
            raise CalcError("Result too large")
        return float(math.factorial(int(x)))
    return math.gamma(x + 1)


def _int_arg(x: float, name: str) -> int:
    if x != int(x):
        raise CalcError(f"{name} needs whole numbers")
    return int(x)


def _ncr(n: float, r: float) -> float:
    return float(math.comb(_int_arg(n, "nCr"), _int_arg(r, "nCr")))


def _npr(n: float, r: float) -> float:
    return float(math.perm(_int_arg(n, "nPr"), _int_arg(r, "nPr")))


def _root(x: float, n: float) -> float:
    if x < 0 and n == int(n) and int(n) % 2 == 1:
        return -((-x) ** (1 / n))
    return x ** (1 / n)


def _log(x: float, base: float | None = None) -> float:
    return math.log10(x) if base is None else math.log(x, base)


def _round(x: float, digits: float = 0) -> float:
    return float(round(x, int(digits)))


CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "phi": (1 + math.sqrt(5)) / 2,
    "inf": math.inf,
    # Physical constants (SI)
    "c": 299_792_458.0,          # speed of light, m/s
    "g": 9.80665,                # standard gravity, m/s^2
    "G": 6.67430e-11,            # gravitational constant
    "h": 6.62607015e-34,         # Planck constant
    "kB": 1.380649e-23,          # Boltzmann constant
    "NA": 6.02214076e23,         # Avogadro constant
    "qe": 1.602176634e-19,       # elementary charge
    "R": 8.314462618,            # gas constant
    "me": 9.1093837015e-31,      # electron mass
    "eps0": 8.8541878128e-12,    # vacuum permittivity
    "mu0": 1.25663706212e-6,     # vacuum permeability
}

CONSTANT_DESCRIPTIONS: dict[str, str] = {
    "pi": "π  3.14159…",
    "e": "Euler's number",
    "tau": "τ = 2π",
    "phi": "Golden ratio",
    "c": "Speed of light (m/s)",
    "g": "Standard gravity (m/s²)",
    "G": "Gravitational constant",
    "h": "Planck constant (J·s)",
    "kB": "Boltzmann constant (J/K)",
    "NA": "Avogadro constant (1/mol)",
    "qe": "Elementary charge (C)",
    "R": "Gas constant (J/mol·K)",
    "me": "Electron mass (kg)",
    "eps0": "Vacuum permittivity (F/m)",
    "mu0": "Vacuum permeability (H/m)",
}

# Functions whose input is an angle / whose output is an angle.
_TRIG_IN = {"sin", "cos", "tan", "sec", "csc", "cot"}
_TRIG_OUT = {"asin", "acos", "atan", "atan2"}

FUNCTIONS: dict[str, Callable[..., float]] = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sec": lambda x: 1 / math.cos(x),
    "csc": lambda x: 1 / math.sin(x),
    "cot": lambda x: 1 / math.tan(x),
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
    "sqrt": math.sqrt, "cbrt": lambda x: _root(x, 3), "root": _root,
    "ln": math.log, "log": _log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "abs": abs, "floor": math.floor, "ceil": math.ceil,
    "round": _round, "fact": _factorial, "gamma": math.gamma,
    "nCr": _ncr, "nPr": _npr,
    "gcd": lambda *a: float(math.gcd(*(_int_arg(x, "gcd") for x in a))),
    "lcm": lambda *a: float(math.lcm(*(_int_arg(x, "lcm") for x in a))),
    "min": min, "max": max, "hypot": math.hypot,
    "mod": math.fmod,
    "deg": math.degrees, "rad": math.radians,
    "erf": math.erf, "erfc": math.erfc,
}

FUNCTION_DESCRIPTIONS: dict[str, str] = {
    "sin": "sine", "cos": "cosine", "tan": "tangent",
    "asin": "inverse sine", "acos": "inverse cosine", "atan": "inverse tangent",
    "sinh": "hyperbolic sine", "cosh": "hyperbolic cosine", "tanh": "hyperbolic tangent",
    "sqrt": "square root", "cbrt": "cube root", "root": "root(x, n) — nth root",
    "ln": "natural log", "log": "log base 10, or log(x, base)", "log2": "log base 2",
    "exp": "e to the x", "abs": "absolute value", "round": "round(x, digits)",
    "floor": "round down", "ceil": "round up", "fact": "factorial (same as x!)",
    "nCr": "combinations nCr(n, r)", "nPr": "permutations nPr(n, r)",
    "gcd": "greatest common divisor", "lcm": "least common multiple",
    "min": "smallest value", "max": "largest value", "hypot": "√(x²+y²)",
    "mod": "remainder mod(a, b)", "deg": "radians → degrees", "rad": "degrees → radians",
    "erf": "error function (normal-curve areas)", "erfc": "1 − erf(x)",
}


# --------------------------------------------------------------------------
# AST
# --------------------------------------------------------------------------

@dataclass
class Num:
    value: float


@dataclass
class Var:
    name: str


@dataclass
class Unary:
    op: str
    operand: object


@dataclass
class Binary:
    op: str
    left: object
    right: object


@dataclass
class Percent:
    operand: object


@dataclass
class Factorial:
    operand: object


@dataclass
class Call:
    name: str
    args: list


# Binding powers
_BP_ADD = 10
_BP_MUL = 20
_BP_UNARY = 30
_BP_POW = 40
_BP_POSTFIX = 50

_INFIX = {"+": _BP_ADD, "-": _BP_ADD, "*": _BP_MUL, "/": _BP_MUL, "^": _BP_POW}


class Parser:
    def __init__(self, text: str, names: set[str]):
        self.tokens = tokenize(text)
        self.i = 0
        self.names = names

    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        t = self.tokens[self.i]
        self.i += 1
        return t

    def expect(self, value: str) -> None:
        if self.tok.value != value:
            found = self.tok.value or "end of input"
            raise CalcError(f"Expected '{value}' but found {found}")
        self.advance()

    def parse(self):
        if self.tok.kind == "end":
            raise CalcError("Empty expression")
        node = self.expr(0)
        if self.tok.kind != "end":
            raise CalcError(f"Unexpected '{self.tok.value}'")
        return node

    def _starts_operand(self) -> bool:
        t = self.tok
        return t.kind in ("num", "name") or t.value == "("

    def expr(self, min_bp: int):
        left = self.prefix()
        while True:
            t = self.tok
            if t.kind == "op" and t.value in ("!", "%"):
                self.advance()
                left = Factorial(left) if t.value == "!" else Percent(left)
                continue
            if t.kind == "op" and t.value in _INFIX:
                bp = _INFIX[t.value]
                if bp < min_bp or (bp == min_bp and t.value != "^"):
                    break
                self.advance()
                # ^ is right associative; others left associative
                right = self.expr(bp if t.value == "^" else bp + 1)
                left = Binary(t.value, left, right)
                continue
            if self._starts_operand():
                # implicit multiplication: 2pi, 3(4), (1+2)(3+4)
                if _BP_MUL < min_bp:
                    break
                right = self.expr(_BP_MUL + 1)
                left = Binary("*", left, right)
                continue
            break
        return left

    def prefix(self):
        t = self.advance()
        if t.kind == "num":
            return Num(float(t.value))
        if t.kind == "op" and t.value in "+-":
            operand = self.expr(_BP_UNARY)
            return operand if t.value == "+" else Unary("-", operand)
        if t.value == "(":
            node = self.expr(0)
            self.expect(")")
            return node
        if t.kind == "name":
            if t.value in FUNCTIONS:
                return self.call(t.value)
            if t.value in self.names or t.value in CONSTANTS:
                return Var(t.value)
            raise CalcError(f"Unknown name '{t.value}'")
        if t.kind == "end":
            raise CalcError("Expression is incomplete")
        raise CalcError(f"Unexpected '{t.value}'")

    def call(self, name: str):
        if self.tok.value != "(":
            # Allow "sin 30" / "√9" style: bind to the next tight operand
            arg = self.expr(_BP_POW)
            return Call(name, [arg])
        self.advance()
        args = []
        if self.tok.value != ")":
            args.append(self.expr(0))
            while self.tok.value == ",":
                self.advance()
                args.append(self.expr(0))
        self.expect(")")
        return Call(name, args)


# --------------------------------------------------------------------------
# Evaluator
# --------------------------------------------------------------------------

class Calculator:
    """Evaluates expressions, remembering ``ans`` and user variables."""

    def __init__(self, angle_mode: str = "deg"):
        self.angle_mode = angle_mode  # "deg" or "rad"
        self.variables: dict[str, float] = {"ans": 0.0}

    def evaluate(self, text: str, store: bool = True) -> float:
        text = text.strip()
        target = None
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*=(?!=)(.*)$", text)
        if m and m.group(1) not in FUNCTIONS and m.group(1) not in CONSTANTS:
            target, text = m.group(1), m.group(2)
        tree = Parser(text, set(self.variables)).parse()
        try:
            result = float(self._eval(tree))
        except CalcError:
            raise
        except ZeroDivisionError:
            raise CalcError("Cannot divide by zero") from None
        except OverflowError:
            raise CalcError("Result too large") from None
        except (ValueError, TypeError) as exc:
            raise CalcError(_friendly_math_error(exc)) from None
        if math.isnan(result):
            raise CalcError("Undefined result")
        if store:
            self.variables["ans"] = result
            if target:
                self.variables[target] = result
        return result

    # -- internals ---------------------------------------------------------

    def _to_rad(self, x: float) -> float:
        return math.radians(x) if self.angle_mode == "deg" else x

    def _from_rad(self, x: float) -> float:
        return math.degrees(x) if self.angle_mode == "deg" else x

    def _eval(self, node) -> float:
        if isinstance(node, Num):
            return node.value
        if isinstance(node, Var):
            if node.name in self.variables:
                return self.variables[node.name]
            return CONSTANTS[node.name]
        if isinstance(node, Unary):
            return -self._eval(node.operand)
        if isinstance(node, Percent):
            return self._eval(node.operand) / 100
        if isinstance(node, Factorial):
            return _factorial(self._eval(node.operand))
        if isinstance(node, Binary):
            left = self._eval(node.left)
            if node.op in "+-" and isinstance(node.right, Percent):
                # 200 + 10% -> 220 (percent of the left side)
                pct = self._eval(node.right.operand) / 100
                right = left * pct
            else:
                right = self._eval(node.right)
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
            if node.op == "/":
                if right == 0:
                    raise CalcError("Cannot divide by zero")
                return left / right
            if node.op == "^":
                if left < 0 and right != int(right):
                    # allow odd roots of negatives, e.g. (-8)^(1/3)
                    inv = 1 / right
                    if abs(inv - round(inv)) < 1e-9 and round(inv) % 2 == 1:
                        return -((-left) ** right)
                    raise CalcError("Fractional power of a negative number")
                return math.pow(left, right)
        if isinstance(node, Call):
            fn = FUNCTIONS[node.name]
            args = [self._eval(a) for a in node.args]
            if node.name in _TRIG_IN:
                args = [self._to_rad(args[0])] + args[1:]
            result = fn(*args)
            if node.name in _TRIG_IN:
                result = _clean_trig(result)
            if node.name in _TRIG_OUT:
                result = self._from_rad(result)
            return result
        raise CalcError("Invalid expression")


def _clean_trig(x: float) -> float:
    """sin(180°) should be 0, not 1.2e-16; tan(90°) should be an error."""
    if abs(x) < 1e-12:
        return 0.0
    if abs(x) > 1e15:
        raise CalcError("Undefined (asymptote)")
    return x


def _friendly_math_error(exc: Exception) -> str:
    msg = str(exc)
    if "math domain" in msg:
        return "Input is outside the function's domain"
    if "positional argument" in msg or "argument" in msg:
        return "Wrong number of arguments"
    return msg[:1].upper() + msg[1:]


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def format_number(x: float, precision: int = 12, mode: str = "auto") -> str:
    """Human-friendly number formatting.

    mode: "auto" (plain, switching to scientific for very large/small),
          "sci" (scientific), "eng" (engineering, exponent multiple of 3).
    """
    if math.isinf(x):
        return "∞" if x > 0 else "-∞"
    if mode == "sci":
        return _sci(x, precision)
    if mode == "eng":
        return _eng(x, precision)
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e15 or ax < 1e-9:
        return _sci(x, precision)
    rounded = float(f"{x:.{precision}g}")
    if rounded == int(rounded) and abs(rounded) < 1e15:
        return f"{int(rounded):,}"
    decimals = max(0, precision - 1 - math.floor(math.log10(ax)))
    return f"{rounded:,.{decimals}f}".rstrip("0").rstrip(".")


def _sci(x: float, precision: int) -> str:
    if x == 0:
        return "0"
    mant, exp = f"{x:.{precision - 1}e}".split("e")
    mant = mant.rstrip("0").rstrip(".")
    return f"{mant}e{int(exp)}"


def _eng(x: float, precision: int) -> str:
    if x == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(x))))
    exp3 = exp - (exp % 3)
    mant = x / 10**exp3
    m = f"{mant:.{max(0, precision - 3)}f}".rstrip("0").rstrip(".")
    return m if exp3 == 0 else f"{m}e{exp3}"
