#!/usr/bin/env python3
"""Test every RSS feed in config.yaml and report how many items each returns."""
from pathlib import Path
import feedparser, requests, yaml

cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
for s in cfg["sources"]:
    try:
        r = requests.get(s["url"], headers={"User-Agent": "OurVoiceNW-NewsBot/1.0"}, timeout=20)
        n = len(feedparser.parse(r.content).entries)
        print(f"{'OK ' if n else 'EMPTY'} {r.status_code}  {n:3d} items  {s['name']}")
    except Exception as e:
        print(f"FAIL       {s['name']}: {e}")
