"""
gui/fix_actions.py

Explicit, user-triggered fix actions. These are the ONLY functions in the
app that ever write a modified image file, and they always write to a NEW
path chosen by the user — original files are never overwritten silently,
per the brief's "DO NOT automatically edit files unless the user explicitly
requests it" requirement.
"""
from __future__ import annotations
from PIL import Image
from core.raster_analysis import strip_exif_and_save


def apply_resize(src_path: str, dst_path: str, target_w: int, target_h: int):
    with Image.open(src_path) as img:
        resized = img.resize((target_w, target_h), Image.LANCZOS)
        resized.save(dst_path)


def apply_strip_metadata(src_path: str, dst_path: str):
    strip_exif_and_save(src_path, dst_path)


def apply_flatten_transparency(src_path: str, dst_path: str, bg_color=(255, 255, 255)):
    with Image.open(src_path) as img:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, bg_color)
            bg.paste(rgba, mask=rgba.split()[-1])
            bg.save(dst_path)
        else:
            img.convert("RGB").save(dst_path)
