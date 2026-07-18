"""
core/marketplace_checker.py

Compares a RasterReport or VectorReport's ACTUAL measured facts against the
publicly documented, static technical specs in data/marketplace_rules.json.

This never predicts moderation outcomes. It only says: "your file's
measured megapixels/format/color-mode do or don't meet the PUBLISHED
technical minimum", and clearly separates that from anything requiring a
human decision.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import List

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "marketplace_rules.json")


def _load_rules():
    with open(_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class MarketplaceResult:
    marketplace: str
    status: str  # "PASS", "WARNING", "FAIL", "UNDETERMINED"
    reasons: List[str] = field(default_factory=list)


def check_raster(report, file_kind: str = "photo") -> List[MarketplaceResult]:
    """file_kind: 'photo' or 'png'
    Simplified per request: marketplace compatibility now checks resolution
    (megapixels) only — the one hard, unambiguous number every marketplace
    publishes. Format/transparency/color-mode notes are still shown
    elsewhere in the per-file analysis, just not repeated here as
    marketplace pass/fail reasons.
    """
    rules = _load_rules()
    results = []

    for name, spec in rules.items():
        if name.startswith("_"):
            continue
        reasons = []
        status = "PASS"

        min_mp = spec.get("png_min_megapixels") if file_kind == "png" else spec.get("photo_min_megapixels")
        if min_mp is not None:
            if report.megapixels < min_mp:
                status = "FAIL"
                reasons.append(f"Resolution {report.megapixels}MP is below published minimum {min_mp}MP for {name}.")
            else:
                reasons.append(f"Resolution {report.megapixels}MP meets the published {min_mp}MP minimum for {name}.")
        else:
            reasons.append(f"No published megapixel minimum found for {name} — Cannot be determined offline.")

        results.append(MarketplaceResult(marketplace=name, status=status, reasons=reasons))

    return results


def check_vector(report) -> List[MarketplaceResult]:
    """Simplified per request: marketplace compatibility now checks the
    artwork's megapixels only (never the artboard — see RESEARCH.md).
    Structural notes (live text, embedded raster, linked files, hidden
    layers) are still shown in the per-file Object Analysis section, just
    not repeated here as marketplace pass/fail reasons.
    """
    rules = _load_rules()
    results = []

    for name, spec in rules.items():
        if name.startswith("_"):
            continue
        reasons = []
        status = "PASS"

        min_mp = spec.get("photo_min_megapixels") or spec.get("png_min_megapixels")
        if min_mp and report.artwork_width_pt and report.artwork_height_pt:
            artwork_mp = (report.artwork_width_pt * report.artwork_height_pt) / 1_000_000
            if artwork_mp < min_mp:
                status = "FAIL"
                reasons.append(
                    f"Artwork size is approx. {artwork_mp:.2f}MP, below the published {min_mp}MP minimum for {name} "
                    f"(measured from the artwork's own bounding box, not the artboard)."
                )
            else:
                reasons.append(
                    f"Artwork size is approx. {artwork_mp:.2f}MP, meets the published {min_mp}MP minimum for {name}."
                )
        elif min_mp:
            status = "UNDETERMINED"
            reasons.append(
                f"Could not measure artwork extent separately from the artboard, so the {min_mp}MP minimum "
                f"could not be verified for {name} — Cannot be determined offline for this file."
            )
        else:
            reasons.append(f"No published megapixel minimum found for {name} — Cannot be determined offline.")

        results.append(MarketplaceResult(marketplace=name, status=status, reasons=reasons))

    return results


def rejection_simulation(results: List[MarketplaceResult]) -> dict:
    """Turns marketplace check results into a plain-language 'possible
    rejection reasons' summary. This is a summary of ACTUAL detected issues,
    not a prediction of what a human reviewer will decide."""
    out = {}
    for r in results:
        if r.status in ("FAIL", "WARNING"):
            out[r.marketplace] = {
                "likely_outcome": "Likely Rejected (technical issue found)" if r.status == "FAIL" else "Possible Review Flags (verify manually)",
                "reasons": r.reasons,
            }
        else:
            out[r.marketplace] = {
                "likely_outcome": "No offline-detectable technical blockers found",
                "reasons": r.reasons,
            }
    return out
