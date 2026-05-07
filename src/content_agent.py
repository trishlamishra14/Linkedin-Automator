"""Claude-powered content generation for LinkedIn posts.

The agent reads a folder of context files (brand, voice, strategy, ideas) and
produces idea lists or fully-formed posts. Each call is a single Anthropic
Messages API request — no chains, no frameworks, just a clean prompt with
context injected as plain text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from anthropic import Anthropic

from .config import CONTEXT_DIR, DATA_DIR, settings


# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------

CONTEXT_FILES = ("brand.md", "voice.md", "strategy.md")
DATA_FILES = ("ideas.md",)


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_context() -> str:
    """Concatenate all context files into one string, with file-level headers."""
    parts: list[str] = []
    for name in CONTEXT_FILES:
        content = _read_if_exists(CONTEXT_DIR / name)
        if content:
            parts.append(f"=== {name} ===\n{content.strip()}")
    for name in DATA_FILES:
        content = _read_if_exists(DATA_DIR / name)
        if content:
            parts.append(f"=== data/{name} ===\n{content.strip()}")
    return "\n\n".join(parts) or "(no context files configured)"


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_IDEAS = """You are a senior LinkedIn ghostwriter for a personal brand.
Read the supplied brand, voice, strategy, and idea-bank context, then propose
fresh post ideas that fit the brand's content rotation and audience. Avoid
generic productivity advice. Each idea should have a sharp angle and a clear
reason it would stop the scroll for the target reader.

Return STRICT JSON ONLY in this shape:
{"ideas": [{"hook": "...", "angle": "...", "audience": "...", "format": "story|insight|hot-take|how-to|case-study"}]}
No prose outside the JSON."""


SYSTEM_WRITE = """You are a senior LinkedIn ghostwriter for a personal brand.
Read the supplied brand, voice, and strategy context, then write ONE LinkedIn
post in that voice on the given topic.

RULES:
- Hook: 1-2 lines, scroll-stopping. No clichés.
- Body: 5-12 short lines, one sentence per line, plenty of whitespace.
- CTA: ends with a clear next step (DM, link, or a comment-worthy question).
- Hashtags: 3-6 relevant ones on a final line.
- NEVER use em-dashes (--).
- NEVER sound like a guru or use corporate jargon.
- Specifics > generics. Real numbers, real tools, real outcomes.

Return STRICT JSON ONLY in this shape:
{"content": "<full post body without hashtags>", "hashtags": "#tag1 #tag2 #tag3"}
No prose outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class PostIdea:
    hook: str
    angle: str
    audience: str
    format: str


@dataclass
class GeneratedPost:
    content: str
    hashtags: str

    @property
    def full_text(self) -> str:
        return f"{self.content.strip()}\n\n{self.hashtags.strip()}".strip()


class ContentAgent:
    """Thin wrapper around the Anthropic Messages API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.anthropic_model

    # -- ideas -------------------------------------------------------------
    def generate_ideas(self, count: int = 5, focus: str | None = None) -> list[PostIdea]:
        focus_line = f"\nFocus area: {focus}" if focus else ""
        user = (
            f"Generate {count} LinkedIn post ideas.{focus_line}\n\n"
            f"=== context ===\n{load_context()}"
        )
        data = self._call(SYSTEM_IDEAS, user)
        return [PostIdea(**item) for item in data.get("ideas", [])][:count]

    # -- write a single post ----------------------------------------------
    def write_post(self, topic: str) -> GeneratedPost:
        user = (
            f"TOPIC: {topic}\n\n"
            f"Write the LinkedIn post now.\n\n"
            f"=== context ===\n{load_context()}"
        )
        data = self._call(SYSTEM_WRITE, user)
        return GeneratedPost(content=data["content"], hashtags=data.get("hashtags", ""))

    # -- internal ----------------------------------------------------------
    def _call(self, system: str, user: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Tolerant JSON extraction. Claude returns clean JSON 99% of the time but
    occasionally wraps it in ```json ... ``` fences."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last-resort: find first { and last }
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


# Convenience for one-off scripting
def quick_post(topic: str) -> GeneratedPost:
    return ContentAgent().write_post(topic)


def quick_ideas(count: int = 5, focus: str | None = None) -> Iterable[PostIdea]:
    return ContentAgent().generate_ideas(count=count, focus=focus)
