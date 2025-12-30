"""Unit tests for encryption signature compliance.

Tests the encrypt() method signature and behavior to ensure it matches
the CryptoBox protocol specification:
- encrypt(plaintext: bytes, their_public_key: PublicKey) -> tuple[Nonce, Ciphertext]

Test Strategy: technical-spike (focused unit testing)
Test Agent: Agent 2 of 4 - Encryption signature compliance
"""

import pytest

from agent_remote.shared.crypto import (
    NaClBox,
    generate_keypair,
)


class TestEncryptionSignature:
    """Tests for encryption method signature compliance.

    Validates that encrypt() returns the correct types and formats
    according to the CryptoBox protocol specification.
    """

    @pytest.fixture
    def alice_keypair(self):
        """Generate Alice's keypair for testing."""
        return generate_keypair()

    @pytest.fixture
    def bob_keypair(self):
        """Generate Bob's keypair for testing."""
        return generate_keypair()

    @pytest.fixture
    def alice_box(self, alice_keypair):
        """Create Alice's encryption box."""
        return NaClBox(alice_keypair)

    def test_encrypt_returns_tuple_of_bytes(self, alice_box, bob_keypair):
        """Test that encrypt() returns tuple[bytes, bytes] (nonce, ciphertext)."""
        plaintext = b"Hello, World!"
        result = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Verify it's a tuple
        assert isinstance(result, tuple), f"Expected tuple, got {type(result).__name__}"

        # Verify tuple has exactly 2 elements
        assert len(result) == 2, f"Expected tuple of length 2, got {len(result)}"

        # Verify both elements are bytes
        nonce, ciphertext = result
        assert isinstance(nonce, bytes), f"Expected nonce to be bytes, got {type(nonce).__name__}"
        assert isinstance(ciphertext, bytes), f"Expected ciphertext to be bytes, got {type(ciphertext).__name__}"

    def test_nonce_is_exactly_24_bytes(self, alice_box, bob_keypair):
        """Test that nonce is exactly 24 bytes (XSalsa20 requirement)."""
        plaintext = b"Test message"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        assert len(nonce) == 24, f"Expected nonce to be 24 bytes, got {len(nonce)} bytes"

    def test_ciphertext_longer_than_plaintext(self, alice_box, bob_keypair):
        """Test that ciphertext is longer than plaintext (includes 16-byte Poly1305 MAC)."""
        plaintext = b"Secret message"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Ciphertext should be plaintext length + 16 bytes (Poly1305 MAC)
        expected_length = len(plaintext) + 16
        assert len(ciphertext) == expected_length, (
            f"Expected ciphertext to be {expected_length} bytes "
            f"(plaintext {len(plaintext)} + MAC 16), got {len(ciphertext)} bytes"
        )

    def test_different_encryptions_produce_different_nonces(self, alice_box, bob_keypair):
        """Test that different encryptions produce different nonces (randomness check)."""
        plaintext = b"Same message"

        # Encrypt the same message multiple times
        nonce1, ciphertext1 = alice_box.encrypt(plaintext, bob_keypair.public_key)
        nonce2, ciphertext2 = alice_box.encrypt(plaintext, bob_keypair.public_key)
        nonce3, ciphertext3 = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # All nonces should be different (extremely high probability with random 24 bytes)
        assert nonce1 != nonce2, "First and second nonces should be different"
        assert nonce1 != nonce3, "First and third nonces should be different"
        assert nonce2 != nonce3, "Second and third nonces should be different"

        # Ciphertexts should also be different (due to different nonces)
        assert ciphertext1 != ciphertext2, "First and second ciphertexts should be different"
        assert ciphertext1 != ciphertext3, "First and third ciphertexts should be different"
        assert ciphertext2 != ciphertext3, "Second and third ciphertexts should be different"

    def test_tuple_unpacking_works(self, alice_box, bob_keypair):
        """Test that tuple unpacking works: nonce, ciphertext = box.encrypt(...)"""
        plaintext = b"Testing unpacking"

        # Test direct unpacking
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Verify the unpacked values are valid
        assert len(nonce) == 24, "Unpacked nonce should be 24 bytes"
        assert len(ciphertext) == len(plaintext) + 16, "Unpacked ciphertext should be plaintext + 16 bytes"
        assert isinstance(nonce, bytes), "Unpacked nonce should be bytes"
        assert isinstance(ciphertext, bytes), "Unpacked ciphertext should be bytes"

        # Verify we can use the unpacked values for decryption
        bob_box = NaClBox(bob_keypair)
        decrypted = bob_box.decrypt(ciphertext, nonce, alice_box._keypair.public_key)
        assert decrypted == plaintext, "Should be able to decrypt with unpacked values"
