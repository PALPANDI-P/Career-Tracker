"""
Career Tracker — Hourly Email Bot Verification Test

Validates that:
1. Hourly job bot initializes properly
2. Correctly targets palulaptop@gmail.com
3. Generates valid HTML digest format
4. Successfully triggers email dispatch/logging pipeline
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings import get_settings
from notifier.email_notifier import send_email_digest, _build_html_digest


def test_email_digest_for_palulaptop():
    settings = get_settings()
    assert settings.email_to == "palulaptop@gmail.com", f"Expected default email_to to be palulaptop@gmail.com, got {settings.email_to}"
    assert settings.schedule_interval_hours == 1, f"Expected schedule_interval_hours to be 1, got {settings.schedule_interval_hours}"

    sample_jobs = [
        {
            "job_id": "test:fresher-dev-001",
            "title": "Graduate Trainee Engineer — Python / Backend",
            "company": "TCS",
            "location": "Chennai, Tamil Nadu",
            "url": "https://learning.tcsionhub.in/hub/national-qualifier-test/",
            "match_score": 0.95,
            "match_reason": "Direct MCA graduate match for Python & PostgreSQL stack.",
            "priority": "hot",
            "category": "fresher",
            "is_fresher_eligible": 1,
        },
        {
            "job_id": "test:trainee-dev-002",
            "title": "Software Development Engineer Trainee",
            "company": "Zoho",
            "location": "Chennai, Tamil Nadu",
            "url": "https://www.zoho.com/careers/freshers.html",
            "match_score": 0.91,
            "match_reason": "AI Verified GET hiring drive.",
            "priority": "hot",
            "category": "training",
            "is_fresher_eligible": 1,
        },
    ]

    html_content = _build_html_digest(sample_jobs, target_email="palulaptop@gmail.com")
    assert "palulaptop@gmail.com" in html_content
    assert "Graduate Trainee Engineer" in html_content
    assert "Zoho" in html_content

    sent = send_email_digest(sample_jobs, recipient_email="palulaptop@gmail.com")
    assert sent is True
    print("✅ Email digest verification test for palulaptop@gmail.com PASSED!")


if __name__ == "__main__":
    test_email_digest_for_palulaptop()
