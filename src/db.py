"""SQLite-backed persistence for profiles, trends, drafts, and post history."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import settings, ensure_dirs


class Profile(SQLModel, table=True):
    """The analyzed LinkedIn profile that drives voice + niche.

    There's typically one row per installation. The `data` field holds the full
    Claude-analyzed JSON: bio, niche, audience, tone, hook patterns, sample
    voice phrases. The flat fields are convenience copies for fast queries.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_url: str
    name: str = ""
    headline: str = ""
    niche: str = ""
    audience: str = ""
    tone: str = ""
    raw_bio: str = ""
    raw_posts: str = ""           # newline-separated scraped posts
    analysis_json: str = ""       # full structured analysis from Claude
    last_scraped_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Trend(SQLModel, table=True):
    """A trending topic surfaced from HN / Reddit / Google News."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str = ""
    summary: str = ""
    source: str                   # hackernews | reddit | google_news
    source_score: int = 0         # raw score from source (HN points, Reddit upvotes, etc.)
    relevance_score: float = 0.0  # Claude-rated 0-100 against user's niche
    angle: str = ""               # Claude-suggested angle for the post
    used: bool = Field(default=False, index=True)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class Post(SQLModel, table=True):
    """A LinkedIn post in any state of its lifecycle."""

    id: Optional[int] = Field(default=None, primary_key=True)
    topic: str
    content: str
    hashtags: str = ""
    image_path: Optional[str] = None
    image_prompt: Optional[str] = None
    trend_id: Optional[int] = Field(default=None, foreign_key="trend.id")

    # lifecycle: draft -> scheduled -> published | failed
    status: str = Field(default="draft", index=True)

    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    linkedin_url: Optional[str] = None
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        ensure_dirs()
        _engine = create_engine(settings.database_url, echo=False)
        SQLModel.metadata.create_all(_engine)
    return _engine


def session() -> Session:
    return Session(get_engine())


# ---------- helpers ----------

def create_draft(topic: str, content: str, hashtags: str = "", image_path: str | None = None) -> Post:
    with session() as s:
        post = Post(topic=topic, content=content, hashtags=hashtags, image_path=image_path)
        s.add(post)
        s.commit()
        s.refresh(post)
        return post


def list_posts(status: str | None = None, limit: int = 50) -> list[Post]:
    with session() as s:
        stmt = select(Post).order_by(Post.created_at.desc()).limit(limit)
        if status:
            stmt = select(Post).where(Post.status == status).order_by(Post.created_at.desc()).limit(limit)
        return list(s.exec(stmt))


def get_post(post_id: int) -> Post | None:
    with session() as s:
        return s.get(Post, post_id)


def update_post(post_id: int, **fields) -> Post | None:
    with session() as s:
        post = s.get(Post, post_id)
        if not post:
            return None
        for key, value in fields.items():
            setattr(post, key, value)
        post.updated_at = datetime.utcnow()
        s.add(post)
        s.commit()
        s.refresh(post)
        return post


def delete_post(post_id: int) -> bool:
    with session() as s:
        post = s.get(Post, post_id)
        if not post:
            return False
        s.delete(post)
        s.commit()
        return True


# ---------- profile helpers ----------

def upsert_profile(**fields) -> Profile:
    """Single-profile installation: create one if none exists, otherwise update."""
    with session() as s:
        existing = s.exec(select(Profile).limit(1)).first()
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing
        profile = Profile(**fields)
        s.add(profile)
        s.commit()
        s.refresh(profile)
        return profile


def get_profile() -> Profile | None:
    with session() as s:
        return s.exec(select(Profile).limit(1)).first()


# ---------- trend helpers ----------

def insert_trends(items: list[dict]) -> int:
    """Bulk-insert trends, deduping on (source, url)."""
    if not items:
        return 0
    inserted = 0
    with session() as s:
        for item in items:
            existing = s.exec(
                select(Trend).where(Trend.source == item["source"]).where(Trend.url == item.get("url", ""))
            ).first()
            if existing:
                continue
            s.add(Trend(**item))
            inserted += 1
        s.commit()
    return inserted


def list_trends(limit: int = 30, only_unused: bool = True, min_relevance: float = 0.0) -> list[Trend]:
    with session() as s:
        stmt = select(Trend).order_by(Trend.relevance_score.desc(), Trend.fetched_at.desc()).limit(limit)
        results = list(s.exec(stmt))
        if only_unused:
            results = [t for t in results if not t.used]
        if min_relevance:
            results = [t for t in results if t.relevance_score >= min_relevance]
        return results


def get_trend(trend_id: int) -> Trend | None:
    with session() as s:
        return s.get(Trend, trend_id)


def mark_trend_used(trend_id: int) -> None:
    with session() as s:
        trend = s.get(Trend, trend_id)
        if trend:
            trend.used = True
            s.add(trend)
            s.commit()


def update_trend_score(trend_id: int, relevance: float, angle: str) -> None:
    with session() as s:
        trend = s.get(Trend, trend_id)
        if trend:
            trend.relevance_score = relevance
            trend.angle = angle
            s.add(trend)
            s.commit()
