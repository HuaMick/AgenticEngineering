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

from agenticcli.utils.ntfy import (
    notify_new_question,
    parse_question_id_from_message,
    poll_ntfy,
    send_ntfy,
)


@pytest.fixture(autouse=True)
def _block_real_ntfy():
    """Override conftest safety net — these tests manage ntfy mocking themselves."""
    yield


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
    suggested_answers: list = None


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
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["topic"] == "topic"
        assert call_kwargs["title"] == "New Question [BLOCKING]"
        assert call_kwargs["priority"] == "urgent"
        assert call_kwargs["tags"] == ["warning"]
        assert call_kwargs["message"].endswith(f"[QID: {q.id}]")
        assert q.text in call_kwargs["message"]

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
        """Text longer than 200 chars is truncated, then QID appended."""
        mock_send.return_value = True
        long_text = "A" * 300
        q = FakeQuestion(text=long_text)

        notify_new_question("topic", q)

        call_kwargs = mock_send.call_args[1]
        msg = call_kwargs["message"]
        # Text truncated to 203 chars (200 + "..."), then "\n\n[QID: ...]"
        assert msg.startswith("A" * 200 + "...")
        assert msg.endswith(f"[QID: {q.id}]")
        assert "\n\n[QID:" in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_short_message_not_truncated(self, mock_send):
        """Text at exactly 200 chars is not truncated, QID still appended."""
        mock_send.return_value = True
        exact_text = "B" * 200
        q = FakeQuestion(text=exact_text)

        notify_new_question("topic", q)

        call_kwargs = mock_send.call_args[1]
        msg = call_kwargs["message"]
        assert msg.startswith(exact_text)
        assert msg.endswith(f"[QID: {q.id}]")

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_message_includes_question_id(self, mock_send):
        """Message body includes QID footer in correct format."""
        mock_send.return_value = True
        q = FakeQuestion()

        notify_new_question("topic", q)

        call_kwargs = mock_send.call_args[1]
        msg = call_kwargs["message"]
        assert f"[QID: {q.id}]" in msg
        assert "\n\n[QID:" in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_custom_server(self, mock_send):
        """Custom server URL is passed through."""
        mock_send.return_value = True
        q = FakeQuestion()

        notify_new_question("topic", q, server="https://custom.ntfy.io")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["server"] == "https://custom.ntfy.io"


# --- TestMultiChoiceFormatting ---

