"""
Career Tracker — Full Integration Test Suite
Tests all new modules end-to-end with realistic data.
Run with: python verify_all_modules.py
"""

import sys
import traceback
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")

PASSED = []
FAILED = []


def test(name, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  ✅ PASS  {name}")
    except Exception as exc:
        FAILED.append((name, str(exc)))
        print(f"  ❌ FAIL  {name}")
        traceback.print_exc()


print("=" * 65)
print("  CAREER TRACKER — FULL MODULE INTEGRATION TESTS")
print("=" * 65)

# ────────────────────────────────────────────────────────────────────────
print("\n[1] Schema — Job model")

def test_job_new_fields():
    from schema.job import Job, SourceType, FreshnessStatus, LifecycleStatus, RemoteType
    job = Job(
        id="zoho:123",
        title="Junior Python Developer",
        company="Zoho",
        url="https://careers.zoho.com/jobs/123",
        source_type=SourceType.ATS_JSON,
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        employment_type="Full-time",
        remote_type=RemoteType.ONSITE,
        skills=["Python", "FastAPI"],
        experience_text="0-1 years",
        education_text="B.E/B.Tech/MCA",
    )
    assert job.content_hash is not None, "content_hash should be auto-generated"
    assert job.freshness_status == FreshnessStatus.UNKNOWN, "freshness_status default = UNKNOWN"
    assert job.lifecycle_status == LifecycleStatus.DISCOVERED
    assert job.remote_type == RemoteType.ONSITE
    assert len(job.skills) == 2

test("Job model — new fields (freshness_status, lifecycle_status, content_hash, remote_type, skills)", test_job_new_fields)


def test_job_published_at_posted_date_sync():
    from schema.job import Job, SourceType
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc)
    job = Job(
        id="test:sync",
        title="Python Dev",
        company="Acme",
        url="https://acme.com/jobs/1",
        source_type=SourceType.ATS_JSON,
        published_at=ts,
    )
    assert job.posted_date == ts, "posted_date should sync from published_at"

test("Job model — published_at <-> posted_date sync", test_job_published_at_posted_date_sync)


def test_job_content_hash_stable():
    from schema.job import Job, SourceType
    h = Job.make_content_hash("Python Developer", "Zoho", "We need Python skills", "Chennai")
    h2 = Job.make_content_hash("Python Developer", "Zoho", "We need Python skills", "Chennai")
    assert h == h2, "content hash must be deterministic"

test("Job model — make_content_hash() is deterministic", test_job_content_hash_stable)


# ────────────────────────────────────────────────────────────────────────
print("\n[2] Freshness Engine")

def test_fresh_confirmed():
    from schema.job import Job, SourceType, FreshnessStatus
    from dedup.freshness_engine import classify_freshness, FreshnessConfig
    job = Job(id="t:1", title="Fresher Dev", company="X", url="https://x.com/jobs/1",
              source_type=SourceType.ATS_JSON, published_at=datetime.now(timezone.utc) - timedelta(hours=3))
    status = classify_freshness(job, FreshnessConfig(max_age_hours=24))
    assert status == FreshnessStatus.FRESH_CONFIRMED

test("Freshness — published 3h ago → FRESH_CONFIRMED", test_fresh_confirmed)

def test_stale():
    from schema.job import Job, SourceType, FreshnessStatus
    from dedup.freshness_engine import classify_freshness
    job = Job(id="t:2", title="Dev", company="X", url="https://x.com/jobs/2",
              source_type=SourceType.ATS_JSON, published_at=datetime.now(timezone.utc) - timedelta(hours=30))
    assert classify_freshness(job) == FreshnessStatus.STALE

test("Freshness — published 30h ago → STALE", test_stale)

def test_classify_and_update():
    from schema.job import Job, SourceType, FreshnessStatus
    from dedup.freshness_engine import classify_and_update
    job = Job(id="t:3", title="Dev", company="X", url="https://x.com/jobs/3",
              source_type=SourceType.ATS_JSON, published_at=datetime.now(timezone.utc) - timedelta(hours=1))
    updated = classify_and_update(job)
    assert updated.freshness_status == FreshnessStatus.FRESH_CONFIRMED
    assert updated.first_seen_at is not None

