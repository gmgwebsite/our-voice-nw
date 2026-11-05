#!/usr/bin/env python3
"""Daily robot for Our Voice NW.

1. Reads the RSS feeds listed in config.yaml
2. Asks Claude to pick the 3–4 stories that matter most to our readers
3. Reads each chosen article and asks Claude to write an ORIGINAL short news piece
   in Russian and Ukrainian (not a copy, not a word-for-word translation)
4. Saves each story to content/articles/<id>.json

Needs the environment variable ANTHROPIC_API_KEY.
Run:  python scripts/fetch_and_write.py            (normal daily run)
      python scripts/fetch_and_write.py --dry-run  (show what would be picked, write nothing)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import feedparser
import requests
import yaml

from images import find_image

try:
    import trafilatura  # better full-text extraction
except ImportError:  # pragma: no cover
    trafilatura = None

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
UA = "OurVoiceNW-NewsBot/1.0 (+community news digest; links back to sources)"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def clean(text: str, limit: int | None = None) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:limit] if limit else text


def seen_urls() -> set[str]:
    urls = set()
    for p in ARTICLES.glob("*.json"):
        try:
            urls.add(json.loads(p.read_text(encoding="utf-8"))["source"]["url"])
        except Exception:
            pass
    return urls


def collect(cfg) -> list[dict]:
    max_age = timedelta(hours=cfg["pipeline"].get("max_age_hours", 36))
    now = datetime.now(timezone.utc)
    skip = seen_urls() if cfg["pipeline"].get("avoid_duplicates", True) else set()
    items = []
    for src in cfg["sources"]:
        try:
            r = requests.get(src["url"], headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
        except Exception as e:
            log(f"  ! skipped feed {src['name']}: {e}")
            continue
        n = 0
        for e in feed.entries[:40]:
            t = e.get("published_parsed") or e.get("updated_parsed")
            when = datetime(*t[:6], tzinfo=timezone.utc) if t else now
            link = e.get("link")
            if not link or link in skip or now - when > max_age:
                continue
            items.append({
                "source": src["name"], "url": link, "title": clean(e.get("title", "")),
                "summary": clean(e.get("summary", ""), 600), "published": when.isoformat(),
            })
            n += 1
        log(f"  · {src['name']}: {n} fresh items")
    # de-duplicate by title
    uniq, titles = [], set()
    for it in items:
        k = it["title"].lower()[:80]
        if k not in titles:
            titles.add(k)
            uniq.append(it)
    return uniq


def full_text(url: str, fallback: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
        r.raise_for_status()
        if trafilatura:
            txt = trafilatura.extract(r.text, include_comments=False, include_tables=False) or ""
        else:
            txt = clean(r.text)
        if len(txt) > 400:
            return txt[:12000]
    except Exception as e:
        log(f"  ! could not read {url}: {e}")
    return fallback


# ---------- Claude ----------
SELECT_TOOL = {
    "name": "select_stories",
    "description": "Return the chosen stories for today's edition.",
    "input_schema": {
        "type": "object",
        "properties": {
            "picks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "Number of the candidate"},
                        "category": {"type": "string"},
                        "rank": {"type": "integer", "description": "1 = lead story of the day"},
                        "reason": {"type": "string"},
                    },
                    "required": ["index", "category", "rank", "reason"],
                },
            }
        },
        "required": ["picks"],
    },
}

def _lang_fields(lang: str, name: str) -> dict:
    return {
        f"{lang}_title": {"type": "string", "description": f"{name} headline, max ~90 characters, no clickbait"},
        f"{lang}_summary": {"type": "string", "description": f"{name}: 1-2 sentence lede with the key fact"},
        f"{lang}_body": {"type": "string", "description": f"{name}: 3-5 short paragraphs separated by a blank line"},
        f"{lang}_why": {"type": "string", "description": f"{name}: 2-3 sentences on why this matters to our readers / what to do"},
    }


# Flat string fields only: newer models fill these far more reliably than nested objects.
WRITE_TOOL = {
    "name": "publish_article",
    "description": "Publish the finished bilingual article, or skip it if the source is insufficient.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skip": {"type": "boolean", "description": "true if the source text is too thin, unclear or not newsworthy"},
            "skip_reason": {"type": "string"},
            "slug": {"type": "string", "description": "short latin-letter url slug, e.g. tps-ukraine-extension"},
            "image_queries": {"type": "string", "description": (
                "2-3 short English search phrases for Wikimedia Commons, separated by ' | ', "
                "most specific first. Name a real PLACE, BUILDING or LANDMARK central to the story "
                "(e.g. 'Idaho State Capitol | Boise Idaho skyline'), or a public figure's name. "
                "Never describe an event, a crowd or a private person.")},
            **_lang_fields("ru", "Russian"),
            **_lang_fields("uk", "Ukrainian"),
        },
        "required": ["skip"],
    },
}


def unflatten(out: dict) -> dict:
    """Turn ru_title/ru_body/... fields into {"ru": {...}, "uk": {...}}."""
    for lang in ("ru", "uk"):
        if isinstance(out.get(lang), dict):
            continue
        if isinstance(out.get(lang), str):  # sometimes a JSON string
            try:
                v = json.loads(out[lang])
                if isinstance(v, dict):
                    out[lang] = v
                    continue
            except json.JSONDecodeError:
                pass
        body = out.get(f"{lang}_body", "")
        out[lang] = {
            "title": (out.get(f"{lang}_title") or "").strip(),
            "summary": (out.get(f"{lang}_summary") or "").strip(),
            "body": [x.strip() for x in re.split(r"\n\s*\n|\n", body) if x.strip()] if isinstance(body, str) else body,
            "why": (out.get(f"{lang}_why") or "").strip(),
        }
    return out


WRITER_RULES = """You are the editor of "Our Voice NW", a news site for Russian- and Ukrainian-speaking
people in the US Pacific Northwest. Write ONE short news article in BOTH Russian (ru) and Ukrainian (uk)
based ONLY on the source text provided.

