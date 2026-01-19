"""Friction pattern detection from LangSmith traces."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from .service import LangSmithService


class FrictionPatternType(Enum):
    """Types of friction patterns detected in traces."""

    EXCESSIVE_RETRIES = "FP-001"
    EXPLORATION_DRIFT = "FP-002"
    MISSING_CONTEXT = "FP-003"
    SCHEMA_VIOLATIONS = "FP-004"
    CONVENTION_VIOLATIONS = "FP-005"
    AUTOMATABLE_PATTERNS = "FP-006"


class Severity(Enum):
    """Severity levels for friction patterns."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FrictionPattern:
    """A detected friction pattern instance."""

    pattern_type: FrictionPatternType
    severity: Severity
    description: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)
    frequency: int = 1
    suggested_resolution: Optional[str] = None


@dataclass
class FrictionReport:
    """Report of all friction patterns detected in analyzed traces."""

    project_name: str
    analyzed_runs: int
    timeframe_days: int
    patterns: list[FrictionPattern] = field(default_factory=list)
    analysis_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def severity_breakdown(self) -> dict[str, int]:
        """Count patterns by severity level."""
        breakdown = {s.value: 0 for s in Severity}
        for pattern in self.patterns:
            breakdown[pattern.severity.value] += 1
        return breakdown

    @property
    def has_friction(self) -> bool:
        """Check if any friction was detected."""
        return len(self.patterns) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "project_name": self.project_name,
            "analyzed_runs": self.analyzed_runs,
            "timeframe_days": self.timeframe_days,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "has_friction": self.has_friction,
            "severity_breakdown": self.severity_breakdown,
            "patterns": [
                {
                    "pattern_type": p.pattern_type.value,
                    "severity": p.severity.value,
                    "description": p.description,
                    "frequency": p.frequency,
                    "run_ids": p.run_ids,
                    "evidence": p.evidence,
                    "suggested_resolution": p.suggested_resolution,
                }
                for p in self.patterns
            ],
        }