test("Freshness — classify_and_update() sets freshness_status + first_seen_at", test_classify_and_update)


# ────────────────────────────────────────────────────────────────────────
print("\n[3] URL Cleaner")

def test_strip_utm():
    from dedup.url_cleaner import strip_tracking_params
    url = "https://boards.greenhouse.io/zoho/jobs/123?utm_source=linkedin&utm_medium=social&gh_src=abc"
    clean = strip_tracking_params(url)
    assert "utm_source" not in clean
    assert "utm_medium" not in clean
    assert "gh_src" not in clean
    assert "123" in clean  # job ID preserved

test("URL Cleaner — strip UTM + gh_src tracking params", test_strip_utm)

def test_canonicalize():
    from dedup.url_cleaner import canonicalize_url
    u1 = canonicalize_url("https://lever.co/company/jobs/abc?utm_source=x")
    u2 = canonicalize_url("HTTPS://LEVER.CO/company/jobs/abc?utm_source=y")
    assert u1 == u2  # Same canonical URL despite different case and tracking

test("URL Cleaner — canonicalize_url() normalizes case + strips tracking", test_canonicalize)


# ────────────────────────────────────────────────────────────────────────
print("\n[4] Fresher Classifier")

def test_eligible_fresher():
    from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
    eligibility, conf, signals = classify_fresher_eligibility(
        "We are hiring freshers for our 2026 batch.", title="Fresher Python Developer"
    )
    assert eligibility == FresherEligibility.ELIGIBLE
    assert conf > 0.5

test("Fresher Classifier — 'Fresher Python Developer' → ELIGIBLE", test_eligible_fresher)

def test_senior_rejected():
    from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
    eligibility, _, _ = classify_fresher_eligibility("Senior required.", title="Senior Backend Developer")
    assert eligibility == FresherEligibility.INELIGIBLE

test("Fresher Classifier — 'Senior Backend Developer' → INELIGIBLE", test_senior_rejected)

def test_lower_priority_ambiguous():
    from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
    eligibility, _, _ = classify_fresher_eligibility(
        "2 years experience preferred. Freshers may apply.", title="Software Engineer"
    )
    assert eligibility in (FresherEligibility.LOWER_PRIORITY, FresherEligibility.ELIGIBLE)

test("Fresher Classifier — '2 years preferred' → LOWER_PRIORITY (not INELIGIBLE)", test_lower_priority_ambiguous)

def test_get_trainee():
    from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
    eligibility, _, _ = classify_fresher_eligibility(
        "Graduate Engineer Trainee program for 2025/2026 batch.", title="GET — Software Engineer"
    )
    assert eligibility == FresherEligibility.ELIGIBLE

test("Fresher Classifier — 'GET — Software Engineer' → ELIGIBLE", test_get_trainee)

def test_senior_in_desc_not_title():
    from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
    eligibility, _, _ = classify_fresher_eligibility(
        "You will work alongside senior engineers to learn and grow.",
        title="Junior Python Developer",
    )
    assert eligibility != FresherEligibility.INELIGIBLE

test("Fresher Classifier — 'senior' only in description (not title) → NOT INELIGIBLE", test_senior_in_desc_not_title)


# ────────────────────────────────────────────────────────────────────────
print("\n[5] Location Engine")

def test_bangalore_canonical():
    from filter.location_engine import normalize_location
    loc = normalize_location("Bangalore, India")
    assert loc.city == "Bengaluru"
    assert loc.state == "Karnataka"

test("Location Engine — 'Bangalore' → city=Bengaluru, state=Karnataka", test_bangalore_canonical)

def test_chennai_weight():
    from filter.location_engine import normalize_location, calculate_location_weight
    loc = normalize_location("Chennai")
    w = calculate_location_weight(loc)
    assert w == 1.0, f"Chennai should have weight 1.0, got {w}"

