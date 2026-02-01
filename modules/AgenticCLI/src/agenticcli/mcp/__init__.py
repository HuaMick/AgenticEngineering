"""MCP (Model Context Protocol) server implementations for AgenticCLI.

This module provides MCP servers that can be used with Claude and other
MCP-compatible clients to provide orchestration monitoring and other
agentic capabilities.

Available servers:
    - orchestration_server: Provides live orchestration monitoring dashboard
"""

from agenticcli.mcp.orchestration_server import mcp as orchestration_mcp

__all__ = ["orchestration_mcp"]
