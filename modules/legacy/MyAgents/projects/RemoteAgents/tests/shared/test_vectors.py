"""Test vectors for cross-platform validation between Python and Flutter.

This module contains pytest tests that validate protocol message serialization
and cryptography operations against known-good test vectors. These vectors
ensure that the Python and Flutter implementations are compatible.

Test vectors are stored in JSON files in the fixtures/ directory:
- protocol_vectors.json: Message serialization/deserialization tests
- crypto_vectors.json: NaCl encryption/decryption tests

Run these tests with:
    pytest tests/shared/test_vectors.py -v
    pytest -m test_vectors  # Run all test vector tests
"""

import base64
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

# Import all message types
from agent_remote.shared.protocol.base import deserialize_message
from agent_remote.shared.protocol.terminal_messages import (
    TerminalClose,
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)
from agent_remote.shared.protocol.session_messages import (
    SessionClose,
    SessionCreate,
    SessionCreated,
    SessionPair,
    SessionPaired,
)
from agent_remote.shared.protocol.relay_messages import (
    EncryptedBlob,
    Error,
    Ping,
    Pong,
)


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def protocol_vectors():
    """Load protocol test vectors from JSON file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    vectors_file = fixtures_dir / "protocol_vectors.json"

    with open(vectors_file, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def crypto_vectors():
    """Load crypto test vectors from JSON file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    vectors_file = fixtures_dir / "crypto_vectors.json"

    with open(vectors_file, "r") as f:
        return json.load(f)


# ==============================================================================
# Protocol Message Tests - Valid Examples
# ==============================================================================


@pytest.mark.test_vectors
class TestProtocolValidExamples:
    """Test valid protocol message examples can be deserialized and re-serialized."""

    def test_terminal_output(self, protocol_vectors):
        """Test TerminalOutput message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["terminal_output"]
        json_str = json.dumps(vector["json"])

        # Deserialize from JSON
        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalOutput)
        assert msg.type == "terminal.output"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.timestamp == 1234567890.123

        # Verify data field is correctly decoded from base64
        assert msg.data == b"Hello World\n"

        # Re-serialize and verify structure
        reserialized = json.loads(msg.to_json())
        assert reserialized["type"] == "terminal.output"
        assert reserialized["data"] == "SGVsbG8gV29ybGQK"

    def test_terminal_input(self, protocol_vectors):
        """Test TerminalInput message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["terminal_input"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalInput)
        assert msg.type == "terminal.input"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.timestamp == 1234567890.456
        assert msg.data == b"ls -la\r"

    def test_terminal_resize(self, protocol_vectors):
        """Test TerminalResize message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["terminal_resize"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalResize)
        assert msg.type == "terminal.resize"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.rows == 24
        assert msg.cols == 80

    def test_terminal_close(self, protocol_vectors):
        """Test TerminalClose message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["terminal_close"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalClose)
        assert msg.type == "terminal.close"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.reason == "User disconnected"

    def test_session_create(self, protocol_vectors):
        """Test SessionCreate message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["session_create"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, SessionCreate)
        assert msg.type == "session.create"
        assert len(msg.desktop_public_key) == 32

        # Re-serialize and verify base64 encoding
        reserialized = json.loads(msg.to_json())
        assert reserialized["desktop_public_key"] == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    def test_session_created(self, protocol_vectors):
        """Test SessionCreated message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["session_created"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, SessionCreated)
        assert msg.type == "session.created"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.pairing_code == "ABC123"

    def test_session_pair(self, protocol_vectors):
        """Test SessionPair message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["session_pair"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, SessionPair)
        assert msg.type == "session.pair"
        assert msg.pairing_code == "XYZ789"
        assert len(msg.client_public_key) == 32

    def test_session_paired(self, protocol_vectors):
        """Test SessionPaired message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["session_paired"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, SessionPaired)
        assert msg.type == "session.paired"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert len(msg.desktop_public_key) == 32

    def test_session_close(self, protocol_vectors):
        """Test SessionClose message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["session_close"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, SessionClose)
        assert msg.type == "session.close"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"

    def test_encrypted_blob(self, protocol_vectors):
        """Test EncryptedBlob message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["encrypted_blob"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, EncryptedBlob)
        assert msg.type == "relay.encrypted"
        assert msg.session_id == "123e4567-e89b-12d3-a456-426614174000"
        assert msg.sender == "desktop"

        # Verify nonce is exactly 24 bytes
        nonce_bytes = msg.get_nonce_bytes()
        assert len(nonce_bytes) == 24

    def test_ping(self, protocol_vectors):
        """Test Ping message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["ping"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, Ping)
        assert msg.type == "relay.ping"
        assert msg.timestamp == 1234567890.789

    def test_pong(self, protocol_vectors):
        """Test Pong message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["pong"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, Pong)
        assert msg.type == "relay.pong"
        assert msg.timestamp == 1234567890.789

    def test_error(self, protocol_vectors):
        """Test Error message serialization/deserialization."""
        vector = protocol_vectors["valid_examples"]["error"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, Error)
        assert msg.type == "relay.error"
        assert msg.code == "SESSION_EXPIRED"
        assert msg.message == "Session abc123 expired after 1 hour of inactivity"
        assert msg.details == {
            "session_id": "abc123",
            "expired_at": "2025-12-04T10:00:00Z"
        }