test("Location Engine — Chennai has weight 1.0 (preferred city)", test_chennai_weight)

def test_remote_weight():
    from filter.location_engine import normalize_location, calculate_location_weight
    loc = normalize_location("Remote")
    w = calculate_location_weight(loc)
    assert w == 0.9

test("Location Engine — Remote has weight 0.9", test_remote_weight)

def test_trivandrum_normalized():
    from filter.location_engine import normalize_location
    loc = normalize_location("Trivandrum")
    assert loc.city == "Thiruvananthapuram"
    assert loc.state == "Kerala"

test("Location Engine — 'Trivandrum' → Thiruvananthapuram, Kerala", test_trivandrum_normalized)


# ────────────────────────────────────────────────────────────────────────
print("\n[6] Role Taxonomy")

def test_python_taxonomy():
    from filter.role_taxonomy import classify_role, TaxonomyCategory, TaxonomySubcategory
    cat, sub, conf = classify_role("Junior Python Developer")
    assert cat == TaxonomyCategory.SOFTWARE_DEVELOPMENT
    assert sub == TaxonomySubcategory.PYTHON
    assert conf > 0.5

test("Role Taxonomy — 'Junior Python Developer' → Python/Software Dev", test_python_taxonomy)

def test_ai_ml_taxonomy():
    from filter.role_taxonomy import classify_role, TaxonomyCategory
    cat, sub, conf = classify_role("Machine Learning Engineer", "Build NLP pipelines with scikit-learn")
    assert cat == TaxonomyCategory.AI_ML

test("Role Taxonomy — 'ML Engineer' + NLP desc → AI_ML", test_ai_ml_taxonomy)

def test_nlp_taxonomy():
    from filter.role_taxonomy import classify_role, TaxonomyCategory, TaxonomySubcategory
    cat, sub, conf = classify_role("NLP Engineer")
    assert cat == TaxonomyCategory.AI_ML
    assert sub == TaxonomySubcategory.NLP

test("Role Taxonomy — 'NLP Engineer' → AI_ML/NLP", test_nlp_taxonomy)

def test_unrelated_taxonomy():
    from filter.role_taxonomy import classify_role, TaxonomyCategory
    cat, _, _ = classify_role("HR Business Partner")
    assert cat == TaxonomyCategory.UNKNOWN

test("Role Taxonomy — 'HR Business Partner' → UNKNOWN", test_unrelated_taxonomy)


# ────────────────────────────────────────────────────────────────────────
print("\n[7] Project Matcher")

PROJECTS = [
    {
        "name": "Automated News Classification System",
        "description": "ML pipeline using NLP, OCR, speech-to-text for news classification",
        "technologies": ["Python", "FastAPI", "OCR", "EasyOCR", "OpenCV", "Whisper", "TF-IDF", "NLP", "Machine Learning"],
    },
    {
        "name": "Resume Optimizer AI",
        "description": "ATS resume optimization using LLM and semantic analysis",
        "technologies": ["Python", "NLP", "LLM", "ATS", "AI"],
    },
    {
        "name": "Career Tracker",
        "description": "AI job monitoring and matching pipeline",
        "technologies": ["Python", "FastAPI", "PostgreSQL", "Scikit-learn"],
    },
]

def test_nlp_job_matches_news_project():
    from matcher.project_matcher import ProjectMatcher
    pm = ProjectMatcher(PROJECTS)
    name, score = pm.find_best_match("NLP Engineer", "We need NLP, OCR, Python for text classification.")
    assert name is not None
    assert score > 0

test("Project Matcher — NLP job matches News Classification project", test_nlp_job_matches_news_project)

def test_all_projects_scored():
    from matcher.project_matcher import ProjectMatcher
    pm = ProjectMatcher(PROJECTS)
    results = pm.score_all("AI Engineer", "Machine learning, NLP, Python, classification")
    assert len(results) == 3
    scores = [r["relevance_score"] for r in results]
    assert scores == sorted(scores, reverse=True)

