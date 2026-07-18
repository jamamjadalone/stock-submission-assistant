# Stock Submission Assistant

**A free, open-source, 100% offline desktop tool that checks your vector (AI/EPS), PNG, and photo files against the real technical submission requirements of Adobe Stock, Shutterstock, Freepik, Vecteezy, Depositphotos, and Dreamstime — before you upload.**

No internet connection required. No data ever leaves your computer. No fake "acceptance scores." Just real, measurable checks: resolution, DPI, color mode, live text detection, embedded raster detection, sharpness/noise/exposure analysis, and marketplace-by-marketplace compatibility reports — all computed locally with Python, Pillow, OpenCV, and PyMuPDF.

If you're a **microstock contributor**, **stock photographer**, **vector illustrator**, or **AI stock asset creator** looking for a **stock image checker**, **vector file validator**, **Adobe Stock rejection checker**, or **offline stock photo QA tool**, this project is for you.

---

## Table of Contents

- [Why this exists](#why-this-exists)
- [Features](#features)
- [What this tool does NOT do (and why)](#what-this-tool-does-not-do-and-why)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Building a Windows .exe](#building-a-windows-exe)
- [Project structure](#project-structure)
- [Supported marketplaces](#supported-marketplaces)
- [Tech stack](#tech-stack)
- [Contributing](#contributing)
- [FAQ](#faq)
- [License](#license)
- [Author](#author)

---

## Why this exists

Every stock contributor knows the pain: you spend hours preparing an icon set or a photo shoot, upload it, and days later it comes back **rejected** for something you could have caught yourself — a font that wasn't outlined, a resolution just under 4MP, a linked file reference, GPS metadata you forgot to strip.

**Stock Submission Assistant** catches these *technical* problems before you submit, using deterministic, explainable checks — not guesses, not AI hallucination, not a black-box "quality score." Every number in the report is either read directly from your file or computed with a named, documented algorithm.

## Features

### 🖼️ Vector module (AI / EPS)
- Artboard size, aspect ratio, PostScript/Illustrator version info
- Live/unoutlined text detection
- Embedded raster image detection
- Linked (external) file detection
- Hidden or locked layer detection
- Auto-fix suggestions for target size, padding, and scaling — pure math, no guessing

### 🎨 PNG module
- Exact resolution, megapixels, bit depth, DPI
- Exact transparency/occupancy measurement via the alpha channel
- ICC color profile presence check

### 📷 Photo module (JPG / JPEG / PNG)
- Resolution, DPI, color profile (RGB/sRGB)
- Sharpness via Laplacian variance (a standard, peer-reviewed blur-detection technique)
- Noise estimation, exposure/histogram analysis, highlight/shadow clipping
- Composition/occupancy estimate
- EXIF & GPS metadata leak detection

### 🛒 Marketplace compatibility checker
Compares your file's **actual measured resolution (megapixels)** — pixel dimensions for photos/PNGs, the real artwork bounding box (never the empty artboard) for vectors — against the published 4MP-style minimum of:
Adobe Stock · Shutterstock · Freepik · Vecteezy · Depositphotos · Dreamstime

Produces a clear **PASS / FAIL** per marketplace with the exact numbers — never a vague "might get rejected." Other structural details (live text, embedded raster, linked files, EXIF/GPS, color profile) are still shown in each file's own Analysis/Notes section.

### 🛠️ Auto-fix suggestions
When a file falls short of the MP minimum, get an instant suggested resize with exact pixel dimensions — and a **Save As New File** button that writes the fix to a brand-new file. Your original is never touched or overwritten.

### 📐 Size & megapixel calculator
Plan a new artwork's dimensions before you even open Illustrator or Photoshop. Type a width/height (or tap Portrait/Landscape), and instantly see the resulting megapixels and whether it clears the 4MP minimum — with one-click suggested sizes if it doesn't.

### 📦 Batch checker
- Analyze dozens of files in one run
- Export a CSV summary for spreadsheet QA workflows
- Detect near-duplicate images in a batch using a locally computed perceptual hash

### 📄 Report generator
Save `.txt`, `.json`, or `.csv` reports for your records or client delivery.

### 🖥️ Modern desktop UI
Dark-themed CustomTkinter interface with animated progress indicators, color-coded status badges, and a dedicated About tab.

## What this tool does NOT do (and why)

This project follows a strict **no-fake-analysis policy**. It will never show you:
- An "acceptance probability" or predicted approval score
- A sales or demand prediction
- Keyword/title relevance scoring
- Catalog-duplicate, trademark, or copyright detection
- Model/property release validity checks

All of the above require either a live connection to a marketplace's private servers/database or genuine human judgment — neither of which is possible offline. Wherever a check can't be done reliably offline, the app says exactly that instead of guessing. See [`RESEARCH.md`](RESEARCH.md) for the full breakdown of what's checkable offline per marketplace and what isn't.

## Screenshots

> Add your own screenshots to `assets/` and reference them here, e.g.:
> `![Vector module screenshot](assets/screenshot-vector.png)`

## Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/jamamjadalone/stock-submission-assistant.git
cd stock-submission-assistant
pip install -r requirements.txt
```

## Usage

```bash
python gui/app.py
```

1. Open the **Vector**, **PNG**, or **Photos** tab and choose a file.
2. Review the analysis, warnings, and marketplace compatibility results.
3. Click **Generate Report** to save a `.txt` or `.json` report.
4. Use the **Batch Checker** tab to validate an entire folder at once and export a CSV.

`PyMuPDF` enables full AI-file analysis; without it, AI files fall back to a limited text-scan mode (the app tells you which mode is active in the **Settings** tab).

## Building a Windows .exe

Full step-by-step PyInstaller instructions — hidden imports, one-file/no-console flags, icon setup, and a troubleshooting table — are in [`README-build.md`](README-build.md). Short version:

```bat
pip install pyinstaller
pyinstaller --name StockSubmissionAssistant --onefile --windowed ^
  --add-data "data;data" --collect-all customtkinter ^
  --hidden-import fitz --hidden-import cv2 gui\app.py
```

> If `pyinstaller` is not recognized as a command, use `python -m PyInstaller` instead (same tool, doesn't depend on PATH).

## Project structure

```
stock-submission-assistant/
├── core/                    # Analysis engine (no UI dependencies)
│   ├── raster_analysis.py   # JPG/PNG pixel + metadata analysis
│   ├── vector_analysis.py   # AI/EPS structural analysis
│   ├── marketplace_checker.py
│   ├── autofix_engine.py
│   ├── report_generator.py
│   └── batch_checker.py
├── gui/                      # CustomTkinter desktop UI
│   ├── app.py                # entry point
│   └── fix_actions.py
├── data/marketplace_rules.json
├── RESEARCH.md               # offline-feasibility research notes
├── requirements.txt
└── LICENSE
```

## Supported marketplaces

| Marketplace | Vector | PNG | Photo |
|---|---|---|---|
| Adobe Stock | ✅ | ✅ | ✅ |
| Shutterstock | ✅ | ✅ | ✅ |
| Freepik | ✅ | ✅ | ✅ |
| Vecteezy | ✅ | ✅ | ✅ |
| Depositphotos | ✅ | ✅ | ✅ |
| Dreamstime | ✅ | ✅ | ✅ |

## Tech stack

Python · CustomTkinter · Pillow · OpenCV · NumPy · PyMuPDF

## Contributing

Issues and pull requests are welcome — especially:
- Additional offline-checkable rules for any of the six marketplaces
- Bug reports where a check doesn't match a marketplace's current published spec
- UI/UX improvements

Please open an issue before submitting a large PR so we can discuss the approach.

## FAQ

**Does this app upload my images anywhere?**
No. It has no network calls at all. All analysis runs locally on your machine.

**Can it guarantee my file will be accepted?**
No, and it will never claim to. It only checks what's technically measurable offline. Final moderation is always a human/AI decision on the marketplace's own servers.

**Does it support SVG?**
Not currently — the vector module focuses on AI and EPS, the formats most commonly required by major stock marketplaces.

**Is it free?**
Yes, MIT licensed, free for personal and commercial use.

## License

MIT — see [LICENSE](LICENSE).

## Author

**Jam Amjad Rasheed**
YouTube: [@jamamjadrasheed](https://www.youtube.com/@jamamjadrasheed)