Strict rules:
- Write in your own words. Do NOT translate the source sentence by sentence and do NOT copy
  more than a few words in a row. Quotes: at most one short quote, clearly attributed.
- Use ONLY facts present in the source. Never invent numbers, dates, names, quotes or advice.
  If something is unclear, leave it out. If the source is too thin to write a reliable piece, set skip=true.
- Neutral, calm, factual tone. No opinions, no clickbait, no political slant.
- Keep English proper names recognisable; add the original in brackets the first time when useful
  (e.g. «Служба гражданства и иммиграции США (USCIS)»). Keep program names like TPS, U4U, SNAP, Medicaid.
- Ukrainian must be natural, idiomatic Ukrainian written for Ukrainians — not a calque of the Russian text.
- "why": explain plainly why this matters to immigrants/refugees in WA/OR/ID and any concrete
  next step stated in the source (deadline, where to apply). For legal topics add that this is not legal advice.
- Body: 3–5 short paragraphs, 180–320 words per language in total.
"""


def ask(client, model, system, user, tool, max_tokens=4000):
    # Some newer models don't accept a forced tool_choice, so we let the model
    # choose ("auto"), tell it to use the tool, and fall back to parsing JSON text.
    system = system + (f"\n\nAlways answer by calling the `{tool['name']}` tool exactly once. "
                       "Do not reply with plain text.")
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                tools=[tool], tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": user}],
            )
            text = ""
            for block in msg.content:
                if block.type == "tool_use":
                    return block.input
                if block.type == "text":
                    text += block.text
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            log("  ! Claude answered without using the tool; retrying…")
        except anthropic.BadRequestError as e:
            raise RuntimeError(f"Claude rejected the request: {e}") from e
        except anthropic.APIError as e:
            log(f"  ! Claude error ({e}); retrying…")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Claude did not return a result")


def valid_article(out) -> bool:
    """True only if both languages have a proper title, summary, body list and why."""
    for lang in ("ru", "uk"):
        b = out.get(lang) if isinstance(out, dict) else None
        if not isinstance(b, dict):
            return False
        if not all(isinstance(b.get(k), str) and b[k].strip() for k in ("title", "summary", "why")):
            return False
        body = b.get("body")
        if isinstance(body, str):  # tolerate a single string by splitting paragraphs
            body = [x.strip() for x in body.split("\n") if x.strip()]
            b["body"] = body
        if not (isinstance(body, list) and body and all(isinstance(x, str) for x in body)):
            return False
        if "<parameter" in b["title"] or "<parameter" in " ".join(body):
            return False
    return True


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "story"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    pl, cats = cfg["pipeline"], cfg["categories"]
    model = os.environ.get("CLAUDE_MODEL") or pl["model"]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")
    client = anthropic.Anthropic()

    log("Collecting news…")
    cands = collect(cfg)
    log(f"{len(cands)} candidate stories")
    if not cands:
        log("Nothing new today.")
        return

    listing = "\n".join(
        f"[{i}] ({c['source']}) {c['title']} — {c['summary'][:300]}" for i, c in enumerate(cands[:150]))
    n = pl.get("stories_per_day", 4)
    sel = ask(client, model,
              "You are the news editor for a Russian/Ukrainian-language community news site in the US Pacific Northwest.",
              f"Editorial brief:\n{cfg['editorial_brief']}\n\nAllowed categories: {', '.join(cats)}\n\n"
              f"Pick the {n} most important and useful stories for our readers from the candidates below. "
              f"Pick distinct topics (no two stories about the same event). Give each a category and a rank (1 = lead).\n\n{listing}",
              SELECT_TOOL, max_tokens=1500)
    picks = sorted(sel["picks"], key=lambda p: p["rank"])[:n]
    for p in picks:
        if 0 <= p["index"] < len(cands):
            log(f"  ✓ #{p['rank']} [{p['category']}] {cands[p['index']]['title']}  — {p['reason']}")
    if args.dry_run:
        return

    today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    written = 0
    for p in picks:
        if not (0 <= p["index"] < len(cands)):
            continue
        c = cands[p["index"]]
        cat = p["category"] if p["category"] in cats else "local"
        log(f"Writing: {c['title']}")
        text = full_text(c["url"], c["summary"])
        prompt = (f"Source: {c['source']}\nOriginal headline: {c['title']}\nPublished: {c['published']}\n"
                  f"URL: {c['url']}\nSection: {cats[cat]['ru']}\n\nSOURCE TEXT:\n{text}")
        out = None
        for attempt in range(3):
            try:
                out = ask(client, model, WRITER_RULES, prompt, WRITE_TOOL)
            except RuntimeError as e:
                log(f"  ! {e}")
                out = None
                break
            if not out.get("skip"):
                out = unflatten(out)
            if out.get("skip") or valid_article(out):
                break
            log("  ! malformed article from Claude; asking again…")
            out = None
        if not out or out.get("skip") or not valid_article(out):
            log(f"  – skipped: {(out or {}).get('skip_reason', 'no valid article')}")
            continue
        aid = f"{today}-{slugify(out.get('slug') or c['title'])}"
        art = {
            "id": aid, "date": today, "rank": p["rank"], "category": cat,
            "source": {"name": c["source"], "url": c["url"], "title": c["title"]},
            "ru": out["ru"], "uk": out["uk"],
            "generated": {"model": model, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        }
        queries = [q.strip() for q in str(out.get("image_queries") or "").split("|") if q.strip()]
        art["image_queries"] = queries
        img = find_image(queries) if queries else None
        art["image_checked"] = True
        if img:
            art["image"] = img
            log(f"  🖼  photo: {img['title']} ({img['license']})")
        else:
            log("  –  no suitable free photo; using the colored cover")
        (ARTICLES / f"{aid}.json").write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1

    # Remove demo articles once real ones exist
    if written:
        for f in ARTICLES.glob("*.json"):
            try:
                if json.loads(f.read_text(encoding="utf-8")).get("sample"):
                    f.unlink()
            except Exception:
                pass
    log(f"Done: {written} new articles.")


if __name__ == "__main__":
    main()
