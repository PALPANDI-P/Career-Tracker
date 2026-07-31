"""
Career Tracker — HTML Parsers

Placeholder for per-company custom CSS selector parsers (Phase 5).
For now, only a generic fallback is provided.
"""

from __future__ import annotations

from typing import Any

from schema.job import ATSType, CompanyConfig, Job, SourceType


def parse_html(company: CompanyConfig, raw_content: str | bytes) -> list[Job]:
    if company.custom_selectors:
        return _parse_custom_selectors(company, raw_content)
    return _parse_generic(raw_content, company)


def _parse_custom_selectors(company: CompanyConfig, raw_content: str | bytes) -> list[Job]:
    from bs4 import BeautifulSoup

    if isinstance(raw_content, bytes):
        raw_content = raw_content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(raw_content, "lxml")
    selectors = company.custom_selectors or {}
    title_sel = selectors.get("title", "h2, h3, .job-title")
    link_sel = selectors.get("link", "a")
    jobs: list[Job] = []

    cards = soup.select(selectors.get("card", "div, li, article"))

    for card in cards:
        title_tag = card.select_one(title_sel)
        link_tag = card.select_one(link_sel)
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        href = (link_tag or {}).get("href", "") if link_tag else ""
        if href and not href.startswith("http"):
            href = company.careers_url.rstrip("/") + "/" + href.lstrip("/")

        if not title or not href:
            continue

        description = card.get_text("\n", strip=True)

        job = Job(
            id=Job.make_id(company.name, content=title + description),
            title=title,
            company=company.name,
            url=href,
            description=description,
            source_type=SourceType.HTML_PARSED,
            ats_type=ATSType.CUSTOM,
        )
        jobs.append(job)

    return jobs


def _parse_generic(raw_content: str | bytes, company: CompanyConfig) -> list[Job]:
    from bs4 import BeautifulSoup

    if isinstance(raw_content, bytes):
        raw_content = raw_content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(raw_content, "lxml")
    jobs: list[Job] = []

    candidates = soup.select("a[href]")
    seen_ids: set[str] = set()

    for tag in candidates:
        href = tag.get("href", "")
        if not href or any(skip in href.lower() for skip in ("/jobs/", "/postings/", "/careers/")) is False:
            continue

        if tag.name != "a":
            continue

        job_id = href.split("/")[-1].split("?")[0]
        if not job_id or job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        title = tag.get_text(strip=True)
        if not title:
            continue

        if not href.startswith("http"):
            href = company.careers_url.rstrip("/") + "/" + href.lstrip("/")

        job = Job(
            id=Job.make_id(company.name, content=title),
            title=title,
            company=company.name,
            url=href,
            description=title,
            source_type=SourceType.HTML_PARSED,
            ats_type=ATSType.CUSTOM,
        )
        jobs.append(job)

    return jobs