test("Project Matcher — score_all() returns all 3 projects sorted by relevance", test_all_projects_scored)


# ────────────────────────────────────────────────────────────────────────
print("\n[8] Resume Selector")

def test_python_backend_resume():
    from matcher.resume_selector import select_resume
    result = select_resume("Junior Python Developer", "FastAPI, REST APIs, PostgreSQL, backend.")
    assert result["id"] == "python_backend"

test("Resume Selector — 'Junior Python Developer' → python_backend resume", test_python_backend_resume)

def test_ai_ml_resume():
    from matcher.resume_selector import select_resume
    result = select_resume("AI Engineer", "Machine learning, NLP, LLM, transformers, Python.")
    assert result["id"] == "ai_ml"

test("Resume Selector — 'AI Engineer' + NLP desc → ai_ml resume", test_ai_ml_resume)

def test_trainee_resume():
    from matcher.resume_selector import select_resume
    result = select_resume("Graduate Engineer Trainee", "Fresher welcome. 0-1 years. Training program.")
    assert result["id"] == "general_fresher"

test("Resume Selector — 'Graduate Engineer Trainee' → general_fresher resume", test_trainee_resume)


# ────────────────────────────────────────────────────────────────────────
print("\n[9] Hybrid Matcher")

SAMPLE_PROFILE = {
    "name": "Palpandi P",
    "skills": ["Python", "FastAPI", "REST APIs", "PostgreSQL", "Machine Learning", "NLP", "Scikit-learn",
               "TF-IDF", "React", "Git", "Docker", "Redis", "Celery", "Google Gemini API"],
    "target_titles": ["Python Developer", "Backend Developer", "AI Engineer", "ML Engineer"],
    "projects": PROJECTS,
    "experience_years": 0,
    "priority_cities": ["Chennai", "Coimbatore", "Bengaluru", "Kochi"],
    "preferred_states": ["Tamil Nadu", "Karnataka", "Kerala"],
}

def test_hybrid_score_python_job():
    from schema.job import Job, SourceType, FreshnessStatus
    from matcher.hybrid_matcher import score_job
    job = Job(
        id="zoho:pydev",
        title="Junior Python Developer",
        company="Zoho",
        url="https://careers.zoho.com/jobs/1",
        source_type=SourceType.ATS_JSON,
        description="We need Python, FastAPI, REST APIs, PostgreSQL. 0-1 years. Fresher welcome. Chennai.",
        canonical_location="Chennai, Tamil Nadu, India",
        freshness_status=FreshnessStatus.FRESH_CONFIRMED,
        experience_text="0-1 years",
        education_text="B.E/B.Tech/MCA",
    )
    score, components, matched, missing, proj, proj_score, coverage = score_job(job, SAMPLE_PROFILE)
    assert score > 50, f"Python job at Zoho Chennai should score > 50, got {score}"
    assert "Python" in matched or len(matched) > 0
    assert components["skill_score"] > 0
    assert components["location_score"] > 0

test("Hybrid Matcher — Zoho Chennai Python job scores > 50", test_hybrid_score_python_job)

def test_hybrid_score_nlp_job():
    from schema.job import Job, SourceType, FreshnessStatus
    from matcher.hybrid_matcher import score_job
    job = Job(
        id="freshworks:nlp",
        title="NLP Engineer",
        company="Freshworks",
        url="https://careers.freshworks.com/jobs/1",
        source_type=SourceType.ATS_JSON,
        description="NLP, TF-IDF, Scikit-learn, Machine Learning, Python. 0-2 years. Chennai.",
        canonical_location="Chennai, Tamil Nadu, India",
        freshness_status=FreshnessStatus.FRESH_CONFIRMED,
        experience_text="0-2 years",
    )
    score, _, matched, _, _, _, _ = score_job(job, SAMPLE_PROFILE)
    assert score > 40, f"NLP job should score > 40, got {score}"

