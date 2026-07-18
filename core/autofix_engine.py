"""
core/autofix_engine.py

Generates suggested-fix numbers using plain arithmetic (aspect-ratio
preserving scale-to-target-megapixels, padding %, grid layout suggestions).
This never edits a file automatically — it only proposes numbers. Applying
a fix is a separate, explicit, user-triggered action (see raster_analysis
.strip_exif_and_save and gui/fix_actions.py for the few fixes that DO
write a new file, always to a new path, never overwriting the original).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SizeSuggestion:
    width: int
    height: int
    megapixels: float
    label: str


def suggest_sizes_for_target_mp(current_w: int, current_h: int, target_mp: float, options: int = 1) -> List[SizeSuggestion]:
    """Scale (w,h) up to reach >= target_mp while preserving aspect ratio.
    Returns the exact minimum needed, plus one clean rounded option ONLY if
    it differs meaningfully from the exact value — no filler/duplicate
    suggestions.
    """
    current_mp = (current_w * current_h) / 1_000_000
    if current_mp >= target_mp:
        return [SizeSuggestion(current_w, current_h, round(current_mp, 2), "Already meets target — no resize needed")]

    scale = math.sqrt((target_mp * 1_000_000) / (current_w * current_h))
    exact_w = round(current_w * scale)
    exact_h = round(current_h * scale)

    suggestions = [
        SizeSuggestion(exact_w, exact_h, round((exact_w * exact_h) / 1_000_000, 2), "Exact minimum to meet target")
    ]

    # One clean rounded-to-nearest-100px option, only if it's actually
    # different from the exact size (avoids showing near-identical noise).
    w2 = int(round(exact_w / 100.0)) * 100
    h2 = round(w2 * (current_h / current_w))
    mp2 = (w2 * h2) / 1_000_000
    if mp2 >= target_mp and (w2, h2) != (exact_w, exact_h):
        suggestions.append(SizeSuggestion(w2, h2, round(mp2, 2), "Rounded to a clean 100px value"))

    return suggestions


def suggest_scale_percentage(current_w: int, current_h: int, target_w: int, target_h: int) -> float:
    scale_w = target_w / current_w
    scale_h = target_h / current_h
    scale = max(scale_w, scale_h)  # scale to cover the larger requirement
    return round((scale - 1.0) * 100.0, 1)


def suggest_icon_grid_layout(icon_count: int) -> Tuple[int, int]:
    """Suggest a rows x cols grid closest to a 2:1 or square-ish layout for
    an icon pack preview sheet — pure combinatorics, not a guess."""
    best = None
    for cols in range(1, icon_count + 1):
        rows = math.ceil(icon_count / cols)
        remainder_waste = (rows * cols) - icon_count
        aspect_penalty = abs((cols / rows) - 2.0)  # prefer a wide-ish sheet
        score = remainder_waste * 2 + aspect_penalty
        if best is None or score < best[0]:
            best = (score, rows, cols)
    return best[2], best[1]  # cols, rows


def suggest_padding_px(artboard_w: int, artboard_h: int, target_occupancy_pct: float = 85.0) -> int:
    """Given a target occupancy percentage, back-calculate a suggested
    uniform padding in px so that the artwork bounding box would occupy
    roughly target_occupancy_pct of the artboard, assuming a roughly
    square/centered artwork region. This is a geometric estimate, labeled
    as such in the UI."""
    shrink_factor = math.sqrt(target_occupancy_pct / 100.0)
    min_dim = min(artboard_w, artboard_h)
    padding = (min_dim * (1 - shrink_factor)) / 2.0
    return max(0, round(padding))


def suggest_occupancy_fix(current_occupancy_pct: float, recommended_min: float = 70.0, recommended_max: float = 90.0) -> str:
    if current_occupancy_pct < recommended_min:
        return f"Increase artwork size or crop tighter — current occupancy {current_occupancy_pct}% is below the typical recommended range ({recommended_min}-{recommended_max}%)."
    elif current_occupancy_pct > recommended_max:
        return f"Add more margin/padding — current occupancy {current_occupancy_pct}% is above the typical recommended range ({recommended_min}-{recommended_max}%), risking a too-tight crop."
    else:
        return f"Occupancy {current_occupancy_pct}% is within the typical recommended range ({recommended_min}-{recommended_max}%)."
