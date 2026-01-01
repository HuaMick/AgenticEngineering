# RemoteAgents Cryptography Specification

This document specifies the cryptographic interfaces, key formats, and encryption protocols for the RemoteAgents system.

## Overview

RemoteAgents uses end-to-end encryption between the desktop agent and web client. The relay service cannot decrypt messages - it only routes encrypted blobs.

**Algorithm**: NaCl box (Curve25519-XSalsa20-Poly1305)
- **Key Exchange**: X25519 elliptic curve Diffie-Hellman
- **Encryption**: XSalsa20 stream cipher
- **Authentication**: Poly1305 MAC

## Security Properties

| Property | Guarantee |
|----------|-----------|
| **Confidentiality** | Only intended recipient can decrypt |
| **Integrity** | Any tampering is detected (Poly1305 MAC) |
| **Authenticity** | Recipient can verify sender's identity |
| **Forward Secrecy** | Each message uses unique nonce |

---

## Key Formats

### Public Key (X25519)

- **Size**: Exactly 32 bytes
- **Format**: Raw X25519 public key bytes
- **Transport**: Base64-encoded in JSON
- **Usage**: Shared with other parties for encryption

```python
# Python (PyNaCl)
from nacl.public import PrivateKey
private = PrivateKey.generate()
public_key = bytes(private.public_key)  # 32 bytes
public_b64 = base64.b64encode(public_key).decode('ascii')
```

```dart
// Flutter (flutter_sodium)
final keyPair = CryptoBox.generateKeyPair();
final publicKey = keyPair.publicKey;  // 32 bytes
final publicB64 = base64Encode(publicKey);
```

### Private Key (X25519)

- **Size**: Exactly 32 bytes
- **Format**: Raw X25519 private key bytes
- **Transport**: **NEVER transmitted** - kept local only
- **Storage**: Must be stored securely (encrypted at rest)

```python
# Python (PyNaCl)
from nacl.public import PrivateKey
private_key = PrivateKey.generate()
private_bytes = bytes(private_key)  # 32 bytes - KEEP SECRET
```

```dart
// Flutter (flutter_sodium)
final keyPair = CryptoBox.generateKeyPair();
final privateKey = keyPair.secretKey;  // 32 bytes - KEEP SECRET
```

### Nonce

- **Size**: Exactly 24 bytes
- **Format**: Random bytes (crypto_box_NONCEBYTES)
- **Transport**: Base64-encoded, sent with ciphertext
- **CRITICAL**: Must be unique per message with same key pair

```python
# Python (PyNaCl)
import nacl.utils
from nacl.public import Box
nonce = nacl.utils.random(Box.NONCE_SIZE)  # 24 bytes
```

```dart
// Flutter (flutter_sodium)
final nonce = Sodium.randomBytes(CryptoBox.nonceBytes);  // 24 bytes
```

---

## Encryption Process

### Encrypting a Message

```
1. Plaintext (bytes)
       |
       v
2. Encode to UTF-8 if string
       |
       v
3. Generate random 24-byte nonce (MUST be unique!)
       |
       v
4. Create NaCl box with sender's private key + recipient's public key
       |
       v
5. Encrypt: ciphertext = box.encrypt(plaintext, nonce)
       |
       v
6. Output: (nonce, ciphertext) - both base64-encoded for transport
```

### Decrypting a Message

```
1. Receive (nonce, ciphertext) - base64-decode both
       |
       v
2. Create NaCl box with recipient's private key + sender's public key
       |
       v
3. Decrypt: plaintext = box.decrypt(ciphertext, nonce)
       |
       v
4. Verify MAC (automatic in NaCl - throws if tampered)
       |
       v
5. Output: plaintext bytes
```

---

## Python Implementation (PyNaCl)

### Key Generation

```python
from nacl.public import PrivateKey
import base64

# Generate keypair
private_key = PrivateKey.generate()
public_key = private_key.public_key

# Export to base64 for storage/transport
private_b64 = base64.b64encode(bytes(private_key)).decode('ascii')
public_b64 = base64.b64encode(bytes(public_key)).decode('ascii')

# Import from base64
private_key = PrivateKey(base64.b64decode(private_b64))
```

