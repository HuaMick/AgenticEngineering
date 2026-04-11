# story: US-PLN-048
"""UAT workflow runner — on-demand UAT validation decoupled from epics.

The UatRunner spawns `test-uat` once per story and reads the story's own
``uat_plan`` block as the agent prompt (agent-blind-test contract). The
agent itself records ``last_uat_commit`` via ``agentic stories update
<id> --status pass --kind uat`` as its final step. The framework verifies
the stamp landed and escalates if the agent forgot.

This workflow is strictly on-demand. ``session implement`` never triggers
it. Epic completion never implies it has run.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import yaml

from agenticcli.commands.stories import _find_userstories_dir
from agenticguidance.services.story import (
    Story,
    StoryService,
    get_epic_stories_path,
)

logger = logging.getLogger(__name__)


DEFAULT_UAT_TIMEOUT = 1800  # seconds
DEFAULT_UAT_MAX_TURNS = 150


class UatRunner:
    """Runs UAT sessions: one `test-uat` agent invocation per story.

    Resolves the target story set from the scope flags (single story, epic
    scope, or stale set) and spawns one test-uat agent per story. The agent
    is responsible for recording its own pass via
    ``agentic stories update <id> --status pass --kind uat``. The runner
    verifies the stamp after each spawn and treats a missing stamp as a
    failure (agent forgot to record).
    """

    def __init__(
        self,
        *,
        story_id: Optional[str] = None,
        epic_folder: Optional[str] = None,
        stale: bool = False,
        dry_run: bool = False,
        dangerously_skip_permissions: bool = False,
        timeout: int = DEFAULT_UAT_TIMEOUT,
        max_turns: int = DEFAULT_UAT_MAX_TURNS,
        working_dir: Optional[str] = None,
        transport: Optional[object] = None,
    ):
        self.story_id = story_id
        self.epic_folder = epic_folder
        self.stale = stale
        self.dry_run = dry_run
        self.dangerously_skip_permissions = dangerously_skip_permissions
        self.timeout = timeout
        self.max_turns = max_turns
        self.working_dir = working_dir or os.getcwd()
        self._transport = transport  # optional injected spawner for tests
        self.state = {
            "passed": [],
            "failed": [],
            "skipped": [],
            "commits": {},
            "errors": [],
        }

    # ----- story resolution ------------------------------------------------
    def resolve_stories(self) -> list[Story]:
        """Return the set of stories this run should validate."""
        svc = StoryService(_find_userstories_dir())

        if self.story_id:
            story = svc.get_by_id(self.story_id)
            if story is None:
                self.state["errors"].append(f"Story not found: {self.story_id}")
                return []
            return [story]

        if self.epic_folder:
            path = get_epic_stories_path(self.epic_folder)
            if not path.exists():
                self.state["errors"].append(
                    f"No epic stories file at {path}",
                )
                return []
            try:
                data = yaml.safe_load(path.read_text()) or {}
            except Exception as e:
                self.state["errors"].append(f"Could not parse {path}: {e}")
                return []
            ids = [s.get("id") for s in (data.get("stories") or []) if s.get("id")]
            resolved: list[Story] = []
            for sid in ids:
                s = svc.get_by_id(sid)
                if s is not None:
                    resolved.append(s)
            return resolved

        if self.stale:
            return svc.get_stale_stories()

        self.state["errors"].append(
            "UatRunner requires one of: story_id, epic_folder, stale=True",
        )
        return []

    # ----- uat_plan extraction --------------------------------------------
    @staticmethod
    def extract_uat_plan(story: Story) -> Optional[dict]:
        """Read the raw YAML for a story and return its `uat_plan` block.

        The Story dataclass doesn't persist uat_plan fields, so we re-parse
        the source file. Returns None if the block is missing.
        """
        if not story.source_file:
            return None
        try:
            path = Path(story.source_file)
            data = yaml.safe_load(path.read_text()) or {}
        except Exception:
            return None
        for entry in data.get("stories") or []:
            if entry.get("id") == story.id:
                plan = entry.get("uat_plan")
                if isinstance(plan, dict):
                    return plan
                return None
        return None

    # ----- prompt --------------------------------------------------------
    @staticmethod
    def build_prompt(story: Story, uat_plan: dict) -> str:
        """Build the agent-blind-test prompt for a single story.

        Minimum context: story ID + title + the uat_plan block serialized
        as YAML. No surrounding code or epic context leaks in — the point
        is to validate the story against its own documented contract.
        """
        body = yaml.safe_dump(uat_plan, sort_keys=False, default_flow_style=False)
        return (
            f"You are the test-uat agent. Execute UAT for story {story.id}.\n\n"
            f"Story: {story.title}\n\n"
            f"uat_plan:\n{body}\n\n"
            "Follow the journey steps in order. Do not fabricate observations. "
            "Report PASS only if every success_signal is directly observed.\n\n"
            "As your FINAL step, you MUST record the outcome via the CLI:\n"
            f"  - On pass: `agentic stories update {story.id} --status pass --kind uat --notes \"<one-line summary>\"`\n"
            f"  - On fail: `agentic stories update {story.id} --status fail --kind uat --notes \"<reason>\"`\n"
            "The framework will verify the stamp landed and will treat a missing "
            "stamp as a failure."
        )

    # ----- spawn --------------------------------------------------------
    def _build_spawn_command(
        self, *, prompt: str, epic_folder: Optional[str],
    ) -> list[str]:
        """Build the `agentic orchestrate session spawn` command.

        ``--epic`` is only included when the caller passed ``--epic`` to
        the UAT run. For single-story (``--story``) and stale scopes there
        is no owning epic — spawn tolerates this since ``--task`` is the
        only flag that requires ``--epic``.
        """
        cmd = [
            "agentic", "-j", "orchestrate", "session", "spawn",
            "--role", "test-uat",
            "--prompt", prompt,
            "-b", "--tmux",
            "--max-turns", str(self.max_turns),
        ]
        if epic_folder:
            cmd.extend(["--epic", epic_folder])
        if self.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        return cmd

    def _spawn_and_wait(self, story: Story, prompt: str) -> bool:
        """Spawn test-uat for one story and wait for completion.

        Returns True on success, False on failure. Errors are logged and
        appended to ``self.state["errors"]``.
        """
        if self._transport is not None:
            # Test injection path — call the mock directly.
            return bool(self._transport(story=story, prompt=prompt))

        cmd = self._build_spawn_command(
            prompt=prompt, epic_folder=self.epic_folder,
        )

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=self.working_dir,
            )
        except subprocess.TimeoutExpired:
            self.state["errors"].append(f"Spawn timed out for {story.id}")
            return False

        if result.returncode != 0:
            self.state["errors"].append(
                f"Spawn failed for {story.id}: {result.stderr.strip()}"
            )
            return False

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
        except (json.JSONDecodeError, KeyError):
            self.state["errors"].append(f"Could not parse spawn output for {story.id}")
            return False

        if not session_id:
            self.state["errors"].append(f"No session_id returned for {story.id}")
            return False

        # Wait for completion via OrchestrationWorkflow
        from agenticcli.workflows.orchestration import OrchestrationWorkflow
        workflow = OrchestrationWorkflow(working_dir=self.working_dir)
        status = workflow.wait_for_session(session_id, timeout=self.timeout)
        return status == "completed"

    # ----- main -----------------------------------------------------------
    def run(self) -> bool:
        """Execute UAT against the resolved story set.

        Returns True when every resolved story passes (or when the set is
        empty but no errors were recorded). False otherwise.
        """
        stories = self.resolve_stories()
        if not stories and self.state["errors"]:
            return False
        if not stories:
            logger.info("UatRunner: no stories resolved for scope — nothing to do")
            return True

        logger.info(
            "UatRunner: %d story(ies) resolved%s",
            len(stories),
            " (dry-run)" if self.dry_run else "",
        )

        for story in stories:
            uat_plan = self.extract_uat_plan(story)
            if not uat_plan:
                self.state["skipped"].append(story.id)
                logger.warning("Skipping %s: missing uat_plan", story.id)
                continue

            if self.dry_run:
                logger.info("[dry-run] would spawn test-uat for %s", story.id)
                continue

            prompt = self.build_prompt(story, uat_plan)
            pre_commit = self._read_last_uat_commit(story.id)
            ok = self._spawn_and_wait(story, prompt)
            if not ok:
                self.state["failed"].append(story.id)
                logger.error("UAT fail: %s (agent did not exit cleanly)", story.id)
                continue

            # Verify the agent recorded its own pass via CLI. The agent is
            # the sole writer (no framework fallback — see docstring).
            post_commit = self._read_last_uat_commit(story.id)
            if post_commit and post_commit != pre_commit:
                self.state["passed"].append(story.id)
                self.state["commits"][story.id] = post_commit
                logger.info("UAT pass: %s @ %s", story.id, post_commit[:7])
            else:
                self.state["failed"].append(story.id)
                self.state["errors"].append(
                    f"{story.id}: agent exited cleanly but last_uat_commit was "
                    "not updated — the agent forgot to run "
                    "`agentic stories update --kind uat`."
                )
                logger.error(
                    "UAT fail: %s — agent did not stamp last_uat_commit",
                    story.id,
                )

        return not self.state["failed"] and not self.state["errors"]

    @staticmethod
    def _read_last_uat_commit(story_id: str) -> Optional[str]:
        """Read the current ``last_uat_commit`` for a story, or None if unset.

        Used before/after each agent run to verify the agent recorded its
        own pass via ``agentic stories update --kind uat``.
        """
        try:
            service = StoryService()
            story = service.get_by_id(story_id)
            if story is None:
                return None
            return getattr(story, "last_uat_commit", None) or None
        except Exception as exc:
            logger.warning(
                "Could not read last_uat_commit for %s: %s", story_id, exc,
            )
            return None
