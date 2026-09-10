"""
Tests for the Fresher Classifier (Section 10 of MASTER DEVELOPMENT PROMPT).
"""
from __future__ import annotations

import pytest
from filter.fresher_classifier import (
    classify_fresher_eligibility,
    is_hard_reject,
    FresherEligibility,
)


class TestPositiveSignals:
    def test_fresher_in_title(self):
        eligibility, conf, signals = classify_fresher_eligibility(
            "We are hiring freshers for our Python team.",
            title="Fresher Python Developer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE
        assert conf > 0.5

    def test_get_acronym(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Graduate Engineer Trainee program for B.Tech/MCA graduates.",
            title="GET — Software Engineer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_zero_one_year_range(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Experience: 0-1 years required.",
            title="Junior Backend Developer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_entry_level_in_title(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Entry-level software engineer role at a product startup.",
            title="Entry-Level Software Engineer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_trainee_title(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Trainee program for recent graduates.",
            title="Software Engineer Trainee",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_intern(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Internship in AI/ML for MCA/B.Tech students.",
            title="ML Intern",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_campus_hire(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Campus hire program for 2025/2026 graduates.",
            title="Campus Hire — Python Developer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE

    def test_associate_software_engineer(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Associate Software Engineer role for fresh graduates.",
            title="Associate Software Engineer",
        )
        assert eligibility == FresherEligibility.ELIGIBLE


class TestNegativeSignals:
    def test_senior_title_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Senior Python Developer needed.",
            title="Senior Python Developer",
        )
        assert eligibility == FresherEligibility.INELIGIBLE

    def test_5_plus_years_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "We require 5+ years of experience in backend development.",
            title="Backend Developer",
        )
        assert eligibility == FresherEligibility.INELIGIBLE

    def test_manager_title_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Engineering Manager for the Platform team.",
            title="Engineering Manager",
        )
        assert eligibility == FresherEligibility.INELIGIBLE

    def test_director_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Director of Engineering at our HQ.",
            title="Director of Engineering",
        )
        assert eligibility == FresherEligibility.INELIGIBLE

    def test_vp_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "VP of Engineering role.",
            title="VP of Engineering",
        )
        assert eligibility == FresherEligibility.INELIGIBLE

    def test_principal_engineer_rejected(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Principal Engineer needed.",
            title="Principal Engineer",
        )
        assert eligibility == FresherEligibility.INELIGIBLE


class TestAmbiguousSignals:
    def test_two_years_preferred_is_lower_priority(self):
        """
        Section 10: '2 years preferred' should be LOWER_PRIORITY, not INELIGIBLE.
        """
        eligibility, _, _ = classify_fresher_eligibility(
            "Software Engineer — 2 years preferred. Freshers may also apply.",
            title="Software Engineer",
        )
        # Should NOT be INELIGIBLE — Section 10 explicitly states LOWER_PRIORITY
        assert eligibility in (FresherEligibility.LOWER_PRIORITY, FresherEligibility.ELIGIBLE)

    def test_1_to_3_years_lower_priority(self):
        eligibility, _, _ = classify_fresher_eligibility(
            "Looking for developer with 1-3 years experience.",
            title="Python Developer",
        )
        assert eligibility in (FresherEligibility.LOWER_PRIORITY, FresherEligibility.ELIGIBLE)

    def test_senior_in_description_only_not_title(self):
        """
        Section 9: Do not reject purely because description contains 'senior'.
        Only reject if the ROLE LEVEL is actually senior.
        """
        eligibility, _, _ = classify_fresher_eligibility(
            "You will work alongside senior engineers and learn from them.",
            title="Junior Python Developer",
        )
        # Title is junior, description mentions senior engineers (context)
        assert eligibility != FresherEligibility.INELIGIBLE


class TestIsHardReject:
    def test_senior_python_developer_is_hard_reject(self):
        assert is_hard_reject("Senior Python Developer") is True

    def test_junior_is_not_hard_reject(self):
        assert is_hard_reject("Junior Python Developer") is False

    def test_director_is_hard_reject(self):
        assert is_hard_reject("Director of Engineering") is True

    def test_software_engineer_is_not_hard_reject(self):
        assert is_hard_reject("Software Engineer") is False

    def test_associate_is_not_hard_reject(self):
        assert is_hard_reject("Associate Software Engineer") is False
