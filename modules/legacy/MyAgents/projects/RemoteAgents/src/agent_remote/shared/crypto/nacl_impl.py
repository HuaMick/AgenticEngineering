"""PyNaCl implementation of cryptographic operations.

This module provides a concrete implementation of the crypto interfaces using PyNaCl.
It implements X25519 key operations compatible with the pinenacl Flutter library.

Algorithm: Curve25519-XSalsa20-Poly1305 (NaCl box)
Key Exchange: X25519 elliptic curve Diffie-Hellman
Key Format: Raw 32-byte X25519 keys (no encoding wrappers)

The implementation ensures compatibility with pinenacl by using raw byte encoding
for all keys. Keys are exactly 32 bytes in X25519 format.
"""

import base64
from typing import Union

import nacl.encoding
import nacl.exceptions
import nacl.public
import nacl.utils

from .types import Ciphertext, Nonce, PrivateKey, PublicKey


class NaClKeyPair:
    """X25519 key pair implementation using PyNaCl.

    Wraps nacl.public.PrivateKey to provide the KeyPair protocol interface.
    Keys are stored and returned in raw 32-byte X25519 format for compatibility
    with pinenacl and other NaCl implementations.

    Attributes:
        _private_key: The underlying PyNaCl PrivateKey object.

    Example:
        >>> keypair = generate_keypair()
        >>> public_bytes = keypair.public_key  # 32 bytes
        >>> private_bytes = keypair.private_key  # 32 bytes
    """

    def __init__(self, private_key: Union[nacl.public.PrivateKey, bytes]):
        """Initialize a key pair.

        Args:
            private_key: Either a PyNaCl PrivateKey object or raw 32-byte
                private key bytes.

        Raises:
            ValueError: If private_key bytes are not exactly 32 bytes.
            TypeError: If private_key is not a PrivateKey or bytes.
        """
        if isinstance(private_key, nacl.public.PrivateKey):
            self._private_key = private_key
        elif isinstance(private_key, bytes):
            if len(private_key) != 32:
                raise ValueError(
                    f"Private key must be exactly 32 bytes, got {len(private_key)} bytes"
                )
            self._private_key = nacl.public.PrivateKey(
                private_key, encoder=nacl.encoding.RawEncoder
            )
        else:
            raise TypeError(
                f"private_key must be PrivateKey or bytes, got {type(private_key).__name__}"
            )

    @property
    def public_key(self) -> PublicKey:
        """Get the public key in raw 32-byte X25519 format.

        Returns:
            32-byte X25519 public key that can be safely shared.
            This is the raw key bytes without any encoding wrapper.
        """
        return bytes(
            self._private_key.public_key.encode(encoder=nacl.encoding.RawEncoder)
        )

    @property
    def private_key(self) -> PrivateKey:
        """Get the private key in raw 32-byte X25519 format.

        Returns:
            32-byte X25519 private key that must be kept secret.
            This is the raw key bytes without any encoding wrapper.

        Security: This key must never be transmitted or logged.
        """
        return bytes(self._private_key.encode(encoder=nacl.encoding.RawEncoder))


def generate_keypair() -> NaClKeyPair:
    """Generate a new X25519 key pair.

    Creates a fresh key pair using PyNaCl's cryptographically secure random
    number generator. The private key is generated with 256 bits of entropy.

    Returns:
        NaClKeyPair with random X25519 public and private keys (32 bytes each).

    Security: Keys are generated using the system's secure random source
    (typically /dev/urandom on Linux, CryptGenRandom on Windows).
    The private key must be stored securely and never transmitted.

    Example:
        >>> keypair = generate_keypair()
        >>> assert len(keypair.public_key) == 32
        >>> assert len(keypair.private_key) == 32
    """
    private_key = nacl.public.PrivateKey.generate()
    return NaClKeyPair(private_key)


def keypair_from_bytes(private_key: bytes) -> NaClKeyPair:
    """Reconstruct a key pair from raw private key bytes.

    Creates a NaClKeyPair from a previously generated private key.
    The public key is derived from the private key using X25519 operations.

    Args:
        private_key: Raw X25519 private key bytes (must be exactly 32 bytes).

    Returns:
        NaClKeyPair reconstructed from the private key.

    Raises:
        ValueError: If private_key is not exactly 32 bytes.

    Security: The private_key parameter must be kept secret. Only use this
    function when loading a previously saved key pair. Never transmit
    private keys over the network.

    Example:
        >>> original = generate_keypair()
        >>> private_bytes = original.private_key
        >>> restored = keypair_from_bytes(private_bytes)
        >>> assert restored.public_key == original.public_key
        >>> assert restored.private_key == original.private_key
    """
    if len(private_key) != 32:
        raise ValueError(
            f"Private key must be exactly 32 bytes, got {len(private_key)} bytes. "
            f"X25519 private keys are always 32 bytes in raw format."
        )

    return NaClKeyPair(private_key)


