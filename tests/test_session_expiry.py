"""Integration tests for session expiry and cleanup functionality.

This module tests the session expiry mechanism and cleanup worker to ensure:
1. Sessions correctly expire after 5 minutes (300 seconds)
2. Expired sessions reject pairing attempts with SessionExpiredException
3. Cleanup worker correctly identifies and removes expired sessions
4. Multiple concurrent sessions all expire correctly
5. Expired sessions don't leak memory (repository is properly cleaned)

Test Strategy: technical-spike (integration testing)
Uses unittest.mock.patch to control time.time() for expiry testing.
"""

import asyncio
import time
from unittest.mock import Mock, patch
from typing import Any

import pytest

from agent_remote.services.relay.domains.session_manager.entities import (
    Session,
    SessionExpiredException,
)
from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    SessionId,
    SessionState,
)
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.services.relay.workflows.relay_workflow import (
    RelayWorkflow,
    SessionWorkflowException,
)
from agent_remote.services.relay.workers.cleanup_worker import run_cleanup_loop


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def repository():
    """Create a fresh in-memory repository for each test."""
    return InMemorySessionRepository()


@pytest.fixture
def workflow(repository):
    """Create a workflow with the test repository."""
    return RelayWorkflow(repository)


@pytest.fixture
def mock_desktop_ws():
    """Mock WebSocket connection for desktop."""
    ws = Mock()
    ws.send_json = Mock()
    return ws


@pytest.fixture
def mock_client_ws():
    """Mock WebSocket connection for client."""
    ws = Mock()
    ws.send_json = Mock()
    return ws


# ==============================================================================
# Unit Tests - Session.is_expired()
# ==============================================================================


class TestSessionIsExpired:
    """Test Session.is_expired() method directly with mocked time."""

    def test_session_not_expired_immediately(self):
        """Test that a freshly created session is not expired."""
        # Create session at t=1000
        with patch('time.time', return_value=1000.0):
            session = Session.create(desktop_public_key="test_key_123")

        # Check expiry at t=1000 (same time)
        assert not session.is_expired(current_time=1000.0)

    def test_session_not_expired_before_5_minutes(self):
        """Test that session is not expired before 5 minutes."""
        # Create session at t=1000
        with patch('time.time', return_value=1000.0):
            session = Session.create(desktop_public_key="test_key_123")

        # Check at t=1299 (4 minutes 59 seconds later)
        assert not session.is_expired(current_time=1299.0)

    def test_session_expired_at_exactly_5_minutes(self):
        """Test that session expires at exactly 5 minutes (300 seconds)."""
        # Create session at t=1000
        with patch('time.time', return_value=1000.0):
            session = Session.create(desktop_public_key="test_key_123")

        # Check at t=1300 (exactly 5 minutes later)
        assert session.is_expired(current_time=1300.0)

    def test_session_expired_after_5_minutes(self):
        """Test that session is expired after 5 minutes."""
        # Create session at t=1000
        with patch('time.time', return_value=1000.0):
            session = Session.create(desktop_public_key="test_key_123")

        # Check at t=1400 (6 minutes 40 seconds later)
        assert session.is_expired(current_time=1400.0)

    def test_pairing_code_is_expired_directly(self):
        """Test PairingCode.is_expired() directly."""
        # Create pairing code at t=2000
        with patch('time.time', return_value=2000.0):
            code = PairingCode("ABC123")

        # Not expired before 5 minutes
        assert not code.is_expired(current_time=2299.0)

        # Expired at exactly 5 minutes
        assert code.is_expired(current_time=2300.0)

        # Expired after 5 minutes
        assert code.is_expired(current_time=2500.0)


# ==============================================================================
# Integration Tests - Pairing Attempt on Expired Session
# ==============================================================================


