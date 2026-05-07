# Architecture Notes

## Module map

```
src/
├── config.py          Settings via pydantic-settings; loads .env
├── db.py              SQLModel + SQLite; Post model + helpers
├── content_agent.py   Anthropic Claude API; ContentAgent class
├── linkedin_poster.py Playwright async; LinkedInPoster + publish_sync
├── scheduler.py       APScheduler BackgroundScheduler; date triggers
└── api.py             FastAPI app + routes + static mount
```

## Lifecycle of a post

```
draft  ──schedule──▶  scheduled  ──fire──▶  publishing  ──ok──▶  published
                                              │
                                              └──fail──▶  failed (with error + screenshot)
```

## Data model (single table)

```sql
CREATE TABLE post (
  id              INTEGER PRIMARY KEY,
  topic           TEXT,
  content         TEXT,
  hashtags        TEXT,
  image_path      TEXT,
  status          TEXT,             -- draft | scheduled | published | failed
  scheduled_for   TIMESTAMP,
  published_at    TIMESTAMP,
  linkedin_url    TEXT,
  error           TEXT,
  created_at      TIMESTAMP,
  updated_at      TIMESTAMP
);
```

## Failure modes & handling

| Failure                              | Handled by                                         |
|--------------------------------------|----------------------------------------------------|
| Claude returns malformed JSON        | `_parse_json` strips fences + falls back to `{...}`|
| LinkedIn requires 2FA / captcha      | Login times out → status: failed, screenshot saved |
| Playwright selector changes          | Update `SELECTORS` dict at top of `linkedin_poster.py` |
| Image attach fails                   | Caught at publish step, status: failed, retry safe |
| Scheduler missed run (laptop asleep) | APScheduler `coalesce=True` runs once on resume    |

## Extensibility points

- **New surface (Twitter/X, Bluesky)** — add `src/twitter_poster.py`, route by
  channel field on `Post`.
- **New AI engine** — `ContentAgent` is one class; swap `Anthropic` for
  `OpenAI`. Same `_call(system, user) -> dict` signature.
- **Multi-tenant** — add `account_id` to `Post`, scope queries, give each
  account its own `state.json`.
