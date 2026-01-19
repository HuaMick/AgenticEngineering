"""Unit tests for friction pattern detection and resolution."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from agenticlangsmith.friction import (
    FrictionAnalyzer,
    FrictionPattern,
    FrictionPatternType,
    FrictionReport,
    Severity,
)
from agenticlangsmith.resolution import (
    ResolutionPlan,
    ResolutionRecommendation,
    ResolutionRecommender,
    ResolutionType,
)


# ============================================================
# Fixtures for sample trace data
# ============================================================


@pytest.fixture
def mock_service():
    """Create a mocked LangSmithService instance."""
    service = MagicMock()
    service.list_runs.return_value = []
    return service


@pytest.fixture
def make_run():
    """Factory fixture for creating run data."""
    def _make_run(
        run_type: str = "llm",
        name: str = "TestRun",
        status: str = "success",
        error: str = None,
        session_id: str = None,
        inputs: dict = None,
        start_time: datetime = None,
    ):
        return {
            "id": str(uuid4()),
            "name": name,
            "run_type": run_type,
            "status": status,
            "error": error,
            "session_id": session_id or str(uuid4()),
            "inputs": inputs or {},
            "start_time": (start_time or datetime.now()).isoformat(),
        }
    return _make_run


@pytest.fixture
def session_with_retries(make_run):
    """Create a session with excessive retries (3+ consecutive errors)."""
    session_id = str(uuid4())
    base_time = datetime.now()
    return [
        make_run(session_id=session_id, status="error", start_time=base_time),
        make_run(session_id=session_id, status="error", start_time=base_time + timedelta(seconds=1)),
        make_run(session_id=session_id, status="error", start_time=base_time + timedelta(seconds=2)),
        make_run(session_id=session_id, status="error", start_time=base_time + timedelta(seconds=3)),
        make_run(session_id=session_id, status="success", start_time=base_time + timedelta(seconds=4)),
    ]


@pytest.fixture
def session_with_exploration_drift(make_run):
    """Create a session with exploration drift (>60% exploration tools)."""
    session_id = str(uuid4())
    base_time = datetime.now()
    runs = []
    # 8 exploration tool calls out of 12 total = 66.7%
    for i in range(8):
        runs.append(make_run(
            run_type="tool",
            name="Glob",
            session_id=session_id,
            start_time=base_time + timedelta(seconds=i),
        ))
    for i in range(4):
        runs.append(make_run(
            run_type="tool",
            name="Edit",
            session_id=session_id,
            start_time=base_time + timedelta(seconds=8 + i),
        ))
    return runs


@pytest.fixture
def session_with_user_questions(make_run):
    """Create a session with multiple AskUserQuestion calls."""
    session_id = str(uuid4())
    base_time = datetime.now()
    return [
        make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time),
        make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time + timedelta(seconds=1)),
        make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time + timedelta(seconds=2)),
        make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time + timedelta(seconds=3)),
        make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=4)),
    ]


@pytest.fixture
def session_with_schema_errors(make_run):
    """Create a session with schema validation errors."""
    session_id = str(uuid4())
    base_time = datetime.now()
    return [
        make_run(session_id=session_id, status="error", error="schema validation failed: expected object", start_time=base_time),
        make_run(session_id=session_id, status="error", error="format error: invalid JSON", start_time=base_time + timedelta(seconds=1)),
        make_run(session_id=session_id, status="success", start_time=base_time + timedelta(seconds=2)),
    ]


@pytest.fixture
def session_with_convention_violations(make_run):
    """Create a session with naming convention fixes."""
    session_id = str(uuid4())
    base_time = datetime.now()
    return [
        make_run(run_type="tool", name="Bash", inputs={"command": "mv old_name.py new_name.py"}, session_id=session_id, start_time=base_time),
        make_run(run_type="tool", name="rename_file", session_id=session_id, start_time=base_time + timedelta(seconds=1)),
        make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=2)),
    ]


@pytest.fixture
def session_with_repeated_sequences(make_run):
    """Create multiple sessions with repeated tool sequences."""
    sessions = []
    for _ in range(3):
        session_id = str(uuid4())
        base_time = datetime.now()
        sessions.extend([
            make_run(run_type="tool", name="Glob", session_id=session_id, start_time=base_time),
            make_run(run_type="tool", name="Read", session_id=session_id, start_time=base_time + timedelta(seconds=1)),
            make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=2)),
        ])
    return sessions


@pytest.fixture
def clean_session(make_run):
    """Create a clean session with no friction."""
    session_id = str(uuid4())
    base_time = datetime.now()
    return [
        make_run(run_type="llm", name="ChatModel", session_id=session_id, start_time=base_time),
        make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=1)),
        make_run(run_type="llm", name="ChatModel", session_id=session_id, start_time=base_time + timedelta(seconds=2)),
    ]


# ============================================================
# FrictionPatternType and Severity tests
# ============================================================


class TestEnums:
    """Tests for friction pattern and severity enums."""

    def test_friction_pattern_types(self):
        """Test that all 6 friction pattern types are defined."""
        assert FrictionPatternType.EXCESSIVE_RETRIES.value == "FP-001"
        assert FrictionPatternType.EXPLORATION_DRIFT.value == "FP-002"
        assert FrictionPatternType.MISSING_CONTEXT.value == "FP-003"
        assert FrictionPatternType.SCHEMA_VIOLATIONS.value == "FP-004"
        assert FrictionPatternType.CONVENTION_VIOLATIONS.value == "FP-005"
        assert FrictionPatternType.AUTOMATABLE_PATTERNS.value == "FP-006"

    def test_severity_levels(self):
        """Test that severity levels are defined."""
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"


# ============================================================
# FrictionReport tests
# ============================================================


class TestFrictionReport:
    """Tests for FrictionReport dataclass."""

    def test_report_creation(self):
        """Test basic report creation."""
        report = FrictionReport(
            project_name="test-project",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[],
        )
        assert report.project_name == "test-project"
        assert report.analyzed_runs == 100
        assert report.timeframe_days == 7
        assert report.patterns == []

    def test_severity_breakdown_empty(self):
        """Test severity breakdown with no patterns."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=0,
            timeframe_days=7,
        )
        breakdown = report.severity_breakdown
        assert breakdown["high"] == 0
        assert breakdown["medium"] == 0
        assert breakdown["low"] == 0

    def test_severity_breakdown_with_patterns(self):
        """Test severity breakdown counts patterns correctly."""
        patterns = [
            FrictionPattern(
                pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                severity=Severity.HIGH,
                description="Test 1",
            ),
            FrictionPattern(
                pattern_type=FrictionPatternType.EXPLORATION_DRIFT,
                severity=Severity.HIGH,
                description="Test 2",
            ),
            FrictionPattern(
                pattern_type=FrictionPatternType.MISSING_CONTEXT,
                severity=Severity.MEDIUM,
                description="Test 3",
            ),
        ]
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=patterns,
        )
        breakdown = report.severity_breakdown
        assert breakdown["high"] == 2
        assert breakdown["medium"] == 1
        assert breakdown["low"] == 0

    def test_has_friction_true(self):
        """Test has_friction returns True when patterns exist."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=10,
            timeframe_days=7,
            patterns=[FrictionPattern(
                pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                severity=Severity.LOW,
                description="Test",
            )],
        )
        assert report.has_friction is True

    def test_has_friction_false(self):
        """Test has_friction returns False when no patterns."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=10,
            timeframe_days=7,
            patterns=[],
        )
        assert report.has_friction is False

    def test_to_dict(self):
        """Test report serialization to dictionary."""
        report = FrictionReport(
            project_name="test-project",
            analyzed_runs=50,
            timeframe_days=3,
            patterns=[FrictionPattern(
                pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                severity=Severity.HIGH,
                description="Retry detected",
                frequency=5,
                run_ids=["run-1", "run-2"],
            )],
        )
        result = report.to_dict()

        assert result["project_name"] == "test-project"
        assert result["analyzed_runs"] == 50
        assert result["timeframe_days"] == 3
        assert result["has_friction"] is True
        assert len(result["patterns"]) == 1
        assert result["patterns"][0]["pattern_type"] == "FP-001"
        assert result["patterns"][0]["severity"] == "high"


