"""Playwright browser automation for posting to LinkedIn.

Uses a persistent browser-storage state so you only sign in once. After the
first successful login, `state.json` is saved at the project root and reused.

Selectors target the standard LinkedIn web UI as of 2026-Q2. If LinkedIn
changes them, update SELECTORS.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.async_api import Browser, Playwright, async_playwright

from .config import ROOT, settings


STATE_FILE = ROOT / "state.json"
SCREENSHOT_DIR = ROOT / "data" / "screenshots"

SELECTORS = {
    "login_email": "input#username",
    "login_password": "input#password",
    "login_submit": "button[type=submit]",
    "start_post_button": "button:has-text('Start a post')",
    "post_textarea": "div.ql-editor[role='textbox']",
    "add_image_button": "button[aria-label*='photo' i]",
    "image_done_button": "button:has-text('Done')",
    "post_submit_button": "button.share-actions__primary-action",
}


@dataclass
class PostResult:
    success: bool
    linkedin_url: str | None = None
    screenshot: str | None = None
    error: str | None = None


class LinkedInPoster:
    """Async Playwright worker that publishes a single post."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None

    # ------------------------------------------------------------------
    # context managers
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "LinkedInPoster":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # ------------------------------------------------------------------
    # public api
    # ------------------------------------------------------------------
    async def publish(self, content: str, image_path: str | None = None) -> PostResult:
        """Publish `content` (and optional image) to LinkedIn. Returns a
        PostResult with success/error and a screenshot path on success."""
        assert self._browser, "use 'async with LinkedInPoster()'"
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        context_kwargs = {"viewport": {"width": 1280, "height": 900}}
        if STATE_FILE.exists():
            context_kwargs["storage_state"] = str(STATE_FILE)

        ctx = await self._browser.new_context(**context_kwargs)
        page = await ctx.new_page()

        try:
            await page.goto("https://www.linkedin.com/feed/", timeout=60_000)

            if "/login" in page.url or "/checkpoint" in page.url:
                await self._login(page)

            # Open composer
            await page.wait_for_selector(SELECTORS["start_post_button"], timeout=30_000)
            await page.click(SELECTORS["start_post_button"])

            # Type content
            await page.wait_for_selector(SELECTORS["post_textarea"], timeout=15_000)
            await page.click(SELECTORS["post_textarea"])
            await page.keyboard.type(content, delay=8)

            # Optional image
            if image_path and Path(image_path).exists():
                await page.click(SELECTORS["add_image_button"])
                async with page.expect_file_chooser() as fc_info:
                    await page.locator("input[type=file]").first.set_input_files(image_path)
                _ = await fc_info.value
                await page.click(SELECTORS["image_done_button"])

            # Publish
            await page.click(SELECTORS["post_submit_button"])
            await page.wait_for_load_state("networkidle", timeout=30_000)

            # Persist storage state so future runs skip login
            await ctx.storage_state(path=str(STATE_FILE))

            shot = SCREENSHOT_DIR / f"post-{datetime.utcnow():%Y%m%dT%H%M%SZ}.png"
            await page.screenshot(path=str(shot), full_page=False)

            return PostResult(success=True, screenshot=str(shot), linkedin_url=page.url)

        except Exception as exc:  # pragma: no cover - browser-driven
            shot = SCREENSHOT_DIR / f"error-{datetime.utcnow():%Y%m%dT%H%M%SZ}.png"
            try:
                await page.screenshot(path=str(shot), full_page=True)
            except Exception:
                shot = None
            return PostResult(success=False, error=str(exc), screenshot=str(shot) if shot else None)
        finally:
            await ctx.close()

    # ------------------------------------------------------------------
    async def _login(self, page) -> None:
        if not settings.linkedin_email or not settings.linkedin_password:
            raise RuntimeError("LINKEDIN_EMAIL / LINKEDIN_PASSWORD not configured in .env")
        await page.goto("https://www.linkedin.com/login", timeout=60_000)
        await page.fill(SELECTORS["login_email"], settings.linkedin_email)
        await page.fill(SELECTORS["login_password"], settings.linkedin_password)
        await page.click(SELECTORS["login_submit"])
        await page.wait_for_url("**/feed/**", timeout=60_000)


# ----------------------------------------------------------------------
# Sync convenience
# ----------------------------------------------------------------------

def publish_sync(content: str, image_path: str | None = None, headless: bool = True) -> PostResult:
    """Blocking helper for use from non-async code (e.g. APScheduler jobs)."""
    async def _run() -> PostResult:
        async with LinkedInPoster(headless=headless) as poster:
            return await poster.publish(content, image_path)

    return asyncio.run(_run())
