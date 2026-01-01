"""Integration tests for terminal service relay client.

This test module validates the RelayClient infrastructure component:
1. Connection to relay WebSocket endpoint
2. E2E encryption/decryption with NaCl box
3. Message routing (send terminal output, receive input)
4. Reconnect logic with exponential backoff
5. Keepalive ping/pong handling

Test Strategy: Integration testing with mock relay server
"""

import asyncio
import base64
import json
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nacl.public import Box, PrivateKey, PublicKey
from nacl.utils import random as nacl_random

from agent_remote.services.terminal.infrastructure.relay_client import (
    ConnectionState,
    RelayClient,
    RelayClientConfig,
    RelayClientError,
    RelayConnectionError,
    RelayEncryptionError,
)
from agent_remote.shared.protocol.base import bytes_to_base64, deserialize_message
from agent_remote.shared.protocol.relay_messages import EncryptedBlob, Error, Ping, Pong
from agent_remote.shared.protocol.terminal_messages import (
    TerminalClose,
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)


class TestRelayClientConfig:
    """Test RelayClientConfig dataclass."""

    def test_01_config_with_required_fields(self):
        """Test config creation with required fields only."""
        private_key = PrivateKey.generate()
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(private_key),
        )

        assert config.relay_ws_url == "wss://relay.example.com"
        assert config.session_id == "12345678-1234-1234-1234-123456789012"
        assert len(config.private_key) == 32
        # Check defaults
        assert config.max_reconnect_attempts == 10
        assert config.initial_reconnect_delay == 1.0
        assert config.max_reconnect_delay == 30.0
        assert config.keepalive_interval == 30.0
        assert config.connection_timeout == 10.0

    def test_02_config_with_custom_settings(self):
        """Test config creation with custom reconnect settings."""
        private_key = PrivateKey.generate()
        config = RelayClientConfig(
            relay_ws_url="ws://localhost:8000",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(private_key),
            max_reconnect_attempts=5,
            initial_reconnect_delay=0.5,
            max_reconnect_delay=10.0,
            keepalive_interval=15.0,
            connection_timeout=5.0,
        )

        assert config.max_reconnect_attempts == 5
        assert config.initial_reconnect_delay == 0.5
        assert config.max_reconnect_delay == 10.0
        assert config.keepalive_interval == 15.0
        assert config.connection_timeout == 5.0


class TestRelayClientInitialization:
    """Test RelayClient initialization."""

    def test_01_initialization_success(self):
        """Test successful client initialization."""
        private_key = PrivateKey.generate()
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(private_key),
        )

        client = RelayClient(config)

        assert client.state == ConnectionState.DISCONNECTED
        assert not client.is_connected
        assert client.on_input is None
        assert client.on_resize is None
        assert client.on_close is None
        assert client.on_error is None

    def test_02_initialization_invalid_private_key(self):
        """Test initialization with invalid private key."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=b"too_short",  # Invalid - not 32 bytes
        )

        with pytest.raises(RelayClientError, match="Invalid private key"):
            RelayClient(config)


class TestRelayClientEncryption:
    """Test RelayClient encryption/decryption."""

    @pytest.fixture
    def desktop_keypair(self):
        """Generate desktop keypair."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def client_keypair(self):
        """Generate client keypair (web client)."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def relay_client(self, desktop_keypair):
        """Create RelayClient instance."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(desktop_keypair["private"]),
        )
        return RelayClient(config)

    def test_01_set_client_public_key_success(self, relay_client, client_keypair):
        """Test setting client public key creates encryption box."""
        # Initially no encryption box
        assert relay_client._box is None

        # Set client public key
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Encryption box should be created
        assert relay_client._box is not None
        assert relay_client._client_public_key == bytes(client_keypair["public"])

    def test_02_set_invalid_client_public_key(self, relay_client):
        """Test setting invalid client public key raises error."""
        with pytest.raises(RelayClientError, match="Invalid client public key"):
            relay_client.set_client_public_key(b"invalid_key")

    def test_03_encryption_roundtrip(self, desktop_keypair, client_keypair):
        """Test encryption from desktop to client and back."""
        # Create boxes for both ends
        desktop_box = Box(desktop_keypair["private"], client_keypair["public"])
        client_box = Box(client_keypair["private"], desktop_keypair["public"])

        # Desktop encrypts message
        plaintext = b"Hello from desktop"
        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = desktop_box.encrypt(plaintext, nonce)

        # Client decrypts
        decrypted = client_box.decrypt(ciphertext.ciphertext, nonce)
        assert decrypted == plaintext

        # Client encrypts response
        response = b"Hello from client"
        nonce2 = nacl_random(Box.NONCE_SIZE)
        ciphertext2 = client_box.encrypt(response, nonce2)

        # Desktop decrypts
        decrypted2 = desktop_box.decrypt(ciphertext2.ciphertext, nonce2)
        assert decrypted2 == response