# ============================================================
# FrictionAnalyzer pattern detection tests
# ============================================================


class TestDetectRetryPattern:
    """Tests for FP-001: Excessive Retries detection."""

    def test_detect_retry_pattern(self, mock_service, session_with_retries):
        """Test that retry sequences are detected."""
        mock_service.list_runs.return_value = session_with_retries

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project", limit=100, lookback_days=7)

        retry_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXCESSIVE_RETRIES]
        assert len(retry_patterns) == 1
        assert retry_patterns[0].frequency >= 1
        assert "retry" in retry_patterns[0].description.lower() or "error" in retry_patterns[0].description.lower()

    def test_no_retry_pattern_under_threshold(self, mock_service, make_run):
        """Test that fewer than 3 consecutive errors doesn't trigger pattern."""
        session_id = str(uuid4())
        base_time = datetime.now()
        runs = [
            make_run(session_id=session_id, status="error", start_time=base_time),
            make_run(session_id=session_id, status="error", start_time=base_time + timedelta(seconds=1)),
            make_run(session_id=session_id, status="success", start_time=base_time + timedelta(seconds=2)),
        ]
        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        retry_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXCESSIVE_RETRIES]
        assert len(retry_patterns) == 0


class TestDetectExplorationDrift:
    """Tests for FP-002: Exploration Drift detection."""

    def test_detect_exploration_drift(self, mock_service, session_with_exploration_drift):
        """Test that exploration drift is detected."""
        mock_service.list_runs.return_value = session_with_exploration_drift

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        drift_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXPLORATION_DRIFT]
        assert len(drift_patterns) == 1
        assert "exploration" in drift_patterns[0].description.lower()

    def test_no_drift_with_balanced_tools(self, mock_service, make_run):
        """Test that balanced tool usage doesn't trigger drift."""
        session_id = str(uuid4())
        base_time = datetime.now()
        runs = []
        # 5 exploration tools out of 12 = ~41%, below 60% threshold
        for i in range(5):
            runs.append(make_run(run_type="tool", name="Glob", session_id=session_id, start_time=base_time + timedelta(seconds=i)))
        for i in range(7):
            runs.append(make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=5 + i)))
        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        drift_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXPLORATION_DRIFT]
        assert len(drift_patterns) == 0


