"""
gui/app.py

Stock Submission Assistant — desktop UI (CustomTkinter).
Tabs: Vector | PNG | Photos | Batch Checker | Reports | Settings | Help
"""
from __future__ import annotations
import os
import sys
import threading
import traceback
from dataclasses import asdict

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import raster_analysis, vector_analysis, marketplace_checker, autofix_engine, report_generator, batch_checker
from gui import fix_actions

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

APP_TITLE = "Stock Submission Assistant"
LAST_REPORT_DIR = os.path.expanduser("~")


def fmt(value):
    if value is None:
        return "Cannot be determined offline"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


class ResultsPanel(ctk.CTkScrollableFrame):
    """Reusable scrollable panel that renders an analysis dict + marketplace results."""

    STATUS_COLORS = {"PASS": "#3ddc84", "WARNING": "#e0a30c", "FAIL": "#ff5555", "UNDETERMINED": "#888888"}

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_analysis = None
        self.current_filename = None
        self.current_mk_results = []

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _section(self, title):
        card = ctk.CTkFrame(self, fg_color="#1f1f1f", corner_radius=8)
        card.pack(fill="x", padx=8, pady=(14, 4))
        lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
                           text_color="#3ddc84")
        lbl.pack(fill="x", padx=10, pady=8)
        return card

    def _row(self, key, value):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=1)
        ctk.CTkLabel(frame, text=f"{key}:", anchor="w", width=260, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkLabel(frame, text=fmt(value), anchor="w", wraplength=420, justify="left").pack(side="left", fill="x", expand=True)

    def _list_block(self, title, items, color="#e0a30c"):
        if not items:
            return
        self._section(title)
        for item in items:
            ctk.CTkLabel(self, text=f"• {item}", anchor="w", wraplength=680, justify="left", text_color=color).pack(fill="x", padx=20, pady=1)

    def _status_badge(self, parent, status):
        color = self.STATUS_COLORS.get(status, "#888888")
        emoji = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌", "UNDETERMINED": "❔"}.get(status, "")
        badge = ctk.CTkLabel(parent, text=f" {emoji} {status} ", font=ctk.CTkFont(size=11, weight="bold"),
                              fg_color=color, text_color="#101010", corner_radius=6, width=120)
        return badge

    def _marketplace_block(self, results):
        for r in results:
            row = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=6)
            row.pack(fill="x", padx=10, pady=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))
            self._status_badge(top, r.status).pack(side="left")
            ctk.CTkLabel(top, text=r.marketplace.replace("_", " ").title(), anchor="w",
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=8)
            for reason in r.reasons:
                ctk.CTkLabel(row, text=f"   - {reason}", anchor="w", wraplength=660, justify="left").pack(fill="x", padx=10, pady=1)
            ctk.CTkFrame(row, fg_color="transparent", height=4).pack()

    def _autofix_card(self, sizes, padding=None, subtitle=None, on_apply=None, src_path=None):
        """Cool, emoji-driven auto-fix suggestions card, reused by both the
        vector and raster panels. `sizes` is a list of autofix_engine
        SizeSuggestion objects. If on_apply is given, each size gets a
        '💾 Save As New File' button that NEVER overwrites the original —
        it always prompts for a new destination path."""
        outer = ctk.CTkFrame(self, fg_color="#15201a", corner_radius=10, border_width=1, border_color="#2d5c43")
        outer.pack(fill="x", padx=8, pady=(4, 10))

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(header, text="🛠️  Auto-Fix Suggestions", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#3ddc84").pack(side="left")

        if subtitle:
            ctk.CTkLabel(outer, text=subtitle, anchor="w", wraplength=680, justify="left",
                         text_color="#8ab4f8", font=ctk.CTkFont(size=11, slant="italic")).pack(fill="x", padx=14, pady=(0, 8))

        for s in sizes:
            already_ok = "Already meets" in s.label or "no resize" in s.label.lower()
            icon = "✨" if already_ok else "📐"
            card = ctk.CTkFrame(outer, fg_color="#1f2b24", corner_radius=8)
            card.pack(fill="x", padx=14, pady=4)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=f"{icon}  {s.width} × {s.height} px", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"🔢 {s.megapixels} MP", text_color="#3ddc84", font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")
            ctk.CTkLabel(card, text=f"   {s.label}", anchor="w", text_color="gray", font=ctk.CTkFont(size=11)).pack(fill="x", padx=10, pady=(0, 8))

            if on_apply and not already_ok and src_path:
                btn_row = ctk.CTkFrame(card, fg_color="transparent")
                btn_row.pack(fill="x", padx=10, pady=(0, 8))
                ctk.CTkButton(
                    btn_row, text="💾 Save As New File...", width=180, height=26,
                    fg_color="#2b6e4f", hover_color="#358560",
                    command=lambda sw=s.width, sh=s.height: on_apply(src_path, sw, sh)
                ).pack(side="left")
                ctk.CTkLabel(btn_row, text="original file is never modified", text_color="gray",
                             font=ctk.CTkFont(size=10, slant="italic")).pack(side="left", padx=8)

        if padding is not None:
            pad_row = ctk.CTkFrame(outer, fg_color="transparent")
            pad_row.pack(fill="x", padx=14, pady=(2, 12))
            ctk.CTkLabel(pad_row, text=f"📏  Suggested padding: {padding}px", font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#e0a30c").pack(side="left")
            ctk.CTkLabel(pad_row, text=" (targets ~85% occupancy)", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")

        return outer

    def render_raster(self, report, filename, extra_fields=None):
        self.clear()
        self.current_analysis = asdict(report)
        self.current_filename = filename
        self._section("File Analysis")
        self._row("Filename", report.filename)
        self._row("Format", report.file_format)
        self._row("File size", f"{report.file_size_bytes/1024:.1f} KB")
        self._row("Dimensions", f"{report.width} x {report.height} px")
        self._row("Megapixels", report.megapixels)
        self._row("Aspect ratio", report.aspect_ratio)
        self._row("DPI", report.dpi)
        self._row("Color mode", report.color_mode)
        self._row("Bit depth", f"{report.bit_depth}-bit" if report.bit_depth else None)
        self._row("Has alpha/transparency", report.has_alpha)
        self._row("ICC profile", report.icc_profile_name if report.icc_profile_present else "Not present")
        self._row("EXIF present", report.exif_present)
        self._row("GPS metadata present", report.gps_metadata_present)

        self._section("Quality Analysis")
        self._row("Sharpness (Laplacian variance)", report.sharpness_laplacian_var)
        self._row("Sharpness verdict", report.sharpness_verdict)
        self._row("Noise estimate", report.noise_estimate)
        self._row("Noise verdict", report.noise_verdict)
        self._row("Brightness (mean)", report.brightness_mean)
        self._row("Contrast (std dev)", report.contrast_std)
        self._row("Exposure verdict", report.exposure_verdict)
        self._row("Clipped highlights %", report.clipped_highlights_pct)
        self._row("Clipped shadows %", report.clipped_shadows_pct)
        self._row("Histogram balance", report.histogram_balance)

        self._section("Composition Analysis")
        self._row("Object occupancy %", report.object_occupancy_pct)
        self._row("Empty space %", report.empty_space_pct)
        self._row("Center-of-mass offset (x%,y%)", report.center_of_mass_offset_pct)

        self._list_block("Warnings", report.warnings)
        self._list_block("Errors", report.errors, color="#ff5555")

        if extra_fields:
            self._section("Marketplace Compatibility")
            self._marketplace_block(extra_fields)
            self.current_mk_results = extra_fields

        # MP auto-fix: if the file falls short of any marketplace's
        # published minimum, suggest the exact resize needed.
        if extra_fields:
            failing = [r for r in extra_fields if r.status == "FAIL"]
            if failing:
                target_mp = 4.0  # every marketplace here publishes 4MP as photo/PNG minimum
                sizes = autofix_engine.suggest_sizes_for_target_mp(report.width, report.height, target_mp)
                self._autofix_card(
                    sizes,
                    subtitle=f"🎯 Target: {target_mp} MP — the minimum published by every marketplace checked above.",
                    on_apply=self._apply_resize_fix,
                    src_path=report.filepath
                )

    def _apply_resize_fix(self, src_path, target_w, target_h):
        dst_path = filedialog.asksaveasfilename(
            title="Save resized copy as...",
            defaultextension=os.path.splitext(src_path)[1],
            initialfile=f"{os.path.splitext(os.path.basename(src_path))[0]}_resized{os.path.splitext(src_path)[1]}",
            filetypes=[("Image", "*.jpg *.jpeg *.png")]
        )
        if not dst_path:
            return
        try:
            fix_actions.apply_resize(src_path, dst_path, target_w, target_h)
            messagebox.showinfo("✅ Saved", f"Resized copy saved to:\n{dst_path}\n\nYour original file was not modified.")
        except Exception as e:
            messagebox.showerror("Resize failed", str(e))

    def render_vector(self, report, extra_fields=None):
        self.clear()
        self.current_analysis = asdict(report)
        self.current_filename = report.filename
        self._section("File Analysis")
        self._row("Filename", report.filename)
        self._row("Format", report.file_format)
        self._row("File size", f"{report.file_size_bytes/1024:.1f} KB")
        self._row("Version info", report.version_info)
        self._row("Artboard/canvas size (pt)", f"{report.artboard_width_pt} x {report.artboard_height_pt}" if report.artboard_width_pt else None)
        self._row("Artwork size (pt)", f"{report.artwork_width_pt} x {report.artwork_height_pt}" if report.artwork_width_pt else None)
        self._row("Artwork measurement method", report.artwork_bbox_method)
        self._row("Aspect ratio", report.aspect_ratio)
        self._row("Number of artboards", report.num_artboards)

        self._section("Object Analysis")
        self._row("Live text present", report.has_live_text)
        self._row("Text/font element count", report.live_text_count)
        self._row("Embedded raster images", report.has_embedded_raster)
        self._row("Embedded raster count", report.embedded_raster_count)
        self._row("Linked (external) files", report.has_linked_files)
        self._row("Linked file names", ", ".join(report.linked_file_names) if report.linked_file_names else None)
        self._row("Hidden/locked layers", report.has_locked_or_hidden_layers)
        self._row("Layer names", ", ".join(report.layer_names) if report.layer_names else None)

        self._list_block("Notes", report.notes, color="#8ab4f8")
        self._list_block("Warnings", report.warnings)
        self._list_block("Errors", report.errors, color="#ff5555")

        if extra_fields:
            self._section("Marketplace Compatibility / Rejection Simulation")
            self._marketplace_block(extra_fields)
            self.current_mk_results = extra_fields

        # IMPORTANT: the 4MP minimum applies to the ARTWORK itself, not the
        # empty artboard/canvas around it. Only run the auto-fix MP
        # calculation when we actually have a measured artwork extent —
        # falling back to artboard size here would understate (or
        # overstate) how much scaling is really needed.
        if report.artwork_width_pt and report.artwork_height_pt:
            target_mp = 4.0
            w, h = int(report.artwork_width_pt), int(report.artwork_height_pt)
            sizes = autofix_engine.suggest_sizes_for_target_mp(w, h, target_mp)
            padding = autofix_engine.suggest_padding_px(w, h)
            self._autofix_card(
                sizes, padding=padding,
                subtitle="📐 Based on measured ARTWORK size (not the artboard) — this is what marketplaces actually check against the 4MP minimum."
            )
        elif report.artboard_width_pt:
            self._section("Auto-Fix Suggestions")
            ctk.CTkLabel(
                self, text="❔ Could not isolate the artwork's own bounding box for this file, so a reliable MP auto-fix suggestion can't be shown — "
                           "sizing off the artboard alone could give you the wrong number. Check 'Artwork measurement method' above/Notes for why.",
                anchor="w", wraplength=680, justify="left", text_color="#e0a30c"
            ).pack(fill="x", padx=10, pady=(0, 6))


class BaseFileTab(ctk.CTkFrame):
    """Shared skeleton for Vector/PNG/Photo tabs: file picker + results panel."""

    def __init__(self, master, title, filetypes, analyze_fn, kind, app):
        super().__init__(master, fg_color="transparent")
        self.filetypes = filetypes
        self.analyze_fn = analyze_fn
        self.kind = kind
        self.app = app
        self.current_path = None
        self._spinner_job = None
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_i = 0

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top, text=title, font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Generate Report", command=self.generate_report, width=140,
                      fg_color="#2b2b2b", hover_color="#3a3a3a").pack(side="right", padx=4)
        ctk.CTkButton(top, text="Choose File", command=self.pick_file, width=140).pack(side="right", padx=4)

        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=14)
        self.file_label = ctk.CTkLabel(status_row, text="No file selected", anchor="w", text_color="gray")
        self.file_label.pack(side="left", fill="x", expand=True)
        self.spinner_label = ctk.CTkLabel(status_row, text="", anchor="e", text_color="#3ddc84", width=160)
        self.spinner_label.pack(side="right")

        self.results = ResultsPanel(self)
        self.results.pack(fill="both", expand=True, padx=10, pady=10)

    def _start_spinner(self, message="Analyzing"):
        self._spinner_message = message
        self._tick_spinner()

    def _tick_spinner(self):
        frame = self._spinner_frames[self._spinner_i % len(self._spinner_frames)]
        self.spinner_label.configure(text=f"{frame}  {self._spinner_message}...")
        self._spinner_i += 1
        self._spinner_job = self.after(90, self._tick_spinner)

    def _stop_spinner(self, final_text=""):
        if self._spinner_job:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None
        self.spinner_label.configure(text=final_text)

    def pick_file(self):
        path = filedialog.askopenfilename(title="Select file", filetypes=self.filetypes)
        if not path:
            return
        self.current_path = path
        self.file_label.configure(text=path)
        self.results.clear()
        self._start_spinner("Analyzing")
        threading.Thread(target=self._run_analysis, args=(path,), daemon=True).start()

    def _run_analysis(self, path):
        try:
            report = self.analyze_fn(path)
            if self.kind in ("photo", "png"):
                mk = marketplace_checker.check_raster(report, file_kind=self.kind)
                self.after(0, lambda: self._finish(lambda: self.results.render_raster(report, os.path.basename(path), mk)))
            else:
                mk = marketplace_checker.check_vector(report)
                self.after(0, lambda: self._finish(lambda: self.results.render_vector(report, mk)))
        except Exception as e:
            err = traceback.format_exc()
            self.after(0, lambda: self._finish(lambda: messagebox.showerror("Analysis failed", f"{e}\n\n{err}")))

    def _finish(self, render_fn):
        self._stop_spinner("✓ Done")
        render_fn()
        self.after(2500, lambda: self._stop_spinner(""))

    def generate_report(self):
        if not self.results.current_analysis:
            messagebox.showinfo("No analysis", "Analyze a file first.")
            return
        self.app.show_report(self.results.current_filename, self.results.current_analysis, self.results.current_mk_results)


class BatchTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.filepaths = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(top, text="Batch Checker", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Choose Files", command=self.pick_files, width=140).pack(side="right", padx=4)
        ctk.CTkButton(top, text="Export CSV", command=self.export_csv, width=140).pack(side="right", padx=4)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14, pady=(0, 6))

        self.output = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.output.pack(fill="both", expand=True, padx=10, pady=10)
        self.last_results = []
        self.last_dupes = []

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select files for batch check",
            filetypes=[("Supported files", "*.jpg *.jpeg *.png *.ai *.eps")]
        )
        if not paths:
            return
        self.filepaths = list(paths)
        threading.Thread(target=self._run_batch, daemon=True).start()

    def _run_batch(self):
        self.output.delete("1.0", "end")

        def cb(done, total):
            self.after(0, lambda: self.progress.set(done / total))

        results, dupes = batch_checker.analyze_batch(self.filepaths, progress_callback=cb)
        self.last_results = results
        self.last_dupes = dupes
        self.after(0, lambda: self._render(results, dupes))

    def _render(self, results, dupes):
        lines = []
        for r in results:
            status = r.get("status", "?")
            lines.append(f"[{status}] {r['filename']}")
            if r.get("error"):
                lines.append(f"    ERROR: {r['error']}")
            for mk in r.get("marketplace_results", []):
                if mk.status != "PASS":
                    lines.append(f"    - {mk.marketplace}: {mk.status} — {mk.reasons[0]}")
        if dupes:
            lines.append("")
            lines.append("=== Possible near-duplicate groups (batch-only feature) ===")
            for group in dupes:
                lines.append("  Group: " + ", ".join(os.path.basename(p) for p in group))
        self.output.insert("1.0", "\n".join(lines))

    def export_csv(self):
        if not self.last_results:
            messagebox.showinfo("No data", "Run a batch check first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        rows = []
        for r in self.last_results:
            row = {"filename": r["filename"], "status": r.get("status"), "kind": r.get("kind")}
            report = r.get("report")
            if report:
                d = asdict(report)
                for k in ("width", "height", "megapixels", "file_format", "aspect_ratio"):
                    if k in d:
                        row[k] = d[k]
            rows.append(row)
        report_generator.save_batch_csv(path, rows)
        messagebox.showinfo("Saved", f"Batch report saved to:\n{path}")


class ReportsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Reports", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=10, pady=10)
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btns, text="Save as .txt", command=self.save_txt).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Save as .json", command=self.save_json).pack(side="left", padx=4)
        self._current = None

    def show(self, filename, analysis, mk_results):
        text = report_generator.build_text_report(filename, analysis, mk_results)
        self._current = (filename, analysis, mk_results, text)
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)

    def save_txt(self):
        if not self._current:
            messagebox.showinfo("No report", "Generate a report from a file tab first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        report_generator.save_text_report(path, self._current[3])
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    def save_json(self):
        if not self._current:
            messagebox.showinfo("No report", "Generate a report from a file tab first.")
            return
        filename, analysis, mk_results, _ = self._current
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        report_generator.save_json_report(path, filename, analysis, mk_results)
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")


class AboutTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.pack(expand=True, fill="both")

        card = ctk.CTkFrame(wrapper, fg_color="#1f1f1f", corner_radius=16)
        card.pack(pady=60, padx=60)

        self.logo_label = ctk.CTkLabel(card, text="📦", font=ctk.CTkFont(size=48))
        self.logo_label.pack(pady=(30, 6))

        ctk.CTkLabel(card, text=APP_TITLE, font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(card, text="Offline vector, PNG & photo checker for stock marketplaces",
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=(0, 20))

        ctk.CTkFrame(card, height=1, fg_color="#333333").pack(fill="x", padx=40)

        ctk.CTkLabel(card, text="Developed By", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(20, 2))
        ctk.CTkLabel(card, text="Jam Amjad Rasheed", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 10))

        link_btn = ctk.CTkButton(
            card, text="▶  YouTube — @jamamjadrasheed", width=280,
            fg_color="#c4302b", hover_color="#e0433d",
            command=lambda: self._open_link("https://www.youtube.com/@jamamjadrasheed")
        )
        link_btn.pack(pady=(0, 30))

        self._pulse_dir = 1
        self._pulse_val = 0
        self._animate_logo()

    def _open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def _animate_logo(self):
        # subtle breathing scale-ish effect using font size oscillation
        self._pulse_val += self._pulse_dir * 2
        if self._pulse_val >= 8:
            self._pulse_dir = -1
        elif self._pulse_val <= 0:
            self._pulse_dir = 1
        size = 44 + self._pulse_val
        self.logo_label.configure(font=ctk.CTkFont(size=size))
        self.after(120, self._animate_logo)


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=10, pady=10)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame, text="Appearance mode:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.mode_var = ctk.StringVar(value="dark")
        ctk.CTkOptionMenu(frame, values=["dark", "light", "system"], variable=self.mode_var,
                           command=lambda v: ctk.set_appearance_mode(v)).grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Optional dependency status:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        status_text = self._dependency_status()
        ctk.CTkLabel(frame, text=status_text, justify="left", anchor="w").grid(row=1, column=1, sticky="w", padx=10, pady=10)

    def _dependency_status(self):
        lines = []
        try:
            import fitz  # noqa
            lines.append("PyMuPDF (AI file analysis): installed")
        except ImportError:
            lines.append("PyMuPDF (AI file analysis): NOT installed — AI analysis will use limited fallback")
        import shutil
        gs = shutil.which("gs") or shutil.which("gswin64c")
        lines.append(f"Ghostscript (EPS raster preview): {'found' if gs else 'NOT found — EPS metadata analysis still works'}")
        return "\n".join(lines)


class HelpTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Help", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=10, pady=10)
        box = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13))
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", HELP_TEXT)
        box.configure(state="disabled")


HELP_TEXT = """STOCK SUBMISSION ASSISTANT — HELP

WHAT THIS APP DOES
This app analyzes vector (AI/EPS), PNG, and photo (JPG/JPEG/PNG) files
entirely offline and compares the measured facts against publicly
documented technical specs for Adobe Stock, Shutterstock, Freepik,
Vecteezy, Depositphotos, and Dreamstime.

WHAT THIS APP DOES NOT DO
It does not predict whether a human/AI reviewer will accept your file.
It does not check keyword relevance, catalog duplication, trademark issues,
or model/property release validity — none of that is possible offline.
Anywhere the app can't determine something offline, it says so explicitly
instead of guessing.

TABS
- Vector: analyze a single AI/EPS file (structure, live text, linked
  files, hidden layers, auto-fix size/padding suggestions).
- PNG: analyze a single PNG (resolution, transparency, occupancy).
- Photos: analyze a single JPG/PNG photo (sharpness, noise, exposure,
  composition).
- Batch Checker: analyze many files at once, export a CSV summary, and
  detect near-duplicate images in the batch.
- Reports: view/save the last generated report as .txt or .json.
- Settings: appearance mode + optional dependency status (PyMuPDF and
  Ghostscript enable deeper analysis but are not required for the core
  checks).
- About: app info and developer credit.

TIPS
- For AI files, install PyMuPDF (`pip install pymupdf`) for full analysis.
- Occupancy/empty-space on flattened JPEGs is an ESTIMATE based on border
  color; PNGs with real transparency get an EXACT measurement.
- The app never edits your original files unless you explicitly use an
  "Apply Fix" action, and even then it always writes to a new file.
"""


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x760")
        self.minsize(900, 600)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        for name in ["Vector", "PNG", "Photos", "Batch Checker", "Reports", "Settings", "About", "Help"]:
            self.tabview.add(name)

        self.vector_tab = BaseFileTab(
            self.tabview.tab("Vector"), "Vector Module (AI / EPS)",
            [("Vector files", "*.ai *.eps")],
            vector_analysis.analyze_vector, "vector", self
        )
        self.vector_tab.pack(fill="both", expand=True)

        self.png_tab = BaseFileTab(
            self.tabview.tab("PNG"), "PNG Module",
            [("PNG files", "*.png")],
            raster_analysis.analyze_raster, "png", self
        )
        self.png_tab.pack(fill="both", expand=True)

        self.photo_tab = BaseFileTab(
            self.tabview.tab("Photos"), "Photo Module (JPG / JPEG / PNG)",
            [("Photo files", "*.jpg *.jpeg *.png")],
            raster_analysis.analyze_raster, "photo", self
        )
        self.photo_tab.pack(fill="both", expand=True)

        self.batch_tab = BatchTab(self.tabview.tab("Batch Checker"), self)
        self.batch_tab.pack(fill="both", expand=True)

        self.reports_tab = ReportsTab(self.tabview.tab("Reports"))
        self.reports_tab.pack(fill="both", expand=True)

        self.settings_tab = SettingsTab(self.tabview.tab("Settings"))
        self.settings_tab.pack(fill="both", expand=True)

        self.about_tab = AboutTab(self.tabview.tab("About"))
        self.about_tab.pack(fill="both", expand=True)

        self.help_tab = HelpTab(self.tabview.tab("Help"))
        self.help_tab.pack(fill="both", expand=True)

    def show_report(self, filename, analysis, mk_results):
        self.reports_tab.show(filename, analysis, mk_results)
        self.tabview.set("Reports")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
