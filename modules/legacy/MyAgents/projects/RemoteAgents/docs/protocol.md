# RemoteAgents Protocol Specification

This document specifies the protocol message types, validation rules, and message flow patterns for the RemoteAgents system.

## Overview

RemoteAgents uses a message-based protocol for communication between:
- **Desktop Agent**: Runs on the user's machine, manages PTY sessions
- **Relay Service**: Cloud service that routes encrypted messages between desktop and client
- **Web Client**: Browser-based terminal interface

All messages are JSON-serialized Pydantic models with a `type` field for routing.

## Message Categories

| Category | Messages | Purpose |
|----------|----------|---------|
| Session | SessionCreate, SessionCreated, SessionPair, SessionPaired, SessionClose | Pairing flow and session lifecycle |
| Terminal | TerminalOutput, TerminalInput, TerminalResize, TerminalClose | PTY communication |
| Relay | EncryptedBlob, Ping, Pong, Error | Encrypted transport and control |

## Message Flow Patterns

### Session Pairing Flow

```
Desktop                    Relay                      Client
   |                         |                          |
   |-- SessionCreate ------->|                          |
   |   (desktop_public_key)  |                          |
   |                         |                          |
   |<-- SessionCreated ------|                          |
   |   (session_id,          |                          |
   |    pairing_code)        |                          |
   |                         |                          |
   |                         |<----- SessionPair -------|
   |                         |   (pairing_code,         |
   |                         |    client_public_key)    |
   |                         |                          |
   |<-- SessionPaired -------|------ SessionPaired --->|
   |   (desktop_public_key)  |   (desktop_public_key)   |
   |                         |                          |
   [Session Active - E2E Encrypted Communication]
   |                         |                          |
   |-- SessionClose -------->| or |<-- SessionClose ---|
```

### Terminal I/O Flow

```
Desktop                    Relay                      Client
   |                         |                          |
   |<======= EncryptedBlob(TerminalInput) =============|
   |                         |                          |
   [PTY processes input]
   |                         |                          |
   |======== EncryptedBlob(TerminalOutput) ==========>|
   |                         |                          |
   |<======= EncryptedBlob(TerminalResize) ============|
   |                         |                          |
   [PTY resizes]
```

### WebSocket Keepalive

```
Any Party                  Other Party
   |                          |
   |-------- Ping ----------->|
   |                          |
   |<------- Pong ------------|
   |                          |
```

## Session State Machine

```
                    SessionCreate
                         |
                         v
    [DISCONNECTED] --> [CREATING] --> [CREATED]
                                          |
                                    SessionPair
                                          |
                                          v
                                     [PAIRING]
                                          |
                                    SessionPaired
                                          |
                                          v
                                      [PAIRED]
                                          |
                                    SessionClose
                                          |
                                          v
                                      [CLOSED]
```

---

## Session Messages

### SessionCreate

Desktop initiates session creation with its public key.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"session.create"` | Yes | Message type discriminator |
| desktop_public_key | bytes (base64) | Yes | X25519 public key (32 bytes) |

**Validation Rules:**
- `desktop_public_key` must be exactly 32 bytes when decoded

**JSON Example:**
```json
{
  "type": "session.create",
  "desktop_public_key": "QElQLbksojQsP5LaxdbefIXbXfVAeltJls458u+36Cc="
}
```

---

### SessionCreated

Relay confirms session creation with session ID and pairing code.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"session.created"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| pairing_code | string | Yes | 6-char uppercase alphanumeric code |

**Validation Rules:**
- `session_id` must be valid UUID format
- `pairing_code` must match pattern `^[A-Z0-9]{6}$`

**JSON Example:**
```json
{
  "type": "session.created",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "pairing_code": "ABC123"
}
```

---

### SessionPair

Client requests to pair with session using pairing code.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"session.pair"` | Yes | Message type discriminator |
| pairing_code | string | Yes | 6-char uppercase alphanumeric code |
| client_public_key | bytes (base64) | Yes | X25519 public key (32 bytes) |

**Validation Rules:**
- `pairing_code` must match pattern `^[A-Z0-9]{6}$`
- `client_public_key` must be exactly 32 bytes when decoded

**JSON Example:**
```json
{
  "type": "session.pair",
  "pairing_code": "ABC123",
  "client_public_key": "Sk+MzeGY1m6ZtMAUQYoyI84lbJiQCuSmgR/RD364TCw="
}
```

---

### SessionPaired

Relay confirms successful pairing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"session.paired"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| desktop_public_key | bytes (base64) | Yes | Desktop's X25519 public key (32 bytes) |

**Validation Rules:**
- `session_id` must be valid UUID format
- `desktop_public_key` must be exactly 32 bytes when decoded

**JSON Example:**
```json
{
  "type": "session.paired",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "desktop_public_key": "QElQLbksojQsP5LaxdbefIXbXfVAeltJls458u+36Cc="
}
```

---

### SessionClose

Either party requests to close the session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"session.close"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |

**Validation Rules:**
- `session_id` must be valid UUID format

