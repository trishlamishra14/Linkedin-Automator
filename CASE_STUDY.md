# LinkedIn Automator — Case Study

> *Project 05 · AI Agents & Automation pillar · Trishla Mishra*
>
> A multi-agent content system that turns a 2-line idea into a fully drafted,
> brand-voice LinkedIn post — and ships it on a schedule, headless, with a
> screenshot for proof.

---

## TL;DR

| | |
|---|---|
| **Built in** | 1 weekend |
| **Stack** | Anthropic Claude · Playwright · FastAPI · APScheduler · SQLite · Vanilla JS |
| **Lines of code** | ~720 (excluding HTML/CSS) |
| **What it replaces** | A 30-min daily writing-and-posting ritual |
| **Outcome (target)** | 5 on-brand LinkedIn posts/week, sub-3 minutes per post |

---

## Problem

Every founder I talk to says the same thing about LinkedIn:

> *"I know I should post. I sit down. I stare. I open Twitter. I close my laptop."*

The cost isn't the writing. It's the **starting**. By the time the founder
remembers their angle, finds their voice, and types the post, it's 11:47 AM and
the morning is gone.

I needed a system that:

1. Knew my voice well enough to draft a post that sounds like me.
2. Let me approve / edit before anything went live.
3. Could schedule and publish without me opening a browser at 9 AM.
4. Logged every published post for performance review later.

LinkedIn's official API requires an Anthropic-style approval process I didn't
want to wait on. Off-the-shelf schedulers (Buffer, Typefully) are great but
they don't *write* the post — they only *send* it.

So I built the missing piece.

---

## Solution

A four-layer system, all running locally, all under my control.

### 1. The content agent (`src/content_agent.py`)

A thin wrapper around the Anthropic Messages API. Two methods:

- `generate_ideas(count, focus)` — returns 5 fresh hooks with audience + format hints.
- `write_post(topic)` — returns a JSON object: `{content, hashtags}`.

Both calls inject the brand/voice/strategy context as plain markdown. No
LangChain, no chains, no agents-of-agents. Just one Claude call, strict JSON,
parsed defensively.

Why a folder of markdown for context? Because **prompts are the new SOPs**.
Editing voice rules should feel like editing a Notion doc, not refactoring
Python.

### 2. The browser worker (`src/linkedin_poster.py`)

Async Playwright session. First run, it logs in with your `.env` creds and
saves `state.json`. Every subsequent run reuses the cookie jar and skips
straight to the composer.

Selectors live in one dict at the top of the file — when LinkedIn changes the
DOM (and they will), it's a 3-line fix.

Every successful post gets a timestamped screenshot in `data/screenshots/`.
That screenshot becomes proof for portfolio and for clients.

### 3. The scheduler (`src/scheduler.py`)

APScheduler running in-process. `schedule_post(post_id, fire_at)` registers a
DateTrigger; the job pulls the post from SQLite at fire time and routes through
the browser worker.

Three posting modes (`dry_run`, `manual_review`, `auto`) make this safe to
demo: dry-run never touches LinkedIn, manual_review always waits on a human
click, auto is the full-send mode.

### 4. The dashboard (`web/`)

Single HTML page. No build step. Three columns:

- **Compose** — type a topic, hit Write.
- **Preview** — edit the draft, save, schedule, or publish now.
- **History** — every draft / scheduled / published / failed post, click to
  reload.

Styled to match the rest of my portfolio: dark `#070014` background, electric
purple `#A855F7`, hot pink `#EC4899`, glass surfaces with backdrop blur. The
status pill in the top-right pulses cyan when the server is online.

---

## Architecture

```
   User                 FastAPI                 SQLite
    │                      │                       │
    │  POST /posts/write   │                       │
    ├──────────────────────▶                       │
    │                      │  Anthropic.messages   │
    │                      ├──────────────────────▶│
    │                      │◀ JSON {content, tags} │
    │                      │  insert draft         │
    │                      ├──────────────────────▶│
    │◀───────── draft ─────┤                       │
    │                      │                       │
    │ POST /schedule       │                       │
    ├──────────────────────▶ APScheduler.add_job   │
    │                      │                       │
    │                  ⏰  fire_at reached         │
    │                      │  load post            │
    │                      ◀───────────────────────┤
    │                      │  Playwright.publish   │
    │                      ├──────▶ LinkedIn       │
    │                      │  screenshot           │
    │                      │  update status        │
    │                      ├──────────────────────▶│
```

---

## Build decisions worth defending

**Why Anthropic Claude over GPT-4?** Sonnet 4.5 is the most reliable JSON-mode
model I've used for SOP-style prompting. The voice it produces from a markdown
brand brief is closer to "you" than any model I tested.

**Why Playwright over Selenium / Puppeteer?** Better async ergonomics, built-in
storage state for session reuse, and the file-chooser API for image attach is
two lines instead of twenty.

**Why APScheduler over Celery + Redis?** Solo-user product. Zero infra. The
moment I need multi-tenant or fan-out, swap to Celery in an afternoon.

**Why SQLite over Postgres?** Single file. Backs up via `cp data/posts.db`.
Scales to ~100K posts before I'd care.

**Why vanilla JS for the dashboard?** Three files. No npm. No build pipeline.
The whole UI ships in 8KB of JS.

---

## What I'd ship next

1. **Image agent** — the SOP folder already plans for it. DALL·E or Flux call,
   image saved to `data/images/`, attached to the draft.
2. **Carousel generator** — PIL renders branded slides → PDF → uploaded as a
   document post.
3. **Engagement agent** — reads comments on the last 5 published posts, drafts
   replies in your voice, queues them for approval.
4. **Marketing API path** — once Anthropic-approved, swap the Playwright worker
   for an HTTP client. Same scheduler, same dashboard.

---

## What this proves about me

- **Multi-agent thinking + production deployment** — content agent, browser
  worker, scheduler, dashboard all communicating through a clean DB layer.
- **Browser automation under real-world conditions** — selectors, session
  persistence, error screenshots, file-chooser handling.
- **Pragmatic stack choices** — picked the smallest tool for each job and
  justified each one.
- **Design taste** — the dashboard is not an after-thought. It looks like a
  product, not a developer demo.
- **Business framing** — the README and this case study lead with outcomes,
  not technology.

---

*Live demo: `python run.py` → `http://127.0.0.1:8000`*
*Source: [github.com/trishlamishra14/Linkedin-Automator](https://github.com/trishlamishra14/Linkedin-Automator)*
