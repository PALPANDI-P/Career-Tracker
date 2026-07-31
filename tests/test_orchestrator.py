"""
Tests for the orchestrator pipeline.

All external modules are mocked — no real HTTP/LLM/Telegram calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from schema.job import Job, ScoredJob, SourceType, SeniorityLevel


def _make_job(title: str, company: str = "Acme") -> Job:
    return Job(
        id=Job.make_id(company, content=title),
        title=title,
        company=company,
        url=f"https://example.com/jobs/{title.lower().replace(' ', '-')}",
        description=f"Build things with Python. Title: {title}",
        source_type=SourceType.ATS_JSON,
        seniority_level=SeniorityLevel.MID,
    )


def _make_scored(title: str, score: float = 0.8) -> ScoredJob:
    return ScoredJob(
        job=_make_job(title),
        match_score=score,
        match_reason="Python overlap",
    )


class TestMain:
    """Tests for the main() orchestration function."""

    @patch("orchestrator.run.fetch_page")
    @patch("orchestrator.run.extract_jobs")
    @patch("orchestrator.run.filter_by_seniority")
    @patch("orchestrator.run.match_jobs")
    @patch("orchestrator.run.notify_matches")
    @patch("orchestrator.run.DedupStore")
    def test_main_orchestration(
        self,
        mock_store_cls: MagicMock,
        mock_notify: MagicMock,
        mock_match: MagicMock,
        mock_filter: MagicMock,
        mock_extract: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        from orchestrator.run import main

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.is_new.return_value = True

        job_a = _make_job("Python Engineer")
        mock_extract.return_value = [job_a]
        mock_filter.return_value = [job_a]
        mock_match.return_value = [_make_scored("Python Engineer", 0.9)]
        mock_fetch.return_value = MagicMock()

        from config.settings import Settings
        s = Settings()
        s.companies_dir = "/fake"
        s.target_seniority_levels = ["mid"]
        s.match_threshold_low = 0.55
        s.match_threshold_high = 0.80
        s.db_path = ":memory:"
        s.telegram_chat_id = "fake-chat-id"
        s.telegram_bot_token = "fake-token"

        companies_data = (
            "companies:\n"
            "  - name: Acme\n"
            "    careers_url: https://acme.com\n"
            "    ats_type: greenhouse\n"
            "    enabled: true\n"
        )

        sample_company = {
            "name": "Acme",
            "careers_url": "https://acme.com",
            "ats_type": "greenhouse",
            "enabled": True,
        }

        with patch("orchestrator.run.get_settings", return_value=s), \
             patch("orchestrator.run.load_companies", return_value=[sample_company]):
            result = main()

        mock_fetch.assert_called_once()
        mock_extract.assert_called_once()
        mock_store.record_run.assert_called_once()
        call_kwargs = mock_store.record_run.call_args.kwargs
        assert call_kwargs["companies_processed"] == 1
        assert call_kwargs["jobs_found"] == 1
        assert call_kwargs["jobs_new"] == 1
        mock_notify.assert_called_once()
        assert result == 0

    @patch("orchestrator.run.fetch_page")
    def test_main_handles_fetch_error(self, mock_fetch: MagicMock) -> None:
        from orchestrator.run import main
        from fetcher.fetch import FetchError

        mock_fetch.side_effect = FetchError("Acme", "https://acme.com", "timeout")

        from config.settings import Settings
        s = Settings()
        s.companies_dir = "/fake"
        s.target_seniority_levels = ["mid"]
        s.match_threshold_low = 0.55
        s.match_threshold_high = 0.80
        s.db_path = ":memory:"
        s.telegram_chat_id = None
        s.telegram_bot_token = None

        sample_company = {
            "name": "Acme",
            "careers_url": "https://acme.com",
            "ats_type": "greenhouse",
            "enabled": True,
        }

        with patch("orchestrator.run.get_settings", return_value=s), \
             patch("orchestrator.run.DedupStore"), \
             patch("orchestrator.run.load_companies", return_value=[sample_company]):
            result = main()

        assert result == 0
