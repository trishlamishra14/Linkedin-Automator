"""FastAPI server that powers the dashboard."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, scheduler
from .config import DATA_DIR, WEB_DIR, settings, ensure_dirs
from .content_agent import ContentAgent


app = FastAPI(title="LinkedIn Post Automator", version="0.1.0")
ensure_dirs()
db.get_engine()  # ensure tables


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IdeaRequest(BaseModel):
    count: int = 5
    focus: Optional[str] = None


class WriteRequest(BaseModel):
    topic: str
    polish: bool = False  # if true, treat `topic` as the user's draft to polish in voice


class ProfileRequest(BaseModel):
    url: str
    headless: bool = True


class TrendPostRequest(BaseModel):
    trend_id: int


class ScheduleRequest(BaseModel):
    fire_at: datetime


class PostUpdate(BaseModel):
    content: Optional[str] = None
    hashtags: Optional[str] = None
    image_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "mode": settings.posting_mode}


@app.post("/api/ideas")
def gen_ideas(req: IdeaRequest) -> dict:
    agent = ContentAgent()
    ideas = agent.generate_ideas(count=req.count, focus=req.focus)
    return {"ideas": [idea.__dict__ for idea in ideas]}


@app.post("/api/posts/write")
def write(req: WriteRequest) -> dict:
    agent = ContentAgent()
    if req.polish:
        topic = (
            "Polish the following draft into the brand voice. Keep the core idea "
            "and key facts intact, but rewrite hook, structure, and CTA to match.\n\n"
            f"DRAFT:\n{req.topic}"
        )
        title = req.topic[:60] + ("…" if len(req.topic) > 60 else "")
    else:
        topic = req.topic
        title = req.topic
    generated = agent.write_post(topic)
    post = db.create_draft(
        topic=title,
        content=generated.content,
        hashtags=generated.hashtags,
    )
    return {"post": post.model_dump()}


@app.get("/api/posts")
def list_posts(status: Optional[str] = None) -> dict:
    posts = db.list_posts(status=status)
    return {"posts": [p.model_dump() for p in posts]}


@app.get("/api/posts/{post_id}")
def get_post(post_id: int) -> dict:
    post = db.get_post(post_id)
    if not post:
        raise HTTPException(404, "post not found")
    return {"post": post.model_dump()}


@app.patch("/api/posts/{post_id}")
def patch_post(post_id: int, payload: PostUpdate) -> dict:
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    post = db.update_post(post_id, **fields)
    if not post:
        raise HTTPException(404, "post not found")
    return {"post": post.model_dump()}


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int) -> dict:
    if not db.delete_post(post_id):
        raise HTTPException(404, "post not found")
    return {"ok": True}


@app.post("/api/posts/{post_id}/schedule")
def schedule(post_id: int, req: ScheduleRequest) -> dict:
    if not db.get_post(post_id):
        raise HTTPException(404, "post not found")
    job_id = scheduler.schedule_post(post_id, req.fire_at)
    return {"ok": True, "job_id": job_id}


@app.post("/api/posts/{post_id}/cancel")
def cancel(post_id: int) -> dict:
    if not scheduler.cancel_post(post_id):
        raise HTTPException(400, "no schedule to cancel")
    return {"ok": True}


@app.post("/api/posts/{post_id}/publish-now")
def publish_now(post_id: int) -> dict:
    """Publish immediately by scheduling for the next second."""
    if not db.get_post(post_id):
        raise HTTPException(404, "post not found")
    fire_at = datetime.utcnow().replace(microsecond=0)
    scheduler.schedule_post(post_id, fire_at)
    return {"ok": True, "scheduled_for": fire_at.isoformat()}


# ---------------------------------------------------------------------------
# Profile analysis
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def get_profile() -> dict:
    profile = db.get_profile()
    if not profile:
        return {"profile": None}
    payload = profile.model_dump()
    try:
        payload["analysis"] = json.loads(profile.analysis_json) if profile.analysis_json else None
    except json.JSONDecodeError:
        payload["analysis"] = None
    return {"profile": payload}


@app.post("/api/profile/analyze")
def analyze_profile(req: ProfileRequest) -> dict:
    """Synchronous: scrape -> Claude analysis -> persist. Can take 30-60 seconds."""
    from .profile_analyzer import analyze_profile_sync
    try:
        analysis = analyze_profile_sync(req.url, headless=req.headless)
    except Exception as exc:
        raise HTTPException(500, f"profile analysis failed: {exc}") from exc
    return {"ok": True, "analysis": analysis}


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

@app.get("/api/trends")
def get_trends(only_unused: bool = True, min_relevance: float = 0.0, limit: int = 30) -> dict:
    trends = db.list_trends(limit=limit, only_unused=only_unused, min_relevance=min_relevance)
    return {"trends": [t.model_dump() for t in trends]}


@app.post("/api/trends/refresh")
def refresh_trends_now(background: BackgroundTasks) -> dict:
    """Kick a background refresh — returns immediately."""
    from .trend_scout import refresh_trends
    background.add_task(refresh_trends)
    return {"ok": True, "queued": True}


@app.post("/api/posts/from-trend")
def post_from_trend(req: TrendPostRequest) -> dict:
    """Generate a draft post seeded with a chosen trend's title + angle."""
    trend = db.get_trend(req.trend_id)
    if not trend:
        raise HTTPException(404, "trend not found")

    topic = (
        f"Trend: {trend.title}\n"
        f"Source: {trend.source}\n"
        f"Suggested angle: {trend.angle or '(none)'}\n"
        f"URL: {trend.url}"
    )
    agent = ContentAgent()
    generated = agent.write_post(topic)
    post = db.create_draft(
        topic=trend.title,
        content=generated.content,
        hashtags=generated.hashtags,
    )
    db.update_post(post.id, trend_id=trend.id)
    db.mark_trend_used(trend.id)
    return {"post": post.model_dump()}


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

@app.post("/api/posts/{post_id}/generate-image")
def generate_image(post_id: int) -> dict:
    if not db.get_post(post_id):
        raise HTTPException(404, "post not found")
    from .image_agent import generate_image_for_post
    try:
        path = generate_image_for_post(post_id)
    except Exception as exc:
        raise HTTPException(500, f"image generation failed: {exc}") from exc
    return {"ok": True, "image_path": path}


@app.get("/api/images/{filename}")
def serve_image(filename: str) -> FileResponse:
    """Serve generated images back to the dashboard."""
    path = DATA_DIR / "images" / filename
    if not path.exists() or ".." in filename:
        raise HTTPException(404, "image not found")
    return FileResponse(path)


# ---------------------------------------------------------------------------
# Static dashboard
# ---------------------------------------------------------------------------

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