class NaClBox:
    """Authenticated encryption box using PyNaCl.

    Implements the CryptoBox protocol using Curve25519-XSalsa20-Poly1305.
    This provides authenticated encryption with the following security properties:

    - Confidentiality: Only the intended recipient can decrypt messages
    - Authenticity: Recipients can verify the sender's identity
    - Integrity: Any tampering is detected via Poly1305 MAC
    - Forward secrecy: Each message uses a unique random nonce

    Algorithm details:
    - Key Exchange: X25519 elliptic curve Diffie-Hellman
    - Encryption: XSalsa20 stream cipher
    - Authentication: Poly1305 MAC (16 bytes appended to ciphertext)
    - Nonce: 24 bytes, must be unique per message

    Attributes:
        _keypair: The NaClKeyPair used for encryption/decryption operations.

    Example:
        >>> alice_keypair = generate_keypair()
        >>> bob_keypair = generate_keypair()
        >>> alice_box = NaClBox(alice_keypair)
        >>>
        >>> # Alice encrypts a message for Bob
        >>> nonce, ciphertext = alice_box.encrypt(b"Hello Bob!", bob_keypair.public_key)
        >>>
        >>> # Bob decrypts the message from Alice
        >>> bob_box = NaClBox(bob_keypair)
        >>> plaintext = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)
        >>> assert plaintext == b"Hello Bob!"
    """

    def __init__(self, keypair: NaClKeyPair):
        """Initialize an encryption box with a key pair.

        Args:
            keypair: The NaClKeyPair to use for encryption/decryption operations.
                This box will use the keypair's private key for decryption and
                the recipient's public key for encryption.

        Raises:
            TypeError: If keypair is not a NaClKeyPair instance.
        """
        if not isinstance(keypair, NaClKeyPair):
            raise TypeError(
                f"keypair must be NaClKeyPair, got {type(keypair).__name__}"
            )
        self._keypair = keypair

    def encrypt(
        self, plaintext: bytes, their_public_key: PublicKey
    ) -> tuple[Nonce, Ciphertext]:
        """Encrypt plaintext for a recipient.

        Encrypts the plaintext using Curve25519-XSalsa20-Poly1305. The message can only
        be decrypted by someone with the corresponding private key and this box's public key.

        The encryption process:
        1. Generates a random 24-byte nonce (cryptographically secure)
        2. Performs X25519 key exchange between our private key and their public key
        3. Encrypts plaintext with XSalsa20 using the shared secret
        4. Appends 16-byte Poly1305 MAC for authentication

        Args:
            plaintext: Raw bytes to encrypt. Can be any length.
            their_public_key: Recipient's X25519 public key (must be exactly 32 bytes).

        Returns:
            Tuple of (nonce, ciphertext):
                - nonce: Random 24-byte nonce (must be transmitted with ciphertext)
                - ciphertext: Encrypted data with 16-byte Poly1305 MAC appended
                  (length = len(plaintext) + 16)

        Raises:
            ValueError: If their_public_key is not exactly 32 bytes.
            TypeError: If plaintext is not bytes.

        Security Notes:
            - The nonce is randomly generated and MUST be unique for each message
            - The nonce does not need to be kept secret and must be transmitted
            - Reusing a nonce with the same key pair breaks security
            - The 16-byte MAC ensures integrity and authenticity

        Example:
            >>> box = NaClBox(generate_keypair())
            >>> recipient_pubkey = generate_keypair().public_key
            >>> nonce, ciphertext = box.encrypt(b"Secret message", recipient_pubkey)
            >>> assert len(nonce) == 24
            >>> assert len(ciphertext) == len(b"Secret message") + 16  # +16 for MAC
        """
        # Validate inputs
        if not isinstance(plaintext, bytes):
            raise TypeError(f"plaintext must be bytes, got {type(plaintext).__name__}")

        if not isinstance(their_public_key, bytes):
            raise ValueError(
                f"their_public_key must be bytes, got {type(their_public_key).__name__}"
            )

        if len(their_public_key) != 32:
            raise ValueError(
                f"their_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(their_public_key)} bytes"
            )

        # Create PyNaCl PublicKey from raw bytes
        recipient_public_key = nacl.public.PublicKey(
            their_public_key, encoder=nacl.encoding.RawEncoder
        )

        # Create encryption box using our private key and their public key
        box = nacl.public.Box(self._keypair._private_key, recipient_public_key)

        # Generate random nonce (24 bytes)
        nonce = nacl.utils.random(nacl.public.Box.NONCE_SIZE)

        # Encrypt the plaintext
        # PyNaCl's encrypt() returns nonce+ciphertext combined (nonce || ciphertext+MAC)
        encrypted = box.encrypt(plaintext, nonce)

        # Extract components from the encrypted result
        # PyNaCl format: first 24 bytes = nonce, remaining = ciphertext+MAC
        nonce_from_encrypted = bytes(encrypted[:24])
        ciphertext_with_mac = bytes(encrypted[24:])

        # Return tuple as specified by CryptoBox protocol
        return (nonce_from_encrypted, ciphertext_with_mac)

    def decrypt(
        self, ciphertext: Ciphertext, nonce: Nonce, their_public_key: PublicKey
    ) -> bytes:
        """Decrypt ciphertext from a sender.

        Decrypts the ciphertext using Curve25519-XSalsa20-Poly1305 and verifies the
        Poly1305 MAC to ensure integrity and authenticity.

        The decryption process:
        1. Validates input parameters (nonce 24 bytes, public key 32 bytes, etc.)
        2. Performs X25519 key exchange between our private key and their public key
        3. Verifies the 16-byte Poly1305 MAC (authentication)
        4. Decrypts ciphertext with XSalsa20 using the shared secret

        Args:
            ciphertext: Encrypted data with Poly1305 MAC (must be at least 16 bytes).
                Format: encrypted_plaintext || 16-byte MAC
            nonce: The 24-byte nonce used during encryption (must be exactly 24 bytes).
            their_public_key: Sender's X25519 public key (must be exactly 32 bytes).

        Returns:
            Decrypted plaintext bytes.

        Raises:
            ValueError: If nonce is not 24 bytes, their_public_key is not 32 bytes,
                or ciphertext is less than 16 bytes (minimum for MAC).
            ValueError: If decryption fails or MAC verification fails (indicates
                tampering, wrong keys, or wrong nonce).
            TypeError: If inputs are not bytes.

        Security Notes:
            - MAC verification failure indicates message tampering or wrong keys/nonce
            - Failed decryption should result in message rejection
            - The ciphertext must include the 16-byte Poly1305 MAC
            - Minimum ciphertext length is 16 bytes (empty plaintext + MAC)

        Example:
            >>> alice_keypair = generate_keypair()
            >>> bob_keypair = generate_keypair()
            >>> alice_box = NaClBox(alice_keypair)
            >>> bob_box = NaClBox(bob_keypair)
            >>>
            >>> # Alice encrypts for Bob
            >>> nonce, ciphertext = alice_box.encrypt(b"Hello", bob_keypair.public_key)
            >>>
            >>> # Bob decrypts from Alice
            >>> plaintext = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)
            >>> assert plaintext == b"Hello"
        """
        # Validate inputs
        if not isinstance(ciphertext, bytes):
            raise TypeError(
                f"ciphertext must be bytes, got {type(ciphertext).__name__}"
            )

        if not isinstance(nonce, bytes):
            raise ValueError(f"nonce must be bytes, got {type(nonce).__name__}")

        if not isinstance(their_public_key, bytes):
            raise ValueError(
                f"their_public_key must be bytes, got {type(their_public_key).__name__}"
            )

        if len(nonce) != 24:
            raise ValueError(
                f"nonce must be exactly 24 bytes, got {len(nonce)} bytes. "
                f"XSalsa20 requires a 24-byte nonce."
            )

        if len(their_public_key) != 32:
            raise ValueError(
                f"their_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(their_public_key)} bytes"
            )

        if len(ciphertext) < 16:
            raise ValueError(
                f"ciphertext must be at least 16 bytes (for Poly1305 MAC), "
                f"got {len(ciphertext)} bytes"
            )

        # Create PyNaCl PublicKey from raw bytes
        sender_public_key = nacl.public.PublicKey(
            their_public_key, encoder=nacl.encoding.RawEncoder
        )

        # Create decryption box using our private key and their public key
        box = nacl.public.Box(self._keypair._private_key, sender_public_key)

        # PyNaCl's decrypt() expects combined format: nonce || ciphertext+MAC
        combined = nonce + ciphertext

        # Decrypt and verify MAC
        try:
            plaintext = box.decrypt(combined)
        except nacl.exceptions.CryptoError as e:
            raise ValueError(
                f"Decryption failed: {e}. This may indicate message tampering, "
                f"wrong keys, or wrong nonce. The Poly1305 MAC verification failed."
            ) from e

        return bytes(plaintext)


