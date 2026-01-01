# Networking Layer Documentation

## Overview

The networking layer provides WebSocket-based communication with the RemoteAgents relay server, featuring end-to-end encryption, automatic reconnection, and robust state management.

### Purpose

This layer serves as the core communication channel between the MyAgents Flutter frontend and the RemoteAgents backend, enabling:

- Real-time bidirectional communication over WebSockets
- End-to-end encrypted messaging using NaCl (X25519-XSalsa20-Poly1305)
- Reliable message delivery with automatic reconnection
- Connection state tracking for UI feedback

### Key Components

1. **RelayClient**: Main WebSocket client managing connection lifecycle and message handling
2. **ConnectionStateManager**: Reactive state management using Flutter's ChangeNotifier pattern
3. **MessageEnvelope Integration**: Seamless integration with the crypto layer for encrypted messaging

### Integration with Crypto Layer

The networking layer deeply integrates with the crypto layer:

- Uses `KeyPair` for public/private key management
- Leverages `MessageEnvelope` for message encryption/decryption
- Employs `NaClCrypto` for secure box operations (X25519-XSalsa20-Poly1305)

All messages are encrypted before transmission and decrypted upon receipt, ensuring end-to-end security.

---

## Architecture

### WebSocket Connection Lifecycle

```
disconnected
    |
    v
connecting  <--+
    |          |
    v          |
connected      |
    |          |
    v          |
(connection lost)
    |          |
    v          |
reconnecting --+
    |
    v
error (max retries)
    |
    v
disconnected
```

The lifecycle consists of:

1. **Initial Connection**: Client connects to `wss://{relay}/ws/client/{pairing_code}`
2. **Active State**: Bidirectional message exchange with encryption
3. **Automatic Recovery**: Reconnection attempts with exponential backoff on connection loss
4. **Clean Shutdown**: Graceful disconnection when requested

### State Management Patterns

The `ConnectionStateManager` uses Flutter's `ChangeNotifier` to provide reactive updates:

```dart
enum ConnectionState {
  disconnected,   // Not connected
  connecting,     // Initial connection attempt
  connected,      // Active connection
  reconnecting,   // Attempting to reconnect
  error,          // Connection error occurred
}
```

State transitions are strictly controlled:
- `disconnected` → `connecting`
- `connecting` → `connected` or `error`
- `connected` → `disconnected` or `error`
- `error` → `reconnecting` or `disconnected`
- `reconnecting` → `connected` or `error`

### Message Encryption Flow

**Sending Messages:**

```
payload data (plaintext)
    |
    v
MessageEnvelope.seal(type, data, ourKeys, remoteKeys)
    |
    v
encrypted payload (Base64)
    |
    v
JSON serialization
    |
    v
WebSocket transmission
```

**Receiving Messages:**

```
WebSocket message
    |
    v
JSON deserialization
    |
    v
MessageEnvelope.fromJson(json)
    |
    v
envelope.open(ourKeys, remoteKeys)
    |
    v
decrypted payload (plaintext)
```

### Auto-Reconnect Strategy

The client implements exponential backoff with jitter:

- **Formula**: `delay = baseDelay × 2^(attempt-1)`
- **Base Delay**: 1 second
- **Max Delay**: 60 seconds
- **Max Attempts**: 10
- **Jitter**: ±10% random variance to prevent thundering herd

Example reconnection timeline:
- Attempt 1: 1s delay
- Attempt 2: 2s delay
- Attempt 3: 4s delay
- Attempt 4: 8s delay
- Attempt 5: 16s delay
- Attempt 6-10: 60s delay (capped)

---

## Usage Examples

### Creating RelayClient Instance

```dart
import 'package:myagents/core/networking/relay_client.dart';
import 'package:myagents/core/crypto/key_pair.dart';

// Create client instance
final client = RelayClient();

// Generate or load key pairs
final ourKeys = KeyPair.generate();
final remoteKeys = KeyPair.fromBase64(receivedKeysJson);

// Set encryption keys
client.setKeys(ourKeys, remoteKeys);
```

### Connecting to Relay Server

```dart
// Connect to relay server
try {
  await client.connect('relay.example.com', 'ABC123');
  print('Connected successfully!');
} catch (e) {
  print('Connection failed: $e');
}

// Listen to connection state changes
client.stateManager.addListener(() {
  final state = client.stateManager.currentState;
  print('Connection state: $state');

  if (client.stateManager.hasError) {
    print('Error: ${client.stateManager.errorMessage}');
  }
});
```

### Sending Encrypted Messages

