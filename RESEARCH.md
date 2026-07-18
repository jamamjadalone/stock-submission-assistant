# Research & Feasibility Notes — Stock Submission Assistant

This document records what was checked before writing code, per the brief's
Phase 1 / Phase 2 requirement. It states plainly what CAN be verified
offline from a file itself, and what CANNOT — because it depends on a
marketplace's live moderation team, algorithm, or account-specific data.

## Hard rule applied throughout the code

Every number this app reports is either:
- Read directly from file metadata/bytes (dimensions, DPI, color mode, file size, EPS/PDF version tags, embedded objects, etc.), or
- Computed directly from pixel/vector data with a named, deterministic algorithm (e.g. Laplacian variance for blur, histogram stats for exposure).

Nothing is a machine-learning "acceptance score", nothing is a sales
prediction, and nothing claims to know what a human reviewer will decide.
Where the requested feature needs that, the code returns the literal string
`"Cannot be determined offline"` and explains why.

## Per-marketplace: what is publicly documented and checkable offline

The technical submission specs below are publicly published by each
marketplace (dimensions, formats, DPI/megapixel minimums). They are static
facts, so they are safe to hard-code as reference data (`data/marketplace_rules.json`)
and compare a file against, offline, with no network call. What is NOT
safe to hard-code is anything that changes over time without notice
(promotions, category quotas, trending keywords, acceptance rates) — those
are excluded.

| Marketplace | Offline-checkable | NOT offline-checkable |
|---|---|---|
| Adobe Stock | Min 4MP for photos/PNG, vector artboard size rules, EPS 10 recommendation, embedded raster/live-font/linked-file detection in AI/EPS, sRGB check | Actual moderation decision, keyword relevance, similarity to existing catalog, trend/demand |
| Shutterstock | Min 4MP / min 3.5MP for photos, no upscaling detectable heuristically only (not provable offline), vector file structure checks | Content moderation, "editorial vs commercial" classification, model/property release validity |
| Freepik | Min resolution/format rules, PSD/AI/EPS structure checks | Premium/free tier acceptance, review queue outcome |
| Vecteezy | Vector cleanliness checks (paths, fonts outlined), PNG/JPEG resolution | Curator approval, exclusivity terms |
| Depositphotos | Resolution/format/DPI checks | Reviewer decision, release document validity (can't verify a PDF is a *real* signed release, only that a file is attached) |
| Dreamstime | Resolution/DPI/format checks, basic noise/sharpness heuristics (Dreamstime is known for strict quality review) | Actual quality review outcome, isolation/pure-white-background judgment beyond simple heuristic |

Across every marketplace, the following are algorithmically CANNOT-DO items,
and the code says so instead of guessing:
- Whether an image is a copy/trademark/logo infringement (needs internet + reverse image search)
- Whether a property/model release is valid (needs human/legal check)
- Whether keywords/title are "relevant enough" (needs the marketplace's live taxonomy)
- Whether the artwork is a duplicate of something already in the catalog (needs the marketplace's database)
- Final accept/reject outcome (needs the human/AI reviewer on their servers)

## Feature discovery beyond the brief (Phase 2 additions)

While researching what image-processing libraries can reliably compute
offline, these were added because they are cheap, deterministic, and
directly useful to a contributor, even though the prompt didn't name them
explicitly:
- **EXIF/metadata leak checker** — flags GPS/location or personal camera
  metadata left in JPEGs before upload (privacy + rejection risk).
- **Duplicate/near-duplicate detector within a batch** — perceptual hash
  (`imagehash`-style, implemented locally with a DCT hash) so a contributor
  doesn't upload near-identical frames of the same shot as "different" files.
- **ICC profile presence/sRGB mismatch check** for photos and PNGs.
- **Vector "text not outlined" detector** — parses AI-PDF font resources
  and EPS DSC font comments, since live text is one of the most common
  Adobe Stock vector rejections.
- **Batch summary CSV/JSON export** for spreadsheet-based QA workflows.

## Libraries used and why

- **Pillow** — raster metadata, EXIF, ICC profile, resizing for fix previews.
- **NumPy** — histogram/statistics math.
- **OpenCV (cv2)** — Laplacian-variance blur/sharpness, noise estimate.
- **scikit-image** — SSIM-based near-duplicate comparison as a cross-check.
- **PyMuPDF (fitz)** — AI files are PDF-compatible; used to read page/artboard
  size, embedded images, fonts, and OCG (layer) names without needing
  Illustrator.
- Vector analysis targets **AI** and **EPS** only; SVG support was removed
  to keep the module focused on the formats most commonly required by
  major stock marketplaces.
- **CustomTkinter** — desktop UI.

EPS is analyzed as *text* (PostScript is largely ASCII/DSC-comment based),
reading `%%BoundingBox`, `%%Creator`, `%%For`, `%%DocumentFonts`, and
similar Document Structuring Convention comments. This is reliable for the
metadata fields but cannot rasterize the artwork without Ghostscript,
which is treated as optional (see Settings tab).

## Correction: artwork size vs. artboard size

An earlier version of this tool measured the 4MP-style minimum against the
vector file's **artboard/canvas** dimensions. That's wrong — Adobe Stock's
own published requirement is explicit that the minimum applies to **the
artwork itself**, not the empty canvas around it. A 4000x4000pt artboard
with a tiny 500x500pt icon centered in it does NOT meet a 4MP artwork
requirement, even though the artboard alone would.

Fixed by adding a genuine artwork-bounding-box measurement:
- **AI files**: PyMuPDF computes the union of all vector path bounding
  boxes, embedded image bounding boxes, and text bounding boxes on the
  page, then clips that union to the artboard (to discard stray off-canvas
  objects). This is the real "ink extent" of the artwork.
- **EPS files**: by the PostScript DSC specification, `%%BoundingBox` is
  *already defined* as the tightest box enclosing the actual marks on the
  page — it was never an arbitrary canvas size to begin with, so it's used
  directly as the artwork size.

If the artwork extent can't be reliably isolated (e.g. PyMuPDF fallback
mode without full parsing), the app explicitly says so and declines to
run the MP auto-fix suggestion rather than silently using the artboard
size as a stand-in, which could understate how much scaling is needed.

## Simplified to MP-only marketplace checks

Per a later scope decision, the marketplace PASS/FAIL comparison was
simplified to check **resolution (megapixels) only** — the one number
every marketplace publishes unambiguously and that this tool can measure
with total confidence. Format, transparency, and color-mode notes are
still shown in the per-file Analysis section (they're genuinely useful
info) but are no longer folded into the marketplace verdict, since those
rules vary more and change more often across marketplaces than the core
resolution requirement does. This keeps the "PASS/WARNING/FAIL" verdict
meaning one consistent thing everywhere: does the artwork/photo/PNG meet
the published megapixel minimum.

Also fixed in this pass: `marketplace_rules.json` previously used
inconsistent key names between marketplaces (`photo_png_min_megapixels`
for Adobe Stock vs. `photo_min_megapixels` for everyone else), and the
lookup code's fallback checked the *same missing key twice* — meaning
Adobe Stock's photo resolution was silently never being verified. Data
file now uses one consistent `photo_min_megapixels` / `png_min_megapixels`
schema across all six marketplaces.
