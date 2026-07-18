# Building Instructions

See the main [README.md](README.md) for general usage. This file contains the detailed Windows .exe build guide.

## Building StockSubmissionAssistant.exe (Windows, PyInstaller)

Run these commands on a **Windows machine** with Python 3.10+ and the
project's virtualenv active (PyInstaller must build on the target OS —
you cannot cross-build a Windows .exe from Linux/macOS).

> **Note:** If the `pyinstaller` command gives `'pyinstaller' is not
> recognized as an internal or external command` (a common PATH issue on
> Windows), use `python -m PyInstaller` instead of `pyinstaller` in every
> command below — it calls the same tool without depending on PATH.
> Example: `python -m PyInstaller --name StockSubmissionAssistant --onefile ...`

### 1. Install build tooling

```bat
pip install -r requirements.txt
pip install pyinstaller
```

### 2. One-file, no-console build

```bat
pyinstaller ^
  --name StockSubmissionAssistant ^
  --onefile ^
  --windowed ^
  --icon assets\app_icon.ico ^
  --add-data "data;data" ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import customtkinter ^
  --collect-all customtkinter ^
  --hidden-import fitz ^
  --hidden-import cv2 ^
  gui\app.py
```

Flag notes:
- `--onefile` — single .exe output (slower startup, simplest distribution).
- `--windowed` — suppresses the console window (GUI app).
- `--add-data "data;data"` — bundles `marketplace_rules.json`; on
  macOS/Linux PyInstaller use `data:data` (colon, not semicolon).
- `--collect-all customtkinter` — CustomTkinter ships theme JSON files
  that PyInstaller's import scanner misses without this.
- `--icon` — point at a real `.ico` file if you have branded artwork;
  omit the flag if you don't have one yet.

The finished executable appears at `dist\StockSubmissionAssistant.exe`.

### 3. If you'd rather have a folder build (faster startup, easier debugging)

Drop `--onefile` from the command above; PyInstaller will produce
`dist\StockSubmissionAssistant\StockSubmissionAssistant.exe` plus its
dependency folder. Zip the whole folder to distribute it.

### 4. Common troubleshooting

| Symptom | Fix |
|---|---|
| App opens then instantly closes | Rebuild without `--windowed` temporarily to see the traceback in the console. |
| `ModuleNotFoundError: customtkinter` at runtime | Add `--collect-all customtkinter` (see above) — its assets aren't found by static analysis alone. |
| `FileNotFoundError: data/marketplace_rules.json` | Confirm the `--add-data` flag matches your OS separator (`;` on Windows, `:` on macOS/Linux), and that `core/marketplace_checker.py`'s path resolves relative to the bundle — PyInstaller sets `sys._MEIPASS` for onefile temp extraction; if you rename folders, re-check the relative path in `_RULES_PATH`. |
| AI file analysis silently falls back to "limited" mode | PyMuPDF wasn't bundled — add `--hidden-import fitz` and confirm `pip show pymupdf` succeeds in the build environment. |
| Large .exe size (100MB+) | Expected with OpenCV + PyMuPDF + CustomTkinter bundled. Use `--exclude-module` for any scikit-image submodules you don't use, or switch to the folder build (step 3) which starts faster even though it's not smaller. |
| Antivirus flags the .exe | Common false-positive for PyInstaller onefile builds (unsigned binary that self-extracts). Code-sign the executable if distributing publicly, or use the folder build instead. |

### Build optimization

- Use a fresh virtualenv with only `requirements.txt` installed — extra
  packages get scanned and sometimes bundled unnecessarily.
- Add `--strip` (Linux/macOS) to shrink binary size (not available on
  Windows).
- If startup time matters more than a single file, prefer the folder
  build (step 3); `--onefile` re-extracts to a temp dir on every launch.
