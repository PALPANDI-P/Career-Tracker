"""
Career Tracker — LLM Extraction Fallback

Used when unstructured HTML pages cannot be parsed structurally.
Delegates to the AI Engine for intelligent job extraction.
"""

from __future__ import annotations

from advisor.ai_engine import extract_jobs_llm
from schema.job import Job

__all__ = ["extract_jobs_llm"]
