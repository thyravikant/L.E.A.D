"""Synthetic cadastral layer for the demo (NOT real survey data).

Parcels are rectangles laid out on a grid near Rupnagar. Areas are chosen so that
most bundled-sample ledger rows reconcile, one deliberately does not (1241), and
Khasra 1250 is left out so the 'not in cadastral layer' rule is demonstrated.
"""
import json

from . import config
from .geo import polygon_area_m2, unproject
from .units import unit_factors

LON0, LAT0 = 76.5265, 30.9700  # Rupnagar area (demo)

K = unit_factors(5.5)


def kms(k, m, s):
    return k * K["kanal"] + m * K["marla"] + s * K["sarsahi"]


# (khasra, village, area in m2)
PARCELS = [
    ("1234/2", "Sample Pur", kms(8, 4, 0)),
    ("1235", "Sample Pur", kms(5, 0, 0)),
    ("1236", "Sample Pur", kms(6, 10, 0)),
    ("1237", "Sample Pur", kms(4, 0, 0)),
    ("1240/1", "Sample Pur", kms(3, 12, 4)),
    ("1241", "Sample Pur", 4300.0),          # ledger says 10-0-0 (~5058 m2): mismatch demo
    ("1257/3", "Sample Pur", kms(4, 0, 0)),
    ("1258", "Sample Pur", kms(7, 0, 0)),
]


def build_geojson():
    feats = []
    cols = 4
    gap = 12.0
    cell = 90.0
    for i, (khasra, village, area) in enumerate(PARCELS):
        w = 60.0
        h = area / w
        cx = (i % cols) * (cell + gap)
        cy = (i // cols) * (cell + gap + 40)
        ring_m = [(cx, cy), (cx + w, cy), (cx + w, cy + h), (cx, cy + h), (cx, cy)]
        ring = [list(unproject(x, y, LON0, LAT0)) for x, y in ring_m]
        geom = {"type": "Polygon", "coordinates": [ring]}
        feats.append({
            "type": "Feature",
            "properties": {"khasra_no": khasra, "village": village, "tehsil": "Rupnagar (demo)",
                           "area_m2": round(polygon_area_m2(geom), 3)},
            "geometry": geom,
        })
    return {"type": "FeatureCollection", "features": feats}


def ensure_parcels():
    if not config.PARCELS_PATH.exists():
        config.PARCELS_PATH.write_text(json.dumps(build_geojson()), encoding="utf-8")


def load_parcels():
    """Return (geojson, {khasra_no: {village, area_m2}})."""
    ensure_parcels()
    gj = json.loads(config.PARCELS_PATH.read_text(encoding="utf-8"))
    index = {f["properties"]["khasra_no"]: f["properties"] for f in gj["features"]}
    return gj, index
