"""
Career Tracker — Hourly AI Job Monitoring & Email Bot

Runs every 1 hour (or on-demand):
1. Scans career pages & APIs across 200+ target companies
2. Filters for fresher / trainee / MCA graduate openings
3. Matches jobs against profile & ranks opportunities
4. Pushes notifications to the dashboard
5. Sends HTML job digest directly to palulaptop@gmail.com

Usage:
    python hourly_job_bot.py          # Single run (for Cron / GitHub Actions)
    python hourly_job_bot.py --daemon # Continuous loop running every 1 hour
"""

from __future__ import annotations

import argparse
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings import get_settings
from orchestrator.run import main as run_pipeline
from notifier.email_notifier import send_email_digest
from dedup.store import DedupStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("HourlyJobBot")


def execute_hourly_scan(target_email: str = "palulaptop@gmail.com") -> dict:
    """Execute a single hourly scan run and send email digest to recipient."""
    settings = get_settings()
    logger.info("=" * 65)
    logger.info("⏰ STARTING HOURLY JOB BOT SCAN")
    logger.info("   Target Email Address : %s", target_email)
    logger.info("   Scan Time            : %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 65)

    start_time = time.time()
    result_code = run_pipeline()

    elapsed = time.time() - start_time
    logger.info("✅ Hourly job scan completed in %.2f seconds (exit code: %d)", elapsed, result_code)

    # Fetch newly matched jobs from DB to format and verify email alert
    import sqlite3
    store = DedupStore(settings.db_path)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT job_id, company, title, location, url, match_score, match_reason, priority, is_fresher_eligible
            FROM notifications
            ORDER BY id DESC
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        matched_jobs = [dict(r) for r in rows]

    if matched_jobs:
        logger.info("📧 Sending HTML Email Digest (%d roles) to %s...", len(matched_jobs), target_email)
        email_sent = send_email_digest(matched_jobs, recipient_email=target_email)
        if email_sent:
            logger.info("🎉 Email digest successfully delivered/logged for %s!", target_email)
    else:
        logger.info("ℹ️ No new matched jobs in this cycle. Next scan in 1 hour.")

    return {
        "status": "success" if result_code == 0 else "error",
        "jobs_matched": len(matched_jobs),
        "elapsed_seconds": round(elapsed, 2),
        "email_target": target_email,
    }


def run_daemon_loop(interval_seconds: int = 3600, target_email: str = "palulaptop@gmail.com") -> None:
    """Run continuous hourly background loop."""
    logger.info("🚀 Launching Hourly Job Bot in DAEMON mode (Interval: %d seconds / 1 hour)", interval_seconds)
    try:
        while True:
            try:
                execute_hourly_scan(target_email=target_email)
            except Exception as e:
                logger.exception("❌ Error during hourly scan iteration: %s", e)

            logger.info("💤 Sleeping for %d seconds (1 hour) until next scan cycle...", interval_seconds)
            time.sleep(interval_seconds)
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Hourly Job Bot daemon stopped gracefully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Career Tracker Hourly Job Monitoring & Email Bot")
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in background every 1 hour",
    )
    parser.add_argument(
        "--email",
        type=str,
        default="palulaptop@gmail.com",
        help="Target email recipient for job alerts (default: palulaptop@gmail.com)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Daemon sleep interval in seconds (default: 3600)",
    )

    args = parser.parse_args()

    if args.daemon:
        run_daemon_loop(interval_seconds=args.interval, target_email=args.email)
    else:
        execute_hourly_scan(target_email=args.email)


if __name__ == "__main__":
    main()