```dart
// Send terminal input
await client.sendTerminalInput('ls -la\n');

// Send terminal resize
await client.sendResize(rows: 24, cols: 80);

// Send custom message type
await client.send(
  MessageType.pairingRequest,
  {'publicKey': base64Encode(ourKeys.publicKeyBytes)},
);
```

### Handling Connection State Changes

```dart
import 'package:flutter/material.dart';

class ConnectionStatusWidget extends StatefulWidget {
  final RelayClient client;

  const ConnectionStatusWidget({required this.client});

  @override
  State<ConnectionStatusWidget> createState() => _ConnectionStatusWidgetState();
}

class _ConnectionStatusWidgetState extends State<ConnectionStatusWidget> {
  @override
  void initState() {
    super.initState();
    // Listen to state changes
    widget.client.stateManager.addListener(_onStateChange);
  }

  @override
  void dispose() {
    widget.client.stateManager.removeListener(_onStateChange);
    super.dispose();
  }

  void _onStateChange() {
    setState(() {}); // Rebuild on state change
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.client.stateManager.currentState;

    return Row(
      children: [
        Icon(_getIconForState(state)),
        SizedBox(width: 8),
        Text(_getTextForState(state)),
      ],
    );
  }

  IconData _getIconForState(ConnectionState state) {
    switch (state) {
      case ConnectionState.connected:
        return Icons.check_circle;
      case ConnectionState.connecting:
      case ConnectionState.reconnecting:
        return Icons.sync;
      case ConnectionState.error:
        return Icons.error;
      case ConnectionState.disconnected:
        return Icons.cloud_off;
    }
  }

  String _getTextForState(ConnectionState state) {
    switch (state) {
      case ConnectionState.connected:
        return 'Connected';
      case ConnectionState.connecting:
        return 'Connecting...';
      case ConnectionState.reconnecting:
        return 'Reconnecting...';
      case ConnectionState.error:
        return 'Error: ${widget.client.stateManager.errorMessage}';
      case ConnectionState.disconnected:
        return 'Disconnected';
    }
  }
}
```

### Listening to Message Streams

```dart
// Listen to all messages
client.messageStream.listen((envelope) {
  final data = envelope.open(ourKeys, remoteKeys);
  print('Received ${envelope.type}: $data');
});

// Listen to specific message type
client.terminalOutputStream.listen((envelope) {
  final data = envelope.open(ourKeys, remoteKeys);
  final output = data['data'] as String;
  print('Terminal output: $output');
});

// Filter messages by type
client.getMessagesByType(MessageType.resize).listen((envelope) {
  final data = envelope.open(ourKeys, remoteKeys);
  print('Terminal resized: ${data['cols']}x${data['rows']}');
});

// Handle multiple message types
client.messageStream.listen((envelope) {
  final data = envelope.open(ourKeys, remoteKeys);

  switch (envelope.type) {
    case MessageType.terminalOutput:
      _handleTerminalOutput(data['data']);
      break;
    case MessageType.pairingRequest:
      _handlePairingRequest(data);
      break;
    default:
      print('Unhandled message type: ${envelope.type}');
  }
});
```

---

## Testing

### MockRelayServer Usage

The `MockRelayServer` class provides a test double for the RemoteAgents relay server:

```dart
import 'package:test/test.dart';
import '../test/mock_relay_server.dart';

void main() {
  late MockRelayServer server;
  late RelayClient client;

  setUp(() async {
    // Start mock server
    server = MockRelayServer(
      config: MockRelayServerConfig.verbose(),
    );
    await server.start();

    // Create client
    client = RelayClient();
  });

  tearDown(() async {
    await client.dispose();
    await server.stop();
  });

  test('client connects to server successfully', () async {
    // Generate keys
    final ourKeys = KeyPair.generate();
    final serverKeys = server.getServerKeys();

    // Set keys and connect
    client.setKeys(ourKeys, serverKeys);
    await client.connect('localhost:${server.getPort()}', 'TEST01');

    // Verify connection
    expect(client.isConnected, isTrue);
    expect(server.isClientConnected('TEST01'), isTrue);
  });

  test('messages are encrypted in transit', () async {
    final ourKeys = KeyPair.generate();
    final serverKeys = server.getServerKeys();

    client.setKeys(ourKeys, serverKeys);
    await client.connect('localhost:${server.getPort()}', 'TEST02');

    // Send message
    await client.sendTerminalInput('test input');

    // Wait for server to receive
    await server.waitForMessages(1);

    // Verify message was received and decrypted
    final messages = server.getReceivedMessages();
    expect(messages.length, 1);
    expect(messages[0].type, MessageType.terminalInput);
    expect(messages[0].payload['data'], 'test input');
  });
}
```