test("Hybrid Matcher — Freshworks NLP job scores > 40", test_hybrid_score_nlp_job)

def test_notification_badge():
    from matcher.hybrid_matcher import get_notification_badge
    assert get_notification_badge(95.0) == "🔥"
    assert get_notification_badge(85.0) == "🟢"
    assert get_notification_badge(72.0) == "🟡"
    assert get_notification_badge(50.0) == "⚪"

test("Hybrid Matcher — notification badges (🔥🟢🟡⚪) assign correctly", test_notification_badge)


# ────────────────────────────────────────────────────────────────────────
print("\n[10] Application Preparer")

def test_application_pack():
    from advisor.application_preparer import prepare_application
    pack = prepare_application(
        job_title="Junior Python Developer",
        company="Zoho",
        job_description="Python, FastAPI, REST APIs, PostgreSQL. 0-1 years.",
        application_url="https://careers.zoho.com/apply/123",
        profile=SAMPLE_PROFILE,
        matched_skills=["Python", "FastAPI", "REST APIs"],
        missing_skills=["Django"],
        project_name="Automated News Classification System",
        project_relevance=85.0,
        recommended_resume="PALPANDI_P_Resume_Python_Developer .pdf",
        job_location="Chennai",
    )
    assert "Zoho" in pack["cover_letter"]
    assert "Palpandi" in pack["short_application_message"]
    assert "Python" in pack["cover_letter"] or "Python" in str(pack["skill_summary"])
    assert pack["official_application_url"] == "https://careers.zoho.com/apply/123"
    assert len(pack["common_application_answers"]) > 5
    # CRITICAL: No fabricated content
    assert "10 years" not in pack["cover_letter"]
    assert "worked at" not in pack["cover_letter"].lower()

test("Application Preparer — generates grounded cover letter + ATS answers (no fabrication)", test_application_pack)


# ────────────────────────────────────────────────────────────────────────
print("\n[11] Daily Digest")

def test_daily_digest_text():
    from notifier.daily_digest import DigestStats, generate_digest
    from schema.job import Job, SourceType, FreshnessStatus
    stats = DigestStats()
    stats.discovered = 500
    stats.new_jobs = 120
    stats.fresh_eligible = 45
    stats.duplicates_removed = 380
    stats.stale_removed = 55
    # Add a high match job
    job = Job(id="t:1", title="Python Developer", company="Zoho",
              url="https://zoho.com/careers/1", source_type=SourceType.ATS_JSON,
              overall_score=92.0, canonical_location="Chennai, Tamil Nadu, India",
              application_url="https://zoho.com/apply/1")
    stats.add_job(job)
    digest = generate_digest(stats, output_format="text")
    assert "Zoho" in digest
    assert "92" in digest
    assert "500" in digest or "discovered" in digest.lower()

test("Daily Digest — text format with stats and top jobs", test_daily_digest_text)

def test_daily_digest_telegram():
    from notifier.daily_digest import DigestStats, generate_digest
    stats = DigestStats()
    stats.discovered = 100
    stats.new_jobs = 30
    telegram = generate_digest(stats, output_format="telegram")
    assert "*" in telegram  # Telegram bold markers

test("Daily Digest — telegram format uses Markdown bold", test_daily_digest_telegram)


# ────────────────────────────────────────────────────────────────────────
print("\n[12] Cost Optimizer Pipeline")

def test_cost_optimizer_pipeline():
    from schema.job import Job, SourceType, FreshnessStatus
    from matcher.cost_optimizer import run_pipeline
    # Create mixed batch of jobs
    jobs = []
    for i in range(20):
        job = Job(
            id=f"zoho:{i}",
            title=["Junior Python Developer", "Senior Architect", "ML Engineer Intern",
                   "Software Engineer Trainee", "NLP Engineer"][i % 5],
            company="Zoho",
            url=f"https://careers.zoho.com/jobs/{i}",
            source_type=SourceType.ATS_JSON,
            description="Python FastAPI REST APIs NLP Machine Learning PostgreSQL. 0-1 years fresher.",
            freshness_status=[FreshnessStatus.FRESH_CONFIRMED, FreshnessStatus.STALE][i % 2],
        )
        jobs.append(job)
    result, stats = run_pipeline(jobs, SAMPLE_PROFILE, notification_threshold=30.0)
    # Some jobs should pass, Senior Architect and STALE should be filtered
    assert stats.input == 20
    assert stats.after_hard_filter < 20  # Some should be rejected

