"""MCP Server for Orchestration Monitoring.

Provides a live dashboard for monitoring agentic orchestration sessions
and their progress through plan diagrams.

Configuration:
    AGENTIC_PLANS_DIR: Path to plans directory (default: auto-discovered via git)
    AGENTIC_PROJECT_ROOT: Path to project root (default: auto-discovered via git)

Usage:
    # Run as standalone server
    python -m agenticcli.mcp.orchestration_server

    # Or use the console script entry point
    agentic-mcp-orchestration
"""

import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("OrchestrationMonitor")


def get_project_root() -> Path | None:
    """Discover the project root using git or environment variable.

    Checks in order:
        1. AGENTIC_PROJECT_ROOT environment variable
        2. Git repository root (via git rev-parse --show-toplevel)

    Returns:
        Path to project root, or None if not discoverable.
    """
    # Check environment variable first
    env_root = os.environ.get("AGENTIC_PROJECT_ROOT")
    if env_root:
        root_path = Path(env_root)
        if root_path.exists():
            return root_path

    # Fall back to git discovery
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_plans_dir() -> Path | None:
    """Get the plans directory path.

    Checks in order:
        1. AGENTIC_PLANS_DIR environment variable
        2. {project_root}/docs/plans/live

    Returns:
        Path to live plans directory, or None if not found.
    """
    # Check environment variable first
    env_plans = os.environ.get("AGENTIC_PLANS_DIR")
    if env_plans:
        plans_path = Path(env_plans)
        if plans_path.exists():
            return plans_path

    # Fall back to standard location relative to project root
    project_root = get_project_root()
    if project_root:
        plans_dir = project_root / "docs" / "plans" / "live"
        if plans_dir.exists():
            return plans_dir

    return None


def get_agentic_data():
    """Fetches active sessions and loops from agentic CLI."""
    try:
        # Get active sessions
        sessions_res = subprocess.run(["agentic", "-j", "session", "list", "--active"], capture_output=True, text=True)
        sessions = json.loads(sessions_res.stdout) if sessions_res.returncode == 0 else []

        # Get active loops
        loops_res = subprocess.run(["agentic", "-j", "loop", "history", "--active"], capture_output=True, text=True)
        loops = json.loads(loops_res.stdout) if loops_res.returncode == 0 else []

        return sessions, loops
    except Exception as e:
        return [], []

def find_current_plan() -> Path | None:
    """Find the most recently modified live plan folder.

    Uses configurable plans directory (see get_plans_dir).

    Returns:
        Path to the most recently modified plan folder, or None if no plans found.
    """
    plans_dir = get_plans_dir()
    if plans_dir is None or not plans_dir.exists():
        return None

    plans = [d for d in plans_dir.iterdir() if d.is_dir()]
    if not plans:
        return None

    # Sort by modification time of the folder
    plans.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return plans[0]

