import 'dart:convert';
import 'package:pinenacl/x25519.dart';

/// Manages X25519 key generation and storage for E2E encryption.
///
/// This class uses the pinenacl package to match PyNaCl's behavior in RemoteAgents.
/// X25519 keys are 32 bytes each (256 bits) and are serialized as Base64 for transport.
class KeyPair {
  final PrivateKey _privateKey;
  final PublicKey _publicKey;

  /// Creates a KeyPair from existing pinenacl PrivateKey and PublicKey objects.
  ///
  /// The public key must be derived from the private key. This constructor
  /// validates that both keys are exactly 32 bytes.
  KeyPair._(this._privateKey, this._publicKey) {
    _validateKeyLengths();
    _validatePublicKeyDerivation();
  }

  /// Generates a new random X25519 key pair.
  ///
  /// Uses pinenacl's PrivateKey.generate() to create a cryptographically
  /// secure random private key, then derives the corresponding public key.
  ///
  /// Returns a new KeyPair instance.
  static KeyPair generate() {
    final privateKey = PrivateKey.generate();
    final publicKey = privateKey.publicKey;
    return KeyPair._(privateKey, publicKey);
  }

  /// Creates a KeyPair from Base64-encoded key strings.
  ///
  /// Expects a Map with 'privateKey' and 'publicKey' fields containing
  /// Base64-encoded 32-byte keys. This is the inverse of toBase64().
  ///
  /// Throws FormatException if the Base64 strings are invalid.
  /// Throws ArgumentError if the decoded keys are not exactly 32 bytes.
  static KeyPair fromBase64(Map<String, String> keys) {
    if (!keys.containsKey('privateKey') || !keys.containsKey('publicKey')) {
      throw ArgumentError(
        'Map must contain both "privateKey" and "publicKey" fields',
      );
    }

    final privateKeyBytes = base64Decode(keys['privateKey']!);
    final publicKeyBytes = base64Decode(keys['publicKey']!);

    if (privateKeyBytes.length != 32) {
      throw ArgumentError(
        'Private key must be exactly 32 bytes, got ${privateKeyBytes.length}',
      );
    }

    if (publicKeyBytes.length != 32) {
      throw ArgumentError(
        'Public key must be exactly 32 bytes, got ${publicKeyBytes.length}',
      );
    }

    final privateKey = PrivateKey(privateKeyBytes);
    final publicKey = PublicKey(publicKeyBytes);

    return KeyPair._(privateKey, publicKey);
  }

  /// Exports the key pair as Base64-encoded strings.
  ///
  /// Returns a Map with 'privateKey' and 'publicKey' fields containing
  /// Base64-encoded 32-byte keys suitable for transport or storage.
  Map<String, String> toBase64() {
    return {
      'privateKey': base64Encode(_privateKey.asTypedList),
      'publicKey': base64Encode(_publicKey.asTypedList),
    };
  }

  /// Gets the raw private key bytes as a Uint8List.
  ///
  /// Returns exactly 32 bytes representing the X25519 private key.
  Uint8List get privateKeyBytes => _privateKey.asTypedList;

  /// Gets the raw public key bytes as a Uint8List.
  ///
  /// Returns exactly 32 bytes representing the X25519 public key.
  Uint8List get publicKeyBytes => _publicKey.asTypedList;

  /// Gets the pinenacl PrivateKey object for use with Box encryption.
  ///
  /// This is useful when creating a Box for encryption/decryption operations.
  PrivateKey get privateKey => _privateKey;

  /// Gets the pinenacl PublicKey object for use with Box encryption.
  ///
  /// This is useful when creating a Box for encryption/decryption operations.
  PublicKey get publicKey => _publicKey;

  /// Validates that both private and public keys are exactly 32 bytes.
  ///
  /// Throws ArgumentError if either key is not the correct length.
  void _validateKeyLengths() {
    if (_privateKey.asTypedList.length != 32) {
      throw ArgumentError(
        'Private key must be exactly 32 bytes, got ${_privateKey.asTypedList.length}',
      );
    }

    if (_publicKey.asTypedList.length != 32) {
      throw ArgumentError(
        'Public key must be exactly 32 bytes, got ${_publicKey.asTypedList.length}',
      );
    }
  }

  /// Validates that the public key was correctly derived from the private key.
  ///
  /// This ensures that the public key matches what would be generated from
  /// the private key, preventing mismatched key pairs.
  ///
  /// Throws ArgumentError if the public key doesn't match the derived key.
  void _validatePublicKeyDerivation() {
    final derivedPublicKey = _privateKey.publicKey;
    final derivedBytes = derivedPublicKey.asTypedList;
    final providedBytes = _publicKey.asTypedList;

    if (derivedBytes.length != providedBytes.length) {
      throw ArgumentError(
        'Public key length mismatch: derived ${derivedBytes.length} bytes, '
        'provided ${providedBytes.length} bytes',
      );
    }

    for (int i = 0; i < derivedBytes.length; i++) {
      if (derivedBytes[i] != providedBytes[i]) {
        throw ArgumentError(
          'Public key does not match the key derived from private key',
        );
      }
    }
  }

  @override
  String toString() {
    return 'KeyPair(publicKey: ${base64Encode(_publicKey.asTypedList).substring(0, 8)}...)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    if (other is! KeyPair) return false;

    return _bytesEqual(_privateKey.asTypedList, other._privateKey.asTypedList) &&
           _bytesEqual(_publicKey.asTypedList, other._publicKey.asTypedList);
  }

  @override
  int get hashCode {
    return Object.hash(
      _hashBytes(_privateKey.asTypedList),
      _hashBytes(_publicKey.asTypedList),
    );
  }

  /// Helper method to compare two Uint8List byte arrays for equality.
  bool _bytesEqual(Uint8List a, Uint8List b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  /// Helper method to compute a hash code for a Uint8List.
  int _hashBytes(Uint8List bytes) {
    int hash = 0;
    for (int i = 0; i < bytes.length; i++) {
      hash = (hash * 31 + bytes[i]) & 0x3FFFFFFF;
    }
    return hash;
  }
}
