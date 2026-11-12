# 🌾 L.E.A.D — Land Extraction, Analysis & Digitization
### Intelligent Land Record Digitization, GIS Cross-Verification & Human-in-the-Loop Review Platform

[![Live Demo on Vercel](https://img.shields.io/badge/Live%20Demo-lead--land--records.vercel.app-black?style=flat&logo=vercel)](https://lead-land-records.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/Image%20Processing-OpenCV-5C3EE8.svg)](https://opencv.org/)
[![Tesseract OCR](https://img.shields.io/badge/OCR-Tesseract-green.svg)](https://github.com/tesseract-ocr/tesseract)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Overview

**L.E.A.D** is an end-to-end prototype engineered for automated digitization and validation of complex historical land records (such as **Jamabandi** registers). 

Land records are typically degraded, skewed, and recorded in regional measurement systems. **L.E.A.D** restores uploaded scans, extracts tabular ledger entries via OCR, translates regional land units (e.g., *Kanal, Marla, Sarsahi, Karam*) to metric equivalents, cross-references physical records with Cadastral GIS layers, calculates dual-factor confidence scores, and intelligently routes discrepancies to human review queues.

---

## ✨ Key Features

- **Adaptive Image Preprocessing Pipeline**:
  - **CLAHE** (Contrast Limited Adaptive Histogram Equalization) for localized contrast enhancement.
  - **Sauvola Local Thresholding** computed with integral images for binarizing stained or aged parchment.
  - **Radon / Projection-Profile Deskewing** for precision page alignment.
  - **Morphological Table Structure Separation** to eliminate ledger border noise before OCR.
- **Multilingual OCR Engine**:
  - Word-level confidence mapping with Tesseract OCR supporting script expansion (`eng`, `hin`, `pan`).
- **Domain-Specific Unit Normalizer**:
  - Dynamic conversion for Punjabi and North Indian land systems:
    $$\text{1 Karam} = 5.5\text{ ft}$$
    $$\text{1 Sarsahi} = 1\text{ sq Karam} \approx 2.81\text{ m}^2$$
    $$\text{1 Marla} = 9\text{ Sarsahi} \quad | \quad \text{1 Kanal} = 20\text{ Marla} \quad | \quad \text{1 Killa} = 8\text{ Kanal}$$
- **GIS Cadastral Cross-Validation Engine**:
  - Automatic cross-checking of Khasra numbers against spatial GeoJSON parcels.
  - Dual tolerance matching: comparing reported ledger area vs. geometric GIS polygon area ($\le 2\%$ pass, $\le 10\%$ warning).
- **Dual-Factor Confidence Scoring**:
  - Combines visual clarity $c_v$ (geometric mean of word confidences) and semantic consistency $c_s$ (weighted business rule checks):
    $$C = c_v^\alpha \cdot c_s^{(1-\alpha)} \quad (\text{Default } \alpha = 0.5)$$
- **Human-in-the-Loop Review & Audit Tracking**:
  - High-confidence records are automatically approved; ambiguous rows are flagged with actionable explanations.
  - Manual edits are automatically archived to a `hard-examples` dataset for active-learning and OCR fine-tuning.
- **Interactive Web Interface & Static Demo**:
  - Full-stack UI with side-by-side original/processed document viewer and parcel inspection.
  - Standalone serverless static deployment support (`site/`) for GitHub Pages, Vercel, and Firebase.

---

## 🏗️ Architecture & Data Flow

```
┌──────────────┐     ┌───────────────────────┐     ┌─────────────────────┐
│ Scanned Page │ ──> │ Adaptive Preprocess   │ ──> │ OCR Engine          │
│ (PDF / Image)│     │ CLAHE + Sauvola + Deskew│    │ Tesseract Word Conf │
└──────────────┘     └───────────────────────┘     └──────────┬──────────┘
                                                              │
┌──────────────────────┐     ┌───────────────────────┐        │
│ Decision Engine      │ <── │ Cadastral Validation  │ <──────┴──────────┐
│ Auto-Accept vs Review│     │ GIS Polygon & Units   │  Tabular Extractor│
└──────────┬───────────┘     └───────────────────────┘  (Khewat, Khasra, │
           │                                             Owner, Area)    │
     ┌─────┴───────────────┐                                             │
     ▼                     ▼                                             │
┌──────────────┐   ┌───────────────┐                                     │
│ Auto-Accepted│   │ Review Queue  │ <───────────────────────────────────┘
│ Records      │   │ (Human-in-loop)
└──────────────┘   └───────┬───────┘
                           ▼
                   ┌───────────────┐
                   │ Hard Examples │ (Active Learning)
                   │ Export        │
                   └───────────────┘
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+**
- **Tesseract OCR**:
  - **Windows**: Install via [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and ensure it is added to your system `PATH`.
  - **macOS**: `brew install tesseract`
  - **Ubuntu / Debian**: `sudo apt install tesseract-ocr`

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/thyravikant/L.E.A.D.git
cd L.E.A.D

# Set up virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Tip for Linux / macOS / Git Bash:** You can also run `./ps.sh` for an automated setup and run.

### 2. Launch the Application

```bash
python run.py
```
- **Web App**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Testing Scenarios in the Demo

Click **"Try sample scan"** on the dashboard to test the built-in demo records:

| Khasra | System Decision | Trigger / Cause | Resolution Action |
|:---:|:---:|:---|:---|
| **1241** | ⚠️ Needs Review | Area mismatch: ledger specifies `10-0-0` (5,058 m²), while GIS cadastral polygon calculates 4,300 m². | Edit ledger area to `8-9-6` and click save. System re-validates and passes. |
| **1250** | ❌ Needs Review (Hard Fail) | Spatial mismatch: Khasra number is not present in the cadastral GIS layer. | Mark for manual field surveyor verification or spatial update. |
| **OCR Low-Conf** | ⚠️ Needs Review | Low word-level confidence (e.g. damaged name reading like *"Harhans"*). | Correct name in reviewer modal; saved automatically to `/api/hard-examples`. |
| **Clean Rows** | ✅ Auto-Accepted | High optical confidence ($c_v \ge 0.85$) and passed all semantic GIS validation rules. | Automatically indexed. |

---

## ⚙️ Configuration Reference

Configure platform behavior using environment variables:

| Variable | Default | Description |
|:---|:---:|:---|
| `LR_OCR_LANGS` | `eng` | Tesseract language codes (e.g., `eng+hin+pan`). |
| `LR_KARAM_FT` | `5.5` | Defined length of Karam in feet (standard Punjab = 5.5 ft). |
| `LR_ALPHA` | `0.5` | Weight balance factor between visual ($\alpha$) and semantic ($1-\alpha$) confidence. |
| `LR_AUTO_THRESHOLD` | `0.80` | Minimum aggregate confidence score required for auto-approval. |
| `LR_FIELD_CONF_OK` | `0.85` | Per-field optical confidence baseline. |
| `LR_DATA_DIR` | `./data` | File storage path for SQLite database, GeoJSON, and upload artifacts. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Host address and port for the FastAPI web server. |

---

## 📂 Repository Structure

```plaintext
L.E.A.D/
├── .github/workflows/    # CI/CD and GitHub Pages deployment actions
├── app/                  # FastAPI backend source
│   ├── config.py         # Global configuration & environment settings
│   ├── db.py             # SQLite database models & query operations
│   ├── extract.py        # Tabular rule parser & column segmenter
│   ├── geo.py            # Spatial GIS layer parser & polygon area calculator
│   ├── main.py           # FastAPI REST routes & request handlers
│   ├── ocr.py            # Tesseract OCR invocation & bounding box mapper
│   ├── pipeline.py       # Orchestration pipeline (Image -> OCR -> Validate)
│   ├── preprocess.py     # Image filters (Sauvola, CLAHE, Deskew, Grid cleaning)
│   ├── seed.py           # Synthetic cadastral parcel generator
│   ├── units.py          # Regional land unit conversion logic
│   └── validate.py       # Deterministic business rule validation engine
├── samples/              # Degraded test scans & synthetic generator (make_sample.py)
├── site/                 # Standalone static showcase (GitHub Pages / Firebase)
├── static/               # Dynamic web app assets (HTML, CSS, JS)
├── tests/                # Automated pytest validation suite
├── firebase.json         # Firebase hosting configuration
├── requirements.txt      # Python dependencies
└── run.py                # Server launcher script
```

---

## 🧪 Running Automated Tests

Run the full test suite with:

```bash
python -m pytest -v
```

---

## 🌐 Live Demo & Deployment

🚀 **Live Showcase**: **[lead-land-records.vercel.app](https://lead-land-records.vercel.app/)**

The static interactive preview (`site/`) is live and ready to run without backend dependencies (client-side verification with precomputed OCR results & local storage):

- **Vercel**: Deployed at [lead-land-records.vercel.app](https://lead-land-records.vercel.app/) with Root Directory set to `site/`.
- **GitHub Pages**: Automated via `.github/workflows/pages.yml`.
- **Firebase Hosting**: Configured via `firebase.json` (`firebase deploy --only hosting`).

> 💡 **Full Features vs. Static Demo**: The live Vercel showcase demonstrates record review, inline discrepancy corrections, interactive parcel search, and re-validation in the browser. Uploading custom unread scans and generating new OCR models runs via the local FastAPI backend (`python run.py`).

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
