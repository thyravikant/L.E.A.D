"""End-to-end processing: load -> preprocess -> OCR -> extract -> validate -> store."""
from pathlib import Path

import cv2
import numpy as np

from . import config, db, extract, ocr, preprocess, validate
from .seed import load_parcels


def load_image(path: Path) -> np.ndarray:
    """Read an image or the first page of a PDF as a BGR array."""
    if path.suffix.lower() == ".pdf":
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # older PyMuPDF
        with fitz.open(path) as pdf:
            pix = pdf[0].get_pixmap(dpi=200)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            if pix.n == 1:
                return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read the file as an image or PDF.")
    return img


def process(path: Path, filename: str, recorded: Path | None = None) -> int:
    bgr = load_image(path)
    processed, restored, metrics = preprocess.preprocess(bgr)
    words, engine = ocr.get_words(processed, recorded)
    rows = extract.parse_rows(words)
    metrics["words"] = len(words)

    _, parcels = load_parcels()
    doc_id = db.create_document(filename, engine, metrics)
    cv2.imwrite(str(config.UPLOAD_DIR / f"{doc_id}_original.png"), restored)
    cv2.imwrite(str(config.UPLOAD_DIR / f"{doc_id}_processed.png"), processed)

    doc_khasras = [r["fields"]["khasra"]["text"] for r in rows]
    for idx, row in enumerate(rows):
        f = row["fields"]
        area_m2 = row["area"]["area_m2"] if row["area"] else None
        rec = {
            "khewat": f["khewat"]["text"], "khasra": f["khasra"]["text"],
            "owner": f["owner"]["text"], "area_raw": f["area"]["text"], "area_m2": area_m2,
            "field_conf": {k: v["conf"] for k, v in f.items()},
        }
        result = validate.validate(rec, parcels, doc_khasras)
        c_joint = validate.joint_confidence(row["c_v"], result["c_s"])
        db.add_record(doc_id, idx, {
            **rec,
            "box": row["box"],
            "field_boxes": {k: v["box"] for k, v in f.items()},
            "field_conf": {k: v["conf"] for k, v in f.items()},
            "c_v": row["c_v"], "c_s": result["c_s"], "c_joint": c_joint,
            "rules": result["rules"], "parcel": result["parcel"],
            "route": validate.route(c_joint, result["rules"]),
        })
    return doc_id