class NaClProvider:
    """Factory for creating NaCl cryptographic objects.

    Implements the CryptoProvider protocol to provide a concrete implementation
    of cryptographic operations using PyNaCl. This provider creates NaClKeyPair
    and NaClBox instances compatible with the pinenacl Flutter library.

    This class is stateless and can be instantiated once and reused throughout
    an application. For convenience, a DEFAULT_PROVIDER instance is available
    in the crypto package.

    Example:
        >>> provider = NaClProvider()
        >>> keypair = provider.generate_keypair()
        >>> box = provider.create_box(keypair)
        >>> nonce, ciphertext = box.encrypt(b"message", recipient_public_key)
    """

    def generate_keypair(self) -> NaClKeyPair:
        """Generate a new X25519 key pair.

        Creates a fresh key pair using PyNaCl's cryptographically secure random
        number generator. The private key is generated with 256 bits of entropy.

        Returns:
            NaClKeyPair with random X25519 public and private keys (32 bytes each).

        Security: Keys are generated using the system's secure random source
        (typically /dev/urandom on Linux, CryptGenRandom on Windows).
        The private key must be stored securely and never transmitted.

        Example:
            >>> provider = NaClProvider()
            >>> keypair = provider.generate_keypair()
            >>> assert len(keypair.public_key) == 32
            >>> assert len(keypair.private_key) == 32
        """
        return generate_keypair()

    def create_box(self, keypair: NaClKeyPair) -> NaClBox:
        """Create an encryption box from a key pair.

        Creates a NaClBox that can encrypt messages to others and decrypt messages
        from others using the provided key pair.

        Args:
            keypair: The NaClKeyPair to use for this box's operations.

        Returns:
            NaClBox configured with the provided key pair.

        Raises:
            TypeError: If keypair is not a NaClKeyPair instance.

        Example:
            >>> provider = NaClProvider()
            >>> keypair = provider.generate_keypair()
            >>> box = provider.create_box(keypair)
            >>> assert isinstance(box, NaClBox)
        """
        return NaClBox(keypair)


