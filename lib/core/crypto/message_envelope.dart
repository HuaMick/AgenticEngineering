import 'dart:convert';
import 'key_pair.dart';
import 'nacl_crypto.dart';

/// Message types supported by the RemoteAgents protocol
enum MessageType {
  /// User input to remote terminal
  terminalInput,

  /// Terminal output from remote agent
  terminalOutput,

  /// Terminal dimension changes
  resize,

  /// Initial pairing handshake
  pairingRequest,
}

/// Extension to convert MessageType to/from snake_case strings
extension MessageTypeExtension on MessageType {
  /// Converts MessageType to snake_case string for JSON serialization
  String toSnakeCase() {
    switch (this) {
      case MessageType.terminalInput:
        return 'terminal_input';
      case MessageType.terminalOutput:
        return 'terminal_output';
      case MessageType.resize:
        return 'resize';
      case MessageType.pairingRequest:
        return 'pairing_request';
    }
  }

  /// Parses snake_case string to MessageType enum
  static MessageType fromSnakeCase(String value) {
    switch (value) {
      case 'terminal_input':
        return MessageType.terminalInput;
      case 'terminal_output':
        return MessageType.terminalOutput;
      case 'resize':
        return MessageType.resize;
      case 'pairing_request':
        return MessageType.pairingRequest;
      default:
        throw ArgumentError('Unknown message type: $value');
    }
  }
}

/// Wraps protocol messages with encryption metadata for RemoteAgents communication.
///
/// MessageEnvelope provides encryption and serialization for all client-relay
/// communication. The protocol format matches RemoteAgents exactly:
/// {
///   "type": "terminal_input" | "terminal_output" | "resize" | "pairing_request",
///   "payload": <encrypted_data_base64>,
///   "sender_public_key": <base64>,
///   "timestamp": <iso8601>
/// }
///
/// The payload is always encrypted using NaClCrypto (X25519-XSalsa20-Poly1305).
class MessageEnvelope {
  /// The type of message being sent
  final MessageType type;

  /// The encrypted payload as Base64 string
  final String payload;

  /// The sender's public key as Base64 string (32 bytes)
  final String senderPublicKey;

  /// The timestamp when the message was created (UTC)
  final DateTime timestamp;

  /// Creates a MessageEnvelope with the specified fields.
  ///
  /// If timestamp is null, uses DateTime.now().toUtc().
  MessageEnvelope({
    required this.type,
    required this.payload,
    required this.senderPublicKey,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now().toUtc();

  /// Creates an encrypted MessageEnvelope from payload data.
  ///
  /// This factory method:
  /// 1. Converts payloadData to JSON string
  /// 2. Encrypts the JSON using NaClCrypto.encrypt()
  /// 3. Stores encrypted Base64 string in payload field
  /// 4. Includes our public key in senderPublicKey field
  /// 5. Creates MessageEnvelope with type, payload, senderPublicKey, timestamp
  ///
  /// Args:
  ///   type: The message type
  ///   payloadData: The data to encrypt (will be JSON encoded)
  ///   ourKeys: Our key pair (private key used for encryption)
  ///   recipientKeys: Recipient's key pair (public key used for encryption)
  ///
  /// Returns: A new MessageEnvelope with encrypted payload
  static MessageEnvelope seal(
    MessageType type,
    Map<String, dynamic> payloadData,
    KeyPair ourKeys,
    KeyPair recipientKeys,
  ) {
    // Convert payload data to JSON string
    final payloadJson = jsonEncode(payloadData);

    // Encrypt the JSON string
    final encryptedPayload = NaClCrypto.encrypt(
      payloadJson,
      ourKeys,
      recipientKeys,
    );

    // Get our public key as Base64
    final senderPublicKeyBase64 = base64Encode(ourKeys.publicKeyBytes);

    // Create and return the envelope
    return MessageEnvelope(
      type: type,
      payload: encryptedPayload,
      senderPublicKey: senderPublicKeyBase64,
    );
  }

  /// Decrypts and returns the payload data.
  ///
  /// This method:
  /// 1. Decrypts the payload using NaClCrypto.decrypt()
  /// 2. Parses the decrypted JSON string
  /// 3. Returns the payload data as Map
  ///
  /// Args:
  ///   ourKeys: Our key pair (private key used for decryption)
  ///   senderKeys: Sender's key pair (public key used for decryption)
  ///
  /// Returns: The decrypted payload data as Map
  ///
  /// Throws:
  ///   CryptoException: If decryption fails
  ///   FormatException: If JSON parsing fails
  Map<String, dynamic> open(KeyPair ourKeys, KeyPair senderKeys) {
    // Decrypt the payload
    final decryptedJson = NaClCrypto.decrypt(
      payload,
      ourKeys,
      senderKeys,
    );

    // Parse and return the JSON
    final payloadData = jsonDecode(decryptedJson);

    // Validate that the result is a Map
    if (payloadData is! Map<String, dynamic>) {
      throw const FormatException(
        'Decrypted payload is not a valid JSON object',
      );
    }

    return payloadData;
  }

  /// Creates a MessageEnvelope from a JSON map.
  ///
  /// Parses the protocol format:
  /// {
  ///   "type": "terminal_input",
  ///   "payload": "<base64>",
  ///   "sender_public_key": "<base64>",
  ///   "timestamp": "2025-12-04T10:30:00.000Z"
  /// }
  ///
  /// Throws:
  ///   ArgumentError: If required fields are missing
  ///   FormatException: If timestamp format is invalid
  factory MessageEnvelope.fromJson(Map<String, dynamic> json) {
    // Validate required fields
    if (!json.containsKey('type')) {
      throw ArgumentError('Missing required field: type');
    }
    if (!json.containsKey('payload')) {
      throw ArgumentError('Missing required field: payload');
    }
    if (!json.containsKey('sender_public_key')) {
      throw ArgumentError('Missing required field: sender_public_key');
    }
    if (!json.containsKey('timestamp')) {
      throw ArgumentError('Missing required field: timestamp');
    }

    // Parse type from snake_case string
    final type = MessageTypeExtension.fromSnakeCase(json['type'] as String);

    // Parse timestamp from ISO 8601 string
    final timestamp = DateTime.parse(json['timestamp'] as String);

    return MessageEnvelope(
      type: type,
      payload: json['payload'] as String,
      senderPublicKey: json['sender_public_key'] as String,
      timestamp: timestamp,
    );
  }

  /// Converts MessageEnvelope to JSON map.
  ///
  /// Returns the protocol format:
  /// {
  ///   "type": "terminal_input",
  ///   "payload": "<base64>",
  ///   "sender_public_key": "<base64>",
  ///   "timestamp": "2025-12-04T10:30:00.000Z"
  /// }
  Map<String, dynamic> toJson() {
    return {
      'type': type.toSnakeCase(),
      'payload': payload,
      'sender_public_key': senderPublicKey,
      'timestamp': timestamp.toIso8601String(),
    };
  }

  @override
  String toString() {
    return 'MessageEnvelope(type: ${type.toSnakeCase()}, '
        'senderPublicKey: ${senderPublicKey.substring(0, 8)}..., '
        'timestamp: ${timestamp.toIso8601String()})';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    if (other is! MessageEnvelope) return false;

    return type == other.type &&
        payload == other.payload &&
        senderPublicKey == other.senderPublicKey &&
        timestamp.isAtSameMomentAs(other.timestamp);
  }

  @override
  int get hashCode {
    return Object.hash(
      type,
      payload,
      senderPublicKey,
      timestamp,
    );
  }
}
