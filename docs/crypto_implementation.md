# Crypto Implementation Documentation

## Overview

This document describes the PyNaCl-based cryptographic implementation for the RemoteAgents protocol. The implementation provides a concrete wrapper around PyNaCl that implements the shared-contracts crypto interfaces, enabling secure end-to-end encrypted communication between Python services and Flutter clients.

### Architecture

- **Implementation**: PyNaCl wrapper (libsodium Python bindings)
- **Algorithm**: Curve25519-XSalsa20-Poly1305 (NaCl box)
- **Interfaces**: Implements `KeyPair`, `CryptoBox`, and `CryptoProvider` protocols from shared-contracts
- **Cross-platform compatibility**: Compatible with Flutter's pinenacl library

### Why Wrap PyNaCl?

1. **Interface Abstraction**: Provides protocol-based interfaces allowing different implementations
2. **Cross-platform Compatibility**: Ensures Python and Flutter implementations use identical formats
3. **Dependency Injection**: Factory pattern enables testing and alternative implementations
4. **Consistent API**: Normalizes PyNaCl's API to match shared-contracts specifications

### Cryptographic Algorithm

**NaCl Box (Curve25519-XSalsa20-Poly1305)**:
- **Key Exchange**: X25519 elliptic curve Diffie-Hellman
- **Encryption**: XSalsa20 stream cipher
- **Authentication**: Poly1305 MAC (16 bytes)
- **Key Format**: Raw 32-byte X25519 keys
- **Nonce**: 24 bytes, cryptographically random, unique per message

## Usage Examples

### Basic Encryption with DEFAULT_PROVIDER

```python
from agent_remote.shared.crypto import DEFAULT_PROVIDER

# Generate keypairs for Alice and Bob
alice_keypair = DEFAULT_PROVIDER.generate_keypair()
bob_keypair = DEFAULT_PROVIDER.generate_keypair()

# Alice creates a box and encrypts a message for Bob
alice_box = DEFAULT_PROVIDER.create_box(alice_keypair)
nonce, ciphertext = alice_box.encrypt(
    b"Hello Bob!",
    bob_keypair.public_key
)

# Bob creates a box and decrypts the message from Alice
bob_box = DEFAULT_PROVIDER.create_box(bob_keypair)
plaintext = bob_box.decrypt(
    ciphertext,
    nonce,
    alice_keypair.public_key
)
assert plaintext == b"Hello Bob!"
```

### Base64 Encoding for JSON Transport

The relay service uses base64 encoding to transmit binary crypto data in JSON messages:

```python
from agent_remote.shared.crypto import (
    DEFAULT_PROVIDER,
    bytes_to_base64,
    base64_to_bytes
)

# Encrypt a message
keypair = DEFAULT_PROVIDER.generate_keypair()
recipient_keypair = DEFAULT_PROVIDER.generate_keypair()
box = DEFAULT_PROVIDER.create_box(keypair)
nonce, ciphertext = box.encrypt(b"message", recipient_keypair.public_key)

# Encode for JSON (used in EncryptedBlob)
nonce_b64 = bytes_to_base64(nonce)
ciphertext_b64 = bytes_to_base64(ciphertext)

# Later: decode from JSON
nonce = base64_to_bytes(nonce_b64)
ciphertext = base64_to_bytes(ciphertext_b64)

# Decrypt
recipient_box = DEFAULT_PROVIDER.create_box(recipient_keypair)
plaintext = recipient_box.decrypt(ciphertext, nonce, keypair.public_key)
```

### Using Convenience Functions

```python
from agent_remote.shared.crypto import (
    generate_keypair,
    keypair_from_bytes,
    NaClBox
)

# Generate and save keypair
keypair = generate_keypair()
private_key_bytes = keypair.private_key

# Later: restore keypair from saved private key
restored_keypair = keypair_from_bytes(private_key_bytes)
assert restored_keypair.public_key == keypair.public_key

# Create box directly
box = NaClBox(keypair)
```

### Error Handling Patterns

