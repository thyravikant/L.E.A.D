"""Regional land unit normalizer.

Converts compound ledger areas such as "8-4-0" (Kanal-Marla-Sarsahi) or
"8 Kanal 4 Marla" to square metres, using the local Karam length.

Punjab/Haryana reference (Karam = 5.5 ft):
    1 Sarsahi = 1 square Karam = 30.25 sq ft
    1 Marla   = 9 Sarsahi
    1 Kanal   = 20 Marla = 5445 sq ft = 505.857 m2
    1 Killa   = 8 Kanal  (one acre)

Bigha / Biswa / Guntha differ between states, districts and eras, so they are
deliberately NOT hard-coded here. Add them to EXTRA_UNITS_M2 once the local
table is confirmed with the revenue office.
"""
import re

SQFT_TO_M2 = 0.09290304
ACRE_M2 = 4046.8564224

# Extra, user-configurable units: name -> square metres. Empty on purpose.
EXTRA_UNITS_M2: dict[str, float] = {}

# Unit aliases (Latin, Devanagari, Gurmukhi) -> canonical unit
ALIASES = {
    "kanal": "kanal", "k": "kanal", "kn": "kanal", "कनाल": "kanal", "ਕਨਾਲ": "kanal",
    "marla": "marla", "m": "marla", "मरला": "marla", "ਮਰਲਾ": "marla",
    "sarsahi": "sarsahi", "s": "sarsahi", "sar": "sarsahi", "सरसाई": "sarsahi", "ਸਰਸਾਹੀ": "sarsahi",
    "killa": "killa", "acre": "killa", "acres": "killa", "किला": "killa", "ਕਿੱਲਾ": "killa",
    "ha": "hectare", "hectare": "hectare", "hectares": "hectare",
    "sqm": "sqm", "m2": "sqm", "sqft": "sqft",
}


def unit_factors(karam_ft: float = 5.5) -> dict[str, float]:
    """Square metres per unit for a given Karam length."""
    sarsahi = (karam_ft ** 2) * SQFT_TO_M2
    marla = 9 * sarsahi
    kanal = 20 * marla
    f = {
        "sarsahi": sarsahi,
        "marla": marla,
        "kanal": kanal,
        "killa": 8 * kanal,
        "hectare": 10_000.0,
        "sqm": 1.0,
        "sqft": SQFT_TO_M2,
    }
    f.update(EXTRA_UNITS_M2)
    return f


_DASH = re.compile(r"[‐-―−]")
_KMS = re.compile(r"^\s*(\d+)\s*-\s*(\d+)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*$")
_LABELLED = re.compile(r"(\d+(?:\.\d+)?)\s*([^\W\d_]+)", re.UNICODE)


def parse_area(text: str, karam_ft: float = 5.5):
    """Return {"area_m2", "parts", "format"} or None if the text is not an area."""
    if not text:
        return None
    t = _DASH.sub("-", text.strip())
    f = unit_factors(karam_ft)

    m = _KMS.match(t)
    if m:
        k, ma, s = m.group(1), m.group(2), m.group(3) or "0"
        parts = {"kanal": float(k), "marla": float(ma), "sarsahi": float(s)}
        if parts["marla"] >= 20 or parts["sarsahi"] >= 9:
            return None  # not a valid K-M-S triple
        area = sum(v * f[u] for u, v in parts.items())
        return {"area_m2": round(area, 3), "parts": parts, "format": "K-M-S"}

    parts: dict[str, float] = {}
    for num, word in _LABELLED.findall(t):
        unit = ALIASES.get(word.lower())
        if unit and unit in f:
            parts[unit] = parts.get(unit, 0.0) + float(num)
    if not parts:
        return None
    area = sum(v * f[u] for u, v in parts.items())
    return {"area_m2": round(area, 3), "parts": parts, "format": "labelled"}
