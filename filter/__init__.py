"""Career Tracker — Filter package."""

from __future__ import annotations

from filter.seniority_filter import (
    detect_fresher_category,
    detect_job_category,
    detect_seniority,
    filter_by_seniority,
)

__all__ = [
    "detect_fresher_category",
    "detect_job_category",
    "detect_seniority",
    "filter_by_seniority",
]

