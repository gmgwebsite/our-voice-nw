# Our Voice NW: automatic Russian and Ukrainian news site

Every morning a robot:

1. reads local and national news feeds (Seattle Times, OPB, Washington State Standard, NPR and others; see `config.yaml`),
2. asks **Claude** to pick the 3–4 stories that matter most to Russian- and Ukrainian-speaking people in WA, OR and ID,
3. has Claude write a short **original** article for each story in Russian and in Ukrainian, with a "Why this matters" box and a link to the source,
4. publishes the stories to the website, or sends them to you for one-click approval first.

Hosting on GitHub Pages is free. The only running cost is Claude API usage, roughly $3–10 a month for 4 stories a day.

---

## One-time setup (about 20 minutes, no coding)

### 1. Put the project on GitHub
1. Create a free account at <https://github.com>.
2. Click **New repository**, name it `our-voice-nw`, choose **Public**, and click **Create**.
3. On the new repository page, click **uploading an existing file**. Drag in **everything inside this folder**, including the hidden `.github` folder. (On a Mac, press `Cmd+Shift+.` in Finder to show hidden folders.) Then click **Commit changes**.

### 2. Turn on the website
**Settings → Pages → Build and deployment → Source: GitHub Actions.**

### 3. Add your Claude API key
1. Get a key at <https://console.anthropic.com> (**API Keys → Create key**) and add a few dollars of credit.
2. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
   Name: `ANTHROPIC_API_KEY`. Value: paste the key.

### 4. Set your site address
In `config.yaml`, change `base_url` to `https://<your-github-username>.github.io/our-voice-nw` and `contact_email` to your email address. You can edit files directly on GitHub with the pencil icon.

### 5. Do a first run
Go to **Actions → Daily news → Run workflow**. After a few minutes:
- **Review mode** (the default): open **Pull requests**, read the stories, and click **Merge**. The site updates about a minute later.
- When you trust the robot, set `auto_publish: true` in `config.yaml` and stories will go live with no approval step.

The demo articles are deleted automatically when the first real stories arrive.

---

## Everyday controls (all in `config.yaml`)

| Want to… | Change |
|---|---|
| Publish more or fewer stories per day | `stories_per_day` |
| Skip the approval step | `auto_publish: true` |
| Change which stories get picked | `editorial_brief` (plain English) |
| Add or remove news sources | `sources` (any RSS feed) |
| Rename sections or change their colors | `categories` |
| Use a newer Claude model | `model` |
| Change the run time | `cron` line in `.github/workflows/daily-news.yml` |

**Fixing a story:** open `content/articles/<story>.json` on GitHub, click the pencil icon, edit the text, and commit. The site rebuilds itself.
**Removing a story:** delete its `.json` file.

**Custom domain** (for example, ourvoicenw.org): Settings → Pages → Custom domain. Then update `base_url`.

---

## Running it on your own computer (optional)

```bash
pip install -r requirements.txt
python scripts/check_feeds.py                 # test the news sources
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/fetch_and_write.py --dry-run   # see which stories it would pick
python scripts/fetch_and_write.py             # write them
python scripts/build.py                       # build the site into ./public
python -m http.server -d public 8000          # open http://localhost:8000
```

## How it stays legal and trustworthy
- Claude writes **new text in its own words**. It never copies or translates a full article, and it quotes at most one short line. Every story credits and links to the original source.
- Claude is told to use only facts that appear in the source, and to skip a story if the source is too thin.
- Cover images are generated from section colors and icons, so no copyrighted photos are used.
- Every article carries an AI disclosure and a contact email for corrections.
- Review mode lets a person check every story before it goes live. Keep it on for at least the first few weeks.
- This isn't legal advice. Immigration stories remind readers to consult a licensed attorney.

## Files
```
config.yaml                 ← all settings
content/articles/*.json     ← one file per story (RU + UK)
scripts/fetch_and_write.py  ← the daily robot (Claude)
scripts/build.py            ← turns stories into the website
scripts/check_feeds.py      ← tests news sources
templates/, static/         ← site design (HTML, CSS, JS)
.github/workflows/          ← daily schedule + automatic deploy
```
