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
MONTHS_NOM = {
    "ru": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
           "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
    "uk": ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень", "Липень", "Серпень",
           "Вересень", "Жовтень", "Листопад", "Грудень"],
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
        "ai_note": "Материал основан на публикации источника. Нашли ошибку? Напишите нам.",
        "related": "Читайте также", "share": "Поделиться", "copy": "Скопировать ссылку",
        "copied": "Скопировано", "other_lang": "Українською", "all_in": "Все материалы раздела",
        "empty": "Здесь пока нет материалов.", "sections": "Разделы",
        "theme": "Сменить тему", "menu": "Меню", "updated": "Обновляется ежедневно",
        "rights": "Все права на исходные материалы принадлежат их авторам.",
        "skip": "Перейти к содержанию", "photo": "Фото", "photo_note": "Иллюстративное фото", "demo": "Демо-режим: показаны примеры материалов.", "back_top": "Наверх", "rss": "RSS", "radio": "Радио", "listen": "Слушать радио", "on_air": "В эфире", "popout": "Слушать в отдельном окне", "close_player": "Закрыть плеер", "radio_intro": "Прямой эфир радио для славянской общины Северо-Запада. Нажмите «Слушать», чтобы включить трансляцию.", "radio_tip": "Совет: откройте плеер в отдельном окне — радио будет играть, пока вы читаете новости.", "radio_error": "Если трансляция не запускается, попробуйте позже или откройте станцию на TuneIn.", "open_tunein": "Открыть на TuneIn",
        "afisha": "Журнал «Афиша»", "afisha_short": "Афиша", "afisha_tag": "Журнал славянской общины Портленда с 1993 года",
        "afisha_intro": "Ежемесячный журнал о жизни русско- и украиноязычной общины Орегона и Юго-Западного Вашингтона: недвижимость, здоровье, иммиграция, семья, события и рецепты.",
        "afisha_current": "Свежий номер", "afisha_inside": "В этом номере", "afisha_read": "Читать онлайн",
        "afisha_here": "Листать здесь", "afisha_archive": "Архив номеров", "afisha_all": "Все номера",
        "afisha_lang_note": "", "afisha_more": "Больше о журнале и реклама в «Афише» —",
    },
    "uk": {
        "home": "Головна", "latest": "Свіжі новини", "top": "Головне сьогодні",
        "archive": "Архів", "about": "Про проєкт", "search": "Пошук",
        "search_ph": "Пошук новин…", "no_results": "Нічого не знайдено",
        "read_more": "Читати", "min": "хв читання", "why": "Чому це важливо",
        "source": "Джерело", "read_original": "Читати оригінал",
        "ai_note": "Матеріал підготовлено на основі публікації джерела. Знайшли помилку? Напишіть нам.",
        "related": "Читайте також", "share": "Поділитися", "copy": "Скопіювати посилання",
        "copied": "Скопійовано", "other_lang": "По-русски", "all_in": "Усі матеріали розділу",
        "empty": "Тут поки немає матеріалів.", "sections": "Розділи",
        "theme": "Змінити тему", "menu": "Меню", "updated": "Оновлюється щодня",
        "rights": "Усі права на вихідні матеріали належать їхнім авторам.",
        "skip": "Перейти до змісту", "photo": "Фото", "photo_note": "Ілюстративне фото", "demo": "Демо-режим: показано приклади матеріалів.", "back_top": "Вгору", "rss": "RSS", "radio": "Радіо", "listen": "Слухати радіо", "on_air": "В ефірі", "popout": "Слухати в окремому вікні", "close_player": "Закрити плеєр", "radio_intro": "Прямий ефір радіо для слов'янської громади Північного Заходу. Натисніть «Слухати», щоб увімкнути трансляцію.", "radio_tip": "Порада: відкрийте плеєр в окремому вікні — радіо гратиме, поки ви читаєте новини.", "radio_error": "Якщо трансляція не запускається, спробуйте пізніше або відкрийте станцію на TuneIn.", "open_tunein": "Відкрити на TuneIn",
        "afisha": "Журнал «Афіша»", "afisha_short": "Афіша", "afisha_tag": "Журнал слов'янської громади Портленда з 1993 року",
        "afisha_intro": "Щомісячний журнал про життя російсько- та україномовної громади Орегону та Південно-Західного Вашингтона: нерухомість, здоров'я, імміграція, родина, події та рецепти.",
        "afisha_current": "Свіжий номер", "afisha_inside": "У цьому номері", "afisha_read": "Читати онлайн",
        "afisha_here": "Гортати тут", "afisha_archive": "Архів номерів", "afisha_all": "Усі номери",
        "afisha_lang_note": "Журнал виходить російською мовою.", "afisha_more": "Більше про журнал і реклама в «Афіші» —",
    },
}

ABOUT = {
    "ru": [
        "«Our Voice NW» — ежедневная лента самых важных новостей для русско- и украиноязычных жителей Вашингтона, Орегона и Айдахо.",
        "Каждое утро мы просматриваем местные и национальные издания и выбираем 3–4 истории, которые действительно влияют на жизнь нашего сообщества: иммиграция, работа, жильё, здоровье, школы, местные законы и события.",
        "Мы кратко пересказываем публикации своими словами на русском и украинском и объясняем, почему это важно. Мы всегда указываем источник и ссылку на оригинал.",
        "Это не юридическая консультация. По вопросам иммиграции обращайтесь к лицензированному адвокату или аккредитованной организации.",
    ],
    "uk": [
        "«Our Voice NW» — щоденна стрічка найважливіших новин для російсько- та україномовних мешканців Вашингтона, Орегону та Айдахо.",
        "Щоранку ми переглядаємо місцеві та національні видання й обираємо 3–4 історії, які справді впливають на життя нашої громади: імміграція, робота, житло, здоров'я, школи, місцеві закони та події.",
        "Ми стисло переказуємо публікації своїми словами українською та російською й пояснюємо, чому це важливо. Ми завжди вказуємо джерело та посилання на оригінал.",
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
        try:
            a = json.loads(p.read_text(encoding="utf-8"))
            assert all(isinstance(a[l], dict) and isinstance(a[l]["body"], list) and a[l]["title"]
                       for l in LANGS)
        except Exception as e:  # never let one bad file break the whole site
            print(f"  ! skipping malformed article {p.name}: {e}")
            continue
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
    ap = ROOT / "content" / "afisha.json"
    try:
        afisha_raw = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else []
    except Exception as e:
        print(f"  ! afisha.json unreadable: {e}")
        afisha_raw = []

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
        base = dict(site=site, cats=cats, lang=lang, other=other, t=T[lang], radio=cfg.get("radio") or {},
                    tagline=site["tagline"][lang], build_time=build_time,
                    has_samples=any(a.get("sample") for a in articles),
                    afisha=[dict(i, label=f"{MONTHS_NOM[lang][i['month'] - 1]} {i['year']}",
                                 month_name=MONTHS_NOM[lang][i["month"] - 1]) for i in afisha_raw])
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
        if afisha_raw:
            render("afisha.html", pg("afisha.html"), **base, page="afisha", alt_url=f"{other}/afisha.html")
            sitemap.append(f"{lang}/afisha.html")
        if (cfg.get("radio") or {}).get("enabled"):
            render("radio.html", pg("radio.html"), **base, page="radio", alt_url=f"{other}/radio.html")
            render("radio_popup.html", pg("radio-player.html"), **base, page="radio")

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
