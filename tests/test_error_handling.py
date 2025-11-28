"""
Tests for comprehensive error handling (Task 11)
Tests Requirements 7.1, 7.2, 1.4
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager


@pytest.mark.asyncio
async def test_lock_release_on_error_in_submit_operation():
    """
    Test that locks are released when an error occurs in _submit_operation
    Requirement 7.1: Lock release on error paths
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the operation to raise an error
    async def failing_operation():
        raise ValueError("Test error")
    
    # Verify lock is not held initially
    assert not session.operation_lock.locked()
    
    # Try to execute operation that will fail
    with pytest.raises(ValueError, match="Test error"):
        await session._submit_operation('scraping', failing_operation)
    
    # Verify lock is released after error
    assert not session.operation_lock.locked()
    assert session.current_operation is None
    assert session.operation_start_time is None


@pytest.mark.asyncio
async def test_queue_overflow_handling():
    """
    Test that queue overflow is properly handled
    Requirement 1.4: Queue overflow handling
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Fill the queue to capacity (100 items)
    async def slow_operation():
        await asyncio.sleep(10)  # Long operation to keep queue full
    
    # Acquire the operation lock to force queuing
    await session.operation_lock.acquire()
    
    try:
        # Fill queue to max capacity
        tasks = []
        for i in range(100):
            task = asyncio.create_task(
                session._submit_operation('scraping', slow_operation)
            )
            tasks.append(task)
            await asyncio.sleep(0.01)  # Small delay to allow queue to fill
        
        # Wait a bit for queue to fill
        await asyncio.sleep(0.5)
        
        # Try to add one more operation - should fail with queue full error
        with pytest.raises(Exception, match="queue is full"):
            await session._submit_operation('scraping', slow_operation)
        
        # Cancel all pending tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        
    finally:
        session.operation_lock.release()


@pytest.mark.asyncio
async def test_queue_depth_query():
    """
    Test queue depth query method
    Requirement 1.4: Provide queue depth query method
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Initially queue should be empty
    assert session.get_queue_depth() == 0
    
    # Get queue status
    status = session.get_queue_status()
    assert status['queue_depth'] == 0
    assert status['max_queue_size'] == 100
    assert status['queue_utilization'] == 0.0
    assert status['is_full'] is False


@pytest.mark.asyncio
async def test_error_logging_includes_operation_context():
    """
    Test that error logging includes operation context
    Requirement 7.1: Log operation context on errors
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock logger to capture log messages
    with patch.object(session, 'logger') as mock_logger:
        async def failing_operation():
            raise RuntimeError("Test error")
        
        # Execute operation that will fail
        with pytest.raises(RuntimeError):
            await session._submit_operation('scraping', failing_operation)
        
        # Verify error was logged with context
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        assert 'scraping' in error_call
        assert 'Test error' in error_call
        assert 'session' in error_call


@pytest.mark.asyncio
async def test_lock_timeout_logging_includes_lock_state():
    """
    Test that lock timeout logging includes lock state
    Requirement 7.3: Log lock state on timeouts
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Acquire lock to cause timeout
    await session.operation_lock.acquire()
    
    try:
        # Mock logger to capture log messages
        with patch.object(session, 'logger') as mock_logger:
            # Try to acquire lock with very short timeout
            result = await session._acquire_lock_with_timeout(
                session.operation_lock,
                timeout=0.1,
                lock_name="test_lock"
            )
            
            # Should timeout
            assert result is False
            
            # Verify warning was logged with lock state
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert 'TIMEOUT' in warning_call
            assert 'test_lock' in warning_call
            assert 'Lock state:' in warning_call
            
    finally:
        session.operation_lock.release()


@pytest.mark.asyncio
async def test_retry_logging_includes_context():
    """
    Test that retry logging includes full context
    Requirement 7.3: Log retry attempts with context
    """
    manager = TelegramSessionManager()
    
    # Mock logger to capture log messages
    with patch.object(manager, 'logger') as mock_logger:
        attempt_count = [0]
        
        async def flaky_operation():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ConnectionError("Transient error")
            return "success"
        
        # Execute operation with retry
        result = await manager._execute_with_retry(
            'scraping',
            flaky_operation
        )
        
        assert result == "success"
        
        # Verify retry was logged with context
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        assert any('scraping' in call and 'failed' in call for call in warning_calls)
        assert any('error_type' in call for call in warning_calls)
        assert any('is_transient' in call for call in warning_calls)


@pytest.mark.asyncio
async def test_semaphore_release_on_error():
    """
    Test that semaphores are released when errors occur
    Requirement 7.1: Lock release on all error paths
    """
    manager = TelegramSessionManager()
    
    # Create a mock session
    mock_session = Mock()
    mock_session.is_connected = True
    mock_session.scrape_group_members = AsyncMock(side_effect=RuntimeError("Test error"))
    
    manager.sessions = {'test_session': mock_session}
    manager.session_locks = {'test_session': asyncio.Lock()}
    manager.session_load = {'test_session': 0}
    
    # Get initial semaphore count
    initial_count = manager.scrape_semaphore._value
    
    # Execute operation that will fail
    result = await manager.scrape_group_members_random_session('test_group')
    
    # Verify operation failed
    assert result['success'] is False
    
    # Verify semaphore was released (count should be back to initial)
    assert manager.scrape_semaphore._value == initial_count
    
    # Verify session load was decremented
    assert manager.session_load['test_session'] == 0


@pytest.mark.asyncio
async def test_nested_lock_release_on_error():
    """
    Test that nested locks are properly released on error
    Requirement 7.1: Lock release on all error paths
    """
    manager = TelegramSessionManager()
    
    # Create a mock session
    mock_session = Mock()
    mock_session.is_connected = True
    mock_session.scrape_group_members = AsyncMock(side_effect=RuntimeError("Test error"))
    
    manager.sessions = {'test_session': mock_session}
    manager.session_locks = {'test_session': asyncio.Lock()}
    manager.session_load = {'test_session': 0}
    
    # Verify locks are not held initially
    assert not manager.session_locks['test_session'].locked()
    assert manager.scrape_semaphore._value == 5  # Initial value
    
    # Execute operation that will fail
    result = await manager.scrape_group_members_random_session('test_group')
    
    # Verify operation failed
    assert result['success'] is False
    
    # Verify all locks/semaphores are released
    assert not manager.session_locks['test_session'].locked()
    assert manager.scrape_semaphore._value == 5
    assert manager.session_load['test_session'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
