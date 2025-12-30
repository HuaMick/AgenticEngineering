import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../lib/core/crypto/key_pair.dart';
import '../lib/core/crypto/message_envelope.dart';
import '../lib/core/crypto/nacl_crypto.dart';

/// Mock relay server for testing RelayClient without RemoteAgents dependency.
///
/// This mock server simulates the RemoteAgents relay WebSocket behavior:
/// - Accepts connections at ws://localhost:{port}/ws/client/{pairing_code}
/// - Validates pairing code format (6 characters)
/// - Handles encrypted MessageEnvelope protocol
/// - Echoes terminal_input messages back as terminal_output
/// - Supports resize messages
/// - Handles disconnections and reconnections
///
/// Usage:
/// ```dart
/// final server = MockRelayServer();
/// await server.start();
/// final port = server.getPort();
/// // ... test with client ...
/// await server.stop();
/// ```
class MockRelayServer {
  HttpServer? _server;
  int? _port;

  /// Server's key pair for message encryption
  late KeyPair _serverKeys;

  /// Connected client WebSockets mapped by pairing code
  final Map<String, WebSocket> _clients = {};

  /// Client public keys mapped by pairing code
  final Map<String, KeyPair> _clientKeys = {};

  /// Messages received by the server (for test verification)
  final List<ReceivedMessage> _receivedMessages = [];

  /// Server configuration
  final MockRelayServerConfig _config;

  /// Create a new mock relay server with optional configuration
  MockRelayServer({MockRelayServerConfig? config})
      : _config = config ?? MockRelayServerConfig();

  /// Start the server on a random available port
  ///
  /// Returns the port number the server is listening on
  Future<int> start({int? port}) async {
    if (_server != null) {
      throw StateError('Server is already running');
    }

    // Generate server key pair
    _serverKeys = KeyPair.generate();

    // Start HTTP server
    _server = await HttpServer.bind(
      InternetAddress.loopbackIPv4,
      port ?? 0, // 0 = random available port
    );
    _port = _server!.port;

    // Handle incoming connections
    _server!.listen(_handleRequest);

    if (_config.verbose) {
      print('MockRelayServer started on port $_port');
      print('Server public key: ${base64Encode(_serverKeys.publicKeyBytes)}');
    }

    return _port!;
  }

  /// Stop the server and close all connections
  Future<void> stop() async {
    if (_server == null) {
      return;
    }

    if (_config.verbose) {
      print('MockRelayServer stopping...');
    }

    // Close all client connections (copy list to avoid concurrent modification)
    final clientsToClose = List<WebSocket>.from(_clients.values);
    for (final ws in clientsToClose) {
      try {
        await ws.close(WebSocketStatus.goingAway, 'Server shutting down');
      } catch (_) {
        // Ignore errors closing already-closed sockets
      }
    }
    _clients.clear();
    _clientKeys.clear();

    // Close server
    await _server!.close(force: true);
    _server = null;
    _port = null;

    if (_config.verbose) {
      print('MockRelayServer stopped');
    }
  }

  /// Get the server port
  ///
  /// Throws StateError if server is not running
  int getPort() {
    if (_port == null) {
      throw StateError('Server is not running');
    }
    return _port!;
  }

  /// Get the server's public key (for client pairing)
  KeyPair getServerKeys() => _serverKeys;

  /// Get all messages received by the server
  List<ReceivedMessage> getReceivedMessages() => List.unmodifiable(_receivedMessages);

  /// Clear received messages history
  void clearReceivedMessages() => _receivedMessages.clear();

  /// Force disconnect a client by pairing code
  ///
  /// Useful for testing reconnection logic
  Future<void> forceDisconnect(String pairingCode) async {
    final ws = _clients[pairingCode];
    if (ws != null) {
      await ws.close(WebSocketStatus.goingAway, 'Forced disconnect');
      _clients.remove(pairingCode);
      _clientKeys.remove(pairingCode);

      if (_config.verbose) {
        print('Force disconnected client: $pairingCode');
      }
    }
  }

  /// Check if a client is connected
  bool isClientConnected(String pairingCode) {
    return _clients.containsKey(pairingCode);
  }

