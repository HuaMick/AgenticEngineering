"""AgenticFrontend server — Tornado + terminado web terminal server.

Provides:
- REST API for terminal lifecycle (create, list, delete)
- WebSocket /ws/terminals/<name> for PTY data (via terminado)
- WebSocket /ws/events for lifecycle event push
- Static file serving for xterm.js frontend
- Auto-creates an "orchestrator" terminal on startup
"""

import json
import logging
import os
import signal
import sys
from pathlib import Path

import tornado.ioloop
import tornado.web
import tornado.websocket
from terminado import TermSocket, NamedTermManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# All connected event-stream WebSocket clients
_event_clients: set["EventWebSocket"] = set()

# Track terminal metadata (name -> metadata dict)
_terminal_meta: dict[str, dict] = {}


def _broadcast_event(event_type: str, data: dict) -> None:
    """Push an event to all connected /ws/events clients."""
    payload = json.dumps({"type": event_type, **data})
    dead = set()
    for client in _event_clients:
        try:
            client.write_message(payload)
        except Exception:
            dead.add(client)
    _event_clients.difference_update(dead)


# ---------------------------------------------------------------------------
# WebSocket: /ws/events — lifecycle event push
# ---------------------------------------------------------------------------

class EventWebSocket(tornado.websocket.WebSocketHandler):
    """Push-only WebSocket for terminal lifecycle events."""

    def check_origin(self, origin):
        return True

    def open(self):
        _event_clients.add(self)
        logger.debug("Event client connected (%d total)", len(_event_clients))
        # Send current terminal list on connect
        terminals = []
        for name, meta in _terminal_meta.items():
            terminals.append({"name": name, **meta})
        self.write_message(json.dumps({"type": "terminal_list", "terminals": terminals}))

    def on_close(self):
        _event_clients.discard(self)
        logger.debug("Event client disconnected (%d total)", len(_event_clients))

    def on_message(self, message):
        # Events socket is push-only; ignore client messages
        pass


# ---------------------------------------------------------------------------
# REST API handlers
# ---------------------------------------------------------------------------

class TerminalsHandler(tornado.web.RequestHandler):
    """POST /api/terminals — create a terminal.
    GET  /api/terminals — list terminals.
    """

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self):
        self.set_status(204)
        self.finish()

    def get(self):
        """List all active terminals."""
        term_manager: NamedTermManager = self.application.settings["term_manager"]
        terminals = []
        for name in list(term_manager.terminals):
            meta = _terminal_meta.get(name, {})
            terminals.append({"name": name, **meta})
        self.write(json.dumps({"terminals": terminals}))

    def post(self):
        """Create a new terminal."""
        try:
            body = json.loads(self.request.body or "{}")
        except json.JSONDecodeError:
            self.set_status(400)
            self.write(json.dumps({"error": "Invalid JSON"}))
            return

        name = body.get("name")
        cmd = body.get("cmd")
        cwd = body.get("cwd", os.getcwd())
        orchestrator_id = body.get("orchestrator_id")
        role = body.get("role")

        if not name:
            self.set_status(400)
            self.write(json.dumps({"error": "name is required"}))
            return

        term_manager: NamedTermManager = self.application.settings["term_manager"]

        # Check if terminal already exists
        if name in term_manager.terminals:
            self.set_status(409)
            self.write(json.dumps({"error": f"Terminal '{name}' already exists"}))
            return

        # Create the terminal
        try:
            # Use get_terminal which creates with specified name
            term = term_manager.get_terminal(name)

            # Set up the environment and run command in the PTY
            server_url = self.application.settings.get("server_url", "http://localhost:8765")
            env_cmds = [f'export AGENTIC_TERMINAL_URL="{server_url}"']
            if orchestrator_id:
                env_cmds.append(f'export AGENTIC_ORCHESTRATOR_ID="{orchestrator_id}"')

            # Change working directory
            if cwd and os.path.isdir(cwd):
                env_cmds.append(f'cd {cwd}')

            # Execute command if provided
            if cmd:
                if isinstance(cmd, str):
                    env_cmds.append(cmd)
                else:
                    env_cmds.append(' '.join(cmd))

            # Write all setup commands to the PTY
            for c in env_cmds:
                term.ptyproc.write(c + '\n')

            meta = {
                "orchestrator_id": orchestrator_id,
                "role": role,
                "cwd": cwd,
                "cmd": cmd if isinstance(cmd, str) else " ".join(cmd) if cmd else "bash",
            }
            _terminal_meta[name] = meta

            _broadcast_event("terminal_created", {"name": name, **meta})

            self.set_status(201)
            self.write(json.dumps({"name": name, **meta}))
            logger.info("Terminal created: %s (cmd=%s, cwd=%s)", name, cmd, cwd)
        except Exception as e:
            logger.exception("Failed to create terminal %s", name)
            self.set_status(500)
            self.write(json.dumps({"error": str(e)}))