class TestRelayClientMessageHandling:
    """Test RelayClient message handling."""

    @pytest.fixture
    def desktop_keypair(self):
        """Generate desktop keypair."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def client_keypair(self):
        """Generate client keypair."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def relay_client(self, desktop_keypair):
        """Create RelayClient instance."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(desktop_keypair["private"]),
        )
        return RelayClient(config)

    @pytest.fixture
    def client_box(self, client_keypair, desktop_keypair):
        """Create client's encryption box."""
        return Box(client_keypair["private"], desktop_keypair["public"])

    @pytest.mark.asyncio
    async def test_01_handle_ping_sends_pong(self, relay_client):
        """Test that receiving Ping sends Pong response."""
        # Mock WebSocket
        relay_client._ws = AsyncMock()
        relay_client._state = ConnectionState.CONNECTED

        ping = Ping()
        await relay_client._handle_ping(ping)

        # Verify pong was sent
        relay_client._ws.send.assert_called_once()
        sent_json = relay_client._ws.send.call_args[0][0]
        sent_msg = deserialize_message(sent_json)
        assert isinstance(sent_msg, Pong)
        assert sent_msg.timestamp == ping.timestamp

    @pytest.mark.asyncio
    async def test_02_handle_error_calls_callback(self, relay_client):
        """Test that Error message triggers error callback."""
        error_handler = AsyncMock()
        relay_client.on_error = error_handler

        error = Error(
            code="SESSION_EXPIRED",
            message="Session has expired",
            details={"session_id": "12345678-1234-1234-1234-123456789012"},
        )

        await relay_client._handle_error(error)

        error_handler.assert_called_once_with("SESSION_EXPIRED", "Session has expired")

    @pytest.mark.asyncio
    async def test_03_handle_encrypted_input(
        self, relay_client, client_keypair, client_box
    ):
        """Test handling encrypted TerminalInput from client."""
        # Set up encryption
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Set up input handler
        input_handler = AsyncMock()
        relay_client.on_input = input_handler

        # Create and encrypt terminal input message
        session_id = "12345678-1234-1234-1234-123456789012"
        input_msg = TerminalInput(session_id=session_id, data=b"ls -la\r")
        plaintext = input_msg.to_json().encode("utf-8")

        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = client_box.encrypt(plaintext, nonce)

        blob = EncryptedBlob.create(
            session_id=session_id,
            sender="client",
            payload=ciphertext.ciphertext,
            nonce=nonce,
        )

        # Handle the encrypted blob
        await relay_client._handle_encrypted_blob(blob)

        # Verify input handler was called with decrypted data
        input_handler.assert_called_once_with(b"ls -la\r")

    @pytest.mark.asyncio
    async def test_04_handle_encrypted_resize(
        self, relay_client, client_keypair, client_box
    ):
        """Test handling encrypted TerminalResize from client."""
        # Set up encryption
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Set up resize handler
        resize_handler = AsyncMock()
        relay_client.on_resize = resize_handler

        # Create and encrypt terminal resize message
        session_id = "12345678-1234-1234-1234-123456789012"
        resize_msg = TerminalResize(session_id=session_id, rows=40, cols=120)
        plaintext = resize_msg.to_json().encode("utf-8")

        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = client_box.encrypt(plaintext, nonce)

        blob = EncryptedBlob.create(
            session_id=session_id,
            sender="client",
            payload=ciphertext.ciphertext,
            nonce=nonce,
        )

        # Handle the encrypted blob
        await relay_client._handle_encrypted_blob(blob)

        # Verify resize handler was called
        resize_handler.assert_called_once_with(40, 120)

    @pytest.mark.asyncio
    async def test_05_handle_encrypted_close(
        self, relay_client, client_keypair, client_box
    ):
        """Test handling encrypted TerminalClose from client."""
        # Set up encryption
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Set up close handler
        close_handler = AsyncMock()
        relay_client.on_close = close_handler

        # Create and encrypt terminal close message
        session_id = "12345678-1234-1234-1234-123456789012"
        close_msg = TerminalClose(session_id=session_id, reason="User disconnected")
        plaintext = close_msg.to_json().encode("utf-8")

        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = client_box.encrypt(plaintext, nonce)

        blob = EncryptedBlob.create(
            session_id=session_id,
            sender="client",
            payload=ciphertext.ciphertext,
            nonce=nonce,
        )

        # Handle the encrypted blob
        await relay_client._handle_encrypted_blob(blob)

        # Verify close handler was called
        close_handler.assert_called_once_with("User disconnected")

    @pytest.mark.asyncio
    async def test_06_handle_encrypted_without_box(self, relay_client):
        """Test handling encrypted message without encryption box."""
        error_handler = AsyncMock()
        relay_client.on_error = error_handler

        # Create a fake encrypted blob (won't be decrypted)
        blob = EncryptedBlob.create(
            session_id="12345678-1234-1234-1234-123456789012",
            sender="client",
            payload=b"fake_encrypted_data",
            nonce=b"x" * 24,
        )

        await relay_client._handle_encrypted_blob(blob)

        # Error handler should be called
        error_handler.assert_called_once()
        call_args = error_handler.call_args[0]
        assert "CRYPTO_ERROR" in call_args[0]


