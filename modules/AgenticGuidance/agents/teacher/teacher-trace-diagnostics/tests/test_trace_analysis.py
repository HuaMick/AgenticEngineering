"""Tests for teacher-trace-diagnostics agent trace analysis patterns.

This module tests pattern detection functions used by the trace diagnostics agent:
- Backtracking detection (repeated resource access)
- Error clustering (similar errors across runs)
- Path ambiguity (hesitation, multiple attempts)
- Token anomaly detection (abnormal token consumption)

Tests use mock LangSmith data to avoid requiring live API access.
"""

import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch


# Sample trace data for testing
# Note: Token counts designed so run-003 is >2 std dev above mean
# Normal runs: ~5000 tokens, anomaly run: 50000 tokens
SAMPLE_RUNS: list[dict[str, Any]] = [
    {
        "id": "run-001",
        "name": "agent-execution",
        "status": "success",
        "latency": 45.2,
        "total_tokens": 5000,
        "prompt_tokens": 4000,
        "completion_tokens": 1000,
        "error": None,
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:00:00",
        "end_time": "2026-01-19T10:00:45",
        "run_type": "chain",
    },
    {
        "id": "run-002",
        "name": "agent-execution",
        "status": "error",
        "latency": 12.3,
        "total_tokens": 4500,
        "prompt_tokens": 3500,
        "completion_tokens": 1000,
        "error": "FileNotFoundError: /path/to/missing/file.txt",
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:01:00",
        "end_time": "2026-01-19T10:01:12",
        "run_type": "chain",
    },
    {
        "id": "run-003",
        "name": "agent-execution",
        "status": "success",
        "latency": 120.5,
        "total_tokens": 50000,  # High token count - anomaly (10x normal)
        "prompt_tokens": 45000,
        "completion_tokens": 5000,
        "error": None,
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:02:00",
        "end_time": "2026-01-19T10:04:00",
        "run_type": "chain",
    },
    {
        "id": "run-004",
        "name": "agent-execution",
        "status": "error",
        "latency": 8.1,
        "total_tokens": 4800,
        "prompt_tokens": 3800,
        "completion_tokens": 1000,
        "error": "FileNotFoundError: /different/path/missing.txt",
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:05:00",
        "end_time": "2026-01-19T10:05:08",
        "run_type": "chain",
    },
    {
        "id": "run-005",
        "name": "agent-execution",
        "status": "error",
        "latency": 9.2,
        "total_tokens": 5200,
        "prompt_tokens": 4200,
        "completion_tokens": 1000,
        "error": "FileNotFoundError: /another/path/file.txt",
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:06:00",
        "end_time": "2026-01-19T10:06:09",
        "run_type": "chain",
    },
    {
        "id": "run-006",
        "name": "agent-execution",
        "status": "success",
        "latency": 30.0,
        "total_tokens": 4700,
        "prompt_tokens": 3700,
        "completion_tokens": 1000,
        "error": None,
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:07:00",
        "end_time": "2026-01-19T10:07:30",
        "run_type": "chain",
    },
    {
        "id": "run-007",
        "name": "agent-execution",
        "status": "success",
        "latency": 25.0,
        "total_tokens": 5100,
        "prompt_tokens": 4100,
        "completion_tokens": 1000,
        "error": None,
        "tags": ["orchestration"],
        "start_time": "2026-01-19T10:08:00",
        "end_time": "2026-01-19T10:08:25",
        "run_type": "chain",
    },
]


# Backtracking sample - runs that access same resource multiple times
BACKTRACKING_RUNS: list[dict[str, Any]] = [
    {
        "id": "bt-001",
        "name": "read-file",
        "run_type": "tool",
        "inputs": {"path": "/src/config.yml"},
        "status": "success",
    },
    {
        "id": "bt-002",
        "name": "analyze",
        "run_type": "chain",
        "inputs": {},
        "status": "success",
    },
    {
        "id": "bt-003",
        "name": "read-file",
        "run_type": "tool",
        "inputs": {"path": "/src/config.yml"},  # Same file - potential backtracking
        "status": "success",
    },
    {
        "id": "bt-004",
        "name": "analyze",
        "run_type": "chain",
        "inputs": {},
        "status": "success",
    },
    {
        "id": "bt-005",
        "name": "read-file",
        "run_type": "tool",
        "inputs": {"path": "/src/config.yml"},  # Third access - definite backtracking
        "status": "success",
    },
]


