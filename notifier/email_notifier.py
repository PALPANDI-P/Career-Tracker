"""
Career Tracker — Email Notifier Module

Sends HTML job alert emails to palulaptop@gmail.com
when new high-priority fresher & trainee jobs are found.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import get_settings

logger = logging.getLogger(__name__)


def send_email_digest(matched_jobs: list, recipient_email: str = "palulaptop@gmail.com") -> bool:
    """
    Send an HTML email digest of newly discovered fresher jobs to recipient_email.

    Args:
        matched_jobs: List of ScoredJob or notification dict items
        recipient_email: Target email address

    Returns:
        True if email was sent or logged successfully.
    """
    if not matched_jobs:
        logger.info("No new jobs to send in email digest.")
        return True

    settings = get_settings()
    target_email = recipient_email or settings.email_to or "palulaptop@gmail.com"

    subject = f"🎯 Career Tracker Alert: {len(matched_jobs)} New Fresher & Trainee Jobs Found!"

    html_content = _build_html_digest(matched_jobs, target_email)

    # Attempt SMTP dispatch if user credentials are provided in .env
    if settings.smtp_user and settings.smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_user
            msg["To"] = target_email

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_user, [target_email], msg.as_string())

            logger.info("✅ Sent email job digest (%d jobs) to %s", len(matched_jobs), target_email)
            return True
        except Exception as e:
            logger.warning("SMTP email dispatch failed: %s. Logging digest locally instead.", e)

    # Fallback / Demo Mode: Log email digest nicely
    logger.info(
        "📧 EMAIL DIGEST PREPARED FOR [%s] — %d New Fresher Jobs Found! (Configure SMTP_USER & SMTP_PASSWORD in .env for live inbox delivery)",
        target_email,
        len(matched_jobs),
    )
    return True


def _build_html_digest(matched_jobs: list, target_email: str) -> str:
    """Build clean HTML email body for job notifications."""
    job_rows = ""
    for item in matched_jobs[:15]:
        if hasattr(item, "job"):
            job = item.job
            title = job.title
            company = job.company
            location = job.location or "Not specified"
            url = str(job.url)
            score = f"{int(item.match_score * 100)}%"
            reason = item.match_reason
            priority = getattr(job, "notification_priority", "hot")
        elif isinstance(item, dict):
            title = item.get("title", "Software Engineer")
            company = item.get("company", "Company")
            location = item.get("location", "Not specified")
            url = item.get("url", "#")
            score = f"{int(item.get('match_score', 0.8) * 100)}%"
            reason = item.get("match_reason", "Skill alignment")
            priority = item.get("priority", "hot")
        else:
            continue

        priority_color = {
            "hot": "#16a34a",
            "urgent": "#dc2626",
            "good": "#2563eb",
            "worth_checking": "#d97706",
            "new": "#7c3aed",
        }.get(str(priority).lower(), "#2563eb")

        job_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 12px; vertical-align: top;">
                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:{priority_color}; margin-right:6px;"></span>
                <strong style="font-size:16px; color:#1e293b;">{title}</strong><br>
                <span style="color:#475569; font-size:14px;">🏢 <strong>{company}</strong> | 📍 {location}</span><br>
                <em style="color:#64748b; font-size:13px; display:block; margin-top:4px;">💡 {reason}</em>
            </td>
            <td style="padding: 12px; text-align: center; vertical-align: middle;">
                <span style="background-color:#eff6ff; color:#1d4ed8; font-weight:bold; padding:4px 8px; border-radius:4px; font-size:13px;">{score}</span>
            </td>
            <td style="padding: 12px; text-align: center; vertical-align: middle;">
                <a href="{url}" target="_blank" style="background-color:#2563eb; color:#ffffff; text-decoration:none; padding:8px 14px; border-radius:6px; font-weight:bold; font-size:13px; display:inline-block;">Apply Now →</a>
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1d4ed8, #2563eb); padding: 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px;">🎯 Career Tracker — Fresher Job Alert</h1>
                <p style="margin: 6px 0 0 0; font-size: 14px; opacity: 0.9;">New fresher & trainee openings discovered for <strong>{target_email}</strong></p>
            </div>

            <div style="padding: 20px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b;">
                            <th style="padding: 10px;">Job Details</th>
                            <th style="padding: 10px; text-align: center;">Match</th>
                            <th style="padding: 10px; text-align: center;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {job_rows}
                    </tbody>
                </table>

                <div style="margin-top: 24px; text-align: center; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                    Career Tracker AI • Tracking 200+ Genuine Software Company Portals across India (Tamil Nadu, Karnataka, Kerala, Telangana, Maharashtra, Delhi-NCR)<br>
                    <a href="http://localhost:5000/notifications" style="color: #2563eb; text-decoration: none;">Open Web Dashboard</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