class TestRelayClientSending:
    """Test RelayClient sending messages."""

    @pytest.fixture
    def desktop_keypair(self):
        """Generate desktop keypair."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def client_keypair(self):
        """Generate client keypair."""
        private_key = PrivateKey.generate()
        return {
            "private": private_key,
            "public": private_key.public_key,
        }

    @pytest.fixture
    def relay_client(self, desktop_keypair):
        """Create RelayClient instance with mock WebSocket."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(desktop_keypair["private"]),
        )
        client = RelayClient(config)
        client._ws = AsyncMock()
        client._state = ConnectionState.CONNECTED
        return client

    @pytest.mark.asyncio
    async def test_01_send_output_not_connected(self, relay_client):
        """Test sending output when not connected raises error."""
        relay_client._state = ConnectionState.DISCONNECTED

        with pytest.raises(RelayClientError, match="Not connected"):
            await relay_client.send_output(b"Hello")

    @pytest.mark.asyncio
    async def test_02_send_output_no_client_key(self, relay_client):
        """Test sending output without client key raises error."""
        with pytest.raises(RelayEncryptionError, match="Client public key not set"):
            await relay_client.send_output(b"Hello")

    @pytest.mark.asyncio
    async def test_03_send_output_success(
        self, relay_client, client_keypair, desktop_keypair
    ):
        """Test successfully sending encrypted output."""
        # Set client public key
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Send output
        await relay_client.send_output(b"Hello World")

        # Verify encrypted message was sent
        relay_client._ws.send.assert_called_once()
        sent_json = relay_client._ws.send.call_args[0][0]

        # Parse the sent message
        sent_msg = deserialize_message(sent_json)
        assert isinstance(sent_msg, EncryptedBlob)
        assert sent_msg.session_id == "12345678-1234-1234-1234-123456789012"
        assert sent_msg.sender == "desktop"

        # Decrypt and verify content
        client_box = Box(client_keypair["private"], desktop_keypair["public"])
        payload = sent_msg.get_payload_bytes()
        nonce = sent_msg.get_nonce_bytes()
        plaintext = client_box.decrypt(payload, nonce)

        # Parse inner message
        inner_msg = deserialize_message(plaintext.decode("utf-8"))
        assert isinstance(inner_msg, TerminalOutput)
        assert inner_msg.data == b"Hello World"

    @pytest.mark.asyncio
    async def test_04_send_close(self, relay_client, client_keypair, desktop_keypair):
        """Test sending close message."""
        # Set client public key
        relay_client.set_client_public_key(bytes(client_keypair["public"]))

        # Send close
        await relay_client.send_close("Session ended")

        # Verify encrypted message was sent
        relay_client._ws.send.assert_called_once()
        sent_json = relay_client._ws.send.call_args[0][0]

        # Parse and decrypt
        sent_msg = deserialize_message(sent_json)
        client_box = Box(client_keypair["private"], desktop_keypair["public"])
        plaintext = client_box.decrypt(
            sent_msg.get_payload_bytes(), sent_msg.get_nonce_bytes()
        )

        inner_msg = deserialize_message(plaintext.decode("utf-8"))
        assert isinstance(inner_msg, TerminalClose)
        assert inner_msg.reason == "Session ended"


