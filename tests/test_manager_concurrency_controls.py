"""
Tests for manager-level concurrency controls (Task 6)

This test file verifies:
- Task 6.1: Scrape semaphore limits concurrent scrapes to 5
- Task 6.2: Global task tracking across sessions
- Task 6.3: Operation metrics tracking
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.session import TelegramSession


@pytest.mark.asyncio
async def test_scrape_semaphore_initialization():
    """Test that scrape semaphore is initialized with limit of 5 (Task 6.1)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Verify scrape semaphore exists and has correct limit
    assert hasattr(manager, 'scrape_semaphore')
    assert manager.scrape_semaphore._value == 5
    
    # Verify active scrape count tracking
    assert hasattr(manager, 'active_scrape_count')
    assert manager.active_scrape_count == 0
    
    # Verify get_active_scrape_count method exists
    assert hasattr(manager, 'get_active_scrape_count')
    assert manager.get_active_scrape_count() == 0


@pytest.mark.asyncio
async def test_global_task_tracking_initialization():
    """Test that global task tracking is initialized (Task 6.2)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Verify global task tracking structures exist
    assert hasattr(manager, 'global_tasks')
    assert isinstance(manager.global_tasks, dict)
    assert len(manager.global_tasks) == 0
    
    # Verify global task lock exists
    assert hasattr(manager, 'global_task_lock')
    assert isinstance(manager.global_task_lock, asyncio.Lock)
    
    # Verify task tracking methods exist
    assert hasattr(manager, 'register_task_globally')
    assert hasattr(manager, 'unregister_task_globally')
    assert hasattr(manager, 'get_global_task_count')
    assert hasattr(manager, 'cleanup_session_tasks')


@pytest.mark.asyncio
async def test_operation_metrics_initialization():
    """Test that operation metrics tracking is initialized (Task 6.3)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Verify operation metrics structure exists
    assert hasattr(manager, 'operation_metrics')
    assert isinstance(manager.operation_metrics, dict)
    
    # Verify all operation types are tracked
    assert 'scraping' in manager.operation_metrics
    assert 'monitoring' in manager.operation_metrics
    assert 'sending' in manager.operation_metrics
    assert 'other' in manager.operation_metrics
    
    # Verify all metrics start at 0
    assert manager.operation_metrics['scraping'] == 0
    assert manager.operation_metrics['monitoring'] == 0
    assert manager.operation_metrics['sending'] == 0
    assert manager.operation_metrics['other'] == 0
    
    # Verify metrics lock exists
    assert hasattr(manager, 'metrics_lock')
    assert isinstance(manager.metrics_lock, asyncio.Lock)
    
    # Verify metrics methods exist
    assert hasattr(manager, 'increment_operation_metric')
    assert hasattr(manager, 'decrement_operation_metric')
    assert hasattr(manager, 'get_operation_metrics')
    assert hasattr(manager, 'get_operation_count')


@pytest.mark.asyncio
async def test_register_and_unregister_task_globally():
    """Test registering and unregistering tasks globally (Task 6.2)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Create a dummy task
    async def dummy_coro():
        await asyncio.sleep(0.1)
    
    task = asyncio.create_task(dummy_coro())
    
    # Register task for a session
    await manager.register_task_globally('session1', task)
    
    # Verify task is registered
    assert 'session1' in manager.global_tasks
    assert task in manager.global_tasks['session1']
    assert await manager.get_global_task_count('session1') == 1
    assert await manager.get_global_task_count() == 1
    
    # Unregister task
    await manager.unregister_task_globally('session1', task)
    
    # Verify task is unregistered
    assert 'session1' not in manager.global_tasks
    assert await manager.get_global_task_count('session1') == 0
    assert await manager.get_global_task_count() == 0
    
    # Clean up
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_increment_and_decrement_operation_metrics():
    """Test incrementing and decrementing operation metrics (Task 6.3)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Increment scraping metric
    await manager.increment_operation_metric('scraping')
    assert await manager.get_operation_count('scraping') == 1
    
    # Increment monitoring metric
    await manager.increment_operation_metric('monitoring')
    await manager.increment_operation_metric('monitoring')
    assert await manager.get_operation_count('monitoring') == 2
    
    # Get all metrics
    metrics = await manager.get_operation_metrics()
    assert metrics['scraping'] == 1
    assert metrics['monitoring'] == 2
    assert metrics['sending'] == 0
    assert metrics['other'] == 0
    
    # Decrement metrics
    await manager.decrement_operation_metric('scraping')
    await manager.decrement_operation_metric('monitoring')
    
    assert await manager.get_operation_count('scraping') == 0
    assert await manager.get_operation_count('monitoring') == 1
    
    # Verify decrement doesn't go below 0
    await manager.decrement_operation_metric('scraping')
    assert await manager.get_operation_count('scraping') == 0


@pytest.mark.asyncio
async def test_cleanup_session_tasks():
    """Test cleaning up all tasks for a session (Task 6.2)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Create multiple dummy tasks
    async def dummy_coro():
        await asyncio.sleep(10)  # Long sleep to ensure tasks are running
    
    tasks = [asyncio.create_task(dummy_coro()) for _ in range(3)]
    
    # Register all tasks for a session
    for task in tasks:
        await manager.register_task_globally('session1', task)
    
    # Verify tasks are registered
    assert await manager.get_global_task_count('session1') == 3
    
    # Clean up session tasks
    await manager.cleanup_session_tasks('session1')
    
    # Verify all tasks are cancelled and unregistered
    assert await manager.get_global_task_count('session1') == 0
    assert 'session1' not in manager.global_tasks
    
    # Verify tasks are actually cancelled
    for task in tasks:
        assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_scrape_semaphore_limits_concurrent_operations():
    """Test that scrape semaphore limits concurrent scrapes to 5 (Task 6.1)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Track how many operations are running concurrently
    concurrent_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()
    
    async def mock_scrape():
        nonlocal concurrent_count, max_concurrent
        
        async with manager.scrape_semaphore:
            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            # Simulate scraping work
            await asyncio.sleep(0.1)
            
            async with lock:
                concurrent_count -= 1
    
    # Start 10 scraping operations
    tasks = [asyncio.create_task(mock_scrape()) for _ in range(10)]
    
    # Wait for all to complete
    await asyncio.gather(*tasks)
    
    # Verify max concurrent was limited to 5
    assert max_concurrent <= 5
    assert concurrent_count == 0  # All operations completed


@pytest.mark.asyncio
async def test_global_task_tracking_multiple_sessions():
    """Test global task tracking across multiple sessions (Task 6.2)"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Create tasks for multiple sessions
    async def dummy_coro():
        await asyncio.sleep(0.1)
    
    session1_tasks = [asyncio.create_task(dummy_coro()) for _ in range(2)]
    session2_tasks = [asyncio.create_task(dummy_coro()) for _ in range(3)]
    
    # Register tasks for different sessions
    for task in session1_tasks:
        await manager.register_task_globally('session1', task)
    
    for task in session2_tasks:
        await manager.register_task_globally('session2', task)
    
    # Verify counts
    assert await manager.get_global_task_count('session1') == 2
    assert await manager.get_global_task_count('session2') == 3
    assert await manager.get_global_task_count() == 5
    
    # Clean up
    for task in session1_tasks + session2_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