# ==============================================================================
# Protocol Message Tests - Invalid Examples
# ==============================================================================


@pytest.mark.test_vectors
class TestProtocolInvalidExamples:
    """Test invalid protocol messages fail validation as expected."""

    def test_invalid_session_id_wrong_format(self, protocol_vectors):
        """Test that invalid UUID format fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_session_id_wrong_format"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        # Verify error message mentions UUID
        error_msg = str(exc_info.value).lower()
        assert "uuid" in error_msg or "session_id" in error_msg

    def test_invalid_nonce_length_short(self, protocol_vectors):
        """Test that short nonce fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_nonce_length_short"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "24 bytes" in error_msg or "nonce" in error_msg.lower()

    def test_invalid_nonce_length_long(self, protocol_vectors):
        """Test that long nonce fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_nonce_length_long"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "24 bytes" in error_msg or "nonce" in error_msg.lower()

    def test_invalid_public_key_length_short(self, protocol_vectors):
        """Test that short public key fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_public_key_length_short"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "32 bytes" in error_msg or "public_key" in error_msg.lower()

    def test_invalid_public_key_length_long(self, protocol_vectors):
        """Test that long public key fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_public_key_length_long"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "32 bytes" in error_msg or "public_key" in error_msg.lower()

    def test_invalid_terminal_rows_negative(self, protocol_vectors):
        """Test that negative rows fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_terminal_rows_negative"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)):
            deserialize_message(json_str)

    def test_invalid_terminal_rows_zero(self, protocol_vectors):
        """Test that zero rows fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_terminal_rows_zero"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)):
            deserialize_message(json_str)

    def test_invalid_terminal_rows_too_large(self, protocol_vectors):
        """Test that rows > 1000 fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_terminal_rows_too_large"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)):
            deserialize_message(json_str)

    def test_invalid_pairing_code_too_short(self, protocol_vectors):
        """Test that short pairing code fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_pairing_code_too_short"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "pairing_code" in error_msg.lower() or "6" in error_msg

    def test_invalid_pairing_code_lowercase(self, protocol_vectors):
        """Test that lowercase pairing code fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_pairing_code_lowercase"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            deserialize_message(json_str)

        error_msg = str(exc_info.value)
        assert "uppercase" in error_msg.lower() or "pairing_code" in error_msg.lower()

    def test_invalid_pairing_code_special_chars(self, protocol_vectors):
        """Test that pairing code with special characters fails validation."""
        vector = protocol_vectors["invalid_examples"]["invalid_pairing_code_special_chars"]
        json_str = json.dumps(vector["json"])

        with pytest.raises((ValidationError, ValueError)):
            deserialize_message(json_str)


# ==============================================================================
# Protocol Message Tests - Edge Cases
# ==============================================================================


@pytest.mark.test_vectors
class TestProtocolEdgeCases:
    """Test edge cases for protocol messages."""

    def test_terminal_output_empty_data(self, protocol_vectors):
        """Test terminal output with empty data (0 bytes)."""
        vector = protocol_vectors["edge_cases"]["terminal_output_empty_data"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalOutput)
        assert msg.data == b""

    def test_terminal_output_unicode(self, protocol_vectors):
        """Test terminal output with UTF-8 emoji."""
        vector = protocol_vectors["edge_cases"]["terminal_output_unicode"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalOutput)
        # Verify it contains emoji (UTF-8 encoded)
        assert len(msg.data) > 0

    def test_terminal_resize_minimum_size(self, protocol_vectors):
        """Test minimum terminal size (1x1)."""
        vector = protocol_vectors["edge_cases"]["terminal_resize_minimum_size"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalResize)
        assert msg.rows == 1
        assert msg.cols == 1

    def test_terminal_resize_maximum_size(self, protocol_vectors):
        """Test maximum terminal size (1000x1000)."""
        vector = protocol_vectors["edge_cases"]["terminal_resize_maximum_size"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, TerminalResize)
        assert msg.rows == 1000
        assert msg.cols == 1000

    def test_error_minimal(self, protocol_vectors):
        """Test error message without optional details field."""
        vector = protocol_vectors["edge_cases"]["error_minimal"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, Error)
        assert msg.code == "INTERNAL_ERROR"
        assert msg.message == "An error occurred"
        assert msg.details is None

    def test_error_empty_details(self, protocol_vectors):
        """Test error message with empty details dict."""
        vector = protocol_vectors["edge_cases"]["error_empty_details"]
        json_str = json.dumps(vector["json"])

        msg = deserialize_message(json_str)
        assert isinstance(msg, Error)
        assert msg.details == {}


