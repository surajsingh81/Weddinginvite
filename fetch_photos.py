#!/usr/bin/env python3
"""Download freely-licensed photos for the invitation from Wikimedia Commons.

Only permissive licences are accepted (CC0, Public domain, CC BY, CC BY-SA).
Everything else, including NC and ND variants, is skipped. Attribution for
each accepted file is written to docs/assets/photos/CREDITS.json so the
credits can be published alongside the site.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "assets", "photos")
API = "https://commons.wikimedia.org/w/api.php"
UA = "wedding-invite-build/1.0 (personal invitation; contact via GitHub repo)"

# Licences we are willing to publish under.
OK_LICENCE = re.compile(
    r"^(cc0|public domain|cc by([ -]sa)?([ -]\d(\.\d)?)?|pd[- ]|no restrictions)", re.I
)
BAD_LICENCE = re.compile(r"[- ](nc|nd)\b", re.I)

# slot -> Commons search terms. The first slot becomes the hero image, so it is
# deliberately searched for wide, bright, unambiguous flower photography.
SLOTS = {
    "hero": "marigold garden yellow flowers",
    "mehndi": "mehndi henna hands bride India",
    "baraat": "decorated horse India wedding",
    "ritual": "jasmine gajra flower garland",
}


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def search(term, limit=8, width=1800):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {term}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": str(width),
        "format": "json",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as fh:
        data = json.load(fh)

    out = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not lic or BAD_LICENCE.search(lic) or not OK_LICENCE.search(lic):
            continue
        thumb = info.get("thumburl")
        if not thumb:
            continue
        out.append(
            {
                "title": page.get("title", ""),
                "licence": lic,
                "author": clean_html(meta.get("Artist", {}).get("value", "")),
                "credit": clean_html(meta.get("Credit", {}).get("value", "")),
                "page": "https://commons.wikimedia.org/wiki/"
                + urllib.parse.quote(page.get("title", "").replace(" ", "_")),
                "thumb": thumb,
                "width": info.get("thumbwidth") or 0,
                "height": info.get("thumbheight") or 0,
            }
        )
    return out


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as fh:
        blob = fh.read()
    if len(blob) < 8000:
        raise ValueError(f"suspiciously small ({len(blob)} bytes)")
    with open(dest, "wb") as out:
        out.write(blob)
    return len(blob)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}

    for slot, term in SLOTS.items():
        print(f"\n=== {slot}: {term}")
        try:
            hits = search(term)
        except Exception as exc:  # network hiccup should not kill the build
            print(f"  search failed: {exc}")
            continue
        if not hits:
            print("  no permissively-licensed candidates")
            continue

        # Prefer landscape and reasonably large.
        hits.sort(key=lambda h: (h["width"] >= 1400, h["width"] * h["height"]), reverse=True)

        saved = 0
        for hit in hits:
            if saved >= 2:
                break
            name = f"{slot}-{saved + 1}.jpg"
            dest = os.path.join(OUT, name)
            try:
                size = download(hit["thumb"], dest)
            except Exception as exc:
                print(f"  skip {hit['title']}: {exc}")
                continue
            print(f"  {name}  {hit['width']}x{hit['height']}  {size // 1024}KB  [{hit['licence']}]")
            print(f"      {hit['title']}")
            manifest.setdefault(slot, []).append({**{k: v for k, v in hit.items() if k != "thumb"}, "file": name})
            saved += 1

    with open(os.path.join(OUT, "CREDITS.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    total = sum(len(v) for v in manifest.values())
    print(f"\nwrote CREDITS.json for {total} image(s)")


if __name__ == "__main__":
    sys.exit(main())
