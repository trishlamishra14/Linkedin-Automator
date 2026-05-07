"""Trend scout — pulls trending items from HackerNews, Reddit, and Google News
and ranks them against the user's analyzed niche.

All three sources are free. Reddit needs a registered OAuth app (free) to read
public listings without rate-limit pain; HN is fully open; Google News is
RSS-based.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from anthropic import Anthropic

from . import db
from .config import settings
from .content_agent import _parse_json


USER_AGENT = "linkedin-automator/0.2 (+https://trishla.dev)"


# ---------------------------------------------------------------------------
# Source: HackerNews
# ---------------------------------------------------------------------------

def fetch_hackernews(limit: int = 30) -> list[dict]:
    """Top stories from the HN Firebase API. No key required."""
    url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    ids = _get_json(url)[:limit]
    items: list[dict] = []
    for item_id in ids:
        try:
            data = _get_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if not data or data.get("type") != "story":
                continue
            items.append({
                "title": data.get("title", "").strip(),
                "url": data.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
                "summary": "",
                "source": "hackernews",
                "source_score": int(data.get("score", 0)),
            })
        except Exception:
            continue
    return items


# ---------------------------------------------------------------------------
# Source: Reddit
# ---------------------------------------------------------------------------

def fetch_reddit(subreddits: list[str], limit_per: int = 10) -> list[dict]:
    """Hot posts from a list of subreddits via Reddit's public JSON endpoint.

    Doesn't require auth for read-only listings, but supplying the OAuth keys
    in .env (REDDIT_CLIENT_ID/SECRET) avoids the 60-req/hour anonymous cap.
    """
    items: list[dict] = []
    headers = {"User-Agent": USER_AGENT}

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit_per}"
            data = _get_json(url, headers=headers)
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                if d.get("stickied") or d.get("over_18"):
                    continue
                items.append({
                    "title": d.get("title", "").strip(),
                    "url": "https://reddit.com" + d.get("permalink", ""),
                    "summary": (d.get("selftext", "") or "")[:400],
                    "source": "reddit",
                    "source_score": int(d.get("ups", 0)),
                })
        except Exception:
            continue
    return items


# ---------------------------------------------------------------------------
# Source: Google News RSS
# ---------------------------------------------------------------------------

def fetch_google_news(queries: list[str], limit_per: int = 8) -> list[dict]:
    """Google News RSS search per query keyword. No key, no signup."""
    items: list[dict] = []
    for query in queries:
        try:
            q = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
            data = _get(url, headers={"User-Agent": USER_AGENT})
            root = ET.fromstring(data)
            channel = root.find("channel")
            if channel is None:
                continue
            for entry in channel.findall("item")[:limit_per]:
                title = (entry.findtext("title") or "").strip()
                link = (entry.findtext("link") or "").strip()
                desc = (entry.findtext("description") or "").strip()
                if not title:
                    continue
                items.append({
                    "title": title,
                    "url": link,
                    "summary": _strip_tags(desc)[:400],
                    "source": "google_news",
                    "source_score": 0,
                })
        except Exception:
            continue
    return items


# ---------------------------------------------------------------------------
# Ranking via Claude
# ---------------------------------------------------------------------------

SYSTEM_RANK = """You score trending news items by relevance to a content
creator's niche. For each item return a relevance score 0-100 and a short
suggested angle they could take when posting about it.

Return STRICT JSON ONLY:
{"items":[{"index": 0, "relevance": 0-100, "angle": "..."}]}"""


def rank_against_niche(items: list[dict], niche: str, audience: str, topics: list[str]) -> list[dict]:
    """Ask Claude to score each item; merges scores back into the items in place."""
    if not items:
        return items

    listing = "\n".join(
        f"{i}. [{item['source']}] {item['title']} -- {item.get('summary','')[:160]}"
        for i, item in enumerate(items)
    )
    user = (
        f"NICHE: {niche}\n"
        f"AUDIENCE: {audience}\n"
        f"TOPICS THE CREATOR WRITES ABOUT: {', '.join(topics)}\n\n"
        f"ITEMS:\n{listing}"
    )

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=3000,
        system=SYSTEM_RANK,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    parsed = _parse_json(text)
    by_idx = {entry["index"]: entry for entry in parsed.get("items", [])}
    for i, item in enumerate(items):
        score = by_idx.get(i, {})
        item["relevance_score"] = float(score.get("relevance", 0))
        item["angle"] = score.get("angle", "")
    items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return items


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------

DEFAULT_SUBREDDITS = ["startups", "SaaS", "MachineLearning", "Entrepreneur", "AskStartups"]


def derive_keywords(niche: str, topics: list[str]) -> list[str]:
    """Pick a few short search queries for Google News from niche + topics."""
    keywords = []
    if niche:
        keywords.append(niche)
    keywords.extend(topics[:3])
    return [k for k in keywords if k][:5]


def refresh_trends(top_k: int = 25) -> int:
    """Fetch from all sources, score, and persist. Returns the number inserted."""
    profile = db.get_profile()
    if not profile:
        return 0

    try:
        analysis = json.loads(profile.analysis_json) if profile.analysis_json else {}
    except json.JSONDecodeError:
        analysis = {}

    topics = analysis.get("topics", [])
    keywords = derive_keywords(profile.niche, topics)

    raw: list[dict] = []
    raw.extend(fetch_hackernews(limit=20))
    raw.extend(fetch_reddit(DEFAULT_SUBREDDITS, limit_per=8))
    if keywords:
        raw.extend(fetch_google_news(keywords, limit_per=6))

    if not raw:
        return 0

    scored = rank_against_niche(raw, profile.niche, profile.audience, topics)
    top = scored[:top_k]

    return db.insert_trends([{
        "title": t["title"],
        "url": t.get("url", ""),
        "summary": t.get("summary", ""),
        "source": t["source"],
        "source_score": t.get("source_score", 0),
        "relevance_score": t.get("relevance_score", 0.0),
        "angle": t.get("angle", ""),
        "fetched_at": datetime.utcnow(),
    } for t in top])


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, headers: dict | None = None, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url: str, headers: dict | None = None) -> Any:
    return json.loads(_get(url, headers=headers).decode("utf-8"))


def _strip_tags(s: str) -> str:
    """Crude HTML strip — Google News descriptions are simple HTML."""
    out = []
    in_tag = False
    for ch in s:
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            out.append(ch)
    return "".join(out).strip()
