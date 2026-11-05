#!/usr/bin/env python3
"""Build the static Our Voice NW website (Russian + Ukrainian) into ./public.

Reads every article JSON in content/articles/ and renders HTML pages with Jinja2.
Run:  python scripts/build.py
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"
LANGS = ["ru", "uk"]

MONTHS = {
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
           "сентября", "октября", "ноября", "декабря"],
    "uk": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
           "вересня", "жовтня", "листопада", "грудня"],
}
WEEKDAYS = {
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
    "uk": ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"],
}

T = {  # interface strings
    "ru": {
        "home": "Главная", "latest": "Свежие новости", "top": "Главное сегодня",
        "archive": "Архив", "about": "О проекте", "search": "Поиск",
        "search_ph": "Поиск по новостям…", "no_results": "Ничего не найдено",
        "read_more": "Читать", "min": "мин чтения", "why": "Почему это важно",
        "source": "Источник", "read_original": "Читать оригинал",
        "ai_note": "Материал подготовлен с помощью ИИ (Claude) на основе публикации источника и проверен по исходному тексту. Нашли ошибку? Напишите нам.",
        "related": "Читайте также", "share": "Поделиться", "copy": "Скопировать ссылку",
        "copied": "Скопировано", "other_lang": "Українською", "all_in": "Все материалы раздела",
        "empty": "Здесь пока нет материалов.", "sections": "Разделы",
        "theme": "Сменить тему", "menu": "Меню", "updated": "Обновляется ежедневно",
        "rights": "Все права на исходные материалы принадлежат их авторам.",
        "skip": "Перейти к содержанию", "demo": "Демо-режим: показаны примеры материалов. Настоящие новости появятся после первого запуска робота.", "back_top": "Наверх", "rss": "RSS",
    },
    "uk": {
        "home": "Головна", "latest": "Свіжі новини", "top": "Головне сьогодні",
        "archive": "Архів", "about": "Про проєкт", "search": "Пошук",
        "search_ph": "Пошук новин…", "no_results": "Нічого не знайдено",
        "read_more": "Читати", "min": "хв читання", "why": "Чому це важливо",
        "source": "Джерело", "read_original": "Читати оригінал",
        "ai_note": "Матеріал підготовлено за допомогою ШІ (Claude) на основі публікації джерела та перевірено за вихідним текстом. Знайшли помилку? Напишіть нам.",
        "related": "Читайте також", "share": "Поділитися", "copy": "Скопіювати посилання",
        "copied": "Скопійовано", "other_lang": "По-русски", "all_in": "Усі матеріали розділу",
        "empty": "Тут поки немає матеріалів.", "sections": "Розділи",
        "theme": "Змінити тему", "menu": "Меню", "updated": "Оновлюється щодня",
        "rights": "Усі права на вихідні матеріали належать їхнім авторам.",
        "skip": "Перейти до змісту", "demo": "Демо-режим: показано приклади матеріалів. Справжні новини з'являться після першого запуску робота.", "back_top": "Вгору", "rss": "RSS",
    },
}

ABOUT = {
    "ru": [
        "«Our Voice NW» — ежедневная лента самых важных новостей для русско- и украиноязычных жителей Вашингтона, Орегона и Айдахо.",
        "Каждое утро мы просматриваем местные и национальные издания и выбираем 3–4 истории, которые действительно влияют на жизнь нашего сообщества: иммиграция, работа, жильё, здоровье, школы, местные законы и события.",
        "Тексты готовятся с помощью искусственного интеллекта (Claude от Anthropic): он кратко пересказывает публикацию своими словами на русском и украинском и объясняет, почему это важно. Мы всегда указываем источник и ссылку на оригинал.",
        "Это не юридическая консультация. По вопросам иммиграции обращайтесь к лицензированному адвокату или аккредитованной организации.",
    ],
    "uk": [
        "«Our Voice NW» — щоденна стрічка найважливіших новин для російсько- та україномовних мешканців Вашингтона, Орегону та Айдахо.",
        "Щоранку ми переглядаємо місцеві та національні видання й обираємо 3–4 історії, які справді впливають на життя нашої громади: імміграція, робота, житло, здоров'я, школи, місцеві закони та події.",
        "Тексти готуються за допомогою штучного інтелекту (Claude від Anthropic): він стисло переказує публікацію своїми словами українською та російською й пояснює, чому це важливо. Ми завжди вказуємо джерело та посилання на оригінал.",
        "Це не юридична консультація. З питань імміграції звертайтеся до ліцензованого адвоката або акредитованої організації.",
    ],
}


def fmt_date(d: str, lang: str, weekday: bool = False) -> str:
    dt = date.fromisoformat(d[:10])
    s = f"{dt.day} {MONTHS[lang][dt.month - 1]} {dt.year}"
    if weekday:
        s = f"{WEEKDAYS[lang][dt.weekday()].capitalize()}, {s}"
    return s


def load_articles() -> list[dict]:
    arts = []
    for p in sorted((ROOT / "content" / "articles").glob("*.json")):
        a = json.loads(p.read_text(encoding="utf-8"))
        a.setdefault("id", p.stem)
        arts.append(a)
    # newest day first; within a day, rank 1 (lead story) first
    arts.sort(key=lambda a: (a["date"], -a.get("rank", 9)), reverse=True)
    return arts


def reading_time(a: dict, lang: str) -> int:
    words = sum(len(p.split()) for p in a[lang]["body"]) + len(a[lang].get("why", "").split())
    return max(1, math.ceil(words / 180))


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    site, cats = cfg["site"], cfg["categories"]
    articles = load_articles()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html", "xml"]))
    env.filters["date"] = fmt_date
    build_time = datetime.now(timezone.utc).isoformat(timespec="minutes")

    def render(tpl: str, path: Path, **ctx) -> None:
        depth = len(path.relative_to(OUT).parts) - 1
        ctx["root"] = "../" * depth if depth else "./"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(tpl).render(**ctx), encoding="utf-8")

    # language splash / redirect
    render("root.html", OUT / "index.html", site=site, T=T)
    render("404.html", OUT / "404.html", site=site, T=T)

    sitemap = []
    for lang in LANGS:
        other = "uk" if lang == "ru" else "ru"
        base = dict(site=site, cats=cats, lang=lang, other=other, t=T[lang],
                    tagline=site["tagline"][lang], build_time=build_time,
                    has_samples=any(a.get("sample") for a in articles))
        for a in articles:
            a.setdefault("_rt", {})[lang] = reading_time(a, lang)
        latest_day = articles[0]["date"] if articles else date.today().isoformat()
        top = [a for a in articles if a["date"] == latest_day][:4]
        rest = [a for a in articles if a not in top]

        by_cat = {c: [a for a in articles if a["category"] == c] for c in cats}

        def pg(rel: str) -> Path:
            return OUT / lang / rel

        render("index.html", pg("index.html"), **base, page="home", top=top,
               rest=rest[:12], by_cat=by_cat, today=latest_day,
               alt_url=f"{other}/index.html")
        sitemap.append(f"{lang}/index.html")

        for c in cats:
            render("category.html", pg(f"c/{c}.html"), **base, page=c, cat=c,
                   items=by_cat[c], alt_url=f"{other}/c/{c}.html")
            sitemap.append(f"{lang}/c/{c}.html")

        # archive grouped by date
        days: dict[str, list] = {}
        for a in articles:
            days.setdefault(a["date"], []).append(a)
        render("archive.html", pg("archive.html"), **base, page="archive", days=days,
               alt_url=f"{other}/archive.html")
        render("about.html", pg("about.html"), **base, page="about", about=ABOUT[lang],
               alt_url=f"{other}/about.html")

        for a in articles:
            related = [b for b in articles if b is not a and b["category"] == a["category"]][:3]
            if len(related) < 3:
                related += [b for b in articles if b is not a and b not in related][: 3 - len(related)]
            render("article.html", pg(f"a/{a['id']}.html"), **base, page=a["category"],
                   a=a, related=related, alt_url=f"{other}/a/{a['id']}.html",
                   canonical=f"{site['base_url']}/{lang}/a/{a['id']}.html")
            sitemap.append(f"{lang}/a/{a['id']}.html")

        # search index
        idx = [{"id": a["id"], "t": a[lang]["title"], "s": a[lang]["summary"],
                "c": cats[a["category"]][lang], "d": fmt_date(a["date"], lang)} for a in articles]
        (OUT / lang / "search.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")

        # RSS
        items = [{
            "title": a[lang]["title"], "summary": a[lang]["summary"],
            "link": f"{site['base_url']}/{lang}/a/{a['id']}.html",
            "date": format_datetime(datetime.fromisoformat(a["date"]).replace(tzinfo=timezone.utc)),
        } for a in articles[:30]]
        render("feed.xml", pg("feed.xml"), **base, items=items)

    urls = "\n".join(f"  <url><loc>{site['base_url']}/{u}</loc></url>" for u in sitemap)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',
        encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}/sitemap.xml\n")
    print(f"Built {len(articles)} articles × {len(LANGS)} languages → {OUT}")


if __name__ == "__main__":
    main()
