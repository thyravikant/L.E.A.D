"""Cross-validation and dual-confidence scoring.

    c_v  visual confidence  = geometric mean of OCR word confidences (from extract.py)
    c_s  semantic confidence = weighted pass rate of validation rules; a hard
                               rule failure sets it to 0
    C    = c_v^alpha * c_s^(1-alpha)

A record is auto-accepted (straight-through) only if C >= AUTO_THRESHOLD and no
rule scored below RULE_FLOOR; otherwise it goes to the human review queue.
"""
import re

from . import config
from .units import parse_area

KHASRA_FORMAT = re.compile(r"^\d{1,5}(?:/\d{1,3})*$")


def validate(record: dict, parcels: dict, doc_khasras: list[str]) -> dict:
    """record: khasra, owner, area_raw, area_m2 (may be None). Returns rules + c_s."""
    rules = []

    def add(name, weight, score, detail, hard=False):
        rules.append({"name": name, "weight": weight, "score": score, "detail": detail, "hard": hard})

    khasra = (record.get("khasra") or "").strip()
    owner = (record.get("owner") or "").strip()
    area_m2 = record.get("area_m2")

    add("Khasra format", 1, 1.0 if KHASRA_FORMAT.match(khasra) else 0.0,
        "digits with optional /sub-number" if KHASRA_FORMAT.match(khasra) else "unexpected Khasra pattern")

    parcel = parcels.get(khasra)
    add("Khasra exists in cadastral layer", 3, 1.0 if parcel else 0.0,
        f"parcel found in {parcel['village']}" if parcel else "no matching parcel polygon", hard=True)

    add("Area parsed to SI units", 2, 1.0 if area_m2 else 0.0,
        f"{area_m2:,.1f} m²" if area_m2 else "area text not understood")

    if parcel and area_m2:
        gis = parcel["area_m2"]
        rel = abs(area_m2 - gis) / gis
        if rel <= config.AREA_TOL:
            score, detail = 1.0, f"ledger {area_m2:,.1f} vs GIS {gis:,.1f} m² ({rel:.1%} apart)"
        elif rel <= config.AREA_WARN_TOL:
            score, detail = 0.5, f"ledger {area_m2:,.1f} vs GIS {gis:,.1f} m² ({rel:.1%} apart): check"
        else:
            score, detail = 0.0, f"MISMATCH: ledger {area_m2:,.1f} vs GIS {gis:,.1f} m² ({rel:.1%} apart)"
        add("Ledger area matches GIS polygon", 3, score, detail)
    else:
        add("Ledger area matches GIS polygon", 3, 0.0, "cannot compare (missing parcel or area)")

    ok_owner = len(owner) >= 3 and not re.search(r"\d", owner)
    add("Owner name plausible", 1, 1.0 if ok_owner else 0.0,
        "alphabetic name" if ok_owner else "empty or contains digits")

    fc = record.get("field_conf") or {}
    if fc:
        worst = min(fc, key=fc.get)
        low = fc[worst]
        if low >= config.FIELD_CONF_OK:
            score = 1.0
        elif low >= config.FIELD_CONF_LOW:
            score = 0.4
        else:
            score = 0.0
        add("OCR confidence of every field", 2, score, f"weakest field: {worst} at {low:.0%}")

    dup = doc_khasras.count(khasra) > 1
    add("Khasra unique in document", 1, 0.0 if dup else 1.0,
        "duplicate Khasra in this document" if dup else "unique")

    total = sum(r["weight"] for r in rules)
    c_s = sum(r["weight"] * r["score"] for r in rules) / total
    if any(r["hard"] and r["score"] == 0 for r in rules):
        c_s = 0.0
    return {"rules": rules, "c_s": round(c_s, 4), "parcel": parcel}


def joint_confidence(c_v: float, c_s: float) -> float:
    if c_s <= 0 or c_v <= 0:
        return 0.0
    return round((c_v ** config.ALPHA) * (c_s ** (1 - config.ALPHA)), 4)


def route(c_joint: float, rules: list[dict]) -> str:
    weakest = min(r["score"] for r in rules)
    if c_joint >= config.AUTO_THRESHOLD and weakest >= config.RULE_FLOOR:
        return "auto_accepted"
    return "needs_review"


def revalidate(fields: dict, c_v: float, parcels: dict, doc_khasras: list[str], field_conf: dict | None = None) -> dict:
    """Re-run validation after a reviewer edits fields (keeps the visual score)."""
    area = parse_area(fields.get("area_raw", ""), config.KARAM_FT)
    rec = {**fields, "area_m2": area["area_m2"] if area else None, "field_conf": field_conf}
    result = validate(rec, parcels, doc_khasras)
    c_joint = joint_confidence(c_v, result["c_s"])
    return {"area_m2": rec["area_m2"], **result, "c_joint": c_joint,
            "route": route(c_joint, result["rules"])}
