# LinkedIn Automator — Progress

> Living document. Updated at the end of every sprint.
> Current sprint: [`sprint-01-public-ship.md`](./sprint-01-public-ship.md)

---

## Vision

An AI agent + browser automation that learns your LinkedIn voice from your own profile, watches HackerNews / Reddit / Google News for trends in your niche, drafts posts in your voice (with A/B variants), generates a matching image, schedules and publishes — and drafts replies to comments in your voice. Self-hosted. Open source. Built with Anthropic Claude, Playwright, FastAPI, and Replicate.

The full UX vision is in [`preview.html`](./preview.html) — open it in a browser to see the seven-view product (Dashboard, Compose with A/B variants, Trends, Schedule, Inbox, Analytics, Setup with voice tuning).

The portfolio narrative is "AI agents & automation, shipped solo, end-to-end."

---

## Current state

### What works today (v0.2)
- **Profile analyzer** (`src/profile_analyzer.py`) — Playwright scrapes a LinkedIn profile URL, Claude extracts niche / audience / tone / hook patterns / topics, auto-writes `context/voice.md` and `context/brand.md`.
- **Trend scout** (`src/trend_scout.py`) — pulls from HackerNews API, Reddit JSON, and Google News RSS; Claude scores 0-100 against the user's niche.
- **Content agent** (`src/content_agent.py`) — generates ideas and full posts in your voice (single variant for now).
- **Image agent** (`src/image_agent.py`) — Claude crafts an image prompt, Replicate Flux Schnell generates, saves locally.
- **LinkedIn poster** (`src/linkedin_poster.py`) — Playwright async browser automation with persistent session via `state.json`.
- **Scheduler** (`src/scheduler.py`) — APScheduler with `DateTrigger` for scheduled posts and a daily cron for trend refresh.
- **API** (`src/api.py`) — FastAPI with 17 routes covering profile, trends, posts, schedule, images.
- **Database** (`src/db.py`) — SQLite + SQLModel with `Profile`, `Trend`, `Post` tables.
- **Live dashboard** (`web/`) — three working tabs (Compose, Trends, Setup) with the *old* dark cyberpunk-purple theme.

### Vision preview (HTML mockup, not wired to backend)
[`preview.html`](./preview.html) shows the target end-state: dark sky-blue Linear-style theme, sidebar nav with logo, seven views including Dashboard / Inbox / Analytics, A/B variants in Compose, voice-tuning sliders, command palette, notifications.

### Gap between live dashboard and vision preview
- Live dashboard uses old purple theme; vision uses dark sky-blue.
- Live has no Dashboard, Schedule, Inbox, or Analytics views.
- Live Compose has no A/B variants.
- Live Setup has no voice-tuning sliders.
- No command palette, notifications dropdown, or toasts in live dashboard.
- No engagement-back agent (Inbox is UI-only in the vision; needs backend in `src/`).
- No analytics aggregations (Analytics is UI-only in the vision; needs backend).

---

## Roadmap

### Sprint 1 — Brand refresh + public ship readiness *(active)*
Get the live dashboard onto the new dark sky-blue theme, drop the `trish.exe` branding, add the LinkedIn Automator logo + wordmark, ship LICENSE + GitHub-ready README. Don't add new views yet — just port the polish from `preview.html` to the parts of the app that already exist.

**Outcome:** project moves from "in build" to "shipped, open source" on the portfolio. One weekend of focused work.

See [`sprint-01-public-ship.md`](./sprint-01-public-ship.md).

### Sprint 2 — Dog-food on real LinkedIn *(planned)*
Set up `.env` with real keys, run profile analyzer on Trishla's actual LinkedIn, generate 5 posts, ship them through the tool over a real week. Capture screenshots and engagement numbers for the case study.

**Outcome:** real-world proof + concrete numbers in the portfolio case study.

