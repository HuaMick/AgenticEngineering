"""Tests for partial-success error summarisation in orchestrate.py.

Covers _summarise_runner_errors (unit) and the partial-success headline
produced by _run_planning_loop (integration).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-046")


# ---------------------------------------------------------------------------
# Unit tests: _summarise_runner_errors
# ---------------------------------------------------------------------------


class TestSummariseRunnerErrors:
    """Unit tests for the module-level helper."""

    def _fn(self):
        from agenticcli.commands.orchestrate import _summarise_runner_errors
        return _summarise_runner_errors

    @pytest.mark.story("US-PLN-046")
    def test_empty_list_returns_no_details(self):
        assert self._fn()([]) == "no error details"

    @pytest.mark.story("US-PLN-046")
    def test_string_list_returns_first_string(self):
        result = self._fn()(["first error", "second error"])
        assert result == "first error"

    @pytest.mark.story("US-PLN-046")
    def test_dict_list_returns_error_field(self):
        errors = [
            {
                "plan": "260401XX_test",
                "error": "mock-crash-fast: deliberate SDK-style failure",
                "phase": "P1",
                "session_id": "abc123",
            }
        ]
        result = self._fn()(errors)
        assert result == "mock-crash-fast: deliberate SDK-style failure"

    @pytest.mark.story("US-PLN-046")
    def test_dict_missing_error_field_returns_unknown(self):
        errors = [{"plan": "some-epic", "phase": "P1"}]
        result = self._fn()(errors)
        assert result == "unknown error"

    @pytest.mark.story("US-PLN-046")
    def test_mixed_list_first_element_wins_string(self):
        errors = ["string-wins", {"error": "dict-loses"}]
        result = self._fn()(errors)
        assert result == "string-wins"

    @pytest.mark.story("US-PLN-046")
    def test_mixed_list_first_element_wins_dict(self):
        errors = [{"error": "dict-wins"}, "string-loses"]
        result = self._fn()(errors)
        assert result == "dict-wins"

    @pytest.mark.story("US-PLN-046")
    def test_long_string_truncated_to_120_chars(self):
        long_str = "x" * 200
        result = self._fn()([long_str])
        assert len(result) == 123  # 120 + "..."
        assert result.endswith("...")

    @pytest.mark.story("US-PLN-046")
    def test_exactly_120_chars_not_truncated(self):
        exact = "a" * 120
        result = self._fn()([exact])
        assert result == exact
        assert not result.endswith("...")

    @pytest.mark.story("US-PLN-046")
    def test_121_chars_truncated(self):
        over = "b" * 121
        result = self._fn()([over])
        assert len(result) == 123
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# Integration test: _run_planning_loop partial-success headline
# ---------------------------------------------------------------------------


class TestRunPlanningLoopPartialSuccessHeadline:
    """Integration test: partial-success path emits real error cause, not
    'budget/iteration cap' boilerplate."""

    def _make_args(self, tmp_path, plan_folder="260401XX_test_epic"):
        return SimpleNamespace(
            background=False,
            max_iterations=5,
            completion_promise=None,
            project=None,
            plan=plan_folder,
            directory=str(tmp_path),
            prompt=None,
            dangerously_skip_permissions=False,
            json=False,
            budget_usd=50.0,
        )

    @pytest.mark.story("US-PLN-046")
    def test_partial_success_headline_contains_fixture_error(self, tmp_path, capsys):
        """Headline must contain the actual error, not 'budget' or 'iteration cap'."""
        from agenticcli.commands.orchestrate import _run_planning_loop

        fixture_error = "mock-crash-fast: deliberate SDK-style failure"
        error_dict = {
            "plan": "260401XX_test_epic",
            "error": fixture_error,
            "phase": "P1",
            "session_id": "sess-abc",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = False
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": ["260401XX_test_epic"],
            "errors": [error_dict],
        }

        mock_phase = MagicMock()
        mock_phase.agent = "build-python"

        mock_epic = MagicMock()
        mock_epic.tasks = [MagicMock(), MagicMock()]  # 2 tickets

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow"), \
             patch("agenticcli.utils.phase_validation.validate_phase_routing",
                   return_value=(True, "ok")), \
             patch("agenticguidance.services.epic_repository.EpicRepository") as MockRepo, \
             patch("agenticcli.commands.orchestrate._store"):

            MockRunner.return_value = mock_runner

            mock_repo_inst = MagicMock()
            mock_repo_inst.__enter__ = MagicMock(return_value=mock_repo_inst)
            mock_repo_inst.__exit__ = MagicMock(return_value=False)
            mock_repo_inst.list_phases.return_value = [mock_phase]
            mock_repo_inst.get_epic.return_value = mock_epic
            MockRepo.return_value = mock_repo_inst

            _run_planning_loop(self._make_args(tmp_path))

        captured = capsys.readouterr()
        output = captured.out + captured.err

        assert "mock-crash-fast" in output, (
            f"Expected 'mock-crash-fast' in output; got:\n{output}"
        )
        assert "budget" not in output, (
            f"'budget' should not appear in output; got:\n{output}"
        )
        assert "iteration cap" not in output, (
            f"'iteration cap' should not appear in output; got:\n{output}"
        )
