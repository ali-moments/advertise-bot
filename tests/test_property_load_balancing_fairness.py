"""
Property-Based Test for Load Balancing Fairness

**Feature: telegram-concurrency-fix, Property 10: Load balancing fairness**

Tests that for any scraping request when multiple sessions are available, the system 
should select a session using the configured strategy (round-robin or least-loaded) 
to distribute load evenly across sessions.

**Validates: Requirements 2.2**
"""

import asyncio
import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.session import TelegramSession


# Strategy for generating number of sessions
session_counts = st.integers(min_value=2, max_value=10)

# Strategy for generating number of operations
operation_counts = st.integers(min_value=5, max_value=30)


@st.composite
def load_balancing_scenario(draw):
    """Generate a load balancing test scenario"""
    num_sessions = draw(st.integers(min_value=2, max_value=8))
    num_operations = draw(st.integers(min_value=5, max_value=25))
    strategy = draw(st.sampled_from(['round_robin', 'least_loaded']))
    
    return {
        'num_sessions': num_sessions,
        'num_operations': num_operations,
        'strategy': strategy
    }


@pytest.mark.asyncio
@given(scenario=load_balancing_scenario())
@settings(max_examples=100, deadline=None)
async def test_property_load_balancing_fairness(scenario):
    """
    Property Test: Load balancing fairness
    
    For any scraping request when multiple sessions are available, the system 
    should select a session using the configured strategy to distribute load 
    evenly across sessions.
    
    Test Strategy:
    1. Create a manager with N sessions
    2. Configure load balancing strategy (round-robin or least-loaded)
    3. Submit M operations
    4. Track which session handles each operation
    5. Verify fair distribution according to strategy
    """
    num_sessions = scenario['num_sessions']
    num_operations = scenario['num_operations']
    strategy = scenario['strategy']
    
    # Ensure we have enough operations to test distribution
    assume(num_operations >= num_sessions)
    
    # Create a test manager
    manager = TelegramSessionManager(max_concurrent_operations=20)
    manager.load_balancing_strategy = strategy
    
    # Create mock sessions
    for i in range(num_sessions):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize session load
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Track session selection
    selected_sessions = []
    
    # Simulate operations by calling _get_available_session
    for _ in range(num_operations):
        session_name = manager._get_available_session()
        assert session_name is not None, "Should always get a session when sessions are available"
        selected_sessions.append(session_name)
        
        # Simulate operation by incrementing load
        await manager.increment_session_load(session_name)
        
        # Small delay to simulate operation
        await asyncio.sleep(0.001)
        
        # Decrement load after "operation"
        await manager.decrement_session_load(session_name)
    
    # Verify fairness based on strategy
    session_counts = {f"session_{i}": 0 for i in range(num_sessions)}
    for session_name in selected_sessions:
        session_counts[session_name] += 1
    
    if strategy == 'round_robin':
        # For round-robin, verify distribution is relatively even
        # Each session should get approximately num_operations / num_sessions operations
        expected_per_session = num_operations / num_sessions
        
        for session_name, count in session_counts.items():
            # Allow some variance due to rounding
            # Each session should get within ±1 of the expected count
            assert abs(count - expected_per_session) <= 1, \
                f"Round-robin fairness violated for {session_name}: " \
                f"got {count} operations, expected ~{expected_per_session}. " \
                f"Distribution: {session_counts}"
    
    elif strategy == 'least_loaded':
        # For least-loaded, verify that load was balanced
        # Since we increment and decrement immediately, all sessions should be used
        # and distribution should be relatively even
        min_count = min(session_counts.values())
        max_count = max(session_counts.values())
        
        # The difference between most and least used sessions should be small
        # Since operations complete immediately in this test, distribution should be very even
        assert max_count - min_count <= 1, \
            f"Least-loaded fairness violated: " \
            f"max={max_count}, min={min_count}, diff={max_count - min_count}. " \
            f"Distribution: {session_counts}"
    
    # Verify all sessions were used (fairness means everyone gets work)
    for session_name, count in session_counts.items():
        assert count > 0, \
            f"Session {session_name} was never selected, indicating unfair distribution. " \
            f"Distribution: {session_counts}"