```python
from agent_remote.shared.crypto import DEFAULT_PROVIDER

alice_keypair = DEFAULT_PROVIDER.generate_keypair()
bob_keypair = DEFAULT_PROVIDER.generate_keypair()
alice_box = DEFAULT_PROVIDER.create_box(alice_keypair)

# Encrypt message
nonce, ciphertext = alice_box.encrypt(b"Secret", bob_keypair.public_key)

# Decryption with error handling
bob_box = DEFAULT_PROVIDER.create_box(bob_keypair)
try:
    plaintext = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)
except ValueError as e:
    # MAC verification failed (wrong key, wrong nonce, or tampering)
    print(f"Decryption failed: {e}")
    # Message should be rejected - do not retry
```

## Implementation Details

### X25519 Keys

**Format**: Raw 32-byte X25519 keys (no headers, no encoding wrappers)

- **Public Key**: 32 bytes, can be safely transmitted
- **Private Key**: 32 bytes, must be kept secret, never transmitted
- **Encoding**: Uses `nacl.encoding.RawEncoder` for pinenacl compatibility

```python
# Key generation
keypair = generate_keypair()
assert len(keypair.public_key) == 32
assert len(keypair.private_key) == 32
assert isinstance(keypair.public_key, bytes)
assert isinstance(keypair.private_key, bytes)
```

### encrypt() Return Format

**Signature**: `encrypt(plaintext: bytes, their_public_key: PublicKey) -> tuple[Nonce, Ciphertext]`

The encrypt method returns a tuple with the nonce and ciphertext as separate components:

- **Nonce**: First element, 24 bytes, randomly generated
- **Ciphertext**: Second element, encrypted data with 16-byte Poly1305 MAC appended
- **Length**: `len(ciphertext) == len(plaintext) + 16`

```python
nonce, ciphertext = box.encrypt(b"Hello", recipient_public_key)

assert len(nonce) == 24
assert len(ciphertext) == len(b"Hello") + 16  # Message + MAC
assert isinstance(nonce, bytes)
assert isinstance(ciphertext, bytes)
```

**Important**: PyNaCl internally combines nonce and ciphertext, but our interface returns them separately to match the shared-contracts specification and EncryptedBlob message format.

### decrypt() Parameters

**Signature**: `decrypt(ciphertext: Ciphertext, nonce: Nonce, their_public_key: PublicKey) -> bytes`

The decrypt method accepts three separate parameters:

1. **ciphertext**: Encrypted data with 16-byte MAC (minimum 16 bytes)
2. **nonce**: The 24-byte nonce used during encryption
3. **their_public_key**: Sender's 32-byte X25519 public key

```python
plaintext = box.decrypt(ciphertext, nonce, sender_public_key)
```

**Important**: PyNaCl expects combined `nonce || ciphertext` format internally, but our interface accepts them as separate parameters to match shared-contracts specification.

### Nonce Generation and Requirements

**Nonce**: 24-byte random value, unique per message

- **Generation**: Cryptographically secure random (via `nacl.utils.random()`)
- **Uniqueness**: MUST be unique for each message encrypted with the same key pair
- **Security**: Reusing a nonce with the same key pair catastrophically breaks security
- **Transmission**: Nonce must be transmitted with ciphertext (not secret)

```python
# Each encrypt() call generates a fresh random nonce
nonce1, ciphertext1 = box.encrypt(b"Message 1", recipient_pk)
nonce2, ciphertext2 = box.encrypt(b"Message 2", recipient_pk)

assert nonce1 != nonce2  # Different nonces for different messages
```

### Ciphertext Format

**Ciphertext**: Encrypted plaintext with 16-byte Poly1305 MAC appended

- **Format**: `encrypted_data || 16-byte MAC`
- **Length**: Always 16 bytes longer than plaintext
- **MAC**: Provides authentication and integrity verification
- **Minimum**: 16 bytes (empty plaintext + MAC)

```python
plaintext = b"Test message"
nonce, ciphertext = box.encrypt(plaintext, recipient_pk)

assert len(ciphertext) == len(plaintext) + 16
assert len(ciphertext) >= 16  # Minimum size with MAC
```

**MAC Verification**: During decryption, the Poly1305 MAC is verified. Any tampering, wrong keys, or wrong nonce causes MAC verification to fail with a `ValueError`.

### Input Validation

All crypto methods validate inputs and raise clear errors:

