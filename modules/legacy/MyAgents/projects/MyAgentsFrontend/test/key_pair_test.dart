import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/core/crypto/key_pair.dart';

void main() {
  group('KeyPair', () {
    test('generate creates valid 32-byte keys', () {
      final keyPair = KeyPair.generate();

      expect(keyPair.privateKeyBytes.length, equals(32));
      expect(keyPair.publicKeyBytes.length, equals(32));
    });

    test('toBase64 and fromBase64 round-trip preserves keys', () {
      final original = KeyPair.generate();
      final encoded = original.toBase64();

      expect(encoded.containsKey('privateKey'), isTrue);
      expect(encoded.containsKey('publicKey'), isTrue);

      final decoded = KeyPair.fromBase64(encoded);

      expect(decoded.privateKeyBytes, equals(original.privateKeyBytes));
      expect(decoded.publicKeyBytes, equals(original.publicKeyBytes));
    });

    test('fromBase64 validates key lengths', () {
      // Test with invalid private key length
      final invalidPrivate = {
        'privateKey': base64Encode(List.filled(16, 0)),
        'publicKey': base64Encode(List.filled(32, 0)),
      };

      expect(
        () => KeyPair.fromBase64(invalidPrivate),
        throwsArgumentError,
      );

      // Test with invalid public key length
      final invalidPublic = {
        'privateKey': base64Encode(List.filled(32, 0)),
        'publicKey': base64Encode(List.filled(16, 0)),
      };

      expect(
        () => KeyPair.fromBase64(invalidPublic),
        throwsArgumentError,
      );
    });

    test('fromBase64 requires both keys', () {
      expect(
        () => KeyPair.fromBase64({'privateKey': 'test'}),
        throwsArgumentError,
      );

      expect(
        () => KeyPair.fromBase64({'publicKey': 'test'}),
        throwsArgumentError,
      );
    });

    test('public key derives correctly from private key', () {
      final keyPair = KeyPair.generate();

      // The public key should match what's derived from the private key
      final derivedPublicKey = keyPair.privateKey.publicKey;
      expect(
        keyPair.publicKeyBytes,
        equals(Uint8List.fromList(derivedPublicKey)),
      );
    });

    test('generates different keys on each call', () {
      final keyPair1 = KeyPair.generate();
      final keyPair2 = KeyPair.generate();

      expect(keyPair1.privateKeyBytes, isNot(equals(keyPair2.privateKeyBytes)));
      expect(keyPair1.publicKeyBytes, isNot(equals(keyPair2.publicKeyBytes)));
    });

    test('equality operator works correctly', () {
      final keyPair1 = KeyPair.generate();
      final encoded = keyPair1.toBase64();
      final keyPair2 = KeyPair.fromBase64(encoded);

      expect(keyPair1, equals(keyPair2));

      final keyPair3 = KeyPair.generate();
      expect(keyPair1, isNot(equals(keyPair3)));
    });

    test('toString returns readable format', () {
      final keyPair = KeyPair.generate();
      final str = keyPair.toString();

      expect(str, startsWith('KeyPair(publicKey:'));
      expect(str, contains('...'));
    });

    test('getters provide access to pinenacl types', () {
      final keyPair = KeyPair.generate();

      expect(keyPair.privateKey, isNotNull);
      expect(keyPair.publicKey, isNotNull);
      expect(keyPair.privateKeyBytes, isNotNull);
      expect(keyPair.publicKeyBytes, isNotNull);
    });
  });
}
