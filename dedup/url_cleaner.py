"""
Career Tracker — URL Cleaner

Strips tracking parameters from job application URLs per Section 7 of
MASTER DEVELOPMENT PROMPT.

Removes: utm_source, utm_medium, utm_campaign, tracking IDs, session parameters.
Preserves: domain, path, essential query parameters (e.g., job ID).

Also provides URL canonicalization used by the duplicate detection engine.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

logger = logging.getLogger(__name__)

# Query parameters to strip (tracking / session / analytics)
STRIP_PARAMS: set[str] = {
    # UTM / Analytics
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "ga_source",
    "ga_medium",
    "ga_campaign",
    # Common tracking tokens
    "ref",
    "referrer",
    "source",
    "track",
    "tracking",
    "trackingid",
    "tracking_id",
    "click_id",
    "clickid",
    "fbclid",
    "gclid",
    "gclsrc",
    "msclkid",
    "dclid",
    "li_fat_id",
    "mc_eid",
    "mc_cid",
    "mkt_tok",
    # Session / ATS noise
    "sessionid",
    "session_id",
    "sid",
    "token",
    "auth_token",
    "csrftoken",
    "_ga",
    "_gl",
    # ATS-specific noise
    "ss_source",
    "gh_src",
    "lever_source",
    "sr_source",
}


def strip_tracking_params(url: str) -> str:
    """
    Remove known tracking and session parameters from a URL.

    Preserves all other query parameters (e.g., jobId, boardToken, etc.)
    which are essential for ATS deep links.

    Args:
        url: Raw URL string (possibly with tracking parameters).

    Returns:
        Cleaned URL with tracking parameters removed.
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Remove tracked params (case-insensitive key matching)
        cleaned_params: dict[str, list[str]] = {}
        stripped: list[str] = []

        for key, values in query_params.items():
            if key.lower() in STRIP_PARAMS:
                stripped.append(key)
            else:
                cleaned_params[key] = values

        if stripped:
            logger.debug("Stripped tracking params from URL: %s", stripped)

        # Rebuild URL with cleaned params
        clean_query = urlencode(cleaned_params, doseq=True)
        clean_parsed = parsed._replace(query=clean_query)
        return urlunparse(clean_parsed)

    except Exception as exc:
        logger.warning("Could not parse URL for param stripping: %s — %s", url, exc)
        return url


def canonicalize_url(url: str) -> str:
    """
    Produce a canonical (normalized) form of a job URL for deduplication.

    Operations:
      1. Lowercase scheme and netloc
      2. Strip trailing slashes from path
      3. Remove fragment (#)
      4. Strip tracking parameters
      5. Sort remaining query parameters for stable comparison

    Args:
        url: Raw URL string.

    Returns:
        Canonical URL string.
    """
    if not url:
        return url

    try:
        # First strip tracking params
        url = strip_tracking_params(url)
        parsed = urlparse(url)

        # Normalize scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Normalize path: strip trailing slashes
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        # Sort query params for stable ordering
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(sorted(query_params.items()), doseq=True)

        # Drop fragment entirely
        canonical = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))
        return canonical

    except Exception as exc:
        logger.warning("Could not canonicalize URL: %s — %s", url, exc)
        return url


def normalize_ats_url(url: str, ats_type: str) -> str:
    """
    ATS-specific URL normalization.

    Some ATS platforms add non-functional variation to their URLs.
    This function applies known ATS-specific normalization rules.

    Args:
        url: Raw URL from ATS.
        ats_type: ATS platform identifier (e.g., 'greenhouse', 'lever').

    Returns:
        Normalized URL.
    """
    clean = strip_tracking_params(url)

    if ats_type == "greenhouse":
        # Greenhouse sometimes appends /apply or #application — strip fragment
        parsed = urlparse(clean)
        if parsed.fragment in ("application", "apply"):
            clean = urlunparse(parsed._replace(fragment=""))

    elif ats_type == "lever":
        # Lever adds ?lever-source= tracking — already stripped above
        pass

    elif ats_type == "smartrecruiters":
        # SmartRecruiters sometimes appends ?lang= — keep it as it may affect page
        pass

    return canonicalize_url(clean)
