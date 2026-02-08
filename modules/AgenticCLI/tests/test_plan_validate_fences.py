"""Tests for agentic plan validate --check-fences."""

import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from agenticcli.commands.plan import _check_fences


def _write_plan_yaml(plan_dir: Path, content: dict) -> Path:
    """Write a plan_build.yml file in the given directory."""
    f = plan_dir / "plan_build.yml"
    f.write_text(yaml.dump(content, sort_keys=False))
    return f


def _write_mmd(plan_dir: Path, content: str) -> Path:
    """Write an orchestration_test.mmd file in the given directory."""
    f = plan_dir / "orchestration_test.mmd"
    f.write_text(content)
    return f


def _make_story_data(story_ids, test_status="untested"):
    """Create mock story data as returned by _collect_all_stories."""
    return [
        {"id": sid, "test_status": test_status, "title": f"Story {sid}"}
        for sid in story_ids
    ]


# ============================================================================
# Fence 1: Story Discovery
# ============================================================================


class TestFence1StoryDiscovery:
    """Tests for Fence 1: plan has affected_stories or no_stories_rationale."""

    def test_pass_with_affected_stories(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035", "US-ORCH-036"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=_make_story_data(["US-ORCH-035", "US-ORCH-036"])):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 1 (Story Discovery)"]["status"] == "PASS"
        assert "2 affected stories" in results["Fence 1 (Story Discovery)"]["message"]

    def test_warn_with_rationale(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "no_stories_rationale": "Infrastructure only change",
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 1 (Story Discovery)"]["status"] == "WARN"
        assert "rationale provided" in results["Fence 1 (Story Discovery)"]["message"]

    def test_fail_no_stories_no_rationale(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 1 (Story Discovery)"]["status"] == "FAIL"

    def test_pass_with_user_stories_yml(self, tmp_path):
        """affected_stories in user_stories.yml should be detected."""
        plan_yaml = _write_plan_yaml(tmp_path, {"name": "test", "phases": []})
        us_file = tmp_path / "user_stories.yml"
        us_file.write_text(yaml.dump({
            "affected_stories": ["US-ORCH-035"],
        }))
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=_make_story_data(["US-ORCH-035"])):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 1 (Story Discovery)"]["status"] == "PASS"


# ============================================================================
# Fence 2: UAT Existence
# ============================================================================


class TestFence2UATExistence:
    """Tests for Fence 2: MMD has UAT subgraph."""

    def test_pass_with_uat_subgraph(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, textwrap.dedent("""\
            flowchart LR
                subgraph UAT_SG ["User Acceptance Testing"]
                    RunUAT --> CheckResults
                end
        """))

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=_make_story_data(["US-ORCH-035"])):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 2 (UAT Existence)"]["status"] == "PASS"

    def test_fail_no_uat_subgraph(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, textwrap.dedent("""\
            flowchart LR
                Build --> Test --> Done
        """))

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=_make_story_data(["US-ORCH-035"])):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 2 (UAT Existence)"]["status"] == "FAIL"

    def test_warn_no_mmd_file(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "phases": [],
        })

        results = _check_fences(tmp_path, [plan_yaml], [])

        assert results["Fence 2 (UAT Existence)"]["status"] == "WARN"


# ============================================================================
# Fence 3: Story Coverage
# ============================================================================


class TestFence3StoryCoverage:
    """Tests for Fence 3: all affected stories have test_status != untested."""

    def test_pass_all_tested(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035", "US-ORCH-036"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        stories = _make_story_data(["US-ORCH-035", "US-ORCH-036"], test_status="pass")
        with patch("agenticcli.commands.stories._collect_all_stories", return_value=stories):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 3 (Story Coverage)"]["status"] == "PASS"
        assert "All 2 stories tested" in results["Fence 3 (Story Coverage)"]["message"]

    def test_warn_partial_coverage(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035", "US-ORCH-036"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        stories = [
            {"id": "US-ORCH-035", "test_status": "pass", "title": "Story 035"},
            {"id": "US-ORCH-036", "test_status": "untested", "title": "Story 036"},
        ]
        with patch("agenticcli.commands.stories._collect_all_stories", return_value=stories):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 3 (Story Coverage)"]["status"] == "WARN"
        assert "US-ORCH-036" in results["Fence 3 (Story Coverage)"]["message"]
        assert "50%" in results["Fence 3 (Story Coverage)"]["message"]

    def test_warn_no_stories(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 3 (Story Coverage)"]["status"] == "WARN"
        assert "No affected stories" in results["Fence 3 (Story Coverage)"]["message"]

    def test_warn_story_not_found(self, tmp_path):
        """Stories in affected_stories but not in story files count as untested."""
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-999"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=[]):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 3 (Story Coverage)"]["status"] == "WARN"
        assert "US-ORCH-999" in results["Fence 3 (Story Coverage)"]["message"]


# ============================================================================
# Integration: All fences together
# ============================================================================


class TestAllFences:
    """Integration tests checking all three fences together."""

    def test_all_fences_pass(self, tmp_path):
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "affected_stories": ["US-ORCH-035"],
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  UAT --> Done")

        stories = _make_story_data(["US-ORCH-035"], test_status="pass")
        with patch("agenticcli.commands.stories._collect_all_stories", return_value=stories):
            results = _check_fences(tmp_path, [plan_yaml], [mmd])

        for fence_name, result in results.items():
            assert result["status"] == "PASS", f"{fence_name} should pass"

    def test_all_fences_fail(self, tmp_path):
        """Plan with no stories, no UAT, no coverage should fail Fence 1 and 2."""
        plan_yaml = _write_plan_yaml(tmp_path, {
            "name": "test",
            "phases": [],
        })
        mmd = _write_mmd(tmp_path, "flowchart LR\n  Build --> Done")

        results = _check_fences(tmp_path, [plan_yaml], [mmd])

        assert results["Fence 1 (Story Discovery)"]["status"] == "FAIL"
        assert results["Fence 2 (UAT Existence)"]["status"] == "FAIL"
