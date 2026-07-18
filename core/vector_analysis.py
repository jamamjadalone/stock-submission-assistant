"""
core/vector_analysis.py

Offline analysis of AI and EPS vector files. (SVG support removed per
user request — this module now handles Illustrator-native formats only.)

- AI: modern Illustrator files are PDF-compatible; parsed with PyMuPDF (fitz)
  when available. If fitz is missing, falls back to raw byte/text scanning
  for DSC-style comments (less complete, clearly labeled).
- EPS: PostScript is DSC-comment based (ASCII header). Parsed as text for
  %%BoundingBox, %%Creator, fonts, etc. Cannot rasterize without Ghostscript
  (optional, checked in Settings) — anything needing rasterization is
  reported as "Cannot be determined offline (requires Ghostscript)".
"""
from __future__ import annotations
import os
import re
import math
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


@dataclass
class VectorReport:
    filepath: str
    filename: str
    file_format: str
    file_size_bytes: int
    version_info: Optional[str] = None
    artboard_width_pt: Optional[float] = None
    artboard_height_pt: Optional[float] = None
    artwork_width_pt: Optional[float] = None
    artwork_height_pt: Optional[float] = None
    artwork_bbox_method: Optional[str] = None
    num_artboards: Optional[int] = None
    aspect_ratio: Optional[str] = None

    has_live_text: Optional[bool] = None
    live_text_count: int = 0
    has_embedded_raster: Optional[bool] = None
    embedded_raster_count: int = 0
    has_linked_files: Optional[bool] = None
    linked_file_names: list = field(default_factory=list)
    layer_names: list = field(default_factory=list)
    has_locked_or_hidden_layers: Optional[bool] = None

    determinable: bool = True
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _pt_to_px(pt: float, dpi: float = 72.0) -> float:
    return pt  # PDF/AI native unit is already 72dpi "points" == px at 72dpi


# ---------------------------------------------------------------------------
# AI (PDF-compatible) via PyMuPDF
# ---------------------------------------------------------------------------
def analyze_ai(filepath: str) -> VectorReport:
    filename = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    report = VectorReport(filepath=filepath, filename=filename, file_format="AI", file_size_bytes=size)

    if not HAS_FITZ:
        report.determinable = False
        report.notes.append("PyMuPDF (fitz) not installed — AI analysis limited to raw text scan.")
        return _analyze_ai_fallback_text(filepath, report)

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        report.determinable = False
        report.errors.append(f"Could not open AI file (not a valid PDF-compatible Illustrator file?): {e}")
        return report

    report.num_artboards = doc.page_count
    page = doc[0]
    rect = page.rect
    report.artboard_width_pt = round(rect.width, 2)
    report.artboard_height_pt = round(rect.height, 2)
    g = math.gcd(int(rect.width), int(rect.height)) or 1
    report.aspect_ratio = f"{int(rect.width/g)}:{int(rect.height/g)}"

    # --- Artwork bounding box (NOT the artboard) ---------------------------
    # Adobe Stock and others measure the 4MP minimum against the actual
    # artwork content, not the empty artboard/canvas around it. We compute
    # the real ink extent from vector paths, embedded images, and text,
    # then union them into one bounding box.
    artwork_bbox = None

    def _union(a, b):
        if a is None:
            return b
        if b is None:
            return a
        return fitz.Rect(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1))

    try:
        for drawing in page.get_drawings():
            r = drawing.get("rect")
            if r:
                artwork_bbox = _union(artwork_bbox, fitz.Rect(r))
    except Exception:
        pass

    try:
        for img in page.get_images(full=True):
            try:
                bbox_list = page.get_image_bbox(img)
                if bbox_list:
                    artwork_bbox = _union(artwork_bbox, fitz.Rect(bbox_list))
            except Exception:
                continue
    except Exception:
        pass

    try:
        text_bbox = page.get_bboxlog()
        for _kind, r in text_bbox:
            artwork_bbox = _union(artwork_bbox, fitz.Rect(r))
    except Exception:
        pass

    if artwork_bbox is not None and artwork_bbox.width > 0 and artwork_bbox.height > 0:
        # Clip to the artboard in case of stray off-canvas objects skewing the box
        clipped = artwork_bbox & rect
        if clipped.width > 0 and clipped.height > 0:
            report.artwork_width_pt = round(clipped.width, 2)
            report.artwork_height_pt = round(clipped.height, 2)
            report.artwork_bbox_method = "measured (vector paths + embedded images + text extent)"
        else:
            report.notes.append("Detected artwork extent fell entirely outside the artboard — using artboard size as fallback for MP calculations.")
    else:
        report.notes.append("Could not isolate an artwork bounding box distinct from the artboard — MP requirement checks fall back to full artboard size, which may understate how much you need to scale up.")

    # Fonts (live text indicator)
    fonts = page.get_fonts(full=True)
    report.has_live_text = len(fonts) > 0
    report.live_text_count = len(fonts)
    font_names = sorted(set(f[3] for f in fonts))
    if font_names:
        report.notes.append("Fonts referenced: " + ", ".join(font_names))

    # Embedded raster images
    images = page.get_images(full=True)
    report.has_embedded_raster = len(images) > 0
    report.embedded_raster_count = len(images)

    # Layers (Illustrator stores as Optional Content Groups)
    try:
        ocgs = doc.get_ocgs()
        report.layer_names = [v.get("name", "") for v in ocgs.values()]
        report.has_locked_or_hidden_layers = any(not v.get("on", True) for v in ocgs.values())
    except Exception:
        pass

    metadata = doc.metadata or {}
    creator = metadata.get("creator", "") or metadata.get("producer", "")
    if creator:
        report.version_info = creator

    if report.has_live_text:
        report.warnings.append(f"{report.live_text_count} font(s) referenced — verify text is outlined; live fonts are a top rejection cause on Adobe Stock/Shutterstock.")
    if report.has_embedded_raster:
        report.warnings.append(f"{report.embedded_raster_count} embedded raster image(s) found inside the AI file.")
    if report.has_locked_or_hidden_layers:
        report.warnings.append("Hidden/locked layer(s) detected via Illustrator Optional Content Groups.")

    doc.close()
    return report