### Encryption

```python
from nacl.public import Box, PrivateKey, PublicKey
import nacl.utils
import base64

# Load keys
sender_private = PrivateKey(base64.b64decode(sender_private_b64))
recipient_public = PublicKey(base64.b64decode(recipient_public_b64))

# Create box
box = Box(sender_private, recipient_public)

# Encrypt
plaintext = message.encode('utf-8')
nonce = nacl.utils.random(Box.NONCE_SIZE)  # 24 bytes - RANDOM!
encrypted = box.encrypt(plaintext, nonce)
ciphertext = encrypted.ciphertext

# Output for transport
nonce_b64 = base64.b64encode(nonce).decode('ascii')
ciphertext_b64 = base64.b64encode(ciphertext).decode('ascii')
```

### Decryption

```python
from nacl.public import Box, PrivateKey, PublicKey
import base64

# Load keys
recipient_private = PrivateKey(base64.b64decode(recipient_private_b64))
sender_public = PublicKey(base64.b64decode(sender_public_b64))

# Create box
box = Box(recipient_private, sender_public)

# Decode from transport
nonce = base64.b64decode(nonce_b64)
ciphertext = base64.b64decode(ciphertext_b64)

# Decrypt (raises CryptoError if MAC fails)
plaintext = box.decrypt(ciphertext, nonce)
message = plaintext.decode('utf-8')
```

---

## Flutter Implementation (flutter_sodium)

### Key Generation

```dart
import 'package:flutter_sodium/flutter_sodium.dart';
import 'dart:convert';

// Generate keypair
final keyPair = CryptoBox.generateKeyPair();
final publicKey = keyPair.publicKey;   // Uint8List, 32 bytes
final privateKey = keyPair.secretKey;  // Uint8List, 32 bytes

// Export to base64
final publicB64 = base64Encode(publicKey);
final privateB64 = base64Encode(privateKey);  // Store securely!

// Import from base64
final importedPublic = base64Decode(publicB64);
final importedPrivate = base64Decode(privateB64);
```

### Encryption

```dart
import 'package:flutter_sodium/flutter_sodium.dart';
import 'dart:convert';

// Load keys
final senderPrivate = base64Decode(senderPrivateB64);
final recipientPublic = base64Decode(recipientPublicB64);

// Generate random nonce (MUST be unique!)
final nonce = Sodium.randomBytes(CryptoBox.nonceBytes);  // 24 bytes

// Encrypt
final plaintext = utf8.encode(message);
final ciphertext = CryptoBox.easy(
  message: plaintext,
  nonce: nonce,
  publicKey: recipientPublic,
  secretKey: senderPrivate,
);

// Output for transport
final nonceB64 = base64Encode(nonce);
final ciphertextB64 = base64Encode(ciphertext);
```

### Decryption

```dart
import 'package:flutter_sodium/flutter_sodium.dart';
import 'dart:convert';

// Load keys
final recipientPrivate = base64Decode(recipientPrivateB64);
final senderPublic = base64Decode(senderPublicB64);

// Decode from transport
final nonce = base64Decode(nonceB64);
final ciphertext = base64Decode(ciphertextB64);

// Decrypt (throws if MAC fails)
final plaintext = CryptoBox.openEasy(
  cipherText: ciphertext,
  nonce: nonce,
  publicKey: senderPublic,
  secretKey: recipientPrivate,
);

final message = utf8.decode(plaintext);
```

---

## Type Interfaces

The following Protocol classes define the cryptographic contracts:

### KeyPair

```python
@runtime_checkable
class KeyPair(Protocol):
    @property
    def public_key(self) -> bytes:
        """Get public key (32 bytes X25519)"""
        ...

    @property
    def private_key(self) -> bytes:
        """Get private key (32 bytes X25519) - KEEP SECRET"""
        ...
```

### CryptoBox