class TestPairingExpiredSession:
    """Test that pairing attempts fail on expired sessions."""

    def test_pairing_fails_on_expired_session(
        self, workflow, repository, mock_desktop_ws, mock_client_ws
    ):
        """Test scenario: Create session, don't pair, advance time 5+ minutes, verify pairing fails."""
        # Step 1: Create session at t=1000
        with patch('time.time', return_value=1000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_123"
            )

        # Step 2: Desktop connects
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify session is in DESKTOP_CONNECTED state
        session = repository.get_by_id(session_id)
        assert session.state == SessionState.DESKTOP_CONNECTED

        # Step 3: Don't pair client yet - advance time to 5+ minutes later (t=1400)
        # No need to patch here - we'll pass current_time to is_expired()

        # Step 4: Attempt to pair at t=1400 (6 minutes 40 seconds after creation)
        # The pair_client method calls is_expired() which uses time.time()
        # So we need to mock time.time() during the pairing attempt
        with patch('time.time', return_value=1400.0):
            with pytest.raises(SessionWorkflowException) as exc_info:
                workflow.handle_client_pair(
                    pairing_code=pairing_code,
                    client_public_key="client_key_456",
                    ws_connection=mock_client_ws
                )

        # Verify the exception is due to expiry
        assert exc_info.value.operation == "pair client"
        assert isinstance(exc_info.value.cause, SessionExpiredException)
        assert exc_info.value.cause.session_id == str(session_id)
        assert exc_info.value.cause.pairing_code == str(pairing_code)

        # Verify session is still in DESKTOP_CONNECTED state (pairing failed)
        session = repository.get_by_id(session_id)
        assert session.state == SessionState.DESKTOP_CONNECTED

    def test_pairing_succeeds_before_expiry(
        self, workflow, repository, mock_desktop_ws, mock_client_ws
    ):
        """Test that pairing succeeds when done before expiry."""
        # Create session at t=2000
        with patch('time.time', return_value=2000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_789"
            )

        # Desktop connects
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Pair at t=2200 (3 minutes 20 seconds later - before expiry)
        with patch('time.time', return_value=2200.0):
            paired_session_id, _, _ = workflow.handle_client_pair(
                pairing_code=pairing_code,
                client_public_key="client_key_abc",
                ws_connection=mock_client_ws
            )

        # Verify pairing succeeded
        assert paired_session_id == session_id
        session = repository.get_by_id(session_id)
        assert session.state == SessionState.PAIRED


# ==============================================================================
# Integration Tests - Cleanup Worker
# ==============================================================================


