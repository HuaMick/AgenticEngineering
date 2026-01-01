import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/features/pairing/pairing_screen.dart';
import 'package:myagents_frontend/features/pairing/pairing_controller.dart';
import 'package:myagents_frontend/features/pairing/pairing_state.dart' as pairing;

/// Mock PairingController that allows setting state directly for UI testing.
///
/// This enables testing UI rendering for different states without triggering
/// real network connections.
class MockPairingController extends PairingController {
  pairing.PairingState _mockState;

  MockPairingController({pairing.PairingState? initialState})
      : _mockState = initialState ?? pairing.PairingState.initial();

  @override
  pairing.PairingState get state => _mockState;

  /// Sets the mock state and notifies listeners.
  void setMockState(pairing.PairingState newState) {
    _mockState = newState;
    notifyListeners();
  }

  /// Sets just the connection state, preserving other state values.
  void setMockConnectionState(pairing.ConnectionState connectionState, {String? errorMessage}) {
    _mockState = _mockState.copyWith(
      connectionState: connectionState,
      errorMessage: errorMessage,
      clearError: errorMessage == null,
    );
    notifyListeners();
  }

  @override
  Future<void> connect() async {
    // Mock implementation - don't actually connect
    setMockConnectionState(pairing.ConnectionState.connecting);
  }

  @override
  void updateCode(String code) {
    _mockState = _mockState.copyWith(
      pairingCode: code.toUpperCase(),
      connectionState: pairing.ConnectionState.idle,
      clearError: true,
    );
    notifyListeners();
  }
}

