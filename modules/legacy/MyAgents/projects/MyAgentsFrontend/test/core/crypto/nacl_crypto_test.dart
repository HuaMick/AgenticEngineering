import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/core/crypto/nacl_crypto.dart';
import 'package:myagents_frontend/core/crypto/key_pair.dart';

void main() {
  group('NaClCrypto encrypt/decrypt round-trip tests', () {
    late KeyPair aliceKeys;
    late KeyPair bobKeys;

    setUp(() {
      // Generate two key pairs for Alice and Bob
      aliceKeys = KeyPair.generate();
      bobKeys = KeyPair.generate();
    });

    test('basic round-trip: Alice encrypts to Bob, Bob decrypts', () {
      const originalMessage = 'Hello, Bob! This is Alice.';

      // Alice encrypts message to Bob
      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Bob decrypts message from Alice
      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      // Verify plaintext matches original
      expect(decrypted, equals(originalMessage));
    });

    test('empty string message', () {
      const originalMessage = '';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });

    test('1 byte message', () {
      const originalMessage = 'a';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });

    test('100 bytes message (short sentence)', () {
      // Create a message that's approximately 100 bytes
      const originalMessage =
          'This is a short sentence that is approximately one hundred bytes long to test encryption and decryption.';

      expect(utf8.encode(originalMessage).length, greaterThanOrEqualTo(100));

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });

    test('1KB message (paragraph)', () {
      // Create a message that's approximately 1KB
      final originalMessage = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * 20;

      expect(utf8.encode(originalMessage).length, greaterThanOrEqualTo(1024));

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });

    test('verify nonce is 24 bytes and ciphertext format', () {
      const originalMessage = 'Test message for nonce verification';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Decode Base64 result
      final encryptedBytes = base64Decode(encrypted);

      // First 24 bytes should be nonce
      final nonceBytes = encryptedBytes.sublist(0, 24);
      expect(nonceBytes.length, equals(24));

      // Remaining bytes should be ciphertext (plaintext + 16-byte MAC)
      final ciphertextBytes = encryptedBytes.sublist(24);
      final plaintextBytes = utf8.encode(originalMessage);

      // Ciphertext should be plaintext length + 16 bytes for Poly1305 MAC
      expect(ciphertextBytes.length, equals(plaintextBytes.length + 16));

      // Total length should be nonce (24) + plaintext + MAC (16)
      expect(
        encryptedBytes.length,
        equals(24 + plaintextBytes.length + 16),
      );
    });

    test('different messages produce different nonces', () {
      const message = 'Same message encrypted twice';

      // Encrypt the same message twice
      final encrypted1 = NaClCrypto.encrypt(
        message,
        aliceKeys,
        bobKeys,
      );

      final encrypted2 = NaClCrypto.encrypt(
        message,
        aliceKeys,
        bobKeys,
      );

      // The encrypted messages should be different
      expect(encrypted1, isNot(equals(encrypted2)));

      // Extract nonces from both
      final encryptedBytes1 = base64Decode(encrypted1);
      final encryptedBytes2 = base64Decode(encrypted2);

      final nonce1 = encryptedBytes1.sublist(0, 24);
      final nonce2 = encryptedBytes2.sublist(0, 24);

      // Nonces should be different
      expect(_bytesEqual(nonce1, nonce2), isFalse);

      // But both should decrypt to the same plaintext
      final decrypted1 = NaClCrypto.decrypt(encrypted1, bobKeys, aliceKeys);
      final decrypted2 = NaClCrypto.decrypt(encrypted2, bobKeys, aliceKeys);

      expect(decrypted1, equals(message));
      expect(decrypted2, equals(message));
    });

    test('decrypt with wrong recipient keys throws CryptoException', () {
      const originalMessage = 'Secret message';

      // Alice encrypts to Bob
      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Generate a third party (Charlie) with different keys
      final charlieKeys = KeyPair.generate();

      // Charlie tries to decrypt with his keys (should fail)
      expect(
        () => NaClCrypto.decrypt(encrypted, charlieKeys, aliceKeys),
        throwsA(isA<CryptoException>()),
      );
    });

    test('decrypt with wrong sender keys throws CryptoException', () {
      const originalMessage = 'Secret message';

      // Alice encrypts to Bob
      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Generate a third party (Charlie) with different keys
      final charlieKeys = KeyPair.generate();

      // Bob tries to decrypt but uses Charlie's public key instead of Alice's
      expect(
        () => NaClCrypto.decrypt(encrypted, bobKeys, charlieKeys),
        throwsA(isA<CryptoException>()),
      );
    });

    test('corrupt ciphertext throws CryptoException', () {
      const originalMessage = 'Message to be corrupted';

      // Alice encrypts to Bob
      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Corrupt the ciphertext by flipping a byte
      final encryptedBytes = base64Decode(encrypted);

      // Flip a byte in the ciphertext (after the 24-byte nonce)
      // Make sure we modify the ciphertext part, not the nonce
      final corruptedBytes = Uint8List.fromList(encryptedBytes);
      corruptedBytes[30] ^= 0xFF; // Flip all bits of byte at index 30

      final corruptedEncrypted = base64Encode(corruptedBytes);

      // Attempting to decrypt corrupted ciphertext should throw
      expect(
        () => NaClCrypto.decrypt(corruptedEncrypted, bobKeys, aliceKeys),
        throwsA(isA<CryptoException>()),
      );
    });

    test('corrupt nonce throws CryptoException', () {
      const originalMessage = 'Message with corrupted nonce';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      // Corrupt the nonce by flipping a byte
      final encryptedBytes = base64Decode(encrypted);
      final corruptedBytes = Uint8List.fromList(encryptedBytes);
      corruptedBytes[5] ^= 0xFF; // Flip all bits of byte 5 in nonce

      final corruptedEncrypted = base64Encode(corruptedBytes);

      // Attempting to decrypt with corrupted nonce should throw
      expect(
        () => NaClCrypto.decrypt(corruptedEncrypted, bobKeys, aliceKeys),
        throwsA(isA<CryptoException>()),
      );
    });

    test('invalid base64 throws FormatException', () {
      expect(
        () => NaClCrypto.decrypt('invalid!base64!', bobKeys, aliceKeys),
        throwsA(isA<FormatException>()),
      );
    });

    test('too short encrypted message throws ArgumentError', () {
      // Create a message shorter than minimum 40 bytes (24 nonce + 16 MAC)
      final tooShort = base64Encode(Uint8List(39));

      expect(
        () => NaClCrypto.decrypt(tooShort, bobKeys, aliceKeys),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('bidirectional communication: Bob replies to Alice', () {
      const aliceMessage = 'Hello Bob, how are you?';
      const bobMessage = 'Hi Alice, I am doing well!';

      // Alice encrypts to Bob
      final encryptedToRob = NaClCrypto.encrypt(
        aliceMessage,
        aliceKeys,
        bobKeys,
      );

      // Bob decrypts Alice's message
      final decryptedByBob = NaClCrypto.decrypt(
        encryptedToRob,
        bobKeys,
        aliceKeys,
      );
      expect(decryptedByBob, equals(aliceMessage));

      // Bob encrypts reply to Alice
      final encryptedToAlice = NaClCrypto.encrypt(
        bobMessage,
        bobKeys,
        aliceKeys,
      );

      // Alice decrypts Bob's message
      final decryptedByAlice = NaClCrypto.decrypt(
        encryptedToAlice,
        aliceKeys,
        bobKeys,
      );
      expect(decryptedByAlice, equals(bobMessage));
    });

    test('unicode and special characters', () {
      const originalMessage = 'Hello 世界! 🚀 Special chars: @#\$%^&*()';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });

    test('multiline message', () {
      const originalMessage = '''This is a
multiline message
with several lines
and different indentation
  to test encryption''';

      final encrypted = NaClCrypto.encrypt(
        originalMessage,
        aliceKeys,
        bobKeys,
      );

      final decrypted = NaClCrypto.decrypt(
        encrypted,
        bobKeys,
        aliceKeys,
      );

      expect(decrypted, equals(originalMessage));
    });
  });
}

/// Helper function to compare two Uint8List byte arrays
bool _bytesEqual(Uint8List a, Uint8List b) {
  if (a.length != b.length) return false;
  for (int i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
