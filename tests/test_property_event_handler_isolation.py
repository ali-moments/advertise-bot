"""
Property-Based Test for Event Handler Isolation

**Feature: telegram-concurrency-fix, Property 3: Event handler isolation**

Tests that for any two sessions S1 and S2 both monitoring the same channel, 
an event in that channel should trigger both handlers independently, and an 
error in S1's handler should not affect S2's handler.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, AsyncMock, MagicMock
from telegram_manager.session import TelegramSession


# Strategy for generating number of sessions
num_sessions_strategy = st.integers(min_value=2, max_value=5)

# Strategy for generating error scenarios
error_scenario_strategy = st.sampled_from([
    'no_error',
    'first_session_error',
    'middle_session_error',
    'last_session_error',
    'multiple_errors'
])


@pytest.mark.asyncio
@given(
    num_sessions=num_sessions_strategy,
    error_scenario=error_scenario_strategy
)
@settings(max_examples=100, deadline=None)
async def test_property_event_handler_isolation(num_sessions, error_scenario):
    """
    Property Test: Event handler isolation
    
    For any two sessions S1 and S2 both monitoring the same channel, an event 
    in that channel should trigger both handlers independently, and an error 
    in S1's handler should not affect S2's handler.
    
    Test Strategy:
    1. Create multiple sessions monitoring the same channel
    2. Setup isolated event handlers for each session
    3. Simulate an event that triggers all handlers
    4. Inject errors into specific handlers based on error_scenario
    5. Verify all handlers execute independently
    6. Verify errors in one handler don't crash others
    7. Verify error counts are tracked per session
    """
    # Skip if we have too few sessions
    assume(num_sessions >= 2)
    
    # Create multiple sessions
    sessions = []
    for i in range(num_sessions):
        session = TelegramSession(
            session_file=f'test_isolation_{i}.session',
            api_id=12345,
            api_hash='test_hash'
        )
        session.is_connected = True
        sessions.append(session)
    
    # Track which handlers were called and their results
    handler_calls = []
    handler_errors = []
    call_lock = asyncio.Lock()
    
    # Determine which sessions should error based on scenario
    error_sessions = set()
    if error_scenario == 'first_session_error':
        error_sessions.add(0)
    elif error_scenario == 'middle_session_error' and num_sessions > 2:
        error_sessions.add(num_sessions // 2)
    elif error_scenario == 'last_session_error':
        error_sessions.add(num_sessions - 1)
    elif error_scenario == 'multiple_errors':
        # Add errors to half the sessions
        for i in range(0, num_sessions, 2):
            error_sessions.add(i)
    
    # Setup mock event handlers for each session
    for i, session in enumerate(sessions):
        # Mock the Telegram client
        session.client = Mock()
        
        # Track handler function for this session
        handler_func = None
        
        def make_mock_on(session_idx):
            """Create a mock 'on' decorator for this specific session"""
            def mock_on(event_type):
                def decorator(func):
                    nonlocal handler_func
                    handler_func = func
                    return func
                return decorator
            return mock_on
        
        session.client.on = make_mock_on(i)
        session.client.remove_event_handler = Mock()
        
        # Setup event handler
        await session._setup_event_handler()
        
        # Store the handler function for later invocation
        session._test_handler_func = handler_func
    
    # Create a mock event
    mock_event = Mock()
    mock_event.out = False
    
    # Create mock chat that all sessions are monitoring
    mock_chat = Mock()
    mock_chat.username = 'test_channel'
    mock_chat.id = 12345
    
    # Setup monitoring targets for all sessions (same channel)
    from telegram_manager.config import MonitoringTarget
    for session in sessions:
        target = MonitoringTarget(
            chat_id='test_channel',
            reaction='👍',
            cooldown=0.1
        )
        session.monitoring_targets['test_channel'] = target
    
    # Configure mock event behavior based on error scenario
    async def make_get_chat(session_idx):
        """Create get_chat function that may error for specific sessions"""
        async def get_chat():
            async with call_lock:
                handler_calls.append({
                    'session_idx': session_idx,
                    'timestamp': time.time(),
                    'event': 'handler_called'
                })
            
            # Inject error if this session should error
            if session_idx in error_sessions:
                async with call_lock:
                    handler_errors.append({
                        'session_idx': session_idx,
                        'timestamp': time.time(),
                        'error': 'Simulated error'
                    })
                raise Exception(f"Simulated error in session {session_idx}")
            
            return mock_chat
        return get_chat
    
    # Trigger all handlers concurrently
    tasks = []
    for i, session in enumerate(sessions):
        # Create a new mock event for each session to avoid shared state
        event_copy = Mock()
        event_copy.out = False
        event_copy.get_chat = await make_get_chat(i)
        event_copy.message = Mock()
        event_copy.message.id = 999
        
        # Call the handler
        task = asyncio.create_task(session._test_handler_func(event_copy))
        tasks.append(task)
    
    # Wait for all handlers to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Small delay to ensure all async operations complete
    await asyncio.sleep(0.1)
    
    # Property Verification 1: All handlers should have been called
    assert len(handler_calls) == num_sessions, \
        f"Expected {num_sessions} handler calls, got {len(handler_calls)}. " \
        f"Handlers: {handler_calls}"
    
    # Property Verification 2: Each session should have been called exactly once
    session_indices = [call['session_idx'] for call in handler_calls]
    assert len(set(session_indices)) == num_sessions, \
        f"Not all sessions were called. Called sessions: {session_indices}"
    
    # Property Verification 3: Errors should only occur in expected sessions
    error_indices = [err['session_idx'] for err in handler_errors]
    assert set(error_indices) == error_sessions, \
        f"Expected errors in sessions {error_sessions}, got errors in {set(error_indices)}"
    
    # Property Verification 4: Error counts should be tracked per session
    for i, session in enumerate(sessions):
        if i in error_sessions:
            assert session._handler_error_count > 0, \
                f"Session {i} should have error count > 0, got {session._handler_error_count}"
        else:
            assert session._handler_error_count == 0, \
                f"Session {i} should have error count = 0, got {session._handler_error_count}"
    
    # Property Verification 5: All handlers completed (no crashes)
    # If any handler crashed the event loop, we wouldn't reach here
    assert len(handler_calls) == num_sessions, \
        "All handlers should complete without crashing the event loop"
    
    # Cleanup
    for session in sessions:
        session.is_connected = False


@pytest.mark.asyncio
async def test_event_handler_isolation_simple_example():
    """
    Simple example test to verify basic event handler isolation
    
    This is a concrete example that demonstrates the property with specific values.
    """
    # Create two sessions
    session1 = TelegramSession('test_session1.session', 12345, 'test_hash')
    session2 = TelegramSession('test_session2.session', 12345, 'test_hash')
    
    session1.is_connected = True
    session2.is_connected = True
    
    # Track handler calls
    handler1_called = []
    handler2_called = []
    
    # Setup mock clients
    for session, handler_list in [(session1, handler1_called), (session2, handler2_called)]:
        session.client = Mock()
        
        handler_func = None
        def make_mock_on(calls_list):
            def mock_on(event_type):
                def decorator(func):
                    nonlocal handler_func
                    handler_func = func
                    # Store reference to track calls
                    func._calls_list = calls_list
                    return func
                return decorator
            return mock_on
        
        session.client.on = make_mock_on(handler_list)
        session.client.remove_event_handler = Mock()
        
        await session._setup_event_handler()
        session._test_handler = handler_func
    
    # Setup monitoring targets
    from telegram_manager.config import MonitoringTarget
    target = MonitoringTarget(chat_id='test_channel', reaction='👍', cooldown=0.1)
    session1.monitoring_targets['test_channel'] = target
    session2.monitoring_targets['test_channel'] = target
    
    # Create mock event
    mock_chat = Mock()
    mock_chat.username = 'test_channel'
    mock_chat.id = 12345
    
    # Session 1 event (no error)
    event1 = Mock()
    event1.out = False
    event1.get_chat = AsyncMock(return_value=mock_chat)
    event1.message = Mock()
    event1.message.id = 999
    
    # Session 2 event (with error)
    event2 = Mock()
    event2.out = False
    event2.get_chat = AsyncMock(side_effect=Exception("Test error"))
    event2.message = Mock()
    event2.message.id = 999
    
    # Call both handlers
    await session1._test_handler(event1)
    await session2._test_handler(event2)
    
    # Verify session 1 succeeded (no error count)
    assert session1._handler_error_count == 0, \
        "Session 1 should have no errors"
    
    # Verify session 2 had error but didn't crash
    assert session2._handler_error_count == 1, \
        "Session 2 should have 1 error"
    
    # Both handlers should have been called
    assert event1.get_chat.called, "Session 1 handler should be called"
    assert event2.get_chat.called, "Session 2 handler should be called"


@pytest.mark.asyncio
async def test_event_handler_removal_isolation():
    """
    Test that removing one session's handler doesn't affect other sessions
    
    Verifies handler removal isolation.
    """
    # Create three sessions
    sessions = []
    for i in range(3):
        session = TelegramSession(f'test_removal_{i}.session', 12345, 'test_hash')
        session.is_connected = True
        session.client = Mock()
        
        handler_func = None
        def mock_on(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator
        
        session.client.on = mock_on
        session.client.remove_event_handler = Mock()
        
        await session._setup_event_handler()
        session._test_handler = handler_func
        sessions.append(session)
    
    # Verify all sessions have handlers
    for session in sessions:
        assert session._event_handler is not None, "All sessions should have handlers"
    
    # Stop monitoring on session 1 (should remove its handler)
    await sessions[1].stop_monitoring()
    
    # Verify session 1 handler was removed
    assert sessions[1]._event_handler is None, "Session 1 handler should be removed"
    sessions[1].client.remove_event_handler.assert_called_once()
    
    # Verify other sessions still have handlers
    assert sessions[0]._event_handler is not None, "Session 0 handler should still exist"
    assert sessions[2]._event_handler is not None, "Session 2 handler should still exist"
    
    # Verify other sessions' remove_event_handler was not called
    assert not sessions[0].client.remove_event_handler.called, \
        "Session 0 remove_event_handler should not be called"
    assert not sessions[2].client.remove_event_handler.called, \
        "Session 2 remove_event_handler should not be called"


@pytest.mark.asyncio
async def test_concurrent_handler_setup_isolation():
    """
    Test that concurrent handler setup operations are isolated
    
    Verifies that setting up handlers concurrently doesn't cause interference.
    """
    # Create multiple sessions
    num_sessions = 5
    sessions = []
    
    for i in range(num_sessions):
        session = TelegramSession(f'test_concurrent_{i}.session', 12345, 'test_hash')
        session.is_connected = True
        session.client = Mock()
        
        def mock_on(event_type):
            def decorator(func):
                return func
            return decorator
        
        session.client.on = mock_on
        session.client.remove_event_handler = Mock()
        sessions.append(session)
    
    # Setup handlers concurrently
    setup_tasks = [session._setup_event_handler() for session in sessions]
    await asyncio.gather(*setup_tasks)
    
    # Verify all sessions have unique handlers
    handlers = [session._event_handler for session in sessions]
    
    # All handlers should exist
    assert all(h is not None for h in handlers), "All sessions should have handlers"
    
    # All handlers should be unique (different function objects)
    handler_ids = [id(h) for h in handlers]
    assert len(set(handler_ids)) == num_sessions, \
        f"All handlers should be unique, got {len(set(handler_ids))} unique out of {num_sessions}"


@pytest.mark.asyncio
async def test_handler_error_tracking_independence():
    """
    Test that error tracking is independent per session
    
    Verifies that error counts don't leak between sessions.
    """
    # Create two sessions
    session1 = TelegramSession('test_error_track1.session', 12345, 'test_hash')
    session2 = TelegramSession('test_error_track2.session', 12345, 'test_hash')
    
    session1.is_connected = True
    session2.is_connected = True
    
    # Setup mock clients
    for session in [session1, session2]:
        session.client = Mock()
        
        handler_func = None
        def mock_on(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator
        
        session.client.on = mock_on
        session.client.remove_event_handler = Mock()
        
        await session._setup_event_handler()
        session._test_handler = handler_func
    
    # Setup monitoring
    from telegram_manager.config import MonitoringTarget
    target = MonitoringTarget(chat_id='test_channel', reaction='👍', cooldown=0.1)
    session1.monitoring_targets['test_channel'] = target
    session2.monitoring_targets['test_channel'] = target
    
    # Create error event
    error_event = Mock()
    error_event.out = False
    error_event.get_chat = AsyncMock(side_effect=Exception("Test error"))
    
    # Trigger errors in session1 multiple times
    for _ in range(3):
        await session1._test_handler(error_event)
    
    # Trigger errors in session2 once
    await session2._test_handler(error_event)
    
    # Verify error counts are independent
    assert session1._handler_error_count == 3, \
        f"Session 1 should have 3 errors, got {session1._handler_error_count}"
    assert session2._handler_error_count == 1, \
        f"Session 2 should have 1 error, got {session2._handler_error_count}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