### Sprint 3 — A/B variants + voice tuning *(planned)*
Add 3-variant generation to `content_agent`, add voice-tuning parameters (length, tone, specificity, contrarianism, self-disclosure) to the DB and prompt, expose sliders in the Setup view.

**Outcome:** Compose view matches the vision preview, content quality improves.

### Sprint 4 — Engagement agent (Inbox backend) *(planned)*
New module `src/engagement_agent.py`. Periodic poll of new comments on published posts, Claude drafts a reply in your voice, lands in the Inbox view for human approval.

**Outcome:** the Inbox view becomes real, closing the loop from posting to relationship-building.

### Sprint 5 — Analytics aggregations + view *(planned)*
Add aggregation queries to `db.py`, a stats endpoint to `api.py`, and the Analytics view from the preview (chart, heatmap, top posts, engagement-by-topic).

**Outcome:** project demonstrates closed feedback loop — write, post, measure, learn.

### Sprint 6 — Production hardening *(planned)*
Tests for the content agent, prompt regression evals, error handling for LinkedIn selector breakage, deploy options doc (Vercel for dashboard, Railway/Hetzner for the FastAPI worker).

**Outcome:** ready for paid client installs.

---

## Done log

### 2026-05-04 — Project initialized
- Built v0.1: content_agent, linkedin_poster, scheduler, api, db, dashboard with 3 tabs (Compose, Trends, Setup).
- Built v0.2: added profile_analyzer, trend_scout, image_agent. Extended db with Profile + Trend tables.
- Wrote 17-route FastAPI surface, vanilla JS dashboard with neon-purple theme.
- Created portfolio case study and added project card to `trishla-portfolio` Next.js site.
- Iterated dashboard preview through three theme rounds: dark cyberpunk → light Linear → dark sky-blue (current target).
- Saved final vision preview as [`preview.html`](./preview.html).

### 2026-05-04 — Sprint 1 shipped: brand refresh + GitHub-readiness
- Wrote [`progress.md`](./progress.md) and [`sprint-01-public-ship.md`](./sprint-01-public-ship.md).
- Ported the dark sky-blue theme tokens from `preview.html` into `web/styles.css`. No purple anywhere.
- Restructured `web/index.html` from top-tab layout to sidebar layout with brand logo (3-node SVG), wordmark, profile chip, and a new Dashboard landing view with 4 stat cards + activity feed.
- Adapted `web/app.js` for sidebar nav, default Dashboard landing, dashboard data hydration, profile chip auto-update, and keyboard shortcuts (D/C/T/S).
- Added MIT [`LICENSE`](./LICENSE).
- Refreshed README with centered hero, badges, anchor nav.
- All four nav items (Dashboard, Compose, Trends, Setup) functional. Existing backend wiring preserved.

**Definition-of-done check:**
- [x] `web/styles.css` uses the dark sky-blue token system, no purple.
- [x] `web/index.html` shows sidebar nav with logo + wordmark; `trish.exe` removed.
- [x] All four nav items work; backend wiring preserved.
- [x] Dashboard view renders without backend stats endpoint (uses placeholder cards + live data from existing `/api/posts`).
- [x] `LICENSE` exists (MIT).
- [x] README has GitHub-ready hero with badges.
- [x] No syntax errors (verified via Read tool — bash mount stale; files end at proper closure).

**Hand-off:** Next is Sprint 2 — set `.env`, run `python run.py`, hard-refresh the dashboard, and start the 30-day dog-food experiment on Trishla's real LinkedIn.

### 2026-05-04 — Sprint 1.5 shipped: marketing landing page + Vercel deploy
Gap caught: the `web/` dashboard only runs at localhost — there was no public-facing surface a portfolio visitor could land on without cloning the repo.