```python
@runtime_checkable
class CryptoBox(Protocol):
    def encrypt(
        self, plaintext: bytes, their_public_key: bytes
    ) -> tuple[bytes, bytes]:  # (nonce, ciphertext)
        """Encrypt plaintext for recipient"""
        ...

    def decrypt(
        self, ciphertext: bytes, nonce: bytes, their_public_key: bytes
    ) -> bytes:
        """Decrypt ciphertext from sender"""
        ...
```

### CryptoProvider

```python
@runtime_checkable
class CryptoProvider(Protocol):
    def generate_keypair(self) -> KeyPair:
        """Generate new X25519 keypair"""
        ...

    def create_box(self, keypair: KeyPair) -> CryptoBox:
        """Create encryption box from keypair"""
        ...
```

---

## Security Constraints

### Nonce Uniqueness (CRITICAL)

**NEVER reuse a nonce with the same key pair.**

Reusing nonces catastrophically breaks security:
- Allows XOR of plaintexts
- Reveals plaintext patterns
- Enables chosen-ciphertext attacks

Best practice: Always generate random nonces using cryptographically secure RNG.

```python
# CORRECT: Random nonce each time
nonce = nacl.utils.random(Box.NONCE_SIZE)

# WRONG: Counter or predictable nonce
nonce = struct.pack('>I', counter)  # DON'T DO THIS
```

### Key Length Validation

Always validate key lengths before use:

| Type | Required Length |
|------|-----------------|
| Public Key | 32 bytes |
| Private Key | 32 bytes |
| Nonce | 24 bytes |

```python
def validate_public_key(key: bytes) -> None:
    if len(key) != 32:
        raise ValueError(f"Public key must be 32 bytes, got {len(key)}")

def validate_nonce(nonce: bytes) -> None:
    if len(nonce) != 24:
        raise ValueError(f"Nonce must be 24 bytes, got {len(nonce)}")
```

### MAC Verification

NaCl box includes Poly1305 MAC (16 bytes appended to ciphertext).

- **Always use authenticated decryption** - built into NaCl
- **Never skip MAC verification**
- **Reject messages if MAC fails** - indicates tampering

```python
try:
    plaintext = box.decrypt(ciphertext, nonce)
except nacl.exceptions.CryptoError:
    # MAC verification failed - message was tampered!
    raise SecurityError("Message authentication failed")
```

---

## Test Vectors

See `tests/shared/fixtures/crypto_vectors.json` for cross-platform validation:

### Test Keypairs

```json
{
  "keypair_1": {
    "public_key": "QElQLbksojQsP5LaxdbefIXbXfVAeltJls458u+36Cc=",
    "private_key": "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
  },
  "keypair_2": {
    "public_key": "Sk+MzeGY1m6ZtMAUQYoyI84lbJiQCuSmgR/RD364TCw=",
    "private_key": "YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI="
  }
}
```

**WARNING**: These keys are for testing only. Never use in production!

### Encryption Examples

| Example | Plaintext | Nonce (base64) |
|---------|-----------|----------------|
| example_1 | "Hello, World!" | `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA` |
| example_2 | "" (empty) | `AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB` |
| example_3 | "Hello World" (emoji) | `AgICAgICAgICAgICAgICAgICAgICAgIC` |

### Validation Process

1. Load test vectors JSON
2. For each encryption example:
   - Load sender/receiver keypairs
   - Decrypt ciphertext with nonce
   - Verify plaintext matches expected
3. For roundtrip examples:
   - Encrypt plaintext with nonce
   - Decrypt result
   - Verify matches original
4. For invalid examples:
   - Attempt operation
   - Verify expected error is raised

---

## References

- [NaCl: Networking and Cryptography library](https://nacl.cr.yp.to/)
- [libsodium Documentation](https://doc.libsodium.org/)
- [PyNaCl Documentation](https://pynacl.readthedocs.io/)
- [flutter_sodium Package](https://pub.dev/packages/flutter_sodium)
- [Curve25519 Specification](https://cr.yp.to/ecdh.html)
- [XSalsa20 Specification](https://cr.yp.to/snuffle/xsalsa-20110204.pdf)
- [Poly1305 Specification](https://cr.yp.to/mac.html)

---

Last updated: 2025-12-04