### Writing Integration Tests

Integration tests should cover:

1. **Connection Lifecycle**: Connect, disconnect, reconnect scenarios
2. **Message Encryption**: Verify end-to-end encryption works correctly
3. **Error Handling**: Invalid URLs, bad pairing codes, network errors
4. **State Transitions**: Verify state changes occur correctly
5. **Auto-Reconnect**: Test reconnection with various failure scenarios

Example integration test structure:

```dart
group('RelayClient Integration Tests', () {
  group('Connection Lifecycle', () {
    test('connects successfully with valid credentials', () { });
    test('disconnects cleanly on request', () { });
    test('reconnects after server disconnect', () { });
  });

  group('Message Encryption', () {
    test('sends encrypted terminal input', () { });
    test('receives and decrypts terminal output', () { });
    test('handles resize messages correctly', () { });
  });

  group('Error Handling', () {
    test('handles invalid relay URL', () { });
    test('handles invalid pairing code', () { });
    test('handles connection timeout', () { });
  });

  group('State Management', () {
    test('transitions through states correctly', () { });
    test('notifies listeners on state change', () { });
    test('stores error messages correctly', () { });
  });
});
```

### Test Coverage Expectations

Aim for the following coverage targets:

- **Line Coverage**: ≥90%
- **Branch Coverage**: ≥85%
- **Critical Paths**: 100% (connection, encryption, state transitions)

Key areas requiring thorough testing:

1. WebSocket connection establishment and closure
2. Message encryption/decryption roundtrips
3. Reconnection logic with exponential backoff
4. State transition validation
5. Error handling and recovery
6. Stream management and disposal

---

## Troubleshooting

### Common Connection Issues

#### Issue: "Connection terminated during handshake"

**Symptoms**: WebSocket connection fails immediately after initiating.

**Possible Causes**:
- Invalid relay server URL
- Network connectivity issues
- Firewall blocking WebSocket connections
- Server not accepting connections

**Solutions**:
1. Verify relay URL format: `wss://relay.example.com` (not `https://`)
2. Test network connectivity: `ping relay.example.com`
3. Check firewall rules for outbound WebSocket connections
4. Verify server is running and accepting connections

#### Issue: "Max reconnection attempts reached"

**Symptoms**: Client stops trying to reconnect after multiple failures.

**Possible Causes**:
- Persistent network issues
- Server is down or unreachable
- Invalid credentials (wrong pairing code)

**Solutions**:
1. Check server status and availability
2. Verify pairing code is correct
3. Increase max reconnect attempts if needed:
   ```dart
   // Note: Max attempts is currently hardcoded
   // Consider making it configurable
   ```
4. Manually trigger reconnection:
   ```dart
   await client.reconnect();
   ```

#### Issue: "StateError: Already connected to relay server"

**Symptoms**: Attempting to connect when already connected throws error.

**Possible Causes**:
- Calling `connect()` multiple times without disconnecting

**Solutions**:
1. Check connection state before connecting:
   ```dart
   if (!client.isConnected) {
     await client.connect(relayUrl, pairingCode);
   }
   ```
2. Disconnect before reconnecting:
   ```dart
   await client.disconnect();
   await client.connect(relayUrl, pairingCode);
   ```

### Debugging Encrypted Messages

#### Verifying Message Encryption

Check that messages are properly encrypted before transmission:

```dart
// Enable verbose logging
client.messageStream.listen((envelope) {
  print('Received envelope:');
  print('  Type: ${envelope.type}');
  print('  Encrypted payload: ${envelope.encryptedPayload.substring(0, 50)}...');
  print('  Sender key: ${envelope.senderPublicKey.substring(0, 20)}...');
  print('  Nonce: ${envelope.nonce.substring(0, 20)}...');
});
```

#### Decryption Failures

**Symptoms**: `Exception: Failed to decrypt message`

**Possible Causes**:
- Incorrect key pair configuration
- Keys not set before sending/receiving
- Message corrupted in transit
- Sender/receiver using different keys

**Solutions**:
1. Verify keys are set correctly:
   ```dart
   print('Our public key: ${base64Encode(ourKeys.publicKeyBytes)}');
   print('Remote public key: ${base64Encode(remoteKeys.publicKeyBytes)}');
   print('Keys set: ${client.hasKeys}');
   ```
2. Ensure key exchange completed successfully
3. Check that both sides are using the same protocol version
4. Verify message envelope structure is correct

#### Inspecting Message Payloads

For debugging, temporarily decrypt and log message contents:

