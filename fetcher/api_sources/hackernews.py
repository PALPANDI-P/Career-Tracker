"""
Career Tracker — HackerNews Who's Hiring Fetcher

Free, no API key needed.
Source: HackerNews "Ask HN: Who is hiring?" monthly threads.
Uses the Algolia HN Search API.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

# Algolia HN Search API
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HackerNewsFetcher:
    """Fetch jobs from HackerNews 'Who is Hiring?' threads."""

    name = "hackernews"

    @property
    def is_configured(self) -> bool:
        return True  # Free, no API key

    def fetch_jobs(
        self,
        location: str = "",
        keywords: str = "",
    ) -> list[Job]:
        """Fetch the latest 'Who is Hiring?' thread and parse job postings."""
        # Find the latest "Who is hiring?" thread
        thread_id = self._find_latest_thread()
        if not thread_id:
            logger.warning("Could not find latest HN hiring thread")
            return []

        # Fetch comments from the thread
        comments = self._fetch_comments(thread_id)
        return self._parse_comments(comments, location, keywords)

    def _find_latest_thread(self) -> int | None:
        """Find the latest 'Ask HN: Who is hiring?' thread."""
        params = {
            "query": "Ask HN: Who is hiring?",
            "tags": "ask_hn",
            "hitsPerPage": 1,
        }
        try:
            resp = requests.get(HN_SEARCH_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            if hits:
                return int(hits[0]["objectID"])
        except Exception as e:
            logger.error("Failed to find HN hiring thread: %s", e)
        return None

    def _fetch_comments(self, thread_id: int, max_comments: int = 100) -> list[dict]:
        """Fetch top-level comments from a HN thread."""
        try:
            url = HN_ITEM_URL.format(thread_id)
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            thread = resp.json()
            kid_ids = thread.get("kids", [])[:max_comments]
        except Exception as e:
            logger.error("Failed to fetch HN thread: %s", e)
            return []

        comments = []
        for kid_id in kid_ids[:50]:  # Limit to 50 to avoid rate limits
            try:
                url = HN_ITEM_URL.format(kid_id)
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                comment = resp.json()
                if comment and comment.get("text"):
                    comments.append(comment)
            except Exception:
                continue

        return comments

    def _parse_comments(
        self, comments: list[dict], location: str, keywords: str
    ) -> list[Job]:
        """Parse HN comments into Job objects."""
        jobs: list[Job] = []

        for comment in comments:
            text = comment.get("text", "")
            if not text:
                continue

            # Clean HTML
            clean_text = re.sub(r"<[^>]+>", " ", text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            # Try to extract company and title from first line
            lines = clean_text.split("|")
            if len(lines) < 2:
                continue

            company = lines[0].strip()
            title_parts = [p.strip() for p in lines[1:3]]
            title = " | ".join(title_parts) if title_parts else "Engineering Role"

            # Filter by location if specified
            if location:
                text_lower = clean_text.lower()
                loc_lower = location.lower()
                if loc_lower not in text_lower and "remote" not in text_lower:
                    continue

            # Filter by keywords if specified
            if keywords:
                text_lower = clean_text.lower()
                if not any(kw.lower() in text_lower for kw in keywords.split()):
                    continue

            try:
                job = Job(
                    id=Job.make_id("hackernews", str(comment.get("id", ""))),
                    external_id=str(comment.get("id", "")),
                    title=title[:200],
                    company=company[:100],
                    location="See description",
                    url=f"https://news.ycombinator.com/item?id={comment.get('id', '')}",
                    description=clean_text[:2000],
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=["hackernews", "api-source", "who-is-hiring"],
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse HN comment as job: %s", e)
                continue

        logger.info("HackerNews: parsed %d jobs from hiring thread", len(jobs))
        return jobs


def fetch_hackernews_jobs(location: str = "", keywords: str = "") -> list[Job]:
    """Module-level helper to fetch HackerNews jobs."""
    fetcher = HackerNewsFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