@pytest.mark.asyncio
@given(
    num_sessions=session_counts,
    num_operations=operation_counts
)
@settings(max_examples=100, deadline=None)
async def test_property_round_robin_cycles_through_all_sessions(num_sessions, num_operations):
    """
    Property Test: Round-robin cycles through all sessions
    
    For round-robin strategy, verify that sessions are selected in a cyclic pattern.
    """
    assume(num_sessions >= 2)
    assume(num_operations >= num_sessions * 2)  # At least 2 full cycles
    
    manager = TelegramSessionManager(max_concurrent_operations=20)
    manager.load_balancing_strategy = 'round_robin'
    
    # Create mock sessions
    for i in range(num_sessions):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Get session selections
    selected_sessions = []
    for _ in range(num_operations):
        session_name = manager._get_available_session()
        selected_sessions.append(session_name)
    
    # Verify cyclic pattern
    # Check that the pattern repeats every num_sessions selections
    for i in range(num_operations - num_sessions):
        current_session = selected_sessions[i]
        next_cycle_session = selected_sessions[i + num_sessions]
        
        assert current_session == next_cycle_session, \
            f"Round-robin cycle broken at position {i}: " \
            f"expected {current_session} to repeat after {num_sessions} selections, " \
            f"but got {next_cycle_session}. Selections: {selected_sessions}"


@pytest.mark.asyncio
@given(
    num_sessions=session_counts,
    num_operations=operation_counts
)
@settings(max_examples=100, deadline=None)
async def test_property_least_loaded_selects_minimum_load(num_sessions, num_operations):
    """
    Property Test: Least-loaded selects session with minimum load
    
    For least-loaded strategy, verify that the session with the lowest load is selected.
    """
    assume(num_sessions >= 2)
    assume(num_operations >= 5)
    
    manager = TelegramSessionManager(max_concurrent_operations=20)
    manager.load_balancing_strategy = 'least_loaded'
    
    # Create mock sessions
    for i in range(num_sessions):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Simulate operations with varying loads
    for op_idx in range(num_operations):
        # Get current loads
        current_loads = {}
        async with manager.metrics_lock:
            for session_name in manager.sessions.keys():
                current_loads[session_name] = manager.session_load[session_name]
        
        # Find minimum load
        min_load = min(current_loads.values())
        sessions_with_min_load = [s for s, load in current_loads.items() if load == min_load]
        
        # Select session
        selected_session = manager._get_available_session()
        
        # Verify selected session has minimum load
        assert selected_session in sessions_with_min_load, \
            f"Least-loaded strategy violated at operation {op_idx}: " \
            f"selected {selected_session} with load {current_loads[selected_session]}, " \
            f"but minimum load is {min_load}. " \
            f"Sessions with min load: {sessions_with_min_load}. " \
            f"All loads: {current_loads}"
        
        # Increment load for selected session
        await manager.increment_session_load(selected_session)
        
        # Randomly decrement some session loads to create variation
        if op_idx % 3 == 0 and op_idx > 0:
            # Pick a random session to "complete" an operation
            import random
            session_to_decrement = random.choice(list(manager.sessions.keys()))
            await manager.decrement_session_load(session_to_decrement)


@pytest.mark.asyncio
async def test_load_balancing_fairness_simple_round_robin():
    """
    Simple example test for round-robin load balancing
    
    Verifies that round-robin distributes operations evenly across sessions.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    manager.load_balancing_strategy = 'round_robin'
    
    # Create 3 sessions
    for i in range(3):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Select 9 sessions (3 full cycles)
    selected = []
    for _ in range(9):
        session_name = manager._get_available_session()
        selected.append(session_name)
    
    # Verify round-robin pattern
    expected = ['session_0', 'session_1', 'session_2'] * 3
    assert selected == expected, \
        f"Expected round-robin pattern {expected}, got {selected}"


@pytest.mark.asyncio
async def test_load_balancing_fairness_simple_least_loaded():
    """
    Simple example test for least-loaded load balancing
    
    Verifies that least-loaded selects the session with minimum load.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    manager.load_balancing_strategy = 'least_loaded'
    
    # Create 3 sessions
    for i in range(3):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Set different loads
    await manager.increment_session_load('session_0')
    await manager.increment_session_load('session_0')  # load = 2
    await manager.increment_session_load('session_1')  # load = 1
    # session_2 has load = 0
    
    # Should select session_2 (lowest load)
    selected = manager._get_available_session()
    assert selected == 'session_2', \
        f"Expected least-loaded to select session_2, got {selected}"
    
    # Increase session_2 load
    await manager.increment_session_load('session_2')
    await manager.increment_session_load('session_2')  # load = 2
    
    # Now session_1 has lowest load (1)
    selected = manager._get_available_session()
    assert selected == 'session_1', \
        f"Expected least-loaded to select session_1, got {selected}"


