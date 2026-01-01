"""Unit tests for crypto implementation.

This module contains unit tests for:
- Base64 encoding/decoding utilities
- NaClProvider factory methods
- Exported API validation
- Decryption signature compliance

Run these tests with:
    pytest tests/shared/test_crypto.py -v
    pytest tests/shared/test_crypto.py::TestUtilitiesAndFactory -v
    pytest tests/shared/test_crypto.py::TestDecryptionSignature -v
"""

import base64

import pytest

from agent_remote.shared.crypto import (
    CryptoBox,
    CryptoProvider,
    DEFAULT_PROVIDER,
    KeyPair,
    NaClBox,
    NaClKeyPair,
    NaClProvider,
    base64_to_bytes,
    bytes_to_base64,
)


class TestUtilitiesAndFactory:
    """Test base64 utilities and NaClProvider factory."""

    # ==========================================================================
    # Base64 Utilities Tests
    # ==========================================================================

    def test_bytes_to_base64_roundtrip(self):
        """Test bytes_to_base64() and base64_to_bytes() round trip."""
        # Test with various byte sequences
        test_cases = [
            b"",  # Empty bytes
            b"\x00",  # Single null byte
            b"\x01\x02\x03\x04",  # Simple sequence
            b"Hello World!",  # ASCII text
            b"\xff" * 32,  # 32 bytes of 0xff (like a key)
            b"\x00" * 24,  # 24 bytes of zeros (like a nonce)
            bytes(range(256)),  # All possible byte values
        ]

        for original_bytes in test_cases:
            # Encode to base64
            encoded = bytes_to_base64(original_bytes)
            assert isinstance(encoded, str), "Encoded value should be a string"

            # Decode back to bytes
            decoded = base64_to_bytes(encoded)
            assert isinstance(decoded, bytes), "Decoded value should be bytes"

            # Verify round trip
            assert (
                decoded == original_bytes
            ), f"Round trip failed for {original_bytes!r}"

    def test_bytes_to_base64_type_validation(self):
        """Test bytes_to_base64() validates input type."""
        # Should raise TypeError for non-bytes input
        with pytest.raises(TypeError, match="data must be bytes"):
            bytes_to_base64("not bytes")

        with pytest.raises(TypeError, match="data must be bytes"):
            bytes_to_base64(123)

        with pytest.raises(TypeError, match="data must be bytes"):
            bytes_to_base64(None)

    def test_base64_to_bytes_type_validation(self):
        """Test base64_to_bytes() validates input type."""
        # Should raise TypeError for non-string input
        with pytest.raises(TypeError, match="data must be str"):
            base64_to_bytes(b"not a string")

        with pytest.raises(TypeError, match="data must be str"):
            base64_to_bytes(123)

        with pytest.raises(TypeError, match="data must be str"):
            base64_to_bytes(None)

    def test_base64_to_bytes_invalid_base64(self):
        """Test base64_to_bytes() rejects invalid base64."""
        # Invalid base64 strings
        invalid_inputs = [
            "not valid base64!@#",  # Invalid characters
            "ABC",  # Incorrect padding
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError, match="Invalid base64 string"):
                base64_to_bytes(invalid_input)

    def test_bytes_to_base64_standard_encoding(self):
        """Test bytes_to_base64() uses standard RFC 4648 encoding."""
        # Test a known conversion
        test_bytes = b"\x01\x02\x03\x04"
        encoded = bytes_to_base64(test_bytes)

        # Verify it matches Python's standard base64 encoding
        expected = base64.b64encode(test_bytes).decode("utf-8")
        assert encoded == expected, "Should use standard base64 encoding"

        # Verify format: standard encoding with padding
        assert encoded == "AQIDBA==", "Should match expected base64 output"

    # ==========================================================================
    # NaClProvider Factory Tests
    # ==========================================================================

    def test_nacl_provider_generate_keypair_returns_keypair_instance(self):
        """Test NaClProvider.generate_keypair() returns KeyPair instance."""
        provider = NaClProvider()
        keypair = provider.generate_keypair()

        # Should return a NaClKeyPair instance
        assert isinstance(keypair, NaClKeyPair), "Should return NaClKeyPair instance"

        # Should satisfy KeyPair protocol (has public_key and private_key properties)
        assert hasattr(keypair, "public_key"), "Should have public_key property"
        assert hasattr(keypair, "private_key"), "Should have private_key property"

        # Keys should be correct length
        assert len(keypair.public_key) == 32, "Public key should be 32 bytes"
        assert len(keypair.private_key) == 32, "Private key should be 32 bytes"

        # Keys should be bytes
        assert isinstance(keypair.public_key, bytes), "Public key should be bytes"
        assert isinstance(keypair.private_key, bytes), "Private key should be bytes"

    def test_nacl_provider_generate_keypair_generates_unique_keys(self):
        """Test NaClProvider.generate_keypair() generates unique keys each time."""
        provider = NaClProvider()

        # Generate multiple keypairs
        keypair1 = provider.generate_keypair()
        keypair2 = provider.generate_keypair()
        keypair3 = provider.generate_keypair()

        # All keys should be different
        assert (
            keypair1.public_key != keypair2.public_key
        ), "Should generate different public keys"
        assert (
            keypair1.private_key != keypair2.private_key
        ), "Should generate different private keys"
        assert (
            keypair2.public_key != keypair3.public_key
        ), "Should generate different public keys"
        assert (
            keypair2.private_key != keypair3.private_key
        ), "Should generate different private keys"

    def test_nacl_provider_create_box_returns_cryptobox_instance(self):
        """Test NaClProvider.create_box() returns CryptoBox instance."""
        provider = NaClProvider()
        keypair = provider.generate_keypair()

        box = provider.create_box(keypair)

        # Should return a NaClBox instance
        assert isinstance(box, NaClBox), "Should return NaClBox instance"

        # Should satisfy CryptoBox protocol (has encrypt and decrypt methods)
        assert hasattr(box, "encrypt"), "Should have encrypt method"
        assert hasattr(box, "decrypt"), "Should have decrypt method"
        assert callable(box.encrypt), "encrypt should be callable"
        assert callable(box.decrypt), "decrypt should be callable"

    def test_nacl_provider_create_box_validates_keypair_type(self):
        """Test NaClProvider.create_box() validates keypair type."""
        provider = NaClProvider()

        # Should raise TypeError for non-keypair input
        with pytest.raises(TypeError, match="keypair must be NaClKeyPair"):
            provider.create_box("not a keypair")

        with pytest.raises(TypeError, match="keypair must be NaClKeyPair"):
            provider.create_box(None)

        with pytest.raises(TypeError, match="keypair must be NaClKeyPair"):
            provider.create_box({"public_key": b"x" * 32, "private_key": b"y" * 32})

    def test_nacl_provider_box_can_encrypt_and_decrypt(self):
        """Test boxes created by NaClProvider can encrypt and decrypt."""
        provider = NaClProvider()

        # Create two keypairs and boxes
        alice_keypair = provider.generate_keypair()
        bob_keypair = provider.generate_keypair()

        alice_box = provider.create_box(alice_keypair)
        bob_box = provider.create_box(bob_keypair)

        # Alice encrypts a message for Bob
        message = b"Hello Bob!"
        nonce, ciphertext = alice_box.encrypt(message, bob_keypair.public_key)

        # Verify encryption output
        assert isinstance(nonce, bytes), "Nonce should be bytes"
        assert isinstance(ciphertext, bytes), "Ciphertext should be bytes"
        assert len(nonce) == 24, "Nonce should be 24 bytes"
        assert len(ciphertext) == len(message) + 16, "Ciphertext should include MAC"

        # Bob decrypts the message from Alice
        plaintext = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)

        # Verify decryption
        assert plaintext == message, "Decrypted message should match original"

    # ==========================================================================
    # Exported API Tests
    # ==========================================================================

    def test_exported_api_keypair_importable(self):
        """Test KeyPair is importable from agent_remote.shared.crypto."""
        # KeyPair should be a Protocol type
        assert KeyPair is not None, "KeyPair should be importable"

    def test_exported_api_cryptobox_importable(self):
        """Test CryptoBox is importable from agent_remote.shared.crypto."""
        # CryptoBox should be a Protocol type
        assert CryptoBox is not None, "CryptoBox should be importable"

    def test_exported_api_cryptoprovider_importable(self):
        """Test CryptoProvider is importable from agent_remote.shared.crypto."""
        # CryptoProvider should be a Protocol type
        assert CryptoProvider is not None, "CryptoProvider should be importable"

    def test_exported_api_naclprovider_importable(self):
        """Test NaClProvider is importable from agent_remote.shared.crypto."""
        # NaClProvider should be the concrete implementation class
        assert NaClProvider is not None, "NaClProvider should be importable"
        assert isinstance(
            NaClProvider, type
        ), "NaClProvider should be a class (type)"

    def test_exported_api_default_provider_importable(self):
        """Test DEFAULT_PROVIDER is importable from agent_remote.shared.crypto."""
        # DEFAULT_PROVIDER should be a pre-instantiated NaClProvider
        assert DEFAULT_PROVIDER is not None, "DEFAULT_PROVIDER should be importable"
        assert isinstance(
            DEFAULT_PROVIDER, NaClProvider
        ), "DEFAULT_PROVIDER should be a NaClProvider instance"

    def test_exported_api_default_provider_is_functional(self):
        """Test DEFAULT_PROVIDER is functional and can be used directly."""
        # Should be able to generate keypairs
        keypair = DEFAULT_PROVIDER.generate_keypair()
        assert isinstance(keypair, NaClKeyPair), "Should generate NaClKeyPair"

        # Should be able to create boxes
        box = DEFAULT_PROVIDER.create_box(keypair)
        assert isinstance(box, NaClBox), "Should create NaClBox"

        # Should be able to encrypt/decrypt
        recipient_keypair = DEFAULT_PROVIDER.generate_keypair()
        nonce, ciphertext = box.encrypt(b"test", recipient_keypair.public_key)
        assert isinstance(nonce, bytes), "Should encrypt successfully"
        assert isinstance(ciphertext, bytes), "Should produce ciphertext"

    # ==========================================================================
    # Module Docstring Usage Examples (Optional - Time Permitting)
    # ==========================================================================

    def test_module_docstring_example_basic_encryption(self):
        """Test module docstring basic encryption example is accurate."""
        # This is the example from __init__.py lines 45-68
        from agent_remote.shared.crypto import DEFAULT_PROVIDER

        # Generate keypairs for Alice and Bob
        alice_keypair = DEFAULT_PROVIDER.generate_keypair()
        bob_keypair = DEFAULT_PROVIDER.generate_keypair()

        # Alice creates a box and encrypts a message for Bob
        alice_box = DEFAULT_PROVIDER.create_box(alice_keypair)
        nonce, ciphertext = alice_box.encrypt(b"Hello Bob!", bob_keypair.public_key)

        # Bob creates a box and decrypts the message from Alice
        bob_box = DEFAULT_PROVIDER.create_box(bob_keypair)
        plaintext = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)
        assert plaintext == b"Hello Bob!"

    def test_module_docstring_example_json_encoding(self):
        """Test module docstring JSON encoding example is accurate."""
        # This is the example from __init__.py lines 70-93
        from agent_remote.shared.crypto import (
            DEFAULT_PROVIDER,
            base64_to_bytes,
            bytes_to_base64,
        )

        # Setup: create a recipient keypair and sender keypair
        keypair = DEFAULT_PROVIDER.generate_keypair()
        recipient_keypair = DEFAULT_PROVIDER.generate_keypair()
        recipient_public_key = recipient_keypair.public_key

        # Encrypt a message
        box = DEFAULT_PROVIDER.create_box(keypair)
        nonce, ciphertext = box.encrypt(b"message", recipient_public_key)

        # Encode for JSON (used in EncryptedBlob)
        nonce_b64 = bytes_to_base64(nonce)
        ciphertext_b64 = bytes_to_base64(ciphertext)

        # Verify encoded values are strings
        assert isinstance(nonce_b64, str)
        assert isinstance(ciphertext_b64, str)

        # Decode from JSON
        nonce_decoded = base64_to_bytes(nonce_b64)
        ciphertext_decoded = base64_to_bytes(ciphertext_b64)

        # Verify decoded values match originals
        assert nonce_decoded == nonce
        assert ciphertext_decoded == ciphertext

        # Decrypt using the recipient's box
        sender_public_key = keypair.public_key
        recipient_box = DEFAULT_PROVIDER.create_box(recipient_keypair)
        plaintext = recipient_box.decrypt(
            ciphertext_decoded, nonce_decoded, sender_public_key
        )
        assert plaintext == b"message"

    def test_module_docstring_example_convenience_functions(self):
        """Test module docstring convenience functions example is accurate."""
        # This is the example from __init__.py lines 95-113
        from agent_remote.shared.crypto import (
            NaClBox,
            generate_keypair,
            keypair_from_bytes,
        )

        # Generate and save keypair
        keypair = generate_keypair()
        private_key_bytes = keypair.private_key

        # Later: restore keypair
        restored_keypair = keypair_from_bytes(private_key_bytes)
        assert restored_keypair.public_key == keypair.public_key

        # Create box directly
        box = NaClBox(keypair)
        assert isinstance(box, NaClBox)


