#!/usr/bin/env python3
"""Refresh the list of Afisha magazine issues from the publisher's FlipHTML5 bookshelf.

Writes content/afisha.json (newest first). New issues are merged in; issues already
saved are kept, so a temporary outage or a shorter shelf never wipes the archive.
Run:  python scripts/afisha.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "afisha.json"
SHELF = "https://fliphtml5.com/home/togmr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en-US;q=0.8,en;q=0.6",
}

# month stems in Russian / Ukrainian / English titles -> month number
MONTHS = [
    (1, ["январ", "січ", "january"]), (2, ["феврал", "лют", "february"]),
    (3, ["март", "берез", "march"]), (4, ["апрел", "квіт", "april"]),
    (5, ["май", "мая", "травн", "may"]), (6, ["июн", "черв", "june"]),
    (7, ["июл", "лип", "july"]), (8, ["август", "серп", "august"]),
    (9, ["сентябр", "верес", "september"]), (10, ["октябр", "жовт", "october"]),
    (11, ["ноябр", "листопад", "november"]), (12, ["декабр", "груд", "december"]),
]

BOOK = re.compile(
    r'\{"id":(\d+),[^{}]*?"title":"((?:[^"\\]|\\.)*)","desc":"((?:[^"\\]|\\.)*)"'
    r'[^{}]*?"bLink":"([^"]+)","newTime":(\d+)')


def month_of(text: str) -> int | None:
    low = text.lower()
    for n, stems in MONTHS:
        if any(s in low for s in stems):
            return n
    return None


SKIP = re.compile(r"http|www\.|читайте|слушайте|подкаст|радио|не пропустите|выпуск|^#", re.I)


def topics(desc: str) -> tuple[str, list[str]]:
    """Split the publisher's description into a short intro and a list of topic headings."""
    intro, items = "", []
    for raw in desc.replace("\r", "").split("\n"):
        l = raw.strip()
        if not l or SKIP.search(l) or re.match(r"^в (этом|цьому) номер", l, re.I) or l.startswith(("—", "-", "–")):
            continue
        if re.match(r"^[^\w«\"(]", l):                # starts with an emoji / bullet -> topic heading
            head = re.sub(r"^[^\w«\"(]+", "", l).strip()
            head = re.split(r"\.\s|\.$|!\s|!$", head)[0].strip(" .")
            if len(head) > 95:
                head = head[:92].rsplit(" ", 1)[0] + "…"
            if head:
                items.append(head)
        elif not intro and not items:
            intro = l if len(l) <= 420 else l[:417].rsplit(" ", 1)[0] + "…"
    return intro, items[:9]


def fetch() -> list[dict]:
    r = requests.get(SHELF, headers=HEADERS, timeout=30)
    html = r.text
    print(f"  shelf: HTTP {r.status_code}, {len(html)} bytes, bLink x{html.count('bLink')}")
    if "bLink" not in html:
        print("  page start:", re.sub(r"\s+", " ", html[:300]))
    issues = []
    for m in BOOK.finditer(html):
        title = json.loads(f'"{m[2]}"')
        desc = json.loads(f'"{m[3]}"')
        if not re.search(r"афиш|afisha", title, re.I):   # skip other publications on the shelf
            continue
        pub = datetime.fromtimestamp(int(m[5]) / 1000, timezone.utc).date()
        month = month_of(title) or month_of(m[4]) or pub.month
        y = re.search(r"20\d\d", title + " " + m[4])
        year = int(y[0]) if y else pub.year
        if not y and month == 1 and pub.month == 12:      # January issue released in late December
            year += 1
        if not y and month == 12 and pub.month == 1:
            year -= 1
        intro, items = topics(desc)
        slug = m[4]
        issues.append({
            "slug": slug, "year": year, "month": month, "published": pub.isoformat(),
            "url": f"https://online.fliphtml5.com/togmr/{slug}/",
            "cover": f"https://online.fliphtml5.com/togmr/{slug}/files/shot.jpg",
            "intro": intro, "topics": items,
        })
    return issues


def main() -> None:
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    try:
        new = fetch()
    except Exception as e:
        print(f"! Afisha shelf unavailable, keeping saved list: {e}")
        return
    if not new:
        print("! No issues found on the shelf, keeping saved list")
        return
    by_slug = {i["slug"]: i for i in old}
    by_slug.update({i["slug"]: i for i in new})
    # one entry per month: the newest upload wins
    by_month: dict[tuple, dict] = {}
    for i in by_slug.values():
        k = (i["year"], i["month"])
        if k not in by_month or i["published"] > by_month[k]["published"]:
            by_month[k] = i
    issues = sorted(by_month.values(), key=lambda i: (i["year"], i["month"]), reverse=True)
    OUT.write_text(json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Afisha: {len(issues)} issues, latest {issues[0]['month']:02d}/{issues[0]['year']}")


if __name__ == "__main__":
    sys.exit(main())
