import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/core/crypto/message_envelope.dart';
import 'package:myagents_frontend/core/crypto/key_pair.dart';
import 'package:myagents_frontend/core/crypto/nacl_crypto.dart';

void main() {
  group('MessageEnvelope', () {
    late KeyPair clientKeys;
    late KeyPair serverKeys;

    setUp(() {
      // Generate fresh key pairs for each test
      clientKeys = KeyPair.generate();
      serverKeys = KeyPair.generate();
    });

    group('Message Creation - All Types', () {
      test('creates terminalInput message with payload', () {
        final payload = {'input': 'ls -la'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        expect(envelope.type, MessageType.terminalInput);
        expect(envelope.payload, isNotEmpty);
        expect(envelope.senderPublicKey, isNotEmpty);
        expect(envelope.timestamp, isNotNull);
      });

      test('creates terminalOutput message with payload', () {
        final payload = {'output': 'file1\nfile2'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalOutput,
          payload,
          serverKeys,
          clientKeys,
        );

        expect(envelope.type, MessageType.terminalOutput);
        expect(envelope.payload, isNotEmpty);
        expect(envelope.senderPublicKey, isNotEmpty);
        expect(envelope.timestamp, isNotNull);
      });

      test('creates resize message with payload', () {
        final payload = {'cols': 120, 'rows': 30};
        final envelope = MessageEnvelope.seal(
          MessageType.resize,
          payload,
          clientKeys,
          serverKeys,
        );

        expect(envelope.type, MessageType.resize);
        expect(envelope.payload, isNotEmpty);
        expect(envelope.senderPublicKey, isNotEmpty);
        expect(envelope.timestamp, isNotNull);
      });

      test('creates pairingRequest message with payload', () {
        final payload = {'pairing_code': 'TEST123'};
        final envelope = MessageEnvelope.seal(
          MessageType.pairingRequest,
          payload,
          clientKeys,
          serverKeys,
        );

        expect(envelope.type, MessageType.pairingRequest);
        expect(envelope.payload, isNotEmpty);
        expect(envelope.senderPublicKey, isNotEmpty);
        expect(envelope.timestamp, isNotNull);
      });
    });

    group('toJson/fromJson Round-Trip - All Types', () {
      test('terminalInput round-trip preserves all fields', () {
        final originalPayload = {'input': 'ls -la'};
        final original = MessageEnvelope.seal(
          MessageType.terminalInput,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        // Convert to JSON
        final json = original.toJson();

        // Parse back from JSON
        final restored = MessageEnvelope.fromJson(json);

        // Verify all fields match
        expect(restored.type, original.type);
        expect(restored.payload, original.payload);
        expect(restored.senderPublicKey, original.senderPublicKey);
        expect(
          restored.timestamp.toIso8601String(),
          original.timestamp.toIso8601String(),
        );
      });

      test('terminalOutput round-trip preserves all fields', () {
        final originalPayload = {'output': 'file1\nfile2'};
        final original = MessageEnvelope.seal(
          MessageType.terminalOutput,
          originalPayload,
          serverKeys,
          clientKeys,
        );

        final json = original.toJson();
        final restored = MessageEnvelope.fromJson(json);

        expect(restored.type, original.type);
        expect(restored.payload, original.payload);
        expect(restored.senderPublicKey, original.senderPublicKey);
        expect(
          restored.timestamp.toIso8601String(),
          original.timestamp.toIso8601String(),
        );
      });

      test('resize round-trip preserves all fields', () {
        final originalPayload = {'cols': 120, 'rows': 30};
        final original = MessageEnvelope.seal(
          MessageType.resize,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        final json = original.toJson();
        final restored = MessageEnvelope.fromJson(json);

        expect(restored.type, original.type);
        expect(restored.payload, original.payload);
        expect(restored.senderPublicKey, original.senderPublicKey);
        expect(
          restored.timestamp.toIso8601String(),
          original.timestamp.toIso8601String(),
        );
      });

      test('pairingRequest round-trip preserves all fields', () {
        final originalPayload = {'pairing_code': 'TEST123'};
        final original = MessageEnvelope.seal(
          MessageType.pairingRequest,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        final json = original.toJson();
        final restored = MessageEnvelope.fromJson(json);

        expect(restored.type, original.type);
        expect(restored.payload, original.payload);
        expect(restored.senderPublicKey, original.senderPublicKey);
        expect(
          restored.timestamp.toIso8601String(),
          original.timestamp.toIso8601String(),
        );
      });
    });

    group('seal/open Encryption - All Types', () {
      test('seal/open round-trip for terminalInput', () {
        final originalPayload = {'input': 'ls -la'};

        // Seal message from client to server
        final sealed = MessageEnvelope.seal(
          MessageType.terminalInput,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        // Verify payload is encrypted (Base64, not plaintext JSON)
        expect(sealed.payload, isNot(contains('ls -la')));
        expect(() => base64Decode(sealed.payload), returnsNormally);

        // Open message as server
        final decryptedPayload = sealed.open(serverKeys, clientKeys);

        // Verify decrypted payload matches original
        expect(decryptedPayload, originalPayload);
      });

      test('seal/open round-trip for terminalOutput', () {
        final originalPayload = {'output': 'file1\nfile2'};

        final sealed = MessageEnvelope.seal(
          MessageType.terminalOutput,
          originalPayload,
          serverKeys,
          clientKeys,
        );

        // Verify payload is encrypted
        expect(sealed.payload, isNot(contains('file1')));
        expect(() => base64Decode(sealed.payload), returnsNormally);

        final decryptedPayload = sealed.open(clientKeys, serverKeys);
        expect(decryptedPayload, originalPayload);
      });

      test('seal/open round-trip for resize', () {
        final originalPayload = {'cols': 120, 'rows': 30};

        final sealed = MessageEnvelope.seal(
          MessageType.resize,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        // Verify payload is encrypted
        expect(sealed.payload, isNot(contains('120')));
        expect(() => base64Decode(sealed.payload), returnsNormally);

        final decryptedPayload = sealed.open(serverKeys, clientKeys);
        expect(decryptedPayload, originalPayload);
      });

      test('seal/open round-trip for pairingRequest', () {
        final originalPayload = {'pairing_code': 'TEST123'};

        final sealed = MessageEnvelope.seal(
          MessageType.pairingRequest,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        // Verify payload is encrypted
        expect(sealed.payload, isNot(contains('TEST123')));
        expect(() => base64Decode(sealed.payload), returnsNormally);

        final decryptedPayload = sealed.open(serverKeys, clientKeys);
        expect(decryptedPayload, originalPayload);
      });

      test('encrypted payload is Base64-encoded', () {
        final payload = {'input': 'test command'};
        final sealed = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        // Should be valid Base64
        expect(() => base64Decode(sealed.payload), returnsNormally);

        // Should not contain plaintext
        expect(sealed.payload, isNot(contains('test command')));
        expect(sealed.payload, isNot(contains('input')));
      });
    });

    group('sender_public_key Field', () {
      test('sender_public_key is included in JSON', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        final json = envelope.toJson();

        expect(json.containsKey('sender_public_key'), isTrue);
        expect(json['sender_public_key'], isNotEmpty);
      });

      test('sender_public_key is Base64-encoded 32-byte key', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        final json = envelope.toJson();
        final publicKeyBase64 = json['sender_public_key'] as String;

        // Should be valid Base64
        final decoded = base64Decode(publicKeyBase64);

        // Should be exactly 32 bytes
        expect(decoded.length, 32);

        // Should match the client's public key
        expect(publicKeyBase64, base64Encode(clientKeys.publicKeyBytes));
      });
    });

    group('Timestamp Format', () {
      test('timestamp is in ISO 8601 format', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        final json = envelope.toJson();
        final timestamp = json['timestamp'] as String;

        // Should match ISO 8601 format: YYYY-MM-DDTHH:MM:SS.sss...Z (3-6 decimal places)
        final iso8601Pattern = RegExp(
          r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3,6}Z$',
        );
        expect(timestamp, matches(iso8601Pattern));
      });

      test('timestamp can be parsed back to DateTime', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        final json = envelope.toJson();
        final timestamp = json['timestamp'] as String;

        // Should parse without error
        final parsedTime = DateTime.parse(timestamp);

        // Should be in UTC
        expect(parsedTime.isUtc, isTrue);

        // Should match original timestamp
        expect(
          parsedTime.toIso8601String(),
          envelope.timestamp.toIso8601String(),
        );
      });

      test('timestamp is automatically set to current UTC time', () {
        final before = DateTime.now().toUtc();

        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        final after = DateTime.now().toUtc();

        // Timestamp should be between before and after
        expect(envelope.timestamp.isAfter(before.subtract(Duration(seconds: 1))), isTrue);
        expect(envelope.timestamp.isBefore(after.add(Duration(seconds: 1))), isTrue);
        expect(envelope.timestamp.isUtc, isTrue);
      });
    });

    group('Error Handling', () {
      test('fromJson throws on invalid JSON (malformed)', () {
        expect(
          () => MessageEnvelope.fromJson({}),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('fromJson throws on missing type field', () {
        final json = {
          'payload': 'test',
          'sender_public_key': 'test',
          'timestamp': '2025-12-04T10:30:00.000Z',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(
            isA<ArgumentError>().having(
              (e) => e.message,
              'message',
              contains('Missing required field: type'),
            ),
          ),
        );
      });

      test('fromJson throws on missing payload field', () {
        final json = {
          'type': 'terminal_input',
          'sender_public_key': 'test',
          'timestamp': '2025-12-04T10:30:00.000Z',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(
            isA<ArgumentError>().having(
              (e) => e.message,
              'message',
              contains('Missing required field: payload'),
            ),
          ),
        );
      });

      test('fromJson throws on missing sender_public_key field', () {
        final json = {
          'type': 'terminal_input',
          'payload': 'test',
          'timestamp': '2025-12-04T10:30:00.000Z',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(
            isA<ArgumentError>().having(
              (e) => e.message,
              'message',
              contains('Missing required field: sender_public_key'),
            ),
          ),
        );
      });

      test('fromJson throws on missing timestamp field', () {
        final json = {
          'type': 'terminal_input',
          'payload': 'test',
          'sender_public_key': 'test',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(
            isA<ArgumentError>().having(
              (e) => e.message,
              'message',
              contains('Missing required field: timestamp'),
            ),
          ),
        );
      });

      test('fromJson throws on invalid message type', () {
        final json = {
          'type': 'invalid_type',
          'payload': 'test',
          'sender_public_key': 'test',
          'timestamp': '2025-12-04T10:30:00.000Z',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(
            isA<ArgumentError>().having(
              (e) => e.message,
              'message',
              contains('Unknown message type'),
            ),
          ),
        );
      });

      test('open throws on corrupted encrypted payload', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        // Corrupt the payload by changing a character
        final corruptedPayload = envelope.payload.substring(0, 10) +
            'X' +
            envelope.payload.substring(11);
        final corruptedEnvelope = MessageEnvelope(
          type: envelope.type,
          payload: corruptedPayload,
          senderPublicKey: envelope.senderPublicKey,
          timestamp: envelope.timestamp,
        );

        expect(
          () => corruptedEnvelope.open(serverKeys, clientKeys),
          throwsA(isA<CryptoException>()),
        );
      });

      test('open throws with wrong sender public key (decryption fails)', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        // Try to decrypt with wrong sender keys
        final wrongKeys = KeyPair.generate();

        expect(
          () => envelope.open(serverKeys, wrongKeys),
          throwsA(isA<CryptoException>()),
        );
      });

      test('open throws with wrong recipient private key', () {
        final payload = {'input': 'test'};
        final envelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          payload,
          clientKeys,
          serverKeys,
        );

        // Try to decrypt with wrong recipient keys
        final wrongKeys = KeyPair.generate();

        expect(
          () => envelope.open(wrongKeys, clientKeys),
          throwsA(isA<CryptoException>()),
        );
      });

      test('fromJson throws on invalid timestamp format', () {
        final json = {
          'type': 'terminal_input',
          'payload': 'test',
          'sender_public_key': 'test',
          'timestamp': 'not-a-valid-timestamp',
        };

        expect(
          () => MessageEnvelope.fromJson(json),
          throwsA(isA<FormatException>()),
        );
      });
    });

    group('Message Type Snake Case Conversion', () {
      test('terminalInput converts to terminal_input', () {
        expect(MessageType.terminalInput.toSnakeCase(), 'terminal_input');
      });

      test('terminalOutput converts to terminal_output', () {
        expect(MessageType.terminalOutput.toSnakeCase(), 'terminal_output');
      });

      test('resize converts to resize', () {
        expect(MessageType.resize.toSnakeCase(), 'resize');
      });

      test('pairingRequest converts to pairing_request', () {
        expect(MessageType.pairingRequest.toSnakeCase(), 'pairing_request');
      });

      test('fromSnakeCase parses all types correctly', () {
        expect(
          MessageTypeExtension.fromSnakeCase('terminal_input'),
          MessageType.terminalInput,
        );
        expect(
          MessageTypeExtension.fromSnakeCase('terminal_output'),
          MessageType.terminalOutput,
        );
        expect(
          MessageTypeExtension.fromSnakeCase('resize'),
          MessageType.resize,
        );
        expect(
          MessageTypeExtension.fromSnakeCase('pairing_request'),
          MessageType.pairingRequest,
        );
      });
    });

    group('Integration Tests', () {
      test('full message lifecycle: create, serialize, deserialize, decrypt', () {
        // 1. Create original payload
        final originalPayload = {
          'input': 'ls -la',
          'metadata': {'user': 'test', 'session': '12345'},
        };

        // 2. Seal message from client to server
        final sealed = MessageEnvelope.seal(
          MessageType.terminalInput,
          originalPayload,
          clientKeys,
          serverKeys,
        );

        // 3. Serialize to JSON (for network transport)
        final json = sealed.toJson();
        final jsonString = jsonEncode(json);

        // 4. Deserialize from JSON (received on server)
        final receivedJson = jsonDecode(jsonString) as Map<String, dynamic>;
        final received = MessageEnvelope.fromJson(receivedJson);

        // 5. Verify envelope fields match
        expect(received.type, sealed.type);
        expect(received.payload, sealed.payload);
        expect(received.senderPublicKey, sealed.senderPublicKey);

        // 6. Decrypt payload
        final decryptedPayload = received.open(serverKeys, clientKeys);

        // 7. Verify payload matches original
        expect(decryptedPayload, originalPayload);
      });

      test('bidirectional communication between client and server', () {
        // Client sends to server
        final clientMessage = {'input': 'echo hello'};
        final clientEnvelope = MessageEnvelope.seal(
          MessageType.terminalInput,
          clientMessage,
          clientKeys,
          serverKeys,
        );

        // Server receives and decrypts
        final receivedByServer = clientEnvelope.open(serverKeys, clientKeys);
        expect(receivedByServer, clientMessage);

        // Server responds to client
        final serverMessage = {'output': 'hello'};
        final serverEnvelope = MessageEnvelope.seal(
          MessageType.terminalOutput,
          serverMessage,
          serverKeys,
          clientKeys,
        );

        // Client receives and decrypts
        final receivedByClient = serverEnvelope.open(clientKeys, serverKeys);
        expect(receivedByClient, serverMessage);
      });

      test('complex payload with nested structures', () {
        final complexPayload = {
          'input': 'complex command',
          'metadata': {
            'user': 'testuser',
            'session': 'abc123',
            'options': ['--verbose', '--debug'],
            'environment': {
              'PATH': '/usr/bin',
              'HOME': '/home/user',
            },
          },
        };

        final sealed = MessageEnvelope.seal(
          MessageType.terminalInput,
          complexPayload,
          clientKeys,
          serverKeys,
        );

        final decrypted = sealed.open(serverKeys, clientKeys);
        expect(decrypted, complexPayload);
      });
    });
  });
}
