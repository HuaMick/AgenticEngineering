import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/features/pairing/pairing_state.dart';

void main() {
  group('ConnectionState enum', () {
    test('should have all 4 values: idle, connecting, connected, error', () {
      expect(ConnectionState.values.length, 4);
      expect(ConnectionState.values, contains(ConnectionState.idle));
      expect(ConnectionState.values, contains(ConnectionState.connecting));
      expect(ConnectionState.values, contains(ConnectionState.connected));
      expect(ConnectionState.values, contains(ConnectionState.error));
    });
  });

  group('PairingState constructor and properties', () {
    test('should create state with all properties', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.connected,
        errorMessage: 'Test error',
      );

      expect(state.pairingCode, 'ABC123');
      expect(state.connectionState, ConnectionState.connected);
      expect(state.errorMessage, 'Test error');
    });

    test('should create state with default null errorMessage', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
      );

      expect(state.pairingCode, 'ABC123');
      expect(state.connectionState, ConnectionState.idle);
      expect(state.errorMessage, isNull);
    });
  });

  group('isValidCode getter', () {
    test('should return true for valid code "ABC123"', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isTrue);
    });

    test('should return true for valid code "123456"', () {
      const state = PairingState(
        pairingCode: '123456',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isTrue);
    });

    test('should return true for valid code "AAABBB"', () {
      const state = PairingState(
        pairingCode: 'AAABBB',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isTrue);
    });

    test('should return false for code "ABC12" (too short)', () {
      const state = PairingState(
        pairingCode: 'ABC12',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isFalse);
    });

    test('should return false for code "ABC1234" (too long)', () {
      const state = PairingState(
        pairingCode: 'ABC1234',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isFalse);
    });

    test('should return false for code "ABC-12" (special char)', () {
      const state = PairingState(
        pairingCode: 'ABC-12',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isFalse);
    });

    test('should return false for empty code', () {
      const state = PairingState(
        pairingCode: '',
        connectionState: ConnectionState.idle,
      );
      expect(state.isValidCode, isFalse);
    });
  });

  group('canConnect getter', () {
    test('should return true for valid code and idle state', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
      );
      expect(state.canConnect, isTrue);
    });

    test('should return false for valid code and connecting state', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.connecting,
      );
      expect(state.canConnect, isFalse);
    });

    test('should return false for invalid code and idle state', () {
      const state = PairingState(
        pairingCode: 'ABC12',
        connectionState: ConnectionState.idle,
      );
      expect(state.canConnect, isFalse);
    });

    test('should return true for valid code and connected state', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.connected,
      );
      expect(state.canConnect, isTrue);
    });

    test('should return true for valid code and error state', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.error,
      );
      expect(state.canConnect, isTrue);
    });
  });

  group('copyWith()', () {
    test('should create new instance with updated pairingCode', () {
      const originalState = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Original error',
      );

      final newState = originalState.copyWith(pairingCode: 'NEW123');

      expect(newState.pairingCode, 'NEW123');
      expect(newState.connectionState, ConnectionState.idle);
      expect(newState.errorMessage, 'Original error');
      expect(newState, isNot(same(originalState)));
    });

    test('should create new instance with updated connectionState', () {
      const originalState = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Original error',
      );

      final newState = originalState.copyWith(
        connectionState: ConnectionState.error,
      );

      expect(newState.pairingCode, 'ABC123');
      expect(newState.connectionState, ConnectionState.error);
      expect(newState.errorMessage, 'Original error');
      expect(newState, isNot(same(originalState)));
    });

    test('should create new instance with updated errorMessage', () {
      const originalState = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Original error',
      );

      final newState = originalState.copyWith(errorMessage: 'New error');

      expect(newState.pairingCode, 'ABC123');
      expect(newState.connectionState, ConnectionState.idle);
      expect(newState.errorMessage, 'New error');
      expect(newState, isNot(same(originalState)));
    });

    test('should return equal state when called with no arguments', () {
      const originalState = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Original error',
      );

      final newState = originalState.copyWith();

      expect(newState.pairingCode, originalState.pairingCode);
      expect(newState.connectionState, originalState.connectionState);
      expect(newState.errorMessage, originalState.errorMessage);
      expect(newState, equals(originalState));
      expect(newState, isNot(same(originalState)));
    });

    test('should clear errorMessage when clearError is true', () {
      const stateWithError = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.error,
        errorMessage: 'Connection failed',
      );

      final clearedState = stateWithError.copyWith(clearError: true);

      expect(clearedState.pairingCode, 'ABC123');
      expect(clearedState.connectionState, ConnectionState.error);
      expect(clearedState.errorMessage, isNull);
    });

    test('clearError should take precedence over errorMessage parameter', () {
      const stateWithError = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.error,
        errorMessage: 'Old error',
      );

      // Even if errorMessage is provided, clearError: true should set it to null
      final clearedState = stateWithError.copyWith(
        clearError: true,
        errorMessage: 'New error',
      );

      expect(clearedState.errorMessage, isNull);
    });

    test('should update other fields while clearing error', () {
      const stateWithError = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.error,
        errorMessage: 'Connection failed',
      );

      final newState = stateWithError.copyWith(
        connectionState: ConnectionState.idle,
        clearError: true,
      );

      expect(newState.pairingCode, 'ABC123');
      expect(newState.connectionState, ConnectionState.idle);
      expect(newState.errorMessage, isNull);
    });
  });

  group('initial() factory', () {
    test('should create state with empty code', () {
      final state = PairingState.initial();
      expect(state.pairingCode, '');
    });

    test('should create state with idle connection state', () {
      final state = PairingState.initial();
      expect(state.connectionState, ConnectionState.idle);
    });

    test('should create state with null error message', () {
      final state = PairingState.initial();
      expect(state.errorMessage, isNull);
    });
  });

  group('equality and hashCode', () {
    test('should be equal when all properties match', () {
      const state1 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Error',
      );
      const state2 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Error',
      );

      expect(state1, equals(state2));
      expect(state1.hashCode, equals(state2.hashCode));
    });

    test('should not be equal when pairingCode differs', () {
      const state1 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
      );
      const state2 = PairingState(
        pairingCode: 'XYZ789',
        connectionState: ConnectionState.idle,
      );

      expect(state1, isNot(equals(state2)));
    });

    test('should not be equal when connectionState differs', () {
      const state1 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
      );
      const state2 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.connecting,
      );

      expect(state1, isNot(equals(state2)));
    });

    test('should not be equal when errorMessage differs', () {
      const state1 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Error 1',
      );
      const state2 = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Error 2',
      );

      expect(state1, isNot(equals(state2)));
    });
  });

  group('toString()', () {
    test('should return formatted string representation', () {
      const state = PairingState(
        pairingCode: 'ABC123',
        connectionState: ConnectionState.idle,
        errorMessage: 'Test error',
      );

      final result = state.toString();

      expect(result, contains('PairingState('));
      expect(result, contains('pairingCode: ABC123'));
      expect(result, contains('connectionState: ConnectionState.idle'));
      expect(result, contains('errorMessage: Test error'));
    });
  });
}
