# MyAgents Frontend

Flutter web and mobile frontend for MyAgents remote terminal access.

## Overview

MyAgentsFrontend provides a cross-platform frontend for remotely controlling Claude Code terminal sessions:
- **Web**: Primary development target
- **iOS/Android**: Future expansion using same codebase

## Architecture

```
MyAgentsFrontend (Flutter)
    │
    │ WSS (E2E encrypted)
    ▼
RemoteAgents Relay Server
    │
    │ WSS (E2E encrypted)
    ▼
Desktop CLI (Claude Code in PTY)
```

## Features

- Remote terminal view (xterm)
- E2E encrypted communication (NaCl/pinenacl)
- Voice-to-text input (Deepgram Nova-3)
- Session pairing via codes

## Related Repositories

- **RemoteAgents**: Python backend (relay server + terminal PTY wrapper)
- **MyAgents**: Python CLI integration

## Installation

```bash
# Prerequisites
flutter --version  # Ensure Flutter is installed

# Clone and setup
cd /home/code/myagents
git clone <repo> MyAgentsFrontend
cd MyAgentsFrontend
flutter pub get

# Run web
flutter run -d chrome
```

## Project Structure

```
lib/
├── main.dart
├── core/                    # Shared infrastructure
│   ├── config/
│   ├── crypto/              # E2E encryption (pinenacl)
│   ├── networking/          # WebSocket client
│   └── theme/
│
├── features/
│   ├── remote_terminal/     # Terminal display + input
│   ├── voice/               # Deepgram voice-to-text
│   └── pairing/             # Session pairing UI
│
└── routing/
```

## Development

```bash
# Run web in debug mode
flutter run -d chrome

# Run tests
flutter test

# Analyze code
flutter analyze

# Build web release
flutter build web
```

## Pairing Feature

### Overview

The pairing feature enables users to connect to remote Claude Code terminal sessions through a simple, secure flow:

1. User enters a 6-character alphanumeric pairing code
2. Frontend establishes an encrypted WebSocket connection to the relay server
3. Upon successful connection, user is automatically redirected to the terminal screen

The pairing feature follows a clean, separation-of-concerns architecture with three main components:

- **PairingState**: Immutable state model that represents the current pairing status, code validation, and error handling
- **PairingController**: Business logic layer that orchestrates key generation, relay connection, and state transitions
- **PairingScreen**: UI layer that provides the user interface and responds to state changes

This architecture ensures testability, maintainability, and clear data flow throughout the pairing process.

### Using the Pairing Screen

#### Navigation

The pairing screen is the initial route (`/`) of the application. When the app launches, users land directly on the pairing screen.

#### User Flow

1. **Enter Pairing Code**: User types a 6-character alphanumeric code in the input field
   - Code is automatically converted to uppercase
   - Only alphanumeric characters (A-Z, 0-9) are accepted
   - Input is limited to 6 characters
   - Real-time validation ensures code format is correct

2. **Connect**: Once a valid code is entered, the "Connect" button becomes enabled
   - Click the button to initiate connection
   - A loading spinner appears during connection attempt
   - Status message displays "Connecting to session..."

3. **Redirect**: Upon successful connection
   - Status message changes to "Connected! Redirecting..."
   - Automatic navigation to `/terminal` route
   - Terminal screen loads with active session

#### Behind the Scenes

When the user clicks "Connect", the following happens:

1. **Key Generation**: A new X25519 key pair is generated for end-to-end encryption
2. **Relay Connection**: WebSocket connection established to `wss://relay.remoteagents.dev/ws/client/{pairingCode}`
3. **State Management**: Connection state transitions from `idle` → `connecting` → `connected`
4. **Navigation**: React to connection success by navigating to terminal screen
5. **Error Handling**: If connection fails, appropriate error message is displayed:
   - "Invalid pairing code" (404 from relay)
   - "Connection timeout - please check your network" (timeout)
   - "Network error - please check your connection" (network issues)
   - "Failed to establish connection: ..." (WebSocket errors)

## CI/CD

This project uses Google Cloud Build for continuous integration. See [CI_CD.md](CI_CD.md) for setup and details.

**Quick Links:**
- [CI/CD Documentation](CI_CD.md) - Setup, monitoring, and troubleshooting
- [Trigger Reference](TRIGGERS.md) - Trigger configuration details

## License

Apache-2.0
