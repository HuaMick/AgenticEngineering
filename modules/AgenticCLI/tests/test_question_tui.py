"""Tests for QuestionTUI component.

Tests the question scanning, severity ordering, and rendering of
the terminal UI for pending agent questions.
"""

import time
from pathlib import Path

import pytest
import yaml

from agenticcli.tui.question_tui import QuestionTUI, _SEVERITY_ORDER


def _make_question_yaml(
    question_id: str = "Q001",
    text: str = "Should we proceed?",
    severity: str = "medium",
    status: str = "pending",
    asked_by: str = "test-agent",
    created_at: float | None = None,
) -> str:
    """Build a minimal question YAML string."""
    data = {
        "id": question_id,
        "text": text,
        "severity": severity,
        "status": status,
        "asked_by": asked_by,
        "created_at": created_at or time.time(),
    }
    return yaml.dump(data, default_flow_style=False)


def _create_pending_question(
    tmp_path: Path,
    plan_name: str,
    filename: str,
    **kwargs,
) -> Path:
    """Create a pending question YAML file under the standard plan directory layout."""
    pending_dir = tmp_path / "docs" / "epics" / "live" / plan_name / "questions" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    question_file = pending_dir / filename
    question_file.write_text(_make_question_yaml(**kwargs), encoding="utf-8")
    return question_file


def _cell(table, col_index: int, row_index: int) -> str:
    """Return the raw markup cell value for a given column and row index."""
    return list(table.columns[col_index]._cells)[row_index]


# ---------------------------------------------------------------------------
# _build_questions_table tests
# ---------------------------------------------------------------------------


