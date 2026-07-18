"""
core/report_generator.py

Produces plain-text, JSON, and CSV reports from analysis results.
"""
from __future__ import annotations
import json
import csv
import os
import datetime
from dataclasses import asdict, is_dataclass


def _to_dict(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def build_text_report(filename: str, analysis: dict, marketplace_results: list) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("STOCK SUBMISSION ASSISTANT — ANALYSIS REPORT")
    lines.append(f"Generated: {datetime.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"File: {filename}")
    lines.append("=" * 70)
    lines.append("")

    lines.append("-- FILE ANALYSIS --")
    for k, v in analysis.items():
        if isinstance(v, list):
            if v:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("")

    lines.append("-- MARKETPLACE COMPATIBILITY --")
    overall_pass = True
    for r in marketplace_results:
        status = r.status if hasattr(r, "status") else r["status"]
        marketplace = r.marketplace if hasattr(r, "marketplace") else r["marketplace"]
        reasons = r.reasons if hasattr(r, "reasons") else r["reasons"]
        if status != "PASS":
            overall_pass = False
        lines.append(f"[{status}] {marketplace}")
        for reason in reasons:
            lines.append(f"    - {reason}")
    lines.append("")
    lines.append(f"OVERALL: {'PASS' if overall_pass else 'WARNING/FAIL — see details above'}")
    lines.append("")
    lines.append("NOTE: All results above are derived from direct file measurement or")
    lines.append("published static technical specs. Nothing here predicts human/AI")
    lines.append("moderation outcomes, keyword relevance, or catalog similarity —")
    lines.append("those cannot be determined offline.")

    return "\n".join(lines)


def save_text_report(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def save_json_report(path: str, filename: str, analysis: dict, marketplace_results: list):
    payload = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "file": filename,
        "analysis": analysis,
        "marketplace_results": [
            _to_dict(r) for r in marketplace_results
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def save_batch_csv(path: str, rows: list):
    """rows: list of dicts with consistent-ish keys; missing keys become blank."""
    if not rows:
        return
    all_keys = []
    for row in rows:
        for k in row.keys():
            if k not in all_keys:
                all_keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
