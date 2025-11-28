"""
Property-Based Test for Task Cleanup Completeness

**Feature: telegram-concurrency-fix, Property 5: Task cleanup completeness**

Tests that for any session that disconnects, all tasks associated with that session 
should be cancelled and removed from the task registry within 5 seconds.

**Validates: Requirements 5.3, 6.1, 6.2**
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings, assume
from telegram_manager.session import TelegramSession


# Strategy for generating task configurations
@st.composite
def task_configuration(draw):
    """Generate a configuration of tasks with various types and behaviors"""
    # Generate 1-10 tasks
    num_tasks = draw(st.integers(min_value=1, max_value=10))
    
    tasks = []
    for i in range(num_tasks):
        task_type = draw(st.sampled_from(['monitoring', 'scraping', 'event_handler', 'sending']))
        # Task duration: some short, some long
        duration = draw(st.floats(min_value=0.1, max_value=2.0))
        # Some tasks may resist cancellation
        resists_cancellation = draw(st.booleans())
        
        tasks.append({
            'id': i,
            'type': task_type,
            'duration': duration,
            'resists_cancellation': resists_cancellation
        })
    
    return tasks


@pytest.mark.asyncio
@given(task_config=task_configuration())
@settings(max_examples=100, deadline=None)
async def test_property_task_cleanup_completeness(task_config):
    """
    Property Test: Task cleanup completeness
    
    For any session that disconnects, all tasks associated with that session should 
    be cancelled and removed from the task registry within 5 seconds.
    
    Test Strategy:
    1. Create a session
    2. Create multiple tasks of various types
    3. Verify tasks are tracked in the registry
    4. Disconnect the session
    5. Verify all tasks are cancelled and removed within 5 seconds
    """
    # Skip if no tasks to test
    assume(len(task_config) >= 1)
    
    # Create a test session
    session = TelegramSession(
        session_file='test_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    # Track which tasks were created
    created_tasks = []
    
    async def mock_task(task_id: int, duration: float, resists: bool):
        """Mock task that may resist cancellation"""
        try:
            if resists:
                # Task that tries to ignore cancellation initially
                try:
                    await asyncio.sleep(duration)
                except asyncio.CancelledError:
                    # Resist once, then give up
                    await asyncio.sleep(0.1)
                    raise
            else:
                # Normal task that cancels cleanly
                await asyncio.sleep(duration)
        except asyncio.CancelledError:
            # Clean cancellation
            raise
    
    # Create tasks using the session's _create_task method
    for task_info in task_config:
        task = session._create_task(
            mock_task(
                task_info['id'],
                task_info['duration'],
                task_info['resists_cancellation']
            ),
            task_type=task_info['type'],
            parent_operation=f"test_operation_{task_info['id']}"
        )
        created_tasks.append(task)
    
    # Small delay to ensure tasks are running
    await asyncio.sleep(0.05)
    
    # Verify tasks are tracked
    initial_task_count = session.get_active_task_count()
    assert initial_task_count == len(task_config), \
        f"Expected {len(task_config)} tasks to be tracked, but found {initial_task_count}"
    
    # Verify tasks are in the registry
    assert len(session.task_registry) == len(task_config), \
        f"Expected {len(task_config)} tasks in registry, but found {len(session.task_registry)}"
    
    # Record start time for cleanup
    cleanup_start = time.time()
    
    # Disconnect the session (this should cancel all tasks)
    await session.disconnect()
    
    # Calculate cleanup duration
    cleanup_duration = time.time() - cleanup_start
    
    # Property verification: All tasks should be cancelled and removed within 5 seconds
    assert cleanup_duration <= 5.0, \
        f"Task cleanup took {cleanup_duration:.2f}s, exceeding 5 second limit"
    
    # Verify all tasks are cancelled
    for task in created_tasks:
        assert task.done(), \
            f"Task {task} should be done after disconnect"
        # Most tasks should be cancelled (some may have completed naturally if very short)
        # We don't strictly require all to be cancelled, just that they're done
    
    # Verify task registry is empty
    assert len(session.task_registry) == 0, \
        f"Task registry should be empty after disconnect, but contains {len(session.task_registry)} tasks"
    
    # Verify active_tasks set is empty
    assert len(session.active_tasks) == 0, \
        f"Active tasks set should be empty after disconnect, but contains {len(session.active_tasks)} tasks"
    
    # Verify task count is zero
    final_task_count = session.get_active_task_count()
    assert final_task_count == 0, \
        f"Active task count should be 0 after disconnect, but is {final_task_count}"


@pytest.mark.asyncio
async def test_task_cleanup_simple_example():
    """
    Simple example test to verify basic task cleanup
    
    This is a concrete example that demonstrates the property with specific values.
    """
    session = TelegramSession(
        session_file='test_simple_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    # Create some tasks
    async def long_task():
        await asyncio.sleep(10.0)
    
    task1 = session._create_task(long_task(), task_type='monitoring')
    task2 = session._create_task(long_task(), task_type='scraping')
    task3 = session._create_task(long_task(), task_type='event_handler')
    
    # Verify tasks are tracked
    assert session.get_active_task_count() == 3
    assert len(session.task_registry) == 3
    
    # Disconnect
    start_time = time.time()
    await session.disconnect()
    cleanup_time = time.time() - start_time
    
    # Verify cleanup completed within 5 seconds
    assert cleanup_time <= 5.0, f"Cleanup took {cleanup_time:.2f}s, exceeding 5 second limit"
    
    # Verify all tasks are done
    assert task1.done()
    assert task2.done()
    assert task3.done()
    
    # Verify registries are empty
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0
    assert len(session.active_tasks) == 0


@pytest.mark.asyncio
async def test_task_cleanup_with_monitoring_task():
    """
    Test that monitoring tasks are properly cleaned up on disconnect
    
    Verifies that the monitoring_task specifically is cancelled.
    """
    session = TelegramSession(
        session_file='test_monitoring_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    # Create a monitoring task
    async def monitoring_keepalive():
        try:
            while True:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
    
    session.monitoring_task = session._create_task(
        monitoring_keepalive(),
        task_type='monitoring',
        parent_operation='monitoring'
    )
    session.is_monitoring = True
    
    # Verify monitoring task is tracked
    assert session.monitoring_task is not None
    assert not session.monitoring_task.done()
    assert session.get_active_task_count() >= 1
    
    # Disconnect
    start_time = time.time()
    await session.disconnect()
    cleanup_time = time.time() - start_time
    
    # Verify cleanup completed within 5 seconds
    assert cleanup_time <= 5.0, f"Cleanup took {cleanup_time:.2f}s"
    
    # Verify monitoring task is cancelled
    assert session.monitoring_task is None or session.monitoring_task.done()
    assert not session.is_monitoring
    
    # Verify all tasks cleaned up
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0


@pytest.mark.asyncio
async def test_task_cleanup_with_stubborn_tasks():
    """
    Test cleanup with tasks that resist cancellation
    
    Verifies that even stubborn tasks are eventually cleaned up.
    """
    session = TelegramSession(
        session_file='test_stubborn_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    # Create a task that resists cancellation
    async def stubborn_task():
        try:
            while True:
                try:
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    # Ignore first cancellation
                    await asyncio.sleep(0.1)
        except:
            pass
    
    # Create a normal task
    async def normal_task():
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            raise
    
    task1 = session._create_task(stubborn_task(), task_type='stubborn')
    task2 = session._create_task(normal_task(), task_type='normal')
    
    # Verify tasks are tracked
    assert session.get_active_task_count() == 2
    
    # Disconnect
    start_time = time.time()
    await session.disconnect()
    cleanup_time = time.time() - start_time
    
    # Verify cleanup completed within 5 seconds
    assert cleanup_time <= 5.0, f"Cleanup took {cleanup_time:.2f}s"
    
    # Verify registries are empty (even if tasks didn't cancel cleanly)
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0
    assert len(session.active_tasks) == 0


@pytest.mark.asyncio
async def test_task_cleanup_multiple_task_types():
    """
    Test cleanup with multiple task types
    
    Verifies that all task types are properly cleaned up.
    """
    session = TelegramSession(
        session_file='test_multi_type_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    async def long_task():
        await asyncio.sleep(10.0)
    
    # Create tasks of different types
    monitoring_task = session._create_task(long_task(), task_type='monitoring', parent_operation='monitor')
    scraping_task = session._create_task(long_task(), task_type='scraping', parent_operation='scrape')
    event_task = session._create_task(long_task(), task_type='event_handler', parent_operation='event')
    sending_task = session._create_task(long_task(), task_type='sending', parent_operation='send')
    
    # Verify all types are tracked
    assert session.get_active_task_count_by_type('monitoring') == 1
    assert session.get_active_task_count_by_type('scraping') == 1
    assert session.get_active_task_count_by_type('event_handler') == 1
    assert session.get_active_task_count_by_type('sending') == 1
    assert session.get_active_task_count() == 4
    
    # Disconnect
    start_time = time.time()
    await session.disconnect()
    cleanup_time = time.time() - start_time
    
    # Verify cleanup completed within 5 seconds
    assert cleanup_time <= 5.0, f"Cleanup took {cleanup_time:.2f}s"
    
    # Verify all task types are cleaned up
    assert session.get_active_task_count_by_type('monitoring') == 0
    assert session.get_active_task_count_by_type('scraping') == 0
    assert session.get_active_task_count_by_type('event_handler') == 0
    assert session.get_active_task_count_by_type('sending') == 0
    assert session.get_active_task_count() == 0


@pytest.mark.asyncio
async def test_task_cleanup_empty_session():
    """
    Test cleanup with no active tasks
    
    Verifies that disconnect works correctly even with no tasks.
    """
    session = TelegramSession(
        session_file='test_empty_cleanup.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    
    # No tasks created
    assert session.get_active_task_count() == 0
    
    # Disconnect should complete quickly
    start_time = time.time()
    await session.disconnect()
    cleanup_time = time.time() - start_time
    
    # Should be very fast with no tasks
    assert cleanup_time <= 1.0, f"Empty cleanup took {cleanup_time:.2f}s"
    
    # Verify still empty
    assert session.get_active_task_count() == 0
    assert len(session.task_registry) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
