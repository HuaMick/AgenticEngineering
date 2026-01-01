/// Represents the different states of the pairing connection process
enum ConnectionState {
  /// Initial state before any connection attempt
  idle,

  /// Connection is currently in progress
  connecting,

  /// Successfully connected to the device
  connected,

  /// Connection failed with an error
  error,
}

/// Immutable state class for the pairing flow
///
/// This class manages the pairing code input, connection state,
/// and any error messages during the pairing process.
class PairingState {
  /// The current pairing code entered by the user
  final String pairingCode;

  /// The current state of the connection
  final ConnectionState connectionState;

  /// Error message if connection fails, null otherwise
  final String? errorMessage;

  const PairingState({
    required this.pairingCode,
    required this.connectionState,
    this.errorMessage,
  });

  /// Factory constructor for the initial state
  ///
  /// Returns a PairingState with empty code, idle connection state,
  /// and no error message.
  factory PairingState.initial() {
    return const PairingState(
      pairingCode: '',
      connectionState: ConnectionState.idle,
      errorMessage: null,
    );
  }

  /// Validates if the pairing code is valid
  ///
  /// A valid code must be exactly 6 alphanumeric characters.
  bool get isValidCode {
    if (pairingCode.length != 6) {
      return false;
    }

    // Check if all characters are alphanumeric
    final alphanumericRegex = RegExp(r'^[a-zA-Z0-9]+$');
    return alphanumericRegex.hasMatch(pairingCode);
  }

  /// Determines if a connection can be initiated
  ///
  /// Returns true if the code is valid and not currently connecting.
  bool get canConnect {
    return isValidCode && connectionState != ConnectionState.connecting;
  }

  /// Creates a copy of this state with updated fields
  ///
  /// Any fields not provided will retain their current values.
  ///
  /// To explicitly clear the error message, set [clearError] to true.
  /// When [clearError] is true, the errorMessage will be set to null
  /// regardless of the [errorMessage] parameter value.
  PairingState copyWith({
    String? pairingCode,
    ConnectionState? connectionState,
    String? errorMessage,
    bool clearError = false,
  }) {
    return PairingState(
      pairingCode: pairingCode ?? this.pairingCode,
      connectionState: connectionState ?? this.connectionState,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is PairingState &&
        other.pairingCode == pairingCode &&
        other.connectionState == connectionState &&
        other.errorMessage == errorMessage;
  }

  @override
  int get hashCode {
    return Object.hash(
      pairingCode,
      connectionState,
      errorMessage,
    );
  }

  @override
  String toString() {
    return 'PairingState('
        'pairingCode: $pairingCode, '
        'connectionState: $connectionState, '
        'errorMessage: $errorMessage'
        ')';
  }
}