```python
# Key length validation
try:
    keypair_from_bytes(b"wrong_length")
except ValueError as e:
    # "Private key must be exactly 32 bytes, got N bytes"
    pass

# Nonce length validation
try:
    box.decrypt(ciphertext, b"short_nonce", sender_pk)
except ValueError as e:
    # "nonce must be exactly 24 bytes, got N bytes"
    pass

# Ciphertext minimum length validation
try:
    box.decrypt(b"too_short", valid_nonce, sender_pk)
except ValueError as e:
    # "ciphertext must be at least 16 bytes (for Poly1305 MAC)"
    pass

# Public key length validation
try:
    box.encrypt(b"message", b"wrong_length_key")
except ValueError as e:
    # "their_public_key must be exactly 32 bytes (X25519 format)"
    pass
```

## Testing

### Running Tests

```bash
# Run all crypto tests
pytest tests/shared/ -v

# Run specific test class
pytest tests/shared/test_crypto.py::TestUtilitiesAndFactory -v
pytest tests/shared/test_crypto.py::TestDecryptionSignature -v

# Run test vectors (interoperability validation)
pytest tests/shared/test_vectors.py -v
```

### Test Coverage

The implementation includes **76 comprehensive tests** organized into focused test classes:

**TestUtilitiesAndFactory** (17 tests):
- Base64 encoding/decoding utilities
- NaClProvider factory methods
- Exported API validation
- Module docstring usage examples

**TestDecryptionSignature** (7 tests):
- Signature compliance with shared-contracts
- Round trip encryption/decryption
- Error handling (wrong nonce, wrong key, truncated ciphertext)
- Input validation (nonce length, public key length)

**Test Vector Validation** (52 tests):
- Key format test vectors (pinenacl compatibility)
- Encryption/decryption test vectors
- Protocol message serialization vectors
- Cross-platform compatibility validation

### Test Vector Validation

Test vectors in `tests/shared/fixtures/crypto_vectors.json` validate cross-platform compatibility between PyNaCl and pinenacl:

- **Key Format Vectors**: Verify 32-byte X25519 key format matches pinenacl
- **Encryption Vectors**: Known plaintext/nonce/ciphertext for decrypt validation
- **Round Trip Vectors**: Ensure encrypt/decrypt produces identical results

These vectors ensure that Python and Flutter implementations can communicate successfully.

## pinenacl Compatibility

### Flutter pinenacl Library

