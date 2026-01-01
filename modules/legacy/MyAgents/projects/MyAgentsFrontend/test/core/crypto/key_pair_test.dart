import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/core/crypto/key_pair.dart';

void main() {
  group('KeyPair', () {
    // Test Case 1: Generate new KeyPair using KeyPair.generate()
    test('generate creates new KeyPair', () {
      final keyPair = KeyPair.generate();

      expect(keyPair, isNotNull);
      expect(keyPair.privateKeyBytes, isNotNull);
      expect(keyPair.publicKeyBytes, isNotNull);
    });

    // Test Case 2: Verify private key is 32 bytes
    test('private key is exactly 32 bytes', () {
      final keyPair = KeyPair.generate();

      expect(keyPair.privateKeyBytes.length, equals(32));
    });

    // Test Case 3: Verify public key is 32 bytes
    test('public key is exactly 32 bytes', () {
      final keyPair = KeyPair.generate();

      expect(keyPair.publicKeyBytes.length, equals(32));
    });

    // Test Case 4: Test toBase64() produces valid Base64 string
    test('toBase64 produces valid Base64 strings', () {
      final keyPair = KeyPair.generate();
      final encoded = keyPair.toBase64();

      // Check that both keys are present
      expect(encoded.containsKey('privateKey'), isTrue);
      expect(encoded.containsKey('publicKey'), isTrue);

      // Verify the strings are valid Base64 by attempting to decode them
      expect(() => base64Decode(encoded['privateKey']!), returnsNormally);
      expect(() => base64Decode(encoded['publicKey']!), returnsNormally);

      // Verify decoded length is 32 bytes
      final decodedPrivate = base64Decode(encoded['privateKey']!);
      final decodedPublic = base64Decode(encoded['publicKey']!);
      expect(decodedPrivate.length, equals(32));
      expect(decodedPublic.length, equals(32));
    });

    // Test Case 5: Test fromBase64() reconstructs original keys exactly
    test('fromBase64 reconstructs original keys exactly', () {
      final original = KeyPair.generate();
      final encoded = original.toBase64();
      final reconstructed = KeyPair.fromBase64(encoded);

      // Verify private key matches
      expect(reconstructed.privateKeyBytes, equals(original.privateKeyBytes));

      // Verify public key matches
      expect(reconstructed.publicKeyBytes, equals(original.publicKeyBytes));
    });

    // Test Case 6: Verify public key derives from private key consistently
    test('public key derives from private key consistently', () {
      final keyPair1 = KeyPair.generate();

      // The public key should match what's derived from the private key
      final derivedPublicKey = keyPair1.privateKey.publicKey;
      expect(
        keyPair1.publicKeyBytes,
        equals(Uint8List.fromList(derivedPublicKey)),
      );

      // Generate another keypair and verify the same property
      final keyPair2 = KeyPair.generate();
      final derivedPublicKey2 = keyPair2.privateKey.publicKey;
      expect(
        keyPair2.publicKeyBytes,
        equals(Uint8List.fromList(derivedPublicKey2)),
      );
    });

    // Test Case 7: Test round-trip: generate → toBase64 → fromBase64 → verify keys match
    test('round-trip generate to Base64 and back preserves keys', () {
      // Generate original keypair
      final original = KeyPair.generate();

      // Convert to Base64
      final base64Keys = original.toBase64();

      // Reconstruct from Base64
      final reconstructed = KeyPair.fromBase64(base64Keys);

      // Verify all bytes match exactly
      expect(reconstructed.privateKeyBytes, equals(original.privateKeyBytes));
      expect(reconstructed.publicKeyBytes, equals(original.publicKeyBytes));

      // Verify using equality operator
      expect(reconstructed, equals(original));
    });

    // Test Case 8: Edge case - Import invalid Base64 (should throw FormatException)
    test('fromBase64 throws FormatException for invalid Base64', () {
      final invalidBase64 = {
        'privateKey': 'not-valid-base64!!!',
        'publicKey': 'also-not-valid-base64!!!',
      };

      expect(
        () => KeyPair.fromBase64(invalidBase64),
        throwsFormatException,
      );
    });

    // Test Case 9: Edge case - Import keys with wrong length (should throw ArgumentError)
    test('fromBase64 throws ArgumentError for wrong length keys', () {
      // Test with private key that's too short (16 bytes instead of 32)
      final shortPrivateKey = {
        'privateKey': base64Encode(List.filled(16, 0)),
        'publicKey': base64Encode(List.filled(32, 0)),
      };

      expect(
        () => KeyPair.fromBase64(shortPrivateKey),
        throwsA(isA<ArgumentError>().having(
          (e) => e.message,
          'message',
          contains('Private key must be exactly 32 bytes'),
        )),
      );

      // Test with public key that's too short (16 bytes instead of 32)
      final shortPublicKey = {
        'privateKey': base64Encode(List.filled(32, 0)),
        'publicKey': base64Encode(List.filled(16, 0)),
      };

      expect(
        () => KeyPair.fromBase64(shortPublicKey),
        throwsA(isA<ArgumentError>().having(
          (e) => e.message,
          'message',
          contains('Public key must be exactly 32 bytes'),
        )),
      );

      // Test with private key that's too long (64 bytes instead of 32)
      final longPrivateKey = {
        'privateKey': base64Encode(List.filled(64, 0)),
        'publicKey': base64Encode(List.filled(32, 0)),
      };

      expect(
        () => KeyPair.fromBase64(longPrivateKey),
        throwsA(isA<ArgumentError>().having(
          (e) => e.message,
          'message',
          contains('Private key must be exactly 32 bytes'),
        )),
      );

      // Test with public key that's too long (64 bytes instead of 32)
      final longPublicKey = {
        'privateKey': base64Encode(List.filled(32, 0)),
        'publicKey': base64Encode(List.filled(64, 0)),
      };

      expect(
        () => KeyPair.fromBase64(longPublicKey),
        throwsA(isA<ArgumentError>().having(
          (e) => e.message,
          'message',
          contains('Public key must be exactly 32 bytes'),
        )),
      );
    });

    // Additional edge case: Missing keys in map
    test('fromBase64 throws ArgumentError when keys are missing from map', () {
      // Missing public key
      expect(
        () => KeyPair.fromBase64({'privateKey': 'test'}),
        throwsArgumentError,
      );

      // Missing private key
      expect(
        () => KeyPair.fromBase64({'publicKey': 'test'}),
        throwsArgumentError,
      );

      // Empty map
      expect(
        () => KeyPair.fromBase64({}),
        throwsArgumentError,
      );
    });

    // Additional test: Verify keys are different across generations
    test('generates different keys on each call', () {
      final keyPair1 = KeyPair.generate();
      final keyPair2 = KeyPair.generate();

      expect(keyPair1.privateKeyBytes, isNot(equals(keyPair2.privateKeyBytes)));
      expect(keyPair1.publicKeyBytes, isNot(equals(keyPair2.publicKeyBytes)));
    });

    // Additional test: Verify equality operator
    test('equality operator works correctly', () {
      final keyPair1 = KeyPair.generate();
      final encoded = keyPair1.toBase64();
      final keyPair2 = KeyPair.fromBase64(encoded);

      // Same keys should be equal
      expect(keyPair1, equals(keyPair2));

      // Different keys should not be equal
      final keyPair3 = KeyPair.generate();
      expect(keyPair1, isNot(equals(keyPair3)));
    });
  });
}
