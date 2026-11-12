"""Central configuration. Override with environment variables where noted."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("LR_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "land_records.db"
PARCELS_PATH = DATA_DIR / "parcels.geojson"
SAMPLES_DIR = ROOT / "samples"
STATIC_DIR = ROOT / "static"

# OCR languages passed to Tesseract, e.g. "eng", "eng+hin", "eng+hin+pan".
# The matching traineddata files must be installed (see README).
OCR_LANGS = os.getenv("LR_OCR_LANGS", "eng")

# Karam length in feet used by the land unit normalizer (Punjab: 5.5 ft).
KARAM_FT = float(os.getenv("LR_KARAM_FT", "5.5"))

# Dual-confidence scoring: C = c_v^ALPHA * c_s^(1-ALPHA)
ALPHA = float(os.getenv("LR_ALPHA", "0.5"))
# A record is auto-accepted (straight-through) only if C >= AUTO_THRESHOLD
# and no validation rule scored below RULE_FLOOR.
AUTO_THRESHOLD = float(os.getenv("LR_AUTO_THRESHOLD", "0.80"))
RULE_FLOOR = 0.5
# Every extracted field should have OCR confidence >= FIELD_CONF_OK to pass the OCR rule;
# between FIELD_CONF_LOW and FIELD_CONF_OK it scores 0.4 (forces human review).
FIELD_CONF_OK = float(os.getenv("LR_FIELD_CONF_OK", "0.85"))
FIELD_CONF_LOW = 0.70

# Area reconciliation: ledger area vs. GIS polygon area (relative difference).
AREA_TOL = 0.02       # within 2%  -> full score
AREA_WARN_TOL = 0.10  # within 10% -> half score, flagged

for d in (DATA_DIR, UPLOAD_DIR):
    d.mkdir(parents=True, exist_ok=True)
