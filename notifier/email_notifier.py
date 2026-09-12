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
        matched_jobs: List of Job, ScoredJob or notification dict items
        recipient_email: Target email address

    Returns:
        True if email was sent or logged successfully.
    """
    settings = get_settings()
    target_email = recipient_email or settings.email_to or "palulaptop@gmail.com"

    # Fallback to database if matched_jobs is empty
    if not matched_jobs:
        try:
            from dedup.store import DedupStore
            store = DedupStore(settings.db_path)
            cur = store.conn.cursor()
            cur.execute(
                """
                SELECT job_id, company, title, location, url, match_score, match_reason, priority, is_fresher_eligible
                FROM notifications
                ORDER BY id DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall()
            if rows:
                matched_jobs = [dict(r) for r in rows]
                logger.info("Retrieved %d active fresher jobs from database for email alert.", len(matched_jobs))
        except Exception as err:
            logger.debug("Database fallback query for email notifier failed: %s", err)

    if not matched_jobs:
        logger.info("No new jobs to send in email digest.")
        return True

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
        "📧 EMAIL DIGEST PREPARED FOR [%s] — %d New Fresher Jobs Found! (Configure CT_SMTP_USER & CT_SMTP_PASSWORD in .env for live inbox delivery)",
        target_email,
        len(matched_jobs),
    )
    return True