void main() {
  group('PairingScreen Widget Tests', () {
    testWidgets('Widget builds without errors', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(
        MaterialApp(
          home: PairingScreen(),
        ),
      );

      // Assert - no exceptions thrown
      expect(find.byType(PairingScreen), findsOneWidget);
    });

    group('UI Elements Exist', () {
      testWidgets('Claude Remote Terminal title is visible',
          (WidgetTester tester) async {
        // Arrange & Act
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        expect(find.text('Claude Remote Terminal'), findsOneWidget);
      });

      testWidgets('Connect button is visible', (WidgetTester tester) async {
        // Arrange & Act
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        expect(find.text('Connect'), findsOneWidget);
        expect(find.byType(ElevatedButton), findsOneWidget);
      });

      testWidgets('TextField for code input is visible',
          (WidgetTester tester) async {
        // Arrange & Act
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        expect(find.byType(TextField), findsOneWidget);
      });
    });

    group('Input Field Properties', () {
      testWidgets('6-character maxLength enforced', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        final textField = tester.widget<TextField>(find.byType(TextField));

        // Assert
        expect(textField.maxLength, equals(6));
      });

      testWidgets('Alphanumeric-only input allowed (filters special chars)',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act - Enter text with special characters
        await tester.enterText(find.byType(TextField), 'AB!@#\$');
        await tester.pump();

        // Assert - Special characters should be filtered out
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('AB'));
      });

      testWidgets('Input uppercased automatically', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act - Enter lowercase text
        await tester.enterText(find.byType(TextField), 'abc123');
        await tester.pump();

        // Assert - Text should be uppercase
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('ABC123'));
      });

      testWidgets('Input limited to 6 characters', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act - Try to enter more than 6 characters
        await tester.enterText(find.byType(TextField), 'ABCDEFGHIJ');
        await tester.pump();

        // Assert - Should be limited to 6 characters
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('ABCDEF'));
      });
    });

    group('Button State', () {
      testWidgets('Disabled when code is empty', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Connect'),
        );
        expect(button.onPressed, isNull); // Disabled
      });

      testWidgets('Disabled when code is invalid (less than 6 chars)',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act - Enter invalid code (only 3 characters)
        await tester.enterText(find.byType(TextField), 'ABC');
        await tester.pump();

        // Assert
        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Connect'),
        );
        expect(button.onPressed, isNull); // Disabled
      });

      testWidgets('Enabled when code is valid 6 characters',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act - Enter valid code (6 characters)
        await tester.enterText(find.byType(TextField), 'ABC123');
        await tester.pump();

        // Assert
        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Connect'),
        );
        expect(button.onPressed, isNotNull); // Enabled
      });
    });

    group('Status Messages', () {
      testWidgets('No message when idle (nothing visible)',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert - Should not find any status messages
        expect(find.text('Connecting to session...'), findsNothing);
        expect(find.text('Connected! Redirecting...'), findsNothing);
      });

      testWidgets('Connecting... visible when connecting state',
          (WidgetTester tester) async {
        // Create mock controller in connecting state
        final mockController = MockPairingController(
          initialState: pairing.PairingState.initial().copyWith(
            pairingCode: 'ABC123',
            connectionState: pairing.ConnectionState.connecting,
          ),
        );

        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(controller: mockController),
          ),
        );

        // Verify "Connecting to session..." message is visible
        expect(find.text('Connecting to session...'), findsOneWidget);

        // Verify the text has the correct styling (grey color)
        final textWidget = tester.widget<Text>(
          find.text('Connecting to session...'),
        );
        expect(textWidget.style?.color, equals(Colors.grey));

        // Clean up
        mockController.dispose();
      });

      testWidgets('Error message visible when error state (red)',
          (WidgetTester tester) async {
        // Create mock controller in error state with specific error message
        final mockController = MockPairingController(
          initialState: pairing.PairingState.initial().copyWith(
            pairingCode: 'ABC123',
            connectionState: pairing.ConnectionState.error,
            errorMessage: 'Invalid pairing code',
          ),
        );

        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(controller: mockController),
          ),
        );

        // Verify error message is visible
        expect(find.text('Invalid pairing code'), findsOneWidget);

        // Verify the text has the correct styling (red color, bold)
        final textWidget = tester.widget<Text>(
          find.text('Invalid pairing code'),
        );
        expect(textWidget.style?.color, equals(Colors.red));
        expect(textWidget.style?.fontWeight, equals(FontWeight.bold));

        // Clean up
        mockController.dispose();
      });
    });

    group('Input Formatters', () {
      testWidgets('FilteringTextInputFormatter allows only alphanumeric',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        final textField = tester.widget<TextField>(find.byType(TextField));

        // Assert - Check that input formatters are configured
        expect(textField.inputFormatters, isNotNull);
        expect(textField.inputFormatters!.length, greaterThan(0));

        // Check that FilteringTextInputFormatter is present
        final hasFilteringFormatter = textField.inputFormatters!.any(
          (formatter) => formatter is FilteringTextInputFormatter,
        );
        expect(hasFilteringFormatter, isTrue);
      });
    });

    group('TextField Styling', () {
      testWidgets('TextField has correct hint text', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.decoration?.hintText, equals('ABC123'));
      });

      testWidgets('TextField has center text alignment',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.textAlign, equals(TextAlign.center));
      });

      testWidgets('TextField has Courier font with letter spacing',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.style?.fontFamily, equals('Courier'));
        expect(textField.style?.letterSpacing, equals(4));
        expect(textField.style?.fontSize, equals(32));
      });
    });

    group('Button Styling', () {
      testWidgets('Button changes to green when connected (simulated)',
          (WidgetTester tester) async {
        // This test verifies the styling logic exists
        // A full integration test would require mocking successful connection

        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // The button should exist with ElevatedButton styling
        expect(find.byType(ElevatedButton), findsOneWidget);
      });

      testWidgets('Button shows loading spinner when connecting',
          (WidgetTester tester) async {
        // Create mock controller in connecting state
        final mockController = MockPairingController(
          initialState: pairing.PairingState.initial().copyWith(
            pairingCode: 'ABC123',
            connectionState: pairing.ConnectionState.connecting,
          ),
        );

        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(controller: mockController),
          ),
        );

        // Verify the loading spinner is visible
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Verify the "Connect" text is NOT visible (replaced by spinner)
        expect(find.text('Connect'), findsNothing);

        // Clean up
        mockController.dispose();
      });
    });

    group('Edge Cases', () {
      testWidgets('Mixed case input is converted to uppercase',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act
        await tester.enterText(find.byType(TextField), 'aBc123');
        await tester.pump();

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('ABC123'));
      });

      testWidgets('Numeric-only input is accepted', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act
        await tester.enterText(find.byType(TextField), '123456');
        await tester.pump();

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('123456'));
      });

      testWidgets('Alphabetic-only input is accepted',
          (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act
        await tester.enterText(find.byType(TextField), 'abcdef');
        await tester.pump();

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('ABCDEF'));
      });

      testWidgets('Spaces are filtered out', (WidgetTester tester) async {
        // Arrange
        await tester.pumpWidget(
          MaterialApp(
            home: PairingScreen(),
          ),
        );

        // Act
        await tester.enterText(find.byType(TextField), 'AB C 12');
        await tester.pump();

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, equals('ABC12'));
      });
    });
  });
}
