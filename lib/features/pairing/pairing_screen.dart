import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'pairing_controller.dart';
import 'pairing_state.dart' as pairing;

/// Entry point UI for connecting to a remote session.
///
/// This screen provides a user interface for:
/// - Entering a 6-character alphanumeric pairing code
/// - Connecting to a remote session via the relay server
/// - Displaying connection status and error messages
/// - Navigating to the terminal screen upon successful connection
///
/// Supports dependency injection for testing:
/// ```dart
/// // Production usage - creates its own controller
/// PairingScreen()
///
/// // Test usage - inject mock controller
/// PairingScreen(controller: mockController)
/// ```
class PairingScreen extends StatefulWidget {
  /// Optional controller for dependency injection (used in tests).
  /// If null, a new PairingController is created internally.
  final PairingController? controller;

  const PairingScreen({super.key, this.controller});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  late final PairingController _controller;
  late final TextEditingController _textController;

  /// Whether we own the controller (created it) and should dispose it.
  late final bool _ownsController;

  @override
  void initState() {
    super.initState();
    // Use injected controller or create our own
    _ownsController = widget.controller == null;
    _controller = widget.controller ?? PairingController();
    _textController = TextEditingController();

    // Listen to controller state changes for navigation
    _controller.addListener(_handleStateChange);
  }

  @override
  void dispose() {
    _controller.removeListener(_handleStateChange);
    // Only dispose if we created the controller (not injected)
    if (_ownsController) {
      _controller.dispose();
    }
    _textController.dispose();
    super.dispose();
  }

  /// Handles state changes from the controller.
  ///
  /// Navigates to the terminal screen when successfully connected.
  void _handleStateChange() {
    if (_controller.state.connectionState == pairing.ConnectionState.connected) {
      // Navigate to terminal screen on successful connection
      if (mounted) {
        context.go('/terminal');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<PairingController>.value(
      value: _controller,
      child: Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Spacer(),
                // App title
                const Text(
                  'Claude Remote Terminal',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 48),
                // Pairing code input field
                _buildPairingCodeInput(),
                const SizedBox(height: 16),
                // Connect button
                _buildConnectButton(),
                const SizedBox(height: 16),
                // Status message
                _buildStatusMessage(),
                const Spacer(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Builds the pairing code input field.
  ///
  /// Features:
  /// - 6-character maximum length
  /// - Auto-uppercase input
  /// - Alphanumeric characters only
  /// - Monospace font with letter spacing for readability
  /// - Centered text
  Widget _buildPairingCodeInput() {
    return Consumer<PairingController>(
      builder: (context, controller, child) {
        return SizedBox(
          width: 300,
          child: TextField(
            controller: _textController,
            maxLength: 6,
            textCapitalization: TextCapitalization.characters,
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9]')),
            ],
            style: const TextStyle(
              fontSize: 32,
              fontFamily: 'Courier',
              letterSpacing: 4,
            ),
            textAlign: TextAlign.center,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'ABC123',
              counterText: '',
            ),
            onChanged: (value) {
              controller.updateCode(value);
              // Update text field to show formatted code
              final formatted = controller.state.pairingCode;
              if (formatted != value) {
                _textController.value = TextEditingValue(
                  text: formatted,
                  selection: TextSelection.collapsed(offset: formatted.length),
                );
              }
            },
          ),
        );
      },
    );
  }

  /// Builds the connect button.
  ///
  /// Features:
  /// - Shows "Connect" text or loading spinner based on state
  /// - Disabled when code is invalid or already connecting
  /// - Color changes based on connection state
  Widget _buildConnectButton() {
    return Consumer<PairingController>(
      builder: (context, controller, child) {
        final state = controller.state;
        final isConnecting = state.connectionState == pairing.ConnectionState.connecting;
        final isConnected = state.connectionState == pairing.ConnectionState.connected;

        return SizedBox(
          width: 200,
          height: 48,
          child: ElevatedButton(
            onPressed: state.canConnect ? controller.connect : null,
            style: ElevatedButton.styleFrom(
              backgroundColor: isConnected ? Colors.green : null,
            ),
            child: isConnecting
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Text(
                    'Connect',
                    style: TextStyle(fontSize: 16),
                  ),
          ),
        );
      },
    );
  }

  /// Builds the status message display.
  ///
  /// Shows different messages based on connection state:
  /// - idle: No message
  /// - connecting: "Connecting to session..." (gray)
  /// - connected: "Connected! Redirecting..." (green, bold)
  /// - error: Error message (red, bold)
  Widget _buildStatusMessage() {
    return Consumer<PairingController>(
      builder: (context, controller, child) {
        final state = controller.state;

        String message = '';
        Color color = Colors.grey;
        FontWeight fontWeight = FontWeight.normal;

        switch (state.connectionState) {
          case pairing.ConnectionState.idle:
            // No message
            break;
          case pairing.ConnectionState.connecting:
            message = 'Connecting to session...';
            color = Colors.grey;
            fontWeight = FontWeight.normal;
            break;
          case pairing.ConnectionState.connected:
            message = 'Connected! Redirecting...';
            color = Colors.green;
            fontWeight = FontWeight.bold;
            break;
          case pairing.ConnectionState.error:
            message = state.errorMessage ?? 'Connection failed';
            color = Colors.red;
            fontWeight = FontWeight.bold;
            break;
        }

        return SizedBox(
          height: 40,
          child: message.isNotEmpty
              ? Text(
                  message,
                  style: TextStyle(
                    color: color,
                    fontWeight: fontWeight,
                    fontSize: 14,
                  ),
                  textAlign: TextAlign.center,
                )
              : const SizedBox.shrink(),
        );
      },
    );
  }
}
