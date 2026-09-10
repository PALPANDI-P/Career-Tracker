"""
Career Tracker — Candidate Project Matcher

Implements Section 17 of MASTER DEVELOPMENT PROMPT.

Indexes candidate projects and calculates relevance scores against
job descriptions. Detects when a job description aligns with the
candidate's existing project work.

Example:
  Job requires: NLP + OCR + Python
  Candidate project: Automated News Classification System
  -> Project relevance: 97%
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


def _project_to_text(project: dict[str, Any]) -> str:
    """Convert a candidate project dict to a searchable text document."""
    parts = [
        project.get("name", "") * 2,         # Name repeated for weight
        project.get("description", ""),
    ]
    technologies = project.get("technologies", [])
    if technologies:
        parts.extend(technologies * 2)        # Tech stack is very relevant
    return " ".join(str(p) for p in parts if p)


def _job_to_text(title: str, description: str) -> str:
    """Convert job info to a searchable text document."""
    return f"{title} {title} {description[:1500]}"  # Title repeated for weight


class ProjectMatcher:
    """
    Matches job descriptions against candidate projects using TF-IDF.

    Built once from the candidate profile and then used for all job queries.
    """

    def __init__(self, projects: list[dict[str, Any]]) -> None:
        """
        Initialize with candidate projects.

        Args:
            projects: List of project dicts with keys: name, description, technologies.
        """
        self.projects = projects
        self._project_texts = [_project_to_text(p) for p in projects]
        self._vectorizer: Optional[Any] = None
        self._project_matrix: Optional[Any] = None

        if projects and SKLEARN_AVAILABLE:
            self._build_index()

    def _build_index(self) -> None:
        """Build TF-IDF index from project texts."""
        try:
            self._vectorizer = TfidfVectorizer(
                stop_words="english",
                max_features=3000,
                ngram_range=(1, 2),
            )
            self._project_matrix = self._vectorizer.fit_transform(self._project_texts)
            logger.debug("Project matcher: indexed %d projects", len(self.projects))
        except Exception as exc:
            logger.warning("Could not build project TF-IDF index: %s", exc)
            self._vectorizer = None
            self._project_matrix = None

    def find_best_match(
        self,
        job_title: str,
        job_description: str,
    ) -> tuple[Optional[str], float]:
        """
        Find the most relevant candidate project for a given job.

        Args:
            job_title: Job title.
            job_description: Job description text.

        Returns:
            Tuple of (project_name, relevance_score_0_to_100).
            Returns (None, 0.0) if no good match is found.
        """
        if not self.projects:
            return None, 0.0

        job_text = _job_to_text(job_title, job_description)

        if SKLEARN_AVAILABLE and self._vectorizer is not None and self._project_matrix is not None:
            return self._tfidf_match(job_text)
        else:
            return self._keyword_match(job_text)

    def _tfidf_match(self, job_text: str) -> tuple[Optional[str], float]:
        """TF-IDF cosine similarity matching."""
        try:
            job_vector = self._vectorizer.transform([job_text])
            sims = cosine_similarity(job_vector, self._project_matrix).flatten()

            best_idx = int(sims.argmax())
            best_score = float(sims[best_idx])

            if best_score < 0.05:  # Below noise floor
                return None, 0.0

            project_name = self.projects[best_idx].get("name", "Unknown Project")
            # Scale to 0-100
            relevance = round(min(best_score * 2.5 * 100, 100.0), 1)
            logger.debug(
                "Project match: '%s' -> '%s' (%.1f%%)",
                job_text[:40],
                project_name,
                relevance,
            )
            return project_name, relevance

        except Exception as exc:
            logger.warning("TF-IDF project match failed: %s", exc)
            return self._keyword_match(job_text)

    def _keyword_match(self, job_text: str) -> tuple[Optional[str], float]:
        """Fallback keyword-overlap matching."""
        job_words = set(job_text.lower().split())

        best_name = None
        best_score = 0.0

        for project, text in zip(self.projects, self._project_texts):
            proj_words = set(text.lower().split())
            overlap = len(job_words & proj_words)
            if proj_words:
                score = overlap / len(proj_words)
                if score > best_score:
                    best_score = score
                    best_name = project.get("name")

        if best_score < 0.1:
            return None, 0.0

        return best_name, round(min(best_score * 200, 100.0), 1)

    def score_all(
        self,
        job_title: str,
        job_description: str,
    ) -> list[dict[str, Any]]:
        """
        Return relevance scores for all candidate projects.

        Useful for displaying project alignment in the dashboard.

        Returns:
            List of dicts: [{name, description, technologies, relevance_score}]
        """
        if not self.projects:
            return []

        job_text = _job_to_text(job_title, job_description)
        results = []

        if SKLEARN_AVAILABLE and self._vectorizer is not None and self._project_matrix is not None:
            try:
                job_vector = self._vectorizer.transform([job_text])
                sims = cosine_similarity(job_vector, self._project_matrix).flatten()
                for project, sim in zip(self.projects, sims):
                    results.append({
                        **project,
                        "relevance_score": round(min(float(sim) * 2.5 * 100, 100.0), 1),
                    })
            except Exception:
                results = [dict(**p, relevance_score=0.0) for p in self.projects]
        else:
            job_words = set(job_text.lower().split())
            for project, text in zip(self.projects, self._project_texts):
                proj_words = set(text.lower().split())
                overlap = len(job_words & proj_words)
                score = overlap / max(len(proj_words), 1)
                results.append({
                    **project,
                    "relevance_score": round(min(score * 200, 100.0), 1),
                })

        return sorted(results, key=lambda r: r["relevance_score"], reverse=True)