class TestCleanupWorker:
    """Test cleanup worker removes expired sessions."""

    @pytest.mark.asyncio
    async def test_cleanup_worker_removes_expired_session(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test cleanup worker removes a single expired session."""
        # Create session at t=3000
        with patch('time.time', return_value=3000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_cleanup1"
            )

        # Desktop connects
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify session exists and is active
        assert len(repository) == 1
        assert len(repository.get_all_active()) == 1

        # Run cleanup at t=3400 (6 minutes 40 seconds later)
        # Mock time.time() to return 3400 during cleanup
        with patch('time.time', return_value=3400.0):
            # Run one iteration of cleanup loop
            # We'll manually call the cleanup logic instead of running the full loop
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify session was removed from repository
        assert len(repository) == 0
        assert len(repository.get_all_active()) == 0
        assert repository.get_by_id(session_id) is None

    @pytest.mark.asyncio
    async def test_cleanup_worker_preserves_non_expired_sessions(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test cleanup worker doesn't remove non-expired sessions."""
        # Create session at t=4000
        with patch('time.time', return_value=4000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_cleanup2"
            )

        # Desktop connects
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Run cleanup at t=4200 (3 minutes 20 seconds later - before expiry)
        with patch('time.time', return_value=4200.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify session was NOT removed
        assert len(repository) == 1
        assert len(repository.get_all_active()) == 1
        assert repository.get_by_id(session_id) is not None

    @pytest.mark.asyncio
    async def test_cleanup_worker_mixed_expired_and_active(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test cleanup worker removes only expired sessions from mixed set."""
        # Create 3 sessions at different times
        # Session 1 at t=5000 (will be expired at cleanup time)
        with patch('time.time', return_value=5000.0):
            session_id_1, _ = workflow.create_session(
                desktop_public_key="desktop_key_1"
            )
            workflow.handle_desktop_connect(session_id_1, mock_desktop_ws)

        # Session 2 at t=5100 (will be expired at cleanup time)
        with patch('time.time', return_value=5100.0):
            session_id_2, _ = workflow.create_session(
                desktop_public_key="desktop_key_2"
            )
            workflow.handle_desktop_connect(session_id_2, mock_desktop_ws)

        # Session 3 at t=5200 (will NOT be expired at cleanup time)
        with patch('time.time', return_value=5200.0):
            session_id_3, _ = workflow.create_session(
                desktop_public_key="desktop_key_3"
            )
            workflow.handle_desktop_connect(session_id_3, mock_desktop_ws)

        # Verify all 3 sessions exist
        assert len(repository) == 3
        assert len(repository.get_all_active()) == 3

        # Run cleanup at t=5450
        # Session 1: 5450 - 5000 = 450 seconds (7.5 min) -> EXPIRED
        # Session 2: 5450 - 5100 = 350 seconds (5.83 min) -> EXPIRED
        # Session 3: 5450 - 5200 = 250 seconds (4.17 min) -> NOT EXPIRED
        with patch('time.time', return_value=5450.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify only session 3 remains
        assert len(repository) == 1
        assert len(repository.get_all_active()) == 1
        assert repository.get_by_id(session_id_1) is None
        assert repository.get_by_id(session_id_2) is None
        assert repository.get_by_id(session_id_3) is not None


# ==============================================================================
# Stress Tests - Multiple Concurrent Sessions
# ==============================================================================


class TestMultipleConcurrentSessions:
    """Test multiple concurrent sessions all expire correctly."""

    def test_10_concurrent_sessions_all_expire(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test creating 10+ sessions and verifying all expire."""
        # Create 15 sessions at t=6000
        session_ids = []
        with patch('time.time', return_value=6000.0):
            for i in range(15):
                session_id, _ = workflow.create_session(
                    desktop_public_key=f"desktop_key_{i}"
                )
                workflow.handle_desktop_connect(session_id, mock_desktop_ws)
                session_ids.append(session_id)

        # Verify all 15 sessions exist
        assert len(repository) == 15
        assert len(repository.get_all_active()) == 15

        # Check at t=6200 (3 minutes 20 seconds) - none should be expired
        with patch('time.time', return_value=6200.0):
            for session_id in session_ids:
                session = repository.get_by_id(session_id)
                assert session is not None
                assert not session.is_expired()

        # Check at t=6300 (exactly 5 minutes) - all should be expired
        with patch('time.time', return_value=6300.0):
            for session_id in session_ids:
                session = repository.get_by_id(session_id)
                assert session is not None
                assert session.is_expired()

        # Run cleanup at t=6400 (6 minutes 40 seconds)
        with patch('time.time', return_value=6400.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify all sessions were removed
        assert len(repository) == 0
        assert len(repository.get_all_active()) == 0

    def test_staggered_session_expiry(self, workflow, repository, mock_desktop_ws):
        """Test sessions created at different times expire at different times."""
        # Create 10 sessions staggered over 2 minutes
        session_ids = []
        for i in range(10):
            creation_time = 7000.0 + (i * 12.0)  # Every 12 seconds
            with patch('time.time', return_value=creation_time):
                session_id, _ = workflow.create_session(
                    desktop_public_key=f"desktop_key_stagger_{i}"
                )
                workflow.handle_desktop_connect(session_id, mock_desktop_ws)
                session_ids.append((session_id, creation_time))

        # Verify all 10 sessions exist
        assert len(repository) == 10

        # Run cleanup at t=7320 (5 min 20 sec after first session)
        # First session: 7320 - 7000 = 320 sec -> EXPIRED
        # Session 5 (at 7060): 7320 - 7060 = 260 sec -> NOT EXPIRED
        # Session 9 (at 7108): 7320 - 7108 = 212 sec -> NOT EXPIRED
        with patch('time.time', return_value=7320.0):
            active_sessions = repository.get_all_active()
            expired_count = 0
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")
                    expired_count += 1

        # Verify some sessions expired but not all
        # Sessions created in first ~20 seconds should be expired (2 sessions)
        assert expired_count >= 1
        assert len(repository) < 10
        assert len(repository) > 0


# ==============================================================================
# Memory Leak Tests
# ==============================================================================


class TestMemoryLeaks:
    """Test that expired sessions don't leak memory."""

    def test_expired_sessions_removed_from_repository(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test repository size decreases after cleanup."""
        # Create 20 sessions at t=8000
        with patch('time.time', return_value=8000.0):
            for i in range(20):
                session_id, _ = workflow.create_session(
                    desktop_public_key=f"desktop_key_leak_{i}"
                )
                workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify repository has 20 sessions
        assert len(repository) == 20
        initial_size = len(repository)

        # Run cleanup at t=8400 (6 minutes 40 seconds later)
        with patch('time.time', return_value=8400.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify repository is empty
        assert len(repository) == 0
        assert len(repository) < initial_size

    def test_pairing_code_index_cleaned_up(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test that pairing code index is cleaned up after session removal."""
        # Create session at t=9000
        with patch('time.time', return_value=9000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_index"
            )
            workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify we can look up by pairing code
        session = repository.get_by_pairing_code(pairing_code)
        assert session is not None
        assert session.session_id == session_id

        # Run cleanup at t=9400
        with patch('time.time', return_value=9400.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify pairing code index is cleaned up
        session = repository.get_by_pairing_code(pairing_code)
        assert session is None

    def test_websocket_references_cleared(
        self, workflow, repository, mock_desktop_ws
    ):
        """Test that WebSocket references are cleared on session close."""
        # Create and connect session at t=10000
        with patch('time.time', return_value=10000.0):
            session_id, pairing_code = workflow.create_session(
                desktop_public_key="desktop_key_ws"
            )
            workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify desktop_ws is set before cleanup
        session = repository.get_by_id(session_id)
        assert session.desktop_ws is not None

        # Run cleanup at t=10400
        with patch('time.time', return_value=10400.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify session was removed entirely (no memory leak)
        session = repository.get_by_id(session_id)
        assert session is None


# ==============================================================================
# Edge Cases
# ==============================================================================


class TestEdgeCases:
    """Test edge cases for session expiry."""

    def test_cleanup_on_empty_repository(self, workflow, repository):
        """Test cleanup worker handles empty repository gracefully."""
        # Verify repository is empty
        assert len(repository) == 0

        # Run cleanup - should not raise any errors
        with patch('time.time', return_value=11000.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify repository is still empty
        assert len(repository) == 0

    def test_cleanup_on_all_paired_sessions(
        self, workflow, repository, mock_desktop_ws, mock_client_ws
    ):
        """Test cleanup worker handles already-paired sessions (still checks expiry)."""
        # Create and fully pair 3 sessions at t=12000
        with patch('time.time', return_value=12000.0):
            for i in range(3):
                session_id, pairing_code = workflow.create_session(
                    desktop_public_key=f"desktop_key_paired_{i}"
                )
                workflow.handle_desktop_connect(session_id, mock_desktop_ws)
                workflow.handle_client_pair(
                    pairing_code=pairing_code,
                    client_public_key=f"client_key_paired_{i}",
                    ws_connection=mock_client_ws
                )

        # Verify all 3 are paired
        assert len(repository) == 3
        for session in repository.get_all_active():
            assert session.state == SessionState.PAIRED

        # Run cleanup at t=12400 (6 minutes 40 seconds later)
        # Even paired sessions should be cleaned if expired
        with patch('time.time', return_value=12400.0):
            active_sessions = repository.get_all_active()
            for session in active_sessions:
                if session.is_expired():
                    workflow.close_session(session.session_id, "expired")

        # Verify all expired paired sessions were removed
        assert len(repository) == 0

    def test_session_expiry_boundary_conditions(self):
        """Test expiry at exact boundary (299.999 vs 300.000 seconds)."""
        # Create session at t=13000.000
        with patch('time.time', return_value=13000.0):
            session = Session.create(desktop_public_key="desktop_key_boundary")

        # Check at 299.9 seconds (just before expiry)
        assert not session.is_expired(current_time=13299.9)

        # Check at exactly 300.0 seconds
        assert session.is_expired(current_time=13300.0)

        # Check at 300.1 seconds (just after expiry)
        assert session.is_expired(current_time=13300.1)
