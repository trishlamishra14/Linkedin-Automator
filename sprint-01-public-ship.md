# Sprint 01 — Brand refresh + public ship readiness

> **Goal:** convert LinkedIn Automator from "in build" to "shipped, open-source on GitHub" with a polished dark sky-blue dashboard that matches [`preview.html`](./preview.html).
>
> **Why:** the portfolio currently has only one truly-shipped project (BriefForge). LinkedIn Automator's code is 90% done; the missing piece is making it visible. Public ship is a one-weekend conversion that turns vision into proof.
>
> **Window:** one focused work session (this one) + a 30-min push-to-GitHub step Trishla does after.
>
> **Anti-goal:** we are NOT building new views, the engagement agent, A/B variants, or analytics in this sprint. Those are Sprint 3-5. Scope creep here delays the public ship.

---

## Definition of done

This sprint is done when **all** of these are true:

- [ ] `web/styles.css` uses the dark sky-blue token system from `preview.html` (no purple anywhere).
- [ ] `web/index.html` shows a sidebar nav with the LinkedIn Automator logo + wordmark. The `trish.exe` branding is gone.
- [ ] All four nav items (Dashboard, Compose, Trends, Setup) work and the existing backend wiring (Compose/Trends/Setup) still functions.
- [ ] A Dashboard view exists and renders even without a backend stats endpoint (uses placeholder cards that match the preview's layout).
- [ ] `LICENSE` file exists at the repo root (MIT).
- [ ] `README.md` opens cleanly on GitHub (image links, code blocks, sections all render).
- [ ] No syntax errors in any Python file, dashboard JS, or HTML.

Once shipped, the portfolio card in `trishla-portfolio/src/data/projects.ts` gets a `liveUrl` pointing to the GitHub repo.

---

## Tasks (in order)

### 1. CSS theme port
File: `web/styles.css`
- Replace the entire token system (`:root`) with the dark sky-blue palette from `preview.html`.
- Update component classes (panel, btn, chip, draft, history, trends) to use the new tokens.
- Remove all references to `--accent: #a855f7`, `--pink: #ec4899` and any purple/pink gradients.
- Keep the existing class names so `app.js` doesn't need to change much.

### 2. HTML structure refresh
File: `web/index.html`
- Replace the top tab bar with a sidebar (matching `preview.html`).
- Add the brand block: 3-node SVG logo + "LinkedIn Automator" wordmark + small "Vision · v0.2" sub-line.
- Add a profile chip below the brand (avatar + name + niche).
- Keep three existing nav items: Compose, Trends, Setup. Add a fourth: Dashboard (default landing).
- Keep the status indicator (move to sidebar footer).
- Add a `view-dashboard` section with stat cards + activity feed (placeholder data — backend stats endpoint comes in Sprint 5).

### 3. JS adaptation
File: `web/app.js`
- Update the tab-switching logic to handle sidebar nav (selector change from `.tab` to `.nav-item[data-tab]`).
- Default landing view: Dashboard.
- All existing handlers (write, schedule, publish, profile analyze, trend refresh, etc.) keep working unchanged.
- Add keyboard shortcuts (D, C, T, S) matching the preview.

### 4. Repo files for GitHub
- Create `LICENSE` at root with MIT text.
- Verify `README.md` renders correctly (no broken markdown, code blocks intact, section anchors).
- Verify `.gitignore` covers `state.json`, `data/posts.db`, `.env`, `__pycache__/`, `node_modules/`, etc.

### 5. Verification pass
- Python AST parse on every `src/*.py` file.
- Node syntax check on `web/app.js`.
- Spot-check the dashboard renders by reviewing the file structure.

---

## Stretch (only if all above is done)

- Add a tiny SVG favicon matching the logo.
- Add a `screenshots/` folder with the rendered `preview.html` saved as PNG (for the GitHub README hero).
- Update the portfolio's `projects.ts` `liveUrl` to point at the (planned) GitHub repo.

---

## Out of scope (do NOT touch this sprint)

- Inbox, Analytics, or Schedule views (Sprint 4-5).
- A/B variants in content_agent (Sprint 3).
- Voice-tuning sliders in Setup (Sprint 3).
- Command palette, notifications dropdown, toasts (Sprint 5+).
- Engagement-back agent backend (Sprint 4).
- Mobile responsive pass (later).
- Tests / evals (Sprint 6).
- Vercel / Railway deploy config (Sprint 2).

---

## Risks

**LinkedIn DOM may have changed since v0.2.** The Playwright selectors in `linkedin_poster.py` aren't part of this sprint, but flagging here so we test in Sprint 2 before declaring "shipped" too loudly.

**App.js regression.** The CSS token rename + sidebar restructure could break event listeners if class names move. Mitigation: keep `data-tab` attribute as the JS hook, not class names.

**Cache busting.** If you've previously loaded the dashboard in a browser, hard-refresh after the CSS swap or you'll see the old purple theme.

---

## Handoff to Sprint 2

When this sprint closes, update `progress.md` Done log with the date and key changes, and create `sprint-02-dogfood.md` with these tasks:
1. Configure `.env` with real ANTHROPIC_API_KEY, LINKEDIN_*, REPLICATE_API_TOKEN.
2. Run `analyze_profile` on Trishla's real LinkedIn URL.
3. Generate 5 posts across 5 days, post manually first, then via the automator.
4. Track engagement (reactions, comments, reshares) for each.
5. Replace the placeholder metrics in CASE_STUDY.md with real numbers.
6. Take production screenshots and embed in README + portfolio.
