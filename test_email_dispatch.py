"""
Career Tracker — Direct Email Alert Verification Test

Executes complete email notification workflow for palulaptop@gmail.com
with high-priority fresher jobs across Pan-India software companies.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from notifier.email_notifier import send_email_digest, _build_html_digest

sample_fresher_matches = [
    {
        "title": "Graduate Engineer Trainee — Python / FastAPI",
        "company": "Zoho",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.zoho.com/careers/freshers.html",
        "match_score": 0.95,
        "match_reason": "AI Verified: 95% skill overlap. Direct match for Python, FastAPI, and PostgreSQL.",
        "priority": "hot",
        "category": "fresher",
        "region": "tamil_nadu",
    },
    {
        "title": "Junior Software Engineer — Backend",
        "company": "Razorpay",
        "location": "Bengaluru, Karnataka",
        "url": "https://razorpay.com/jobs/",
        "match_score": 0.91,
        "match_reason": "AI Verified: 91% match. Python microservices & REST API alignment.",
        "priority": "hot",
        "category": "fresher",
        "region": "karnataka",
    },
    {
        "title": "Software Development Engineer (Fresher Drive)",
        "company": "Tech Mahindra",
        "location": "Hyderabad, Telangana",
        "url": "https://www.techmahindra.com/en-in/careers/",
        "match_score": 0.88,
        "match_reason": "AI Verified: 88% match. Fresher recruitment drive for GET role.",
        "priority": "urgent",
        "category": "walk_in",
        "region": "telangana",
    },
    {
        "title": "Associate Software Engineer",
        "company": "Persistent Systems",
        "location": "Pune, Maharashtra",
        "url": "https://www.persistent.com/careers/",
        "match_score": 0.84,
        "match_reason": "AI Verified: 84% match. Core Java & Python backend alignment.",
        "priority": "good",
        "category": "junior",
        "region": "maharashtra",
    },
    {
        "title": "Graduate Engineer Trainee — Product Engineering",
        "company": "Kovai.co",
        "location": "Coimbatore, Tamil Nadu",
        "url": "https://www.kovai.co/careers/",
        "match_score": 0.89,
        "match_reason": "AI Verified: 89% match. Product company GET role with training.",
        "priority": "hot",
        "category": "training",
        "region": "tamil_nadu",
    },
]


def test_and_send_alerts():
    print("=" * 70)
    print("  CAREER TRACKER — EMAIL ALERT VERIFICATION TEST")
    print("  Target Recipient: palulaptop@gmail.com")
    print("=" * 70)

    html_output = _build_html_digest(sample_fresher_matches, "palulaptop@gmail.com")
    assert "palulaptop@gmail.com" in html_output
    assert "Zoho" in html_output
    assert "Razorpay" in html_output
    assert "Tech Mahindra" in html_output

    print("\n  📧 Generated Responsive HTML Email Digest Body:")
    print("  " + "-" * 60)
    print(f"  Length: {len(html_output)} characters")
    print(f"  Contains Target Recipient: {'palulaptop@gmail.com' in html_output}")
    print(f"  Contains Job Roles: {len(sample_fresher_matches)} roles rendered")
    print("  " + "-" * 60)

    success = send_email_digest(sample_fresher_matches, "palulaptop@gmail.com")
    assert success is True, "send_email_digest should return True"

    print("\n  ✅ SUCCESS: Email alert engine verified and prepared for palulaptop@gmail.com!")
    print("=" * 70)


if __name__ == "__main__":
    test_and_send_alerts()
