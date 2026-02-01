# technical_spike_for_mcp_gui_orchestration_dashboard

Technical spike to implement a live orchestration dashboard using the MCP standard for GUI applications (MCP Apps). This spike focuses on real-time visualization of agent spawning and task execution state using Mermaid diagrams and server-rendered UI.

## Vision
To provide a real-time, visual "Command Center" for AgenticEngineering orchestrations, allowing users to see exactly which agents are active on a Mermaid flow diagram.

## Success Criteria
- [ ] Registered an MCP server that supports the `ui://` resource protocol.
- [ ] Rendered a Mermaid diagram in a browser window launched by Claude Code `--chrome`.
- [ ] Dynamically highlighted active nodes based on real-time CLI data (`agentic session list`).
- [ ] Established an auto-refresh or event-driven update mechanism for the UI.

## Phases
1. **SPIKE-01: Protocol Validation**: Verify Claude Code can render server-provided HTML via MCP.
2. **SPIKE-02: Real-time Data Integration**: Connect the UI to CLI state (sessions/loops).
3. **SPIKE-03: Visual Orchestration**: Highlight active nodes on the Mermaid diagram.
4. **SPIKE-04: Review & Finalization**: Technical review of the implementation and refinement.
