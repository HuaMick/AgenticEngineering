import 'dart:convert';
import 'package:pinenacl/x25519.dart';
import 'key_pair.dart';

/// Custom exception for cryptographic operations failures
class CryptoException implements Exception {
  final String message;

  CryptoException(this.message);

  @override
  String toString() => 'CryptoException: $message';
}

/// NaCl Box encryption implementation using pinenacl
///
/// Implements X25519-XSalsa20-Poly1305 authenticated encryption compatible with PyNaCl.
/// Output format: Base64(nonce || ciphertext) where:
/// - nonce: 24 bytes (192 bits)
/// - ciphertext: variable length (includes 16-byte Poly1305 MAC)
class NaClCrypto {
  NaClCrypto._(); // Private constructor to prevent instantiation

  /// Encrypts plaintext using Box encryption (X25519-XSalsa20-Poly1305)
  ///
  /// Format: Base64-encoded (nonce || ciphertext)
  /// - Uses our private key + recipient's public key
  /// - Generates random 24-byte nonce automatically
  /// - Includes Poly1305 MAC in ciphertext (16 bytes at end)
  ///
  /// Args:
  ///   plaintext: The message to encrypt
  ///   ourKeys: Our key pair (uses private key)
  ///   recipientKeys: Recipient's key pair (uses public key)
  ///
  /// Returns: Base64-encoded (nonce || ciphertext)
  ///
  /// Throws:
  ///   ArgumentError: If keys are invalid
  static String encrypt(
    String plaintext,
    KeyPair ourKeys,
    KeyPair recipientKeys,
  ) {
    // Convert plaintext to UTF-8 bytes
    final plaintextBytes = utf8.encode(plaintext);

    // Create Box with our private key and recipient's public key
    final box = Box(
      myPrivateKey: ourKeys.privateKey,
      theirPublicKey: recipientKeys.publicKey,
    );

    // Encrypt plaintext - pinenacl automatically generates nonce
    // and returns EncryptedMessage containing (nonce || ciphertext)
    final encrypted = box.encrypt(plaintextBytes);

    // The EncryptedMessage already contains the proper format:
    // nonce (24 bytes) || ciphertext (with Poly1305 MAC)
    // Encode as Base64 for transport
    return base64.encode(encrypted);
  }

  /// Decrypts ciphertext using Box encryption (X25519-XSalsa20-Poly1305)
  ///
  /// Format: Base64-encoded (nonce || ciphertext)
  /// - Uses our private key + sender's public key
  /// - Extracts 24-byte nonce from beginning
  /// - Verifies Poly1305 MAC during decryption
  ///
  /// Args:
  ///   ciphertextBase64: Base64-encoded (nonce || ciphertext)
  ///   ourKeys: Our key pair (uses private key)
  ///   senderKeys: Sender's key pair (uses public key)
  ///
  /// Returns: Decrypted plaintext string
  ///
  /// Throws:
  ///   FormatException: If Base64 is invalid
  ///   ArgumentError: If nonce length is not 24 bytes
  ///   CryptoException: If decryption fails (wrong keys, corrupted data, MAC verification failed)
  static String decrypt(
    String ciphertextBase64,
    KeyPair ourKeys,
    KeyPair senderKeys,
  ) {
    // Decode Base64 to bytes
    final Uint8List encryptedBytes;
    try {
      encryptedBytes = base64Decode(ciphertextBase64);
    } catch (e) {
      throw FormatException('Invalid Base64 encoding: $e');
    }

    // Validate minimum length: nonce (24) + MAC (16) = 40 bytes minimum
    if (encryptedBytes.length < 40) {
      throw ArgumentError(
        'Invalid encrypted message: too short (${encryptedBytes.length} bytes, minimum 40)',
      );
    }

    // Split into nonce and ciphertext
    // First 24 bytes = nonce
    // Remaining bytes = ciphertext (includes Poly1305 MAC at end)
    final nonceBytes = encryptedBytes.sublist(0, 24);
    final ciphertextBytes = encryptedBytes.sublist(24);

    // Validate nonce length
    if (nonceBytes.length != 24) {
      throw ArgumentError(
        'Invalid nonce length: ${nonceBytes.length} bytes (expected 24)',
      );
    }

    // Create Box with our private key and sender's public key
    final box = Box(
      myPrivateKey: ourKeys.privateKey,
      theirPublicKey: senderKeys.publicKey,
    );

    // Decrypt using nonce and ciphertext
    final Uint8List decryptedBytes;
    try {
      // Create EncryptedMessage from nonce and ciphertext
      final encryptedMessage = EncryptedMessage(
        nonce: nonceBytes,
        cipherText: ciphertextBytes,
      );

      decryptedBytes = box.decrypt(encryptedMessage);
    } catch (e) {
      throw CryptoException(
        'Decryption failed: $e (wrong keys, corrupted data, or MAC verification failed)',
      );
    }

    // Convert decrypted bytes to UTF-8 string
    try {
      return utf8.decode(decryptedBytes);
    } catch (e) {
      throw CryptoException('Failed to decode UTF-8: $e');
    }
  }
}
