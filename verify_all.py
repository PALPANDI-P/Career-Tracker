"""
Career Tracker — Verification Script

Tests all major components to ensure proper integration:
1. Schema imports (new enums, fields)
2. Filter detection (fresher keywords)
3. Company YAML loading (all regions)
4. Dashboard app creation
5. API source imports
6. Notification DB operations
7. Sample data integrity

Run: python verify_all.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

# Configure UTF-8 output encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        PASS = "✅"
        FAIL = "❌"
    except Exception:
        PASS = "[PASS]"
        FAIL = "[FAIL]"
else:
    PASS = "✅"
    FAIL = "❌"

results = []


def test(name: str, fn):
    """Run a test and record result."""
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")



def test_schema_imports():
    from schema.job import (
        Job, ScoredJob, CompanyConfig,
        SourceType, ATSType, SeniorityLevel,
        JobCategory, NotificationPriority,
    )
    # Verify new enums
    assert JobCategory.FRESHER.value == "fresher"
    assert JobCategory.TRAINING.value == "training"
    assert JobCategory.WALK_IN.value == "walk_in"
    assert JobCategory.CAMPUS.value == "campus"
    assert NotificationPriority.HOT.value == "hot"
    assert NotificationPriority.URGENT.value == "urgent"
    assert NotificationPriority.GOOD.value == "good"
    assert NotificationPriority.WORTH_CHECKING.value == "worth_checking"
    assert NotificationPriority.NEW.value == "new"

    # Verify Job model with new fields
    job = Job(
        id="test:001",
        title="Fresher Developer",
        company="TestCo",
        url="https://example.com/job/1",
        source_type=SourceType.ATS_JSON,
        region="tamil_nadu",
        city="Chennai",
        is_fresher_eligible=True,
        job_category=JobCategory.FRESHER,
        notification_priority=NotificationPriority.HOT,
    )
    assert job.region == "tamil_nadu"
    assert job.city == "Chennai"
    assert job.is_fresher_eligible is True
    assert job.job_category == JobCategory.FRESHER
    assert job.notification_priority == NotificationPriority.HOT


def test_seniority_filter():
    from filter.seniority_filter import detect_seniority, detect_fresher_category, detect_job_category
    from schema.job import SeniorityLevel, JobCategory

    # Test existing seniority detection still works
    assert detect_seniority("Senior Software Engineer") == SeniorityLevel.SENIOR
    assert detect_seniority("Junior Developer") in (SeniorityLevel.JUNIOR, SeniorityLevel.ENTRY)
    assert detect_seniority("Intern") == SeniorityLevel.INTERN

    # Test new fresher keyword detection
    is_fresher, cat = detect_fresher_category("Fresher Software Engineer")
    assert is_fresher is True
    assert cat == JobCategory.FRESHER

    is_fresher, cat = detect_fresher_category("Graduate Engineer Trainee")
    assert is_fresher is True
    assert cat == JobCategory.TRAINING

    is_fresher, cat = detect_fresher_category("Walk-in Drive for Java Developers")
    assert is_fresher is True
    assert cat == JobCategory.WALK_IN

    is_fresher, cat = detect_fresher_category("Campus Recruitment 2026")
    assert is_fresher is True
    assert cat == JobCategory.CAMPUS

    # Test fresher-related seniority detection (should detect as entry)
    assert detect_seniority("Fresher Python Developer") == SeniorityLevel.ENTRY
    assert detect_seniority("Trainee Software Engineer") == SeniorityLevel.INTERN


def test_company_loading():
    import yaml

    companies_dir = PROJECT_ROOT / "companies"

    # Test Tamil Nadu companies
    with open(companies_dir / "tamil_nadu.yaml", "r", encoding="utf-8") as f:
        tn_data = yaml.safe_load(f)
    tn_companies = tn_data.get("companies", [])
    assert len(tn_companies) >= 50, f"Tamil Nadu has {len(tn_companies)} companies, expected 50+"

    # Test Karnataka companies
    with open(companies_dir / "karnataka.yaml", "r", encoding="utf-8") as f:
        ka_data = yaml.safe_load(f)
    ka_companies = ka_data.get("companies", [])
    assert len(ka_companies) >= 45, f"Karnataka has {len(ka_companies)} companies, expected 45+"

    # Test tier1 (global) companies
    with open(companies_dir / "tier1.yaml", "r", encoding="utf-8") as f:
        t1_data = yaml.safe_load(f)
    t1_companies = t1_data.get("companies", [])
    assert len(t1_companies) >= 10

    # Verify each company has required fields
    for co in tn_companies[:5]:
        assert "name" in co
        assert "careers_url" in co
        assert "tags" in co

    # Verify aggregators
    with open(companies_dir / "naukri_aggregator.yaml", "r", encoding="utf-8") as f:
        agg_data = yaml.safe_load(f)
    assert len(agg_data.get("aggregators", [])) >= 4

    total = len(tn_companies) + len(ka_companies) + len(t1_companies)
    return total


def test_dashboard_app():
    from dashboard.app import create_app, determine_priority
    from schema.job import NotificationPriority

    # Test app creation
    app = create_app()
    assert app is not None

    # Test priority determination
    assert determine_priority(0.85, True, "fresher") == NotificationPriority.HOT.value
    assert determine_priority(0.70, False, "junior") == NotificationPriority.GOOD.value
    assert determine_priority(0.60, True, "training") == NotificationPriority.WORTH_CHECKING.value
    assert determine_priority(0.40, False, "walk_in") == NotificationPriority.URGENT.value
    assert determine_priority(0.30, False, "unknown") == NotificationPriority.NEW.value

    # Test Flask routes respond
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200, f"Dashboard index returned {resp.status_code}"

        resp = client.get("/companies")
        assert resp.status_code == 200, f"Companies page returned {resp.status_code}"

        resp = client.get("/jobs")
        assert resp.status_code == 200, f"Jobs page returned {resp.status_code}"

        resp = client.get("/notifications")
        assert resp.status_code == 200, f"Notifications page returned {resp.status_code}"

        resp = client.get("/api/stats")
        assert resp.status_code == 200, f"API stats returned {resp.status_code}"


def test_api_source_imports():
    from fetcher.api_sources import APISource
    from fetcher.api_sources.remoteok import RemoteOKFetcher
    from fetcher.api_sources.arbeitnow import ArbeitnowFetcher
    from fetcher.api_sources.adzuna import AdzunaFetcher
    from fetcher.api_sources.jsearch import JSearchFetcher
    from fetcher.api_sources.themuse import TheMuseFetcher
    from fetcher.api_sources.hackernews import HackerNewsFetcher

    # Verify all fetchers can be instantiated
    sources = [
        RemoteOKFetcher(),
        ArbeitnowFetcher(),
        AdzunaFetcher(),
        JSearchFetcher(),
        TheMuseFetcher(),
        HackerNewsFetcher(),
    ]
    assert len(sources) == 6

    # Check free sources are auto-configured
    assert RemoteOKFetcher().is_configured is True
    assert ArbeitnowFetcher().is_configured is True
    assert TheMuseFetcher().is_configured is True
    assert HackerNewsFetcher().is_configured is True


def test_notification_db():
    import sqlite3
    from dashboard.app import ensure_notification_tables, save_notification

    # Use a DB in the project data dir (avoids Windows temp file locking)
    db_dir = PROJECT_ROOT / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "_test_verify.db")

    # Clean up from previous runs
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

    try:
        ensure_notification_tables(db_path)

        # Save a notification
        notif = {
            "job_id": "test:001",
            "title": "Test Fresher Job",
            "company": "TestCo",
            "location": "Chennai",
            "url": "https://example.com",
            "match_score": 0.85,
            "match_reason": "Great match",
            "priority": "hot",
            "category": "fresher",
            "region": "tamil_nadu",
            "city": "Chennai",
            "is_fresher_eligible": True,
        }
        notif_id = save_notification(db_path, notif)
        assert notif_id > 0

        # Verify it was saved
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT title, priority, category FROM notifications WHERE job_id = ?",
            ("test:001",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "Test Fresher Job"
        assert row[1] == "hot"
        assert row[2] == "fresher"
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_profile_config():
    import yaml
    with open(PROJECT_ROOT / "config" / "profile.yaml", "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)

    assert "Chennai" in profile["preferred_locations"]
    assert "Bangalore" in profile["preferred_locations"]
    assert "Tamil Nadu" in profile["preferred_locations"]
    assert "Karnataka" in profile["preferred_locations"]
    assert "fresher" in profile["boost_keywords"]
    assert "training" in profile["boost_keywords"]
    assert "campus hire" in profile["boost_keywords"]
    assert "tamil_nadu" in profile.get("target_regions", [])
    assert "karnataka" in profile.get("target_regions", [])


def test_settings_api_keys():
    from config.settings import Settings
    # Verify new API key fields exist in the settings model
    fields = Settings.model_fields
    assert "adzuna_app_id" in fields
    assert "adzuna_api_key" in fields
    assert "jsearch_api_key" in fields
    assert "themuse_api_key" in fields


def test_orchestrator_imports():
    from orchestrator.run import load_companies, build_company_config, main
    from orchestrator.api_pipeline import run_api_pipeline, _load_api_sources

    # Test load_companies loads from all YAML files
    companies = load_companies()
    assert len(companies) >= 100, f"Only {len(companies)} companies loaded, expected 100+"

    # Test API source loading
    sources = _load_api_sources()
    assert len(sources) >= 4, f"Only {len(sources)} API sources loaded, expected 4+"


def test_scheduler_imports():
    from scheduler.scheduler import start_scheduler, _run_main_pipeline, _run_api_pipeline


def test_js_fetcher_fallback():
    from fetcher.fetch import fetch_js
    from schema.job import CompanyConfig, ATSType
    config = CompanyConfig(
        name="TestJSCo",
        careers_url="https://example.com/careers",
        fetch_strategy="js",
        ats_type=ATSType.CUSTOM,
    )
    # Should not raise NotImplementedError anymore
    try:
        res = fetch_js(config)
        assert res is not None
        assert res.company == "TestJSCo"
    except Exception as e:
        # Http fetch error (404/500/Connection) is fine, but NOT NotImplementedError
        assert not isinstance(e, NotImplementedError), "fetch_js should fall back gracefully without NotImplementedError"


def test_new_booster_apis():
    from dashboard.app import create_app
    app = create_app()
    with app.test_client() as client:
        # Test GET /api/health
        h_resp = client.get("/api/health")
        assert h_resp.status_code == 200
        h_data = h_resp.get_json()
        assert h_data["status"] == "healthy"

        # Test POST /api/resume/analyze
        r_resp = client.post(
            "/api/resume/analyze",
            json={
                "job_title": "Python Fresher Developer",
                "job_desc": "Looking for junior developer with Python, Flask, SQL skills.",
                "skills": ["Python", "Flask", "SQL"],
            },
        )
        assert r_resp.status_code == 200
        r_data = r_resp.get_json()
        assert "match_score" in r_data
        assert r_data["match_score"] > 0


def main():
    print("=" * 60)
    print("  Career Tracker — Full Verification Suite")
    print("  Email: palulaptop@gmail.com")
    print("=" * 60)
    print()

    tests = [
        ("Schema imports (new enums + fields)", test_schema_imports),
        ("Seniority & fresher keyword detection", test_seniority_filter),
        ("Company YAML loading (TN + KA + Global)", test_company_loading),
        ("Dashboard Flask app + routes", test_dashboard_app),
        ("API source imports (6 sources)", test_api_source_imports),
        ("Notification DB operations", test_notification_db),
        ("Profile config (TN/KA focus)", test_profile_config),
        ("Settings API key fields", test_settings_api_keys),
        ("Orchestrator multi-source loading", test_orchestrator_imports),
        ("Scheduler imports", test_scheduler_imports),
        ("JS fetcher graceful fallback", test_js_fetcher_fallback),
        ("New booster APIs (Health + Resume Analysis)", test_new_booster_apis),
    ]


    print(f"Running {len(tests)} verification tests...\n")

    for name, fn in tests:
        test(name, fn)

    print()
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    print("=" * 60)
    print(f"  Results: {passed}/{len(results)} passed, {failed} failed")
    if failed == 0:
        print("  🎉 All tests passed! Dashboard is ready to launch.")
        print()
        print("  To start the demo dashboard:")
        print("    python demo_dashboard.py")
        print()
        print("  Then open: http://localhost:5000")
    else:
        print("  ⚠️  Some tests failed. See errors above.")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
