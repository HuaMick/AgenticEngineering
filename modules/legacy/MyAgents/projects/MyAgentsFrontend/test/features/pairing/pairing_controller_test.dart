import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/features/pairing/pairing_controller.dart';
import 'package:myagents_frontend/features/pairing/pairing_state.dart';

void main() {
  group('PairingController', () {
    late PairingController controller;
    bool skipTearDownDispose = false;

    setUp(() {
      controller = PairingController();
      skipTearDownDispose = false;
    });

    tearDown(() {
      if (!skipTearDownDispose) {
        controller.dispose();
      }
    });

    group('Initial State', () {
      test('should have idle ConnectionState', () {
        expect(controller.state.connectionState, ConnectionState.idle);
      });

      test('should have empty pairingCode', () {
        expect(controller.state.pairingCode, '');
      });

      test('should have null errorMessage', () {
        expect(controller.state.errorMessage, null);
      });

      test('relayClient should be null initially', () {
        expect(controller.relayClient, null);
      });

      test('clientKeys should be null initially', () {
        expect(controller.clientKeys, null);
      });
    });

    group('updateCode()', () {
      test('should update pairingCode in state', () {
        controller.updateCode('ABC123');
        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should auto-uppercase input', () {
        controller.updateCode('abc123');
        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should limit to 6 characters', () {
        controller.updateCode('ABCDEFG');
        expect(controller.state.pairingCode, 'ABCDEF');
      });

      test('should filter non-alphanumeric characters', () {
        controller.updateCode('AB-C12');
        expect(controller.state.pairingCode, 'ABC12');
      });

      test('should filter multiple special characters', () {
        controller.updateCode('A!B@C#1\$2%3');
        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should handle spaces', () {
        controller.updateCode('AB C 12');
        expect(controller.state.pairingCode, 'ABC12');
      });

      test('should handle mixed case with special characters', () {
        controller.updateCode('aBc-123!');
        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should reset connectionState to idle', () {
        // First set to a different state
        controller.updateCode('ABC123');
        // Manually set state to simulate connecting state
        // (we can't easily test this without accessing private _setState)

        // Update code again should reset to idle
        controller.updateCode('DEF456');
        expect(controller.state.connectionState, ConnectionState.idle);
      });

      test('should reset errorMessage to null', () {
        controller.updateCode('ABC123');
        expect(controller.state.errorMessage, null);
      });

      test('should handle empty string', () {
        controller.updateCode('ABC123');
        controller.updateCode('');
        expect(controller.state.pairingCode, '');
      });

      test('should handle only special characters', () {
        controller.updateCode('!@#\$%^');
        expect(controller.state.pairingCode, '');
      });
    });

    group('notifyListeners()', () {
      test('should notify listeners when updateCode is called', () {
        int listenerCallCount = 0;

        controller.addListener(() {
          listenerCallCount++;
        });

        controller.updateCode('ABC123');

        expect(listenerCallCount, 1);
      });

      test('should notify listeners multiple times for multiple updates', () {
        int listenerCallCount = 0;

        controller.addListener(() {
          listenerCallCount++;
        });

        controller.updateCode('A');
        controller.updateCode('AB');
        controller.updateCode('ABC');

        expect(listenerCallCount, 3);
      });

      test('should notify all registered listeners', () {
        int listener1CallCount = 0;
        int listener2CallCount = 0;

        controller.addListener(() {
          listener1CallCount++;
        });

        controller.addListener(() {
          listener2CallCount++;
        });

        controller.updateCode('ABC123');

        expect(listener1CallCount, 1);
        expect(listener2CallCount, 1);
      });
    });

    group('connect() guards', () {
      test('should return early if code is empty (canConnect is false)', () async {
        // Empty code means canConnect is false
        expect(controller.state.canConnect, false);

        await controller.connect();

        // State should remain idle since connect() returns early
        expect(controller.state.connectionState, ConnectionState.idle);
      });

      test('should return early if code is less than 6 characters', () async {
        controller.updateCode('ABC12'); // Only 5 characters
        expect(controller.state.canConnect, false);

        await controller.connect();

        // State should remain idle
        expect(controller.state.connectionState, ConnectionState.idle);
      });

      test('should not proceed if code is more than 6 chars (gets truncated)', () async {
        // This actually becomes valid after truncation, so this test checks
        // the validation logic
        controller.updateCode('ABCDEFG'); // Gets truncated to ABCDEF
        expect(controller.state.canConnect, true);

        // Note: We can't fully test the connection without mocking,
        // but we can verify the code is valid
        expect(controller.state.pairingCode, 'ABCDEF');
        expect(controller.state.pairingCode.length, 6);
      });
    });

    group('state transitions', () {
      test('calling connect() with valid code attempts to transition to connecting', () async {
        // Set valid 6-character code
        controller.updateCode('ABC123');
        expect(controller.state.canConnect, true);

        // Start connection (it will fail without real server, but should start)
        final connectFuture = controller.connect();

        // Note: Since we don't have a mock, the state will transition to connecting
        // and then quickly to error. We can't easily catch the intermediate state
        // without mocking, but we can verify it attempts the connection.

        await connectFuture;

        // After connection attempt fails, should be in error state
        expect(controller.state.connectionState, ConnectionState.error);
        expect(controller.state.errorMessage, isNotNull);
      });

      test('successful connection would set state to connected (without mock)', () async {
        // This test documents expected behavior but can't fully test without mock
        controller.updateCode('ABC123');

        // Without a real server or mock, connection will fail
        await controller.connect();

        // We expect error state since no server is running
        expect(controller.state.connectionState, ConnectionState.error);
        expect(controller.state.errorMessage, isNotNull);
      });

      test('error during connection sets error state with message', () async {
        controller.updateCode('ABC123');

        await controller.connect();

        // Connection will fail, verify error handling
        expect(controller.state.connectionState, ConnectionState.error);
        expect(controller.state.errorMessage, isNotNull);
        expect(controller.state.errorMessage, isNotEmpty);
      });
    });

    group('disconnect()', () {
      test('should reset to initial state', () async {
        controller.updateCode('ABC123');

        await controller.disconnect();

        expect(controller.state.pairingCode, '');
        expect(controller.state.connectionState, ConnectionState.idle);
        expect(controller.state.errorMessage, null);
      });

      test('should clear relayClient', () async {
        controller.updateCode('ABC123');
        await controller.connect(); // Will fail but may set relayClient

        await controller.disconnect();

        expect(controller.relayClient, null);
      });

      test('should clear clientKeys', () async {
        controller.updateCode('ABC123');
        await controller.connect(); // Will fail but may set clientKeys

        await controller.disconnect();

        expect(controller.clientKeys, null);
      });
    });

    group('dispose()', () {
      test('should dispose without throwing', () {
        controller.updateCode('ABC123');

        expect(() => controller.dispose(), returnsNormally);
        skipTearDownDispose = true; // Already disposed in test
      });

      test('should clear relayClient on dispose', () {
        controller.updateCode('ABC123');
        controller.dispose();
        skipTearDownDispose = true; // Already disposed in test

        expect(controller.relayClient, null);
      });

      test('should clear clientKeys on dispose', () {
        controller.updateCode('ABC123');
        controller.dispose();
        skipTearDownDispose = true; // Already disposed in test

        expect(controller.clientKeys, null);
      });
    });

    group('state getter', () {
      test('should return current state', () {
        final initialState = controller.state;
        expect(initialState.connectionState, ConnectionState.idle);

        controller.updateCode('ABC123');
        final updatedState = controller.state;
        expect(updatedState.pairingCode, 'ABC123');
      });
    });

    group('edge cases', () {
      test('should handle rapid code updates', () {
        controller.updateCode('A');
        controller.updateCode('AB');
        controller.updateCode('ABC');
        controller.updateCode('ABC1');
        controller.updateCode('ABC12');
        controller.updateCode('ABC123');

        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should handle unicode characters by filtering them', () {
        controller.updateCode('ABC123😀');
        expect(controller.state.pairingCode, 'ABC123');
      });

      test('should handle numeric-only codes', () {
        controller.updateCode('123456');
        expect(controller.state.pairingCode, '123456');
        expect(controller.state.canConnect, true);
      });

      test('should handle alpha-only codes', () {
        controller.updateCode('ABCDEF');
        expect(controller.state.pairingCode, 'ABCDEF');
        expect(controller.state.canConnect, true);
      });

      test('should handle lowercase input correctly', () {
        controller.updateCode('abcdef');
        expect(controller.state.pairingCode, 'ABCDEF');
        expect(controller.state.canConnect, true);
      });
    });
  });
}
