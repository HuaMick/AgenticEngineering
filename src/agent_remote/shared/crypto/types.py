"""Crypto interface types for RemoteAgents protocol.

This module defines Protocol classes and type aliases for cryptographic operations.
These interfaces are implementation-agnostic and can be implemented by both PyNaCl
(Python) and pinenacl (Flutter) to ensure interoperability.

Algorithm: Curve25519-XSalsa20-Poly1305 (NaCl box)
Key Exchange: X25519 elliptic curve Diffie-Hellman
Encryption: XSalsa20 stream cipher
Authentication: Poly1305 MAC

All implementations must follow these specifications exactly to ensure compatibility
across Python and Flutter clients.
"""

from typing import Protocol, runtime_checkable


# Type aliases for clarity and documentation
PublicKey = bytes
"""X25519 public key (32 bytes).

Format: Raw X25519 public key bytes. Used for key exchange in Curve25519-XSalsa20-Poly1305
encryption. Must be exactly 32 bytes.
"""

PrivateKey = bytes
"""X25519 private key (32 bytes).

Format: Raw X25519 private key bytes. Must be kept secret and never transmitted.
Must be exactly 32 bytes.
"""

Nonce = bytes
"""Cryptographic nonce (24 bytes).

Format: Random 24 bytes. MUST be unique for each message encrypted with the same key pair.
Reusing a nonce with the same key pair catastrophically breaks security. The nonce does not
need to be secret and is transmitted with the ciphertext.

Best practice: Generate using a cryptographically secure random number generator.
"""

Ciphertext = bytes
"""Encrypted data with Poly1305 MAC.

Format: Encrypted data concatenated with 16-byte Poly1305 authentication tag.
Length: len(plaintext) + 16 bytes (for MAC).

The MAC ensures integrity and authenticity - any tampering will be detected during decryption.
"""


@runtime_checkable
class KeyPair(Protocol):
    """Key pair for asymmetric encryption.

    Represents an X25519 key pair used for Curve25519-XSalsa20-Poly1305 encryption.
    Both keys must be exactly 32 bytes in X25519 format.

    The private key must be kept secret. The public key can be shared and is used by
    others to encrypt messages that only the private key holder can decrypt.
    """

    @property
    def public_key(self) -> PublicKey:
        """Get the public key (32 bytes X25519 format).

        Returns:
            32-byte X25519 public key that can be safely shared.
        """
        ...

    @property
    def private_key(self) -> PrivateKey:
        """Get the private key (32 bytes X25519 format).

        Returns:
            32-byte X25519 private key that must be kept secret.

        Security: This key must never be transmitted or logged.
        """
        ...


@runtime_checkable
class CryptoBox(Protocol):
    """Authenticated encryption box for secure messaging.

    Implements Curve25519-XSalsa20-Poly1305 authenticated encryption (NaCl box).
    This combines X25519 key exchange, XSalsa20 encryption, and Poly1305 authentication
    to provide confidentiality, integrity, and authenticity.

    Usage pattern:
        1. Sender: box.encrypt(message, recipient_public_key) -> (nonce, ciphertext)
        2. Sender transmits: nonce + ciphertext to recipient
        3. Recipient: box.decrypt(ciphertext, nonce, sender_public_key) -> message

    Security properties:
        - Forward secrecy: Different messages use different nonces
        - Authentication: Recipient can verify sender's identity
        - Integrity: Any tampering is detected
        - Confidentiality: Only recipient can decrypt
    """

    def encrypt(
        self, plaintext: bytes, their_public_key: PublicKey
    ) -> tuple[Nonce, Ciphertext]:
        """Encrypt plaintext for a recipient.

        Encrypts the plaintext using Curve25519-XSalsa20-Poly1305. The message can only
        be decrypted by someone with the corresponding private key and this box's public key.

        Args:
            plaintext: Raw bytes to encrypt. Can be any length.
            their_public_key: Recipient's X25519 public key (32 bytes).

        Returns:
            Tuple of (nonce, ciphertext):
                - nonce: Random 24-byte nonce (must be transmitted with ciphertext)
                - ciphertext: Encrypted data with 16-byte Poly1305 MAC appended

        Raises:
            ValueError: If their_public_key is not 32 bytes.
            CryptoError: If encryption fails (implementation-specific exception).

        Note: The nonce is randomly generated and must be transmitted with the ciphertext.
        It does not need to be kept secret.
        """
        ...

    def decrypt(
        self, ciphertext: Ciphertext, nonce: Nonce, their_public_key: PublicKey
    ) -> bytes:
        """Decrypt ciphertext from a sender.

        Decrypts the ciphertext using Curve25519-XSalsa20-Poly1305. Verifies the Poly1305
        MAC to ensure integrity and authenticity.

        Args:
            ciphertext: Encrypted data with Poly1305 MAC (at least 16 bytes).
            nonce: The 24-byte nonce used during encryption.
            their_public_key: Sender's X25519 public key (32 bytes).

        Returns:
            Decrypted plaintext bytes.

        Raises:
            ValueError: If nonce is not 24 bytes or their_public_key is not 32 bytes.
            CryptoError: If decryption fails (implementation-specific exception).
            AuthenticationError: If MAC verification fails (tampering detected).

        Security: MAC verification failure indicates the message was tampered with or
        the wrong keys/nonce were used. The message should be rejected.
        """
        ...


@runtime_checkable
class CryptoProvider(Protocol):
    """Factory for creating cryptographic objects.

    Provides methods to generate key pairs and create encryption boxes. This abstraction
    allows different implementations (PyNaCl, pinenacl) to be used interchangeably.

    Implementations must use cryptographically secure random number generators for all
    key generation and nonce creation.
    """

    def generate_keypair(self) -> KeyPair:
        """Generate a new X25519 key pair.

        Creates a fresh key pair using a cryptographically secure random number generator.
        The private key should be generated with sufficient entropy (at least 256 bits).

        Returns:
            New KeyPair with random X25519 public and private keys (32 bytes each).

        Security: Keys are generated using the system's secure random source.
        The private key must be stored securely and never transmitted.
        """
        ...

    def create_box(self, keypair: KeyPair) -> CryptoBox:
        """Create an encryption box from a key pair.

        Creates a CryptoBox that can encrypt messages to others and decrypt messages
        from others using the provided key pair.

        Args:
            keypair: The key pair to use for this box's operations.

        Returns:
            CryptoBox configured with the provided key pair.

        Raises:
            ValueError: If keypair keys are not valid X25519 keys (32 bytes each).
        """
        ...
