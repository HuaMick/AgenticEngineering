"""Tests for the ntfy push notification client and watcher hook.

Tests send_ntfy(), notify_new_question(), and the _send_ntfy_if_configured()
hook used by the question watcher callback.
"""

import http.client
from dataclasses import dataclass
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from agenticcli.utils.ntfy import notify_new_question, send_ntfy


# --- Helpers ---

def _make_response(status=200):
    """Create a mock HTTP response."""
    resp = MagicMock()
    resp.getcode.return_value = status
    return resp


@dataclass
class FakeQuestion:
    """Minimal Question-like object for tests."""
    id: str = "Q-20260208-120000-abc1"
    text: str = "Should we use pytest or unittest?"
    severity: str = "medium"
    status: str = "pending"


# --- TestSendNtfy ---

class TestSendNtfy:
    """Tests for send_ntfy()."""

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_success(self, mock_urlopen):
        """Successful POST returns True and sends correct body/headers."""
        mock_urlopen.return_value = _make_response(200)

        result = send_ntfy("test-topic", "Test Title", "Hello world")

        assert result is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.sh/test-topic"
        assert req.data == b"Hello world"
        assert req.get_header("Title") == "Test Title"
        assert req.get_header("Priority") == "default"
        assert req.get_method() == "POST"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_failure_network(self, mock_urlopen):
        """URLError returns False without raising."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = send_ntfy("test-topic", "Title", "Body")

        assert result is False

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_failure_http(self, mock_urlopen):
        """HTTPError 403 returns False without raising."""
        mock_urlopen.side_effect = HTTPError(
            "https://ntfy.sh/test", 403, "Forbidden", {}, BytesIO(b"")
        )

        result = send_ntfy("test-topic", "Title", "Body")

        assert result is False

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_timeout(self, mock_urlopen):
        """Timeout (OSError) returns False without raising."""
        mock_urlopen.side_effect = OSError("timed out")

        result = send_ntfy("test-topic", "Title", "Body")

        assert result is False

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_custom_server(self, mock_urlopen):
        """Custom server URL is used in the request."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("my-topic", "Title", "Body", server="https://ntfy.example.com")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.example.com/my-topic"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_custom_server_trailing_slash(self, mock_urlopen):
        """Trailing slash on server URL is stripped."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("my-topic", "Title", "Body", server="https://ntfy.example.com/")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.example.com/my-topic"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_with_tags(self, mock_urlopen):
        """Tags header is comma-separated."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("topic", "Title", "Body", tags=["warning", "skull"])

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Tags") == "warning,skull"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_no_tags_header_when_none(self, mock_urlopen):
        """No Tags header when tags is None."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("topic", "Title", "Body", tags=None)

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Tags") is None

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_priority_header(self, mock_urlopen):
        """Priority header is set correctly."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("topic", "Title", "Body", priority="urgent")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Priority") == "urgent"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_send_timeout_parameter(self, mock_urlopen):
        """urlopen is called with 5-second timeout."""
        mock_urlopen.return_value = _make_response(200)

        send_ntfy("topic", "Title", "Body")

        assert mock_urlopen.call_args[1]["timeout"] == 5


# --- TestNotifyNewQuestion ---