class TestBuildQuestionsTable:
    """Tests for QuestionTUI._build_questions_table() method."""

    def test_build_table_empty_plans(self, tmp_path: Path):
        """No live plans dir -> table has one row with 'No pending questions' message."""
        # tmp_path has no docs/epics/live directory at all
        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        table = tui._build_questions_table(width=80)

        # Should have exactly the three standard columns
        assert len(table.columns) == 3
        assert table.columns[0].header == "Plan"
        assert table.columns[1].header == "Severity"
        assert table.columns[2].header == "Question"

        # Should have exactly one row containing the empty-state message
        assert table.row_count == 1
        question_cell = _cell(table, 2, 0)
        assert "No pending questions" in question_cell

    def test_build_table_no_pending_questions(self, tmp_path: Path):
        """Live plan dir exists but no questions/pending/*.yml files -> 'No pending questions' row."""
        # Create the plan directory but no question files inside it
        plan_dir = tmp_path / "docs" / "epics" / "live" / "260220XX_my_plan"
        plan_dir.mkdir(parents=True)

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        table = tui._build_questions_table(width=80)

        assert table.row_count == 1
        question_cell = _cell(table, 2, 0)
        assert "No pending questions" in question_cell

    def test_build_table_one_question(self, tmp_path: Path):
        """One pending question YAML -> table has one data row with correct plan, severity, question text."""
        _create_pending_question(
            tmp_path,
            plan_name="test_plan",
            filename="Q-test.yml",
            question_id="Q-test-001",
            text="What framework should we use?",
            severity="high",
            status="pending",
            asked_by="agent",
            created_at=1708000000,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 1

        table = tui._build_questions_table(width=80)

        # Exactly one data row (not an empty-state row)
        assert table.row_count == 1

        # Plan column contains the plan name (may be truncated)
        plan_cell = _cell(table, 0, 0)
        assert "test_plan" in plan_cell

        # Severity column contains "HIGH"
        sev_cell = _cell(table, 1, 0)
        assert "HIGH" in sev_cell

        # Question column contains the question text
        q_cell = _cell(table, 2, 0)
        assert "What framework should we use?" in q_cell

    def test_build_table_multi_plan(self, tmp_path: Path):
        """Two plans each with one pending question -> table has two rows."""
        _create_pending_question(
            tmp_path,
            plan_name="plan_alpha",
            filename="q1.yml",
            question_id="Q001",
            text="Alpha question?",
            severity="medium",
            created_at=1708000000,
        )
        _create_pending_question(
            tmp_path,
            plan_name="plan_beta",
            filename="q2.yml",
            question_id="Q002",
            text="Beta question?",
            severity="medium",
            created_at=1708000001,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 2

        table = tui._build_questions_table(width=80)

        # Two data rows, one per plan
        assert table.row_count == 2

        # Both plan names should appear somewhere in the plan column cells
        plan_cells = [_cell(table, 0, i) for i in range(2)]
        all_plan_text = " ".join(plan_cells)
        assert "plan_alpha" in all_plan_text
        assert "plan_beta" in all_plan_text

    def test_build_table_severity_ordering(self, tmp_path: Path):
        """Critical (blocking) question appears before low -> rows ordered by severity."""
        base_time = 1700000000.0

        # Create a low-severity question first (to ensure ordering is by severity, not insertion)
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_low.yml",
            question_id="Q_LOW",
            text="Low priority question?",
            severity="low",
            created_at=base_time,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_critical.yml",
            question_id="Q_CRITICAL",
            text="Critical blocking question!",
            severity="blocking",
            created_at=base_time + 1,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 2

        table = tui._build_questions_table(width=80)

        assert table.row_count == 2

        # Row 0 should be the blocking/critical question
        sev_cell_row0 = _cell(table, 1, 0)
        assert "BLOCKING" in sev_cell_row0

        # Row 1 should be the low question
        sev_cell_row1 = _cell(table, 1, 1)
        assert "LOW" in sev_cell_row1

        # Question text ordering sanity check
        q_cell_row0 = _cell(table, 2, 0)
        assert "Critical blocking question!" in q_cell_row0

        q_cell_row1 = _cell(table, 2, 1)
        assert "Low priority question?" in q_cell_row1


# ---------------------------------------------------------------------------
# _refresh_questions tests
# ---------------------------------------------------------------------------


class TestRefreshQuestionsEmptyPlans:
    """Tests for when no plans directory exists."""

    def test_build_table_empty_plans(self, tmp_path: Path):
        """No live plans dir -> empty questions list."""
        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert tui.questions == []
        assert tui.cursor == 0


class TestRefreshQuestionsNoPending:
    """Tests for when plan dirs exist but have no pending questions."""

    def test_build_table_no_pending_questions(self, tmp_path: Path):
        """Live plan dir exists but no questions/pending/*.yml files -> empty list."""
        plan_dir = tmp_path / "docs" / "epics" / "live" / "260220XX_my_plan"
        plan_dir.mkdir(parents=True)

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert tui.questions == []
        assert tui.cursor == 0

    def test_no_pending_when_only_deferred(self, tmp_path: Path):
        """Questions with non-pending status are excluded."""
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q1.yml",
            question_id="Q001",
            status="deferred",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert tui.questions == []


class TestRefreshQuestionsOneQuestion:
    """Tests for a single pending question."""

    def test_build_table_one_question(self, tmp_path: Path):
        """One pending question YAML -> one entry with correct plan name and data."""
        _create_pending_question(
            tmp_path,
            plan_name="260220AB_auth_feature",
            filename="q1.yml",
            question_id="Q001",
            text="Should we use JWT?",
            severity="high",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 1

        entry = tui.questions[0]
        assert entry["plan_name"] == "260220AB_auth_feature"
        assert entry["question_data"]["id"] == "Q001"
        assert entry["question_data"]["text"] == "Should we use JWT?"
        assert entry["question_data"]["severity"] == "high"


class TestRefreshQuestionsMultiPlan:
    """Tests for questions across multiple plans."""

    def test_build_table_multi_plan(self, tmp_path: Path):
        """Two plans each with one pending question -> two entries."""
        _create_pending_question(
            tmp_path,
            plan_name="260220AA_plan_one",
            filename="q1.yml",
            question_id="Q001",
            text="First question?",
            severity="medium",
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220BB_plan_two",
            filename="q2.yml",
            question_id="Q002",
            text="Second question?",
            severity="high",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 2
        plan_names = {q["plan_name"] for q in tui.questions}
        assert plan_names == {"260220AA_plan_one", "260220BB_plan_two"}


class TestSeverityOrdering:
    """Tests for severity-based ordering of questions."""

    def test_build_table_severity_ordering(self, tmp_path: Path):
        """Questions are ordered by severity: blocking > high > medium > low."""
        base_time = 1700000000.0

        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_low.yml",
            question_id="Q_LOW",
            text="Low priority question?",
            severity="low",
            created_at=base_time,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_blocking.yml",
            question_id="Q_BLOCKING",
            text="Blocking question!",
            severity="blocking",
            created_at=base_time + 1,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_high.yml",
            question_id="Q_HIGH",
            text="High priority question?",
            severity="high",
            created_at=base_time + 2,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_medium.yml",
            question_id="Q_MEDIUM",
            text="Medium priority question?",
            severity="medium",
            created_at=base_time + 3,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 4

        severities = [q["question_data"]["severity"] for q in tui.questions]
        assert severities == ["blocking", "high", "medium", "low"]

    def test_same_severity_ordered_by_created_at(self, tmp_path: Path):
        """Within the same severity level, questions are ordered by created_at ascending."""
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_newer.yml",
            question_id="Q_NEWER",
            text="Newer question?",
            severity="high",
            created_at=1700000002.0,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q_older.yml",
            question_id="Q_OLDER",
            text="Older question?",
            severity="high",
            created_at=1700000001.0,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert len(tui.questions) == 2
        ids = [q["question_data"]["id"] for q in tui.questions]
        assert ids == ["Q_OLDER", "Q_NEWER"]


class TestCursorPreservation:
    """Tests for cursor position management across refreshes."""

    def test_cursor_preserved_on_refresh(self, tmp_path: Path):
        """Cursor stays on the same question ID after a refresh."""
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q1.yml",
            question_id="Q001",
            severity="high",
            created_at=1700000001.0,
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q2.yml",
            question_id="Q002",
            severity="medium",
            created_at=1700000002.0,
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        # Move cursor to the second question
        tui.cursor = 1
        assert tui.questions[tui.cursor]["question_data"]["id"] == "Q002"

        # Refresh - cursor should stay on Q002
        tui._refresh_questions()
        assert tui.cursor == 1
        assert tui.questions[tui.cursor]["question_data"]["id"] == "Q002"

    def test_cursor_clamped_when_question_removed(self, tmp_path: Path):
        """Cursor is clamped when the selected question disappears."""
        _create_pending_question(
            tmp_path,
            plan_name="260220XX_plan",
            filename="q1.yml",
            question_id="Q001",
            severity="high",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()
        assert len(tui.questions) == 1

        # Now remove all questions
        pending_dir = tmp_path / "docs" / "epics" / "live" / "260220XX_plan" / "questions" / "pending"
        for f in pending_dir.glob("*.yml"):
            f.unlink()

        tui._refresh_questions()
        assert tui.questions == []
        assert tui.cursor == 0


class TestRenderEmptyState:
    """Tests for rendering when there are no questions."""

    def test_render_empty_state_output(self, tmp_path: Path):
        """Empty state renders the 'No pending questions' message."""
        from io import StringIO
        from rich.console import Console

        tui = QuestionTUI(repo_root=tmp_path)
        tui.console = Console(file=StringIO(), width=80, no_color=True, highlight=False)
        tui._refresh_questions()
        tui._render()

        output = tui.console.file.getvalue()
        assert "No pending questions" in output
        assert "PENDING QUESTIONS (0)" in output


class TestRenderWithQuestions:
    """Tests for rendering with question data present."""

    def test_render_shows_question_data(self, tmp_path: Path):
        """Rendered output includes plan name, severity, and question text."""
        from io import StringIO
        from rich.console import Console

        _create_pending_question(
            tmp_path,
            plan_name="260220AB_my_plan",
            filename="q1.yml",
            question_id="Q001",
            text="Is this working?",
            severity="high",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui.console = Console(file=StringIO(), width=100, no_color=True, highlight=False)
        tui._refresh_questions()
        tui._render()

        output = tui.console.file.getvalue()
        assert "PENDING QUESTIONS (1)" in output
        # Plan name may be truncated to fit column width
        assert "260220AB_my_pl" in output
        assert "HIGH" in output
        assert "Is this working?" in output

    def test_render_multi_question_count(self, tmp_path: Path):
        """Header shows correct question count with multiple questions."""
        from io import StringIO
        from rich.console import Console

        _create_pending_question(
            tmp_path,
            plan_name="260220AA_plan",
            filename="q1.yml",
            question_id="Q001",
            severity="medium",
        )
        _create_pending_question(
            tmp_path,
            plan_name="260220BB_plan",
            filename="q2.yml",
            question_id="Q002",
            severity="low",
        )

        tui = QuestionTUI(repo_root=tmp_path)
        tui.console = Console(file=StringIO(), width=100, no_color=True, highlight=False)
        tui._refresh_questions()
        tui._render()

        output = tui.console.file.getvalue()
        assert "PENDING QUESTIONS (2)" in output


class TestMalformedYaml:
    """Tests for handling malformed or invalid YAML files."""

    def test_invalid_yaml_skipped(self, tmp_path: Path):
        """Malformed YAML files are silently skipped."""
        pending_dir = tmp_path / "docs" / "epics" / "live" / "260220XX_plan" / "questions" / "pending"
        pending_dir.mkdir(parents=True)
        (pending_dir / "bad.yml").write_text(":::invalid yaml{{{", encoding="utf-8")

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert tui.questions == []

    def test_empty_yaml_skipped(self, tmp_path: Path):
        """Empty YAML files are silently skipped."""
        pending_dir = tmp_path / "docs" / "epics" / "live" / "260220XX_plan" / "questions" / "pending"
        pending_dir.mkdir(parents=True)
        (pending_dir / "empty.yml").write_text("", encoding="utf-8")

        tui = QuestionTUI(repo_root=tmp_path)
        tui._refresh_questions()

        assert tui.questions == []
