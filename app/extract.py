"""Rule-based key-value extraction of Jamabandi-style ledger rows.

Expected column order per row:  Khewat | Khasra | Owner name(s) | Area
The Area column may be K-M-S ("8-4-0") or labelled ("8 Kanal 4 Marla").
"""
import math
import re
from collections import defaultdict

from . import config
from .units import parse_area

_STRIP = str.maketrans({c: " " for c in "|[]{}()_~"})
_DASH = re.compile(r"[‐-―−]")
KHASRA_RE = re.compile(r"^\d{1,5}(?:/\d{1,3})*(?:/min)?$", re.I)


def norm_khasra(text: str) -> str:
    text = text.replace("\\", "/")
    # OCR often reads '/' as l, I or | between digits
    return re.sub(r"(?<=\d)[lI|](?=\d)", "/", text)


def _clip(conf_pct: float) -> float:
    return min(max(conf_pct / 100.0, 0.01), 0.99)


def _union(boxes):
    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[0] + b[2] for b in boxes)
    y2 = max(b[1] + b[3] for b in boxes)
    return [x1, y1, x2 - x1, y2 - y1]


def _field(tokens):
    text = " ".join(t["text"] for t in tokens)
    conf = sum(_clip(t["conf"]) for t in tokens) / len(tokens)
    box = _union([(t["left"], t["top"], t["width"], t["height"]) for t in tokens])
    return {"text": text, "conf": round(conf, 3), "box": box}


def _line_tokens(line_words):
    tokens = []
    for w in sorted(line_words, key=lambda w: w["left"]):
        text = _DASH.sub("-", w["text"]).translate(_STRIP).strip()
        for piece in text.split():
            tokens.append({**w, "text": piece})
    return tokens


def parse_rows(words):
    """Group OCR words into lines and return structured ledger rows."""
    lines = defaultdict(list)
    for w in words:
        lines[tuple(w["line"])].append(w)

    rows = []
    for key in sorted(lines, key=lambda k: min(w["top"] for w in lines[k])):
        toks = _line_tokens(lines[key])
        if len(toks) < 4 or not re.fullmatch(r"\d{1,5}", toks[0]["text"]):
            continue
        khasra_text = norm_khasra(toks[1]["text"])
        if not KHASRA_RE.match(khasra_text):
            continue
        j = next((i for i in range(2, len(toks)) if re.search(r"\d", toks[i]["text"])), None)
        if j is None or j == 2:
            continue
        toks[1] = {**toks[1], "text": khasra_text}
        fields = {
            "khewat": _field(toks[0:1]),
            "khasra": _field(toks[1:2]),
            "owner": _field(toks[2:j]),
            "area": _field(toks[j:]),
        }
        confs = [_clip(t["conf"]) for t in toks]
        c_v = math.exp(sum(math.log(c) for c in confs) / len(confs))
        area = parse_area(fields["area"]["text"], config.KARAM_FT)
        rows.append({
            "fields": fields,
            "box": _union([(t["left"], t["top"], t["width"], t["height"]) for t in toks]),
            "c_v": round(c_v, 4),
            "area": area,
        })
    return rows