# ==============================================================================
# Decryption Signature Compliance Tests (Agent 3 of 4)
# ==============================================================================


class TestDecryptionSignature:
    """Test decryption signature compliance with shared-contracts interface.

    Tests verify:
    1. decrypt(ciphertext, nonce, their_public_key) signature matches shared-contracts
    2. Round trip encryption/decryption works correctly
    3. Error handling for invalid inputs (wrong nonce, wrong key, truncated ciphertext)

    Test Agent: Agent 3 of 4 - Decryption signature compliance
    Test Strategy: technical-spike (focused unit testing)
    """

    def test_decrypt_signature_matches_shared_contracts(self):
        """Test decrypt(ciphertext, nonce, their_public_key) signature matches shared-contracts."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate two keypairs for encryption/decryption
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()

        # Alice creates a box and encrypts a message for Bob
        alice_box = NaClBox(alice_keypair)
        plaintext = b"Test message for signature compliance"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Bob creates a box and decrypts the message from Alice
        # Verify signature: decrypt(ciphertext, nonce, their_public_key)
        bob_box = NaClBox(bob_keypair)
        decrypted = bob_box.decrypt(ciphertext, nonce, alice_keypair.public_key)

        # Verify decryption succeeded
        assert decrypted == plaintext

        # Verify parameters are in correct order
        assert isinstance(ciphertext, bytes), "First parameter should be ciphertext (bytes)"
        assert isinstance(nonce, bytes), "Second parameter should be nonce (bytes)"
        assert len(nonce) == 24, "Nonce should be 24 bytes"
        assert isinstance(alice_keypair.public_key, bytes), "Third parameter should be public_key (bytes)"
        assert len(alice_keypair.public_key) == 32, "Public key should be 32 bytes"

    def test_round_trip_encrypt_decrypt(self):
        """Test round trip: plaintext_out = box.decrypt(ciphertext, nonce, pk) after box.encrypt(plaintext_in, pk) == plaintext_in."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate two keypairs
        sender_keypair = generate_keypair()
        receiver_keypair = generate_keypair()

        # Create boxes
        sender_box = NaClBox(sender_keypair)
        receiver_box = NaClBox(receiver_keypair)

        # Test multiple message sizes
        test_messages = [
            b"",  # Empty message
            b"Short",  # Short message
            b"A" * 100,  # Medium message
            b"B" * 1000,  # Long message
            b"\x00\x01\x02\x03\xff\xfe\xfd",  # Binary data
        ]

        for plaintext_in in test_messages:
            # Encrypt
            nonce, ciphertext = sender_box.encrypt(plaintext_in, receiver_box._keypair.public_key)

            # Decrypt
            plaintext_out = receiver_box.decrypt(ciphertext, nonce, sender_box._keypair.public_key)

            # Verify round trip
            assert plaintext_out == plaintext_in, f"Round trip failed for message of length {len(plaintext_in)}"

            # Verify ciphertext includes MAC (16 bytes)
            assert len(ciphertext) >= len(plaintext_in) + 16, "Ciphertext should include 16-byte MAC"

    def test_decrypt_with_wrong_nonce_raises_error(self):
        """Test decrypt with wrong nonce raises error."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate keypairs
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()

        # Encrypt a message
        alice_box = NaClBox(alice_keypair)
        plaintext = b"Secret message"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Try to decrypt with wrong nonce
        bob_box = NaClBox(bob_keypair)
        wrong_nonce = b"\x00" * 24  # Different nonce

        with pytest.raises(ValueError) as exc_info:
            bob_box.decrypt(ciphertext, wrong_nonce, alice_keypair.public_key)

        # Verify error message indicates decryption failure
        assert "Decryption failed" in str(exc_info.value)
        assert "MAC verification" in str(exc_info.value) or "tampering" in str(exc_info.value)

    def test_decrypt_with_wrong_public_key_raises_error(self):
        """Test decrypt with wrong public_key raises error."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate three keypairs
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()
        charlie_keypair = generate_keypair()  # Wrong sender

        # Alice encrypts a message for Bob
        alice_box = NaClBox(alice_keypair)
        plaintext = b"Secret message"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Bob tries to decrypt using Charlie's public key (wrong sender)
        bob_box = NaClBox(bob_keypair)

        with pytest.raises(ValueError) as exc_info:
            bob_box.decrypt(ciphertext, nonce, charlie_keypair.public_key)

        # Verify error message indicates decryption failure
        assert "Decryption failed" in str(exc_info.value)

    def test_decrypt_with_truncated_ciphertext_raises_error(self):
        """Test decrypt with truncated ciphertext (< 16 bytes) raises error."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate keypairs
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()

        # Create a box
        bob_box = NaClBox(bob_keypair)

        # Test various truncated ciphertext lengths
        truncated_ciphertexts = [
            b"",  # Empty
            b"short",  # 5 bytes
            b"exactly15bytes",  # 15 bytes (just under minimum)
        ]

        nonce = b"\x00" * 24  # Valid nonce

        for truncated in truncated_ciphertexts:
            with pytest.raises(ValueError) as exc_info:
                bob_box.decrypt(truncated, nonce, alice_keypair.public_key)

            # Verify error message indicates minimum ciphertext length requirement
            assert "at least 16 bytes" in str(exc_info.value) or "Poly1305 MAC" in str(exc_info.value)
            assert str(len(truncated)) in str(exc_info.value), f"Error should mention actual length {len(truncated)}"

    def test_decrypt_validates_nonce_length(self):
        """Test decrypt validates nonce is exactly 24 bytes."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate keypairs
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()

        # Create valid ciphertext
        alice_box = NaClBox(alice_keypair)
        plaintext = b"Test"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Try to decrypt with wrong nonce lengths
        bob_box = NaClBox(bob_keypair)
        invalid_nonces = [
            b"",  # Empty
            b"short",  # Too short
            b"\x00" * 23,  # One byte short
            b"\x00" * 25,  # One byte too long
            b"\x00" * 32,  # Way too long
        ]

        for invalid_nonce in invalid_nonces:
            with pytest.raises(ValueError) as exc_info:
                bob_box.decrypt(ciphertext, invalid_nonce, alice_keypair.public_key)

            # Verify error message mentions 24 bytes requirement
            assert "24 bytes" in str(exc_info.value)
            assert str(len(invalid_nonce)) in str(exc_info.value)

    def test_decrypt_validates_public_key_length(self):
        """Test decrypt validates public_key is exactly 32 bytes."""
        from agent_remote.shared.crypto.nacl_impl import generate_keypair

        # Generate keypairs
        alice_keypair = generate_keypair()
        bob_keypair = generate_keypair()

        # Create valid ciphertext
        alice_box = NaClBox(alice_keypair)
        plaintext = b"Test"
        nonce, ciphertext = alice_box.encrypt(plaintext, bob_keypair.public_key)

        # Try to decrypt with wrong public key lengths
        bob_box = NaClBox(bob_keypair)
        invalid_public_keys = [
            b"",  # Empty
            b"short",  # Too short
            b"\x00" * 31,  # One byte short
            b"\x00" * 33,  # One byte too long
            b"\x00" * 64,  # Way too long
        ]

        for invalid_key in invalid_public_keys:
            with pytest.raises(ValueError) as exc_info:
                bob_box.decrypt(ciphertext, nonce, invalid_key)

            # Verify error message mentions 32 bytes requirement
            assert "32 bytes" in str(exc_info.value)
            assert str(len(invalid_key)) in str(exc_info.value)
