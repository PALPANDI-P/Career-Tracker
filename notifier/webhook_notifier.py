"""
Career Tracker — Webhook Notifier (Discord / Slack)

Dispatches job match notifications to configured Webhook URLs
(Discord, Slack, or generic HTTP Webhook endpoints).
"""

from __future__ import annotations

import logging

import requests

from schema.job import ScoredJob

logger = logging.getLogger(__name__)


def send_webhook_alert(scored_job: ScoredJob, webhook_url: str) -> bool:
    """
    Send a single scored job notification to a Webhook URL (Discord / Slack / Custom).
    """
    if not webhook_url:
        return False

    job = scored_job.job
    score_pct = f"{int(scored_job.match_score * 100)}%"

    # Determine format based on URL endpoint
    if "discord.com/api/webhooks" in webhook_url:
        payload = {
            "embeds": [
                {
                    "title": f"🎯 {job.title} at {job.company}",
                    "url": str(job.url),
                    "color": 3066993,  # Green / Blue accent
                    "fields": [
                        {"name": "Location", "value": job.location or "N/A", "inline": True},
                        {"name": "Match Score", "value": score_pct, "inline": True},
                        {"name": "Category", "value": job.job_category.value, "inline": True},
                        {"name": "Why it fits", "value": scored_job.match_reason[:300]},
                    ],
                    "footer": {"text": "Career Tracker AI • Tamil Nadu & Karnataka Job Feed"},
                }
            ]
        }
    elif "hooks.slack.com" in webhook_url:
        payload = {
            "text": f"🎯 *New Job Alert: {job.title}* at *{job.company}* ({score_pct} Match)\n"
                    f"📍 Location: {job.location}\n"
                    f"💡 Reason: {scored_job.match_reason}\n"
                    f"🔗 Apply: {job.url}"
        }
    else:
        # Standard generic JSON payload
        payload = {
            "event": "new_job_match",
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": str(job.url),
            "match_score": scored_job.match_score,
            "match_reason": scored_job.match_reason,
            "category": job.job_category.value,
        }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Webhook alert sent successfully for %s", job.title)
        return True
    except Exception as e:
        logger.warning("Failed to send webhook alert for %s: %s", job.title, e)
        return False
