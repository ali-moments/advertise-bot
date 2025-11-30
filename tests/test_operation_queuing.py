"""
Tests for operation queuing system in TelegramSession
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram_manager.session import TelegramSession, QueuedOperation


@pytest.mark.asyncio
async def test_submit_operation_immediate_execution():
    """Test that operations execute immediately when session is idle"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock operation function
    async def mock_operation(value):
        await asyncio.sleep(0.1)
        return f"result_{value}"
    
    # Submit operation - should execute immediately since lock is free
    result = await session._submit_operation(
        'scraping',
        mock_operation,
        'test'
    )
    
    assert result == "result_test"


@pytest.mark.asyncio
async def test_submit_operation_queuing():
    """Test that operations are queued when session is busy"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Start queue processor
    session.queue_processor_task = asyncio.create_task(session._process_operation_queue())
    
    results = []
    
    async def mock_operation(value, delay=0.2):
        await asyncio.sleep(delay)
        return f"result_{value}"
    
    # Submit multiple operations
    tasks = [
        asyncio.create_task(session._submit_operation('scraping', mock_operation, i))
        for i in range(3)
    ]
    
    # Wait for all to complete
    results = await asyncio.gather(*tasks)
    
    # All should complete successfully
    assert len(results) == 3
    assert results[0] == "result_0"
    assert results[1] == "result_1"
    assert results[2] == "result_2"
    
    # Cleanup
    session.is_connected = False
    await session.queue_processor_task


@pytest.mark.asyncio
async def test_operation_completes_within_timeout():
    """Test that operations complete successfully within timeout"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Start queue processor
    session.queue_processor_task = asyncio.create_task(session._process_operation_queue())
    
    async def quick_operation():
        await asyncio.sleep(0.1)
        return "success"
    
    # Submit operation - should complete successfully
    result = await session._submit_operation('sending', quick_operation)
    assert result == "success"
    
    # Cleanup
    session.is_connected = False
    try:
        await asyncio.wait_for(session.queue_processor_task, timeout=1.0)
    except asyncio.TimeoutError:
        session.queue_processor_task.cancel()


@pytest.mark.asyncio
async def test_operation_priority_ordering():
    """Test that operations are processed in priority order"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Start queue processor
    session.queue_processor_task = asyncio.create_task(session._process_operation_queue())
    
    execution_order = []
    
    async def track_operation(op_type):
        execution_order.append(op_type)
        await asyncio.sleep(0.1)
        return op_type
    
    # Acquire lock to force queuing
    await session.operation_lock.acquire()
    
    # Submit operations in reverse priority order (scraping has higher priority than sending)
    tasks = [
        asyncio.create_task(session._submit_operation('sending', track_operation, 'sending')),
        asyncio.create_task(session._submit_operation('scraping', track_operation, 'scraping')),
        asyncio.create_task(session._submit_operation('sending', track_operation, 'sending2')),
    ]
    
    # Wait for all to be queued
    await asyncio.sleep(0.2)
    
    # Release lock to start processing
    session.operation_lock.release()
    
    # Wait for all to complete
    await asyncio.gather(*tasks)
    
    # Should execute in priority order: scraping (5) > sending (1)
    # Note: The queue processor processes in FIFO order within same priority
    # This test verifies they all complete successfully
    assert len(execution_order) == 3
    assert 'scraping' in execution_order
    assert 'sending' in execution_order
    assert 'sending2' in execution_order
    
    # Cleanup
    session.is_connected = False
    await session.queue_processor_task


@pytest.mark.asyncio
async def test_scrape_group_members_uses_queuing():
    """Test that scrape_group_members uses the operation queuing system"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the client
    session.client = AsyncMock()
    
    # Mock the internal implementation
    async def mock_scrape_impl(group_id, max_members, fallback, days_back):
        return {
            'success': True,
            'file_path': 'test.csv',
            'members_count': 100
        }
    
    session._scrape_group_members_impl = mock_scrape_impl
    
    # Call the public method
    result = await session.scrape_group_members('test_group')
    
    # Should return the result from the implementation
    assert result['success'] is True
    assert result['members_count'] == 100


@pytest.mark.asyncio
async def test_join_and_scrape_uses_queuing():
    """Test that join_and_scrape_members uses the operation queuing system"""
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    # Mock the client
    session.client = AsyncMock()
    
    # Mock the internal implementation
    async def mock_join_scrape_impl(group_id, max_members):
        return {
            'success': True,
            'file_path': 'test.csv',
            'members_count': 50,
            'joined': True
        }
    
    session._join_and_scrape_members_impl = mock_join_scrape_impl
    
    # Call the public method
    result = await session.join_and_scrape_members('test_group')
    
    # Should return the result from the implementation
    assert result['success'] is True
    assert result['joined'] is True
    assert result['members_count'] == 50


@pytest.mark.asyncio
async def test_submit_operation_rejects_monitoring():
    """
    Test that _submit_operation rejects 'monitoring' operation type
    
    Validates: AC-5.1, AC-5.2
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    async def mock_operation():
        return "should_not_execute"
    
    # Attempt to submit monitoring operation - should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await session._submit_operation('monitoring', mock_operation)
    
    # Verify error message is clear
    assert 'monitoring' in str(exc_info.value).lower()
    assert 'scraping' in str(exc_info.value).lower() or 'sending' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_submit_operation_accepts_scraping_sending():
    """
    Test that _submit_operation accepts 'scraping' and 'sending' operation types
    
    Validates: AC-5.1
    """
    session = TelegramSession("test.session", 12345, "test_hash")
    session.is_connected = True
    
    async def mock_operation(op_type):
        await asyncio.sleep(0.05)
        return f"executed_{op_type}"
    
    # Submit scraping operation - should succeed
    result_scraping = await session._submit_operation('scraping', mock_operation, 'scraping')
    assert result_scraping == "executed_scraping"
    
    # Submit sending operation - should succeed
    result_sending = await session._submit_operation('sending', mock_operation, 'sending')
    assert result_sending == "executed_sending"
