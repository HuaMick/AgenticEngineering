# Relay Service API Documentation

This document describes the REST API and WebSocket endpoints for the relay service.

## Overview

The relay service brokers connections between desktop CLI and Flutter web clients.
All terminal/session messages are end-to-end encrypted; the relay only sees encrypted blobs.

**Base URL:** `http://localhost:8080`

## REST API Endpoints

### Create Session

Creates a new relay session and returns a pairing code.

```
POST /api/sessions
```

**Request Body:**
```json
{
  "desktop_public_key": "base64_encoded_public_key"
}
```

| Field | Type | Description |
|-------|------|-------------|
| desktop_public_key | string | Base64-encoded NaCl public key (32 bytes) |

**Response (201 Created):**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "pairing_code": "ABC123"
}
```

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | UUID identifying the session |
| pairing_code | string | 6-character uppercase alphanumeric code (expires in 5 min) |

**Example:**
```bash
curl -X POST http://localhost:8080/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"desktop_public_key": "dGVzdF9wdWJsaWNfa2V5XzMyX2J5dGVzX2xvbmch"}'
```

**Errors:**
- `400 Bad Request` - Invalid base64 encoding

---

### Get Session Status

Retrieves the current state of a session.

```
GET /api/sessions/{session_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | UUID of the session |

**Response (200 OK):**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "state": "paired",
  "desktop_connected": true,
  "client_connected": true,
  "expires_at": "2025-12-04T18:45:00.123456"
}
```

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | UUID identifying the session |
| state | string | `created`, `desktop_connected`, `paired`, or `closed` |
| desktop_connected | boolean | True if desktop WebSocket is connected |
| client_connected | boolean | True if client WebSocket is connected |
| expires_at | string | ISO 8601 timestamp when pairing code expires |

**Session States:**

| State | Description |
|-------|-------------|
| `created` | Session created, waiting for desktop connection |
| `desktop_connected` | Desktop connected, waiting for client pairing |
| `paired` | Both peers connected, ready for message routing |
| `closed` | Session closed (disconnect or timeout) |

**Errors:**
- `400 Bad Request` - Invalid UUID format
- `404 Not Found` - Session not found

---

### Close Session

Closes a session and disconnects all peers.

```
DELETE /api/sessions/{session_id}
```

**Response:** `204 No Content`

**Errors:**
- `400 Bad Request` - Invalid UUID format

---

### Health Check

Check if the relay service is running.

```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "repository": "InMemorySessionRepository(0 sessions)"
}
```

---

## WebSocket Endpoints

### Desktop Connection

Desktop CLI connects after creating a session.

```
GET /ws/desktop/{session_id}
```

**Connection Flow:**
1. Desktop creates session via `POST /api/sessions`
2. Desktop connects to `/ws/desktop/{session_id}`
3. Relay transitions session to `desktop_connected`
4. Desktop waits for client to pair

**Message Format:**

All messages are JSON with a `type` field:

```json
{
  "type": "EncryptedBlob",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "sender": "desktop",
  "payload": "base64_encrypted_data",
  "nonce": "base64_nonce_24_bytes"
}
```

**Keepalive:**
- Server sends `Ping` every 30 seconds
- Client must respond with `Pong` within 5 seconds
- Connection closes on timeout

**Disconnect Handling:**
- Session closes automatically on disconnect
- Client receives `Error` message before close

---

### Client Connection

Web client connects with pairing code.

```
GET /ws/client/{pairing_code}
```

**Connection Flow:**
1. User enters 6-character pairing code in Flutter app
2. Client connects to `/ws/client/{pairing_code}`
3. Client sends first message with `client_public_key`
4. Relay validates pairing code and pairs session
5. Session transitions to `paired`

**First Message (SessionPair):**
```json
{
  "type": "SessionPair",
  "session_id": null,
  "client_public_key": "base64_encoded_public_key"
}
```

**Subsequent Messages (EncryptedBlob):**
```json
{
  "type": "EncryptedBlob",
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "sender": "client",
  "payload": "base64_encrypted_data",
  "nonce": "base64_nonce_24_bytes"
}
```

**Errors:**
- `404 Not Found` - Invalid pairing code
- `409 Conflict` - Session already paired
- `410 Gone` - Pairing code expired

---

## Message Types

### EncryptedBlob

Encrypted message container for all terminal/session data.

```json
{
  "type": "EncryptedBlob",
  "session_id": "uuid",
  "sender": "desktop|client",
  "payload": "base64_encrypted_nacl_box",
  "nonce": "base64_24_byte_nonce"
}
```

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | UUID of the session |
| sender | string | `desktop` or `client` |
| payload | string | Base64-encoded encrypted payload |
| nonce | string | Base64-encoded 24-byte NaCl nonce |

### Ping/Pong

Keepalive messages.

```json
{"type": "Ping", "timestamp": 1733340300.123}
{"type": "Pong", "timestamp": 1733340300.123}
```

### Error

Error notification before disconnect.

```json
{
  "type": "Error",
  "code": "SESSION_EXPIRED",
  "message": "Pairing code has expired",
  "details": {"session_id": "uuid"}
}
```

**Error Codes:**

| Code | HTTP | Description |
|------|------|-------------|
| `SESSION_NOT_FOUND` | 404 | Session doesn't exist |
| `SESSION_EXPIRED` | 410 | Pairing code expired |
| `PAIRING_CODE_INVALID` | 404 | Invalid pairing code |
| `VALIDATION_FAILED` | 400 | Message validation failed |
| `INVALID_MESSAGE` | 400 | Malformed message |

---

## Example: Python Desktop Client

```python
import base64
import json
import requests
import websockets
import asyncio

