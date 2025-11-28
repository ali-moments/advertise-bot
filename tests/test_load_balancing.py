"""
Tests for load balancing functionality (Task 7)
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.session import TelegramSession


@pytest_asyncio.fixture
async def manager_with_sessions():
    """Create a manager with multiple mock sessions"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Create 3 mock sessions
    for i in range(3):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize session load
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    yield manager


@pytest.mark.asyncio
async def test_session_load_tracking_initialization(manager_with_sessions):
    """Test that session load tracking is initialized correctly"""
    manager = manager_with_sessions
    
    # Check that all sessions have load initialized to 0
    for session_name in manager.sessions.keys():
        load = await manager.get_session_load(session_name)
        assert load == 0, f"Session {session_name} should have load 0"


@pytest.mark.asyncio
async def test_increment_and_decrement_session_load(manager_with_sessions):
    """Test incrementing and decrementing session load"""
    manager = manager_with_sessions
    session_name = "session_0"
    
    # Initial load should be 0
    load = await manager.get_session_load(session_name)
    assert load == 0
    
    # Increment load
    await manager.increment_session_load(session_name)
    load = await manager.get_session_load(session_name)
    assert load == 1
    
    # Increment again
    await manager.increment_session_load(session_name)
    load = await manager.get_session_load(session_name)
    assert load == 2
    
    # Decrement load
    await manager.decrement_session_load(session_name)
    load = await manager.get_session_load(session_name)
    assert load == 1
    
    # Decrement again
    await manager.decrement_session_load(session_name)
    load = await manager.get_session_load(session_name)
    assert load == 0
    
    # Decrement below 0 should stay at 0
    await manager.decrement_session_load(session_name)
    load = await manager.get_session_load(session_name)
    assert load == 0


@pytest.mark.asyncio
async def test_round_robin_session_selection(manager_with_sessions):
    """Test round-robin session selection"""
    manager = manager_with_sessions
    
    # Get sessions in round-robin order
    selected_sessions = []
    for _ in range(6):  # Get 6 sessions (2 full rounds)
        session_name = manager._get_session_round_robin()
        assert session_name is not None
        selected_sessions.append(session_name)
    
    # Check that sessions are selected in round-robin order
    # Should cycle through session_0, session_1, session_2, session_0, session_1, session_2
    expected = ["session_0", "session_1", "session_2", "session_0", "session_1", "session_2"]
    assert selected_sessions == expected


@pytest.mark.asyncio
async def test_round_robin_skips_disconnected_sessions(manager_with_sessions):
    """Test that round-robin skips disconnected sessions"""
    manager = manager_with_sessions
    
    # Disconnect session_1
    manager.sessions["session_1"].is_connected = False
    
    # Get sessions in round-robin order
    selected_sessions = []
    for _ in range(4):
        session_name = manager._get_session_round_robin()
        assert session_name is not None
        selected_sessions.append(session_name)
    
    # Should only select session_0 and session_2 (skipping session_1)
    assert "session_1" not in selected_sessions
    assert all(s in ["session_0", "session_2"] for s in selected_sessions)


@pytest.mark.asyncio
async def test_least_loaded_session_selection(manager_with_sessions):
    """Test least-loaded session selection"""
    manager = manager_with_sessions
    
    # Set different loads for sessions
    await manager.increment_session_load("session_0")
    await manager.increment_session_load("session_0")  # load = 2
    await manager.increment_session_load("session_1")  # load = 1
    # session_2 has load = 0
    
    # Should select session_2 (lowest load)
    session_name = manager._get_session_least_loaded()
    assert session_name == "session_2"
    
    # Increase session_2 load
    await manager.increment_session_load("session_2")
    await manager.increment_session_load("session_2")  # load = 2
    
    # Now session_1 has lowest load (1)
    session_name = manager._get_session_least_loaded()
    assert session_name == "session_1"


@pytest.mark.asyncio
async def test_least_loaded_breaks_ties_with_round_robin(manager_with_sessions):
    """Test that least-loaded uses round-robin to break ties"""
    manager = manager_with_sessions
    
    # All sessions have load = 0 (tie)
    # Should use round-robin to break tie
    selected_sessions = []
    for _ in range(6):
        session_name = manager._get_session_least_loaded()
        assert session_name is not None
        selected_sessions.append(session_name)
    
    # Should cycle through all sessions
    assert "session_0" in selected_sessions
    assert "session_1" in selected_sessions
    assert "session_2" in selected_sessions


@pytest.mark.asyncio
async def test_least_loaded_skips_disconnected_sessions(manager_with_sessions):
    """Test that least-loaded skips disconnected sessions"""
    manager = manager_with_sessions
    
    # Disconnect session_1
    manager.sessions["session_1"].is_connected = False
    
    # Set loads
    await manager.increment_session_load("session_0")  # load = 1
    # session_2 has load = 0
    
    # Should select session_2 (lowest load among connected)
    session_name = manager._get_session_least_loaded()
    assert session_name == "session_2"
    
    # Even if session_1 has lower load, it should be skipped
    await manager.increment_session_load("session_2")
    await manager.increment_session_load("session_2")  # load = 2
    
    # Should still select session_0 (only connected option with lower load)
    session_name = manager._get_session_least_loaded()
    assert session_name == "session_0"


@pytest.mark.asyncio
async def test_get_available_session_round_robin_strategy(manager_with_sessions):
    """Test _get_available_session with round_robin strategy"""
    manager = manager_with_sessions
    manager.load_balancing_strategy = "round_robin"
    
    # Should use round-robin
    selected_sessions = []
    for _ in range(3):
        session_name = manager._get_available_session()
        assert session_name is not None
        selected_sessions.append(session_name)
    
    # Should cycle through sessions
    assert len(set(selected_sessions)) == 3  # All 3 sessions selected


@pytest.mark.asyncio
async def test_get_available_session_least_loaded_strategy(manager_with_sessions):
    """Test _get_available_session with least_loaded strategy"""
    manager = manager_with_sessions
    manager.load_balancing_strategy = "least_loaded"
    
    # Set different loads
    await manager.increment_session_load("session_0")
    await manager.increment_session_load("session_0")  # load = 2
    await manager.increment_session_load("session_1")  # load = 1
    # session_2 has load = 0
    
    # Should select session_2 (lowest load)
    session_name = manager._get_available_session()
    assert session_name == "session_2"


@pytest.mark.asyncio
async def test_no_available_sessions_returns_none(manager_with_sessions):
    """Test that selection returns None when no sessions available"""
    manager = manager_with_sessions
    
    # Disconnect all sessions
    for session in manager.sessions.values():
        session.is_connected = False
    
    # Both strategies should return None
    assert manager._get_session_round_robin() is None
    assert manager._get_session_least_loaded() is None
    assert manager._get_available_session() is None


@pytest.mark.asyncio
async def test_load_balancing_strategy_defaults_to_round_robin(manager_with_sessions):
    """Test that load balancing strategy defaults to round_robin"""
    manager = manager_with_sessions
    
    # Default should be round_robin
    assert manager.load_balancing_strategy == "round_robin"
    
    # _get_available_session should use round_robin by default
    session_name = manager._get_available_session()
    assert session_name is not None
