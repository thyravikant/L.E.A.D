"""FastAPI backend + static frontend."""
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, ocr, pipeline, validate
from .seed import ensure_parcels, load_parcels

app = FastAPI(title="Land Record Digitization and Validation (prototype)", version="0.1.0")

ALLOWED = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"}
EDITABLE = ("khewat", "khasra", "owner", "area_raw")
FIELD_KEY = {"khewat": "khewat", "khasra": "khasra", "owner": "owner", "area_raw": "area"}


@app.on_event("startup")
def startup():
    db.init()
    ensure_parcels()


@app.exception_handler(ocr.OCRUnavailable)
def ocr_unavailable(_, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# ------------------------------------------------------------------ health
@app.get("/api/health")
def health():
    return {"status": "ok", "tesseract": ocr.tesseract_status(), "ocr_langs": config.OCR_LANGS}


# --------------------------------------------------------------- documents
def _run(path: Path, filename: str, recorded: Path | None = None):
    try:
        doc_id = pipeline.process(path, filename, recorded)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db.get_document(doc_id)


@app.post("/api/documents")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use: {', '.join(sorted(ALLOWED))}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=config.UPLOAD_DIR) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        return _run(tmp_path, file.filename or "upload" + suffix)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/demo/sample")
def demo_sample():
    path = config.SAMPLES_DIR / "sample_jamabandi.png"
    return _run(path, "sample_jamabandi.png", config.SAMPLES_DIR / "sample_ocr_words.json")


@app.get("/api/documents")
def documents():
    return db.list_documents()


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@app.get("/api/documents/{doc_id}/image")
def document_image(doc_id: int, kind: str = "processed"):
    if kind not in ("original", "processed"):
        raise HTTPException(400, "kind must be 'original' or 'processed'")
    path = config.UPLOAD_DIR / f"{doc_id}_{kind}.png"
    if not path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, media_type="image/png")


# ----------------------------------------------------------------- records
class RecordEdit(BaseModel):
    khewat: str | None = None
    khasra: str | None = None
    owner: str | None = None
    area_raw: str | None = None


class Note(BaseModel):
    note: str = ""


@app.patch("/api/records/{rid}")
def edit_record(rid: int, body: RecordEdit):
    rec = db.get_record(rid)
    if not rec:
        raise HTTPException(404, "Record not found")
    new = {f: getattr(body, f).strip() for f in EDITABLE if getattr(body, f) is not None}
    changed = {f: v for f, v in new.items() if v != rec[f]}
    if not changed:
        return rec
    for f, v in changed.items():
        key = FIELD_KEY[f]
        db.add_correction(rec, key, rec[f], v, rec["field_conf"].get(key), rec["field_boxes"].get(key))
    merged = {f: rec[f] for f in EDITABLE} | changed

    doc = db.get_document(rec["doc_id"])
    doc_khasras = [merged["khasra"] if r["id"] == rid else r["khasra"] for r in doc["records"]]
    _, parcels = load_parcels()
    # text typed by a reviewer counts as fully confident
    field_conf = {**rec["field_conf"], **{FIELD_KEY[f]: 1.0 for f in changed}}
    res = validate.revalidate(merged, rec["c_v"], parcels, doc_khasras, field_conf)
    db.update_record(rid, **merged, area_m2=res["area_m2"], c_s=res["c_s"], c_joint=res["c_joint"],
                     rules=res["rules"], parcel=res["parcel"], route=res["route"], status="edited",
                     field_conf=field_conf)
    db.add_audit(rid, "edited", ", ".join(f"{k}: {rec[k]!r} -> {v!r}" for k, v in changed.items()))
    return db.get_record(rid)


def _set_status(rid: int, status: str, note: str):
    if not db.get_record(rid):
        raise HTTPException(404, "Record not found")
    db.update_record(rid, status=status, note=note)
    db.add_audit(rid, status, note)
    return db.get_record(rid)


@app.post("/api/records/{rid}/verify")
def verify(rid: int, body: Note = Note()):
    return _set_status(rid, "verified", body.note)


@app.post("/api/records/{rid}/reject")
def reject(rid: int, body: Note = Note()):
    return _set_status(rid, "rejected", body.note)


@app.get("/api/records/{rid}/audit")
def audit(rid: int):
    return db.list_audit(rid)


# ------------------------------------------------------- map / dashboard
@app.get("/api/parcels")
def parcels():
    gj, _ = load_parcels()
    return gj


@app.get("/api/stats")
def stats():
    return db.stats()


@app.get("/api/hard-examples")
def hard_examples():
    """Reviewer corrections: the training signal for incremental model adaptation."""
    return db.list_corrections()


app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
