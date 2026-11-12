# Land Record Workbench (SIH 26018 prototype)

A small, working prototype of an intelligent land record digitization and validation system:
upload a scanned Jamabandi page, and the app restores the image, reads it with OCR, converts
Punjab land units, checks every row against a cadastral (GIS) layer, scores confidence, and
routes doubtful rows to a human reviewer whose corrections are logged.

**Backend:** Python, FastAPI, SQLite, OpenCV, Tesseract. **Frontend:** plain HTML/CSS/JS (no build step).

## Run it

> Quick start on Linux/macOS/Git Bash: `./ps.sh` does steps 1-2 below and starts the app.

1. Install **Python 3.10+** and **Tesseract OCR**.
   - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki and add it to PATH
   - macOS: `brew install tesseract`
   - Ubuntu/Debian: `sudo apt install tesseract-ocr`
2. In this folder:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

3. Open **http://127.0.0.1:8000** and click **Try sample scan**.
   Use **Upload scan** for your own PNG/JPG/TIFF/PDF (first page of a PDF is read).

Run the tests with `python -m pytest -q` (18 tests). Interactive API docs: http://127.0.0.1:8000/docs

If Tesseract is missing, the page shows a warning; the bundled sample still works from a recorded
OCR result, but your own uploads need Tesseract.

## What to try in the demo

| Row | What happens | Why |
|---|---|---|
| 1241 | needs review (area mismatch) | ledger says 10-0-0 (5,058 m²), the GIS polygon is 4,300 m². Edit the area to `8-9-6` and save: it re-validates and becomes consistent. |
| 1250 | needs review (hard fail) | Khasra is not in the cadastral layer |
| Any low-confidence name | needs review | e.g. "Harhans" read with low OCR confidence; correct it and the fix is stored under **Dashboard > Hard examples** |
| Clean rows | auto-accepted | confidence and every rule pass |

Exact OCR output varies with the Tesseract version and image resolution, so a row or two may land
differently on your machine. That is expected.

## How it works

```
scan -> preprocess -> OCR -> row extraction -> unit normalizer -> validation -> confidence -> route
        CLAHE         Tesseract  Khewat|Khasra   Kanal-Marla-      6+ rules      c_v, c_s, C    auto-accept
        Sauvola       word       |Owner|Area    Sarsahi -> m²     incl. GIS                    or human review
        deskew        confidences                                  polygon area
        rule removal
```

- **Preprocessing** (`app/preprocess.py`): CLAHE contrast, Sauvola local thresholding via integral images,
  projection-profile deskew, morphological removal of table rulings so OCR sees text, not grid lines.
- **Units** (`app/units.py`): 1 Sarsahi = 1 sq Karam (Karam = 5.5 ft), 1 Marla = 9 Sarsahi, 1 Kanal = 20 Marla,
  1 Killa = 8 Kanal. Bigha, Biswa and Guntha are *deliberately not hard-coded* because values differ by state and
  era; add confirmed values to `EXTRA_UNITS_M2`.
- **Validation** (`app/validate.py`): Khasra format; Khasra exists in cadastral layer (hard rule); area parses;
  ledger area vs GIS polygon area (2% pass, 10% warn); owner name plausible; OCR confidence of every field; Khasra unique.
- **Confidence**: `c_v` = geometric mean of OCR word confidences, `c_s` = weighted rule pass rate (0 if a hard rule fails),
  `C = c_v^a * c_s^(1-a)` with a = 0.5. Auto-accept only if C >= 0.80 and no rule scores below 0.5.
- **Human in the loop**: edits are re-validated, written to an audit log, and every corrected field is saved as a
  "hard example" (`/api/hard-examples`) for later OCR fine-tuning.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `LR_OCR_LANGS` | `eng` | Tesseract languages, e.g. `eng+hin+pan` (install the matching language packs) |
| `LR_KARAM_FT` | `5.5` | Karam length in feet |
| `LR_ALPHA` | `0.5` | weight of visual vs semantic confidence |
| `LR_AUTO_THRESHOLD` | `0.80` | auto-accept threshold |
| `LR_FIELD_CONF_OK` | `0.85` | per-field OCR confidence considered safe |
| `LR_DATA_DIR` | `./data` | database and uploads location |
| `HOST`, `PORT` | `127.0.0.1`, `8000` | server bind |

## Project layout

```
app/        backend: main.py (API), pipeline.py, preprocess.py, ocr.py, extract.py, units.py,
            geo.py, validate.py, db.py, seed.py, config.py
static/     frontend: index.html, app.js, style.css
samples/    synthetic degraded Jamabandi scan + generator (make_sample.py)
tests/      pytest suite
data/       created at first run (SQLite DB, uploads, parcels.geojson); safe to delete to reset
```

## Honest limitations

- This is a **prototype**, not a production system. The OCR is stock Tesseract: no trained handwriting or
  Gurmukhi model, so handwritten or heavily degraded pages will be read poorly (the confidence scores and the
  review queue exist for exactly that reason).
- Row extraction is rule-based and assumes a four-column Khewat | Khasra | Owner | Area table.
- The cadastral layer is **synthetic** (8 demo parcels in `app/seed.py`). To use real data, replace
  `data/parcels.geojson` with a GeoJSON FeatureCollection whose features have `khasra_no`, `village`, `tehsil`
  properties (the area is computed from the polygon).
- Hindi/Punjabi OCR needs extra Tesseract language packs and has not been validated here.
- No login, no multi-user locking, SQLite only.

## Live demo (static site, no server)

`site/` is a pure static copy of the prototype (Dashboard, Review, Search records) with the sample scan
pre-processed. Edits, verify and reject run in the browser (saved in localStorage; **Reset demo** clears them).
Upload needs the Python backend above.

- **Vercel:** import the repo, set **Root Directory = `site`**, Framework = Other, no build command.
- **GitHub Pages:** Settings > Pages > Source = *GitHub Actions* (workflow in `.github/workflows/pages.yml`).
- **Firebase:** `firebase deploy --only hosting` (uses `firebase.json`).