The Flutter client uses the [pinenacl](https://pub.dev/packages/pinenacl) library, which provides a Dart-native implementation of the same NaCl box algorithm.

**Key Compatibility Points**:

1. **Algorithm**: Both use Curve25519-XSalsa20-Poly1305 (NaCl box)
2. **Key Format**: Both use raw 32-byte X25519 keys (no headers)
3. **Nonce**: Both use 24-byte random nonces
4. **MAC**: Both append 16-byte Poly1305 MAC to ciphertext

### Key Format Compatibility

Both implementations store keys in raw 32-byte format without encoding wrappers:

```python
# Python (PyNaCl)
keypair = generate_keypair()
public_bytes = keypair.public_key  # Raw 32 bytes
private_bytes = keypair.private_key  # Raw 32 bytes
```

```dart
// Flutter (pinenacl)
final keypair = PrivateKey.generate();
final publicBytes = keypair.publicKey;  // Raw 32 bytes
final privateBytes = keypair;  // Raw 32 bytes
```

### Message Format Compatibility

The EncryptedBlob message format in the relay service uses separate nonce and payload fields, matching our interface:

```python
# Python encryption
nonce, ciphertext = box.encrypt(plaintext, recipient_pk)
# Send as: EncryptedBlob(nonce=base64(nonce), payload=base64(ciphertext))

# Flutter decryption receives same format
# Decode: nonce = base64_decode(blob.nonce)
# Decode: ciphertext = base64_decode(blob.payload)
# Decrypt: plaintext = box.decrypt(ciphertext, nonce, sender_pk)
```

### Test Vector Validation

Test vectors in `crypto_vectors.json` validate that PyNaCl and pinenacl produce identical outputs for the same inputs, ensuring cross-platform compatibility.

For complete protocol specifications, see [docs/crypto.md](../../RemoteAgents/docs/crypto.md) in the main repository (from shared-contracts).

## API Reference

### Type Aliases

```python
PublicKey = bytes  # X25519 public key (32 bytes)
PrivateKey = bytes  # X25519 private key (32 bytes)
Nonce = bytes  # Cryptographic nonce (24 bytes)
Ciphertext = bytes  # Encrypted data with Poly1305 MAC
```

### NaClProvider

Factory class implementing the `CryptoProvider` protocol.

```python
class NaClProvider:
    def generate_keypair() -> NaClKeyPair:
        """Generate a new X25519 key pair."""

    def create_box(keypair: NaClKeyPair) -> NaClBox:
        """Create an encryption box from a key pair."""
```

**Convenience Instance**:
```python
from agent_remote.shared.crypto import DEFAULT_PROVIDER

keypair = DEFAULT_PROVIDER.generate_keypair()
box = DEFAULT_PROVIDER.create_box(keypair)
```

### NaClKeyPair

Key pair implementation providing X25519 public and private keys.

```python
class NaClKeyPair:
    @property
    def public_key(self) -> PublicKey:
        """Get the public key (32 bytes X25519 format)."""

    @property
    def private_key(self) -> PrivateKey:
        """Get the private key (32 bytes X25519 format)."""
```

### NaClBox

Authenticated encryption box implementing the `CryptoBox` protocol.

```python
class NaClBox:
    def encrypt(
        self,
        plaintext: bytes,
        their_public_key: PublicKey
    ) -> tuple[Nonce, Ciphertext]:
        """Encrypt plaintext for a recipient.

        Returns:
            Tuple of (nonce, ciphertext) where:
            - nonce: Random 24-byte nonce
            - ciphertext: Encrypted data with 16-byte MAC appended
        """

    def decrypt(
        self,
        ciphertext: Ciphertext,
        nonce: Nonce,
        their_public_key: PublicKey
    ) -> bytes:
        """Decrypt ciphertext from a sender.

        Args:
            ciphertext: Encrypted data with MAC (at least 16 bytes)
            nonce: The 24-byte nonce used during encryption
            their_public_key: Sender's 32-byte X25519 public key

        Returns:
            Decrypted plaintext bytes

        Raises:
            ValueError: If MAC verification fails or inputs invalid
        """
```

### Utility Functions

```python
def generate_keypair() -> NaClKeyPair:
    """Generate a new X25519 key pair."""

def keypair_from_bytes(private_key: bytes) -> NaClKeyPair:
    """Reconstruct a key pair from raw private key bytes (32 bytes)."""

def bytes_to_base64(data: bytes) -> str:
    """Encode bytes to base64 string for JSON transport."""

def base64_to_bytes(data: str) -> bytes:
    """Decode base64 string to bytes for cryptographic operations."""
```

## Security Notes

### Critical Security Requirements

1. **Nonce Uniqueness**: Nonces MUST be unique for each message with the same key pair. Reusing a nonce catastrophically breaks security.

2. **Private Key Protection**: Private keys MUST never be transmitted over the network or logged. Only public keys should be shared.

3. **MAC Verification**: MAC verification failure indicates message tampering or wrong keys. Always reject such messages - do not retry with modified parameters.

4. **Key Storage**: Private keys should be stored securely (encrypted at rest) and never committed to version control.

### Base64 Encoding for JSON

Use `bytes_to_base64()` and `base64_to_bytes()` for encoding crypto data in JSON messages:

```python
# Encoding for EncryptedBlob
nonce_b64 = bytes_to_base64(nonce)
ciphertext_b64 = bytes_to_base64(ciphertext)

# Store in JSON
blob = {
    "nonce": nonce_b64,
    "payload": ciphertext_b64
}

# Decoding from EncryptedBlob
nonce = base64_to_bytes(blob["nonce"])
ciphertext = base64_to_bytes(blob["payload"])
```

**Important**: Base64 encoding is ONLY for JSON transport. The crypto layer operates on raw bytes.

### Random Number Generation

All key generation and nonce creation use cryptographically secure random sources:

- **Linux**: `/dev/urandom`
- **Windows**: `CryptGenRandom`
- **macOS**: `/dev/urandom`

PyNaCl ensures sufficient entropy (256 bits for private keys, 192 bits for nonces).

## Additional Resources

- **Shared-contracts Specification**: [docs/crypto.md](../../RemoteAgents/docs/crypto.md) (protocol interfaces and message formats)
- **PyNaCl Documentation**: https://pynacl.readthedocs.io/
- **pinenacl Documentation**: https://pub.dev/packages/pinenacl
- **NaCl Specification**: https://nacl.cr.yp.to/
- **Test Vectors**: `tests/shared/fixtures/crypto_vectors.json`
