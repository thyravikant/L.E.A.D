"""SQLite storage: documents, extracted records, reviewer corrections (hard examples)."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    created REAL NOT NULL,
    engine TEXT,
    metrics TEXT,
    width INTEGER, height INTEGER
);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    row_index INTEGER,
    khewat TEXT, khasra TEXT, owner TEXT, area_raw TEXT,
    area_m2 REAL,
    box TEXT, field_boxes TEXT, field_conf TEXT,
    c_v REAL, c_s REAL, c_joint REAL,
    rules TEXT, parcel TEXT,
    route TEXT, status TEXT, note TEXT,
    updated REAL
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL, doc_id INTEGER NOT NULL,
    field TEXT, old_value TEXT, new_value TEXT,
    field_conf REAL, box TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER, action TEXT, detail TEXT, ts REAL
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


_JSON_COLS = ("box", "field_boxes", "field_conf", "rules", "parcel", "metrics")


def _row(r):
    d = dict(r)
    for k in _JSON_COLS:
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k])
    return d


def create_document(filename, engine, metrics):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO documents (filename, created, engine, metrics, width, height) VALUES (?,?,?,?,?,?)",
            (filename, time.time(), engine, json.dumps(metrics), metrics["width"], metrics["height"]))
        return cur.lastrowid


def add_record(doc_id, idx, rec):
    with conn() as c:
        cur = c.execute(
            """INSERT INTO records (doc_id,row_index,khewat,khasra,owner,area_raw,area_m2,box,field_boxes,
               field_conf,c_v,c_s,c_joint,rules,parcel,route,status,note,updated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc_id, idx, rec["khewat"], rec["khasra"], rec["owner"], rec["area_raw"], rec["area_m2"],
             json.dumps(rec["box"]), json.dumps(rec["field_boxes"]), json.dumps(rec["field_conf"]),
             rec["c_v"], rec["c_s"], rec["c_joint"], json.dumps(rec["rules"]), json.dumps(rec["parcel"]),
             rec["route"], rec["route"], "", time.time()))
        rid = cur.lastrowid
        c.execute("INSERT INTO audit (record_id, action, detail, ts) VALUES (?,?,?,?)",
                  (rid, "extracted", f"route={rec['route']} C={rec['c_joint']}", time.time()))
        return rid


def get_document(doc_id):
    with conn() as c:
        d = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not d:
            return None
        recs = c.execute("SELECT * FROM records WHERE doc_id=? ORDER BY row_index", (doc_id,)).fetchall()
        doc = _row(d)
        doc["records"] = [_row(r) for r in recs]
        return doc


def list_documents():
    with conn() as c:
        rows = c.execute(
            """SELECT d.id, d.filename, d.created, d.engine,
                      COUNT(r.id) AS n_records,
                      SUM(CASE WHEN r.status='needs_review' THEN 1 ELSE 0 END) AS n_review
               FROM documents d LEFT JOIN records r ON r.doc_id=d.id
               GROUP BY d.id ORDER BY d.id DESC""").fetchall()
        return [dict(r) for r in rows]


def get_record(rid):
    with conn() as c:
        r = c.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return _row(r) if r else None


def update_record(rid, **cols):
    cols["updated"] = time.time()
    sets = ", ".join(f"{k}=?" for k in cols)
    vals = [json.dumps(v) if k in _JSON_COLS else v for k, v in cols.items()]
    with conn() as c:
        c.execute(f"UPDATE records SET {sets} WHERE id=?", (*vals, rid))


def add_correction(rec, field, old, new, field_conf, box):
    with conn() as c:
        c.execute(
            "INSERT INTO corrections (record_id,doc_id,field,old_value,new_value,field_conf,box,ts) VALUES (?,?,?,?,?,?,?,?)",
            (rec["id"], rec["doc_id"], field, old, new, field_conf, json.dumps(box), time.time()))


def add_audit(rid, action, detail=""):
    with conn() as c:
        c.execute("INSERT INTO audit (record_id, action, detail, ts) VALUES (?,?,?,?)",
                  (rid, action, detail, time.time()))


def list_corrections():
    with conn() as c:
        rows = c.execute("SELECT * FROM corrections ORDER BY id DESC LIMIT 200").fetchall()
        return [_row(r) for r in rows]


def list_audit(rid):
    with conn() as c:
        rows = c.execute("SELECT * FROM audit WHERE record_id=? ORDER BY id", (rid,)).fetchall()
        return [dict(r) for r in rows]


def stats():
    with conn() as c:
        n_docs = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        by_status = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) AS n FROM records GROUP BY status")}
        avg = c.execute("SELECT AVG(c_joint), AVG(c_v), AVG(c_s) FROM records").fetchone()
        n_corr = c.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        stp_docs = c.execute(
            """SELECT COUNT(*) FROM documents d WHERE EXISTS (SELECT 1 FROM records r WHERE r.doc_id=d.id)
               AND NOT EXISTS (SELECT 1 FROM records r WHERE r.doc_id=d.id AND r.route!='auto_accepted')"""
        ).fetchone()[0]
    total = sum(by_status.values())
    auto = by_status.get("auto_accepted", 0)
    return {
        "documents": n_docs, "records": total, "by_status": by_status,
        "record_stp_rate": round(auto / total, 3) if total else None,
        "page_stp_rate": round(stp_docs / n_docs, 3) if n_docs else None,
        "avg_joint": round(avg[0], 3) if avg[0] is not None else None,
        "avg_visual": round(avg[1], 3) if avg[1] is not None else None,
        "avg_semantic": round(avg[2], 3) if avg[2] is not None else None,
        "corrections": n_corr,
    }