# ==============================================================================
# Serialization Roundtrip Tests
# ==============================================================================


@pytest.mark.test_vectors
class TestSerializationRoundtrip:
    """Test that messages can be serialized and deserialized identically."""

    def test_terminal_output_roundtrip(self, protocol_vectors):
        """Test TerminalOutput roundtrip serialization."""
        vector = protocol_vectors["serialization_roundtrip"]["examples"][0]
        json_str = json.dumps(vector["json"])

        # Deserialize
        msg = deserialize_message(json_str)

        # Verify data is correct
        assert msg.data.decode("utf-8") == vector["expected_data_bytes"]

        # Re-serialize
        reserialized = msg.to_json()
        msg2 = deserialize_message(reserialized)

        # Verify roundtrip preserves data
        assert msg.data == msg2.data
        assert msg.session_id == msg2.session_id
        assert msg.timestamp == msg2.timestamp

    def test_session_create_roundtrip(self, protocol_vectors):
        """Test SessionCreate roundtrip serialization."""
        vector = protocol_vectors["serialization_roundtrip"]["examples"][1]
        json_str = json.dumps(vector["json"])

        # Deserialize
        msg = deserialize_message(json_str)

        # Verify key length
        assert len(msg.desktop_public_key) == vector["expected_key_bytes_length"]

        # Re-serialize
        reserialized = msg.to_json()
        msg2 = deserialize_message(reserialized)

        # Verify roundtrip preserves key
        assert msg.desktop_public_key == msg2.desktop_public_key


# ==============================================================================
# Crypto Tests - Basic Functionality
# ==============================================================================


@pytest.mark.test_vectors
class TestCryptoBasics:
    """Test basic cryptography operations using test vectors.

    Note: These tests verify that the test vectors are properly formatted
    and can be loaded. Actual encryption/decryption tests require PyNaCl
    to be installed and are in a separate test class.
    """

    def test_load_crypto_vectors(self, crypto_vectors):
        """Test that crypto vectors can be loaded."""
        assert "test_keypairs" in crypto_vectors
        assert "encryption_examples" in crypto_vectors
        assert "roundtrip_examples" in crypto_vectors
        assert "invalid_examples" in crypto_vectors

    def test_keypair_format(self, crypto_vectors):
        """Test that test keypairs are properly formatted."""
        keypair = crypto_vectors["test_keypairs"]["keypair_1"]

        # Decode keys
        public_key = base64.b64decode(keypair["public_key"])
        private_key = base64.b64decode(keypair["private_key"])

        # Verify lengths
        assert len(public_key) == 32, "Public key must be 32 bytes"
        assert len(private_key) == 32, "Private key must be 32 bytes"

    def test_encryption_example_format(self, crypto_vectors):
        """Test that encryption examples are properly formatted."""
        example = crypto_vectors["encryption_examples"]["example_1"]

        # Verify all required fields
        assert "plaintext" in example
        assert "plaintext_base64" in example
        assert "sender_keypair" in example
        assert "receiver_keypair" in example
        assert "nonce" in example
        assert "ciphertext_base64" in example

        # Verify nonce is 24 bytes
        nonce = base64.b64decode(example["nonce"])
        assert len(nonce) == 24, "Nonce must be 24 bytes"


# ==============================================================================
# Crypto Tests - Encryption/Decryption (requires PyNaCl)
# ==============================================================================