class TestDetectMissingContext:
    """Tests for FP-003: Missing Context Requests detection."""

    def test_detect_missing_context(self, mock_service, session_with_user_questions):
        """Test that multiple user questions are detected."""
        mock_service.list_runs.return_value = session_with_user_questions

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        context_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.MISSING_CONTEXT]
        assert len(context_patterns) == 1
        assert "AskUserQuestion" in context_patterns[0].description

    def test_no_pattern_with_few_questions(self, mock_service, make_run):
        """Test that 3 or fewer questions doesn't trigger pattern."""
        session_id = str(uuid4())
        base_time = datetime.now()
        runs = [
            make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time),
            make_run(run_type="tool", name="AskUserQuestion", session_id=session_id, start_time=base_time + timedelta(seconds=1)),
            make_run(run_type="tool", name="Edit", session_id=session_id, start_time=base_time + timedelta(seconds=2)),
        ]
        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        context_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.MISSING_CONTEXT]
        assert len(context_patterns) == 0


class TestDetectSchemaViolations:
    """Tests for FP-004: Output Schema Violations detection."""

    def test_detect_schema_violations(self, mock_service, session_with_schema_errors):
        """Test that schema errors are detected."""
        mock_service.list_runs.return_value = session_with_schema_errors

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        schema_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.SCHEMA_VIOLATIONS]
        assert len(schema_patterns) == 1
        assert "schema" in schema_patterns[0].description.lower() or "format" in schema_patterns[0].description.lower()

    def test_no_pattern_without_schema_errors(self, mock_service, make_run):
        """Test that generic errors don't trigger schema pattern."""
        runs = [
            make_run(status="error", error="Connection timeout"),
            make_run(status="success"),
        ]
        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        schema_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.SCHEMA_VIOLATIONS]
        assert len(schema_patterns) == 0


