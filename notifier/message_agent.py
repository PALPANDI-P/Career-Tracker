"""Career Tracker — Notifier Message Agent."""

from __future__ import annotations

import logging

from config.settings import get_settings

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic  # noqa: F401 — available for patching in tests
except ImportError:
    _anthropic = None  # type: ignore[assignment]


def draft_match_note(job, profile=None):
    settings = get_settings()
    if not settings.anthropic_api_key:
        return getattr(job, 'match_reason', '') or 'Matched against your profile.'
    job_title = job.job.title if hasattr(job, 'job') else getattr(job, 'title', '')
    job_company = job.job.company if hasattr(job, 'job') else getattr(job, 'company', '')
    job_desc = job.job.description if hasattr(job, 'job') else getattr(job, 'description', '')
    prompt = (
        'Given this job and candidate profile, write a 2-3 line note explaining why this is a good match.\n'
        'Be specific about skill overlap.\n\n'
        f'Job: {job_title} at {job_company}\n'
        f'Description: {job_desc[:1000]}\n'
    )
    try:
        client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=min(settings.llm_max_tokens, 300),
            messages=[{'role': 'user', 'content': prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return getattr(job, 'match_reason', '') or 'Matched against your profile.'


def notify_matches(matched_jobs: list) -> None:
    """Send alert messages for matched jobs via Telegram if configured."""
    settings = get_settings()
    if not settings.telegram_chat_id or not settings.telegram_bot_token:
        logger.debug("Telegram credentials not configured — skipping Telegram notification.")
        return

    from notifier.telegram import send_alert
    for item in matched_jobs[:5]:
        note = draft_match_note(item)
        send_alert(settings.telegram_chat_id, note)
