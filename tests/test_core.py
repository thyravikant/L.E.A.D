import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config, geo, preprocess, units, validate
from app.main import app


# ----------------------------------------------------------------- units
def test_kanal_marla_sarsahi_to_m2():
    r = units.parse_area("8-4-0", 5.5)
    # 8 kanal 4 marla = 164 marla; 1 marla = 9 * 30.25 sq ft
    expected = 164 * 9 * 30.25 * 0.09290304
    assert math.isclose(r["area_m2"], expected, rel_tol=1e-4)


def test_labelled_area():
    a = units.parse_area("8 Kanal 4 Marla", 5.5)["area_m2"]
    b = units.parse_area("8-4-0", 5.5)["area_m2"]
    assert math.isclose(a, b, rel_tol=1e-6)


def test_garbage_area_is_none():
    assert units.parse_area("abc", 5.5) is None


def test_karam_changes_result():
    assert units.parse_area("1-0-0", 5.0)["area_m2"] < units.parse_area("1-0-0", 5.5)["area_m2"]


# ------------------------------------------------------------------- geo
def test_polygon_area_of_square():
    lat = 30.97
    dlat = 100 / 111_320.0
    dlon = 100 / (111_320.0 * math.cos(math.radians(lat)))
    ring = [[76.5, lat], [76.5 + dlon, lat], [76.5 + dlon, lat + dlat], [76.5, lat + dlat], [76.5, lat]]
    assert math.isclose(geo.polygon_area_m2({"type": "Polygon", "coordinates": [ring]}), 10_000, rel_tol=0.01)


# ------------------------------------------------------------ preprocess
def test_sauvola_separates_dark_text_on_uneven_background():
    img = np.tile(np.linspace(120, 230, 200, dtype=np.uint8), (100, 1))
    img[40:44, 20:180] = 20  # a dark stroke
    out = preprocess.sauvola(img)
    assert out[41, 100] == 0 and out[10, 100] == 255


def test_rulings_removed_but_text_kept():
    b = np.full((200, 400), 255, np.uint8)
    b[100, :] = 0            # long horizontal rule
    b[50:60, 50:55] = 0      # short text-like stroke
    out, share = preprocess.remove_rulings(b, min_len=70)
    assert out[100, 200] == 255 and out[55, 52] == 0 and share > 0


# -------------------------------------------------------------- validate
PARCELS = {"10": {"khasra_no": "10", "village": "V", "area_m2": 1000.0}}


def _rec(**kw):
    base = dict(khasra="10", owner="Gurmeet Kaur", area_raw="x", area_m2=1005.0,
                field_conf={"khasra": 0.95, "owner": 0.95})
    return {**base, **kw}


def test_clean_record_is_auto_accepted():
    res = validate.validate(_rec(), PARCELS, ["10"])
    c = validate.joint_confidence(0.95, res["c_s"])
    assert validate.route(c, res["rules"]) == "auto_accepted"


def test_unknown_khasra_is_hard_fail():
    res = validate.validate(_rec(khasra="99"), PARCELS, ["99"])
    assert res["c_s"] == 0.0
    assert validate.route(validate.joint_confidence(0.99, res["c_s"]), res["rules"]) == "needs_review"


def test_area_mismatch_goes_to_review():
    res = validate.validate(_rec(area_m2=1300.0), PARCELS, ["10"])
    assert validate.route(validate.joint_confidence(0.95, res["c_s"]), res["rules"]) == "needs_review"


def test_low_ocr_confidence_goes_to_review():
    res = validate.validate(_rec(field_conf={"owner": 0.5}), PARCELS, ["10"])
    assert validate.route(validate.joint_confidence(0.95, res["c_s"]), res["rules"]) == "needs_review"


def test_duplicate_khasra_penalised():
    res = validate.validate(_rec(), PARCELS, ["10", "10"])
    assert any(r["name"].startswith("Khasra unique") and r["score"] == 0 for r in res["rules"])


def test_joint_confidence_is_geometric_mean():
    assert math.isclose(validate.joint_confidence(0.64, 1.0), 0.8, rel_tol=1e-3)  # alpha = 0.5


# ------------------------------------------------------------------- API
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sample_flow(client):
    doc = client.post("/api/demo/sample").json()
    recs = doc["records"]
    assert len(recs) == 6
    by_k = {r["khasra"]: r for r in recs}
    assert by_k["1241"]["status"] == "needs_review"      # area mismatch vs GIS
    assert by_k["1250"]["status"] == "needs_review"      # parcel absent from cadastral layer
    assert by_k["1257/3"]["status"] == "auto_accepted"


def test_edit_revalidates_and_logs_correction(client):
    doc = client.post("/api/demo/sample").json()
    r = next(x for x in doc["records"] if x["khasra"] == "1241")
    out = client.patch(f"/api/records/{r['id']}", json={"area_raw": "8-9-6"}).json()
    assert out["status"] == "edited"
    assert out["area_m2"] != r["area_m2"]
    ex = client.get("/api/hard-examples").json()
    assert any(e["record_id"] == r["id"] and e["field"] == "area" for e in ex)


def test_verify_reject_and_audit(client):
    doc = client.post("/api/demo/sample").json()
    rid = doc["records"][0]["id"]
    assert client.post(f"/api/records/{rid}/verify", json={"note": "ok"}).json()["status"] == "verified"
    assert client.post(f"/api/records/{rid}/reject").json()["status"] == "rejected"
    assert [a["action"] for a in client.get(f"/api/records/{rid}/audit").json()][-2:] == ["verified", "rejected"]


def test_rejects_bad_upload_type(client):
    r = client.post("/api/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


def test_serves_frontend(client):
    assert client.get("/").status_code == 200
    assert "Land Record Workbench" in client.get("/").text