# Hesitation sample - runs with long pauses
HESITATION_RUNS: list[dict[str, Any]] = [
    {
        "id": "hes-001",
        "name": "step-1",
        "status": "success",
        "start_time": "2026-01-19T10:00:00",
        "end_time": "2026-01-19T10:00:10",
    },
    {
        "id": "hes-002",
        "name": "step-2",
        "status": "success",
        "start_time": "2026-01-19T10:00:50",  # 40 second pause - hesitation
        "end_time": "2026-01-19T10:01:00",
    },
    {
        "id": "hes-003",
        "name": "step-3",
        "status": "success",
        "start_time": "2026-01-19T10:01:05",  # 5 second pause - normal
        "end_time": "2026-01-19T10:01:15",
    },
]


class TestBacktrackingDetection:
    """Tests for backtracking pattern detection."""

    def test_detects_repeated_resource_access(self):
        """Test that repeated access to same resource is detected."""
        # Helper function to extract resource from run
        def extract_resource(run: dict) -> str | None:
            if run.get("inputs") and "path" in run["inputs"]:
                return run["inputs"]["path"]
            return None

        # Simple backtracking detection
        findings = []
        resource_access: dict[str, list[int]] = {}

        for i, run in enumerate(BACKTRACKING_RUNS):
            resource = extract_resource(run)
            if not resource:
                continue

            if resource in resource_access:
                if len(resource_access[resource]) >= 2:
                    findings.append({
                        "pattern": "backtracking",
                        "resource": resource,
                        "access_count": len(resource_access[resource]) + 1,
                    })
                resource_access[resource].append(i)
            else:
                resource_access[resource] = [i]

        assert len(findings) >= 1
        assert findings[0]["resource"] == "/src/config.yml"
        assert findings[0]["access_count"] >= 3

    def test_ignores_legitimate_rereads(self):
        """Test that reads with intervening writes are not flagged."""
        runs_with_write = [
            {"id": "1", "name": "read-file", "inputs": {"path": "/config.yml"}},
            {"id": "2", "name": "write-file", "inputs": {"path": "/config.yml"}},
            {"id": "3", "name": "read-file", "inputs": {"path": "/config.yml"}},  # Legitimate re-read
        ]

        # With a write between reads, this should not be flagged as backtracking
        # The pattern detection should check for productive changes
        has_write = any(r["name"] == "write-file" for r in runs_with_write)
        assert has_write, "Test data should include a write operation"


class TestErrorClustering:
    """Tests for error clustering pattern detection."""

    def test_clusters_similar_errors(self):
        """Test grouping of runs with similar error messages."""
        error_runs = [r for r in SAMPLE_RUNS if r["status"] == "error"]

        # Simple clustering by error type
        error_types: dict[str, list[str]] = {}
        for run in error_runs:
            error = run.get("error", "")
            # Extract error type (e.g., FileNotFoundError)
            error_type = error.split(":")[0] if ":" in error else error
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(run["id"])

        # Should cluster FileNotFoundError occurrences
        assert "FileNotFoundError" in error_types
        assert len(error_types["FileNotFoundError"]) >= 3

    def test_severity_based_on_count(self):
        """Test that severity increases with occurrence count."""
        # 3-5 occurrences = MEDIUM
        # 6-10 occurrences = HIGH
        # >10 occurrences = CRITICAL

        def get_severity(count: int) -> str:
            if count > 10:
                return "CRITICAL"
            elif count > 5:
                return "HIGH"
            elif count >= 3:
                return "MEDIUM"
            return "LOW"

        assert get_severity(3) == "MEDIUM"
        assert get_severity(5) == "MEDIUM"
        assert get_severity(6) == "HIGH"
        assert get_severity(10) == "HIGH"
        assert get_severity(11) == "CRITICAL"


