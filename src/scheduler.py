"""APScheduler wrapper:
- DateTrigger jobs: publish a single scheduled post at its fire time.
- Cron job: daily trend refresh (HN + Reddit + Google News, scored against niche).
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from . import db
from .config import settings
from .linkedin_poster import publish_sync

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
        _register_recurring_jobs(_scheduler)
    return _scheduler


def _register_recurring_jobs(sched: BackgroundScheduler) -> None:
    """Background jobs that exist for the lifetime of the server."""
    try:
        cron = settings.trend_refresh_cron.split()
        if len(cron) == 5:
            minute, hour, dom, month, dow = cron
            sched.add_job(
                _refresh_trends_job,
                trigger=CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow),
                id="trend-refresh-daily",
                replace_existing=True,
            )
    except Exception as exc:
        logger.warning("Could not schedule trend refresh: %s", exc)


def _refresh_trends_job() -> None:
    """Background job: fetch + score trends. Imports lazily to avoid circular imports."""
    try:
        from .trend_scout import refresh_trends
        inserted = refresh_trends()
        logger.info("Trend refresh inserted %s new items", inserted)
    except Exception as exc:
        logger.exception("Trend refresh failed: %s", exc)


def schedule_post(post_id: int, fire_at: datetime) -> str:
    sched = get_scheduler()
    job = sched.add_job(
        _publish_job,
        trigger=DateTrigger(run_date=fire_at),
        args=[post_id],
        id=f"post-{post_id}",
        replace_existing=True,
    )
    db.update_post(post_id, status="scheduled", scheduled_for=fire_at)
    return job.id


def cancel_post(post_id: int) -> bool:
    sched = get_scheduler()
    try:
        sched.remove_job(f"post-{post_id}")
    except Exception:
        return False
    db.update_post(post_id, status="draft", scheduled_for=None)
    return True


def _publish_job(post_id: int) -> None:
    """Background job: actually post to LinkedIn."""
    post = db.get_post(post_id)
    if not post:
        logger.warning("Post %s no longer exists", post_id)
        return

    full_text = f"{post.content.strip()}\n\n{post.hashtags.strip()}".strip()

    if settings.posting_mode == "dry_run":
        logger.info("[DRY RUN] would publish post %s", post_id)
        db.update_post(post_id, status="published", published_at=datetime.utcnow(), linkedin_url="dry-run")
        return

    result = publish_sync(full_text, image_path=post.image_path, headless=True)
    if result.success:
        db.update_post(
            post_id,
            status="published",
            published_at=datetime.utcnow(),
            linkedin_url=result.linkedin_url,
        )
    else:
        db.update_post(post_id, status="failed", error=result.error or "unknown error")
