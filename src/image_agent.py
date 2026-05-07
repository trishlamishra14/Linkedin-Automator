"""Image generation via Replicate (Flux Schnell by default).

Two-step:
1. Claude turns the post content into a tight, brand-on image prompt.
2. Replicate generates the image; we download it locally and return the path.

Requires REPLICATE_API_TOKEN in .env.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from . import db
from .config import DATA_DIR, settings
from .content_agent import _parse_json


IMAGES_DIR = DATA_DIR / "images"
DEFAULT_MODEL = "black-forest-labs/flux-schnell"

REPLICATE_API = "https://api.replicate.com/v1"


SYSTEM_IMAGE_PROMPT = """You craft a tight image prompt for a LinkedIn post.

Rules:
- The image must be a clean, modern, slightly editorial illustration or photo.
- No text in the image. No words, no logos, no UI mockups with text.
- One clear subject. Confident composition. Good negative space for an overlay.
- Match the brand voice: confident, modern, approachable.
- Output one prompt, 1-2 sentences max, ready to feed to a text-to-image model.

Return STRICT JSON: {"prompt": "...", "negative": "text, words, watermark, logo, ui, screenshot, cluttered"}"""


def craft_prompt(post_content: str, niche: str = "") -> dict:
    """Ask Claude for a Flux-friendly prompt + negative."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    user = f"NICHE: {niche}\n\nPOST:\n{post_content}\n\nWrite the image prompt."
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=400,
        system=SYSTEM_IMAGE_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Replicate API
# ---------------------------------------------------------------------------

def _replicate_request(method: str, path: str, body: dict | None = None) -> dict:
    token = os.getenv("REPLICATE_API_TOKEN") or settings.replicate_api_token
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not configured in .env")

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        REPLICATE_API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def run_replicate(prompt: str, model: str = DEFAULT_MODEL, aspect_ratio: str = "1:1") -> str:
    """Submit a prediction and poll until it completes. Returns the first image URL."""
    body = {
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "png",
            "num_outputs": 1,
        }
    }
    # The "models/<owner>/<name>/predictions" endpoint kicks off a run on the
    # latest official version of a model — no version-pin lookup required.
    result = _replicate_request("POST", f"/models/{model}/predictions", body)

    # With Prefer: wait the response is usually already terminal, but poll just
    # in case (max 60s).
    for _ in range(30):
        status = result.get("status")
        if status == "succeeded":
            output = result.get("output")
            if isinstance(output, list) and output:
                return output[0]
            if isinstance(output, str):
                return output
            raise RuntimeError(f"Unexpected output shape: {output}")
        if status in {"failed", "canceled"}:
            raise RuntimeError(f"Replicate run {status}: {result.get('error')}")
        time.sleep(2)
        result = _replicate_request("GET", f"/predictions/{result['id']}")

    raise RuntimeError("Replicate run timed out")


def download(url: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as resp, open(out_path, "wb") as f:
        f.write(resp.read())
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_image_for_post(post_id: int) -> str:
    """End-to-end: post -> prompt -> Replicate -> local file -> updated DB row.
    Returns the saved file path."""
    post = db.get_post(post_id)
    if not post:
        raise ValueError(f"Post {post_id} not found")

    profile = db.get_profile()
    niche = profile.niche if profile else ""

    crafted = craft_prompt(post.content, niche=niche)
    prompt = crafted.get("prompt", "")
    if not prompt:
        raise RuntimeError("Claude returned an empty image prompt")

    image_url = run_replicate(prompt)
    out_path = IMAGES_DIR / f"post-{post_id}-{datetime.utcnow():%Y%m%dT%H%M%SZ}.png"
    saved = download(image_url, out_path)

    db.update_post(post_id, image_path=str(saved), image_prompt=prompt)
    return str(saved)
