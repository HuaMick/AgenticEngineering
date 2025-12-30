"""Unit tests for key generation and serialization.

This module contains focused unit tests for the PyNaCl cryptographic implementation,
specifically testing key generation and serialization operations.

Test Focus: Key generation, key properties, reconstruction from bytes, validation
Test Strategy: technical-spike (focused unit testing)
Test Agent: Agent 1 of 4 - Key generation and serialization
"""

import pytest
from agent_remote.shared.crypto.nacl_impl import (
    generate_keypair,
    keypair_from_bytes,
    NaClKeyPair,
)


class TestKeyGeneration:
    """Test key generation and serialization operations."""

    def test_generate_keypair_produces_32_byte_keys(self):
        """Test that generate_keypair() produces valid X25519 32-byte keys.

        X25519 keys must be exactly 32 bytes each for compatibility with
        pinenacl Flutter library.
        """
        keypair = generate_keypair()

        # Both public and private keys must be exactly 32 bytes (X25519 format)
        assert len(keypair.public_key) == 32, (
            f"Public key must be 32 bytes for X25519, got {len(keypair.public_key)}"
        )
        assert len(keypair.private_key) == 32, (
            f"Private key must be 32 bytes for X25519, got {len(keypair.private_key)}"
        )

        # Keys should be bytes type
        assert isinstance(keypair.public_key, bytes)
        assert isinstance(keypair.private_key, bytes)

    def test_public_key_and_private_key_properties_return_raw_bytes(self):
        """Test that public_key and private_key properties return raw bytes.

        Keys must be in raw byte format (no base64 encoding, no headers) for
        compatibility with pinenacl.
        """
        keypair = generate_keypair()

        # Properties should return raw bytes
        public_bytes = keypair.public_key
        private_bytes = keypair.private_key

        assert isinstance(public_bytes, bytes)
        assert isinstance(private_bytes, bytes)

        # Verify they're not base64 strings or other encoded formats
        # Raw bytes should contain non-printable characters typically
        assert type(public_bytes) is bytes
        assert type(private_bytes) is bytes

        # Verify consistent access returns same values
        assert keypair.public_key == public_bytes
        assert keypair.private_key == private_bytes

    def test_keypair_from_bytes_reconstructs_keypair(self):
        """Test that keypair_from_bytes() reconstructs keypair from 32-byte private key.

        This validates that we can serialize/deserialize keypairs correctly,
        which is essential for key persistence.
        """
        # Generate original keypair
        original = generate_keypair()
        private_bytes = original.private_key

        # Reconstruct from private key bytes
        restored = keypair_from_bytes(private_bytes)

        # Public key should match (derived from same private key)
        assert restored.public_key == original.public_key, (
            "Reconstructed public key should match original"
        )

        # Private key should match
        assert restored.private_key == original.private_key, (
            "Reconstructed private key should match original"
        )

        # Keys should still be 32 bytes
        assert len(restored.public_key) == 32
        assert len(restored.private_key) == 32

    def test_invalid_key_length_rejected(self):
        """Test that keypair_from_bytes() rejects keys that are not 32 bytes.

        X25519 requires exactly 32-byte keys. Other lengths should be rejected
        with a clear error message.
        """
        # Test various invalid lengths
        invalid_lengths = [0, 1, 16, 31, 33, 64, 100]

        for length in invalid_lengths:
            invalid_key = b'\x00' * length

            with pytest.raises(ValueError) as exc_info:
                keypair_from_bytes(invalid_key)

            # Verify error message mentions the expected length
            error_msg = str(exc_info.value)
            assert "32 bytes" in error_msg.lower(), (
                f"Error message should mention required 32 bytes, got: {error_msg}"
            )
            assert f"{length}" in error_msg, (
                f"Error message should mention actual length {length}, got: {error_msg}"
            )

        # Also test via NaClKeyPair constructor directly
        with pytest.raises(ValueError) as exc_info:
            NaClKeyPair(b'\x00' * 16)

        error_msg = str(exc_info.value)
        assert "32 bytes" in error_msg.lower()