  /// Send a message to a connected client
  ///
  /// Useful for testing client message handling
  Future<void> sendToClient(
    String pairingCode,
    MessageType type,
    Map<String, dynamic> payloadData,
  ) async {
    final ws = _clients[pairingCode];
    if (ws == null) {
      throw StateError('Client not connected: $pairingCode');
    }

    final clientKeys = _clientKeys[pairingCode];
    if (clientKeys == null) {
      throw StateError('Client keys not found: $pairingCode');
    }

    // Create encrypted envelope
    final envelope = MessageEnvelope.seal(
      type,
      payloadData,
      _serverKeys,
      clientKeys,
    );

    // Send to client
    ws.add(jsonEncode(envelope.toJson()));

    if (_config.verbose) {
      print('Sent ${type.toSnakeCase()} to client $pairingCode');
    }
  }

  /// Handle incoming HTTP requests
  void _handleRequest(HttpRequest request) async {
    try {
      final path = request.uri.path;

      // Check if this is a WebSocket upgrade request
      if (!WebSocketTransformer.isUpgradeRequest(request)) {
        request.response
          ..statusCode = HttpStatus.badRequest
          ..write('WebSocket upgrade required')
          ..close();
        return;
      }

      // Parse pairing code from path: /ws/client/{pairing_code}
      final pathMatch = RegExp(r'^/ws/client/([A-Za-z0-9]+)$').firstMatch(path);
      if (pathMatch == null) {
        request.response
          ..statusCode = HttpStatus.notFound
          ..write('Invalid path format. Expected: /ws/client/{pairing_code}')
          ..close();
        return;
      }

      final pairingCode = pathMatch.group(1)!;

      // Validate pairing code
      final validation = _validatePairingCode(pairingCode);
      if (!validation.isValid) {
        request.response
          ..statusCode = HttpStatus.badRequest
          ..write(validation.error)
          ..close();
        return;
      }

      // Upgrade to WebSocket
      final ws = await WebSocketTransformer.upgrade(request);

      // Store client connection
      _clients[pairingCode] = ws;

      if (_config.verbose) {
        print('Client connected: $pairingCode');
      }

      // Handle WebSocket messages
      _handleWebSocket(ws, pairingCode);
    } catch (e, stackTrace) {
      if (_config.verbose) {
        print('Error handling request: $e');
        print(stackTrace);
      }
      try {
        request.response
          ..statusCode = HttpStatus.internalServerError
          ..write('Internal server error')
          ..close();
      } catch (_) {
        // Ignore if already closed
      }
    }
  }

  /// Handle WebSocket connection for a client
  void _handleWebSocket(WebSocket ws, String pairingCode) {
    ws.listen(
      (dynamic message) {
        _handleMessage(ws, pairingCode, message);
      },
      onDone: () {
        _clients.remove(pairingCode);
        _clientKeys.remove(pairingCode);
        if (_config.verbose) {
          print('Client disconnected: $pairingCode');
        }
      },
      onError: (error) {
        if (_config.verbose) {
          print('WebSocket error for $pairingCode: $error');
        }
        _clients.remove(pairingCode);
        _clientKeys.remove(pairingCode);
      },
      cancelOnError: true,
    );
  }

