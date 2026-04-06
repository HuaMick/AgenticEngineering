"""Tests for EpicService.is_build_plan() — plan-type detection helper.

Validates that build-plan epics are correctly classified vs infra/guidance epics.
Ticket: TS_001 — 260327AG_mandatory_ticket_story_binding_for_build_plans
"""

import pytest

from agenticguidance.services.epic import EpicService
from agenticguidance.services.epic_repository import EpicRepository

pytestmark = []


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


@pytest.fixture
def service(repo):
    """Create an EpicService with the isolated repository."""
    return EpicService(repository=repo)


def _seed_epic(repo, epic_name="test_epic"):
    """Create a bare epic in the repository with no phases."""
    repo.create_epic({
        "epic_folder_name": epic_name,
        "epic_folder": "",
        "name": epic_name,
        "status": "active",
        "objective": f"Test epic {epic_name}",
    })


class TestIsBuildPlan:
    """Test EpicService.is_build_plan() helper for plan-type detection."""

    def test_build_python_agent_returns_true(self, repo, service):
        """Epic with a build-python phase agent should be classified as build plan."""
        epic_name = "260401XX_build_feature"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Build Phase",
            "agent": "build-python",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is True

    def test_teacher_update_guidance_only_returns_false(self, repo, service):
        """Epic with only teacher-update-guidance agent is NOT a build plan."""
        epic_name = "260401XX_guidance_update"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Guidance Phase",
            "agent": "teacher-update-guidance",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is False

    def test_mixed_build_and_non_build_agents_returns_true(self, repo, service):
        """Epic with mixed build-python + deploy-cicd agents → True (conservative)."""
        epic_name = "260401XX_mixed_epic"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Build Phase",
            "agent": "build-python",
            "status": "pending",
        })
        repo.add_phase(epic_name, {
            "name": "Deploy Phase",
            "agent": "deploy-cicd",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is True

    def test_no_phases_returns_false(self, repo, service):
        """Epic with no phases → False (avoids blocking skeleton epics)."""
        epic_name = "260401XX_empty_epic"
        _seed_epic(repo, epic_name)

        assert service.is_build_plan(epic_name) is False

    def test_phases_without_agent_field_returns_false(self, repo, service):
        """Epic with phases but no agent field set → False."""
        epic_name = "260401XX_no_agent_epic"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Phase Without Agent",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is False

    def test_build_flutter_agent_returns_true(self, repo, service):
        """Any build- prefix agent should be classified as build plan."""
        epic_name = "260401XX_flutter_app"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Build Phase",
            "agent": "build-flutter",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is True

    def test_nonexistent_epic_returns_false(self, repo, service):
        """is_build_plan on an epic that doesn't exist → False."""
        assert service.is_build_plan("nonexistent_epic_999") is False

    def test_no_repository_returns_false(self):
        """EpicService with no repository → False."""
        svc = EpicService(repository=None)
        assert svc.is_build_plan("anything") is False

    def test_agent_field_none_returns_false(self, repo, service):
        """Phase with agent explicitly set to None → False."""
        epic_name = "260401XX_none_agent"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Phase With None Agent",
            "agent": None,
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is False

    def test_agent_field_empty_string_returns_false(self, repo, service):
        """Phase with agent set to empty string → False."""
        epic_name = "260401XX_empty_agent"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Phase With Empty Agent",
            "agent": "",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is False

    def test_multiple_non_build_agents_returns_false(self, repo, service):
        """Epic with only non-build agents (test-runner, teacher-*) → False."""
        epic_name = "260401XX_infra_epic"
        _seed_epic(repo, epic_name)
        repo.add_phase(epic_name, {
            "name": "Test Phase",
            "agent": "test-runner",
            "status": "pending",
        })
        repo.add_phase(epic_name, {
            "name": "Guidance Phase",
            "agent": "teacher-update-guidance",
            "status": "pending",
        })

        assert service.is_build_plan(epic_name) is False
