"""
Tests for monitoring isolation enhancements (Task 4)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram_manager.session import TelegramSession


@pytest.mark.asyncio
async def test_handler_lock_prevents_concurrent_setup():
    """Test that handler lock prevents concurrent handler setup/teardown"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.client.on = Mock(return_value=lambda f: f)
    session.client.remove_event_handler = Mock()
    session.is_connected = True
    
    # Track if operations overlap
    setup_started = []
    setup_finished = []
    
    async def slow_setup():
        """Simulate slow handler setup"""
        async with session._handler_lock:
            setup_started.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate work
            setup_finished.append(asyncio.get_event_loop().time())
    
    # Start two setup operations concurrently
    await asyncio.gather(slow_setup(), slow_setup())
    
    # Verify they didn't overlap (second started after first finished)
    assert len(setup_started) == 2
    assert len(setup_finished) == 2
    assert setup_started[1] >= setup_finished[0], "Operations should not overlap"


@pytest.mark.asyncio
async def test_event_handler_error_tracking():
    """Test that event handler errors are tracked per session"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.is_connected = True
    
    # Mock the client.on decorator
    handler_func = None
    def mock_on(event_type):
        def decorator(func):
            nonlocal handler_func
            handler_func = func
            return func
        return decorator
    
    session.client.on = mock_on
    session.client.remove_event_handler = Mock()
    
    # Setup event handler
    await session._setup_event_handler()
    
    # Verify error count starts at 0
    assert session._handler_error_count == 0
    
    # Create a mock event that will cause an error
    mock_event = Mock()
    mock_event.out = False
    mock_event.get_chat = AsyncMock(side_effect=Exception("Test error"))
    
    # Call the handler (should catch error and increment count)
    await handler_func(mock_event)
    
    # Verify error was tracked
    assert session._handler_error_count == 1
    
    # Call again to verify count increments
    await handler_func(mock_event)
    assert session._handler_error_count == 2


@pytest.mark.asyncio
async def test_monitoring_task_cancellation():
    """Test that monitoring task is properly cancelled within 5 seconds"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.client.remove_event_handler = Mock()
    session.is_connected = True
    
    # Create a long-running monitoring task
    async def long_running_task():
        try:
            await asyncio.sleep(100)  # Very long sleep
        except asyncio.CancelledError:
            # Task was cancelled as expected
            raise
    
    session.monitoring_task = asyncio.create_task(long_running_task())
    session._event_handler = Mock()
    
    # Stop monitoring (should cancel task within 5 seconds)
    start_time = asyncio.get_event_loop().time()
    await session.stop_monitoring()
    end_time = asyncio.get_event_loop().time()
    
    # Verify task was cancelled
    assert session.monitoring_task is None
    
    # Verify it completed within 5 seconds
    elapsed = end_time - start_time
    assert elapsed < 5.0, f"Monitoring task cancellation took {elapsed}s, should be < 5s"


@pytest.mark.asyncio
async def test_stop_monitoring_with_handler_lock():
    """Test that stop_monitoring uses handler lock"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.client.remove_event_handler = Mock()
    session.is_connected = True
    session._event_handler = Mock()
    
    # Acquire the handler lock in another task
    lock_acquired = asyncio.Event()
    lock_released = asyncio.Event()
    
    async def hold_lock():
        async with session._handler_lock:
            lock_acquired.set()
            await lock_released.wait()
    
    # Start task that holds the lock
    holder_task = asyncio.create_task(hold_lock())
    await lock_acquired.wait()
    
    # Try to stop monitoring (should wait for lock)
    stop_task = asyncio.create_task(session.stop_monitoring())
    
    # Give it a moment to try acquiring the lock
    await asyncio.sleep(0.1)
    
    # Verify stop_monitoring is waiting (not done yet)
    assert not stop_task.done(), "stop_monitoring should wait for handler lock"
    
    # Release the lock
    lock_released.set()
    await holder_task
    
    # Now stop_monitoring should complete
    await stop_task
    assert stop_task.done(), "stop_monitoring should complete after lock is released"


@pytest.mark.asyncio
async def test_handler_error_does_not_crash_event_loop():
    """Test that handler errors don't crash the event loop"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.is_connected = True
    
    # Mock the client.on decorator
    handler_func = None
    def mock_on(event_type):
        def decorator(func):
            nonlocal handler_func
            handler_func = func
            return func
        return decorator
    
    session.client.on = mock_on
    session.client.remove_event_handler = Mock()
    
    # Setup event handler
    await session._setup_event_handler()
    
    # Create a mock event that will cause an error
    mock_event = Mock()
    mock_event.out = False
    mock_event.get_chat = AsyncMock(side_effect=Exception("Test error"))
    
    # Call the handler multiple times - should not raise
    try:
        await handler_func(mock_event)
        await handler_func(mock_event)
        await handler_func(mock_event)
    except Exception as e:
        pytest.fail(f"Handler should not raise exceptions: {e}")
    
    # Verify errors were tracked
    assert session._handler_error_count == 3


@pytest.mark.asyncio
async def test_setup_event_handler_removes_existing_handler():
    """Test that setting up a new handler removes the existing one"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.client = Mock()
    session.is_connected = True
    
    # Mock the client.on decorator
    def mock_on(event_type):
        def decorator(func):
            return func
        return decorator
    
    session.client.on = mock_on
    session.client.remove_event_handler = Mock()
    
    # Setup first handler
    await session._setup_event_handler()
    first_handler = session._event_handler
    assert first_handler is not None
    
    # Setup second handler
    await session._setup_event_handler()
    second_handler = session._event_handler
    
    # Verify old handler was removed
    session.client.remove_event_handler.assert_called_once_with(first_handler)
    
    # Verify new handler is different
    assert second_handler is not None
    assert second_handler != first_handler


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
