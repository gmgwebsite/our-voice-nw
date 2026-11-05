#!/usr/bin/env python3
"""Find a freely licensed photo on Wikimedia Commons for each story.

Only photos with licenses that allow reuse are accepted (public domain, CC0,
CC BY, CC BY-SA). The photographer and license are saved with the story and
shown under the photo, as those licenses require.

Run on its own to add photos to stories that don't have one yet:
    python scripts/images.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia asks automated clients to identify themselves.
UA = "OurVoiceNW-NewsBot/1.0 (https://gmgwebsite.github.io/our-voice-nw/; community news site)"

OK_LICENSE = re.compile(r"^(public domain|pd\b|cc0|cc[ -]by(-sa)?[ -]?\d?)", re.I)
BAD_WORDS = re.compile(r"\b(logo|map|flag|coat of arms|seal|diagram|chart|icon|svg|signature)\b", re.I)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _plain(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


GENERIC = {"State", "City", "County", "Downtown", "Building", "Center", "Centre", "The", "Of", "And",
           "North", "South", "East", "West", "New", "Old", "Main", "Street", "Park", "Hall"}


def relevant(query: str, text: str) -> bool:
    """The photo must actually show what we searched for: at least half of the
    distinctive capitalized words in the query (place or person names) must
    appear in the photo's title or description."""
    names = [w for w in re.findall(r"[A-Z][\w'.-]+", query) if w not in GENERIC] or \
            [w for w in re.findall(r"[A-Z][\w'.-]+", query)]
    if not names:
        return False
    low = text.lower()
    hits = sum(1 for w in names if w.lower() in low)
    return hits >= 1 and hits * 2 >= len(names)


def search_commons(query: str, limit: int = 12) -> dict | None:
    """Return the best freely licensed photo for `query`, or None."""
    if not query or not query.strip():
        return None
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrnamespace": "6", "gsrlimit": str(limit),
        "gsrsearch": f"{query} filetype:bitmap",
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1400",
    }
    try:
        r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", [])
    except Exception as e:
        log(f"  ! Commons search failed for '{query}': {e}")
        return None

    pages.sort(key=lambda p: p.get("index", 99))
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        title = p.get("title", "")
        lic = _plain(meta.get("LicenseShortName", {}).get("value", ""))
        if info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        if info.get("width", 0) < 900 or info.get("width", 0) < info.get("height", 1):  # landscape only
            continue
        if not OK_LICENSE.search(lic) or "nc" in lic.lower() or "nd" in lic.lower():
            continue
        if BAD_WORDS.search(title):
            continue
        if not relevant(query, title + " " + _plain(meta.get("ImageDescription", {}).get("value", ""))[:300]):
            continue
        author = _plain(meta.get("Artist", {}).get("value", "")) or "Unknown author"
        return {
            "url": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl"),
            "author": author[:120],
            "license": lic,
            "license_url": meta.get("LicenseUrl", {}).get("value", ""),
            "title": re.sub(r"^File:|\.\w+$", "", title),
            "query": query,
        }
    return None


def find_image(queries: list[str]) -> dict | None:
    for q in queries:
        img = search_commons(q)
        if img:
            return img
    return None


IMAGE_VERSION = 2  # bump to make the robot re-check every story's photo


def suggest_queries(a: dict) -> list[str]:
    """Ask Claude for Wikimedia search phrases for an older story."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic
        import yaml
        model = os.environ.get("CLAUDE_MODEL") or yaml.safe_load(
            (ROOT / "config.yaml").read_text(encoding="utf-8"))["pipeline"]["model"]
        msg = anthropic.Anthropic().messages.create(
            model=model, max_tokens=200,
            messages=[{"role": "user", "content": (
                "Give 2-3 short English search phrases for Wikimedia Commons to find a real photo "
                "for this news story. Name a real PLACE, BUILDING or LANDMARK central to it, or a public "
                "figure. Never an event, crowd or private person. Answer with the phrases only, "
                "separated by ' | ', most specific first.\n\n"
                f"Headline: {a.get('source', {}).get('title', '')}\nSummary: {a.get('ru', {}).get('summary', '')}")}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return [q.strip(" .\"'") for q in text.split("|") if q.strip()][:3]
    except Exception as e:
        log(f"  ! could not get photo search terms from Claude: {e}")
        return []


def backfill() -> int:
    """Add photos to stories that don't have a current-version photo check."""
    added = 0
    for f in sorted(ARTICLES.glob("*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        if a.get("sample") or a.get("image_version", 0) >= IMAGE_VERSION:
            continue
        qs = [q for q in (a.get("image_queries") or []) if q] or suggest_queries(a)
        a["image_queries"] = qs
        a.pop("image", None)
        img = find_image(qs)
        a["image_checked"] = True
        a["image_version"] = IMAGE_VERSION
        if img:
            a["image"] = img
            added += 1
            log(f"  🖼  {f.name}: {img['title']} ({img['license']})")
        else:
            log(f"  –  {f.name}: no suitable photo")
        f.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


if __name__ == "__main__":
    n = backfill()
    log(f"Done: {n} photos added.")
