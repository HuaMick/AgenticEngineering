"""NtfyQuestionAgent - sequential question delivery via ntfy.

Lightweight reply router for ntfy question interactions. Uses pattern matching
for intent detection (not an LLM agent). Maintains a current-question pointer
via NtfyQueueState for one-at-a-time question delivery.

Designed to be extended for voice input later - handle_reply(text) accepts any
text string from ntfy replies or future voice transcription.
"""

import dataclasses
import enum
import logging
import re
import time
from pathlib import Path

import yaml

from agenticcli.utils.ntfy import send_ntfy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue State
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class NtfyQueueState:
    """Persistent state for the ntfy question queue.

    Tracks which question is currently active (sent to user and awaiting reply),
    when it was sent, and how many questions have been answered this session.
    """

    current_question_id: str | None = None  # QID of question last sent to user
    sent_at: float | None = None            # Unix timestamp when sent
    answered_count: int = 0                  # Questions answered in this session


def _state_path(plan_path: Path) -> Path:
    """Return path to the ntfy queue state file."""
    return plan_path / "questions" / "ntfy_state.yml"


def load_state(plan_path: Path) -> NtfyQueueState:
    """Load queue state from disk, returning defaults if file is missing."""
    path = _state_path(plan_path)
    if not path.exists():
        return NtfyQueueState()
    data = yaml.safe_load(path.read_text()) or {}
    return NtfyQueueState(
        current_question_id=data.get("current_question_id"),
        sent_at=data.get("sent_at"),
        answered_count=data.get("answered_count", 0),
    )


def save_state(plan_path: Path, state: NtfyQueueState) -> None:
    """Persist queue state to disk atomically via tmp+rename."""
    path = _state_path(plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dataclasses.asdict(state)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yaml.dump(data, default_flow_style=False))
    tmp.rename(path)  # Atomic on same filesystem


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------

class Intent(enum.Enum):
    """Detected intent from an incoming ntfy reply."""

    ANSWER_LETTER = "answer_letter"       # Single letter A-J
    ANSWER_TEXT = "answer_text"           # Free-text answer
    NEXT_QUESTION = "next_question"       # 'next', 'next question', 'skip'
    LIST_QUESTIONS = "list_questions"     # 'list', 'how many'
    MORE_INFO = "more_info"              # 'discuss', 'more info', '?'


# Patterns checked in order - first match wins
_INTENT_PATTERNS: list[tuple[re.Pattern, Intent]] = [
    (re.compile(r'^(next|next question|skip)$', re.IGNORECASE), Intent.NEXT_QUESTION),
    (re.compile(r'^(list|how many|how many\?)$', re.IGNORECASE), Intent.LIST_QUESTIONS),
    (re.compile(r'^(discuss|more info|\?|details|explain)$', re.IGNORECASE), Intent.MORE_INFO),
    (re.compile(r'^[A-Ja-j]$'), Intent.ANSWER_LETTER),
]


def detect_intent(text: str) -> Intent:
    """Detect the user's intent from reply text via pattern matching.

    Args:
        text: Raw reply text from ntfy or voice transcription.

    Returns:
        Detected Intent enum value. Defaults to ANSWER_TEXT for
        unrecognised input (including empty strings).
    """
    text = text.strip()
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.match(text):
            return intent
    return Intent.ANSWER_TEXT  # Default: free-text answer


# ---------------------------------------------------------------------------
# NtfyQuestionAgent
# ---------------------------------------------------------------------------

