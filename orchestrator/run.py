"""Career Tracker — Pipeline Orchestrator.

Updated to support:
- Multi-region company loading (tier1 + tamil_nadu + karnataka)
- India-specific fresher/training detection
- Dashboard notification push (color-coded)
- API pipeline integration
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from config.settings import get_settings
from dedup.store import DedupStore
from extractor import extract_jobs
from fetcher.fetch import FetchError, fetch_page
from filter import detect_job_category, detect_seniority, filter_by_seniority
from matcher import match_jobs
from notifier import notify_matches
from schema.job import CompanyConfig, Job, SeniorityLevel

logger = logging.getLogger(__name__)


def load_companies() -> list[dict]:
    """Load companies from all YAML files (tier1 + regional)."""
    settings = get_settings()
    companies_dir = Path(settings.companies_dir)
    all_companies: list[dict] = []

    yaml_files = [
        "tier1.yaml",
        "tamil_nadu.yaml",
        "karnataka.yaml",
        "kerala.yaml",
        "pan_india.yaml",
        "india_edge_hubs.yaml",
        "data_jobs_freshers.yaml",
    ]

    for yaml_file in yaml_files:
        filepath = companies_dir / yaml_file
        if not filepath.exists():
            logger.debug("Company file not found: %s", filepath)
            continue
        with open(filepath, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        companies = [c for c in data.get("companies", []) if c.get("enabled", True)]
        logger.info("Loaded %d companies from %s", len(companies), yaml_file)
        all_companies.extend(companies)

    logger.info("Total companies loaded: %d", len(all_companies))
    return all_companies


def build_company_config(co: dict) -> CompanyConfig:
    return CompanyConfig(
        name=co["name"],
        careers_url=co["careers_url"],
        fresher_careers_url=co.get("fresher_careers_url"),
        fresher_role_types=co.get("fresher_role_types", []),
        ats_type=co.get("ats_type", "unknown"),
        fetch_strategy=co.get("fetch_strategy", "static"),
        custom_selectors=co.get("custom_selectors"),
        rate_limit_seconds=co.get("rate_limit_seconds", 2.0),
        enabled=co.get("enabled", True),
    )


def _enrich_job_with_company_metadata(job: Job, co: dict) -> None:
    """Enrich a job with region/city/tags from the company config."""
    tags = co.get("tags", [])

    # Detect region from tags
    if "tamil-nadu" in tags:
        job.region = "tamil_nadu"
    elif "karnataka" in tags:
        job.region = "karnataka"
    else:
        job.region = "global"

    # Detect city from tags
    city_tags = ["chennai", "coimbatore", "madurai", "trichy",
                 "bangalore", "mysore", "hubli", "mangalore"]
    for tag in tags:
        if tag in city_tags:
            job.city = tag.title()
            break

    # Detect fresher category
    is_fresher, category = detect_job_category(job)
    job.is_fresher_eligible = is_fresher
    job.job_category = category

    # Add company tags to job
    job.tags = list(set(job.tags + tags))


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    companies = load_companies()
    store = DedupStore(settings.db_path)
    errors: list[str] = []
    total_jobs = 0
    new_jobs = 0
    jobs_all: list[Job] = []

    # Load profile for matching
    with open(settings.profile_path, "r", encoding="utf-8") as fp:
        profile = yaml.safe_load(fp) or {}

    for co in companies:
        config = build_company_config(co)
        try:
            logger.info("Fetching %s", config.name)
            fetch_result = fetch_page(config)
            jobs = extract_jobs(config, fetch_result)
            total_jobs += len(jobs)

            for job in jobs:
                # Detect seniority
                detected = detect_seniority(job.title)
                if detected is not SeniorityLevel.UNKNOWN:
                    job.seniority_level = detected

                # Enrich with company metadata (region, city, fresher detection)
                _enrich_job_with_company_metadata(job, co)

                if store.is_new(job):
                    store.mark_seen(job)
                    new_jobs += 1
                jobs_all.append(job)

        except FetchError as exc:
            errors.append(f"{config.name}: {exc}")
            logger.error("Fetch failed for %s: %s", config.name, exc)
        except Exception as exc:
            errors.append(f"{config.name}: {exc}")
            logger.exception("Unexpected error for %s", config.name)

    # Filter by seniority
    filtered = filter_by_seniority(jobs_all, settings.target_seniority_levels)

    # Score matches
    scored = match_jobs(filtered, profile)
    matched = [s for s in scored if s.match_score >= settings.match_threshold_low]

    # ── Push to dashboard notifications ──────────────
    try:
        from dashboard.app import (
            determine_priority,
            push_notification,
            save_notification,
        )

        for scored_job in matched:
            priority = determine_priority(
                scored_job.match_score,
                scored_job.job.is_fresher_eligible,
                scored_job.job.job_category.value,
            )
            scored_job.job.notification_priority = priority

            notification = {
                "type": "new_job",
                "job_id": scored_job.job.id,
                "title": scored_job.job.title,
                "company": scored_job.job.company,
                "location": scored_job.job.location,
                "url": str(scored_job.job.url),
                "match_score": scored_job.match_score,
                "match_reason": scored_job.match_reason,
                "priority": priority,
                "category": scored_job.job.job_category.value,
                "region": scored_job.job.region or "global",
                "city": scored_job.job.city,
                "is_fresher_eligible": scored_job.job.is_fresher_eligible,
            }

            save_notification(settings.db_path, notification)
            push_notification(notification)

    except ImportError:
        logger.debug("Dashboard not available — skipping notification push")
    except Exception as e:
        logger.warning("Failed to push dashboard notifications: %s", e)

    # ── Send to Telegram & Email ─────────────────────
    notify_matches(matched)
    try:
        from notifier.email_notifier import send_email_digest
        send_email_digest(matched, settings.email_to)
    except Exception as e:
        logger.warning("Email notification failed: %s", e)

    # ── Record run ───────────────────────────────────
    store.record_run(
        companies_processed=len(companies),
        jobs_found=total_jobs,
        jobs_new=new_jobs,
        errors=errors,
    )

    logger.info(
        "Pipeline complete: %d companies, %d jobs, %d new, %d matches",
        len(companies),
        total_jobs,
        new_jobs,
        len(matched),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
