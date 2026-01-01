import 'package:flutter/foundation.dart';

/// Enum representing the various states of a WebSocket connection.
enum ConnectionState {
  /// Not connected to the server.
  disconnected,

  /// Connection attempt is in progress.
  connecting,

  /// Successfully connected to the server.
  connected,

  /// Attempting to reconnect after a disconnection.
  reconnecting,

  /// Connection error has occurred.
  error,
}

/// Manages the connection state of the WebSocket and notifies listeners
/// of state changes.
///
/// This class uses [ChangeNotifier] to provide reactive updates to the UI
/// when the connection state changes.
class ConnectionStateManager extends ChangeNotifier {
  ConnectionState _currentState = ConnectionState.disconnected;
  String? _errorMessage;
  DateTime? _lastStateChange;

  /// Gets the current connection state.
  ConnectionState get currentState => _currentState;

  /// Gets the last error message if the state is [ConnectionState.error].
  String? get errorMessage => _errorMessage;

  /// Gets the timestamp of the last state change.
  DateTime? get lastStateChange => _lastStateChange;

  /// Checks if currently connected.
  bool get isConnected => _currentState == ConnectionState.connected;

  /// Checks if currently connecting or reconnecting.
  bool get isConnecting =>
      _currentState == ConnectionState.connecting ||
      _currentState == ConnectionState.reconnecting;

  /// Checks if in error state.
  bool get hasError => _currentState == ConnectionState.error;

  /// Checks if disconnected.
  bool get isDisconnected => _currentState == ConnectionState.disconnected;

  /// Transitions to the connecting state.
  ///
  /// Valid from: [ConnectionState.disconnected]
  void setConnecting() {
    if (_currentState == ConnectionState.disconnected) {
      _updateState(ConnectionState.connecting);
      _clearError();
    }
  }

  /// Transitions to the connected state.
  ///
  /// Valid from: [ConnectionState.connecting], [ConnectionState.reconnecting]
  void setConnected() {
    if (_currentState == ConnectionState.connecting ||
        _currentState == ConnectionState.reconnecting) {
      _updateState(ConnectionState.connected);
      _clearError();
    }
  }

  /// Transitions to the disconnected state.
  ///
  /// Valid from: [ConnectionState.connected], [ConnectionState.error],
  /// [ConnectionState.connecting], [ConnectionState.reconnecting]
  void setDisconnected() {
    _updateState(ConnectionState.disconnected);
    _clearError();
  }

  /// Transitions to the reconnecting state.
  ///
  /// Valid from: [ConnectionState.disconnected], [ConnectionState.error],
  /// [ConnectionState.connected]
  void setReconnecting() {
    if (_currentState == ConnectionState.disconnected ||
        _currentState == ConnectionState.error ||
        _currentState == ConnectionState.connected) {
      _updateState(ConnectionState.reconnecting);
      _clearError();
    }
  }

  /// Transitions to the error state with an optional error message.
  ///
  /// Valid from: any state
  void setError(String? message) {
    _errorMessage = message;
    _updateState(ConnectionState.error);
  }

  /// Updates the current state and notifies listeners.
  void _updateState(ConnectionState newState) {
    if (_currentState != newState) {
      _currentState = newState;
      _lastStateChange = DateTime.now();
      notifyListeners();
    }
  }

  /// Clears the error message.
  void _clearError() {
    _errorMessage = null;
  }

  /// Resets the connection state manager to initial state.
  void reset() {
    _currentState = ConnectionState.disconnected;
    _errorMessage = null;
    _lastStateChange = null;
    notifyListeners();
  }

  @override
  String toString() {
    return 'ConnectionStateManager(state: $_currentState, error: $_errorMessage, lastChange: $_lastStateChange)';
  }
}
