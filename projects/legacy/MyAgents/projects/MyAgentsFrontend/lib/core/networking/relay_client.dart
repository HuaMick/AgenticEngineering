import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../crypto/key_pair.dart';
import '../crypto/message_envelope.dart';
import 'connection_state.dart';

/// Manages WebSocket connection to RemoteAgents relay server with E2E encryption.
///
/// RelayClient handles:
/// - WebSocket connection lifecycle (connect, disconnect, reconnect)
/// - E2E encryption using NaCl (X25519-XSalsa20-Poly1305)
/// - Message serialization and deserialization
/// - Auto-reconnect with exponential backoff
/// - Connection state management
///
/// Usage:
/// ```dart
/// final client = RelayClient();
/// final ourKeys = KeyPair.generate();
/// final remoteKeys = KeyPair.fromBase64(receivedKeys);
///
/// await client.connect('wss://relay.example.com', 'ABC123');
/// client.setKeys(ourKeys, remoteKeys);
///
/// // Listen for messages
/// client.messageStream
///   .where((msg) => msg.type == MessageType.terminalOutput)
///   .listen((msg) {
///     final data = msg.open(ourKeys, remoteKeys);
///     print('Output: ${data['output']}');
///   });
///
/// // Send message
/// await client.send(MessageType.terminalInput, {'input': 'ls -la'});
/// ```
class RelayClient {
  /// WebSocket channel for relay server communication
  WebSocketChannel? _channel;

  /// Connection state manager
  final ConnectionStateManager stateManager = ConnectionStateManager();

  /// Our key pair for encryption
  KeyPair? _ourKeys;

  /// Remote peer's key pair for encryption
  KeyPair? _remoteKeys;

  /// Relay server URL (e.g., 'wss://relay.example.com')
  String? _relayUrl;

  /// Pairing code for this connection
  String? _pairingCode;

  /// Stream controller for incoming messages
  final StreamController<MessageEnvelope> _messageController =
      StreamController<MessageEnvelope>.broadcast();

  /// Stream controller for WebSocket errors
  final StreamController<dynamic> _errorController =
      StreamController<dynamic>.broadcast();

  /// Auto-reconnect settings
  bool _autoReconnect = true;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const Duration _baseReconnectDelay = Duration(seconds: 1);
  Timer? _reconnectTimer;

  /// Flag to track if disconnect was intentional
  bool _intentionalDisconnect = false;

  /// Subscription to WebSocket stream
  StreamSubscription? _channelSubscription;

  /// Creates a new RelayClient instance.
  ///
  /// The client starts in disconnected state. Call [connect] to establish
  /// a connection to the relay server.
  RelayClient();

  /// Gets the stream of incoming messages.
  ///
  /// Messages are automatically decrypted and parsed. Use [where] to filter
  /// by message type:
  /// ```dart
  /// client.messageStream
  ///   .where((msg) => msg.type == MessageType.terminalOutput)
  ///   .listen((msg) { ... });
  /// ```
  Stream<MessageEnvelope> get messageStream => _messageController.stream;

  /// Gets the stream of WebSocket errors.
  Stream<dynamic> get errorStream => _errorController.stream;

  /// Checks if currently connected.
  bool get isConnected => stateManager.isConnected;

  /// Checks if keys have been set.
  bool get hasKeys => _ourKeys != null && _remoteKeys != null;

  /// Sets the encryption keys for this connection.
  ///
  /// Must be called before sending or receiving encrypted messages.
  ///
  /// Args:
  ///   ourKeys: Our key pair (private key for decryption, public key sent with messages)
  ///   remoteKeys: Remote peer's key pair (public key for encryption)
  void setKeys(KeyPair ourKeys, KeyPair remoteKeys) {
    _ourKeys = ourKeys;
    _remoteKeys = remoteKeys;
  }

  /// Enables or disables automatic reconnection on connection loss.
  ///
  /// Default: true
  void setAutoReconnect(bool enabled) {
    _autoReconnect = enabled;
  }

  /// Connects to the relay server at the specified URL with pairing code.
  ///
  /// The connection URL format is: wss://{relayUrl}/ws/client/{pairingCode}
  ///
  /// Args:
  ///   relayUrl: Base relay server URL (e.g., 'relay.example.com')
  ///   pairingCode: Pairing code for this connection
  ///
  /// Throws:
  ///   StateError: If already connected
  ///   WebSocketException: If connection fails
  Future<void> connect(String relayUrl, String pairingCode) async {
    if (stateManager.isConnected) {
      throw StateError('Already connected to relay server');
    }

    _relayUrl = relayUrl;
    _pairingCode = pairingCode;
    _intentionalDisconnect = false;
    _reconnectAttempts = 0;

    await _connect();
  }

