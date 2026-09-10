"""
Tests for Location Engine (Section 11) and Role Taxonomy (Section 12).
"""
from __future__ import annotations

import pytest
from filter.location_engine import normalize_location, calculate_location_weight
from filter.role_taxonomy import classify_role, TaxonomyCategory, TaxonomySubcategory, is_candidate_relevant_role


class TestLocationNormalization:
    def test_bangalore_canonical(self):
        loc = normalize_location("Bangalore")
        assert loc.city == "Bengaluru"
        assert loc.state == "Karnataka"

    def test_bengaluru_already_canonical(self):
        loc = normalize_location("Bengaluru")
        assert loc.city == "Bengaluru"

    def test_bangalore_karnataka_variant(self):
        loc = normalize_location("Bengaluru, Karnataka")
        assert loc.city == "Bengaluru"
        assert loc.state == "Karnataka"

    def test_chennai(self):
        loc = normalize_location("Chennai, Tamil Nadu")
        assert loc.city == "Chennai"
        assert loc.state == "Tamil Nadu"

    def test_coimbatore(self):
        loc = normalize_location("Coimbatore")
        assert loc.city == "Coimbatore"
        assert loc.state == "Tamil Nadu"

    def test_kochi(self):
        loc = normalize_location("Kochi, Kerala")
        assert loc.city == "Kochi"
        assert loc.state == "Kerala"

    def test_trivandrum(self):
        loc = normalize_location("Trivandrum")
        assert loc.city == "Thiruvananthapuram"
        assert loc.state == "Kerala"

    def test_remote(self):
        loc = normalize_location("Remote")
        assert loc.remote_type == "remote"

    def test_work_from_home(self):
        loc = normalize_location("Work from home")
        assert loc.remote_type == "remote"

    def test_hybrid(self):
        loc = normalize_location("Hybrid")
        assert loc.remote_type == "hybrid"

    def test_empty_location(self):
        loc = normalize_location(None)
        assert loc.city is None

    def test_mysore_canonical(self):
        loc = normalize_location("Mysore")
        assert loc.city == "Mysuru"
        assert loc.state == "Karnataka"


class TestLocationWeights:
    def test_preferred_city_weight(self):
        loc = normalize_location("Chennai")
        weight = calculate_location_weight(loc)
        assert weight == pytest.approx(1.0)

    def test_preferred_state_weight(self):
        loc = normalize_location("Trichy")  # Not in priority_cities but in Tamil Nadu
        weight = calculate_location_weight(loc)
        assert weight == pytest.approx(0.9)

    def test_remote_weight(self):
        loc = normalize_location("Remote")
        weight = calculate_location_weight(loc)
        assert weight == pytest.approx(0.9)

    def test_india_other_weight(self):
        loc = normalize_location("Mumbai")
        weight = calculate_location_weight(loc)
        assert weight == pytest.approx(0.5)

    def test_bangalore_preferred_city(self):
        loc = normalize_location("Bangalore")
        weight = calculate_location_weight(loc)
        assert weight == pytest.approx(1.0)


class TestRoleTaxonomy:
    def test_python_developer(self):
        cat, sub, conf = classify_role("Junior Python Developer")
        assert cat == TaxonomyCategory.SOFTWARE_DEVELOPMENT
        assert sub == TaxonomySubcategory.PYTHON

    def test_ai_ml_engineer(self):
        cat, sub, conf = classify_role("AI/ML Engineer")
        assert cat == TaxonomyCategory.AI_ML

    def test_generative_ai(self):
        cat, sub, conf = classify_role("Generative AI Developer")
        assert cat == TaxonomyCategory.AI_ML
        assert sub == TaxonomySubcategory.GENERATIVE_AI

    def test_nlp_engineer(self):
        cat, sub, conf = classify_role("NLP Engineer")
        assert cat == TaxonomyCategory.AI_ML
        assert sub == TaxonomySubcategory.NLP

    def test_backend_developer(self):
        cat, sub, conf = classify_role("Backend Developer")
        assert cat == TaxonomyCategory.SOFTWARE_DEVELOPMENT
        assert sub == TaxonomySubcategory.BACKEND

    def test_qa_engineer(self):
        cat, sub, conf = classify_role("QA Engineer")
        assert cat == TaxonomyCategory.TESTING

    def test_data_scientist(self):
        cat, sub, conf = classify_role("Data Scientist")
        assert cat == TaxonomyCategory.DATA

    def test_software_engineer_general(self):
        cat, sub, conf = classify_role("Software Engineer")
        assert cat == TaxonomyCategory.SOFTWARE_DEVELOPMENT

    def test_unrelated_role(self):
        cat, sub, conf = classify_role("Marketing Manager")
        assert cat == TaxonomyCategory.UNKNOWN

    def test_full_stack(self):
        cat, sub, conf = classify_role("Full Stack Developer")
        assert cat == TaxonomyCategory.SOFTWARE_DEVELOPMENT
        assert sub == TaxonomySubcategory.FULL_STACK

    def test_candidate_relevant_roles(self):
        assert is_candidate_relevant_role("Python Developer") is True
        assert is_candidate_relevant_role("AI Engineer") is True
        assert is_candidate_relevant_role("QA Engineer") is True
        assert is_candidate_relevant_role("Marketing Manager") is False