- Built [`site/index.html`](./site/index.html) — a full single-page marketing landing in the dark sky-blue brand. Sections: nav, hero with embedded live-demo iframe, "Built with" trust strip, Problem cards, How-it-works pipeline, Features grid (9 cards with v0.3/v0.4/v0.5 roadmap badges), Demo CTA, Architecture SVG diagram, Stack grid, Pricing (self-host free + API usage), FAQ (7 questions), final CTA, footer.
- Iframe in the hero shows the actual interactive `preview.html` framed inside a fake browser chrome.
- Added [`vercel.json`](./vercel.json) — rewrites `/` to `/site/index.html`, `/demo` to `/preview.html`, with sensible security headers.
- Project structure now cleanly separates surfaces: `site/` for marketing, `web/` for runtime, `preview.html` for the static interactive demo.

**Definition-of-done check:**
- [x] Single-page landing in dark sky-blue brand. No purple.
- [x] Hero with browser-framed iframe of the live preview.
- [x] Pricing transparency (self-hosted = $0, API costs = ~$3-5/mo).
- [x] FAQ covers the LinkedIn ToS / scraping risk question directly.
- [x] All CTAs link to GitHub repo placeholder URL — Trishla updates after creating repo.
- [x] Vercel config ready: deploy from project root, rewrites set up, security headers configured.

**To deploy:**
1. Push the project to GitHub (`gh repo create linkedin-automator --public --source=. --push`).
2. On Vercel: New Project → import the repo → no build command needed → Deploy.
3. Update `trishla-portfolio/src/data/projects.ts` `liveUrl` field to the Vercel URL.

### 2026-05-07 — LinkedIn Automator went live 🚀
- Pushed repo to GitHub: [github.com/trishlamishra14/Linkedin-Automator](https://github.com/trishlamishra14/Linkedin-Automator).
- Hit a snag: Vercel auto-detected the project as FastAPI (because of `requirements.txt` + `src/api.py`), which 404'd because no Python entry point matched Vercel's expected layout.
- Fix: copied `site/index.html` to repo root as `index.html` (so Vercel's default static behavior serves it for `/`), simplified `vercel.json` to just the `/demo` rewrite, and added a `.vercelignore` to exclude `src/`, `requirements.txt`, `run.py`, etc. — forcing a pure-static deploy regardless of preset.
- Live URL: **[linkedin-automator-t9n3.vercel.app](https://linkedin-automator-t9n3.vercel.app)**
- Updated `trishla-portfolio/src/data/projects.ts` `liveUrl` field to point at the live Vercel deployment.
- Updated README's "Live" section with the real URL (was a placeholder).
- **Project status:** "In build" → "Shipped, public, open source." 🎯

---

## Decisions log

**Why Anthropic Claude over OpenAI?** Claude Sonnet 4.5 has the most reliable JSON-mode output for SOP-style prompting and the best voice-mimicry from a markdown brand brief.

**Why Playwright over LinkedIn Marketing API?** API requires multi-week approval and is restricted; Playwright works today on personal accounts. Trade-off: selectors will break when LinkedIn changes the DOM (~every 6-9 months). Selectors are isolated to one dict at the top of `linkedin_poster.py` for fast fixes.

**Why APScheduler over Celery?** Solo-user product, no Redis or worker pool needed. Switch later if multi-tenant.

**Why SQLite over Postgres?** Single file, portable, fits a self-hosted product. Migrate to Postgres if multi-account / hosted SaaS.

**Why vanilla JS over React for the dashboard?** Three files, no build step, FastAPI serves them as static. Keeps the install path "clone, install, run" with no npm step. React would add 10 minutes of build setup for zero functional gain at this size.

**Why dark sky-blue instead of the portfolio's neon purple?** The product needs visual distinction from the personal brand. Trishla's portfolio is the *creator's* surface (cyberpunk-soft). The Automator is the *product* surface (premium SaaS, Linear-inspired). Different audiences expect different aesthetics.

**Why no purple in the product theme?** Direct user requirement (2026-05-04). Sky-blue (`#0EA5E9`) works for LinkedIn-adjacent product without copying LinkedIn's blue (`#0A66C2`), which is reserved inside the LinkedIn-style live preview only.
