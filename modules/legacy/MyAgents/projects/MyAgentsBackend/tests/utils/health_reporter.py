"""Workflow health reporter for pytest.

This module provides a pytest plugin that collects test results grouped by workflow
and reports overall workflow health status instead of individual test counts.

Usage:
    pytest --workflow-health
    pytest --workflow-health-json
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class WorkflowStatus(str, Enum):
    """Workflow health status levels."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class WorkflowHealth:
    """Health status for a single workflow."""
    name: str
    status: WorkflowStatus
    passed: int
    total: int

    @property
    def failed(self) -> int:
        """Number of failed tests."""
        return self.total - self.passed

    def determine_status(self) -> WorkflowStatus:
        """Determine workflow status based on pass rate.

        Returns:
            HEALTHY if all tests pass
            DEGRADED if some tests pass (>0% and <100%)
            UNHEALTHY if no tests pass
        """
        if self.total == 0:
            return WorkflowStatus.HEALTHY

        pass_rate = self.passed / self.total

        if pass_rate == 1.0:
            return WorkflowStatus.HEALTHY
        elif pass_rate > 0:
            return WorkflowStatus.DEGRADED
        else:
            return WorkflowStatus.UNHEALTHY


class WorkflowHealthCollector:
    """Pytest plugin that collects and reports workflow health.

    This plugin hooks into pytest's collection and reporting phases to:
    1. Identify tests marked with workflow_* markers
    2. Collect pass/fail results grouped by workflow
    3. Report overall workflow health instead of individual test counts

    Workflow markers are expected to be in the form: @pytest.mark.workflow_<name>
    Tests without workflow markers are grouped under "infrastructure".
    """

    def __init__(self, config):
        """Initialize the health collector.

        Args:
            config: pytest config object
        """
        self.config = config
        self.workflow_results: Dict[str, Dict[str, int]] = {}
        self.show_health = config.getoption("--workflow-health", False)
        self.show_json = config.getoption("--workflow-health-json", False)
        self.skipped_tests = set()  # Track skipped tests

    def pytest_collection_modifyitems(self, items):
        """Called after collection has been performed.

        Examines each test item for workflow_* markers and initializes tracking.

        Args:
            items: List of collected test items
        """
        for item in items:
            workflow_name = self._extract_workflow_name(item)
            if workflow_name not in self.workflow_results:
                self.workflow_results[workflow_name] = {"passed": 0, "total": 0}
            self.workflow_results[workflow_name]["total"] += 1

    def pytest_runtest_logreport(self, report):
        """Called for each test phase (setup, call, teardown).

        Records test results in the call phase.

        Args:
            report: Test report object
        """
        # Only count results from the actual test call phase
        if report.when == "call":
            workflow_name = self._extract_workflow_name(report)

            # Ensure workflow exists in results
            if workflow_name not in self.workflow_results:
                self.workflow_results[workflow_name] = {"passed": 0, "total": 0}

            # Track skipped tests to exclude from total count
            if report.outcome == "skipped":
                self.skipped_tests.add(report.nodeid)
                # Decrement total for skipped tests
                self.workflow_results[workflow_name]["total"] -= 1
            # Count passed tests
            elif report.outcome == "passed":
                self.workflow_results[workflow_name]["passed"] += 1

    def pytest_terminal_summary(self, terminalreporter):
        """Called after all tests have run to display summary.

        Outputs workflow health report in human-readable or JSON format.

        Args:
            terminalreporter: Terminal reporter object for output
        """
        if not (self.show_health or self.show_json):
            return

        # Calculate workflow health
        workflows = []
        for workflow_name, results in sorted(self.workflow_results.items()):
            health = WorkflowHealth(
                name=workflow_name,
                status=WorkflowStatus.HEALTHY,  # Will be calculated
                passed=results["passed"],
                total=results["total"]
            )
            health.status = health.determine_status()
            workflows.append(health)

        if self.show_json:
            self._report_json(workflows, terminalreporter)
        else:
            self._report_human(workflows, terminalreporter)

        # Set exit code based on workflow health
        if any(w.status != WorkflowStatus.HEALTHY for w in workflows):
            terminalreporter.config.exitstatus = 1

    def _extract_workflow_name(self, item) -> str:
        """Extract workflow name from test item markers.

        Looks for markers in the form workflow_<name> and returns <name>.
        Falls back to "infrastructure" if no workflow marker is found.

        Args:
            item: Test item or report with markers

        Returns:
            Workflow name (e.g., "builder_agent", "infrastructure")
        """
        # Get markers from either test item or report
        markers = []
        if hasattr(item, 'iter_markers'):
            markers = list(item.iter_markers())
        elif hasattr(item, 'keywords'):
            # For reports, we need to extract markers from keywords
            for key in item.keywords:
                if key.startswith('workflow_'):
                    return key.replace('workflow_', '')

        # Check for workflow_* markers
        for marker in markers:
            if marker.name.startswith('workflow_'):
                return marker.name.replace('workflow_', '')

        return "infrastructure"

    def _report_human(self, workflows: List[WorkflowHealth], reporter):
        """Output human-readable workflow health report.

        Args:
            workflows: List of workflow health objects
            reporter: Terminal reporter for output
        """
        reporter.write_sep("=", "Workflow Health Report")

        healthy_count = 0
        for workflow in workflows:
            symbol = "✓" if workflow.status == WorkflowStatus.HEALTHY else "✗"
            reporter.write_line(
                f"{symbol} {workflow.name}: {workflow.status.value} "
                f"({workflow.passed}/{workflow.total} tests passed)"
            )
            if workflow.status == WorkflowStatus.HEALTHY:
                healthy_count += 1

        reporter.write_line("")
        reporter.write_line(
            f"Overall: {healthy_count}/{len(workflows)} workflows healthy"
        )

    def _report_json(self, workflows: List[WorkflowHealth], reporter):
        """Output JSON workflow health report.

        Args:
            workflows: List of workflow health objects
            reporter: Terminal reporter for output
        """
        output = {
            "workflows": [
                {
                    "name": w.name,
                    "status": w.status.value,
                    "passed": w.passed,
                    "failed": w.failed,
                    "total": w.total
                }
                for w in workflows
            ],
            "summary": {
                "total_workflows": len(workflows),
                "healthy": sum(1 for w in workflows if w.status == WorkflowStatus.HEALTHY),
                "degraded": sum(1 for w in workflows if w.status == WorkflowStatus.DEGRADED),
                "unhealthy": sum(1 for w in workflows if w.status == WorkflowStatus.UNHEALTHY)
            }
        }
        reporter.write_line(json.dumps(output, indent=2))


def pytest_addoption(parser):
    """Add command-line options for workflow health reporting.

    Args:
        parser: pytest argument parser
    """
    parser.addoption(
        "--workflow-health",
        action="store_true",
        default=False,
        help="Display workflow health report instead of standard test summary"
    )
    parser.addoption(
        "--workflow-health-json",
        action="store_true",
        default=False,
        help="Display workflow health report in JSON format"
    )


def pytest_configure(config):
    """Register the workflow health collector plugin.

    Args:
        config: pytest config object
    """
    if config.getoption("--workflow-health") or config.getoption("--workflow-health-json"):
        plugin = WorkflowHealthCollector(config)
        config.pluginmanager.register(plugin, "workflow_health_collector")