class TestDetectConventionViolations:
    """Tests for FP-005: Convention Violations detection."""

    def test_detect_convention_violations(self, mock_service, session_with_convention_violations):
        """Test that naming fixes are detected."""
        mock_service.list_runs.return_value = session_with_convention_violations

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        convention_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.CONVENTION_VIOLATIONS]
        assert len(convention_patterns) == 1


class TestDetectAutomatablePatterns:
    """Tests for FP-006: Automatable Patterns detection."""

    def test_detect_automatable_patterns(self, mock_service, session_with_repeated_sequences):
        """Test that repeated sequences are detected."""
        mock_service.list_runs.return_value = session_with_repeated_sequences

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        auto_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.AUTOMATABLE_PATTERNS]
        assert len(auto_patterns) == 1
        assert "repeated" in auto_patterns[0].description.lower()


class TestNoFrictionCleanSession:
    """Tests for clean sessions with no friction."""

    def test_no_friction_clean_session(self, mock_service, clean_session):
        """Test that clean sessions have no patterns detected."""
        mock_service.list_runs.return_value = clean_session

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        assert report.has_friction is False
        assert len(report.patterns) == 0

    def test_empty_runs_no_friction(self, mock_service):
        """Test that empty run list produces no friction."""
        mock_service.list_runs.return_value = []

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        assert report.has_friction is False
        assert report.analyzed_runs == 0


class TestSeverityClassification:
    """Tests for severity classification."""

    def test_high_severity_high_frequency(self, mock_service, make_run):
        """Test that high frequency patterns get high severity."""
        # Create a scenario where >50% of sessions have retries
        session_id = str(uuid4())
        base_time = datetime.now()
        runs = []
        # 4 consecutive errors in a single session
        for i in range(4):
            runs.append(make_run(session_id=session_id, status="error", start_time=base_time + timedelta(seconds=i)))
        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        retry_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXCESSIVE_RETRIES]
        # With 1 session having retries out of 1 total, ratio = 1.0 > 0.5 = HIGH
        if retry_patterns:
            assert retry_patterns[0].severity == Severity.HIGH

    def test_low_severity_low_frequency(self, mock_service, make_run):
        """Test that low frequency patterns get low severity."""
        # Create many clean sessions and one with retries
        runs = []
        # One session with retries
        session_with_retries = str(uuid4())
        base_time = datetime.now()
        for i in range(3):
            runs.append(make_run(session_id=session_with_retries, status="error", start_time=base_time + timedelta(seconds=i)))

        # Five clean sessions
        for j in range(5):
            clean_session = str(uuid4())
            runs.append(make_run(session_id=clean_session, status="success", start_time=base_time + timedelta(seconds=10 + j)))

        mock_service.list_runs.return_value = runs

        analyzer = FrictionAnalyzer(service=mock_service)
        report = analyzer.analyze("test-project")

        retry_patterns = [p for p in report.patterns if p.pattern_type == FrictionPatternType.EXCESSIVE_RETRIES]
        # With 1 session having retries out of 6 total, ratio ~0.16 < 0.2 = LOW
        if retry_patterns:
            assert retry_patterns[0].severity == Severity.LOW