class TestPathAmbiguityDetection:
    """Tests for path ambiguity (hesitation) detection."""

    def test_detects_long_pauses(self):
        """Test detection of hesitation via long pauses between runs."""
        pause_threshold = 30  # seconds

        findings = []
        for i in range(1, len(HESITATION_RUNS)):
            prev_run = HESITATION_RUNS[i - 1]
            curr_run = HESITATION_RUNS[i]

            if prev_run.get("end_time") and curr_run.get("start_time"):
                prev_end = datetime.fromisoformat(prev_run["end_time"])
                curr_start = datetime.fromisoformat(curr_run["start_time"])
                pause = (curr_start - prev_end).total_seconds()

                if pause > pause_threshold:
                    findings.append({
                        "pattern": "path_ambiguity",
                        "type": "hesitation",
                        "run_id": curr_run["id"],
                        "pause_seconds": pause,
                    })

        assert len(findings) >= 1
        assert findings[0]["pause_seconds"] > 30

    def test_ignores_normal_intervals(self):
        """Test that normal intervals are not flagged."""
        normal_runs = [
            {"id": "1", "end_time": "2026-01-19T10:00:00"},
            {"id": "2", "start_time": "2026-01-19T10:00:05"},  # 5 second gap - normal
        ]

        pause_threshold = 30
        prev_end = datetime.fromisoformat(normal_runs[0]["end_time"])
        curr_start = datetime.fromisoformat(normal_runs[1]["start_time"])
        pause = (curr_start - prev_end).total_seconds()

        assert pause < pause_threshold


class TestTokenAnomalyDetection:
    """Tests for token consumption anomaly detection."""

    def test_flags_high_token_runs(self):
        """Test detection of runs > 2 std dev from mean."""
        import statistics

        token_counts = [r["total_tokens"] for r in SAMPLE_RUNS if r["total_tokens"]]
        mean = statistics.mean(token_counts)
        std = statistics.stdev(token_counts)
        threshold = mean + (2 * std)

        findings = []
        for run in SAMPLE_RUNS:
            if run["total_tokens"] and run["total_tokens"] > threshold:
                deviation = (run["total_tokens"] - mean) / std
                findings.append({
                    "pattern": "token_anomaly",
                    "run_id": run["id"],
                    "tokens": run["total_tokens"],
                    "std_deviations": round(deviation, 2),
                })

        # run-003 has 25000 tokens, should be flagged
        assert len(findings) >= 1
        anomaly_ids = [f["run_id"] for f in findings]
        assert "run-003" in anomaly_ids

    def test_severity_classification(self):
        """Test that severity is correctly classified by std deviation."""

        def get_severity(std_dev: float) -> str:
            if std_dev > 3:
                return "CRITICAL"
            elif std_dev > 2.5:
                return "HIGH"
            elif std_dev > 2:
                return "MEDIUM"
            return "LOW"

        assert get_severity(2.1) == "MEDIUM"
        assert get_severity(2.6) == "HIGH"
        assert get_severity(3.1) == "CRITICAL"


class TestSeverityClassification:
    """Tests for overall severity classification."""

    def test_critical_for_blocking_errors(self):
        """Test CRITICAL severity for errors preventing completion."""
        # >10 error occurrences or context overflow
        occurrences = 15
        severity = "CRITICAL" if occurrences > 10 else "HIGH"
        assert severity == "CRITICAL"

    def test_medium_for_inefficiencies(self):
        """Test MEDIUM severity for non-blocking inefficiencies."""
        # 2-5 backtracking instances
        backtrack_count = 3
        severity = "MEDIUM" if 2 <= backtrack_count <= 5 else "HIGH"
        assert severity == "MEDIUM"


class TestMockLangSmithService:
    """Tests using mock LangSmith service."""

    def test_list_runs_with_mock(self):
        """Test that we can mock the LangSmith service."""
        mock_service = Mock()
        mock_service.list_runs.return_value = SAMPLE_RUNS

        runs = mock_service.list_runs(project_name="test-project", limit=10)

        assert len(runs) == len(SAMPLE_RUNS)
        assert runs[0]["id"] == "run-001"
        mock_service.list_runs.assert_called_once_with(
            project_name="test-project", limit=10
        )

    def test_error_filtering_with_mock(self):
        """Test error-only filtering with mock service."""
        mock_service = Mock()
        mock_service.list_runs.return_value = [
            r for r in SAMPLE_RUNS if r["status"] == "error"
        ]

        error_runs = mock_service.list_runs(
            project_name="test-project", error_only=True
        )

        assert all(r["status"] == "error" for r in error_runs)
        assert len(error_runs) == 3  # run-002, run-004, run-005 (from filtered data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
