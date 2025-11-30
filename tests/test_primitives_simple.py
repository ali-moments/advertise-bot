"""
Simple test for core concurrency primitives in TelegramSession
"""

import asyncio
import sys
import os
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_manager.session import TelegramSession, QueuedOperation, OperationContext, TaskRegistryEntry


def test_queued_operation_dataclass():
    """Test QueuedOperation dataclass creation"""
    async def dummy_func():
        pass
    
    op = QueuedOperation(
        operation_type='scraping',
        operation_func=dummy_func,
        args=(),
        kwargs={},
        priority=5,
        timeout=300.0
    )
    
    assert op.operation_type == 'scraping'
    assert op.priority == 5
    assert op.timeout == 300.0
    assert op.result_future is not None
    print("✅ test_queued_operation_dataclass passed")


def test_operation_context_dataclass():
    """Test OperationContext dataclass creation"""
    ctx = OperationContext(
        operation_type='monitoring',
        session_name='test_session',
        start_time=1234567890.0,
        metadata={'key': 'value'}
    )
    
    assert ctx.operation_type == 'monitoring'
    assert ctx.session_name == 'test_session'
    assert ctx.start_time == 1234567890.0
    assert ctx.metadata == {'key': 'value'}
    print("✅ test_operation_context_dataclass passed")


@pytest.mark.asyncio
async def test_task_registry_entry_dataclass():
    """Test TaskRegistryEntry dataclass creation"""
    async def dummy_coro():
        await asyncio.sleep(0.1)
    
    task = asyncio.create_task(dummy_coro())
    
    entry = TaskRegistryEntry(
        task=task,
        task_type='scraping',
        session_name='test_session',
        created_at=1234567890.0,
        parent_operation='scrape_op_1'
    )
    
    assert entry.task_type == 'scraping'
    assert entry.session_name == 'test_session'
    assert entry.parent_operation == 'scrape_op_1'
    
    # Clean up
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("✅ test_task_registry_entry_dataclass passed")


def test_session_initialization():
    """Test TelegramSession initializes with concurrency primitives"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    # Check operation synchronization
    assert session.operation_lock is not None
    assert session.current_operation is None
    assert session.operation_start_time is None
    
    # Check operation queuing system
    assert session.operation_queue is not None
    assert session.operation_queue.maxsize == 100
    assert session.queue_processor_task is None
    assert session.operation_timeout == 300.0
    assert session.queue_wait_timeout == 60.0
    
    # Check enhanced task tracking
    assert session.monitoring_task is None
    
    # Check event handler isolation
    assert session._handler_lock is not None
    print("✅ test_session_initialization passed")


def test_get_operation_timeout():
    """Test _get_operation_timeout returns correct timeouts"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    # Only scraping and sending operations use the operation queue
    assert session._get_operation_timeout('scraping') == 300.0
    assert session._get_operation_timeout('sending') == 60.0
    assert session._get_operation_timeout('unknown') == 300.0  # default
    print("✅ test_get_operation_timeout passed")


def test_get_operation_priority():
    """Test _get_operation_priority returns correct priorities"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    # Only scraping and sending operations use the operation queue
    assert session._get_operation_priority('scraping') == 5
    assert session._get_operation_priority('sending') == 1
    assert session._get_operation_priority('unknown') == 0  # default
    print("✅ test_get_operation_priority passed")


@pytest.mark.asyncio
async def test_acquire_lock_with_timeout_success():
    """Test _acquire_lock_with_timeout successfully acquires lock"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    test_lock = asyncio.Lock()
    
    # Should acquire successfully
    result = await session._acquire_lock_with_timeout(test_lock, timeout=1.0, lock_name="test_lock")
    assert result is True
    assert test_lock.locked()
    
    # Release lock
    test_lock.release()
    print("✅ test_acquire_lock_with_timeout_success passed")


@pytest.mark.asyncio
async def test_acquire_lock_with_timeout_failure():
    """Test _acquire_lock_with_timeout times out when lock is held"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    test_lock = asyncio.Lock()
    
    # Acquire lock first
    await test_lock.acquire()
    
    # Should timeout
    result = await session._acquire_lock_with_timeout(test_lock, timeout=0.1, lock_name="test_lock")
    assert result is False
    
    # Release lock
    test_lock.release()
    print("✅ test_acquire_lock_with_timeout_failure passed")


def test_create_operation_context():
    """Test _create_operation_context creates proper context"""
    session = TelegramSession(
        session_file='test.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    ctx = session._create_operation_context(
        operation_type='scraping',
        metadata={'group': 'test_group'}
    )
    
    assert ctx.operation_type == 'scraping'
    assert ctx.session_name == 'test.session'
    assert ctx.start_time > 0
    assert ctx.metadata == {'group': 'test_group'}
    assert ctx.task is None
    print("✅ test_create_operation_context passed")


async def run_async_tests():
    """Run async tests"""
    await test_task_registry_entry_dataclass()
    await test_acquire_lock_with_timeout_success()
    await test_acquire_lock_with_timeout_failure()


def main():
    """Run all tests"""
    print("Running tests for core concurrency primitives...\n")
    
    # Run sync tests
    test_queued_operation_dataclass()
    test_operation_context_dataclass()
    test_session_initialization()
    test_get_operation_timeout()
    test_get_operation_priority()
    test_create_operation_context()
    
    # Run async tests
    asyncio.run(run_async_tests())
    
    print("\n✅ All tests passed!")


if __name__ == '__main__':
    main()
