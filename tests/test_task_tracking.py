"""
Tests for enhanced task tracking functionality (Task 5)
"""

import asyncio
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram_manager.session import TelegramSession, TaskRegistryEntry


@pytest.mark.asyncio
async def test_create_task_with_metadata():
    """Test that _create_task properly tracks task metadata"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Create a simple task
    async def dummy_task():
        await asyncio.sleep(0.1)
        return "done"
    
    task = session._create_task(
        dummy_task(),
        task_type="test_task",
        parent_operation="test_operation"
    )
    
    # Verify task is in both registries
    assert task in session.active_tasks
    assert task in session.task_registry
    
    # Verify metadata
    entry = session.task_registry[task]
    assert entry.task_type == "test_task"
    assert entry.parent_operation == "test_operation"
    assert entry.session_name == "test_session"
    assert entry.created_at > 0
    
    # Wait for task to complete
    await task
    
    # Verify auto-cleanup
    await asyncio.sleep(0.05)  # Give callback time to run
    assert task not in session.active_tasks
    assert task not in session.task_registry
    
    print("✅ test_create_task_with_metadata passed")


@pytest.mark.asyncio
async def test_get_active_task_count():
    """Test get_active_task_count method"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Initially no tasks
    assert session.get_active_task_count() == 0
    
    # Create some tasks
    async def long_task():
        await asyncio.sleep(1.0)
    
    task1 = session._create_task(long_task(), task_type="task1")
    task2 = session._create_task(long_task(), task_type="task2")
    task3 = session._create_task(long_task(), task_type="task3")
    
    # Should have 3 active tasks
    assert session.get_active_task_count() == 3
    
    # Cancel all tasks
    task1.cancel()
    task2.cancel()
    task3.cancel()
    
    try:
        await asyncio.gather(task1, task2, task3)
    except asyncio.CancelledError:
        pass
    
    print("✅ test_get_active_task_count passed")


@pytest.mark.asyncio
async def test_get_active_task_count_by_type():
    """Test get_active_task_count_by_type method"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Create tasks of different types
    async def long_task():
        await asyncio.sleep(1.0)
    
    task1 = session._create_task(long_task(), task_type="monitoring")
    task2 = session._create_task(long_task(), task_type="monitoring")
    task3 = session._create_task(long_task(), task_type="scraping")
    task4 = session._create_task(long_task(), task_type="sending")
    
    # Check counts by type
    assert session.get_active_task_count_by_type("monitoring") == 2
    assert session.get_active_task_count_by_type("scraping") == 1
    assert session.get_active_task_count_by_type("sending") == 1
    assert session.get_active_task_count_by_type("unknown") == 0
    
    # Cancel all tasks
    for task in [task1, task2, task3, task4]:
        task.cancel()
    
    try:
        await asyncio.gather(task1, task2, task3, task4)
    except asyncio.CancelledError:
        pass
    
    print("✅ test_get_active_task_count_by_type passed")


@pytest.mark.asyncio
async def test_get_task_details():
    """Test get_task_details method"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Create tasks with different metadata
    async def long_task():
        await asyncio.sleep(1.0)
    
    task1 = session._create_task(
        long_task(),
        task_type="monitoring",
        parent_operation="start_monitoring"
    )
    task2 = session._create_task(
        long_task(),
        task_type="scraping",
        parent_operation="scrape_group"
    )
    
    # Get task details
    details = session.get_task_details()
    
    # Should have 2 tasks
    assert len(details) == 2
    
    # Check details structure
    for detail in details:
        assert 'task_type' in detail
        assert 'parent_operation' in detail
        assert 'session_name' in detail
        assert 'age_seconds' in detail
        assert 'created_at' in detail
        assert 'done' in detail
        assert 'cancelled' in detail
        
        assert detail['session_name'] == "test_session"
        assert detail['done'] == False
        assert detail['age_seconds'] >= 0
    
    # Verify task types
    task_types = [d['task_type'] for d in details]
    assert "monitoring" in task_types
    assert "scraping" in task_types
    
    # Cancel all tasks
    task1.cancel()
    task2.cancel()
    
    try:
        await asyncio.gather(task1, task2)
    except asyncio.CancelledError:
        pass
    
    print("✅ test_get_task_details passed")


@pytest.mark.asyncio
async def test_cancel_all_tasks_with_timeout():
    """Test _cancel_all_tasks_with_timeout method"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Create some tasks
    async def cancellable_task():
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            # Clean cancellation
            raise
    
    task1 = session._create_task(cancellable_task(), task_type="task1")
    task2 = session._create_task(cancellable_task(), task_type="task2")
    task3 = session._create_task(cancellable_task(), task_type="task3")
    
    # Should have 3 active tasks
    assert session.get_active_task_count() == 3
    
    # Cancel all tasks with timeout
    await session._cancel_all_tasks_with_timeout(timeout=2.0)
    
    # All tasks should be cancelled and cleaned up
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0
    
    print("✅ test_cancel_all_tasks_with_timeout passed")


@pytest.mark.asyncio
async def test_cancel_all_tasks_with_timeout_logs_slow_tasks():
    """Test that _cancel_all_tasks_with_timeout logs tasks that don't cancel cleanly"""
    session = TelegramSession("test_session", 12345, "test_hash")
    
    # Create a task that resists cancellation
    async def stubborn_task():
        try:
            while True:
                try:
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    # Ignore cancellation and keep running
                    await asyncio.sleep(0.1)
        except:
            pass
    
    # Create a normal task
    async def normal_task():
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            raise
    
    task1 = session._create_task(stubborn_task(), task_type="stubborn")
    task2 = session._create_task(normal_task(), task_type="normal")
    
    # Should have 2 active tasks
    assert session.get_active_task_count() == 2
    
    # Cancel all tasks with short timeout
    # This should timeout because stubborn_task won't cancel
    await session._cancel_all_tasks_with_timeout(timeout=0.5)
    
    # Both tasks should be removed from registries even if they didn't cancel cleanly
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0
    
    print("✅ test_cancel_all_tasks_with_timeout_logs_slow_tasks passed")


if __name__ == "__main__":
    print("Running task tracking tests...")
    asyncio.run(test_create_task_with_metadata())
    asyncio.run(test_get_active_task_count())
    asyncio.run(test_get_active_task_count_by_type())
    asyncio.run(test_get_task_details())
    asyncio.run(test_cancel_all_tasks_with_timeout())
    asyncio.run(test_cancel_all_tasks_with_timeout_logs_slow_tasks())
    print("\n✅ All task tracking tests passed!")