class TestNotifyNewQuestion:
    """Tests for notify_new_question()."""

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_blocking_question(self, mock_send):
        """Blocking severity maps to urgent priority with warning tag."""
        mock_send.return_value = True
        q = FakeQuestion(severity="blocking")

        result = notify_new_question("topic", q)

        assert result is True
        mock_send.assert_called_once_with(
            topic="topic",
            title="New Question [BLOCKING]",
            message=q.text,
            priority="urgent",
            server="https://ntfy.sh",
            tags=["warning"],
        )

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_high_question(self, mock_send):
        """High severity maps to high priority with question tag."""
        mock_send.return_value = True
        q = FakeQuestion(severity="high")

        result = notify_new_question("topic", q)

        assert result is True
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["priority"] == "high"
        assert call_kwargs["tags"] == ["question"]
        assert call_kwargs["title"] == "New Question [HIGH]"

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_medium_question(self, mock_send):
        """Medium severity maps to default priority."""
        mock_send.return_value = True
        q = FakeQuestion(severity="medium")

        result = notify_new_question("topic", q)

        assert result is True
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["priority"] == "default"
        assert call_kwargs["tags"] == ["question"]

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_low_question(self, mock_send):
        """Low severity maps to default priority."""
        mock_send.return_value = True
        q = FakeQuestion(severity="low")

        result = notify_new_question("topic", q)

        assert result is True
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["priority"] == "default"

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_long_message_truncated(self, mock_send):
        """Text longer than 200 chars is truncated with ellipsis."""
        mock_send.return_value = True
        long_text = "A" * 300
        q = FakeQuestion(text=long_text)

        notify_new_question("topic", q)

        call_kwargs = mock_send.call_args[1]
        assert len(call_kwargs["message"]) == 203  # 200 + "..."
        assert call_kwargs["message"].endswith("...")

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_short_message_not_truncated(self, mock_send):
        """Text at exactly 200 chars is not truncated."""
        mock_send.return_value = True
        exact_text = "B" * 200
        q = FakeQuestion(text=exact_text)

        notify_new_question("topic", q)

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["message"] == exact_text

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_custom_server(self, mock_send):
        """Custom server URL is passed through."""
        mock_send.return_value = True
        q = FakeQuestion()

        notify_new_question("topic", q, server="https://custom.ntfy.io")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["server"] == "https://custom.ntfy.io"


# --- TestNtfyWatcherHook ---

class TestNtfyWatcherHook:
    """Tests for _send_ntfy_if_configured() watcher hook."""

    def setup_method(self):
        """Reset the dedup set before each test."""
        import agenticcli.commands.question as qmod

        qmod._ntfy_seen_question_ids.clear()

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_sends_notification_when_configured(self, mock_notify, tmp_path):
        """Sends ntfy when topic is configured in preferences."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        # Set up config directory with ntfy topic
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone", "server": "https://ntfy.sh"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        mock_notify.return_value = True
        questions = [FakeQuestion(id="Q-001")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)

        mock_notify.assert_called_once_with("my-phone", questions[0], "https://ntfy.sh")

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_skips_when_no_topic(self, mock_notify, tmp_path):
        """No notification when ntfy.topic is empty."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": ""}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        questions = [FakeQuestion(id="Q-001")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)

        mock_notify.assert_not_called()

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_skips_when_no_prefs_file(self, mock_notify, tmp_path):
        """No notification when preferences.yml doesn't exist."""
        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # No preferences.yml created

        questions = [FakeQuestion(id="Q-001")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)

        mock_notify.assert_not_called()

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_skips_when_disabled(self, mock_notify, tmp_path):
        """No notification when ntfy.enabled is False."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone", "enabled": False}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        questions = [FakeQuestion(id="Q-001")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)

        mock_notify.assert_not_called()

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_deduplicates_seen_questions(self, mock_notify, tmp_path):
        """Same question ID is not notified twice."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        mock_notify.return_value = True
        questions = [FakeQuestion(id="Q-001")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)
            _send_ntfy_if_configured(tmp_path, questions)

        # Only called once despite two invocations
        mock_notify.assert_called_once()

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_notifies_new_question_after_dedup(self, mock_notify, tmp_path):
        """New question IDs are notified even after dedup of earlier ones."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        mock_notify.return_value = True

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, [FakeQuestion(id="Q-001")])
            _send_ntfy_if_configured(tmp_path, [FakeQuestion(id="Q-001"), FakeQuestion(id="Q-002")])

        # Q-001 once, Q-002 once
        assert mock_notify.call_count == 2

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_network_error_does_not_crash(self, mock_notify, tmp_path):
        """Network errors are caught and do not propagate."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        mock_notify.side_effect = Exception("Network exploded")

        questions = [FakeQuestion(id="Q-999")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            # Should not raise
            _send_ntfy_if_configured(tmp_path, questions)

    @patch("agenticcli.utils.ntfy.notify_new_question")
    def test_uses_custom_server_from_config(self, mock_notify, tmp_path):
        """Custom server from preferences is passed to notify_new_question."""
        import yaml

        from agenticcli.commands.question import _send_ntfy_if_configured

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone", "server": "https://ntfy.example.com"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        mock_notify.return_value = True
        questions = [FakeQuestion(id="Q-010")]

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            _send_ntfy_if_configured(tmp_path, questions)

        mock_notify.assert_called_once_with("my-phone", questions[0], "https://ntfy.example.com")
