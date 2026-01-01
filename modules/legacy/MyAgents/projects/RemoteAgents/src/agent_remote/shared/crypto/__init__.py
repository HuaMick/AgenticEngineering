"""PyNaCl wrapper implementing shared-contracts crypto interfaces.

This package provides a concrete implementation of cryptographic operations using PyNaCl,
compatible with the pinenacl Flutter library. It implements Curve25519-XSalsa20-Poly1305
authenticated encryption (NaCl box) for secure end-to-end encrypted communication.

Algorithm: Curve25519-XSalsa20-Poly1305 (NaCl box)
Key Exchange: X25519 elliptic curve Diffie-Hellman
Encryption: XSalsa20 stream cipher
Authentication: Poly1305 MAC (16 bytes)
Key Format: Raw 32-byte X25519 keys
Nonce: 24 bytes, cryptographically random

Compatibility:
    - Python: PyNaCl library (libsodium bindings)
    - Flutter: pinenacl library (dart-native implementation)
    - Both use raw byte encoding for interoperability

Public Interface:
    Type Aliases:
        - PublicKey: X25519 public key (32 bytes)
        - PrivateKey: X25519 private key (32 bytes)
        - Nonce: Cryptographic nonce (24 bytes)
        - Ciphertext: Encrypted data with Poly1305 MAC

    Protocols (shared-contracts interfaces):
        - KeyPair: Key pair with public and private keys
        - CryptoBox: Authenticated encryption operations
        - CryptoProvider: Factory for creating crypto objects

    Concrete Implementations:
        - NaClProvider: Factory for creating NaCl crypto objects
        - NaClKeyPair: X25519 key pair implementation
        - NaClBox: Authenticated encryption box
        - DEFAULT_PROVIDER: Pre-instantiated NaClProvider for convenience

    Utility Functions:
        - generate_keypair(): Generate a new X25519 key pair
        - keypair_from_bytes(private_key): Restore key pair from private key
        - bytes_to_base64(data): Encode bytes to base64 string for JSON
        - base64_to_bytes(data): Decode base64 string to bytes

Usage Examples:

    Basic encryption using DEFAULT_PROVIDER:
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

    Encoding for JSON transport:
        ```python
        from agent_remote.shared.crypto import (
            DEFAULT_PROVIDER,
            bytes_to_base64,
            base64_to_bytes
        )

        # Encrypt a message
        keypair = DEFAULT_PROVIDER.generate_keypair()
        box = DEFAULT_PROVIDER.create_box(keypair)
        nonce, ciphertext = box.encrypt(b"message", recipient_public_key)

        # Encode for JSON (used in EncryptedBlob)
        nonce_b64 = bytes_to_base64(nonce)
        ciphertext_b64 = bytes_to_base64(ciphertext)

        # Decode from JSON
        nonce = base64_to_bytes(nonce_b64)
        ciphertext = base64_to_bytes(ciphertext_b64)

        # Decrypt
        plaintext = box.decrypt(ciphertext, nonce, sender_public_key)
        ```

    Using convenience functions:
        ```python
        from agent_remote.shared.crypto import (
            generate_keypair,
            keypair_from_bytes,
            NaClBox
        )

        # Generate and save keypair
        keypair = generate_keypair()
        private_key_bytes = keypair.private_key

        # Later: restore keypair
        restored_keypair = keypair_from_bytes(private_key_bytes)
        assert restored_keypair.public_key == keypair.public_key

        # Create box directly
        box = NaClBox(keypair)
        ```

Security Notes:
    - Nonces MUST be unique for each message with the same key pair
    - Private keys MUST never be transmitted or logged
    - MAC verification failure indicates tampering - reject the message
    - Use bytes_to_base64/base64_to_bytes for JSON encoding (relay service)
"""

from agent_remote.shared.crypto.nacl_impl import (
    NaClBox,
    NaClKeyPair,
    NaClProvider,
    base64_to_bytes,
    bytes_to_base64,
    generate_keypair,
    keypair_from_bytes,
)
from agent_remote.shared.crypto.types import (
    Ciphertext,
    CryptoBox,
    CryptoProvider,
    KeyPair,
    Nonce,
    PrivateKey,
    PublicKey,
)

# Default provider instance for convenient usage
DEFAULT_PROVIDER = NaClProvider()

__all__ = [
    # Type aliases
    "PublicKey",
    "PrivateKey",
    "Nonce",
    "Ciphertext",
    # Protocol types (shared-contracts interfaces)
    "KeyPair",
    "CryptoBox",
    "CryptoProvider",
    # Concrete implementations
    "NaClProvider",
    "NaClKeyPair",
    "NaClBox",
    # Convenience functions
    "generate_keypair",
    "keypair_from_bytes",
    # Utility functions (base64 encoding for JSON transport)
    "bytes_to_base64",
    "base64_to_bytes",
    # Default provider instance
    "DEFAULT_PROVIDER",
]