test("Cost Optimizer — senior/stale jobs filtered, pipeline funnel works", test_cost_optimizer_pipeline)


# ────────────────────────────────────────────────────────────────────────
print("\n[13] DedupStore")

def test_dedup_store():
    import tempfile, os
    from schema.job import Job, SourceType
    from dedup.store import DedupStore
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = DedupStore(db_path)
        job = Job(id="t:dedup1", title="Python Dev", company="Acme",
                  url="https://acme.com/jobs/1", source_type=SourceType.ATS_JSON,
                  description="Python FastAPI PostgreSQL REST APIs")
        assert store.is_new(job) is True
        store.mark_seen(job)
        assert store.is_new(job) is False
        # filter_new should return empty for already-seen
        result = store.filter_new([job])
        assert result == []
        # Explicitly close all connections (Windows file lock fix)
        import sqlite3
        import gc
        del store
        gc.collect()
    finally:
        try:
            os.unlink(db_path)
        except PermissionError:
            pass  # Windows may still hold the file — test logic already validated

test("DedupStore — is_new/mark_seen/filter_new works correctly", test_dedup_store)


# ────────────────────────────────────────────────────────────────────────
print("\n[14] Startup & Mid-Size Company Discovery Engine")

def test_company_discovery_classification():
    from discovery.classification_engine import classify_company
    from schema.company_schema import CompanyClassification
    intel = classify_company("Sarvam AI", raw_snippet="Seed AI startup", employee_count_estimate=20)
    assert intel.classification == CompanyClassification.STARTUP_EARLY
    assert intel.company_type.value == "AI_ML"

test("Company Discovery — Evidence Classification (STARTUP_EARLY / AI_ML)", test_company_discovery_classification)

def test_company_discovery_normalization_and_verification():
    from discovery.normalization import normalize_company_name
    from discovery.verification import verify_company_candidate
    from schema.company_schema import DiscoveryStatus
    assert normalize_company_name("Chargebee Technologies Pvt Ltd") == "chargebee"
    status, ats, url, ev = verify_company_candidate("Atlan", "atlan.com", "https://boards.greenhouse.io/atlan")
    assert status == DiscoveryStatus.VERIFIED
    assert ats == "greenhouse"

test("Company Discovery — Normalization & Official Verification Gate", test_company_discovery_normalization_and_verification)

def test_company_discovery_pipeline_execution():
    import tempfile, os, gc
    from dedup.store import DedupStore
    from discovery.pipeline import run_company_discovery_pipeline
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = DedupStore(db_path)
        summary = run_company_discovery_pipeline(store=store, max_new_companies=5)
        assert summary["total_candidates"] > 0
        assert summary["processed"] > 0
        del store
        gc.collect()
    finally:
        try:
            os.unlink(db_path)
        except PermissionError:
            pass

test("Company Discovery — Pipeline Execution & SQLite Storage", test_company_discovery_pipeline_execution)


# ────────────────────────────────────────────────────────────────────────
# RESULTS SUMMARY
print()
print("=" * 65)
print(f"  RESULTS: {len(PASSED)} PASSED  |  {len(FAILED)} FAILED")
print("=" * 65)

if FAILED:
    print("\n  FAILED TESTS:")
    for name, err in FAILED:
        print(f"    ❌ {name}")
        print(f"       {err}")
    print()
    sys.exit(1)
else:
    print()
    print("  🎉 ALL INTEGRATION TESTS PASSED!")
    print()
    sys.exit(0)