RELAY_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080"

# Generate keypair (using nacl)
from nacl.public import PrivateKey
private_key = PrivateKey.generate()
public_key = bytes(private_key.public_key)

# Create session
response = requests.post(
    f"{RELAY_URL}/api/sessions",
    json={"desktop_public_key": base64.b64encode(public_key).decode()}
)
data = response.json()
session_id = data["session_id"]
pairing_code = data["pairing_code"]
print(f"Pairing code: {pairing_code}")

# Connect WebSocket
async def desktop_client():
    async with websockets.connect(
        f"{WS_URL}/ws/desktop/{session_id}"
    ) as ws:
        # Receive messages
        async for message in ws:
            msg = json.loads(message)
            if msg["type"] == "EncryptedBlob":
                # Decrypt and process
                pass
            elif msg["type"] == "Ping":
                await ws.send(json.dumps({"type": "Pong", "timestamp": msg["timestamp"]}))

asyncio.run(desktop_client())
```

---

## Example: Dart/Flutter Web Client

```dart
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

const relayUrl = 'ws://localhost:8080';

void connectToRelay(String pairingCode, List<int> publicKey) async {
  final channel = WebSocketChannel.connect(
    Uri.parse('$relayUrl/ws/client/$pairingCode'),
  );

  // Send pairing request with public key
  channel.sink.add(jsonEncode({
    'type': 'SessionPair',
    'session_id': null,
    'client_public_key': base64Encode(publicKey),
  }));

  // Listen for messages
  channel.stream.listen((message) {
    final msg = jsonDecode(message);
    switch (msg['type']) {
      case 'EncryptedBlob':
        // Decrypt and display
        break;
      case 'Ping':
        channel.sink.add(jsonEncode({
          'type': 'Pong',
          'timestamp': msg['timestamp'],
        }));
        break;
      case 'Error':
        print('Error: ${msg['code']} - ${msg['message']}');
        break;
    }
  });
}
```

---

## Running the Server

```bash
# Install dependencies
pip install -e .

# Start server
python -m agent_remote.services.relay.api.server

# Or with uvicorn directly
uvicorn agent_remote.services.relay.api.server:app --host 0.0.0.0 --port 8080
```

**Configuration:**
- Host: `0.0.0.0` (all interfaces)
- Port: `8080` (default)
- Workers: `1` (required for in-memory repository)

**Docker:**
```bash
docker build -t relay-service .
docker run -p 8080:8080 relay-service
```
