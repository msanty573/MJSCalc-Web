"""Unit conversion tables. Each unit maps to its factor relative to the
category's base unit (shown first). Temperature is handled specially."""

from __future__ import annotations

UNITS: dict[str, dict[str, float]] = {
    "Length": {
        "meter (m)": 1, "kilometer (km)": 1e3, "centimeter (cm)": 1e-2,
        "millimeter (mm)": 1e-3, "micrometer (µm)": 1e-6, "nanometer (nm)": 1e-9,
        "inch (in)": 0.0254, "foot (ft)": 0.3048, "yard (yd)": 0.9144,
        "mile (mi)": 1609.344, "nautical mile (nmi)": 1852, "mil (thou)": 2.54e-5,
    },
    "Area": {
        "square meter (m²)": 1, "square kilometer (km²)": 1e6,
        "square centimeter (cm²)": 1e-4, "square millimeter (mm²)": 1e-6,
        "hectare (ha)": 1e4, "acre": 4046.8564224, "square inch (in²)": 0.00064516,
        "square foot (ft²)": 0.09290304, "square yard (yd²)": 0.83612736,
        "square mile (mi²)": 2589988.110336,
    },
    "Volume": {
        "liter (L)": 1, "milliliter (mL)": 1e-3, "cubic meter (m³)": 1e3,
        "cubic centimeter (cm³)": 1e-3, "cubic inch (in³)": 0.016387064,
        "cubic foot (ft³)": 28.316846592, "US gallon (gal)": 3.785411784,
        "US quart (qt)": 0.946352946, "US pint (pt)": 0.473176473,
        "US cup": 0.2365882365, "US fluid ounce (fl oz)": 0.0295735295625,
        "tablespoon (tbsp)": 0.01478676478125, "teaspoon (tsp)": 0.00492892159375,
        "imperial gallon": 4.54609,
    },
    "Mass": {
        "kilogram (kg)": 1, "gram (g)": 1e-3, "milligram (mg)": 1e-6,
        "metric ton (t)": 1e3, "pound (lb)": 0.45359237, "ounce (oz)": 0.028349523125,
        "stone (st)": 6.35029318, "short ton (US)": 907.18474, "long ton (UK)": 1016.0469088,
    },
    "Temperature": {
        "Celsius (°C)": 1, "Fahrenheit (°F)": 1, "Kelvin (K)": 1, "Rankine (°R)": 1,
    },
    "Time": {
        "second (s)": 1, "millisecond (ms)": 1e-3, "microsecond (µs)": 1e-6,
        "nanosecond (ns)": 1e-9, "minute (min)": 60, "hour (h)": 3600,
        "day": 86400, "week": 604800, "year (365.25 d)": 31557600,
    },
    "Speed": {
        "meter/second (m/s)": 1, "kilometer/hour (km/h)": 1 / 3.6,
        "mile/hour (mph)": 0.44704, "foot/second (ft/s)": 0.3048,
        "knot (kn)": 1852 / 3600, "Mach (sea level)": 340.29,
    },
    "Pressure": {
        "pascal (Pa)": 1, "kilopascal (kPa)": 1e3, "megapascal (MPa)": 1e6,
        "bar": 1e5, "millibar (mbar)": 100, "atmosphere (atm)": 101325,
        "psi (lbf/in²)": 6894.757293168, "mmHg (torr)": 133.322387415,
        "inHg": 3386.389,
    },
    "Energy": {
        "joule (J)": 1, "kilojoule (kJ)": 1e3, "calorie (cal)": 4.184,
        "kilocalorie (kcal)": 4184, "watt-hour (Wh)": 3600, "kilowatt-hour (kWh)": 3.6e6,
        "BTU": 1055.05585262, "electronvolt (eV)": 1.602176634e-19,
        "foot-pound (ft·lbf)": 1.3558179483314004,
    },
    "Power": {
        "watt (W)": 1, "kilowatt (kW)": 1e3, "megawatt (MW)": 1e6,
        "horsepower (hp)": 745.69987158227022, "metric horsepower": 735.49875,
        "BTU/hour": 0.29307107017, "ton of refrigeration": 3516.8528420667,
    },
    "Force": {
        "newton (N)": 1, "kilonewton (kN)": 1e3, "pound-force (lbf)": 4.4482216152605,
        "kilogram-force (kgf)": 9.80665, "dyne": 1e-5,
    },
    "Torque": {
        "newton-meter (N·m)": 1, "pound-foot (lbf·ft)": 1.3558179483314004,
        "pound-inch (lbf·in)": 0.1129848290276167, "kgf·m": 9.80665,
    },
    "Angle": {
        "degree (°)": 1, "radian (rad)": 57.29577951308232, "gradian (grad)": 0.9,
        "arcminute (′)": 1 / 60, "arcsecond (″)": 1 / 3600, "revolution": 360,
    },
    "Data": {
        "byte (B)": 1, "bit (b)": 1 / 8, "kilobyte (KB)": 1e3, "megabyte (MB)": 1e6,
        "gigabyte (GB)": 1e9, "terabyte (TB)": 1e12, "kibibyte (KiB)": 1024,
        "mebibyte (MiB)": 1024**2, "gibibyte (GiB)": 1024**3, "tebibyte (TiB)": 1024**4,
    },
    "Fuel economy": {
        # base: km per liter; L/100km handled specially (inverse)
        "km/L": 1, "miles/gallon (US)": 0.425143707, "miles/gallon (UK)": 0.354006189,
        "L/100 km": 1,
    },
}


def _temp_to_c(v: float, unit: str) -> float:
    if unit.startswith("Celsius"):
        return v
    if unit.startswith("Fahrenheit"):
        return (v - 32) * 5 / 9
    if unit.startswith("Kelvin"):
        return v - 273.15
    return (v - 491.67) * 5 / 9  # Rankine


def _temp_from_c(c: float, unit: str) -> float:
    if unit.startswith("Celsius"):
        return c
    if unit.startswith("Fahrenheit"):
        return c * 9 / 5 + 32
    if unit.startswith("Kelvin"):
        return c + 273.15
    return (c + 273.15) * 9 / 5


def convert(value: float, category: str, from_unit: str, to_unit: str) -> float:
    if category == "Temperature":
        return _temp_from_c(_temp_to_c(value, from_unit), to_unit)
    table = UNITS[category]
    if category == "Fuel economy":
        kmpl = 100 / value if from_unit == "L/100 km" else value * table[from_unit]
        return 100 / kmpl if to_unit == "L/100 km" else kmpl / table[to_unit]
    return value * table[from_unit] / table[to_unit]


# --------------------------------------------------------------------------
# Number bases (programmer)
# --------------------------------------------------------------------------

BASES = {"Decimal": 10, "Hexadecimal": 16, "Binary": 2, "Octal": 8}


def parse_int(text: str, base: int) -> int:
    text = text.strip().replace("_", "").replace(" ", "").lower()
    for prefix in ("0x", "0b", "0o"):
        if text.startswith(prefix) or text.startswith("-" + prefix):
            text = text.replace(prefix, "", 1)
    return int(text, base)


def format_int(n: int, base: int) -> str:
    if base == 10:
        return f"{n:,}"
    sign = "-" if n < 0 else ""
    digits = {16: f"{abs(n):X}", 2: f"{abs(n):b}", 8: f"{abs(n):o}"}[base]
    group = 4 if base in (2, 16) else 3
    digits = digits.zfill(-(-len(digits) // group) * group) if base == 2 else digits
    parts = []
    while digits:
        parts.insert(0, digits[-group:])
        digits = digits[:-group]
    return sign + " ".join(parts)
