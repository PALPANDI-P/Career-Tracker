from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from schema.job import Job, ScoredJob, SourceType, SeniorityLevel


def _make_scored_job(title: str = "Python Engineer") -> ScoredJob:
    job = Job(
        id=Job.make_id("Acme", content=title),
        title=title,
        company="Acme Inc",
        url="https://example.com/jobs/1",
        description="Build backend services with Python and PostgreSQL.",
        source_type=SourceType.ATS_JSON,
        seniority_level=SeniorityLevel.MID,
    )
    return ScoredJob(job=job, match_score=0.85, match_reason="Strong overlap: Python")


class TestSendAlert:
    @patch("notifier.telegram.requests.post")
    def test_send_alert_success(self, mock_post: MagicMock) -> None:
        from notifier.telegram import send_alert
        from config.settings import Settings
        s = Settings()
        s.telegram_bot_token = "fake-token"
        with patch("notifier.telegram.get_settings", return_value=s):
            send_alert("123", "test message")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["chat_id"] == "123"
        assert payload["text"] == "test message"

    def test_send_alert_raises_if_no_token(self) -> None:
        from config.settings import Settings
        s = Settings()
        s.telegram_bot_token = None
        s.telegram_chat_id = "123"
        with patch("notifier.telegram.get_settings", return_value=s):
            from notifier.telegram import send_alert
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
                send_alert("123", "test")


class TestDraftMatchNote:
    @patch("anthropic.Anthropic")
    def test_draft_note_with_llm(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="Python and AWS overlap makes this a strong match.")]
        mock_client.messages.create.return_value = mock_resp

        from config.settings import Settings
        s = Settings()
        s.anthropic_api_key = "fake-key"
        s.llm_model = "test-model"
        s.llm_max_tokens = 300
        s.telegram_bot_token = None

        scored = _make_scored_job("Python Engineer")
        with patch("notifier.message_agent.get_settings", return_value=s):
            from notifier.message_agent import draft_match_note
            note = draft_match_note(scored)
        assert "Python" in note

    def test_draft_note_falls_back_without_api_key(self) -> None:
        from config.settings import Settings
        s = Settings()
        s.anthropic_api_key = None
        s.telegram_bot_token = None
        s.llm_model = "test-model"
        s.llm_max_tokens = 300
        scored = _make_scored_job()
        scored.match_reason = "Skills overlap: Python, AWS"
        with patch("notifier.message_agent.get_settings", return_value=s):
            from notifier.message_agent import draft_match_note
            note = draft_match_note(scored)
        assert "Python" in note


class TestNotifyMatches:
    def test_no_chat_id_does_nothing(self) -> None:
        from config.settings import Settings
        s = Settings()
        s.telegram_chat_id = None
        s.telegram_bot_token = "fake-token"
        with patch("notifier.message_agent.get_settings", return_value=s):
            with patch("notifier.telegram.send_alert") as mock_send:
                from notifier import notify_matches
                notify_matches([_make_scored_job()])
                mock_send.assert_not_called()
