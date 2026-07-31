"""
Career Tracker — Non-Blocking Background Scheduler Service

Launches background interval workers that run:
1. Career Page Scraping & Email Alerts (Every 4 hours)
2. API Sources Scanner (Every 2 hours)
"""

from __future__ import annotations

import logging
import threading
import time

from config.settings import get_settings

logger = logging.getLogger(__name__)

_background_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _background_worker(interval_hours: int = 4) -> None:
    """Worker loop that periodically runs the pipeline in the background."""
    logger.info("Background scheduler thread started (scanning every %d hours).", interval_hours)
    interval_seconds = interval_hours * 3600

    while not _stop_event.is_set():
        # Sleep in small increments to allow responsive shutdown
        for _ in range(interval_seconds):
            if _stop_event.is_set():
                return
            time.sleep(1)

        try:
            logger.info("⏰ Background scheduler triggering pipeline scan & email alerts...")
            from orchestrator.run import main as run_main
            run_main()
        except Exception as e:
            logger.warning("Background scheduler run failed: %s", e)


def start_background_scheduler(interval_hours: int = 4) -> None:
    """Start background scheduler thread if not already running."""
    global _background_thread
    if _background_thread and _background_thread.is_alive():
        logger.debug("Background scheduler already running.")
        return

    _stop_event.clear()
    _background_thread = threading.Thread(
        target=_background_worker,
        args=(interval_hours,),
        daemon=True,
        name="CareerTrackerBackgroundScheduler",
    )
    _background_thread.start()
    logger.info("✅ Background scheduler service initialized.")


def stop_background_scheduler() -> None:
    """Stop background scheduler thread."""
    _stop_event.set()
    logger.info("Background scheduler requested to stop.")
