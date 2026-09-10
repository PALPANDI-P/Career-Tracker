"""
Career Tracker — Daily Digest Generator

Implements Section 23 of MASTER DEVELOPMENT PROMPT.

Generates a structured daily summary of job search activity including:
  - Total jobs discovered
  - New jobs (not duplicates)
  - Fresh eligible jobs (within 24h)
  - High matches (score >= 90)
  - Strong matches (score >= 80)
  - Review candidates (score >= 70)
  - Duplicates removed
  - Stale jobs removed

Top opportunities listed with company, role, and match score.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from schema.job import Job, FreshnessStatus, LifecycleStatus

logger = logging.getLogger(__name__)

# Thresholds from Section 22
HIGH_PRIORITY_THRESHOLD = 90.0
STRONG_MATCH_THRESHOLD = 80.0
REVIEW_THRESHOLD = 70.0


class DigestStats:
    """Collects statistics across a pipeline run for the daily digest."""

    def __init__(self) -> None:
        self.discovered: int = 0
        self.new_jobs: int = 0
        self.fresh_eligible: int = 0
        self.duplicates_removed: int = 0
        self.stale_removed: int = 0
        self.eligibility_rejected: int = 0
        self.high_matches: list[Job] = []
        self.strong_matches: list[Job] = []
        self.review_candidates: list[Job] = []
        self.run_date: datetime = datetime.now(timezone.utc)

    def add_job(self, job: Job) -> None:
        """Categorize a job into the appropriate digest bucket."""
        score = job.overall_score or 0.0
        if score >= HIGH_PRIORITY_THRESHOLD:
            self.high_matches.append(job)
        elif score >= STRONG_MATCH_THRESHOLD:
            self.strong_matches.append(job)
        elif score >= REVIEW_THRESHOLD:
            self.review_candidates.append(job)


def generate_digest(
    stats: DigestStats,
    output_format: str = "text",
) -> str:
    """
    Generate the daily digest summary.

    Args:
        stats: DigestStats object collected during the pipeline run.
        output_format: 'text', 'html', or 'telegram'.

    Returns:
        Formatted digest string.
    """
    all_top = sorted(
        stats.high_matches + stats.strong_matches + stats.review_candidates,
        key=lambda j: (j.overall_score or 0.0),
        reverse=True,
    )[:10]

    if output_format == "telegram":
        return _format_telegram(stats, all_top)
    elif output_format == "html":
        return _format_html(stats, all_top)
    else:
        return _format_text(stats, all_top)


def _format_text(stats: DigestStats, top_jobs: list[Job]) -> str:
    """Plain text daily digest."""
    date_str = stats.run_date.strftime("%d %b %Y")
    lines = [
        f"═══════════════════════════════════════",
        f"  🎯 TODAY'S JOB SEARCH — {date_str}",
        f"═══════════════════════════════════════",
        f"",
        f"  Jobs discovered:     {stats.discovered:>6}",
        f"  New jobs:            {stats.new_jobs:>6}",
        f"  Fresh eligible:      {stats.fresh_eligible:>6}",
        f"  Duplicates removed:  {stats.duplicates_removed:>6}",
        f"  Stale removed:       {stats.stale_removed:>6}",
        f"  Ineligible removed:  {stats.eligibility_rejected:>6}",
        f"",
        f"  🔥 High matches (≥90%):   {len(stats.high_matches)}",
        f"  🟢 Strong matches (≥80%): {len(stats.strong_matches)}",
        f"  🟡 Review (≥70%):         {len(stats.review_candidates)}",
        f"",
    ]

    if top_jobs:
        lines.append("─── TOP OPPORTUNITIES ──────────────────")
        for i, job in enumerate(top_jobs, 1):
            score = job.overall_score or 0.0
            badge = _badge(score)
            loc = job.canonical_location or job.location or "Unknown"
            resume = job.recommended_resume or "—"
            lines.append(
                f"  {i}. {badge} {job.company} — {job.title}"
            )
            lines.append(f"     Score: {score:.0f}% | Location: {loc}")
            lines.append(f"     Resume: {resume}")
            if job.application_url:
                lines.append(f"     Apply: {job.application_url[:70]}")
            lines.append("")
    else:
        lines.append("  No high-quality matches found today.")

    lines.append("═══════════════════════════════════════")
    return "\n".join(lines)


def _format_telegram(stats: DigestStats, top_jobs: list[Job]) -> str:
    """Telegram-formatted daily digest (Markdown)."""
    date_str = stats.run_date.strftime("%d %b %Y")
    lines = [
        f"🎯 *Today's Job Search — {date_str}*",
        f"",
        f"📊 *Statistics*",
        f"  Discovered: `{stats.discovered}`",
        f"  New: `{stats.new_jobs}`",
        f"  Fresh eligible: `{stats.fresh_eligible}`",
        f"  Duplicates removed: `{stats.duplicates_removed}`",
        f"  Stale removed: `{stats.stale_removed}`",
        f"",
        f"🏆 *Match Summary*",
        f"  🔥 High (≥90%): `{len(stats.high_matches)}`",
        f"  🟢 Strong (≥80%): `{len(stats.strong_matches)}`",
        f"  🟡 Review (≥70%): `{len(stats.review_candidates)}`",
    ]

    if top_jobs:
        lines.append(f"\n🏅 *Top Opportunities*")
        for i, job in enumerate(top_jobs[:5], 1):
            score = job.overall_score or 0.0
            badge = _badge(score)
            lines.append(
                f"\n{i}. {badge} *{job.company}*"
                f"\n   📌 {job.title}"
                f"\n   📍 {job.canonical_location or job.location or 'Unknown'}"
                f"\n   💯 {score:.0f}%"
            )
            if job.application_url:
                lines.append(f"   🔗 [Apply Here]({job.application_url})")

    return "\n".join(lines)


def _format_html(stats: DigestStats, top_jobs: list[Job]) -> str:
    """HTML-formatted daily digest for email."""
    date_str = stats.run_date.strftime("%d %B %Y")
    rows = ""
    for i, job in enumerate(top_jobs, 1):
        score = job.overall_score or 0.0
        badge = _badge(score)
        rows += f"""
        <tr>
          <td>{i}. {badge}</td>
          <td><strong>{job.company}</strong></td>
          <td>{job.title}</td>
          <td>{job.canonical_location or job.location or '—'}</td>
          <td>{score:.0f}%</td>
          <td><a href="{job.application_url or '#'}">Apply</a></td>
        </tr>"""

    return f"""