  /// Internal method to establish WebSocket connection.
  Future<void> _connect() async {
    if (_relayUrl == null || _pairingCode == null) {
      throw StateError('Relay URL and pairing code must be set');
    }

    // Update state to connecting
    if (_reconnectAttempts == 0) {
      stateManager.setConnecting();
    } else {
      stateManager.setReconnecting();
    }

    try {
      // Build WebSocket URL
      final wsUrl = _buildWebSocketUrl(_relayUrl!, _pairingCode!);

      // Create WebSocket channel
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      // Wait for connection to be established
      await _channel!.ready;

      // Update state to connected
      stateManager.setConnected();
      _reconnectAttempts = 0;

      // Start listening to messages
      _startListening();
    } catch (e) {
      stateManager.setError('Connection failed: $e');
      _errorController.add(e);

      // Attempt reconnection if enabled
      if (_autoReconnect && !_intentionalDisconnect) {
        _scheduleReconnect();
      }

      rethrow;
    }
  }

  /// Builds the WebSocket URL from relay URL and pairing code.
  ///
  /// Preserves the protocol if specified, otherwise defaults to wss://.
  /// Follows the format: {protocol}://{relayUrl}/ws/client/{pairingCode}
  ///
  /// For localhost/127.0.0.1 URLs without explicit protocol, uses ws:// (non-SSL)
  /// to support local testing with MockRelayServer.
  String _buildWebSocketUrl(String relayUrl, String pairingCode) {
    // Check if protocol is already specified
    final hasProtocol = RegExp(r'^(wss?://|https?://)').hasMatch(relayUrl);

    if (hasProtocol) {
      // Convert http(s) to ws(s)
      String cleanUrl = relayUrl
          .replaceAll(RegExp(r'^https://'), 'wss://')
          .replaceAll(RegExp(r'^http://'), 'ws://');
      return '$cleanUrl/ws/client/$pairingCode';
    }

    // No protocol specified - default based on host
    // Use ws:// for localhost/127.0.0.1 (testing), wss:// for everything else
    final isLocalhost = relayUrl.startsWith('localhost') ||
                        relayUrl.startsWith('127.0.0.1');
    final protocol = isLocalhost ? 'ws' : 'wss';

    return '$protocol://$relayUrl/ws/client/$pairingCode';
  }

  /// Starts listening to WebSocket messages.
  void _startListening() {
    _channelSubscription?.cancel();
    _channelSubscription = _channel?.stream.listen(
      _handleMessage,
      onError: _handleError,
      onDone: _handleDone,
      cancelOnError: false,
    );
  }

  /// Handles incoming WebSocket messages.
  void _handleMessage(dynamic message) {
    try {
      // Parse JSON message
      final Map<String, dynamic> json = jsonDecode(message as String);

      // Create MessageEnvelope from JSON
      final envelope = MessageEnvelope.fromJson(json);

      // Add to message stream
      _messageController.add(envelope);
    } catch (e) {
      stateManager.setError('Failed to parse message: $e');
      _errorController.add(e);
    }
  }

  /// Handles WebSocket errors.
  void _handleError(dynamic error) {
    stateManager.setError('WebSocket error: $error');
    _errorController.add(error);

    // Attempt reconnection if enabled
    if (_autoReconnect && !_intentionalDisconnect) {
      _scheduleReconnect();
    }
  }

  /// Handles WebSocket connection closure.
  ///
  /// This is called when the WebSocket stream completes (server closed connection,
  /// network error, or normal close). The state is updated synchronously to ensure
  /// listeners are notified immediately.
  void _handleDone() {
    // Clean up channel reference immediately to reflect disconnected state
    _channel = null;

    // Only reconnect if not intentionally disconnected
    if (!_intentionalDisconnect) {
      stateManager.setError('Connection closed unexpectedly');

      if (_autoReconnect) {
        _scheduleReconnect();
      } else {
        stateManager.setDisconnected();
      }
    } else {
      stateManager.setDisconnected();
    }
  }