class NtfyQuestionAgent:
    """Lightweight reply router for ntfy question interactions.

    Not an LLM agent - uses pattern matching for intent detection.
    Maintains current-question pointer via NtfyQueueState.
    Designed to be extended for voice input later.
    """

    def __init__(self, plan_path: Path, topic: str, server: str = "https://ntfy.sh"):
        self._plan_path = plan_path
        self._topic = topic
        self._server = server

    def handle_reply(self, text: str) -> str | None:
        """Route an incoming reply to the appropriate handler.

        Args:
            text: Raw reply text from ntfy or voice transcription.

        Returns:
            Response message to send back via ntfy, or None if no response needed.
        """
        intent = detect_intent(text)
        state = load_state(self._plan_path)

        if intent == Intent.NEXT_QUESTION:
            return self._handle_next(state)
        elif intent == Intent.LIST_QUESTIONS:
            return self._handle_list(state)
        elif intent == Intent.MORE_INFO:
            return self._handle_more_info(state)
        elif intent == Intent.ANSWER_LETTER:
            return self._handle_answer_letter(text.strip().upper(), state)
        else:  # ANSWER_TEXT
            return self._handle_answer_text(text.strip(), state)

    # ----- Next question -----

    def _handle_next(self, state: NtfyQueueState) -> str | None:
        """Send the next pending question to the user."""
        from agenticguidance.services.question import QuestionQueue

        service = QuestionQueue(self._plan_path)
        pending = service.list_pending_questions()

        # Sort by created_at for FIFO ordering
        pending.sort(key=lambda q: q.created_at)

        if not pending:
            msg = f"No more questions pending. {state.answered_count} answered this session."
            send_ntfy(self._topic, title="All Done", message=msg,
                      server=self._server, tags=["white_check_mark"])
            return msg

        question = pending[0]
        total = len(pending)

        # Format and send notification
        self._send_question_notification(question, 1, total)

        # Update state
        state.current_question_id = question.id
        state.sent_at = time.time()
        save_state(self._plan_path, state)

        return None  # Notification already sent via _send_question_notification

    # ----- Answer handlers -----

    def _handle_answer_letter(self, letter: str, state: NtfyQueueState) -> str | None:
        """Handle a single-letter answer (A-J) mapped to suggested answers."""
        if not state.current_question_id:
            return self._handle_answer_text(letter, state)

        from agenticguidance.services.question import QuestionQueue

        service = QuestionQueue(self._plan_path)
        question = service.get_question(state.current_question_id)

        if not question or not question.suggested_answers:
            return self._handle_answer_text(letter, state)

        letter_index = ord(letter) - ord('A')
        if 0 <= letter_index < len(question.suggested_answers):
            answer_text = question.suggested_answers[letter_index]
            logger.info("Mapped '%s' to: %s", letter, answer_text)
        else:
            answer_text = letter  # Invalid index, use literal

        return self._submit_answer(state, answer_text)

    def _handle_answer_text(self, text: str, state: NtfyQueueState) -> str | None:
        """Handle a free-text answer."""
        if not state.current_question_id:
            return "No question is active. Say 'next' to get a question."
        return self._submit_answer(state, text)

    def _submit_answer(self, state: NtfyQueueState, answer_text: str) -> str | None:
        """Submit answer for the current question and update state."""
        from agenticguidance.services.question import QuestionQueue

        service = QuestionQueue(self._plan_path)
        qid = state.current_question_id

        try:
            service.answer_question(
                qid,
                answer_text,
                answered_by="ntfy-reply",
            )
        except FileNotFoundError:
            logger.debug("Question %s already answered", qid)
            return "Question was already answered."
        except Exception as e:
            logger.warning("Failed to answer %s: %s", qid, e)
            return f"Error saving answer: {e}"

        # Update state
        state.answered_count += 1
        state.current_question_id = None
        state.sent_at = None
        save_state(self._plan_path, state)

        # Send confirmation
        msg = f"Answer saved: {answer_text[:80]}"
        send_ntfy(self._topic, title="Answer Received",
                  message=f"{msg}\n\nSay 'next' for next question.",
                  priority="low", server=self._server, tags=["white_check_mark"])

        logger.info("Answered %s via ntfy", qid)
        return msg

    # ----- Informational handlers -----

    def _handle_list(self, state: NtfyQueueState) -> str | None:
        """Reply with count and summary of pending questions."""
        from agenticguidance.services.question import QuestionQueue

        service = QuestionQueue(self._plan_path)
        pending = service.list_pending_questions()

        if not pending:
            msg = "No questions pending."
        else:
            blocking = [q for q in pending if q.severity == "blocking"]
            high = [q for q in pending if q.severity == "high"]
            msg = f"{len(pending)} questions pending"
            if blocking:
                msg += f" ({len(blocking)} blocking)"
            if high:
                msg += f" ({len(high)} high priority)"
            if state.current_question_id:
                msg += f"\nCurrent: {state.current_question_id}"
            msg += f"\n{state.answered_count} answered this session."

        send_ntfy(self._topic, title="Question Queue",
                  message=msg, priority="low",
                  server=self._server, tags=["clipboard"])
        return msg

    def _handle_more_info(self, state: NtfyQueueState) -> str | None:
        """Send extended context for the current question."""
        if not state.current_question_id:
            return "No question is active. Say 'next' to get a question."

        from agenticguidance.services.question import QuestionQueue

        service = QuestionQueue(self._plan_path)
        question = service.get_question(state.current_question_id)

        if not question:
            return "Current question not found."

        # Send context and full text
        msg = f"Question: {question.text}"
        if question.context:
            msg += f"\n\nContext: {question.context}"
        msg += f"\n\nSeverity: {question.severity}"
        msg += f"\nAsked by: {question.asked_by}"

        send_ntfy(self._topic, title="Question Details",
                  message=msg, priority="low",
                  server=self._server, tags=["mag"])
        return msg

    # ----- Notification formatting -----

    def _send_question_notification(self, question, position: int, total: int) -> bool:
        """Send a formatted question notification with position and hints.

        Args:
            question: Question instance.
            position: 1-based position in queue.
            total: Total pending questions.

        Returns:
            True if notification sent successfully.
        """
        severity = getattr(question, "severity", "medium").lower()
        title = f"Question {position} of {total} [{severity.upper()}]"

        text = getattr(question, "text", "")
        message = text[:200] + "..." if len(text) > 200 else text

        # Append lettered options if suggested_answers present
        suggested = getattr(question, "suggested_answers", None)
        if suggested and isinstance(suggested, list) and len(suggested) > 0:
            message += "\n"
            for i, answer in enumerate(suggested[:10]):
                letter = chr(ord('A') + i)
                message += f"\n{letter}) {answer}"

        # Append QID footer
        q_id = getattr(question, "id", "")
        if q_id:
            message += f"\n\n[QID: {q_id}]"

        # Append hint
        if suggested:
            message += "\n\nReply A/B/C or text. Say 'next' for next question."
        else:
            message += "\n\nReply with your answer. Say 'next' for next question."

        if severity == "blocking":
            priority = "urgent"
            tags = ["warning"]
        elif severity == "high":
            priority = "high"
            tags = ["question"]
        else:
            priority = "default"
            tags = ["question"]

        return send_ntfy(
            topic=self._topic, title=title, message=message,
            priority=priority, server=self._server, tags=tags,
        )