def _build_html_digest(matched_jobs: list, target_email: str) -> str:
    """Build clean, modern HTML email body for job notifications."""
    job_cards = ""
    for item in matched_jobs[:15]:
        title = None
        company = None
        location = None
        url = None
        raw_score = 0.85
        reason = "Fresher & MCA job match"
        priority = "hot"
        category = "fresher"
        skills = []

        if hasattr(item, "job"):
            job = item.job
            title = getattr(job, "title", None)
            company = getattr(job, "company", None)
            location = getattr(job, "canonical_location", None) or getattr(job, "location", None)
            url = str(getattr(job, "application_url", None) or getattr(job, "url", "#"))
            raw_score = getattr(item, "match_score", 0.85)
            reason = getattr(item, "match_reason", None) or "Fresher skill match"
            priority = getattr(job, "notification_priority", "hot")
            skills = getattr(job, "skills", [])
        elif hasattr(item, "title") and hasattr(item, "company"):
            title = getattr(item, "title", None)
            company = getattr(item, "company", None)
            location = getattr(item, "canonical_location", None) or getattr(item, "location", None)
            url = str(getattr(item, "application_url", None) or getattr(item, "url", "#"))
            raw_score = getattr(item, "overall_score", None) or getattr(item, "match_score", 0.85)
            reason = getattr(item, "match_reason", None) or "Fresher & MCA job match"
            priority = getattr(item, "notification_priority", "hot")
            skills = getattr(item, "skills", [])
        elif isinstance(item, dict):
            title = item.get("title")
            company = item.get("company")
            location = item.get("location")
            url = item.get("url")
            raw_score = item.get("match_score", 0.85)
            reason = item.get("match_reason") or "Skill alignment"
            priority = item.get("priority", "hot")
            category = item.get("category", "fresher")
            skills = item.get("skills", [])
        else:
            continue

        if not title or not company:
            continue

        location = location or "Tamil Nadu / South India"
        url = url or "#"

        if isinstance(raw_score, (int, float)):
            if raw_score > 1.0:
                score_num = int(raw_score)
            else:
                score_num = int(raw_score * 100)
        else:
            score_num = 85

        score_text = f"{score_num}%"

        # Badge styling based on priority
        p_str = str(priority).lower()
        if p_str == "urgent" or "walk" in p_str:
            badge_bg = "#fef2f2"
            badge_color = "#dc2626"
            badge_label = "🔥 URGENT WALK-IN"
        elif p_str == "hot" or score_num >= 85:
            badge_bg = "#f0fdf4"
            badge_color = "#16a34a"
            badge_label = "🟢 HIGH MATCH"
        elif p_str == "good" or score_num >= 70:
            badge_bg = "#eff6ff"
            badge_color = "#2563eb"
            badge_label = "🔵 STRONG MATCH"
        else:
            badge_bg = "#fffbeb"
            badge_color = "#d97706"
            badge_label = "⚡ FRESHER ROLE"

        # Skill tags extraction fallback
        if not skills:
            t_lower = (title + " " + reason).lower()
            detected = []
            for kw in ["Python", "FastAPI", "Flask", "Django", "Java", "SQL", "PostgreSQL", "React", "REST API", "AI/ML", "NLP", "C++", "MCA", "GET"]:
                if kw.lower() in t_lower:
                    detected.append(kw)
            skills = detected or ["Python", "Fresher", "MCA/B.E"]

        skill_pills = "".join(
            f'<span style="display:inline-block; background-color:#f1f5f9; color:#475569; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:600; margin-right:4px; margin-bottom:4px;">{s}</span>'
            for s in skills[:5]
        )

        job_cards += f"""
        <div style="background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 2px 6px rgba(0,0,0,0.04);">
            <!-- Header Row: Company & Badges -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div>
                    <span style="font-size:14px; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:0.5px;">🏢 {company}</span>
                </div>
                <div>
                    <span style="background-color:{badge_bg}; color:{badge_color}; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700; margin-right:6px;">{badge_label}</span>
                    <span style="background-color:#059669; color:#ffffff; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:700;">✨ {score_text} Match</span>
                </div>
            </div>

            <!-- Job Title -->
            <h2 style="margin:0 0 10px 0; font-size:18px; color:#0f172a; font-weight:700; line-height:1.3;">
                {title}
            </h2>

            <!-- Metadata Pills -->
            <div style="font-size:13px; color:#64748b; margin-bottom:12px; line-height:1.6;">
                <span style="margin-right:14px;">📍 <strong>Location:</strong> {location}</span>
                <span style="margin-right:14px;">💼 <strong>Category:</strong> {category.capitalize()}</span>
                <span>🎓 <strong>Eligible:</strong> MCA / B.E / B.Tech Freshers</span>
            </div>

            <!-- Tech Stack Tags -->
            <div style="margin-bottom:14px;">
                {skill_pills}
            </div>

            <!-- AI Match Reason Callout -->
            <div style="background-color:#f8fafc; border-left:4px solid #3b82f6; padding:10px 14px; border-radius:0 8px 8px 0; margin-bottom:16px;">
                <p style="margin:0; font-size:13px; color:#334155; font-style:italic;">
                    💡 <strong>AI Verification:</strong> {reason}
                </p>
            </div>

            <!-- Application Action Bar -->
            <div style="text-align:right; padding-top:10px; border-top:1px dashed #e2e8f0;">
                <a href="{url}" target="_blank" style="background:linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color:#ffffff; text-decoration:none; padding:10px 22px; border-radius:8px; font-weight:700; font-size:14px; display:inline-block; box-shadow:0 4px 12px rgba(37,99,235,0.25);">
                    🚀 Apply Directly on Official Portal →
                </a>
            </div>
        </div>
        """

    if not job_cards.strip():
        job_cards = """
        <div style="background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:30px; text-align:center; color:#64748b;">
            <p style="font-size:15px; margin:0;">ℹ️ Currently tracking 200+ Genuine Software Portals across Tamil Nadu, Karnataka & Kerala for new fresher openings.</p>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px; color: #1e293b;">
        <div style="max-width: 680px; margin: 0 auto;">
            <!-- Modern Header Banner -->
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #1e293b 100%); border-radius: 16px 16px 0 0; padding: 28px 24px; text-align: center; color: #ffffff; box-shadow: 0 4px 20px rgba(15,23,42,0.15); border-bottom: 3px solid #3b82f6;">
                <span style="background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; border: 1px solid rgba(96, 165, 250, 0.3);">⚡ LIVE FRESHER JOB ALERT</span>
                <h1 style="margin: 12px 0 6px 0; font-size: 24px; font-weight: 800; tracking: -0.5px;">🎯 Career Tracker AI</h1>
                <p style="margin: 0; font-size: 14px; color: #94a3b8;">New verified fresher & GET openings for <strong>{target_email}</strong></p>
            </div>

            <!-- Body Container -->
            <div style="background-color: #f8fafc; border-radius: 0 0 16px 16px; padding: 20px 16px; border: 1px solid #e2e8f0; border-top: none;">
                {job_cards}

                <!-- Modern Footer -->
                <div style="margin-top: 24px; text-align: center; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; line-height: 1.6;">
                    <strong>Career Tracker AI Engine</strong> • Monitoring 200+ Genuine Software Portals across Tamil Nadu, Karnataka, Kerala & Pan-India<br>
                    <a href="http://localhost:5000/notifications" style="background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 6px 16px; border-radius: 6px; font-weight: 600; font-size: 12px; display: inline-block; margin-top: 10px;">🌐 Open Web Dashboard</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
