"""
Career Tracker — Sample Data Generator & Dashboard Launcher

Populates the SQLite database with realistic sample job notifications
across all priority levels (hot, urgent, good, worth_checking, new)
to demonstrate the color-coded notification system.

Then launches the Flask dashboard at http://localhost:5000

Usage:
    python demo_dashboard.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings import get_settings
from dashboard.app import create_app, ensure_notification_tables


# ─── Sample Job Data ─────────────────────────────────
# Realistic notifications across all color-coded priorities
# targeting Tamil Nadu and Karnataka companies.

SAMPLE_NOTIFICATIONS = [
    # 🟢 HOT — Green glow (score ≥ 80% AND fresher-eligible)
    {
        "job_id": "tcs:fresher-se-001",
        "title": "Graduate Engineer Trainee — Python Developer",
        "company": "TCS",
        "location": "Chennai, Tamil Nadu",
        "url": "https://learning.tcsionhub.in/hub/national-qualifier-test/",
        "match_score": 0.94,
        "match_reason": "AI Verified: TCS NQT 2026 Freshers Drive. Excellent Python + REST API alignment. Chennai location.",
        "priority": "hot",
        "category": "fresher",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "zoho:trainee-dev-002",
        "title": "Graduate Engineer Trainee — Python / Flask",
        "company": "Zoho",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.zoho.com/careers/freshers.html",
        "match_score": 0.90,
        "match_reason": "AI Verified: Zoho GET Fresher Hiring. Direct match for MCA graduates with Flask & PostgreSQL skills.",
        "priority": "hot",
        "category": "training",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "ibs:fresher-002k",
        "title": "Software Engineer Trainee — Backend (Python/Java)",
        "company": "IBS Software",
        "location": "Trivandrum, Kerala",
        "url": "https://www.ibsplc.com/careers/early-careers",
        "match_score": 0.87,
        "match_reason": "AI Verified: Technopark Trivandrum Fresher Program. Strong Python + SQL match for 2026 freshers.",
        "priority": "hot",
        "category": "fresher",
        "region": "kerala",
        "city": "Trivandrum",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "flipkart:sde1-003",
        "title": "SDE-1 (Campus & Off-Campus Fresher Hire)",
        "company": "Flipkart",
        "location": "Bangalore, Karnataka",
        "url": "https://www.flipkartcareers.com/#!/campus-connect",
        "match_score": 0.85,
        "match_reason": "AI Verified: Flipkart Campus Connect 2026. React + Node.js/Python expertise aligns with SDE-1.",
        "priority": "hot",
        "category": "fresher",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 1,
    },

    # 🔴 URGENT — Red flash (walk-in / limited deadline)
    {
        "job_id": "infosys:walkin-004",
        "title": "Walk-in Interview — Systems Engineer Trainee",
        "company": "Infosys",
        "location": "Mysore / Bangalore, Karnataka",
        "url": "https://www.infosys.com/careers/freshers.html",
        "match_score": 0.78,
        "match_reason": "AI Verified: Infosys Mysore Training Campus Drive. Urgent off-campus hiring for freshers.",
        "priority": "urgent",
        "category": "walk_in",
        "region": "karnataka",
        "city": "Mysore",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "cognizant:campus-005",
        "title": "Off-Campus Drive — GenC Next Engineer (Closing Soon!)",
        "company": "Cognizant",
        "location": "Chennai / Coimbatore, Tamil Nadu",
        "url": "https://careers.cognizant.com/global/en/campus-hiring",
        "match_score": 0.74,
        "match_reason": "AI Verified: Cognizant GenC Off-Campus 2026. Full stack development role closing shortly.",
        "priority": "urgent",
        "category": "campus",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },

    # 🔵 GOOD — Blue glow (score ≥ 65%)
    {
        "job_id": "ust:kerala-006k",
        "title": "Associate Software Engineer Trainee",
        "company": "UST Kerala",
        "location": "Kochi, Kerala",
        "url": "https://www.ust.com/en/careers/campus-hiring",
        "match_score": 0.79,
        "match_reason": "AI Verified: UST Infopark Kochi Campus Hiring. REST API & Python focus.",
        "priority": "good",
        "category": "fresher",
        "region": "kerala",
        "city": "Kochi",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "freshworks:junior-006",
        "title": "Product Engineer Trainee — Backend",
        "company": "Freshworks",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.freshworks.com/company/careers/fresher-hiring/",
        "match_score": 0.76,
        "match_reason": "AI Verified: Freshworks Fresh Academy 2026. Strong Python & REST API match for MCA candidates.",
        "priority": "good",
        "category": "junior",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "razorpay:se-007",
        "title": "Software Engineer — Platform (0-2 Yrs)",
        "company": "Razorpay",
        "location": "Bangalore, Karnataka",
        "url": "https://razorpay.com/careers/#freshers",
        "match_score": 0.73,
        "match_reason": "AI Verified: FinTech entry role. Docker & API experience relevant for junior platform engineers.",
        "priority": "good",
        "category": "fresher",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "phonepe:jse-008",
        "title": "Associate Software Engineer",
        "company": "PhonePe",
        "location": "Bangalore, Karnataka",
        "url": "https://www.phonepe.com/careers",
        "match_score": 0.70,
        "match_reason": "High-scale payments system. Java + microservices experience needed. Great learning opportunity.",
        "priority": "good",
        "category": "junior",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 0,
    },
    {
        "job_id": "google:step-009",
        "title": "Software Engineer, Early Career",
        "company": "Google Bangalore",
        "location": "Bangalore, Karnataka",
        "url": "https://www.google.com/about/careers/applications/jobs/results",
        "match_score": 0.67,
        "match_reason": "Google's early career program. Python + ML skills align. Highly competitive but worth applying.",
        "priority": "good",
        "category": "junior",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 0,
    },

    # 🟡 WORTH CHECKING — Yellow glow (score 55-65%)
    {
        "job_id": "wipro:elite-010",
        "title": "Wipro Elite NLTH — Fresher Program",
        "company": "Wipro",
        "location": "Chennai, Tamil Nadu",
        "url": "https://careers.wipro.com",
        "match_score": 0.62,
        "match_reason": "Large-scale fresher hiring. Training provided. Less technical depth but good starting point.",
        "priority": "worth_checking",
        "category": "training",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "capgemini:trainee-011",
        "title": "Trainee — Software Engineering",
        "company": "Capgemini",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.capgemini.com/in-en/careers",
        "match_score": 0.58,
        "match_reason": "Consulting firm with training program. Broad skill development but may not focus on your core stack.",
        "priority": "worth_checking",
        "category": "training",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "accenture:ase-012",
        "title": "Associate Software Engineer — Technology",
        "company": "Accenture Bangalore",
        "location": "Bangalore, Karnataka",
        "url": "https://www.accenture.com/in-en/careers",
        "match_score": 0.60,
        "match_reason": "Large consulting firm. Some cloud and API work relevant. Entry level with training support.",
        "priority": "worth_checking",
        "category": "junior",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 1,
    },

    # 🟣 NEW — Purple pulse (any new job from tracked company)
    {
        "job_id": "swiggy:intern-013",
        "title": "Software Engineering Intern — Summer 2026",
        "company": "Swiggy",
        "location": "Bangalore, Karnataka",
        "url": "https://careers.swiggy.com",
        "match_score": 0.45,
        "match_reason": "Internship at a top food-tech unicorn. React + Node.js alignment. Good stepping stone.",
        "priority": "new",
        "category": "internship",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 1,
    },
    {
        "job_id": "cred:frontend-014",
        "title": "Frontend Engineer — React",
        "company": "CRED",
        "location": "Bangalore, Karnataka",
        "url": "https://careers.cred.club",
        "match_score": 0.52,
        "match_reason": "Premium FinTech startup. React expertise matches. Competitive but great brand on resume.",
        "priority": "new",
        "category": "junior",
        "region": "karnataka",
        "city": "Bangalore",
        "is_fresher_eligible": 0,
    },
    {
        "job_id": "chargebee:se-015",
        "title": "Software Engineer — API Platform",
        "company": "Chargebee",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.chargebee.com/careers",
        "match_score": 0.48,
        "match_reason": "SaaS product company in Chennai. REST API and Python skills align. Good product engineering exposure.",
        "priority": "new",
        "category": "junior",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 0,
    },
    {
        "job_id": "kovai:fullstack-016",
        "title": "Full Stack Developer — Freshers Welcome",
        "company": "Kovai.co",
        "location": "Coimbatore, Tamil Nadu",
        "url": "https://www.kovai.co/careers",
        "match_score": 0.50,
        "match_reason": "Coimbatore-based product company. Full stack role aligns with React + Node.js. Growing startup.",
        "priority": "new",
        "category": "fresher",
        "region": "tamil_nadu",
        "city": "Coimbatore",
        "is_fresher_eligible": 1,
    },

    # Remote / Global jobs from APIs
    {
        "job_id": "remoteok:backend-017",
        "title": "Junior Backend Developer (Remote)",
        "company": "TechStartup Co",
        "location": "Remote",
        "url": "https://remoteok.com/l/12345",
        "match_score": 0.65,
        "match_reason": "Remote junior role. Python + Django stack matches your skills. No location constraint.",
        "priority": "good",
        "category": "junior",
        "region": "global",
        "city": None,
        "is_fresher_eligible": 0,
    },
    {
        "job_id": "adzuna:trainee-018",
        "title": "Management Trainee — IT Services",
        "company": "HCL Technologies",
        "location": "Chennai, Tamil Nadu",
        "url": "https://www.hcltech.com/careers",
        "match_score": 0.55,
        "match_reason": "Management trainee program. Good stepping stone into IT services sector. Training provided.",
        "priority": "worth_checking",
        "category": "training",
        "region": "tamil_nadu",
        "city": "Chennai",
        "is_fresher_eligible": 1,
    },
]


def populate_sample_data() -> None:
    """Insert sample notifications into the database."""
    settings = get_settings()
    db_path = settings.db_path

    # Ensure the data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Create tables
    ensure_notification_tables(db_path)

    # Also create the seen_hashes and runs tables for the dashboard stats
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_hashes (
                hash TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                first_seen_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                companies_processed INTEGER NOT NULL,
                jobs_found INTEGER NOT NULL,
                jobs_new INTEGER NOT NULL,
                errors TEXT
            )
        """)
        conn.commit()

    now = datetime.now(timezone.utc)

    # Insert sample notifications with staggered timestamps
    with sqlite3.connect(db_path) as conn:
        for i, notif in enumerate(SAMPLE_NOTIFICATIONS):
            # Stagger timestamps so they appear in chronological order
            created_at = (now - timedelta(hours=len(SAMPLE_NOTIFICATIONS) - i)).isoformat()

            conn.execute(
                """
                INSERT OR REPLACE INTO notifications
                (job_id, title, company, location, url, match_score, match_reason,
                 priority, category, region, city, is_fresher_eligible, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    notif["job_id"],
                    notif["title"],
                    notif["company"],
                    notif.get("location"),
                    notif["url"],
                    notif["match_score"],
                    notif["match_reason"],
                    notif["priority"],
                    notif["category"],
                    notif["region"],
                    notif.get("city"),
                    notif.get("is_fresher_eligible", 0),
                    created_at,
                ),
            )

            # Also add to seen_hashes for stats
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_hashes (hash, job_id, company, title, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    notif["job_id"],
                    notif["job_id"],
                    notif["company"],
                    notif["title"],
                    created_at,
                ),
            )

        # Insert a sample pipeline run record
        conn.execute(
            """
            INSERT INTO runs (timestamp, companies_processed, jobs_found, jobs_new, errors)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now.isoformat(),
                117,   # 50 TN + 55 KA + 12 Global
                284,
                18,
                json.dumps([]),
            ),
        )
        conn.commit()

    # Populate discovered startup companies
    try:
        from discovery.pipeline import run_company_discovery_pipeline
        run_company_discovery_pipeline(store=DedupStore(db_path))
    except Exception as e:
        print(f"Discovery seed error: {e}")

    print(f"✅ Inserted {len(SAMPLE_NOTIFICATIONS)} sample notifications into {db_path}")
    print(f"   Priority breakdown:")
    priority_counts = {}
    for n in SAMPLE_NOTIFICATIONS:
        p = n["priority"]
        priority_counts[p] = priority_counts.get(p, 0) + 1
    for p, count in sorted(priority_counts.items()):
        emoji_map = {"hot": "🟢", "urgent": "🔴", "good": "🔵", "worth_checking": "🟡", "new": "🟣"}
        print(f"   {emoji_map.get(p, '⚪')} {p}: {count} notifications")


def main() -> None:
    """Populate sample data and launch the dashboard."""
    print("=" * 60)
    print("  Career Tracker — Dashboard Demo")
    print("  Email: palulaptop@gmail.com")
    print("=" * 60)
    print()

    # Step 1: Populate sample data
    print("📊 Populating sample data...")
    populate_sample_data()
    print()

    # Step 2: Launch dashboard
    print("🚀 Launching dashboard at http://localhost:5000")
    print("   Open your browser and navigate to:")
    print()
    print("   📍 Dashboard:     http://localhost:5000/")
    print("   💼 Jobs:          http://localhost:5000/jobs")
    print("   🏢 Companies:     http://localhost:5000/companies")
    print("   🔔 Notifications: http://localhost:5000/notifications")
    print()
    print("   Press Ctrl+C to stop the server.")
    print("=" * 60)

    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)


if __name__ == "__main__":
    main()
