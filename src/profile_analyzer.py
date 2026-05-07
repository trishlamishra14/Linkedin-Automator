"""LinkedIn profile analyzer.

Two-stage pipeline:
1. Playwright opens the profile URL (reusing state.json if available) and
   scrapes the headline/about + the first ~10 visible posts.
2. Claude reads the scraped text and returns structured JSON describing the
   author's niche, audience, tone, hook patterns, and CTA style.

The analysis result is persisted to the DB and also written to
`context/voice.md` + `context/brand.md` so the existing content_agent picks
it up automatically.

LinkedIn aggressively defends against scraping. First-run guidance:
- Set headless=False the first time you analyze a profile.
- Solve any verification challenge manually.
- After success, state.json keeps you signed in for subsequent runs.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from playwright.async_api import async_playwright

from . import db
from .config import CONTEXT_DIR, ROOT, settings
from .content_agent import _parse_json


STATE_FILE = ROOT / "state.json"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_ANALYZE = """You are a brand-voice analyst studying a LinkedIn profile.
Read the supplied bio, headline, and recent posts, then extract a tight, usable
brand profile that another AI will use to write posts in this voice.

Be concrete. Quote actual phrases the author uses. Identify their niche
narrowly (not "tech" — "AI agents for SaaS founders").

Return STRICT JSON ONLY in this shape:
{
  "name": "...",
  "headline": "...",
  "niche": "<narrow niche, 3-7 words>",
  "audience": "<who they write for, 3-7 words>",
  "tone": "<2-3 sentence description of voice>",
  "hook_patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "signature_phrases": ["phrase they actually use", "..."],
  "cta_style": "<how they end posts>",
  "topics": ["topic 1", "topic 2", "topic 3", "topic 4", "topic 5"],
  "do": ["concrete rule 1", "concrete rule 2", "concrete rule 3"],
  "dont": ["concrete rule 1", "concrete rule 2", "concrete rule 3"]
}
No prose outside the JSON."""


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

@dataclass
class ScrapedProfile:
    url: str
    name: str
    headline: str
    about: str
    posts: list[str]

    def to_text(self) -> str:
        posts_text = "\n\n---\n\n".join(self.posts) if self.posts else "(no posts captured)"
        return (
            f"NAME: {self.name}\n"
            f"HEADLINE: {self.headline}\n\n"
            f"ABOUT:\n{self.about or '(empty)'}\n\n"
            f"RECENT POSTS:\n{posts_text}"
        )


async def scrape_profile(url: str, headless: bool = True, max_posts: int = 12) -> ScrapedProfile:
    """Open the LinkedIn profile and scrape headline, about, and recent posts."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        ctx_kwargs = {"viewport": {"width": 1280, "height": 900}}
        if STATE_FILE.exists():
            ctx_kwargs["storage_state"] = str(STATE_FILE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()

        try:
            await page.goto(url, timeout=60_000, wait_until="domcontentloaded")

            # Trigger login flow if redirected
            if "/login" in page.url or "/checkpoint" in page.url:
                if not settings.linkedin_email:
                    raise RuntimeError(
                        "LinkedIn requires login but LINKEDIN_EMAIL is not set in .env"
                    )
                await page.goto("https://www.linkedin.com/login", timeout=60_000)
                await page.fill("input#username", settings.linkedin_email)
                await page.fill("input#password", settings.linkedin_password)
                await page.click("button[type=submit]")
                await page.wait_for_url("**/feed/**", timeout=60_000)
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")

            # Persist session for next time
            await ctx.storage_state(path=str(STATE_FILE))

            # ---- name + headline ----
            name = await _safe_text(page, "h1") or ""
            headline = await _safe_text(page, "div.text-body-medium.break-words") or ""

            # ---- about ----
            about = ""
            about_section = page.locator("section:has-text('About')").first
            if await about_section.count():
                about = (await about_section.inner_text()).replace("About", "", 1).strip()

            # ---- recent posts ----
            # LinkedIn renders activity at /<profile>/recent-activity/all/
            posts: list[str] = []
            activity_url = url.rstrip("/") + "/recent-activity/all/"
            await page.goto(activity_url, timeout=60_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            await _autoscroll(page, scrolls=4)

            post_locator = page.locator(
                "div.feed-shared-update-v2__description, div.update-components-text"
            )
            count = min(await post_locator.count(), max_posts)
            for i in range(count):
                try:
                    text = (await post_locator.nth(i).inner_text()).strip()
                    if text and len(text) > 60:
                        posts.append(text)
                except Exception:
                    continue

            return ScrapedProfile(
                url=url,
                name=name.strip(),
                headline=headline.strip(),
                about=about,
                posts=posts,
            )
        finally:
            await ctx.close()
            await browser.close()


async def _safe_text(page, selector: str) -> str:
    loc = page.locator(selector).first
    if await loc.count():
        try:
            return (await loc.inner_text()).strip()
        except Exception:
            return ""
    return ""


async def _autoscroll(page, scrolls: int = 4) -> None:
    for _ in range(scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(900)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_with_claude(scraped: ScrapedProfile) -> dict:
    """Call Claude with the scraped text and return the structured profile dict."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=SYSTEM_ANALYZE,
        messages=[{"role": "user", "content": scraped.to_text()}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_context_files(analysis: dict) -> None:
    """Render the structured analysis into `context/brand.md` and `context/voice.md`
    so the existing content agent picks it up on the next call."""
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    brand_md = (
        f"# Brand — {analysis.get('name', '')}\n\n"
        f"## One-liner\n{analysis.get('headline', '')}\n\n"
        f"## Niche\n{analysis.get('niche', '')}\n\n"
        f"## Audience\n{analysis.get('audience', '')}\n\n"
        f"## Topics I write about\n"
        + "\n".join(f"- {t}" for t in analysis.get("topics", []))
        + "\n"
    )

    voice_md = (
        f"# Voice — {analysis.get('name', '')}\n\n"
        f"## Tone\n{analysis.get('tone', '')}\n\n"
        f"## Hook patterns that work\n"
        + "\n".join(f"- {p}" for p in analysis.get("hook_patterns", []))
        + "\n\n"
        f"## Signature phrases\n"
        + "\n".join(f"- \"{p}\"" for p in analysis.get("signature_phrases", []))
        + "\n\n"
        f"## CTA style\n{analysis.get('cta_style', '')}\n\n"
        f"## Do\n"
        + "\n".join(f"- {d}" for d in analysis.get("do", []))
        + "\n\n"
        f"## Don't\n"
        + "\n".join(f"- {d}" for d in analysis.get("dont", []))
        + "\n"
    )

    (CONTEXT_DIR / "brand.md").write_text(brand_md, encoding="utf-8")
    (CONTEXT_DIR / "voice.md").write_text(voice_md, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_profile_sync(url: str, headless: bool = True) -> dict:
    """Sync entry point: scrape → analyze → persist. Returns the analysis dict."""
    scraped: ScrapedProfile = asyncio.run(scrape_profile(url, headless=headless))
    analysis = analyze_with_claude(scraped)
    write_context_files(analysis)

    db.upsert_profile(
        profile_url=url,
        name=analysis.get("name", ""),
        headline=analysis.get("headline", ""),
        niche=analysis.get("niche", ""),
        audience=analysis.get("audience", ""),
        tone=analysis.get("tone", ""),
        raw_bio=scraped.about,
        raw_posts="\n\n---\n\n".join(scraped.posts),
        analysis_json=json.dumps(analysis, ensure_ascii=False),
        last_scraped_at=datetime.utcnow(),
    )
    return analysis