class TestMultiChoiceFormatting:
    """Tests for multi-choice letter formatting in notify_new_question()."""

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_two_options_show_ab_format(self, mock_send):
        """Questions with 2 suggested answers show A) B) format."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="Choose framework",
            suggested_answers=["React", "Vue"],
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "A) React" in msg
        assert "B) Vue" in msg
        assert "C)" not in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_four_options_show_abcd_format(self, mock_send):
        """Questions with 4 suggested answers show A) B) C) D) format."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="Choose database",
            suggested_answers=["Redis", "PostgreSQL", "SQLite", "MongoDB"],
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "A) Redis" in msg
        assert "B) PostgreSQL" in msg
        assert "C) SQLite" in msg
        assert "D) MongoDB" in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_no_suggested_answers_no_letters(self, mock_send):
        """Questions without suggested_answers have no lettered options."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="What should we do?",
            suggested_answers=None,
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "A)" not in msg
        assert msg.startswith("What should we do?")

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_empty_suggested_answers_no_letters(self, mock_send):
        """Questions with empty suggested_answers list have no lettered options."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="What should we do?",
            suggested_answers=[],
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "A)" not in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_more_than_10_options_limited_to_aj(self, mock_send):
        """Questions with >10 options only show first 10 (A-J)."""
        mock_send.return_value = True
        options = [f"Option {i}" for i in range(15)]
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="Pick one",
            suggested_answers=options,
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "A) Option 0" in msg
        assert "J) Option 9" in msg
        # 11th option (K) should not appear
        assert "K)" not in msg
        assert "Option 10" not in msg

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_qid_footer_after_options(self, mock_send):
        """QID footer appears after lettered options."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="Choose database",
            suggested_answers=["Redis", "PostgreSQL", "SQLite"],
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "[QID: Q-20260210-123456-a1b2]" in msg
        # Options come before QID footer
        assert msg.index("A) Redis") < msg.index("[QID:")
        assert msg.index("C) SQLite") < msg.index("[QID:")

    @patch("agenticcli.utils.ntfy.send_ntfy")
    def test_letter_format_uses_uppercase(self, mock_send):
        """Letter labels use uppercase A-J."""
        mock_send.return_value = True
        q = FakeQuestion(
            id="Q-20260210-123456-a1b2",
            text="Pick",
            suggested_answers=["one", "two", "three"],
        )

        notify_new_question("topic", q)

        msg = mock_send.call_args[1]["message"]
        assert "\nA) one" in msg
        assert "\nB) two" in msg
        assert "\nC) three" in msg


# --- TestPollNtfy ---

class TestPollNtfy:
    """Tests for poll_ntfy()."""

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_success(self, mock_urlopen):
        """Successful poll returns list of parsed message dicts."""
        ndjson = (
            b'{"id":"msg1","time":1707400000,"message":"Hello"}\n'
            b'{"id":"msg2","time":1707400060,"message":"World"}\n'
        )
        mock_resp = MagicMock()
        mock_resp.read.return_value = ndjson
        mock_urlopen.return_value = mock_resp

        result = poll_ntfy("test-topic")

        assert len(result) == 2
        assert result[0]["id"] == "msg1"
        assert result[0]["message"] == "Hello"
        assert result[1]["id"] == "msg2"
        assert result[1]["message"] == "World"

        # Verify URL construction
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ntfy.sh/test-topic/json?since=30m&poll=1"

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_empty_response(self, mock_urlopen):
        """Empty body returns empty list."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        result = poll_ntfy("test-topic")

        assert result == []

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_network_error(self, mock_urlopen):
        """URLError returns empty list (no exception raised)."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = poll_ntfy("test-topic")

        assert result == []

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_http_error(self, mock_urlopen):
        """HTTPError returns empty list (no exception raised)."""
        mock_urlopen.side_effect = HTTPError(
            "https://ntfy.sh/test", 403, "Forbidden", {}, BytesIO(b"")
        )

        result = poll_ntfy("test-topic")

        assert result == []

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_invalid_json(self, mock_urlopen):
        """Malformed JSON returns empty list."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all\n"
        mock_urlopen.return_value = mock_resp

        result = poll_ntfy("test-topic")

        assert result == []

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_custom_server(self, mock_urlopen):
        """Custom server URL is used in the request."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        poll_ntfy("my-topic", server="https://custom.ntfy.io")

        req = mock_urlopen.call_args[0][0]
        assert req.full_url.startswith("https://custom.ntfy.io/my-topic/json")

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_since_parameter(self, mock_urlopen):
        """Since parameter is included in URL."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        poll_ntfy("topic", since="1707400000")

        req = mock_urlopen.call_args[0][0]
        assert "since=1707400000" in req.full_url

    @patch("agenticcli.utils.ntfy.urlopen")
    def test_poll_timeout_parameter(self, mock_urlopen):
        """urlopen is called with 5-second timeout."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        poll_ntfy("topic")

        assert mock_urlopen.call_args[1]["timeout"] == 5


# --- TestParseQuestionId ---

class TestParseQuestionId:
    """Tests for parse_question_id_from_message()."""

    def test_parse_valid_qid(self):
        """Extracts QID from standard format."""
        msg = "Some reply text\n\n[QID: Q-20260208-120000-abc1]"
        assert parse_question_id_from_message(msg) == "Q-20260208-120000-abc1"

    def test_parse_no_qid(self):
        """Returns None when no QID present."""
        assert parse_question_id_from_message("Just some random text") is None

    def test_parse_qid_in_quoted_reply(self):
        """Extracts QID from multiline quoted reply."""
        msg = "Yes, use pytest.\n\n> Should we use pytest?\n> [QID: Q-20260208-120000-abc1]"
        assert parse_question_id_from_message(msg) == "Q-20260208-120000-abc1"

    def test_parse_partial_match(self):
        """Returns None for invalid QID format."""
        assert parse_question_id_from_message("[QID: invalid-format]") is None

    def test_parse_qid_only(self):
        """Extracts QID when message is just the QID tag."""
        assert parse_question_id_from_message("[QID: Q-20260208-120000-abc1]") == "Q-20260208-120000-abc1"


# --- TestGetNtfyConfig ---

class TestGetNtfyConfig:
    """Tests for _get_ntfy_config()."""

    def test_returns_config_when_configured(self, tmp_path):
        """Returns topic and server when properly configured."""
        import yaml

        from agenticcli.commands.question import _get_ntfy_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone", "server": "https://ntfy.sh"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            result = _get_ntfy_config()

        assert result == {"topic": "my-phone", "server": "https://ntfy.sh"}

    def test_returns_none_when_no_prefs(self, tmp_path):
        """Returns None when preferences.yml doesn't exist."""
        from agenticcli.commands.question import _get_ntfy_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            result = _get_ntfy_config()

        assert result is None

    def test_returns_none_when_no_topic(self, tmp_path):
        """Returns None when ntfy.topic is empty."""
        import yaml

        from agenticcli.commands.question import _get_ntfy_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": ""}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            result = _get_ntfy_config()

        assert result is None

    def test_returns_none_when_disabled(self, tmp_path):
        """Returns None when ntfy.enabled is False."""
        import yaml

        from agenticcli.commands.question import _get_ntfy_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone", "enabled": False}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            result = _get_ntfy_config()

        assert result is None

    def test_default_server(self, tmp_path):
        """Server defaults to https://ntfy.sh when not specified."""
        import yaml

        from agenticcli.commands.question import _get_ntfy_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = {"ntfy": {"topic": "my-phone"}}
        (config_dir / "preferences.yml").write_text(yaml.dump(prefs))

        with patch("agenticcli.commands.config.get_config_dir", return_value=config_dir):
            result = _get_ntfy_config()

        assert result == {"topic": "my-phone", "server": "https://ntfy.sh"}