def bytes_to_base64(data: bytes) -> str:
    """Encode bytes to base64 string for JSON transport.

    Converts raw bytes to a base64-encoded ASCII string suitable for transmission
    in JSON payloads. This is used by the relay service to encode nonce and
    ciphertext fields in EncryptedBlob messages.

    Args:
        data: Raw bytes to encode (e.g., nonce, ciphertext, keys).

    Returns:
        Base64-encoded string using standard encoding (RFC 4648).

    Raises:
        TypeError: If data is not bytes.

    Example:
        >>> nonce = b"\\x01\\x02\\x03\\x04"
        >>> encoded = bytes_to_base64(nonce)
        >>> assert isinstance(encoded, str)
        >>> assert base64_to_bytes(encoded) == nonce
    """
    if not isinstance(data, bytes):
        raise TypeError(f"data must be bytes, got {type(data).__name__}")
    return base64.b64encode(data).decode("utf-8")


def base64_to_bytes(data: str) -> bytes:
    """Decode base64 string to bytes for cryptographic operations.

    Converts a base64-encoded ASCII string back to raw bytes for use in
    cryptographic operations. This is used by the relay service to decode
    nonce and ciphertext fields from EncryptedBlob JSON messages.

    Args:
        data: Base64-encoded string (standard encoding, RFC 4648).

    Returns:
        Decoded raw bytes.

    Raises:
        TypeError: If data is not a string.
        ValueError: If data is not valid base64 (contains invalid characters
            or incorrect padding).

    Example:
        >>> encoded = "AQIDBA=="
        >>> decoded = base64_to_bytes(encoded)
        >>> assert isinstance(decoded, bytes)
        >>> assert bytes_to_base64(decoded) == encoded
    """
    if not isinstance(data, str):
        raise TypeError(f"data must be str, got {type(data).__name__}")
    try:
        return base64.b64decode(data)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}") from e
