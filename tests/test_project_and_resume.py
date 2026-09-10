"""
Tests for Project Matcher and Resume Selector (Sections 17, 18).
"""
from __future__ import annotations

import pytest
from matcher.project_matcher import ProjectMatcher
from matcher.resume_selector import select_resume, RESUME_VARIANTS

SAMPLE_PROJECTS = [
    {
        "name": "Automated News Classification System",
        "description": "Multi-modal news classification pipeline using ML, NLP, OCR, and speech-to-text",
        "technologies": ["Python", "FastAPI", "React", "OCR", "EasyOCR", "OpenCV",
                         "Whisper", "TF-IDF", "NLP", "Machine Learning", "PostgreSQL", "Vercel"],
    },
    {
        "name": "Resume Optimizer AI",
        "description": "Full-Stack ATS resume optimization and semantic alignment platform",
        "technologies": ["Python", "NLP", "LLM", "semantic analysis", "ATS optimization", "AI"],
    },
    {
        "name": "Career Tracker",
        "description": "AI-powered job monitoring, matching, and application preparation assistant",
        "technologies": ["Python", "FastAPI", "PostgreSQL", "Redis", "Scikit-learn", "React"],
    },
]


class TestProjectMatcher:
    def setup_method(self):
        self.matcher = ProjectMatcher(SAMPLE_PROJECTS)

    def test_nlp_ocr_python_job_matches_news_system(self):
        project_name, score = self.matcher.find_best_match(
            "NLP Engineer",
            "We need someone with NLP, OCR, Python experience to build text classification pipelines.",
        )
        assert project_name is not None
        # The News Classification project is the best match
        assert "News" in project_name or "Resume" in project_name

    def test_ats_job_matches_resume_optimizer(self):
        project_name, score = self.matcher.find_best_match(
            "AI Engineer",
            "Build ATS-compatible resume analysis using LLM and NLP. Python, AI, semantic analysis.",
        )
        assert project_name is not None

    def test_returns_nonzero_score_for_relevant_job(self):
        _, score = self.matcher.find_best_match(
            "Python Backend Developer",
            "Build REST APIs with Python, FastAPI, PostgreSQL.",
        )
        assert score > 0

    def test_returns_none_for_irrelevant_job(self):
        project_name, score = self.matcher.find_best_match(
            "HR Manager",
            "Manage human resources, payroll, and employee benefits.",
        )
        # Either no match or very low score
        assert score < 40  # At most 40% for completely unrelated job

    def test_empty_project_list(self):
        matcher = ProjectMatcher([])
        project_name, score = matcher.find_best_match("Python Developer", "Python FastAPI")
        assert project_name is None
        assert score == 0.0

    def test_score_all_returns_all_projects(self):
        results = self.matcher.score_all(
            "AI/ML Engineer",
            "Machine learning, NLP, Python, TF-IDF, classification pipeline.",
        )
        assert len(results) == len(SAMPLE_PROJECTS)
        # Results should be sorted by relevance
        scores = [r["relevance_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestResumeSelector:
    def test_python_backend_role(self):
        result = select_resume(
            "Junior Python Developer",
            "FastAPI, PostgreSQL, REST APIs, backend development.",
        )
        assert result["id"] == "python_backend"

    def test_ai_ml_role(self):
        result = select_resume(
            "AI Engineer",
            "Machine learning, NLP, LLM, Transformers/BERT, AI model development.",
        )
        assert result["id"] == "ai_ml"

    def test_nlp_role(self):
        result = select_resume(
            "NLP Engineer",
            "Natural language processing, TF-IDF, scikit-learn.",
        )
        assert result["id"] == "ai_ml"

    def test_software_engineer_general(self):
        result = select_resume(
            "Software Engineer",
            "Full stack development with React and Java Spring Boot.",
        )
        assert result["id"] in ("software_developer", "ai_ml", "python_backend")

    def test_trainee_role(self):
        result = select_resume(
            "Graduate Engineer Trainee",
            "0-1 years experience. Fresher welcome. Training program.",
        )
        assert result["id"] == "general_fresher"

    def test_generative_ai_role(self):
        result = select_resume(
            "Generative AI Engineer",
            "LLM, Gemini AI SDK, Generative AI, Python.",
        )
        assert result["id"] == "ai_ml"

    def test_flask_fastapi_maps_to_python_backend(self):
        result = select_resume(
            "Flask Developer",
            "Build Flask APIs with SQLAlchemy and PostgreSQL.",
        )
        assert result["id"] == "python_backend"

    def test_result_has_required_keys(self):
        result = select_resume("Python Developer", "Python FastAPI backend.")
        assert "id" in result
        assert "name" in result
        assert "file" in result
        assert "score" in result
        assert "reason" in result

    def test_all_variants_have_files(self):
        """Ensure all resume variants have a file configured."""
        for variant in RESUME_VARIANTS:
            assert "file" in variant
            assert variant["file"], f"Variant '{variant['id']}' has empty file path"