```dart
client.messageStream.listen((envelope) {
  try {
    final decrypted = envelope.open(ourKeys, remoteKeys);
    print('Decrypted message: $decrypted');
  } catch (e) {
    print('Failed to decrypt: $e');
    print('Envelope JSON: ${jsonEncode(envelope.toJson())}');
  }
});
```

### Reconnection Failures

#### Issue: Client not reconnecting automatically

**Symptoms**: Connection drops and client stays disconnected.

**Possible Causes**:
- Auto-reconnect disabled
- Intentional disconnect called

**Solutions**:
1. Verify auto-reconnect is enabled:
   ```dart
   client.setAutoReconnect(true);
   ```
2. Check if disconnect was intentional:
   ```dart
   // Avoid calling disconnect() unless you want to stop reconnection
   await client.disconnect(); // Disables auto-reconnect
   ```

#### Issue: Reconnection loop

**Symptoms**: Client repeatedly connects and disconnects.

**Possible Causes**:
- Server immediately closing connections
- Invalid pairing code
- Authentication failure

**Solutions**:
1. Monitor error messages:
   ```dart
   client.stateManager.addListener(() {
     if (client.stateManager.hasError) {
       print('Connection error: ${client.stateManager.errorMessage}');
     }
   });
   ```
2. Check server logs for rejection reasons
3. Verify pairing code is valid and active

### State Transition Problems

#### Issue: State not updating in UI

**Symptoms**: UI doesn't reflect connection state changes.

**Possible Causes**:
- Not listening to state manager
- Not calling `setState()` in Flutter widgets

**Solutions**:
1. Add listener in widget:
   ```dart
   @override
   void initState() {
     super.initState();
     widget.client.stateManager.addListener(_onStateChange);
   }

   void _onStateChange() {
     setState(() {}); // Trigger rebuild
   }
   ```
2. Remove listener on dispose:
   ```dart
   @override
   void dispose() {
     widget.client.stateManager.removeListener(_onStateChange);
     super.dispose();
   }
   ```

#### Issue: Invalid state transitions

**Symptoms**: State transitions don't follow expected flow.

**Possible Causes**:
- Bug in state management logic
- Race conditions with async operations

**Solutions**:
1. Log all state transitions:
   ```dart
   client.stateManager.addListener(() {
     print('State changed: ${client.stateManager.currentState}');
     print('Last change: ${client.stateManager.lastStateChange}');
   });
   ```
2. Review ConnectionStateManager transition rules
3. Check for concurrent connect/disconnect calls

---

## API Reference

### RelayClient

Main WebSocket client for relay server communication.

#### Constructor

```dart
RelayClient()
```

Creates a new RelayClient instance in disconnected state.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `messageStream` | `Stream<MessageEnvelope>` | Stream of incoming messages |
| `errorStream` | `Stream<dynamic>` | Stream of WebSocket errors |
| `isConnected` | `bool` | Whether currently connected |
| `hasKeys` | `bool` | Whether encryption keys are set |
| `stateManager` | `ConnectionStateManager` | Connection state manager |
| `terminalOutputStream` | `Stream<MessageEnvelope>` | Filtered stream of terminal output messages |
| `pairingRequestStream` | `Stream<MessageEnvelope>` | Filtered stream of pairing request messages |

#### Methods

##### connect

```dart
Future<void> connect(String relayUrl, String pairingCode)
```

Connects to relay server at `wss://{relayUrl}/ws/client/{pairingCode}`.

**Parameters**:
- `relayUrl`: Base relay server URL (e.g., 'relay.example.com')
- `pairingCode`: 6-character pairing code

**Throws**:
- `StateError`: If already connected
- `WebSocketException`: If connection fails

##### disconnect

```dart
Future<void> disconnect()
```

Disconnects from relay server cleanly. Disables auto-reconnect.

##### reconnect

```dart
Future<void> reconnect()
```

Manually triggers reconnection. Disconnects if currently connected, then reconnects.

**Throws**:
- `StateError`: If relay URL or pairing code not set

##### setKeys

```dart
void setKeys(KeyPair ourKeys, KeyPair remoteKeys)
```

Sets encryption keys for this connection. Must be called before sending/receiving encrypted messages.

**Parameters**:
- `ourKeys`: Our key pair (private key for decryption)
- `remoteKeys`: Remote peer's key pair (public key for encryption)

##### setAutoReconnect

```dart
void setAutoReconnect(bool enabled)
```

Enables or disables automatic reconnection on connection loss. Default: `true`.

##### send

```dart
Future<void> send(MessageType type, Map<String, dynamic> payloadData)
```

Sends an encrypted message to the relay server.

**Parameters**:
- `type`: The message type
- `payloadData`: The payload data (will be encrypted)

**Throws**:
- `StateError`: If not connected or keys not set

