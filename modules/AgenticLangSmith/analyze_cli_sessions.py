#!/usr/bin/env python3
"""Analyze LangSmith traces to find sessions with CLI context injection and test sessions."""

import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from langsmith import Client


def search_text_for_keywords(text: str, keywords: list[str]) -> list[str]:
    """Search text for keywords (case insensitive)."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def extract_tool_calls(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool calls from a run's inputs/outputs."""
    tool_calls = []

    # Check if this is a tool run
    if run.get("run_type") == "tool":
        tool_calls.append({
            "name": run.get("name", "unknown"),
            "run_id": run.get("id"),
        })

    # Check inputs for tool call info
    inputs = run.get("inputs", {})
    if inputs:
        # Look for tool-related keys
        if isinstance(inputs, dict):
            if "tool" in inputs:
                tool_calls.append({"name": inputs.get("tool"), "source": "input"})
            if "tool_calls" in inputs:
                for tc in inputs.get("tool_calls", []):
                    if isinstance(tc, dict):
                        tool_calls.append({
                            "name": tc.get("name") or tc.get("function", {}).get("name"),
                            "source": "input"
                        })

    return tool_calls


def search_run_for_keywords(run: dict[str, Any], keywords: list[str]) -> dict[str, list[str]]:
    """Search a run's inputs and outputs for keywords."""
    found = {"inputs": [], "outputs": [], "name": []}

    # Search name
    if run.get("name"):
        found["name"] = search_text_for_keywords(run["name"], keywords)

    # Search inputs
    inputs = run.get("inputs")
    if inputs:
        inputs_str = json.dumps(inputs) if isinstance(inputs, dict) else str(inputs)
        found["inputs"] = search_text_for_keywords(inputs_str, keywords)

    # Search outputs
    outputs = run.get("outputs")
    if outputs:
        outputs_str = json.dumps(outputs) if isinstance(outputs, dict) else str(outputs)
        found["outputs"] = search_text_for_keywords(outputs_str, keywords)

    return found


def run_to_dict(run) -> dict[str, Any]:
    """Convert a Run object to a dictionary."""
    latency = None
    if run.end_time and run.start_time:
        latency = (run.end_time - run.start_time).total_seconds()

    return {
        "id": str(run.id),
        "name": run.name,
        "run_type": run.run_type,
        "latency": latency,
        "status": "error" if run.error else ("running" if not run.end_time else "success"),
        "error": run.error,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "inputs": run.inputs,
        "outputs": run.outputs,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "session_id": str(run.session_id) if run.session_id else None,
        "tags": run.tags or [],
        "trace_id": str(run.trace_id) if hasattr(run, 'trace_id') and run.trace_id else None,
    }


