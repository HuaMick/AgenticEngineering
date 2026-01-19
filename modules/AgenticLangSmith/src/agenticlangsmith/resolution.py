"""Resolution recommendations for detected friction patterns."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .friction import FrictionPattern, FrictionPatternType, FrictionReport


class ResolutionType(Enum):
    """Types of resolution strategies."""

    GUIDANCE_UPDATE = "GUIDANCE_UPDATE"
    CLI_OFFLOAD = "CLI_OFFLOAD"
    ASSET_UPDATE = "ASSET_UPDATE"


@dataclass
class ResolutionRecommendation:
    """A specific resolution recommendation for a friction pattern."""

    pattern_type: FrictionPatternType
    resolution_type: ResolutionType
    description: str
    target_locations: list[str] = field(default_factory=list)
    suggested_changes: list[str] = field(default_factory=list)
    evidence_summary: str = ""
    priority: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_type": self.pattern_type.value,
            "resolution_type": self.resolution_type.value,
            "description": self.description,
            "target_locations": self.target_locations,
            "suggested_changes": self.suggested_changes,
            "evidence_summary": self.evidence_summary,
            "priority": self.priority,
        }


@dataclass
class ResolutionPlan:
    """Complete resolution plan for a friction report."""

    recommendations: list[ResolutionRecommendation] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "next_steps": self.next_steps,
            "total_recommendations": len(self.recommendations),
            "by_resolution_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count recommendations by resolution type."""
        counts = {rt.value: 0 for rt in ResolutionType}
        for rec in self.recommendations:
            counts[rec.resolution_type.value] += 1
        return counts


class ResolutionRecommender:
    """Generates resolution recommendations from friction patterns."""

    # Default resolution mappings per pattern type
    PATTERN_RESOLUTIONS = {
        FrictionPatternType.EXCESSIVE_RETRIES: {
            "type": ResolutionType.GUIDANCE_UPDATE,
            "locations": [
                "modules/AgenticGuidance/agents/*/process.yml",
                "modules/AgenticGuidance/assets/guidelines/",
            ],
            "changes": [
                "Add retry limit fence in error handling section",
                "Add clearer error recovery guidance",
                "Document expected failure modes",
            ],
        },
        FrictionPatternType.EXPLORATION_DRIFT: {
            "type": ResolutionType.GUIDANCE_UPDATE,
            "locations": [
                "modules/AgenticGuidance/agents/*/inputs.yml",
                "modules/AgenticGuidance/agents/*/process.yml",
            ],
            "changes": [
                "Add path hints or signposts for common locations",
                "Document file structure conventions",
                "Add shortcut references to frequently accessed files",
            ],
        },
        FrictionPatternType.MISSING_CONTEXT: {
            "type": ResolutionType.GUIDANCE_UPDATE,
            "locations": [
                "modules/AgenticGuidance/agents/*/process.yml",
                "modules/AgenticGuidance/agents/*/inputs.yml",
            ],
            "changes": [
                "Add missing context to process files",
                "Document common decisions and their defaults",
                "Add examples for ambiguous scenarios",
            ],
        },
        FrictionPatternType.SCHEMA_VIOLATIONS: {
            "type": ResolutionType.ASSET_UPDATE,
            "locations": [
                "modules/AgenticGuidance/assets/examples/",
                "modules/AgenticGuidance/assets/specifications/",
            ],
            "changes": [
                "Add output schema documentation",
                "Create example files showing correct formats",
                "Add validation checklist to process files",
            ],
        },
        FrictionPatternType.CONVENTION_VIOLATIONS: {
            "type": ResolutionType.CLI_OFFLOAD,
            "locations": [
                "modules/AgenticCLI/src/agenticcli/commands/",
            ],
            "changes": [
                "Create CLI command to enforce naming conventions",
                "Add validation to existing CLI commands",
                "Document conventions in CLI help text",
            ],
        },
        FrictionPatternType.AUTOMATABLE_PATTERNS: {
            "type": ResolutionType.CLI_OFFLOAD,
            "locations": [
                "modules/AgenticCLI/src/agenticcli/commands/",
            ],
            "changes": [
                "Create new agentic command for the repeated pattern",
                "Add command to reduce manual steps",
                "Document usage in CLI help",
            ],
        },
    }

    def recommend(self, report: FrictionReport) -> ResolutionPlan:
        """Generate resolution recommendations from a friction report.

        Args:
            report: FrictionReport with detected patterns.

        Returns:
            ResolutionPlan with recommendations and next steps.
        """
        recommendations = []

        for pattern in report.patterns:
            rec = self._recommend_for_pattern(pattern)
            recommendations.append(rec)

        # Sort by priority (high first)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 1))

        # Generate next steps
        next_steps = self._generate_next_steps(recommendations)

        return ResolutionPlan(
            recommendations=recommendations,
            next_steps=next_steps,
        )

    def _recommend_for_pattern(self, pattern: FrictionPattern) -> ResolutionRecommendation:
        """Generate recommendation for a single pattern."""
        mapping = self.PATTERN_RESOLUTIONS.get(pattern.pattern_type, {})

        resolution_type = mapping.get("type", ResolutionType.GUIDANCE_UPDATE)
        locations = mapping.get("locations", [])
        changes = mapping.get("changes", [])

        # Build evidence summary
        evidence_summary = pattern.description
        if pattern.frequency > 1:
            evidence_summary += f" (occurred {pattern.frequency} times)"

        # Determine priority from severity
        priority = pattern.severity.value

        return ResolutionRecommendation(
            pattern_type=pattern.pattern_type,
            resolution_type=resolution_type,
            description=pattern.suggested_resolution or f"Address {pattern.pattern_type.name}",
            target_locations=locations,
            suggested_changes=changes,
            evidence_summary=evidence_summary,
            priority=priority,
        )

    def _generate_next_steps(self, recommendations: list[ResolutionRecommendation]) -> list[str]:
        """Generate actionable next steps from recommendations."""
        steps = []

        # Count by type
        guidance_count = sum(1 for r in recommendations if r.resolution_type == ResolutionType.GUIDANCE_UPDATE)
        cli_count = sum(1 for r in recommendations if r.resolution_type == ResolutionType.CLI_OFFLOAD)
        asset_count = sum(1 for r in recommendations if r.resolution_type == ResolutionType.ASSET_UPDATE)

        if guidance_count > 0:
            steps.append(
                f"GUIDANCE_UPDATE: {guidance_count} recommendation(s) - "
                "Reference @modules/AgenticGuidance/entrypoints/_plan_teach.yml to plan guidance updates"
            )

        if cli_count > 0:
            steps.append(
                f"CLI_OFFLOAD: {cli_count} recommendation(s) - "
                "Reference @modules/AgenticGuidance/entrypoints/_plan_build.yml to plan CLI commands"
            )

        if asset_count > 0:
            steps.append(
                f"ASSET_UPDATE: {asset_count} recommendation(s) - "
                "Reference @modules/AgenticGuidance/entrypoints/_plan_teach.yml to plan asset updates"
            )

        if not steps:
            steps.append("No friction detected - no action required")

        return steps
