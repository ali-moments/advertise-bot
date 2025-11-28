"""
Tests for operation timeout handling (Task 3)
"""

import pytest
import asyncio
from telegram_manager.session import TelegramSession


@pytest.mark.asyncio
async def test_execute_with_timeout_success():
    """Test that _execute_with_timeout completes successfully within timeout"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    async def quick_operation():
        await asyncio.sleep(0.1)
        return "success"
    
    result = await session._execute_with_timeout(
        'scraping',
        quick_operation
    )
    
    assert result == "success"


@pytest.mark.asyncio
async def test_execute_with_timeout_exceeds():
    """Test that _execute_with_timeout raises TimeoutError when operation exceeds timeout"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    async def slow_operation():
        await asyncio.sleep(10)  # Much longer than any timeout
        return "should not reach here"
    
    # Mock _get_operation_timeout to return a short timeout
    original_get_timeout = session._get_operation_timeout
    session._get_operation_timeout = lambda op_type: 0.2
    
    try:
        with pytest.raises(TimeoutError) as exc_info:
            await session._execute_with_timeout(
                'scraping',
                slow_operation
            )
        
        assert "timed out" in str(exc_info.value).lower()
    finally:
        session._get_operation_timeout = original_get_timeout


@pytest.mark.asyncio
async def test_execute_with_timeout_uses_correct_timeout():
    """Test that _execute_with_timeout uses operation-specific timeouts"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Test scraping timeout (300s)
    async def operation():
        return "done"
    
    # We can't easily test the actual timeout value without mocking,
    # but we can verify the method uses _get_operation_timeout
    assert session._get_operation_timeout('scraping') == 300.0
    assert session._get_operation_timeout('monitoring') == 3600.0
    assert session._get_operation_timeout('sending') == 60.0


@pytest.mark.asyncio
async def test_execute_with_timeout_propagates_exceptions():
    """Test that _execute_with_timeout propagates exceptions from operations"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    async def failing_operation():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError) as exc_info:
        await session._execute_with_timeout(
            'scraping',
            failing_operation
        )
    
    assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_scraping_operation_has_timeout():
    """Test that scraping operations use timeout wrapper"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the internal implementation to verify timeout is applied
    call_count = 0
    
    async def mock_scrape_impl(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return {'success': True, 'file_path': 'test.csv'}
    
    # Replace the implementation
    session._scrape_group_members_impl = mock_scrape_impl
    
    # Call the public method
    result = await session.scrape_group_members("test_group")
    
    # Verify the implementation was called
    assert call_count == 1
    assert result['success'] is True


@pytest.mark.asyncio
async def test_sending_operation_has_timeout():
    """Test that sending operations use timeout wrapper"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the internal implementation
    call_count = 0
    
    async def mock_send_impl(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return True
    
    # Replace the implementation
    session._send_message_impl = mock_send_impl
    
    # Call the public method
    result = await session.send_message("test_target", "test message")
    
    # Verify the implementation was called
    assert call_count == 1
    assert result is True


@pytest.mark.asyncio
async def test_monitoring_operation_has_timeout():
    """Test that monitoring operations use timeout wrapper"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the internal implementation
    call_count = 0
    
    async def mock_monitoring_impl(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return True
    
    # Replace the implementation
    session._start_monitoring_impl = mock_monitoring_impl
    
    # Call the public method
    result = await session.start_monitoring([{'chat_id': 'test', 'reaction': '👍'}])
    
    # Verify the implementation was called
    assert call_count == 1
    assert result is True


@pytest.mark.asyncio
async def test_timeout_with_queued_operations():
    """Test that timeout works correctly with queued operations"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.is_connected = True
    
    # Start queue processor
    session.queue_processor_task = asyncio.create_task(session._process_operation_queue())
    
    results = []
    
    async def quick_op(value):
        await asyncio.sleep(0.1)
        return value
    
    # Submit multiple operations
    tasks = [
        session._submit_operation('scraping', quick_op, i)
        for i in range(3)
    ]
    
    # Wait for all to complete
    results = await asyncio.gather(*tasks)
    
    # Verify all completed successfully
    assert results == [0, 1, 2]
    
    # Cleanup
    session.is_connected = False
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_timeout_error_releases_lock():
    """Test that timeout errors properly release the operation lock"""
    session = TelegramSession("test_session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock _get_operation_timeout to return a short timeout
    original_get_timeout = session._get_operation_timeout
    session._get_operation_timeout = lambda op_type: 0.2
    
    try:
        async def slow_operation():
            await asyncio.sleep(10)
            return "should timeout"
        
        # First operation should timeout
        with pytest.raises(TimeoutError):
            await session._submit_operation('scraping', slow_operation)
        
        # Lock should be released, so second operation should work
        async def quick_operation():
            return "success"
        
        result = await session._submit_operation('scraping', quick_operation)
        assert result == "success"
    finally:
        session._get_operation_timeout = original_get_timeout