class TestRelayClientURLBuilding:
    """Test WebSocket URL building."""

    def test_01_wss_url(self):
        """Test WSS URL is preserved."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "wss://relay.example.com/ws/desktop/12345678-1234-1234-1234-123456789012"

    def test_02_ws_url(self):
        """Test WS URL is preserved."""
        config = RelayClientConfig(
            relay_ws_url="ws://localhost:8000",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "ws://localhost:8000/ws/desktop/12345678-1234-1234-1234-123456789012"

    def test_03_http_to_ws(self):
        """Test HTTP URL is converted to WS."""
        config = RelayClientConfig(
            relay_ws_url="http://localhost:8000",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "ws://localhost:8000/ws/desktop/12345678-1234-1234-1234-123456789012"

    def test_04_https_to_wss(self):
        """Test HTTPS URL is converted to WSS."""
        config = RelayClientConfig(
            relay_ws_url="https://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "wss://relay.example.com/ws/desktop/12345678-1234-1234-1234-123456789012"

    def test_05_no_scheme(self):
        """Test URL without scheme gets WSS prefix."""
        config = RelayClientConfig(
            relay_ws_url="relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "wss://relay.example.com/ws/desktop/12345678-1234-1234-1234-123456789012"

    def test_06_trailing_slash_removed(self):
        """Test trailing slash is removed."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com/",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
        )
        client = RelayClient(config)
        url = client._build_ws_url()
        assert url == "wss://relay.example.com/ws/desktop/12345678-1234-1234-1234-123456789012"


class TestRelayClientLifecycle:
    """Test RelayClient connection lifecycle."""

    @pytest.fixture
    def relay_client(self):
        """Create RelayClient instance."""
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id="12345678-1234-1234-1234-123456789012",
            private_key=bytes(PrivateKey.generate()),
            max_reconnect_attempts=3,
            initial_reconnect_delay=0.1,
            max_reconnect_delay=0.5,
            connection_timeout=1.0,
        )
        return RelayClient(config)

    @pytest.mark.asyncio
    async def test_01_close_sets_closed_state(self, relay_client):
        """Test close() sets state to CLOSED."""
        await relay_client.close()
        assert relay_client.state == ConnectionState.CLOSED

    @pytest.mark.asyncio
    async def test_02_cannot_connect_after_close(self, relay_client):
        """Test connect() fails after close()."""
        await relay_client.close()

        with pytest.raises(RelayClientError, match="has been closed"):
            await relay_client.connect()

    @pytest.mark.asyncio
    async def test_03_close_is_idempotent(self, relay_client):
        """Test close() can be called multiple times safely."""
        await relay_client.close()
        await relay_client.close()
        await relay_client.close()
        assert relay_client.state == ConnectionState.CLOSED