  /// Schedules a reconnection attempt with exponential backoff.
  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      stateManager.setError('Max reconnection attempts reached');
      stateManager.setDisconnected();
      return;
    }

    _reconnectAttempts++;

    // Calculate exponential backoff delay
    final delay = _calculateBackoffDelay(_reconnectAttempts);

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      if (!_intentionalDisconnect) {
        _connect().catchError((e) {
          // Error already handled in _connect
        });
      }
    });
  }

  /// Calculates exponential backoff delay.
  ///
  /// Uses formula: baseDelay * (2 ^ attempt) with jitter
  /// Max delay capped at 60 seconds.
  Duration _calculateBackoffDelay(int attempt) {
    final baseMs = _baseReconnectDelay.inMilliseconds;
    final exponentialMs = baseMs * (1 << (attempt - 1)); // 2^(attempt-1)
    final cappedMs = exponentialMs.clamp(baseMs, 60000); // Max 60 seconds

    // Add 10% jitter to prevent thundering herd
    final jitterMs = (cappedMs * 0.1 * (DateTime.now().millisecond / 1000))
        .toInt();

    return Duration(milliseconds: cappedMs + jitterMs);
  }

  /// Sends an encrypted message to the relay server.
  ///
  /// The message is automatically encrypted using [MessageEnvelope.seal]
  /// before being sent.
  ///
  /// Args:
  ///   type: The message type
  ///   payloadData: The payload data (will be encrypted)
  ///
  /// Throws:
  ///   StateError: If not connected or keys not set
  Future<void> send(MessageType type, Map<String, dynamic> payloadData) async {
    if (!stateManager.isConnected) {
      throw StateError('Not connected to relay server');
    }

    if (_ourKeys == null || _remoteKeys == null) {
      throw StateError('Encryption keys not set');
    }

    if (_channel == null) {
      throw StateError('WebSocket channel not initialized');
    }

    try {
      // Create encrypted envelope
      final envelope = MessageEnvelope.seal(
        type,
        payloadData,
        _ourKeys!,
        _remoteKeys!,
      );

      // Serialize to JSON
      final json = jsonEncode(envelope.toJson());

      // Send through WebSocket
      _channel!.sink.add(json);
    } catch (e) {
      stateManager.setError('Failed to send message: $e');
      _errorController.add(e);
      rethrow;
    }
  }

  /// Sends a terminal input message to the remote agent.
  ///
  /// Convenience method for sending terminal input.
  ///
  /// Args:
  ///   input: The terminal input string
  Future<void> sendTerminalInput(String input) async {
    await send(MessageType.terminalInput, {'input': input});
  }

  /// Sends a terminal resize message to the remote agent.
  ///
  /// Convenience method for sending terminal dimension changes.
  ///
  /// Args:
  ///   rows: Number of terminal rows
  ///   cols: Number of terminal columns
  Future<void> sendResize(int rows, int cols) async {
    await send(MessageType.resize, {'rows': rows, 'cols': cols});
  }

  /// Sends a pairing request to the relay server.
  ///
  /// Convenience method for initial pairing handshake.
  ///
  /// Args:
  ///   data: Pairing data (e.g., public key exchange)
  Future<void> sendPairingRequest(Map<String, dynamic> data) async {
    await send(MessageType.pairingRequest, data);
  }

  /// Reconnects to the relay server.
  ///
  /// Disconnects if currently connected, then attempts to reconnect.
  ///
  /// Throws:
  ///   StateError: If relay URL or pairing code not set
  Future<void> reconnect() async {
    if (_relayUrl == null || _pairingCode == null) {
      throw StateError('Cannot reconnect: relay URL and pairing code not set');
    }

    // Cancel any pending reconnect timer
    _reconnectTimer?.cancel();

    // Close existing connection
    await _closeConnection();

    // Reset reconnect attempts
    _reconnectAttempts = 0;
    _intentionalDisconnect = false;

    // Reconnect
    await _connect();
  }

  /// Disconnects from the relay server.
  ///
  /// Closes the WebSocket connection cleanly and updates state to disconnected.
  Future<void> disconnect() async {
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    await _closeConnection();
    stateManager.setDisconnected();
  }

  /// Internal method to close WebSocket connection.
  ///
  /// Uses a timeout to prevent hanging on failed or incomplete connections.
  Future<void> _closeConnection() async {
    // Cancel subscription first to stop receiving messages
    await _channelSubscription?.cancel();
    _channelSubscription = null;

    // Close the channel with a timeout to prevent hanging
    // on failed or incomplete connections
    if (_channel != null) {
      try {
        await _channel!.sink.close().timeout(
          const Duration(seconds: 2),
          onTimeout: () {
            // Timeout expired - connection cleanup incomplete but we proceed
            // This happens when the connection was never fully established
          },
        );
      } catch (e) {
        // Ignore errors during close - we're disposing anyway
      }
      _channel = null;
    }
  }

  /// Gets a filtered stream of messages by type.
  ///
  /// Returns a stream that only emits messages of the specified type.
  ///
  /// Args:
  ///   type: The message type to filter by
  ///
  /// Returns: Stream of MessageEnvelope with the specified type
  Stream<MessageEnvelope> getMessagesByType(MessageType type) {
    return messageStream.where((msg) => msg.type == type);
  }

  /// Gets a stream of terminal output messages.
  ///
  /// Convenience method for filtering terminal output messages.
  Stream<MessageEnvelope> get terminalOutputStream {
    return getMessagesByType(MessageType.terminalOutput);
  }

  /// Gets a stream of pairing request messages.
  ///
  /// Convenience method for filtering pairing request messages.
  Stream<MessageEnvelope> get pairingRequestStream {
    return getMessagesByType(MessageType.pairingRequest);
  }

  /// Disposes of resources used by the client.
  ///
  /// Closes the WebSocket connection and all stream controllers.
  /// Must be called when the client is no longer needed.
  Future<void> dispose() async {
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    await _closeConnection();
    await _messageController.close();
    await _errorController.close();
    stateManager.dispose();
  }

  @override
  String toString() {
    return 'RelayClient(state: ${stateManager.currentState}, '
        'url: $_relayUrl, '
        'pairingCode: $_pairingCode, '
        'hasKeys: $hasKeys, '
        'reconnectAttempts: $_reconnectAttempts)';
  }
}
