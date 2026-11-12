"""OCR layer: Tesseract word boxes with confidences.

If Tesseract is not installed, the bundled sample scan can still be demonstrated
with a recorded OCR output (clearly reported as engine "recorded-sample").
"""
import json
from pathlib import Path

import numpy as np

from . import config

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


class OCRUnavailable(RuntimeError):
    pass


def tesseract_status() -> dict:
    if pytesseract is None:
        return {"available": False, "reason": "pytesseract is not installed", "langs": []}
    try:
        version = str(pytesseract.get_tesseract_version())
        langs = pytesseract.get_languages(config="")
        return {"available": True, "version": version, "langs": langs}
    except Exception as exc:  # TesseractNotFoundError and friends
        return {"available": False, "reason": str(exc).strip().splitlines()[0], "langs": []}


def _usable_langs() -> str:
    """Intersect requested languages with those actually installed."""
    status = tesseract_status()
    wanted = [x for x in config.OCR_LANGS.split("+") if x]
    have = [x for x in wanted if x in status.get("langs", [])]
    return "+".join(have) if have else "eng"


def get_words(image_bgr: np.ndarray, recorded: Path | None = None):
    """Return (words, engine). Each word: text, conf, left, top, width, height, line key."""
    status = tesseract_status()
    if status["available"]:
        langs = _usable_langs()
        data = pytesseract.image_to_data(
            image_bgr, lang=langs, config="--oem 1 --psm 6",
            output_type=pytesseract.Output.DICT)
        words = []
        for i, text in enumerate(data["text"]):
            text = (text or "").strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            words.append({
                "text": text, "conf": conf,
                "left": int(data["left"][i]), "top": int(data["top"][i]),
                "width": int(data["width"][i]), "height": int(data["height"][i]),
                "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            })
        return words, f"tesseract {status['version']} ({langs})"

    if recorded and recorded.exists():
        raw = json.loads(recorded.read_text(encoding="utf-8"))
        for w in raw:
            w["line"] = tuple(w["line"])
        return raw, "recorded-sample"

    raise OCRUnavailable(
        "Tesseract OCR was not found. Install it (see README) and restart, "
        f"detail: {status.get('reason', 'unknown')}")
