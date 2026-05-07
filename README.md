<div align="center">

<h1>LinkedIn Automator</h1>

<p><strong>An AI agent that learns your LinkedIn voice, watches the world for trends in your niche, and ships posts on your schedule.</strong></p>

<p>
  <a href="#quick-start">Quick start</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#api-reference-v2">API</a> ·
  <a href="#roadmap">Roadmap</a>
</p>

<p>
  <img src="https://img.shields.io/badge/license-MIT-3b82f6.svg" alt="MIT license" />
  <img src="https://img.shields.io/badge/python-3.10+-3b82f6.svg" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/status-v0.2-0ea5e9.svg" alt="v0.2" />
  <img src="https://img.shields.io/badge/self--hosted-yes-10b981.svg" alt="Self-hosted" />
</p>

</div>

---

> Watches HackerNews / Reddit / Google News for trending topics in your
> niche, drafts posts in your voice, generates a matching image, schedules
> and publishes via a real browser — all self-hosted.

Built with **Anthropic Claude**, **Playwright**, **Replicate (Flux)**, and
**FastAPI**, by [Trishla Mishra](https://trishla.dev). Open source under the MIT license.

---

## What it does (v2)

```
   [LinkedIn profile URL]
            │
            ▼
   profile_analyzer ──▶  Playwright scrapes bio + recent posts
            │            Claude extracts niche, audience, tone, hooks
            ▼
   context/voice.md  ◀── auto-generated brand profile
   context/brand.md
            │
            ▼
   trend_scout ──▶  HackerNews + Reddit + Google News
            │       Claude scores 0-100 against your niche
            ▼
   [you pick a trend]  or  [you paste your own topic / draft]
            │
            ▼
   content_agent ──▶  Claude writes the post in your voice
            │
            ▼
   image_agent  ──▶  Claude crafts an image prompt
            │       Replicate Flux generates the visual
            ▼
   linkedin_poster ──▶  Playwright publishes to LinkedIn
            │           Screenshot saved as proof
            ▼
   SQLite history (drafts, scheduled, published, failed)
```

Three things make this different from any "AI writes my LinkedIn posts" tool:

1. **Voice learned from your own profile**, not a free-text brand brief.
2. **Topic intel from three free sources**, ranked by relevance to your niche.
3. **End-to-end self-hosted** — Claude API key + LinkedIn login + Replicate
   token, nothing else.

---

## Live

- **Marketing site + interactive demo:** [linkedin-automator.vercel.app](https://linkedin-automator.vercel.app) *(replace with your deploy URL)*
- **Vision dashboard preview:** [linkedin-automator.vercel.app/demo](https://linkedin-automator.vercel.app/demo)
- **Self-hosted runtime:** `python run.py` → `http://127.0.0.1:8000`

---

## Quick start

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. configure
cp .env.example .env
# edit .env: ANTHROPIC_API_KEY, LINKEDIN_EMAIL/PASSWORD, REPLICATE_API_TOKEN

# 3. run
python run.py
# open http://127.0.0.1:8000
```

### First-time setup (5 minutes)

1. Open the dashboard, click the **Setup** tab.
2. Paste your LinkedIn profile URL.
3. **Uncheck "Run headless"** for the first analysis — a Chromium window opens
   so you can solve any "verify you're human" challenge LinkedIn throws.
4. Hit **Analyze profile**. Takes 30-60 seconds.
5. The result auto-populates `context/voice.md` and `context/brand.md`.
6. Switch to **Trends**, hit **↻ Refresh**. First refresh takes ~30s while
   Claude scores items.
7. Pick a trend → click **Write post** → it lands as a draft in **Compose**.
8. (optional) Click **+ Image** to generate a brand-matched visual.
9. Edit, then **Publish now** or **Schedule**.

---

## Deploy the marketing site

The repo ships with a `site/` folder containing a single-page marketing landing
that embeds the interactive demo. Push to Vercel in one click:

```bash
# install Vercel CLI (once)
npm i -g vercel

# from the repo root, deploy
vercel deploy --prod
```

The included [`vercel.json`](./vercel.json) handles the routing — `/` serves the
marketing landing, `/demo` serves the interactive dashboard preview. No build
command needed; it's pure static HTML.

Project layout:

```
site/         marketing landing (deployed to /)
web/          live dashboard runtime (only when self-hosted)
preview.html  interactive demo, embedded by site/ and exposed at /demo
```

---

## Architecture

```
linkedin-automator/
├── src/
│   ├── profile_analyzer.py  ★ NEW — Playwright + Claude profile analysis
│   ├── trend_scout.py       ★ NEW — HN + Reddit + Google News + ranking
│   ├── image_agent.py       ★ NEW — Replicate Flux image generation
│   ├── content_agent.py     # Claude content generation (writes posts)
│   ├── linkedin_poster.py   # Playwright browser automation (publishes)
│   ├── scheduler.py         # APScheduler — cron + one-shot jobs
│   ├── api.py               # FastAPI server (15+ routes)
│   ├── db.py                # SQLModel: Profile, Trend, Post tables
│   └── config.py            # pydantic-settings (.env)
├── context/
│   ├── brand.md             # auto-generated by profile_analyzer
│   ├── voice.md             # auto-generated by profile_analyzer
│   └── strategy.md          # cadence + rotation (you edit this once)
├── data/
│   ├── posts.db             # SQLite history
│   ├── images/              # Replicate-generated images
│   └── screenshots/         # Playwright captures of every published post
├── web/                     # vanilla-JS dashboard with 3 tabs
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── requirements.txt
├── run.py
└── README.md
```

### Why these tools

| Layer            | Pick               | Reason                                                                        |
|------------------|--------------------|-------------------------------------------------------------------------------|
| Profile analysis | Playwright + Claude| LinkedIn has no public profile API. Scrape once, analyze structurally.        |
| Content writing  | Anthropic Claude   | Best JSON-mode reliability for SOP-style prompting + voice mimicry.            |
| Trend sources    | HN + Reddit + GNews| All free, no API keys required (Reddit OAuth optional for higher rate limits).|
| Trend ranking    | Anthropic Claude   | Single 0-100 score against niche + suggested angle in one call.                |
| Image generation | Replicate Flux Schnell | ~$0.003/image, photo-realistic, no signup beyond Replicate.                |
| Posting          | Playwright         | Works without LinkedIn API approval delays.                                    |
| Scheduler        | APScheduler        | In-process, no Redis/Celery overhead.                                          |
| Storage          | SQLite + SQLModel  | Zero-config; one file portable across machines.                                |
| UI               | Vanilla JS + CSS   | Three tabs, no build step, drops into FastAPI's static mount.                  |

### Posting modes (set `POSTING_MODE` in `.env`)

- **`dry_run`** — generate everything, never open a real browser. Best for prompt iteration.
- **`manual_review`** *(default)* — drafts wait in the dashboard for human approval.
- **`auto`** — scheduled posts publish unattended. Use after you trust the prompts.

---

## API reference (v2)

| Method | Path                                  | Purpose                                              |
|--------|---------------------------------------|------------------------------------------------------|
| GET    | `/api/health`                         | Health + posting mode                                |
| GET    | `/api/profile`                        | Current analyzed profile                             |
| POST   | `/api/profile/analyze`                | `{url, headless?}` — scrape + analyze a profile      |
| GET    | `/api/trends`                         | List ranked trends (`?only_unused=true&min_relevance=60`) |
| POST   | `/api/trends/refresh`                 | Background refresh trends from all sources           |
| POST   | `/api/posts/from-trend`               | `{trend_id}` — draft a post seeded by a trend         |
| POST   | `/api/ideas`                          | `{count, focus?}` — generate ideas from idea bank    |
| POST   | `/api/posts/write`                    | `{topic, polish?}` — write OR polish a draft         |
| GET    | `/api/posts`                          | List posts (`?status=draft|scheduled|published|failed`) |
| GET    | `/api/posts/{id}`                     | One post                                              |
| PATCH  | `/api/posts/{id}`                     | Edit content / hashtags / image                       |
| DELETE | `/api/posts/{id}`                     | Delete                                                |
| POST   | `/api/posts/{id}/schedule`            | `{fire_at}` ISO datetime                              |
| POST   | `/api/posts/{id}/cancel`              | Cancel a scheduled post                               |
| POST   | `/api/posts/{id}/publish-now`         | Publish immediately                                   |
| POST   | `/api/posts/{id}/generate-image`      | Replicate-generated image attached to the post        |
| GET    | `/api/images/{filename}`              | Serve a generated image back to the dashboard         |

---

## Forking it for your own brand

Two paths:

**Path A — auto-learn (recommended).** Open the dashboard → Setup → paste your
profile URL. The agent writes `context/voice.md` + `context/brand.md` for you.

**Path B — manual.** Edit `context/voice.md`, `context/brand.md`, and
`context/strategy.md` directly. The content agent reads any markdown there.

Either way, `context/strategy.md` (cadence + rotation) is something you tune
manually — that's the part the agent shouldn't infer for you.

---

## Risks & guardrails

- **LinkedIn scraping is fragile.** First run: `headless=False`, solve any
  challenge manually, let `state.json` save your session.
- **Posting too fast = flagged account.** Default cadence is one post/weekday.
  Don't crank it to hourly.
- **Replicate costs.** Flux Schnell is ~$0.003/image. Set a spend cap in your
  Replicate dashboard.
- **Claude costs.** Profile analysis ≈ $0.02. Trend scoring ≈ $0.04 per refresh.
  Post generation ≈ $0.005. Set a monthly cap in your Anthropic console.

---

## Roadmap

- [x] Profile analyzer (Playwright + Claude)
- [x] Trend scout (HN + Reddit + Google News, ranked)
- [x] Image generation (Replicate Flux)
- [x] Polish-my-draft mode
- [ ] Engagement-back agent: read your last 5 posts' comments, draft replies
- [ ] Carousel slide generator (PIL → PDF)
- [ ] LinkedIn Marketing API path once approved
- [ ] Multi-account support (post for clients)

---

## License

MIT.