<html><body style="font-family: sans-serif; max-width: 700px; margin: auto;">
<h2>🎯 Today's Job Search — {date_str}</h2>
<table border="0" cellpadding="8" style="width:100%">
<tr><td>📦 Discovered</td><td>{stats.discovered}</td>
    <td>✅ New</td><td>{stats.new_jobs}</td></tr>
<tr><td>🔥 Fresh Eligible</td><td>{stats.fresh_eligible}</td>
    <td>🗑️ Duplicates Removed</td><td>{stats.duplicates_removed}</td></tr>
<tr><td>🔥 High Matches (≥90%)</td><td>{len(stats.high_matches)}</td>
    <td>🟢 Strong (≥80%)</td><td>{len(stats.strong_matches)}</td></tr>
</table>
<h3>🏅 Top Opportunities</h3>
<table border="1" cellpadding="8" style="border-collapse:collapse; width:100%">
<tr><th>#</th><th>Company</th><th>Role</th><th>Location</th><th>Score</th><th>Apply</th></tr>
{rows}
</table>
</body></html>
""".strip()


def _badge(score: float) -> str:
    if score >= HIGH_PRIORITY_THRESHOLD:
        return "🔥"
    if score >= STRONG_MATCH_THRESHOLD:
        return "🟢"
    if score >= REVIEW_THRESHOLD:
        return "🟡"
    return "⚪"