  /// Handle incoming WebSocket message
  void _handleMessage(WebSocket ws, String pairingCode, dynamic message) async {
    try {
      if (message is! String) {
        if (_config.verbose) {
          print('Received non-string message from $pairingCode');
        }
        return;
      }

      // Parse JSON message
      final Map<String, dynamic> json;
      try {
        json = jsonDecode(message) as Map<String, dynamic>;
      } catch (e) {
        if (_config.verbose) {
          print('Invalid JSON from $pairingCode: $e');
        }
        return;
      }

      // Parse MessageEnvelope
      final MessageEnvelope envelope;
      try {
        envelope = MessageEnvelope.fromJson(json);
      } catch (e) {
        if (_config.verbose) {
          print('Invalid MessageEnvelope from $pairingCode: $e');
        }
        return;
      }

      // Extract client's public key
      final clientPublicKeyBytes = base64Decode(envelope.senderPublicKey);
      final clientKeys = KeyPair.fromBase64({
        'privateKey': base64Encode(KeyPair.generate().privateKeyBytes), // dummy private key
        'publicKey': envelope.senderPublicKey,
      });

      // Store client keys (update if changed)
      _clientKeys[pairingCode] = clientKeys;

      // Decrypt payload
      Map<String, dynamic> payloadData;
      try {
        payloadData = envelope.open(_serverKeys, clientKeys);
      } catch (e) {
        if (_config.verbose) {
          print('Failed to decrypt message from $pairingCode: $e');
        }
        return;
      }

      // Record received message
      _receivedMessages.add(ReceivedMessage(
        pairingCode: pairingCode,
        type: envelope.type,
        payload: payloadData,
        timestamp: envelope.timestamp,
      ));

      if (_config.verbose) {
        print('Received ${envelope.type.toSnakeCase()} from $pairingCode: $payloadData');
      }

      // Handle message based on type
      await _handleMessageByType(ws, pairingCode, envelope.type, payloadData);
    } catch (e, stackTrace) {
      if (_config.verbose) {
        print('Error handling message from $pairingCode: $e');
        print(stackTrace);
      }
    }
  }

  /// Handle message based on its type
  Future<void> _handleMessageByType(
    WebSocket ws,
    String pairingCode,
    MessageType type,
    Map<String, dynamic> payloadData,
  ) async {
    switch (type) {
      case MessageType.pairingRequest:
        await _handlePairingRequest(ws, pairingCode, payloadData);
        break;

      case MessageType.terminalInput:
        await _handleTerminalInput(ws, pairingCode, payloadData);
        break;

      case MessageType.resize:
        await _handleResize(ws, pairingCode, payloadData);
        break;

      case MessageType.terminalOutput:
        // Client shouldn't send terminal_output, but we'll accept it silently
        if (_config.verbose) {
          print('Warning: Client sent terminal_output message');
        }
        break;
    }
  }

  /// Handle pairing request
  Future<void> _handlePairingRequest(
    WebSocket ws,
    String pairingCode,
    Map<String, dynamic> payloadData,
  ) async {
    // For mock server, we auto-accept pairing
    // In real server, this would validate the request

    if (_config.autoRespondToPairing) {
      // Send pairing confirmation
      await sendToClient(
        pairingCode,
        MessageType.terminalOutput,
        {
          'data': 'Pairing successful! Connected to mock relay server.\r\n',
        },
      );
    }
  }

  /// Handle terminal input (echo back as terminal output)
  Future<void> _handleTerminalInput(
    WebSocket ws,
    String pairingCode,
    Map<String, dynamic> payloadData,
  ) async {
    if (!_config.echoTerminalInput) {
      return;
    }

    // Extract input data
    final data = payloadData['data'] as String?;
    if (data == null) {
      return;
    }

    // Echo back as terminal output
    final echoData = _config.echoPrefix + data + _config.echoSuffix;

    await sendToClient(
      pairingCode,
      MessageType.terminalOutput,
      {
        'data': echoData,
      },
    );
  }

  /// Handle resize message
  Future<void> _handleResize(
    WebSocket ws,
    String pairingCode,
    Map<String, dynamic> payloadData,
  ) async {
    // For mock server, we just acknowledge resize
    // In real server, this would resize the terminal

    if (_config.verbose) {
      final rows = payloadData['rows'];
      final cols = payloadData['cols'];
      print('Terminal resized: ${cols}x${rows}');
    }
  }

  /// Validate pairing code format
  _PairingCodeValidation _validatePairingCode(String pairingCode) {
    // Check length
    if (pairingCode.length != 6) {
      return _PairingCodeValidation(
        isValid: false,
        error: 'Pairing code must be exactly 6 characters',
      );
    }

    // Check characters (alphanumeric)
    if (!RegExp(r'^[A-Za-z0-9]+$').hasMatch(pairingCode)) {
      return _PairingCodeValidation(
        isValid: false,
        error: 'Pairing code must contain only alphanumeric characters',
      );
    }

    // Check against reject list
    if (_config.rejectedPairingCodes.contains(pairingCode)) {
      return _PairingCodeValidation(
        isValid: false,
        error: 'Pairing code rejected by server',
      );
    }

    return _PairingCodeValidation(isValid: true);
  }
}

