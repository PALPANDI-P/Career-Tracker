"""
Tests for the fetcher module.

Tests URL resolution, strategy dispatch, and error handling.
Network calls are not made — we test the logic, not the endpoints.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schema.job import ATSType, CompanyConfig
from fetcher.fetch import (
    FetchError,
    FetchResult,
    _get_ats_api_url,
    fetch_js,
    fetch_page,
)


class TestATSUrlResolution:
    """Tests for _get_ats_api_url — converting careers URLs to API endpoints."""

    def test_greenhouse_boards_url(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://boards.greenhouse.io/testco",
            ats_type=ATSType.GREENHOUSE,
        )
        url = _get_ats_api_url(config)
        assert url == "https://boards-api.greenhouse.io/v1/boards/testco/jobs?content=true"

    def test_greenhouse_custom_domain(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://careers.testco.com",
            ats_type=ATSType.GREENHOUSE,
        )
        url = _get_ats_api_url(config)
        assert url == "https://careers.testco.com/jobs.json"

    def test_lever_url(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://jobs.lever.co/testco",
            ats_type=ATSType.LEVER,
        )
        url = _get_ats_api_url(config)
        assert url == "https://api.lever.co/v0/postings/testco?mode=json"

    def test_smartrecruiters_url(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://jobs.smartrecruiters.com/TestCo",
            ats_type=ATSType.SMARTRECRUITERS,
        )
        url = _get_ats_api_url(config)
        assert url == "https://api.smartrecruiters.com/v1/companies/TestCo/postings"

    def test_unknown_ats_returns_original(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://careers.mystery.com",
            ats_type=ATSType.UNKNOWN,
        )
        url = _get_ats_api_url(config)
        assert url == "https://careers.mystery.com"

    def test_trailing_slash_stripped(self) -> None:
        """Trailing slash in input URL should not cause double slashes."""
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://boards.greenhouse.io/testco/",
            ats_type=ATSType.GREENHOUSE,
        )
        url = _get_ats_api_url(config)
        # Should not have double slashes (except in https://)
        assert "//" not in url.replace("https://", "")


class TestFetchResult:
    """Tests for the FetchResult data class."""

    def test_is_json_true(self) -> None:
        result = FetchResult(
            content='{"jobs": []}',
            status_code=200,
            content_type="application/json; charset=utf-8",
            url="https://example.com",
            company="TestCo",
        )
        assert result.is_json is True

    def test_is_json_false(self) -> None:
        result = FetchResult(
            content="<html>",
            status_code=200,
            content_type="text/html",
            url="https://example.com",
            company="TestCo",
        )
        assert result.is_json is False

    def test_repr(self) -> None:
        result = FetchResult(
            content="hello",
            status_code=200,
            content_type="text/html",
            url="https://example.com",
            company="TestCo",
        )
        repr_str = repr(result)
        assert "TestCo" in repr_str
        assert "200" in repr_str


class TestStrategyDispatch:
    """Tests for fetch strategy dispatch."""

    def test_disabled_company_raises(self) -> None:
        config = CompanyConfig(
            name="DisabledCo",
            careers_url="https://example.com",
            enabled=False,
        )
        with pytest.raises(FetchError, match="disabled"):
            fetch_page(config)

    @patch("fetcher.fetch.fetch_static")
    def test_js_strategy_fallback(self, mock_fetch_static: MagicMock) -> None:
        mock_fetch_static.return_value = FetchResult(
            content="<html>", status_code=200, content_type="text/html", url="https://example.com", company="JSCo"
        )
        config = CompanyConfig(
            name="JSCo",
            careers_url="https://example.com",
            fetch_strategy="js",
        )
        result = fetch_js(config)
        assert result.company == "JSCo"
        assert result.status_code == 200

    @patch("fetcher.fetch.fetch_static")
    def test_js_strategy_dispatch(self, mock_fetch_static: MagicMock) -> None:
        mock_fetch_static.return_value = FetchResult(
            content="<html>", status_code=200, content_type="text/html", url="https://example.com", company="JSCo"
        )
        config = CompanyConfig(
            name="JSCo",
            careers_url="https://example.com",
            fetch_strategy="js",
        )
        result = fetch_page(config)
        assert result.company == "JSCo"



class TestFetchError:
    """Tests for FetchError exception."""

    def test_error_attributes(self) -> None:
        err = FetchError("TestCo", "https://example.com", "timeout")
        assert err.company == "TestCo"
        assert err.url == "https://example.com"
        assert "timeout" in str(err)
        assert "TestCo" in str(err)


class TestFetchStatic:
    """Tests for fetch_static with mocked HTTP responses."""

    @patch("fetcher.fetch.requests.Session")
    def test_fetch_static_returns_content(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = '{"jobs": []}'
        mock_session.get.return_value = mock_resp

        config = CompanyConfig(
            name="TestCo",
            careers_url="https://boards.greenhouse.io/testco",
            ats_type=ATSType.GREENHOUSE,
        )
        from fetcher.fetch import fetch_static
        result = fetch_static(config)
        assert result.status_code == 200
        assert result.is_json is True
        assert "jobs" in result.content

    @patch("fetcher.fetch.requests.Session")
    def test_fetch_static_raises_on_404(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.reason = "Not Found"
        mock_resp.raise_for_status.side_effect = Exception("404")
        mock_session.get.return_value = mock_resp

        config = CompanyConfig(
            name="TestCo",
            careers_url="https://example.com",
            ats_type=ATSType.UNKNOWN,
        )
        from fetcher.fetch import fetch_static
        with pytest.raises(FetchError, match="HTTP"):
            fetch_static(config)