**JSON Example:**
```json
{
  "type": "session.close",
  "session_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

---

## Terminal Messages

### TerminalOutput

Server sends PTY output data to client.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"terminal.output"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| timestamp | float | Yes | Unix epoch timestamp (auto-populated) |
| data | bytes (base64) | Yes | Raw PTY output bytes |

**Validation Rules:**
- `session_id` must be valid UUID format
- `data` is base64-encoded bytes (can contain ANSI codes, binary data)

**JSON Example:**
```json
{
  "type": "terminal.output",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": 1733299200.123,
  "data": "SGVsbG8gV29ybGQK"
}
```

---

### TerminalInput

Client sends input to PTY.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"terminal.input"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| timestamp | float | Yes | Unix epoch timestamp (auto-populated) |
| data | bytes (base64) | Yes | Raw input bytes |

**Validation Rules:**
- `session_id` must be valid UUID format
- `data` is base64-encoded bytes

**JSON Example:**
```json
{
  "type": "terminal.input",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": 1733299200.456,
  "data": "bHMgLWxhDQ=="
}
```

---

### TerminalResize

Client notifies server of terminal dimension change.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"terminal.resize"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| rows | integer | Yes | Number of rows (1-1000) |
| cols | integer | Yes | Number of columns (1-1000) |

**Validation Rules:**
- `session_id` must be valid UUID format
- `rows` must be integer in range 1-1000
- `cols` must be integer in range 1-1000

**JSON Example:**
```json
{
  "type": "terminal.resize",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "rows": 24,
  "cols": 80
}
```

---

### TerminalClose

Either party requests to close the terminal session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"terminal.close"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| reason | string | Yes | Human-readable closure reason |

**Validation Rules:**
- `session_id` must be valid UUID format
- `reason` is required (non-empty string)

**Common Reasons:**
- `"User disconnected"` - Client closed window/tab
- `"Process exited"` - PTY process terminated normally
- `"Process crashed"` - PTY process terminated with error
- `"Timeout"` - Session idle timeout
- `"Authentication failed"` - Security validation failed

**JSON Example:**
```json
{
  "type": "terminal.close",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "reason": "User disconnected"
}
```

---

## Relay Messages

### EncryptedBlob

Encrypted payload wrapper for terminal/session messages.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"relay.encrypted"` | Yes | Message type discriminator |
| session_id | string (UUID) | Yes | UUID identifying the session |
| sender | `"desktop"` or `"client"` | Yes | Message origin |
| payload | string (base64) | Yes | Encrypted message |
| nonce | string (base64) | Yes | 24-byte NaCl nonce |

**Validation Rules:**
- `session_id` must be valid UUID format
- `sender` must be exactly `"desktop"` or `"client"`
- `nonce` must decode to exactly 24 bytes

**JSON Example:**
```json
{
  "type": "relay.encrypted",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "sender": "desktop",
  "payload": "gdX4e53H3eO4ElyLo6sNXRsSN8/JX+uf7ehogpg=",
  "nonce": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
}
```

---

### Ping

WebSocket keepalive ping message.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"relay.ping"` | Yes | Message type discriminator |
| timestamp | float | Yes | Unix epoch timestamp (auto-populated) |

**JSON Example:**
```json
{
  "type": "relay.ping",
  "timestamp": 1733299200.789
}
```

---

### Pong

WebSocket keepalive pong response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"relay.pong"` | Yes | Message type discriminator |
| timestamp | float | Yes | Unix epoch timestamp (echo from Ping) |

**JSON Example:**
```json
{
  "type": "relay.pong",
  "timestamp": 1733299200.789
}
```

---

### Error

Structured error message.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | `"relay.error"` | Yes | Message type discriminator |
| code | string | Yes | Namespaced error code |
| message | string | Yes | Human-readable description |
| details | object | No | Additional context |

**Error Codes:**

| Code | Category | Description |
|------|----------|-------------|
| `SESSION_EXPIRED` | Session | Session timed out |
| `SESSION_NOT_FOUND` | Session | Session ID doesn't exist |
| `SESSION_ALREADY_EXISTS` | Session | Duplicate session creation |
| `PAIRING_FAILED` | Pairing | General pairing failure |
| `PAIRING_CODE_INVALID` | Pairing | Wrong pairing code |
| `PAIRING_CODE_EXPIRED` | Pairing | Pairing code timed out |
| `CRYPTO_ERROR` | Crypto | General encryption error |
| `INVALID_KEY` | Crypto | Malformed public key |
| `DECRYPTION_FAILED` | Crypto | Could not decrypt message |
| `INVALID_NONCE` | Crypto | Nonce wrong length or reused |
| `INVALID_MESSAGE` | Protocol | Malformed message |
| `UNSUPPORTED_MESSAGE_TYPE` | Protocol | Unknown message type |
| `VALIDATION_FAILED` | Protocol | Field validation error |
| `CONNECTION_LOST` | Connection | WebSocket disconnected |
| `TIMEOUT` | Connection | Operation timed out |
| `INTERNAL_ERROR` | General | Server error |
| `UNAUTHORIZED` | General | Authentication required |

**JSON Example:**
```json
{
  "type": "relay.error",
  "code": "SESSION_EXPIRED",
  "message": "Session abc123 expired after 1 hour of inactivity",
  "details": {
    "session_id": "abc123",
    "expired_at": "2025-12-04T10:00:00Z"
  }
}
```

---

## Protocol Invariants

1. **Session ID Required**: All messages except `SessionCreate`, `SessionPair`, `Ping`, `Pong`, and `Error` require a valid `session_id`

2. **Nonce Uniqueness**: Each `EncryptedBlob` must use a unique 24-byte nonce. **NEVER reuse nonces** with the same key pair.

3. **Pairing Code Validity**: Pairing codes are valid for 5 minutes from `SessionCreated`

4. **Timestamp Format**: All timestamps are Unix epoch in seconds (float, e.g., `1733299200.123`)

5. **Bytes Transport**: All bytes fields are transported as base64-encoded strings in JSON

6. **Type Discriminator**: Every message has a `type` field used for routing and deserialization

---

## Test Vectors

See `tests/shared/fixtures/protocol_vectors.json` for complete test vectors including:
- Valid examples of all 13 message types
- Invalid examples for validation testing
- Serialization roundtrip examples

---

## References

- [NaCl Crypto Library](https://nacl.cr.yp.to/)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [UUID Specification](https://www.rfc-editor.org/rfc/rfc4122)

---

Last updated: 2025-12-04
