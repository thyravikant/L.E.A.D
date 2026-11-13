# 🌾 L.E.A.D — Land Evaluation, Authentication & Digitization

**Turn degraded land-record scans into validated, GIS-verified digital records, with a person in the loop only where the machine is unsure.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-lead--land--records.vercel.app-black?logo=vercel)](https://lead-land-records.vercel.app/)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![OpenCV](https://img.shields.io/badge/Image%20Processing-OpenCV-5C3EE8)
![Tesseract](https://img.shields.io/badge/OCR-Tesseract-green)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)



**Problem Statement ID**: SIH 26018 

 **Live demo**:  https://lead-land-records.vercel.app/


## 📑 Contents

[Problem](#-the-problem) · [Solution](#-our-solution) · [Features](#-key-features) · [How it works](#-how-it-works) · [Scoring](#-confidence-scoring--decision-rule) · [Units](#-land-unit-normalization) · [Demo](#-demo-walkthrough) · [Quick start](#-quick-start) · [Config](#-configuration) · [API](#-api) · [Structure](#-project-structure) · [Tests](#-testing) · [Deployment](#-deployment) · [Results](#-results) · [Roadmap](#-limitations--roadmap) · [License](#-license)

---

## 🧩 The Problem

Land records such as **Jamabandi** registers are the legal backbone of property ownership, yet most exist only as aged, stained, skewed paper scans. Digitizing them is hard because:

- **Poor scan quality:** fading, stains, uneven lighting, tilted pages and heavy table borders break standard OCR.
- **Regional measurement systems:** areas are written in Kanal, Marla and Sarsahi, not square metres.
- **Silent errors:** one misread digit in an area or Khasra number can create a wrong ownership record.
- **No cross-checking:** ledgers are rarely compared against the cadastral map, so mismatches go unnoticed.
- **All-or-nothing review:** either everything is checked by hand (slow) or nothing is (unsafe).

## 💡 Our Solution

L.E.A.D is an end-to-end pipeline that **restores** each scan, **extracts** the ledger table with OCR, **normalizes** regional units, **verifies** every row against cadastral GIS polygons, and **scores** how much it trusts each row. High-confidence rows are accepted automatically. Everything else goes to a human reviewer with a plain-language reason for the flag. Every correction is saved as training data to improve the OCR.

---

## ✨ Key Features

| Area | What L.E.A.D does |
|---|---|
| **Image restoration** | CLAHE contrast enhancement, Sauvola local thresholding (integral-image implementation), Radon/projection-profile deskewing, morphological removal of table borders |
| **OCR** | Tesseract with word-level confidence scores; English, Hindi and Punjabi (`eng+hin+pan`) |
| **Table extraction** | Rule-based column segmentation into Khewat, Khasra, Owner and Area |
| **Unit normalization** | Kanal–Marla–Sarsahi (plus Karam, Killa) converted to square metres |
| **GIS cross-validation** | Khasra numbers matched against GeoJSON parcels; ledger area compared with polygon area (≤ 2% pass, ≤ 10% warning) |
| **Dual confidence score** | Combines OCR clarity and rule-based consistency into one number per row |
| **Human-in-the-loop review** | Side-by-side original/processed scan viewer, parcel map, inline editing with instant re-validation |
| **Active-learning data** | Every correction is stored in a `hard-examples` set (OCR read → corrected value → OCR confidence) |

---

## 🏗️ How It Works

```
 Scanned page ──► Preprocess ──► OCR ──► Table extraction ──► Unit normalization
 (PDF / image)   CLAHE, Sauvola   Tesseract   Khewat, Khasra,     Kanal/Marla/Sarsahi
                 deskew, grid     + word      Owner, Area         → square metres
                 removal          confidence
                                                                        │
                                                                        ▼
                    ┌──────────── Decision engine ◄──── GIS + rule validation
                    │            (auto-accept vs review)   Khasra exists? Area matches?
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  Auto-accepted            Review queue ──► Reviewer edits ──► Re-validate
     records               (with reasons)                          │
                                                                   ▼
                                                      Hard-examples dataset
                                                     (OCR fine-tuning signal)
```

**Modules** (`app/`): `preprocess.py` → `ocr.py` → `extract.py` → `units.py` → `geo.py` + `validate.py` → `pipeline.py` (orchestration) → `main.py` (API) → `db.py` (SQLite).

---

## 📐 Confidence Scoring & Decision Rule

Each row gets two scores:

- **Visual confidence `cv`** is the *geometric mean* of the OCR word confidences in the row, so one badly read word pulls the whole row down.
- **Semantic confidence `cs`** is the weighted pass rate of the validation rules (valid unit format, Khasra found in GIS, area within tolerance, and so on). A failed **hard** rule sets `cs = 0`.

They combine into the joint confidence:

```
C = cv^α · cs^(1−α)        (default α = 0.5)
```

**A row is auto-accepted only if `C ≥ 0.80` and no individual rule scores below 0.5.** Anything else goes to review with the failing rule shown as the reason. `α` and the threshold are configurable (see [Results](#-results) for how they were chosen).

---

## 📏 Land Unit Normalization

Standard Punjab system (Karam length is configurable):

| Unit | Definition | ≈ Metric |
|---|---|---|
| 1 Karam | 5.5 ft | 1.676 m |
| 1 Sarsahi | 1 sq Karam | 2.81 m² |
| 1 Marla | 9 Sarsahi | 25.29 m² |
| 1 Kanal | 20 Marla | 505.86 m² |
| 1 Killa | 8 Kanal | 4,046.9 m² |

Ledger areas are written as **Kanal-Marla-Sarsahi**; for example `10-0-0` = 10 Kanal ≈ 5,058 m².

---

## 🧪 Demo Walkthrough

Open the dashboard and click **Try sample scan**. The demo uses a degraded sample scan and synthetic cadastral polygons.

| Row | Decision | Why | What to do |
|---|---|---|---|
| **Khasra 1241** | ⚠️ Needs review | Ledger area `10-0-0` ≈ 5,058 m², GIS polygon ≈ 4,300 m² (outside tolerance) | Edit area to `8-9-6` and save; it re-validates and passes |
| **Khasra 1250** | ❌ Needs review (hard fail) | Khasra not found in the cadastral layer | Flag for field-surveyor verification |
| **Low-confidence name** | ⚠️ Needs review | Damaged text read as *"Harhans"* (low word confidence) | Correct the name; saved to `/api/hard-examples` |
| **Clean rows** | ✅ Auto-accepted | High OCR confidence and all rules pass | Nothing, automatically indexed |

> **Static vs. full demo:** the hosted Vercel site (`site/`) runs in the browser using **precomputed OCR results** to demonstrate review, editing, parcel search and re-validation. Uploading *new* scans runs the real OCR pipeline through the local FastAPI backend (`python run.py`).

---

## 🚀 Quick Start

**Prerequisites:** Python 3.10+ and Tesseract OCR (install the `hin` and `pan` language data for Hindi/Punjabi).

- Windows: [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), then add it to `PATH`
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`

```bash
git clone https://github.com/thyravikant/L.E.A.D.git
cd L.E.A.D

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux / macOS:         source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

On Linux, macOS or Git Bash you can run `./ps.sh` instead for automated setup and launch.

| URL | What |
|---|---|
| http://127.0.0.1:8000 | Web app |
| http://127.0.0.1:8000/docs | Swagger API docs |
| http://127.0.0.1:8000/redoc | ReDoc |

---

## ⚙️ Configuration

Set as environment variables:

| Variable | Default | Description |
|---|---|---|
| `LR_OCR_LANGS` | `eng` | Tesseract languages, e.g. `eng+hin+pan` |
| `LR_KARAM_FT` | `5.5` | Length of a Karam in feet |
| `LR_ALPHA` | `0.5` | Weight of visual vs. semantic confidence |
| `LR_AUTO_THRESHOLD` | `0.80` | Minimum joint confidence for auto-accept |
| `LR_FIELD_CONF_OK` | `0.85` | Per-field OCR confidence baseline |
| `LR_DATA_DIR` | `./data` | SQLite DB, GeoJSON and upload storage |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Server bind address |

---

## 🔌 API

Interactive docs are served at `/docs`. Main capabilities:

- Upload a scan and run the full pipeline
- List records with their decision status and reasons
- Edit a field and re-validate the row
- `GET /api/hard-examples`: export reviewer corrections as training data

_Replace this list with the exact endpoints from `app/main.py`._

---

## 📂 Project Structure

```
L.E.A.D/
├── .github/workflows/   # CI and deployment
├── app/                 # FastAPI backend
│   ├── config.py        # Settings and environment variables
│   ├── db.py            # SQLite models and queries
│   ├── extract.py       # Table parsing and column segmentation
│   ├── geo.py           # GeoJSON parsing and polygon area
│   ├── main.py          # REST routes
│   ├── ocr.py           # Tesseract wrapper with word confidences
│   ├── pipeline.py      # Image → OCR → validate orchestration
│   ├── preprocess.py    # CLAHE, Sauvola, deskew, grid removal
│   ├── seed.py          # Synthetic cadastral parcel generator
│   ├── units.py         # Land unit conversion
│   └── validate.py      # Rule engine and scoring
├── samples/             # Degraded test scans and generator (make_sample.py)
├── site/                # Static demo (Vercel / Pages / Firebase)
├── static/              # Web app assets (HTML, CSS, JS)
├── tests/               # pytest suite
├── firebase.json
├── requirements.txt
└── run.py
```

---

## ✅ Testing

```bash
python -m pytest -v
```

---

## 🌐 Deployment

| Target | How |
|---|---|
| **Vercel** (live) | Project root directory set to `site/` |
| **GitHub Pages** (optional) | `.github/workflows/pages.yml`; requires Settings → Pages → Source: GitHub Actions |
| **Firebase Hosting** (optional) | `firebase deploy --only hosting` |
| **Full backend** | `python run.py` on any machine with Python and Tesseract |

---

## 📈 Results

_Fill in with your own measurements before submission._

| Metric | Value |
|---|---|
| OCR word accuracy, raw scan | _x %_ |
| OCR word accuracy, after preprocessing | _y %_ |
| Rows auto-accepted | _z %_ |
| Precision of auto-accepted rows | _p %_ |
| Errors caught by GIS check that OCR confidence alone missed | _n_ |
| Average time per page | _t s_ |
| Sample set | _N pages, source, degradation type_ |

**Threshold choice:** _explain how `α = 0.5` and `0.80` were selected, for example by sweeping thresholds on the sample set._

---

## 🚧 Limitations & Roadmap

**Current limitations**
- The hosted demo uses precomputed OCR and **synthetic** cadastral polygons.
- Unit rules target the Punjab Kanal–Marla–Sarsahi system.
- Table extraction is rule-based and tuned to Jamabandi-style layouts.
- Hindi/Punjabi accuracy depends on Tesseract language models and scan quality.

**Roadmap**
- [ ] Import real state cadastral GeoJSON/shapefiles
- [ ] Fine-tune OCR using the exported hard examples
- [ ] Support more states and unit systems
- [ ] Layout-aware detection of merged and handwritten cells
- [ ] Batch processing and reviewer assignment queue
- [ ] Role-based access and full audit trail

---

## 📄 License

Released under the [MIT License](LICENSE).
