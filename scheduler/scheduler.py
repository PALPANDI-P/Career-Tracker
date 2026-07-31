"""Career Tracker — Scheduler.

Staggered scheduling for multiple pipeline types:
- Career page scraping: every 6 hours (heavier)
- API sources: every 2 hours (lighter, faster)
- Notification cleanup: daily at 2 AM
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _run_main_pipeline() -> None:
    """Run the main career page scraping pipeline."""
    from orchestrator.run import main
    try:
        main()
    except Exception as e:
        logger.exception("Main pipeline failed: %s", e)


def _run_api_pipeline() -> None:
    """Run the API sources pipeline."""
    try:
        from orchestrator.api_pipeline import run_api_pipeline
        run_api_pipeline()
    except Exception as e:
        logger.exception("API pipeline failed: %s", e)


def _cleanup_old_notifications() -> None:
    """Remove notifications older than 30 days."""
    import sqlite3
    from datetime import datetime, timedelta, timezone
    from config.settings import get_settings

    settings = get_settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        with sqlite3.connect(settings.db_path) as conn:
            deleted = conn.execute(
                "DELETE FROM notifications WHERE created_at < ?", (cutoff,)
            ).rowcount
            conn.commit()
        if deleted:
            logger.info("Cleaned up %d old notifications", deleted)
    except sqlite3.OperationalError:
        pass


def start_scheduler() -> None:
    """Start the staggered job scheduler."""
    settings = get_settings()
    scheduler = BlockingScheduler()

    # Career page scraping: every N hours (default 6)
    scheduler.add_job(
        _run_main_pipeline,
        'interval',
        hours=settings.schedule_interval_hours,
        id='career_tracker_main_pipeline',
        name='Main Career Page Pipeline',
    )

    # API sources: every 2 hours (lighter, faster)
    scheduler.add_job(
        _run_api_pipeline,
        'interval',
        hours=2,
        id='career_tracker_api_pipeline',
        name='API Sources Pipeline',
    )

    # Notification cleanup: daily at 2 AM
    scheduler.add_job(
        _cleanup_old_notifications,
        'cron',
        hour=2,
        id='career_tracker_cleanup',
        name='Notification Cleanup',
    )

    logger.info(
        "Scheduler started: main pipeline every %dh, API pipeline every 2h, cleanup daily at 2 AM",
        settings.schedule_interval_hours,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
