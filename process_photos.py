#!/usr/bin/env python3
"""Crop, resize and compress the downloaded photos, then write credits.

Keeps the page light: guests open this on a phone, often on mobile data, so
every image is re-encoded at a sensible display size and the unused
candidates are removed.
"""

import json
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "assets", "photos")

# slot -> (source candidate, output name, target size, focal bias, quality)
# Focal bias picks the vertical crop: 0.5 centres, lower keeps heads/hands.
PICKS = {
    "hero":   ("hero-1.jpg",   "hero",   (1600, 1067), 0.5,  72),
    "mehndi": ("mehndi-1.jpg", "mehndi", (1000, 750),  0.5,  78),
    "baraat": ("baraat-2.jpg", "baraat", (800, 1000),  0.45, 78),
    "ritual": ("ritual-2.jpg", "ritual", (1000, 667),  0.5,  78),
}
# Extra small render of the hero for phones.
HERO_SMALL = (800, 534)


def crop_to(img, size, bias=0.5):
    """Cover-crop to `size`, keeping the region around `bias` vertically."""
    target_ratio = size[0] / size[1]
    w, h = img.size
    if w / h > target_ratio:                      # too wide, trim sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:                                          # too tall, trim vertically
        new_h = int(w / target_ratio)
        top = int((h - new_h) * bias)
        img = img.crop((0, top, w, top + new_h))
    return img.resize(size, Image.LANCZOS)


def save(img, path, quality=80):
    img.convert("RGB").save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(path)


def main():
    with open(os.path.join(OUT, "CREDITS.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)

    used, before = set(), 0
    for slot, (src, name, size, bias, quality) in PICKS.items():
        src_path = os.path.join(OUT, src)
        if not os.path.exists(src_path):
            print(f"  !! missing source for {slot}: {src}")
            continue
        used.add(src)
        before += os.path.getsize(src_path)

        img = ImageOps.exif_transpose(Image.open(src_path))
        dest = os.path.join(OUT, f"{name}.jpg")
        size_kb = save(crop_to(img, size, bias), dest, quality) // 1024
        print(f"  {name}.jpg  {size[0]}x{size[1]}  {size_kb}KB")

        if slot == "hero":
            small = save(crop_to(img, HERO_SMALL, bias), os.path.join(OUT, "hero-sm.jpg"), 70)
            print(f"  hero-sm.jpg  {HERO_SMALL[0]}x{HERO_SMALL[1]}  {small // 1024}KB")

    # Every candidate is now either re-encoded under a new name or unused.
    keep = {f"{v[1]}.jpg" for v in PICKS.values()} | {"hero-sm.jpg"}
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".jpg") and f not in keep:
            os.remove(os.path.join(OUT, f))
            print(f"  removed {f}")

    # Human-readable credits, published next to the images.
    lines = [
        "# Photo credits",
        "",
        "Photographs are reused under the licences listed below. Sources are",
        "Wikimedia Commons.",
        "",
    ]
    for slot, (src, name, size, bias, quality) in PICKS.items():
        for hit in manifest.get(slot, []):
            if hit.get("file") != src:
                continue
            lines += [
                f"## {name}.jpg",
                "",
                f"- Source: {hit['title']}",
                f"- Author: {hit.get('author') or 'see source page'}",
                f"- Licence: {hit.get('licence')}",
                f"- Page: {hit.get('page')}",
                "",
            ]
    with open(os.path.join(OUT, "CREDITS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    kept = sum(
        os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith(".jpg")
    )
    print(f"\n{before // 1024}KB of candidates -> {kept // 1024}KB shipped")


if __name__ == "__main__":
    main()