def main():
    # Configuration
    API_KEY = "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"
    PROJECTS = [
        "AgenticEngineering-agenticlangsmith",
        "AgenticEngineering-agentic-cli",
        "AgenticEngineering",
    ]
    RUNS_PER_PROJECT = 200
    BATCH_SIZE = 100  # LangSmith API limit

    # Keywords to search for
    KEYWORDS = [
        "context injection",
        "context-injection",
        "agentic",
        "cli",
        "inject",
        "skill",
        "bash",
        "test",
    ]

    # CLI-related tool names
    CLI_TOOLS = ["Bash", "Skill", "bash", "skill"]

    print("Initializing LangSmith client...")
    client = Client(api_key=API_KEY)

    # First list available projects
    print("\nListing available projects...")
    try:
        projects = list(client.list_projects())
        print(f"Found {len(projects)} projects:")
        for p in projects:
            print(f"  - {p.name}")

        # Update PROJECTS to use actual project names
        available_project_names = [p.name for p in projects]
    except Exception as e:
        print(f"Error listing projects: {e}")
        available_project_names = []

    # Collect all runs from all projects
    all_runs = []
    project_run_counts = {}

    for project in PROJECTS:
        # Check if project exists
        if available_project_names and project not in available_project_names:
            print(f"\nSkipping project {project} (not found in workspace)")
            # Try partial matching
            matches = [p for p in available_project_names if project.lower() in p.lower() or p.lower() in project.lower()]
            if matches:
                print(f"  Did you mean: {matches}?")
            project_run_counts[project] = 0
            continue

        print(f"\nQuerying project: {project}")
        try:
            # Paginate to get more runs
            collected_runs = []
            batches_needed = (RUNS_PER_PROJECT + BATCH_SIZE - 1) // BATCH_SIZE

            for batch_num in range(batches_needed):
                remaining = RUNS_PER_PROJECT - len(collected_runs)
                batch_limit = min(BATCH_SIZE, remaining)

                if batch_limit <= 0:
                    break

                runs = list(client.list_runs(
                    project_name=project,
                    limit=batch_limit,
                    # Use offset for pagination if available
                ))

                if not runs:
                    break

                collected_runs.extend([run_to_dict(r) for r in runs])
                print(f"  Batch {batch_num + 1}: {len(runs)} runs (total: {len(collected_runs)})")

                # If we got less than requested, no more data
                if len(runs) < batch_limit:
                    break

            project_run_counts[project] = len(collected_runs)
            all_runs.extend(collected_runs)
            print(f"  Total found: {len(collected_runs)} runs")
        except Exception as e:
            print(f"  Error querying project: {e}")
            project_run_counts[project] = 0

    print(f"\nTotal runs collected: {len(all_runs)}")

    # Group runs by session_id
    sessions = defaultdict(list)
    runs_without_session = []

    for run in all_runs:
        session_id = run.get("session_id")
        if session_id:
            sessions[session_id].append(run)
        else:
            runs_without_session.append(run)

    print(f"Unique sessions found: {len(sessions)}")
    print(f"Runs without session_id: {len(runs_without_session)}")

    # Analyze each session
    session_summaries = []

    for session_id, runs in sessions.items():
        # Sort runs by start_time
        runs_sorted = sorted(runs, key=lambda r: r.get("start_time") or "")

        # Calculate time range
        start_times = [r["start_time"] for r in runs_sorted if r.get("start_time")]
        end_times = [r["end_time"] for r in runs_sorted if r.get("end_time")]

        time_range = {
            "earliest": min(start_times) if start_times else None,
            "latest": max(end_times) if end_times else None,
        }

        # Extract tool calls
        all_tool_calls = []
        cli_tool_calls = []

        for run in runs_sorted:
            tool_calls = extract_tool_calls(run)
            all_tool_calls.extend(tool_calls)

            # Check for CLI-related tools
            if run.get("name") in CLI_TOOLS or run.get("run_type") == "tool":
                if any(t in (run.get("name") or "") for t in CLI_TOOLS):
                    cli_tool_calls.append({
                        "name": run.get("name"),
                        "run_id": run.get("id"),
                        "status": run.get("status"),
                    })

        # Search for keywords
        keyword_matches = defaultdict(list)
        for run in runs_sorted:
            matches = search_run_for_keywords(run, KEYWORDS)
            for location, found_keywords in matches.items():
                if found_keywords:
                    keyword_matches[location].extend(found_keywords)

        # Deduplicate keywords
        keyword_matches = {k: list(set(v)) for k, v in keyword_matches.items()}

        # Count run types
        run_types = defaultdict(int)
        for run in runs_sorted:
            run_types[run.get("run_type", "unknown")] += 1

        # Check for errors
        errors = [r for r in runs_sorted if r.get("status") == "error"]

        session_summary = {
            "session_id": session_id,
            "run_count": len(runs_sorted),
            "time_range": time_range,
            "run_types": dict(run_types),
            "cli_tool_calls": cli_tool_calls,
            "all_tool_calls_count": len(all_tool_calls),
            "keyword_matches": dict(keyword_matches),
            "error_count": len(errors),
            "has_cli_activity": len(cli_tool_calls) > 0,
            "has_keyword_matches": any(keyword_matches.values()),
        }

        session_summaries.append(session_summary)

    # Sort sessions by relevance (CLI activity + keyword matches)
    session_summaries.sort(
        key=lambda s: (s["has_cli_activity"], s["has_keyword_matches"], s["run_count"]),
        reverse=True
    )

    # Build final report
    report = {
        "query_timestamp": datetime.now().isoformat(),
        "projects_queried": PROJECTS,
        "project_run_counts": project_run_counts,
        "total_runs": len(all_runs),
        "total_sessions": len(sessions),
        "runs_without_session": len(runs_without_session),
        "sessions_with_cli_activity": sum(1 for s in session_summaries if s["has_cli_activity"]),
        "sessions_with_keyword_matches": sum(1 for s in session_summaries if s["has_keyword_matches"]),
        "sessions": session_summaries,
    }

    # Print summary
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY")
    print("="*80)
    print(f"Total sessions analyzed: {report['total_sessions']}")
    print(f"Sessions with CLI activity (Bash/Skill tools): {report['sessions_with_cli_activity']}")
    print(f"Sessions with keyword matches: {report['sessions_with_keyword_matches']}")

    # Print interesting sessions
    print("\n" + "-"*80)
    print("TOP SESSIONS WITH CLI ACTIVITY OR KEYWORD MATCHES:")
    print("-"*80)

    interesting_sessions = [s for s in session_summaries if s["has_cli_activity"] or s["has_keyword_matches"]][:10]

    for i, session in enumerate(interesting_sessions, 1):
        print(f"\n{i}. Session: {session['session_id'][:16]}...")
        print(f"   Runs: {session['run_count']}")
        print(f"   Time range: {session['time_range']['earliest']} to {session['time_range']['latest']}")
        print(f"   Run types: {session['run_types']}")
        if session['cli_tool_calls']:
            print(f"   CLI tools used: {len(session['cli_tool_calls'])} calls")
            for tc in session['cli_tool_calls'][:5]:
                print(f"      - {tc['name']} ({tc['status']})")
        if session['keyword_matches']:
            print(f"   Keywords found:")
            for loc, kws in session['keyword_matches'].items():
                if kws:
                    print(f"      - {loc}: {', '.join(kws)}")
        if session['error_count'] > 0:
            print(f"   Errors: {session['error_count']}")

    # Find runs specifically mentioning "inject" for detailed analysis
    print("\n" + "-"*80)
    print("DETAILED INJECT KEYWORD ANALYSIS:")
    print("-"*80)

    inject_runs = []
    for run in all_runs:
        inputs_str = json.dumps(run.get("inputs", {})) if run.get("inputs") else ""
        outputs_str = json.dumps(run.get("outputs", {})) if run.get("outputs") else ""
        combined = inputs_str + outputs_str

        if "inject" in combined.lower():
            # Extract context around "inject"
            inject_contexts = []
            for text, source in [(inputs_str, "inputs"), (outputs_str, "outputs")]:
                if "inject" in text.lower():
                    # Find all occurrences
                    lower_text = text.lower()
                    idx = 0
                    while True:
                        idx = lower_text.find("inject", idx)
                        if idx == -1:
                            break
                        # Extract context (100 chars before and after)
                        start = max(0, idx - 100)
                        end = min(len(text), idx + 106)
                        context = text[start:end]
                        inject_contexts.append({
                            "source": source,
                            "context": context,
                        })
                        idx += 1

            inject_runs.append({
                "run_id": run.get("id"),
                "name": run.get("name"),
                "run_type": run.get("run_type"),
                "session_id": run.get("session_id"),
                "contexts": inject_contexts[:3],  # Limit to 3 contexts per run
            })

    print(f"Found {len(inject_runs)} runs mentioning 'inject'")
    for i, run in enumerate(inject_runs[:10], 1):
        print(f"\n{i}. Run: {run['name']} ({run['run_type']})")
        print(f"   ID: {run['run_id']}")
        for ctx in run['contexts'][:2]:
            # Clean up context for display
            clean_ctx = ctx['context'].replace('\n', ' ').replace('\\n', ' ')[:200]
            print(f"   [{ctx['source']}]: ...{clean_ctx}...")

    # Add inject analysis to report
    report["inject_keyword_analysis"] = {
        "runs_with_inject": len(inject_runs),
        "sample_runs": inject_runs[:10],
    }

    # Output full JSON report
    output_path = "/home/code/AgenticEngineering/modules/AgenticLangSmith/cli_session_analysis.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n\nFull JSON report written to: {output_path}")
    print("\n" + "="*80)

    return report


if __name__ == "__main__":
    main()