class FrictionAnalyzer:
    """Analyzes LangSmith traces for friction patterns."""

    def __init__(self, service: Optional[LangSmithService] = None):
        """Initialize analyzer with optional service instance."""
        self._service = service or LangSmithService()

    def analyze(
        self,
        project_name: str,
        limit: int = 100,
        lookback_days: int = 7,
    ) -> FrictionReport:
        """Analyze traces for friction patterns.

        Args:
            project_name: LangSmith project to analyze.
            limit: Maximum number of runs to analyze.
            lookback_days: Number of days to look back.

        Returns:
            FrictionReport with detected patterns.
        """
        # Query runs from the project
        runs = self._service.list_runs(project_name=project_name, limit=limit)

        # Filter by timeframe
        cutoff = datetime.now() - timedelta(days=lookback_days)
        filtered_runs = [
            r for r in runs
            if r.get("start_time") and datetime.fromisoformat(r["start_time"]) > cutoff
        ]

        # Run all pattern detectors
        patterns = []
        patterns.extend(self._detect_retries(filtered_runs))
        patterns.extend(self._detect_exploration_drift(filtered_runs))
        patterns.extend(self._detect_missing_context(filtered_runs))
        patterns.extend(self._detect_schema_violations(filtered_runs))
        patterns.extend(self._detect_convention_violations(filtered_runs))
        patterns.extend(self._detect_automatable_patterns(filtered_runs))

        return FrictionReport(
            project_name=project_name,
            analyzed_runs=len(filtered_runs),
            timeframe_days=lookback_days,
            patterns=patterns,
        )

    def _classify_severity(self, frequency: int, total_runs: int) -> Severity:
        """Classify severity based on frequency."""
        if total_runs == 0:
            return Severity.LOW
        ratio = frequency / total_runs
        if ratio > 0.5:
            return Severity.HIGH
        elif ratio > 0.2:
            return Severity.MEDIUM
        return Severity.LOW

    def _detect_retries(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-001: Excessive Retries.

        Looks for:
        - Multiple consecutive runs with same name pattern
        - Error -> Retry -> Error -> Retry sequences
        """
        patterns = []
        retry_sequences = []

        # Group runs by session_id to find retries within same session
        sessions: dict[str, list[dict]] = {}
        for run in runs:
            session_id = run.get("session_id", "unknown")
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(run)

        for session_id, session_runs in sessions.items():
            # Sort by start_time
            sorted_runs = sorted(
                session_runs,
                key=lambda r: r.get("start_time", ""),
            )

            # Look for consecutive errors or same-name retry patterns
            consecutive_errors = 0
            error_run_ids = []

            for run in sorted_runs:
                if run.get("status") == "error":
                    consecutive_errors += 1
                    error_run_ids.append(run["id"])
                else:
                    if consecutive_errors >= 3:
                        retry_sequences.append({
                            "session_id": session_id,
                            "retry_count": consecutive_errors,
                            "run_ids": error_run_ids.copy(),
                        })
                    consecutive_errors = 0
                    error_run_ids = []

            # Check end of session
            if consecutive_errors >= 3:
                retry_sequences.append({
                    "session_id": session_id,
                    "retry_count": consecutive_errors,
                    "run_ids": error_run_ids,
                })

        if retry_sequences:
            all_run_ids = []
            for seq in retry_sequences:
                all_run_ids.extend(seq["run_ids"])

            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                severity=self._classify_severity(len(retry_sequences), len(sessions)),
                description=f"Found {len(retry_sequences)} retry sequences with 3+ consecutive errors",
                evidence=retry_sequences,
                run_ids=all_run_ids,
                frequency=len(retry_sequences),
                suggested_resolution="Add clearer error handling guidance or retry limits",
            ))

        return patterns

    def _detect_exploration_drift(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-002: Exploration Drift.

        Looks for:
        - Many Glob/Grep/Read tool calls before task execution
        - High tool-to-llm ratio in early run phases
        """
        patterns = []
        drift_sessions = []

        # Group by session
        sessions: dict[str, list[dict]] = {}
        for run in runs:
            session_id = run.get("session_id", "unknown")
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(run)

        for session_id, session_runs in sessions.items():
            # Count exploration tools vs other tools
            exploration_tools = ["Glob", "Grep", "Read", "Task"]
            exploration_count = 0
            total_tool_count = 0

            for run in session_runs:
                if run.get("run_type") == "tool":
                    total_tool_count += 1
                    name = run.get("name", "")
                    if any(tool in name for tool in exploration_tools):
                        exploration_count += 1

            # Flag if >60% exploration tools and more than 10 tool calls
            if total_tool_count > 10 and exploration_count / total_tool_count > 0.6:
                drift_sessions.append({
                    "session_id": session_id,
                    "exploration_calls": exploration_count,
                    "total_tool_calls": total_tool_count,
                    "ratio": round(exploration_count / total_tool_count, 2),
                })

        if drift_sessions:
            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.EXPLORATION_DRIFT,
                severity=self._classify_severity(len(drift_sessions), len(sessions)),
                description=f"Found {len(drift_sessions)} sessions with excessive exploration (>60% exploration tools)",
                evidence=drift_sessions,
                run_ids=[],
                frequency=len(drift_sessions),
                suggested_resolution="Add path hints or signposts to process files",
            ))

        return patterns

    def _detect_missing_context(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-003: Missing Context Requests.

        Looks for:
        - AskUserQuestion calls for routine decisions
        - Questions about standard patterns/conventions
        """
        patterns = []
        question_runs = []

        for run in runs:
            if run.get("run_type") == "tool" and "AskUser" in run.get("name", ""):
                question_runs.append({
                    "run_id": run["id"],
                    "inputs": run.get("inputs", {}),
                })

        if len(question_runs) > 3:
            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.MISSING_CONTEXT,
                severity=self._classify_severity(len(question_runs), len(runs)),
                description=f"Found {len(question_runs)} AskUserQuestion calls - may indicate missing guidance",
                evidence=question_runs[:5],  # Limit evidence
                run_ids=[q["run_id"] for q in question_runs],
                frequency=len(question_runs),
                suggested_resolution="Add missing context to process files",
            ))

        return patterns

    def _detect_schema_violations(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-004: Output Schema Violations.

        Looks for:
        - Validation errors in tool calls
        - Runs with error status containing schema/format keywords
        """
        patterns = []
        violation_runs = []

        schema_keywords = ["schema", "format", "validation", "invalid", "expected", "type error"]

        for run in runs:
            if run.get("status") == "error":
                error_msg = str(run.get("error", "")).lower()
                if any(kw in error_msg for kw in schema_keywords):
                    violation_runs.append({
                        "run_id": run["id"],
                        "error": run.get("error"),
                        "name": run.get("name"),
                    })

        if violation_runs:
            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.SCHEMA_VIOLATIONS,
                severity=self._classify_severity(len(violation_runs), len(runs)),
                description=f"Found {len(violation_runs)} schema/format validation errors",
                evidence=violation_runs[:5],
                run_ids=[v["run_id"] for v in violation_runs],
                frequency=len(violation_runs),
                suggested_resolution="Add examples or output schema documentation",
            ))

        return patterns

    def _detect_convention_violations(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-005: Convention Violations.

        Looks for:
        - Post-creation renames or corrections
        - Edit/Write calls that fix naming
        """
        patterns = []
        violation_runs = []

        rename_indicators = ["rename", "mv ", "move ", "fix name", "correct"]

        for run in runs:
            if run.get("run_type") == "tool":
                name = run.get("name", "").lower()
                inputs = str(run.get("inputs", {})).lower()

                if any(ind in name or ind in inputs for ind in rename_indicators):
                    violation_runs.append({
                        "run_id": run["id"],
                        "name": run.get("name"),
                    })

        if violation_runs:
            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.CONVENTION_VIOLATIONS,
                severity=self._classify_severity(len(violation_runs), len(runs)),
                description=f"Found {len(violation_runs)} potential convention corrections (renames/fixes)",
                evidence=violation_runs[:5],
                run_ids=[v["run_id"] for v in violation_runs],
                frequency=len(violation_runs),
                suggested_resolution="Enforce via agentic CLI commands",
            ))

        return patterns

    def _detect_automatable_patterns(self, runs: list[dict[str, Any]]) -> list[FrictionPattern]:
        """Detect FP-006: Automatable Patterns.

        Looks for:
        - Identical tool call sequences across sessions
        - Boilerplate generation patterns
        """
        patterns = []

        # Group by session and extract tool sequences
        sessions: dict[str, list[str]] = {}
        for run in runs:
            if run.get("run_type") == "tool":
                session_id = run.get("session_id", "unknown")
                if session_id not in sessions:
                    sessions[session_id] = []
                sessions[session_id].append(run.get("name", ""))

        # Look for repeated sequences (simplified: look for same 3+ tool sequence)
        sequence_counts: dict[tuple, int] = {}
        for session_id, tools in sessions.items():
            for i in range(len(tools) - 2):
                seq = tuple(tools[i:i+3])
                sequence_counts[seq] = sequence_counts.get(seq, 0) + 1

        # Find sequences that appear in multiple sessions
        repeated = [(seq, count) for seq, count in sequence_counts.items() if count >= 3]

        if repeated:
            evidence = [{"sequence": list(seq), "occurrences": count} for seq, count in repeated[:5]]
            patterns.append(FrictionPattern(
                pattern_type=FrictionPatternType.AUTOMATABLE_PATTERNS,
                severity=self._classify_severity(len(repeated), len(sessions)),
                description=f"Found {len(repeated)} repeated tool sequences (3+ occurrences)",
                evidence=evidence,
                run_ids=[],
                frequency=len(repeated),
                suggested_resolution="Create new agentic command for the pattern",
            ))

        return patterns