@pytest.mark.test_vectors
class TestCryptoEncryption:
    """Test encryption/decryption using test vectors.

    These tests require PyNaCl to be installed. If not available, tests are skipped.
    """

    @pytest.fixture(autouse=True)
    def check_nacl(self):
        """Check if PyNaCl is available, skip tests if not."""
        try:
            import nacl.public
            import nacl.utils
        except ImportError:
            pytest.skip("PyNaCl not installed - skipping crypto tests")

    def test_decrypt_example_1(self, crypto_vectors):
        """Test decrypting example 1 produces expected plaintext."""
        from nacl.public import PrivateKey, PublicKey, Box

        example = crypto_vectors["encryption_examples"]["example_1"]

        # Load receiver's keypair
        receiver_kp = crypto_vectors["test_keypairs"]["keypair_2"]
        receiver_private = PrivateKey(base64.b64decode(receiver_kp["private_key"]))

        # Load sender's public key
        sender_kp = crypto_vectors["test_keypairs"]["keypair_1"]
        sender_public = PublicKey(base64.b64decode(sender_kp["public_key"]))

        # Create box for decryption
        box = Box(receiver_private, sender_public)

        # Decrypt
        nonce = base64.b64decode(example["nonce"])
        ciphertext = base64.b64decode(example["ciphertext_base64"])
        plaintext_bytes = box.decrypt(ciphertext, nonce)
        plaintext = plaintext_bytes.decode("utf-8")

        # Verify
        assert plaintext == example["plaintext"]

    def test_decrypt_empty_message(self, crypto_vectors):
        """Test decrypting empty message."""
        from nacl.public import PrivateKey, PublicKey, Box

        example = crypto_vectors["encryption_examples"]["example_2"]

        # Load keys
        receiver_kp = crypto_vectors["test_keypairs"]["keypair_2"]
        receiver_private = PrivateKey(base64.b64decode(receiver_kp["private_key"]))

        sender_kp = crypto_vectors["test_keypairs"]["keypair_1"]
        sender_public = PublicKey(base64.b64decode(sender_kp["public_key"]))

        box = Box(receiver_private, sender_public)

        # Decrypt
        nonce = base64.b64decode(example["nonce"])
        ciphertext = base64.b64decode(example["ciphertext_base64"])
        plaintext_bytes = box.decrypt(ciphertext, nonce)
        plaintext = plaintext_bytes.decode("utf-8")

        # Verify empty string
        assert plaintext == ""
        assert plaintext == example["plaintext"]

    def test_decrypt_unicode_message(self, crypto_vectors):
        """Test decrypting unicode message with emoji."""
        from nacl.public import PrivateKey, PublicKey, Box

        example = crypto_vectors["encryption_examples"]["example_3"]

        # Load keys
        receiver_kp = crypto_vectors["test_keypairs"]["keypair_2"]
        receiver_private = PrivateKey(base64.b64decode(receiver_kp["private_key"]))

        sender_kp = crypto_vectors["test_keypairs"]["keypair_1"]
        sender_public = PublicKey(base64.b64decode(sender_kp["public_key"]))

        box = Box(receiver_private, sender_public)

        # Decrypt
        nonce = base64.b64decode(example["nonce"])
        ciphertext = base64.b64decode(example["ciphertext_base64"])
        plaintext_bytes = box.decrypt(ciphertext, nonce)
        plaintext = plaintext_bytes.decode("utf-8")

        # Verify unicode is preserved
        assert plaintext == example["plaintext"]
        assert "😀" in plaintext
        assert "🌍" in plaintext

    def test_roundtrip_encryption(self, crypto_vectors):
        """Test encrypting and decrypting produces original plaintext."""
        from nacl.public import PrivateKey, PublicKey, Box
        import nacl.utils

        # Load keypairs
        sender_kp = crypto_vectors["test_keypairs"]["keypair_1"]
        sender_private = PrivateKey(base64.b64decode(sender_kp["private_key"]))
        sender_public = PublicKey(base64.b64decode(sender_kp["public_key"]))

        receiver_kp = crypto_vectors["test_keypairs"]["keypair_2"]
        receiver_private = PrivateKey(base64.b64decode(receiver_kp["private_key"]))
        receiver_public = PublicKey(base64.b64decode(receiver_kp["public_key"]))

        # Encrypt with sender
        sender_box = Box(sender_private, receiver_public)
        plaintext = "Test roundtrip message"
        nonce = nacl.utils.random(Box.NONCE_SIZE)
        ciphertext = sender_box.encrypt(plaintext.encode("utf-8"), nonce).ciphertext

        # Decrypt with receiver
        receiver_box = Box(receiver_private, sender_public)
        decrypted_bytes = receiver_box.decrypt(ciphertext, nonce)
        decrypted = decrypted_bytes.decode("utf-8")

        # Verify roundtrip
        assert decrypted == plaintext


# ==============================================================================
# Test Vector Metadata
# ==============================================================================


@pytest.mark.test_vectors
def test_protocol_vectors_metadata(protocol_vectors):
    """Test protocol vectors file has proper metadata."""
    assert "description" in protocol_vectors
    assert "version" in protocol_vectors
    assert "generated_at" in protocol_vectors
    assert protocol_vectors["version"] == "1.0.0"


@pytest.mark.test_vectors
def test_crypto_vectors_metadata(crypto_vectors):
    """Test crypto vectors file has proper metadata."""
    assert "description" in crypto_vectors
    assert "version" in crypto_vectors
    assert "generated_at" in crypto_vectors
    assert "algorithm" in crypto_vectors
    assert crypto_vectors["version"] == "1.0.0"
    assert "NaCl" in crypto_vectors["algorithm"]
