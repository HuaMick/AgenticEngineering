"""LangSmith service wrapper for querying traces and runs."""

import os
from typing import Any, Optional

from langsmith import Client
from langsmith.schemas import Run


class LangSmithConfigError(Exception):
    """Raised when LangSmith configuration is missing or invalid."""

    pass


class LangSmithAPIError(Exception):
    """Raised when LangSmith API calls fail."""

    pass


class LangSmithService:
    """Service for interacting with LangSmith API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize service with API key from param or environment.

        Args:
            api_key: Optional API key. If not provided, reads from LANGSMITH_API_KEY env var.

        Raises:
            LangSmithConfigError: If no API key is available.
        """
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        if not self.api_key:
            raise LangSmithConfigError(
                "LANGSMITH_API_KEY environment variable not set. "
                "Set it or pass api_key parameter."
            )
        try:
            self._client = Client(api_key=self.api_key)
        except Exception as e:
            raise LangSmithAPIError(f"Failed to initialize LangSmith client: {e}") from e

    def _run_to_dict(self, run: Run) -> dict[str, Any]:
        """Convert a Run object to a dictionary with relevant fields.

        Args:
            run: A LangSmith Run object.

        Returns:
            Dictionary with run details.
        """
        # Calculate latency if timing info available
        latency = None
        if run.end_time and run.start_time:
            latency = (run.end_time - run.start_time).total_seconds()

        # Extract token counts from feedback or run data
        total_tokens = None
        if run.total_tokens is not None:
            total_tokens = run.total_tokens
        elif hasattr(run, "prompt_tokens") and hasattr(run, "completion_tokens"):
            if run.prompt_tokens is not None and run.completion_tokens is not None:
                total_tokens = run.prompt_tokens + run.completion_tokens

        # Determine status
        status = "success"
        if run.error:
            status = "error"
        elif run.end_time is None:
            status = "running"

        return {
            "id": str(run.id),
            "name": run.name,
            "run_type": run.run_type,
            "latency": latency,
            "total_tokens": total_tokens,
            "prompt_tokens": getattr(run, "prompt_tokens", None),
            "completion_tokens": getattr(run, "completion_tokens", None),
            "status": status,
            "error": run.error,
            "start_time": run.start_time.isoformat() if run.start_time else None,
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "inputs": run.inputs,
            "outputs": run.outputs,
            "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
            "session_id": str(run.session_id) if run.session_id else None,
            "tags": run.tags or [],
            "extra": run.extra,
        }

    def list_runs(
        self,
        project_name: Optional[str] = None,
        limit: int = 20,
        run_type: Optional[str] = None,
        error_only: bool = False,
        filter_expr: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List recent runs with optional filters.

        Args:
            project_name: Filter by project name. If None, uses default project.
            limit: Maximum number of runs to return.
            run_type: Filter by run type (llm, chain, tool, retriever).
            error_only: If True, only return runs with errors.
            filter_expr: Optional filter expression string.

        Returns:
            List of dicts with run details: id, name, run_type, latency,
            total_tokens, status, error.

        Raises:
            LangSmithAPIError: If the API call fails.
        """
        try:
            # Build kwargs for list_runs
            kwargs: dict[str, Any] = {"limit": limit}

            if project_name:
                kwargs["project_name"] = project_name

            if run_type:
                kwargs["run_type"] = run_type

            if error_only:
                kwargs["error"] = True

            if filter_expr:
                kwargs["filter"] = filter_expr

            runs = self._client.list_runs(**kwargs)
            return [self._run_to_dict(run) for run in runs]

        except Exception as e:
            raise LangSmithAPIError(f"Failed to list runs: {e}") from e

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Get detailed info for a single run.

        Args:
            run_id: The UUID of the run to retrieve.

        Returns:
            Dictionary with full run details.

        Raises:
            LangSmithAPIError: If the API call fails or run not found.
        """
        try:
            run = self._client.read_run(run_id)
            return self._run_to_dict(run)
        except Exception as e:
            raise LangSmithAPIError(f"Failed to get run {run_id}: {e}") from e

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects in the workspace.

        Returns:
            List of dicts with project details: id, name, description,
            created_at, run_count.

        Raises:
            LangSmithAPIError: If the API call fails.
        """
        try:
            projects = self._client.list_projects()
            result = []
            for project in projects:
                result.append({
                    "id": str(project.id),
                    "name": project.name,
                    "description": project.description,
                    "created_at": (
                        project.created_at.isoformat() if project.created_at else None
                    ),
                    "run_count": getattr(project, "run_count", None),
                    "extra": project.extra,
                })
            return result
        except Exception as e:
            raise LangSmithAPIError(f"Failed to list projects: {e}") from e

    def get_project_stats(self, project_name: str, limit: int = 100) -> dict[str, Any]:
        """Get aggregated statistics for a project.

        Args:
            project_name: The name of the project to get stats for.
            limit: Number of recent runs to analyze for statistics.

        Returns:
            Dictionary with aggregated statistics including:
            - total_runs: Total number of runs analyzed
            - error_count: Number of runs with errors
            - error_rate: Percentage of runs with errors
            - avg_latency: Average latency in seconds
            - total_tokens: Total tokens used across all runs
            - run_types: Count of each run type

        Raises:
            LangSmithAPIError: If the API call fails.
        """
        try:
            runs = self.list_runs(project_name=project_name, limit=limit)

            total_runs = len(runs)
            error_count = sum(1 for r in runs if r["status"] == "error")
            error_rate = (error_count / total_runs * 100) if total_runs > 0 else 0

            latencies = [r["latency"] for r in runs if r["latency"] is not None]
            avg_latency = sum(latencies) / len(latencies) if latencies else None

            total_tokens = sum(r["total_tokens"] or 0 for r in runs)

            run_types: dict[str, int] = {}
            for r in runs:
                rt = r["run_type"]
                run_types[rt] = run_types.get(rt, 0) + 1

            return {
                "project_name": project_name,
                "total_runs": total_runs,
                "error_count": error_count,
                "error_rate": round(error_rate, 2),
                "avg_latency": round(avg_latency, 3) if avg_latency else None,
                "total_tokens": total_tokens,
                "run_types": run_types,
            }
        except LangSmithAPIError:
            raise
        except Exception as e:
            raise LangSmithAPIError(f"Failed to get project stats for {project_name}: {e}") from e

    def get_run_url(self, run_id: str) -> str:
        """Generate shareable URL for a run.

        Args:
            run_id: The UUID of the run.

        Returns:
            URL string to view the run in LangSmith web interface.

        Raises:
            LangSmithAPIError: If URL generation fails.
        """
        try:
            # Try using the client's built-in method if available
            if hasattr(self._client, "get_run_url"):
                return self._client.get_run_url(run_id=run_id)

            # Fallback: construct URL manually
            # LangSmith URLs typically follow: https://smith.langchain.com/...
            # We need the run details to construct the URL properly
            run = self._client.read_run(run_id)

            # Get the base URL from environment or use default
            base_url = os.environ.get("LANGSMITH_ENDPOINT", "https://smith.langchain.com")

            # Construct URL - format may vary based on LangSmith version
            if run.session_id:
                return f"{base_url}/o/default/projects/p/{run.session_id}/r/{run_id}"
            else:
                return f"{base_url}/runs/{run_id}"

        except Exception as e:
            raise LangSmithAPIError(f"Failed to generate URL for run {run_id}: {e}") from e

    def get_run_feedback(self, run_id: str) -> list[dict[str, Any]]:
        """Get feedback for a specific run.

        Args:
            run_id: The UUID of the run.

        Returns:
            List of feedback items with scores and comments.

        Raises:
            LangSmithAPIError: If the API call fails.
        """
        try:
            feedbacks = self._client.list_feedback(run_ids=[run_id])
            result = []
            for fb in feedbacks:
                result.append({
                    "id": str(fb.id),
                    "key": fb.key,
                    "score": fb.score,
                    "value": fb.value,
                    "comment": fb.comment,
                    "created_at": fb.created_at.isoformat() if fb.created_at else None,
                })
            return result
        except Exception as e:
            raise LangSmithAPIError(f"Failed to get feedback for run {run_id}: {e}") from e