@mcp.tool()
def show_orchestration():
    """
    Displays a live, interactive dashboard of the current agentic orchestration.
    Highlights active agents and their progress on the Mermaid diagram.
    """
    plan_path = find_current_plan()
    if not plan_path:
        return "No active plan found in docs/plans/live."

    # Find the .mmd file
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    if not mmd_files:
        return f"No orchestration diagram found in {plan_path.name}"

    mmd_content = mmd_files[0].read_text()
    sessions, loops = get_agentic_data()

    # Simple mapping: if a session/loop prompt contains a node label, mark it active
    active_nodes = []
    for s in sessions:
        # Check sessions
        prompt = s.get("prompt", "").lower()
        for line in mmd_content.splitlines():
            if "[" in line and "]" in line:
                label = line.split("[")[1].split("]")[0].lower()
                if label in prompt or prompt in label:
                    node_id = line.split("[")[0].strip()
                    active_nodes.append(node_id)

    # Generate the status HTML
    active_css = ""
    for node_id in active_nodes:
        active_css += f"style {node_id} fill:#3b82f6,stroke:#60a5fa,stroke-width:4px,stroke-dasharray: 5 5;\n"

    # Full HTML for the dashboard with premium Glassmorphism UI
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        *, *::before, *::after {{
            box-sizing: border-box;
        }}

        body {{
            background: linear-gradient(135deg, #0c1222 0%, #1a1f3a 25%, #0f172a 50%, #1e1b4b 75%, #0c1222 100%);
            background-size: 400% 400%;
            animation: gradientShift 15s ease infinite;
            color: #f1f5f9;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            margin: 0;
            padding: 40px 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            overflow-x: hidden;
        }}

        /* Animated background orbs */
        body::before, body::after {{
            content: '';
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            z-index: -1;
            animation: float 20s ease-in-out infinite;
        }}
        body::before {{
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%);
            top: -200px;
            left: -100px;
        }}
        body::after {{
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(168, 85, 247, 0.35) 0%, transparent 70%);
            bottom: -150px;
            right: -100px;
            animation-delay: -7s;
        }}

        @keyframes gradientShift {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}

        @keyframes float {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            33% {{ transform: translate(30px, -30px) scale(1.05); }}
            66% {{ transform: translate(-20px, 20px) scale(0.95); }}
        }}

        .dashboard {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(30, 27, 75, 0.4) 100%);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 40px;
            width: 94%;
            max-width: 1400px;
            box-shadow:
                0 32px 64px -12px rgba(0, 0, 0, 0.6),
                0 0 0 1px rgba(255, 255, 255, 0.05) inset,
                0 1px 0 0 rgba(255, 255, 255, 0.1) inset;
            position: relative;
            overflow: hidden;
            animation: fadeInUp 0.6s ease-out;
        }}

        .dashboard::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        }}

        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .header {{
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 32px;
        }}

        .title-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            margin: 0;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
            background-size: 200% 200%;
            animation: shimmer 3s ease infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        @keyframes shimmer {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}

        .subtitle {{
            font-size: 0.875rem;
            color: #94a3b8;
            font-weight: 400;
            letter-spacing: 0.01em;
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.3s ease;
        }}

        .status-running {{
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(99, 102, 241, 0.1) 100%);
            color: #93c5fd;
            border: 1px solid rgba(96, 165, 250, 0.3);
            box-shadow:
                0 0 20px rgba(59, 130, 246, 0.15),
                0 0 40px rgba(59, 130, 246, 0.05);
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #60a5fa;
            box-shadow: 0 0 12px rgba(96, 165, 250, 0.8);
            animation: glow 2s ease-in-out infinite;
        }}

        @keyframes glow {{
            0%, 100% {{
                opacity: 1;
                box-shadow: 0 0 12px rgba(96, 165, 250, 0.8);
            }}
            50% {{
                opacity: 0.6;
                box-shadow: 0 0 20px rgba(96, 165, 250, 1), 0 0 30px rgba(96, 165, 250, 0.5);
            }}
        }}

        .diagram-container {{
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.95) 100%);
            padding: 32px;
            border-radius: 16px;
            margin: 24px 0;
            box-shadow:
                0 4px 24px rgba(0, 0, 0, 0.2),
                0 0 0 1px rgba(255, 255, 255, 0.1) inset;
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .diagram-container:hover {{
            transform: translateY(-2px);
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.25),
                0 0 0 1px rgba(255, 255, 255, 0.15) inset;
        }}

        .diagram-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
            border-radius: 16px 16px 0 0;
        }}

        .mermaid {{
            display: flex;
            justify-content: center;
        }}

        .section-title {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #64748b;
            margin: 32px 0 16px 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .section-title::before,
        .section-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(100, 116, 139, 0.3), transparent);
        }}

        .agent-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}

        .agent-card {{
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 27, 75, 0.3) 100%);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 20px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow:
                0 4px 16px rgba(0, 0, 0, 0.2),
                0 0 0 1px rgba(255, 255, 255, 0.03) inset;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            animation: slideIn 0.5s ease-out backwards;
        }}

        .agent-card:nth-child(1) {{ animation-delay: 0.1s; }}
        .agent-card:nth-child(2) {{ animation-delay: 0.2s; }}
        .agent-card:nth-child(3) {{ animation-delay: 0.3s; }}
        .agent-card:nth-child(4) {{ animation-delay: 0.4s; }}

        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateX(-20px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}

        .agent-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, #60a5fa, #a78bfa);
            border-radius: 4px 0 0 4px;
        }}

        .agent-card:hover {{
            transform: translateY(-4px) scale(1.01);
            border-color: rgba(96, 165, 250, 0.2);
            box-shadow:
                0 12px 32px rgba(0, 0, 0, 0.3),
                0 0 0 1px rgba(96, 165, 250, 0.1) inset,
                0 0 30px rgba(96, 165, 250, 0.05);
        }}

        .agent-label {{
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #64748b;
            margin-bottom: 4px;
        }}

        .agent-id {{
            font-size: 1rem;
            font-weight: 600;
            color: #e2e8f0;
            font-family: 'SF Mono', 'Fira Code', monospace;
            margin-bottom: 12px;
        }}

        .agent-task {{
            font-size: 0.875rem;
            color: #94a3b8;
            line-height: 1.5;
        }}

        .empty-state {{
            text-align: center;
            padding: 48px 24px;
            color: #64748b;
        }}

        .empty-state-icon {{
            font-size: 3rem;
            margin-bottom: 16px;
            opacity: 0.5;
        }}

        .footer {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: #475569;
        }}

        .refresh-indicator {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .refresh-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #22c55e;
            animation: blink 1s ease-in-out infinite;
        }}

        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <div class="title-row">
                <div>
                    <h1>Orchestration Dashboard</h1>
                    <p class="subtitle">{plan_path.name}</p>
                </div>
                <div class="status-badge status-running">
                    <span class="status-dot"></span>
                    Live Monitoring: {len(sessions)} Session{"s" if len(sessions) != 1 else ""} Active
                </div>
            </div>
        </div>

        <div class="diagram-container">
            <div class="mermaid">
{mmd_content}
{active_css}
            </div>
        </div>

        <div class="section-title">Active Agents</div>

        <div class="agent-list">
            {"".join([f'''<div class="agent-card">
                <div class="agent-label">Agent ID</div>
                <div class="agent-id">{s.get("session_id")[:8]}...</div>
                <div class="agent-label">Current Task</div>
                <div class="agent-task">{s.get("prompt", "No task description")}</div>
            </div>''' for s in sessions]) if sessions else '<div class="empty-state"><div class="empty-state-icon">&#128161;</div><p>No active agents at the moment</p></div>'}
        </div>

        <div class="footer">
            <span>Agentic Orchestration Monitor</span>
            <div class="refresh-indicator">
                <span class="refresh-dot"></span>
                <span>Auto-refresh every 5s</span>
            </div>
        </div>
    </div>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'neutral',
            flowchart: {{
                curve: 'basis',
                padding: 20
            }}
        }});

        // Auto-refresh the page every 5 seconds to show live updates
        // In a real MCP environment, we would use a subscription or event source,
        // but for a standalone HTML preview, a refresh is the most reliable way.
        setTimeout(() => {{
            window.location.reload();
        }}, 5000);
    </script>
</body>
</html>
"""

    return [
        {
            "type": "text",
            "text": f"Rendering live orchestration for {plan_path.name}. Active nodes highlighted in blue."
        },
        {
            "type": "resource",
            "resource": {
                "uri": "ui://orchestration/live",
                "mimeType": "text/html",
                "text": html_content
            }
        }
    ]

if __name__ == "__main__":
    mcp.run()