/// Configuration for MockRelayServer behavior
class MockRelayServerConfig {
  /// Enable verbose logging
  final bool verbose;

  /// Echo terminal_input messages back as terminal_output
  final bool echoTerminalInput;

  /// Prefix to add to echoed messages
  final String echoPrefix;

  /// Suffix to add to echoed messages
  final String echoSuffix;

  /// Auto-respond to pairing requests
  final bool autoRespondToPairing;

  /// List of pairing codes to reject
  final Set<String> rejectedPairingCodes;

  const MockRelayServerConfig({
    this.verbose = false,
    this.echoTerminalInput = true,
    this.echoPrefix = '',
    this.echoSuffix = '',
    this.autoRespondToPairing = true,
    this.rejectedPairingCodes = const {},
  });

  /// Create a verbose config for debugging
  factory MockRelayServerConfig.verbose() {
    return const MockRelayServerConfig(verbose: true);
  }

  /// Create a config that rejects specific pairing codes
  factory MockRelayServerConfig.withRejectedCodes(Set<String> codes) {
    return MockRelayServerConfig(rejectedPairingCodes: codes);
  }

  /// Create a config that doesn't echo messages
  factory MockRelayServerConfig.noEcho() {
    return const MockRelayServerConfig(echoTerminalInput: false);
  }
}

/// Represents a message received by the server
class ReceivedMessage {
  /// The pairing code of the client that sent the message
  final String pairingCode;

  /// The message type
  final MessageType type;

  /// The decrypted payload data
  final Map<String, dynamic> payload;

  /// The timestamp from the message envelope
  final DateTime timestamp;

  /// When the server received the message (local time)
  final DateTime receivedAt;

  ReceivedMessage({
    required this.pairingCode,
    required this.type,
    required this.payload,
    required this.timestamp,
  }) : receivedAt = DateTime.now();

  @override
  String toString() {
    return 'ReceivedMessage(pairingCode: $pairingCode, '
        'type: ${type.toSnakeCase()}, '
        'payload: $payload, '
        'timestamp: ${timestamp.toIso8601String()})';
  }
}

/// Internal helper for pairing code validation
class _PairingCodeValidation {
  final bool isValid;
  final String? error;

  _PairingCodeValidation({required this.isValid, this.error});
}

/// Test helper functions for common scenarios
extension MockRelayServerTestHelpers on MockRelayServer {
  /// Create a server pre-configured for basic echo testing
  static Future<MockRelayServer> startEchoServer({int? port}) async {
    final server = MockRelayServer(
      config: MockRelayServerConfig.verbose(),
    );
    await server.start(port: port);
    return server;
  }

  /// Create a server that rejects specific pairing codes
  static Future<MockRelayServer> startWithRejectedCodes(
    Set<String> rejectedCodes, {
    int? port,
  }) async {
    final server = MockRelayServer(
      config: MockRelayServerConfig.withRejectedCodes(rejectedCodes),
    );
    await server.start(port: port);
    return server;
  }

  /// Create a server that doesn't echo messages
  static Future<MockRelayServer> startSilentServer({int? port}) async {
    final server = MockRelayServer(
      config: MockRelayServerConfig.noEcho(),
    );
    await server.start(port: port);
    return server;
  }

  /// Wait for a specific number of messages to be received
  Future<void> waitForMessages(int count, {Duration timeout = const Duration(seconds: 5)}) async {
    final start = DateTime.now();
    while (getReceivedMessages().length < count) {
      if (DateTime.now().difference(start) > timeout) {
        throw TimeoutException('Timeout waiting for $count messages');
      }
      await Future.delayed(const Duration(milliseconds: 100));
    }
  }

  /// Wait for a client to connect
  Future<void> waitForClient(String pairingCode, {Duration timeout = const Duration(seconds: 5)}) async {
    final start = DateTime.now();
    while (!isClientConnected(pairingCode)) {
      if (DateTime.now().difference(start) > timeout) {
        throw TimeoutException('Timeout waiting for client $pairingCode');
      }
      await Future.delayed(const Duration(milliseconds: 100));
    }
  }
}