# ============================================================
# ResolutionRecommender tests
# ============================================================


class TestResolutionRecommender:
    """Tests for resolution recommendations."""

    def test_recommend_for_retry_pattern(self):
        """Test recommendations for excessive retries."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[FrictionPattern(
                pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                severity=Severity.HIGH,
                description="Found retries",
            )],
        )

        recommender = ResolutionRecommender()
        plan = recommender.recommend(report)

        assert len(plan.recommendations) == 1
        rec = plan.recommendations[0]
        assert rec.pattern_type == FrictionPatternType.EXCESSIVE_RETRIES
        assert rec.resolution_type == ResolutionType.GUIDANCE_UPDATE
        assert len(rec.target_locations) > 0

    def test_recommend_for_cli_offload_pattern(self):
        """Test recommendations suggest CLI offload for convention violations."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[FrictionPattern(
                pattern_type=FrictionPatternType.CONVENTION_VIOLATIONS,
                severity=Severity.MEDIUM,
                description="Naming issues",
            )],
        )

        recommender = ResolutionRecommender()
        plan = recommender.recommend(report)

        assert len(plan.recommendations) == 1
        rec = plan.recommendations[0]
        assert rec.resolution_type == ResolutionType.CLI_OFFLOAD

    def test_recommend_generates_next_steps(self):
        """Test that next steps are generated."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[
                FrictionPattern(
                    pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                    severity=Severity.HIGH,
                    description="Retries",
                ),
                FrictionPattern(
                    pattern_type=FrictionPatternType.CONVENTION_VIOLATIONS,
                    severity=Severity.MEDIUM,
                    description="Conventions",
                ),
            ],
        )

        recommender = ResolutionRecommender()
        plan = recommender.recommend(report)

        assert len(plan.next_steps) >= 2
        assert any("GUIDANCE_UPDATE" in step for step in plan.next_steps)
        assert any("CLI_OFFLOAD" in step for step in plan.next_steps)

    def test_recommend_empty_report(self):
        """Test recommendations for report with no friction."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[],
        )

        recommender = ResolutionRecommender()
        plan = recommender.recommend(report)

        assert len(plan.recommendations) == 0
        assert len(plan.next_steps) == 1
        assert "no action" in plan.next_steps[0].lower()

    def test_resolution_plan_to_dict(self):
        """Test ResolutionPlan serialization."""
        plan = ResolutionPlan(
            recommendations=[
                ResolutionRecommendation(
                    pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                    resolution_type=ResolutionType.GUIDANCE_UPDATE,
                    description="Fix retries",
                    target_locations=["process.yml"],
                    suggested_changes=["Add retry limit"],
                    priority="high",
                ),
            ],
            next_steps=["Update guidance files"],
        )

        result = plan.to_dict()

        assert result["total_recommendations"] == 1
        assert result["by_resolution_type"]["GUIDANCE_UPDATE"] == 1
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["pattern_type"] == "FP-001"

    def test_recommendations_sorted_by_priority(self):
        """Test that recommendations are sorted high -> medium -> low."""
        report = FrictionReport(
            project_name="test",
            analyzed_runs=100,
            timeframe_days=7,
            patterns=[
                FrictionPattern(
                    pattern_type=FrictionPatternType.MISSING_CONTEXT,
                    severity=Severity.LOW,
                    description="Low severity",
                ),
                FrictionPattern(
                    pattern_type=FrictionPatternType.EXCESSIVE_RETRIES,
                    severity=Severity.HIGH,
                    description="High severity",
                ),
                FrictionPattern(
                    pattern_type=FrictionPatternType.EXPLORATION_DRIFT,
                    severity=Severity.MEDIUM,
                    description="Medium severity",
                ),
            ],
        )

        recommender = ResolutionRecommender()
        plan = recommender.recommend(report)

        priorities = [rec.priority for rec in plan.recommendations]
        assert priorities == ["high", "medium", "low"]