@pytest.mark.asyncio
async def test_load_balancing_skips_disconnected_sessions():
    """
    Test that load balancing skips disconnected sessions
    
    Verifies that both strategies only select connected sessions.
    """
    for strategy in ['round_robin', 'least_loaded']:
        manager = TelegramSessionManager(max_concurrent_operations=10)
        manager.load_balancing_strategy = strategy
        
        # Create 3 sessions, disconnect one
        for i in range(3):
            session_name = f"session_{i}"
            mock_session = MagicMock(spec=TelegramSession)
            mock_session.is_connected = (i != 1)  # Disconnect session_1
            mock_session.session_file = f"test_{i}.session"
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
            
            async with manager.metrics_lock:
                manager.session_load[session_name] = 0
        
        # Select sessions multiple times
        selected = []
        for _ in range(6):
            session_name = manager._get_available_session()
            selected.append(session_name)
        
        # Verify session_1 was never selected
        assert 'session_1' not in selected, \
            f"Strategy {strategy} selected disconnected session_1. Selected: {selected}"
        
        # Verify only session_0 and session_2 were selected
        assert all(s in ['session_0', 'session_2'] for s in selected), \
            f"Strategy {strategy} selected unexpected sessions. Selected: {selected}"


@pytest.mark.asyncio
async def test_load_balancing_with_concurrent_operations():
    """
    Test load balancing fairness with actual concurrent operations
    
    Verifies that load balancing works correctly when operations run concurrently.
    """
    manager = TelegramSessionManager(max_concurrent_operations=20)
    manager.load_balancing_strategy = 'round_robin'
    
    # Create 4 sessions
    for i in range(4):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Track session usage
    session_usage = {f"session_{i}": 0 for i in range(4)}
    usage_lock = asyncio.Lock()
    
    async def mock_operation():
        """Mock operation that uses load balancing"""
        # Select session
        session_name = manager._get_available_session()
        
        # Track usage
        async with usage_lock:
            session_usage[session_name] += 1
        
        # Simulate operation
        await manager.increment_session_load(session_name)
        await asyncio.sleep(0.01)
        await manager.decrement_session_load(session_name)
    
    # Run 20 operations concurrently
    tasks = [asyncio.create_task(mock_operation()) for _ in range(20)]
    await asyncio.gather(*tasks)
    
    # Verify fair distribution (each session should get 5 operations)
    for session_name, count in session_usage.items():
        assert count == 5, \
            f"Unfair distribution: {session_name} got {count} operations, expected 5. " \
            f"Distribution: {session_usage}"


@pytest.mark.asyncio
async def test_load_balancing_returns_none_when_no_sessions():
    """
    Test that load balancing returns None when no sessions are available
    
    Verifies graceful handling of empty session pool.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Test both strategies with no sessions
    for strategy in ['round_robin', 'least_loaded']:
        manager.load_balancing_strategy = strategy
        
        result = manager._get_available_session()
        assert result is None, \
            f"Strategy {strategy} should return None when no sessions available, got {result}"


@pytest.mark.asyncio
async def test_load_balancing_returns_none_when_all_disconnected():
    """
    Test that load balancing returns None when all sessions are disconnected
    
    Verifies graceful handling when no connected sessions exist.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create sessions but disconnect all
    for i in range(3):
        session_name = f"session_{i}"
        mock_session = MagicMock(spec=TelegramSession)
        mock_session.is_connected = False
        mock_session.session_file = f"test_{i}.session"
        
        manager.sessions[session_name] = mock_session
        manager.session_locks[session_name] = asyncio.Lock()
        
        async with manager.metrics_lock:
            manager.session_load[session_name] = 0
    
    # Test both strategies
    for strategy in ['round_robin', 'least_loaded']:
        manager.load_balancing_strategy = strategy
        
        result = manager._get_available_session()
        assert result is None, \
            f"Strategy {strategy} should return None when all sessions disconnected, got {result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