class TerminalDetailHandler(tornado.web.RequestHandler):
    """DELETE /api/terminals/<name> — close a terminal."""

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self, name):
        self.set_status(204)
        self.finish()

    def delete(self, name):
        """Close and remove a terminal."""
        term_manager: NamedTermManager = self.application.settings["term_manager"]

        if name not in term_manager.terminals:
            self.set_status(404)
            self.write(json.dumps({"error": f"Terminal '{name}' not found"}))
            return

        try:
            term = term_manager.terminals[name]
            term.killpg()
        except Exception:
            pass

        try:
            del term_manager.terminals[name]
        except KeyError:
            pass

        meta = _terminal_meta.pop(name, {})
        _broadcast_event("terminal_closed", {"name": name, **meta})

        self.write(json.dumps({"name": name, "status": "closed"}))
        logger.info("Terminal closed: %s", name)


# ---------------------------------------------------------------------------
# Custom TermSocket to track terminal close
# ---------------------------------------------------------------------------

class TrackedTermSocket(TermSocket):
    """TermSocket subclass that broadcasts close events."""

    def check_origin(self, origin):
        return True

    def on_close(self):
        super().on_close()
        # Check if this terminal still has clients; if not, it's orphaned.
        # We don't auto-close here — the terminal survives WS disconnects.


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def make_app(port: int = 8765) -> tuple[tornado.web.Application, NamedTermManager]:
    """Build and return the Tornado application and term manager."""
    term_manager = NamedTermManager(
        shell_command=["bash"],
        max_terminals=50,
    )

    static_path = str(Path(__file__).parent / "static")
    server_url = f"http://localhost:{port}"

    app = tornado.web.Application(
        [
            # WebSocket: PTY data per terminal
            (r"/ws/terminals/(.*)", TrackedTermSocket, {"term_manager": term_manager}),
            # WebSocket: lifecycle events
            (r"/ws/events", EventWebSocket),
            # REST API
            (r"/api/terminals", TerminalsHandler),
            (r"/api/terminals/(.*)", TerminalDetailHandler),
            # Static files (index.html)
            (r"/(.*)", tornado.web.StaticFileHandler, {
                "path": static_path,
                "default_filename": "index.html",
            }),
        ],
        term_manager=term_manager,
        server_url=server_url,
    )

    return app, term_manager


def _create_orchestrator_terminal(term_manager: NamedTermManager, port: int) -> None:
    """Create the initial orchestrator terminal with AGENTIC_TERMINAL_URL set."""
    name = "orchestrator"
    server_url = f"http://localhost:{port}"

    # Set the env var so any session spawn from within detects the web terminal
    env_cmd = f'export AGENTIC_TERMINAL_URL="{server_url}"\n'

    term = term_manager.get_terminal(name)
    term.ptyproc.write(env_cmd)

    meta = {
        "orchestrator_id": None,
        "role": "orchestrator",
        "cwd": os.getcwd(),
        "cmd": "bash",
    }
    _terminal_meta[name] = meta

    logger.info("Orchestrator terminal created with AGENTIC_TERMINAL_URL=%s", server_url)


def main(port: int = 8765, open_browser: bool = False) -> None:
    """Start the AgenticFrontend terminal server.

    Args:
        port: Port to listen on (default 8765).
        open_browser: Whether to auto-open browser.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app, term_manager = make_app(port)
    app.listen(port)

    server_url = f"http://localhost:{port}"
    logger.info("AgenticFrontend server starting on %s", server_url)
    print(f"🖥️  AgenticFrontend terminal server running at {server_url}")
    print(f"   Press Ctrl+C to stop")

    # Create orchestrator terminal
    _create_orchestrator_terminal(term_manager, port)

    if open_browser:
        import webbrowser
        webbrowser.open(server_url)

    # Handle graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutting down...")
        print("\n🛑 Shutting down AgenticFrontend server...")
        ioloop = tornado.ioloop.IOLoop.current()
        ioloop.add_callback_from_signal(ioloop.stop)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup terminals after IOLoop has stopped
        for name in list(term_manager.terminals):
            try:
                term_manager.terminals[name].killpg()
            except Exception:
                pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AgenticFrontend terminal server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--open", action="store_true", help="Open browser on start")
    args = parser.parse_args()
    main(port=args.port, open_browser=args.open)
