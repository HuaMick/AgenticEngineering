# Terminal Service Documentation

The terminal service provides PTY (pseudo-terminal) management for remote Claude Code sessions. It handles process lifecycle, input/output streaming, and encrypted communication with web clients through the relay service.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Terminal Service                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │  CLI Entrypoint │───>│  SessionWorkflow │                   │
│  └─────────────────┘    └────────┬─────────┘                   │
│                                  │                              │
│              ┌───────────────────┼───────────────────┐          │
│              │                   │                   │          │
│              ▼                   ▼                   ▼          │
│  ┌───────────────────┐ ┌─────────────────┐ ┌──────────────────┐│
│  │ TerminalWorkflow  │ │   RelayClient   │ │   Relay API      ││
│  │  (PTY lifecycle)  │ │ (WebSocket E2E) │ │(session creation)││
│  └─────────┬─────────┘ └────────┬────────┘ └──────────────────┘│
│            │                    │                               │
│            ▼                    ▼                               │
│  ┌───────────────────┐ ┌─────────────────────────────┐         │
│  │   PTYSpawner      │ │         Relay Service       │         │
│  │  (ptyprocess)     │ │  (wss://relay.example.com)  │         │
│  └───────────────────┘ └─────────────────────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Domain Layer (`domains/pty_manager/`)

**Value Objects:**
- `TerminalDimensions`: Terminal rows/columns (immutable)
- `ProcessState`: Enum of PTY states (created, running, terminated, error)
- `TerminalMode`: Terminal mode settings

**Entities:**
- `PTYSession`: Represents a PTY session with state machine lifecycle
  - States: created → running → terminated/error
  - Tracks: session_id, command, dimensions, PID, exit_code

**Repository Protocol:**
- `PTYRepository`: Abstract interface for session storage

### Infrastructure Layer (`infrastructure/`)

**InMemoryPTYRepository:**
- Thread-safe in-memory storage for PTY sessions
- Uses threading.Lock for concurrent access

**PTYSpawner:**
- Wraps `ptyprocess` library for PTY spawning
- Provides async read/write operations
- Handles terminal resize and process termination

**RelayClient:**
- WebSocket client for relay service communication
- E2E encryption using NaCl box (Curve25519-XSalsa20-Poly1305)
- Features:
  - Automatic reconnection with exponential backoff
  - Keepalive ping/pong handling
  - Message encryption/decryption
  - Async message callbacks for input/resize/close

### Workflow Layer (`workflows/`)

**TerminalWorkflow:**
- Orchestrates PTY session lifecycle
- Output callback pattern for async output delivery
- Methods: `start_session()`, `send_input()`, `resize_terminal()`, `stop_session()`

**SessionWorkflow:**
- Top-level coordinator for complete remote session lifecycle
- Manages:
  1. Session creation via relay API
  2. PTY spawning via TerminalWorkflow
  3. Relay client connection for I/O transport
  4. Bidirectional I/O piping (PTY ↔ Relay)

### Entrypoint Layer (`entrypoints/`)

**CLI (`agent-remote-terminal`):**
- Click-based command-line interface
- Signal handling (SIGINT, SIGTERM) for graceful shutdown
- Displays pairing code for web client connection

## Usage

### Starting the Terminal Service

```bash
# Start with default settings
agent-remote-terminal --relay-url https://relay.example.com

# Specify custom command (default: claude)
agent-remote-terminal --relay-url https://relay.example.com --command "/path/to/claude"

# Custom terminal dimensions
agent-remote-terminal --relay-url https://relay.example.com --rows 40 --cols 120
```

### Session Lifecycle

1. **Session Creation**: CLI calls relay API to create session, receives session_id and pairing_code
2. **Key Generation**: Generates NaCl keypair for E2E encryption
3. **PTY Spawning**: Starts Claude Code CLI in a pseudo-terminal
4. **Relay Connection**: Connects to relay WebSocket with session_id
5. **Client Pairing**: Web client connects with pairing_code, exchanges public keys
6. **I/O Bridge**: Bidirectional encrypted communication:
   - PTY output → encrypt → relay → web client
   - Web client input → relay → decrypt → PTY stdin
7. **Termination**: Either side can close; cleanup includes PTY kill and WebSocket close

## E2E Encryption

All terminal data is encrypted end-to-end between the desktop and web client. The relay service never sees plaintext.

**Algorithm:** NaCl box (Curve25519-XSalsa20-Poly1305)
- Key Exchange: X25519 elliptic curve Diffie-Hellman
- Encryption: XSalsa20 stream cipher
- Authentication: Poly1305 MAC

**Message Flow:**
```
Desktop                           Relay                           Client
   |                               |                                |
   |-- EncryptedBlob(output) ---->|---- EncryptedBlob(output) ---->|
   |                               |                                |
   |<-- EncryptedBlob(input) -----|<---- EncryptedBlob(input) -----|
   |                               |                                |
```

**Security Properties:**
- Confidentiality: Only endpoints can decrypt
- Integrity: Any tampering is detected
- Authentication: Messages verified by MAC
- Forward secrecy: Each message uses unique nonce

## Configuration

### RelayClientConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `relay_ws_url` | Required | WebSocket URL for relay service |
| `session_id` | Required | UUID identifying the session |
| `private_key` | Required | Desktop's NaCl private key (32 bytes) |
| `max_reconnect_attempts` | 10 | Maximum reconnection attempts (0 = infinite) |
| `initial_reconnect_delay` | 1.0s | Initial delay before reconnect |
| `max_reconnect_delay` | 30.0s | Maximum delay between reconnects |
| `keepalive_interval` | 30.0s | Interval between keepalive pings |
| `connection_timeout` | 10.0s | Timeout for connection establishment |

## Error Handling

### Connection Errors
- Invalid session: Fails fast, no retry
- Network errors: Exponential backoff retry up to `max_reconnect_attempts`
- Timeout: Retries with backoff

### Encryption Errors
- Invalid keys: Raises `RelayEncryptionError`
- Decryption failure: Logs error, triggers `on_error` callback
- Missing encryption box: Warns, cannot send/receive encrypted messages

### PTY Errors
- Spawn failure: Session enters error state
- Process exit: Detected by output reader, triggers cleanup

## Testing

```bash
# Run all terminal service tests
pytest tests/test_relay_client.py -v

# Test categories
pytest tests/test_relay_client.py::TestRelayClientConfig -v        # Configuration
pytest tests/test_relay_client.py::TestRelayClientEncryption -v    # Crypto
pytest tests/test_relay_client.py::TestRelayClientMessageHandling -v  # Messages
pytest tests/test_relay_client.py::TestRelayClientSending -v       # Sending
pytest tests/test_relay_client.py::TestRelayClientLifecycle -v     # Lifecycle
```

## Troubleshooting

### Common Issues

**"Session not found or invalid"**
- Session may have expired (default: 1 hour TTL)
- Desktop disconnected, session was closed
- Invalid session_id format

**"Client public key not set"**
- Web client hasn't paired yet
- Client disconnected before pairing completed
- Wait for pairing before sending output

**"Decryption failed"**
- Key mismatch between desktop and client
- Message tampering detected
- Wrong nonce (should never happen with proper implementation)

**"Connection refused"**
- Relay service not running
- Incorrect relay URL
- Network/firewall blocking WebSocket

### Debug Logging

Enable debug logging to see message flow:

```python
import logging
logging.getLogger("agent_remote.services.terminal").setLevel(logging.DEBUG)
```

## Dependencies

```toml
[project.dependencies]
fastapi = ">=0.115.0"
uvicorn = ">=0.32.0"
websockets = ">=13.0"
pynacl = ">=1.5.0"
ptyprocess = ">=0.7.0"
pydantic = ">=2.0.0"
click = ">=8.0.0"
httpx = ">=0.27.0"
```
