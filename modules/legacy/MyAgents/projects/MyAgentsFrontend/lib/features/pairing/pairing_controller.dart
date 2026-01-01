import 'package:flutter/foundation.dart';
import '../../core/crypto/key_pair.dart';
import '../../core/networking/relay_client.dart';
import 'pairing_state.dart';

/// Controller for managing the pairing flow and connection logic.
///
/// This class orchestrates:
/// - Pairing code input validation and formatting
/// - Key pair generation for E2E encryption
/// - Relay server connection establishment
/// - State transitions during the pairing process
///
/// Usage:
/// ```dart
/// final controller = PairingController();
///
/// // Update pairing code
/// controller.updateCode('ABC123');
///
/// // Connect when ready
/// if (controller.state.canConnect) {
///   await controller.connect();
/// }
///
/// // Listen to state changes
/// controller.addListener(() {
///   print('State: ${controller.state}');
/// });
/// ```
class PairingController extends ChangeNotifier {
  /// Current pairing state
  PairingState _state = PairingState.initial();

  /// Relay client instance (created after successful connection)
  RelayClient? _relayClient;

  /// Client key pair (generated during connection)
  KeyPair? _clientKeys;

  /// Gets the current pairing state.
  PairingState get state => _state;

  /// Gets the relay client instance if connected.
  ///
  /// Returns null if not yet connected or connection failed.
  RelayClient? get relayClient => _relayClient;

  /// Gets the client key pair if generated.
  ///
  /// Returns null if keys haven't been generated yet.
  KeyPair? get clientKeys => _clientKeys;

  /// Updates the internal state and notifies listeners.
  ///
  /// This is the single point for state updates to ensure
  /// notifyListeners() is always called when state changes.
  void _setState(PairingState newState) {
    _state = newState;
    notifyListeners();
  }

  /// Updates the pairing code with validation and formatting.
  ///
  /// Applies the following transformations:
  /// - Converts to uppercase
  /// - Filters out non-alphanumeric characters
  /// - Limits to 6 characters maximum
  ///
  /// Args:
  ///   code: The input pairing code (can be partial or complete)
  void updateCode(String code) {
    // Convert to uppercase
    String formatted = code.toUpperCase();

    // Filter out non-alphanumeric characters
    formatted = formatted.replaceAll(RegExp(r'[^A-Z0-9]'), '');

    // Limit to 6 characters
    if (formatted.length > 6) {
      formatted = formatted.substring(0, 6);
    }

    // Update state with new code, reset connection state and error
    _setState(_state.copyWith(
      pairingCode: formatted,
      connectionState: ConnectionState.idle,
      clearError: true,
    ));
  }

  /// Initiates connection to the relay server.
  ///
  /// This method:
  /// 1. Validates that connection can proceed (checks state.canConnect)
  /// 2. Sets state to connecting
  /// 3. Generates a new client key pair
  /// 4. Creates a RelayClient instance
  /// 5. Connects to wss://relay.remoteagents.dev/ws/client/{pairingCode}
  /// 6. On success: Sets state to connected, stores RelayClient
  /// 7. On error: Sets state to error with appropriate error message
  ///
  /// Error handling:
  /// - Invalid pairing code (404): "Invalid pairing code"
  /// - Network timeout: "Connection timeout - please check your network"
  /// - Other errors: Descriptive error message from exception
  ///
  /// Throws:
  ///   StateError: If called when canConnect is false
  Future<void> connect() async {
    // Guard: Return early if connection cannot proceed
    if (!_state.canConnect) {
      return;
    }

    // Set state to connecting
    _setState(_state.copyWith(
      connectionState: ConnectionState.connecting,
      clearError: true,
    ));

    try {
      // Generate client key pair for E2E encryption
      _clientKeys = KeyPair.generate();

      // Create RelayClient instance with generated keys
      _relayClient = RelayClient();

      // Connect to relay server
      // URL format: wss://relay.remoteagents.dev/ws/client/{pairingCode}
      const relayUrl = 'relay.remoteagents.dev';
      await _relayClient!.connect(relayUrl, _state.pairingCode);

      // Connection successful - update state
      _setState(_state.copyWith(
        connectionState: ConnectionState.connected,
        clearError: true,
      ));
    } catch (e) {
      // Handle specific error types
      String errorMessage;

      final errorString = e.toString().toLowerCase();

      if (errorString.contains('404') || errorString.contains('not found')) {
        // Invalid pairing code (relay returned 404)
        errorMessage = 'Invalid pairing code';
      } else if (errorString.contains('timeout') ||
          errorString.contains('timed out')) {
        // Connection timeout
        errorMessage = 'Connection timeout - please check your network';
      } else if (errorString.contains('network') ||
          errorString.contains('connection refused') ||
          errorString.contains('failed to connect')) {
        // Network connectivity issues
        errorMessage = 'Network error - please check your connection';
      } else if (errorString.contains('websocket')) {
        // WebSocket-specific errors
        errorMessage = 'Failed to establish connection: ${e.toString()}';
      } else {
        // Generic error with exception details
        errorMessage = 'Connection failed: ${e.toString()}';
      }

      // Update state to error
      _setState(_state.copyWith(
        connectionState: ConnectionState.error,
        errorMessage: errorMessage,
      ));

      // Clean up relay client on error
      _relayClient?.dispose();
      _relayClient = null;
      _clientKeys = null;
    }
  }

  /// Disconnects from the relay server and resets state.
  ///
  /// Cleans up the RelayClient connection and resets to initial state.
  Future<void> disconnect() async {
    await _relayClient?.disconnect();
    _relayClient = null;
    _clientKeys = null;

    _setState(PairingState.initial());
  }

  /// Cleans up resources when the controller is disposed.
  ///
  /// Disposes of the RelayClient and any other resources.
  /// Must be called when the controller is no longer needed.
  @override
  void dispose() {
    _relayClient?.disconnect();
    _relayClient?.dispose();
    _relayClient = null;
    _clientKeys = null;
    super.dispose();
  }
}