def _analyze_ai_fallback_text(filepath: str, report: VectorReport) -> VectorReport:
    try:
        with open(filepath, "rb") as f:
            head = f.read(200_000).decode("latin-1", errors="ignore")
    except Exception as e:
        report.errors.append(f"Could not read file: {e}")
        return report

    bbox = re.search(r"%%BoundingBox:\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)", head)
    if bbox:
        x0, y0, x1, y1 = map(float, bbox.groups())
        report.artboard_width_pt = round(x1 - x0, 2)
        report.artboard_height_pt = round(y1 - y0, 2)
    creator = re.search(r"%%Creator:\s*(.+)", head)
    if creator:
        report.version_info = creator.group(1).strip()
    report.has_live_text = "/Type /Font" in head or "%%DocumentFonts" in head
    report.notes.append("Fallback text-scan only (install PyMuPDF for complete AI analysis).")
    return report


# ---------------------------------------------------------------------------
# EPS via DSC comment text parsing
# ---------------------------------------------------------------------------
def analyze_eps(filepath: str) -> VectorReport:
    filename = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    report = VectorReport(filepath=filepath, filename=filename, file_format="EPS", file_size_bytes=size)

    try:
        with open(filepath, "rb") as f:
            raw = f.read(500_000)
        head = raw.decode("latin-1", errors="ignore")
    except Exception as e:
        report.determinable = False
        report.errors.append(f"Could not read EPS file: {e}")
        return report

    bbox = re.search(r"%%BoundingBox:\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)", head)
    if bbox:
        x0, y0, x1, y1 = map(float, bbox.groups())
        w, h = x1 - x0, y1 - y0
        # By the DSC spec, %%BoundingBox is defined as the tightest box
        # enclosing the actual marks/artwork on the page — NOT an arbitrary
        # canvas/artboard size. So this value IS the artwork size the 4MP
        # rule cares about. We report it under both fields so the UI's
        # "artboard" display stays informative, but the MP/auto-fix math
        # below is driven off artwork_width/height_pt specifically.
        report.artboard_width_pt = round(w, 2)
        report.artboard_height_pt = round(h, 2)
        report.artwork_width_pt = round(w, 2)
        report.artwork_height_pt = round(h, 2)
        report.artwork_bbox_method = "measured (EPS %%BoundingBox — DSC-defined artwork extent)"
        if w > 0 and h > 0:
            g = math.gcd(int(w), int(h)) or 1
            report.aspect_ratio = f"{int(w/g)}:{int(h/g)}"
    else:
        report.warnings.append("No %%BoundingBox found — EPS may be malformed or not DSC-compliant.")

    ps_level = re.search(r"%!PS-Adobe-([\d.]+)(?:\s+EPSF-([\d.]+))?", head)
    if ps_level:
        report.version_info = f"PS-Adobe {ps_level.group(1)}" + (f" / EPSF-{ps_level.group(2)}" if ps_level.group(2) else "")

    creator = re.search(r"%%Creator:\s*(.+)", head)
    if creator:
        report.notes.append(f"Creator: {creator.group(1).strip()}")

    # Font references — matched per-line with anchors so the tag itself can
    # never be captured as its own "value" (the previous version sometimes
    # printed the literal tag text back, e.g. "%%DocumentNeededFonts:", as a
    # fake font name). Placeholder values like "(atend)" and empty lines are
    # discarded, and results are de-duplicated.
    raw_font_lines = re.findall(
        r"^%%(?:Document(?:Needed|Supplied)?)?Fonts?:[ \t]*(.*)$", head, re.MULTILINE
    )
    font_names = []
    for line in raw_font_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("%%") or line.lower() in ("(atend)", "atend"):
            continue
        for name in line.split():
            if name not in font_names:
                font_names.append(name)

    report.has_live_text = len(font_names) > 0
    if font_names:
        report.notes.append("Referenced fonts: " + ", ".join(font_names[:10]))
        report.warnings.append("Font references found in EPS header — verify all text has been outlined to paths before export.")
    else:
        report.notes.append("No concrete font names found in EPS header (a bare '%%DocumentNeededFonts: (atend)' placeholder does not, by itself, prove live text is present).")

    linked = re.findall(r"%%(?:Included|Linked)File:\s*(.+)", head)
    report.has_linked_files = len(linked) > 0
    report.linked_file_names = [l.strip() for l in linked]
    if linked:
        report.warnings.append(f"{len(linked)} linked file reference(s) found in EPS DSC comments.")

    is_eps10 = "%%LanguageLevel: 2" in head or "%%LanguageLevel: 3" in head
    if is_eps10:
        report.notes.append("EPS reports LanguageLevel 2/3 — generally compatible with EPS10 export target.")
    else:
        report.notes.append("Could not confirm LanguageLevel — verify EPS10 export setting manually in Illustrator.")

    report.notes.append("EPS rasterization/visual preview requires Ghostscript (optional, see Settings). Not required for the checks above.")

    return report


def analyze_vector(filepath: str) -> VectorReport:
    ext = os.path.splitext(filepath)[1].lower().lstrip(".")
    if ext == "ai":
        return analyze_ai(filepath)
    elif ext == "eps":
        return analyze_eps(filepath)
    else:
        raise ValueError(f"Unsupported vector format: .{ext} (supported: AI, EPS)")
