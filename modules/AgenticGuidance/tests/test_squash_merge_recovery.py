"""Squash-merge / reflog GC recovery tests.

Simulates the scenario where `last_pass_commit` is unreachable (e.g. after a
squash-merge rewrites history or git GC purges the reflog), and verifies that:

1. Unreachable commit + matching tree_hash  → story is NOT stale ('passing')
2. Unreachable commit + no tree_hash        → story IS stale (anchor_unreachable)
3. Unreachable commit + mismatched tree_hash → story IS stale (anchor_unreachable)

Uses a real git repository initialised in tmp_path so the git plumbing is
exercised end-to-end — the point is that the fallback logic survives real git
errors, not just mocked subprocess calls.

All tests tagged @pytest.mark.story("US-STR-020").
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-STR-020")

from agenticguidance.services.story import Story, StoryService, _compute_tree_hash


# ---------------------------------------------------------------------------
# Git repo fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path):
    """Initialise a minimal real git repo with one commit and one test file.

    Returns a dict with:
      - repo_root (Path)
      - test_file (Path, relative to repo_root as str)
      - head_commit (str): the full SHA of the single commit
      - tree_hash (str): the computed watch-file tree hash for [test_file]
      - nonexistent_sha (str): a SHA that definitely doesn't exist in history
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def _git(*args, **kwargs):
        return subprocess.run(
            ["git"] + list(args),
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            **kwargs,
        )

    _git("init")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test User")
    _git("config", "commit.gpgsign", "false")

    # Create a tracked test file and commit it
    test_file = repo_root / "watched_module.py"
    test_file.write_text("# initial content\n")
    _git("add", "watched_module.py")
    _git("commit", "-m", "initial commit")

    # Get HEAD sha
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root), capture_output=True, text=True, check=True,
    )
    head_commit = result.stdout.strip()

    # Compute the tree hash for the watched file at HEAD
    tree_hash = _compute_tree_hash(["watched_module.py"], repo_root)

    return {
        "repo_root": repo_root,
        "test_file_rel": "watched_module.py",
        "head_commit": head_commit,
        "tree_hash": tree_hash,
        "nonexistent_sha": "dead0000deadbeefdeadc0dedeadbeef00000000",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSquashMergeRecovery:

    def test_unreachable_commit_matching_tree_hash_is_passing(self, git_repo):
        """Unreachable last_pass_commit + last_pass_tree_hash matches HEAD → 'passing'.

        This simulates the squash-merge scenario: the exact commit is gone,
        but the watch files haven't changed, so the story is not stale.
        """
        repo_root = git_repo["repo_root"]
        tree_hash = git_repo["tree_hash"]
        assert tree_hash is not None, "Fixture setup failed: could not compute tree hash"

        story = Story(
            id="US-TEST-001",
            title="Story with squash-merged commit",
            test_status="pass",
            last_pass_commit=git_repo["nonexistent_sha"],  # definitely unreachable
            last_pass_tree_hash=tree_hash,  # matches current HEAD
            related_files=[git_repo["test_file_rel"]],
        )

        svc = StoryService(userstories_dir=None)
        status = svc.compute_story_status(story, repo_root=repo_root)
        assert status == "passing", (
            f"Expected 'passing' (tree hash matched after unreachable commit), got '{status}'"
        )

    def test_unreachable_commit_no_tree_hash_is_stale(self, git_repo):
        """Unreachable commit + empty last_pass_tree_hash → 'stale' with anchor_unreachable.

        With no tree hash to fall back on, we can't tell whether files changed,
        so the story conservatively becomes stale.
        """
        repo_root = git_repo["repo_root"]

        story = Story(
            id="US-TEST-001",
            title="Story with no tree hash fallback",
            test_status="pass",
            last_pass_commit=git_repo["nonexistent_sha"],
            last_pass_tree_hash="",  # no fallback
            related_files=[git_repo["test_file_rel"]],
        )

        svc = StoryService(userstories_dir=None)
        status = svc.compute_story_status(story, repo_root=repo_root)
        flags = svc.compute_story_flags(story, repo_root=repo_root)

        assert status == "stale", f"Expected 'stale', got '{status}'"
        assert flags["stale_reason"] == "anchor_unreachable", (
            f"Expected stale_reason='anchor_unreachable', got '{flags['stale_reason']}'"
        )

    def test_unreachable_commit_mismatched_tree_hash_is_stale(self, git_repo):
        """Unreachable commit + mismatched tree hash → 'stale' with anchor_unreachable.

        The tree has moved (files changed) AND the original commit is gone —
        so we can't tell what changed. Story is conservatively stale.
        """
        repo_root = git_repo["repo_root"]

        story = Story(
            id="US-TEST-001",
            title="Story with moved tree, gone commit",
            test_status="pass",
            last_pass_commit=git_repo["nonexistent_sha"],
            last_pass_tree_hash="this_hash_does_not_match_current_tree",
            related_files=[git_repo["test_file_rel"]],
        )

        svc = StoryService(userstories_dir=None)
        status = svc.compute_story_status(story, repo_root=repo_root)
        flags = svc.compute_story_flags(story, repo_root=repo_root)

        assert status == "stale", f"Expected 'stale', got '{status}'"
        assert flags["stale_reason"] == "anchor_unreachable", (
            f"Expected stale_reason='anchor_unreachable', got '{flags['stale_reason']}'"
        )

    def test_reachable_commit_unchanged_files_is_passing(self, git_repo):
        """Sanity: reachable commit + no file changes → 'passing' (not stale).

        Guards against the fallback logic incorrectly marking non-squash-merged
        stories as stale.
        """
        repo_root = git_repo["repo_root"]
        head_commit = git_repo["head_commit"]

        story = Story(
            id="US-TEST-001",
            title="Normal passing story",
            test_status="pass",
            last_pass_commit=head_commit,  # reachable
            related_files=[git_repo["test_file_rel"]],
        )

        svc = StoryService(userstories_dir=None)
        status = svc.compute_story_status(story, repo_root=repo_root)
        assert status == "passing", f"Expected 'passing', got '{status}'"

    def test_reachable_commit_changed_file_is_stale(self, git_repo):
        """Sanity: reachable commit + file changed in new commit → 'stale'.

        Ensures the normal (non-fallback) staleness path also works correctly
        in a real git repo.
        """
        repo_root = git_repo["repo_root"]
        head_commit = git_repo["head_commit"]

        # Make a second commit that modifies the watched file
        (repo_root / git_repo["test_file_rel"]).write_text("# modified content\n")
        subprocess.run(
            ["git", "add", git_repo["test_file_rel"]],
            cwd=str(repo_root), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "second commit"],
            cwd=str(repo_root), check=True, capture_output=True,
        )

        # Story still points to the first commit (before the change)
        story = Story(
            id="US-TEST-001",
            title="Story with changed related file",
            test_status="pass",
            last_pass_commit=head_commit,  # first commit — file changed since then
            related_files=[git_repo["test_file_rel"]],
        )

        svc = StoryService(userstories_dir=None)
        status = svc.compute_story_status(story, repo_root=repo_root)
        assert status == "stale", f"Expected 'stale', got '{status}'"