##### sendTerminalInput

```dart
Future<void> sendTerminalInput(String input)
```

Convenience method for sending terminal input.

**Parameters**:
- `input`: The terminal input string

##### sendResize

```dart
Future<void> sendResize(int rows, int cols)
```

Convenience method for sending terminal dimension changes.

**Parameters**:
- `rows`: Number of terminal rows
- `cols`: Number of terminal columns

##### sendPairingRequest

```dart
Future<void> sendPairingRequest(Map<String, dynamic> data)
```

Convenience method for initial pairing handshake.

**Parameters**:
- `data`: Pairing data (e.g., public key exchange)

##### getMessagesByType

```dart
Stream<MessageEnvelope> getMessagesByType(MessageType type)
```

Returns a filtered stream of messages by type.

**Parameters**:
- `type`: The message type to filter by

**Returns**: Stream of MessageEnvelope with the specified type

##### dispose

```dart
Future<void> dispose()
```

Disposes of resources used by the client. Closes the WebSocket connection and all stream controllers. Must be called when the client is no longer needed.

---

### ConnectionState

Enum representing connection states.

#### Values

| Value | Description |
|-------|-------------|
| `disconnected` | Not connected to the server |
| `connecting` | Connection attempt in progress |
| `connected` | Successfully connected to the server |
| `reconnecting` | Attempting to reconnect after disconnection |
| `error` | Connection error has occurred |

---

### ConnectionStateManager

Manages connection state and notifies listeners of changes. Extends `ChangeNotifier`.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `currentState` | `ConnectionState` | Current connection state |
| `errorMessage` | `String?` | Last error message (if in error state) |
| `lastStateChange` | `DateTime?` | Timestamp of last state change |
| `isConnected` | `bool` | Whether currently connected |
| `isConnecting` | `bool` | Whether connecting or reconnecting |
| `hasError` | `bool` | Whether in error state |
| `isDisconnected` | `bool` | Whether disconnected |

#### Methods

##### setConnecting

```dart
void setConnecting()
```

Transitions to connecting state. Valid from: `disconnected`.

##### setConnected

```dart
void setConnected()
```

Transitions to connected state. Valid from: `connecting`, `reconnecting`.

##### setDisconnected

```dart
void setDisconnected()
```

Transitions to disconnected state. Valid from: any state.

##### setReconnecting

```dart
void setReconnecting()
```

Transitions to reconnecting state. Valid from: `disconnected`, `error`, `connected`.

##### setError

```dart
void setError(String? message)
```

Transitions to error state with optional error message. Valid from: any state.

**Parameters**:
- `message`: Error message describing what went wrong

##### reset

```dart
void reset()
```

Resets the connection state manager to initial state (disconnected).

##### dispose

```dart
void dispose()
```

Disposes of the state manager and notifies listeners. Inherited from `ChangeNotifier`.

---

## Additional Resources

- **Crypto Layer**: See `/lib/core/crypto/README.md` for encryption details
- **Message Protocol**: See `MessageEnvelope` and `MessageType` documentation
- **RemoteAgents Relay**: Server-side relay implementation and protocol specification
- **WebSocket Channel**: [pub.dev/packages/web_socket_channel](https://pub.dev/packages/web_socket_channel)

---

## Implementation Notes

### Thread Safety

The RelayClient is designed for single-threaded use (Dart's isolate model). All operations should be called from the same isolate. Stream subscriptions and state listeners are safe to use across widget rebuilds.

### Memory Management

Always call `dispose()` when finished with a RelayClient:

```dart
@override
void dispose() {
  client.dispose();
  super.dispose();
}
```

This ensures:
- WebSocket connection is closed
- Stream controllers are closed
- State manager listeners are removed
- Memory is freed

### Performance Considerations

1. **Message Streaming**: The `messageStream` is a broadcast stream, allowing multiple listeners without replaying events
2. **Encryption Overhead**: Each message incurs ~1-2ms encryption/decryption latency on modern devices
3. **Reconnection Backoff**: Exponential backoff prevents network flooding during outages
4. **Memory Usage**: Approximately 2-5MB per active connection (depends on message volume)

### Security Considerations

1. **Key Storage**: Never hardcode encryption keys in source code
2. **Key Exchange**: Use secure pairing mechanism to exchange public keys
3. **Message Validation**: Always validate decrypted message contents
4. **Connection Security**: Always use `wss://` (WebSocket Secure) in production
5. **Error Messages**: Avoid leaking sensitive information in error messages

---

## Version History

- **v1.0.0** (2025-12-04): Initial implementation with WebSocket client, E2E encryption, and auto-reconnect
