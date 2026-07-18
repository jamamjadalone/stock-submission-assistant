"""
core/batch_checker.py

Runs analysis across many files at once, plus a batch-only feature:
near-duplicate detection using perceptual hashing (raster files only).
"""
from __future__ import annotations
import os
from dataclasses import asdict

from . import raster_analysis, vector_analysis, marketplace_checker

RASTER_EXT = {"jpg", "jpeg", "png"}
VECTOR_EXT = {"ai", "eps"}


def classify_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in RASTER_EXT:
        return "raster"
    if ext in VECTOR_EXT:
        return "vector"
    return "unsupported"


def analyze_batch(filepaths: list, progress_callback=None):
    """Returns (results: list of dict, duplicate_groups: list of list[str])"""
    results = []
    hashes = {}

    for i, path in enumerate(filepaths):
        kind = classify_file(path)
        entry = {"filepath": path, "filename": os.path.basename(path), "kind": kind}
        try:
            if kind == "raster":
                ext = os.path.splitext(path)[1].lower().lstrip(".")
                file_kind = "png" if ext == "png" else "photo"
                report = raster_analysis.analyze_raster(path)
                mk_results = marketplace_checker.check_raster(report, file_kind=file_kind)
                entry["report"] = report
                entry["marketplace_results"] = mk_results
                entry["status"] = "FAIL" if any(r.status == "FAIL" for r in mk_results) else (
                    "WARNING" if any(r.status == "WARNING" for r in mk_results) else "PASS"
                )
                try:
                    hashes[path] = raster_analysis.phash(path)
                except Exception:
                    pass
            elif kind == "vector":
                report = vector_analysis.analyze_vector(path)
                mk_results = marketplace_checker.check_vector(report)
                entry["report"] = report
                entry["marketplace_results"] = mk_results
                entry["status"] = "FAIL" if any(r.status == "FAIL" for r in mk_results) else (
                    "WARNING" if any(r.status == "WARNING" for r in mk_results) else "PASS"
                )
            else:
                entry["status"] = "UNSUPPORTED"
                entry["error"] = f"Unsupported file type: {os.path.splitext(path)[1]}"
        except Exception as e:
            entry["status"] = "ERROR"
            entry["error"] = str(e)

        results.append(entry)
        if progress_callback:
            progress_callback(i + 1, len(filepaths))

    duplicate_groups = _find_duplicate_groups(hashes)
    return results, duplicate_groups


def _find_duplicate_groups(hashes: dict, threshold: int = 6):
    """hashes: {filepath: phash_string}. Groups files whose hamming distance
    is <= threshold (near-duplicate). Deterministic, offline, no ML model."""
    paths = list(hashes.keys())
    visited = set()
    groups = []
    for i, p1 in enumerate(paths):
        if p1 in visited:
            continue
        group = [p1]
        for p2 in paths[i + 1:]:
            if p2 in visited:
                continue
            dist = raster_analysis.hamming_distance(hashes[p1], hashes[p2])
            if dist <= threshold:
                group.append(p2)
                visited.add(p2)
        if len(group) > 1:
            visited.add(p1)
            groups.append(group)
    return groups
