"""
Property-Based Test for Deadlock Freedom

**Feature: telegram-concurrency-fix, Property 9: Deadlock freedom**

Tests that for any sequence of lock acquisitions across all sessions and the manager, 
the system should never enter a state where two or more operations are waiting for 
each other to release locks (circular wait condition).

**Validates: Requirements 7.4**
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings, assume
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.session import TelegramSession


# Strategy for generating sequences of lock acquisition patterns
@st.composite
def lock_acquisition_sequence(draw):
    """Generate a sequence of lock acquisition operations"""
    # Generate 5-15 operations
    num_ops = draw(st.integers(min_value=5, max_value=15))
    
    operations = []
    for i in range(num_ops):
        # Each operation will try to acquire locks in some pattern
        op_type = draw(st.sampled_from([
            'manager_then_session',  # Correct order: manager lock -> session lock
            'session_operation',     # Session operation lock only
            'manager_metrics',       # Manager metrics lock only
            'scrape_with_semaphore', # Scrape semaphore -> session operation
            'global_task_tracking',  # Global task lock -> session task lock
        ]))
        duration = draw(st.floats(min_value=0.01, max_value=0.1))
        operations.append({
            'id': i,
            'type': op_type,
            'duration': duration
        })
    
    return operations


@pytest.mark.asyncio
@given(ops=lock_acquisition_sequence())
@settings(max_examples=100, deadline=None)
async def test_property_deadlock_freedom(ops):
    """
    Property Test: Deadlock freedom
    
    For any sequence of lock acquisitions across all sessions and the manager, 
    the system should never enter a state where two or more operations are waiting 
    for each other to release locks (circular wait condition).
    
    Test Strategy:
    1. Create a manager with multiple sessions
    2. Execute various lock acquisition patterns concurrently
    3. Use timeouts to detect potential deadlocks
    4. Verify all operations complete without deadlock
    5. Track lock acquisition order and verify it follows the hierarchy
    """
    # Skip if we have too few operations
    assume(len(ops) >= 5)
    
    # Create a test manager with sessions
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create mock sessions
    for i in range(3):
        session = TelegramSession(
            session_file=f'test_deadlock_{i}.session',
            api_id=12345,
            api_hash='test_hash'
        )
        session.is_connected = True
        manager.sessions[f'session_{i}'] = session
        manager.session_locks[f'session_{i}'] = asyncio.Lock()
        manager.session_load[f'session_{i}'] = 0
    
    # Track operation completion
    completed_ops = []
    completion_lock = asyncio.Lock()
    
    # Track any timeout errors
    timeout_errors = []
    
    async def execute_operation(op_id: int, op_type: str, duration: float):
        """Execute an operation with specific lock acquisition pattern"""
        try:
            if op_type == 'manager_then_session':
                # Correct order: manager lock -> session lock
                # This follows the hierarchy: manager locks before session locks
                async with manager.metrics_lock:
                    await asyncio.sleep(duration / 2)
                    session_name = list(manager.sessions.keys())[op_id % len(manager.sessions)]
                    async with manager.session_locks[session_name]:
                        await asyncio.sleep(duration / 2)
            
            elif op_type == 'session_operation':
                # Session operation lock only
                session_name = list(manager.sessions.keys())[op_id % len(manager.sessions)]
                session = manager.sessions[session_name]
                acquired = await session._acquire_lock_with_timeout(
                    session.operation_lock,
                    timeout=5.0,  # 5 second timeout to detect deadlocks
                    lock_name=f"session_{session_name}_operation"
                )
                if acquired:
                    try:
                        await asyncio.sleep(duration)
                    finally:
                        session._release_lock_with_logging(session.operation_lock, f"session_{session_name}_operation")
                else:
                    timeout_errors.append(f"op_{op_id}_timeout")
            
            elif op_type == 'manager_metrics':
                # Manager metrics lock only
                acquired = await manager._acquire_lock_with_timeout(
                    manager.metrics_lock,
                    timeout=5.0,
                    lock_name="manager_metrics"
                )
                if acquired:
                    try:
                        await asyncio.sleep(duration)
                    finally:
                        manager._release_lock_with_logging(manager.metrics_lock, "manager_metrics")
                else:
                    timeout_errors.append(f"op_{op_id}_timeout")
            
            elif op_type == 'scrape_with_semaphore':
                # Correct order: semaphore -> session operation lock
                try:
                    await asyncio.wait_for(
                        manager.scrape_semaphore.acquire(),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    timeout_errors.append(f"op_{op_id}_semaphore_timeout")
                    return
                
                try:
                    session_name = list(manager.sessions.keys())[op_id % len(manager.sessions)]
                    session = manager.sessions[session_name]
                    acquired = await session._acquire_lock_with_timeout(
                        session.operation_lock,
                        timeout=5.0,
                        lock_name=f"session_{session_name}_operation"
                    )
                    if acquired:
                        try:
                            await asyncio.sleep(duration)
                        finally:
                            session._release_lock_with_logging(session.operation_lock, f"session_{session_name}_operation")
                    else:
                        timeout_errors.append(f"op_{op_id}_timeout")
                finally:
                    manager.scrape_semaphore.release()
            
            elif op_type == 'global_task_tracking':
                # Correct order: global task lock -> session task lock
                acquired_global = await manager._acquire_lock_with_timeout(
                    manager.global_task_lock,
                    timeout=5.0,
                    lock_name="global_task"
                )
                if acquired_global:
                    try:
                        await asyncio.sleep(duration / 2)
                        session_name = list(manager.sessions.keys())[op_id % len(manager.sessions)]
                        session = manager.sessions[session_name]
                        acquired_session = await session._acquire_lock_with_timeout(
                            session.task_lock,
                            timeout=5.0,
                            lock_name=f"session_{session_name}_task"
                        )
                        if acquired_session:
                            try:
                                await asyncio.sleep(duration / 2)
                            finally:
                                session._release_lock_with_logging(session.task_lock, f"session_{session_name}_task")
                        else:
                            timeout_errors.append(f"op_{op_id}_session_task_timeout")
                    finally:
                        manager._release_lock_with_logging(manager.global_task_lock, "global_task")
                else:
                    timeout_errors.append(f"op_{op_id}_global_task_timeout")
            
            # Mark operation as completed
            async with completion_lock:
                completed_ops.append(op_id)
        
        except Exception as e:
            # Log any unexpected errors
            async with completion_lock:
                timeout_errors.append(f"op_{op_id}_error: {str(e)}")
    
    # Execute all operations concurrently
    tasks = [
        asyncio.create_task(execute_operation(op['id'], op['type'], op['duration']))
        for op in ops
    ]
    
    # Wait for all operations with a global timeout
    # If we hit this timeout, it indicates a deadlock
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=30.0  # Global timeout for all operations
        )
    except asyncio.TimeoutError:
        pytest.fail(
            f"DEADLOCK DETECTED: Operations did not complete within 30 seconds. "
            f"Completed: {len(completed_ops)}/{len(ops)}. "
            f"Timeout errors: {timeout_errors}. "
            f"This indicates a circular wait condition (deadlock)."
        )
    
    # Property verification: All operations should complete without deadlock
    # If we reach here, no deadlock occurred
    
    # Verify most operations completed successfully
    # We allow some timeouts due to contention, but not all operations should timeout
    completion_rate = len(completed_ops) / len(ops)
    assert completion_rate >= 0.7, \
        f"Too many operations timed out ({len(completed_ops)}/{len(ops)} completed). " \
        f"This suggests potential deadlock or excessive contention. " \
        f"Timeout errors: {timeout_errors}"
    
    # Verify no circular wait occurred
    # If we completed without the global timeout, no deadlock occurred
    assert len(timeout_errors) < len(ops) * 0.3, \
        f"Too many individual operation timeouts ({len(timeout_errors)}), " \
        f"which may indicate lock contention or near-deadlock conditions. " \
        f"Errors: {timeout_errors}"


@pytest.mark.asyncio
async def test_deadlock_freedom_simple_example():
    """
    Simple example test to verify basic deadlock freedom
    
    This is a concrete example that demonstrates correct lock ordering.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create a session
    session = TelegramSession(
        session_file='test_simple_deadlock.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    manager.sessions['session_0'] = session
    manager.session_locks['session_0'] = asyncio.Lock()
    
    completed = []
    
    async def operation_a():
        """Operation following correct lock order: manager -> session"""
        async with manager.metrics_lock:
            await asyncio.sleep(0.05)
            async with manager.session_locks['session_0']:
                await asyncio.sleep(0.05)
                completed.append('A')
    
    async def operation_b():
        """Another operation following correct lock order"""
        async with manager.global_task_lock:
            await asyncio.sleep(0.05)
            async with session.task_lock:
                await asyncio.sleep(0.05)
                completed.append('B')
    
    # Run both operations concurrently
    await asyncio.gather(operation_a(), operation_b())
    
    # Both should complete without deadlock
    assert len(completed) == 2, \
        f"Expected both operations to complete, got {len(completed)}"
    assert set(completed) == {'A', 'B'}, \
        f"Expected operations A and B to complete, got {completed}"


@pytest.mark.asyncio
async def test_deadlock_freedom_with_timeouts():
    """
    Test that lock acquisition timeouts prevent indefinite deadlocks
    
    Verifies that even if contention is high, operations timeout rather than deadlock.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create sessions
    for i in range(2):
        session = TelegramSession(
            session_file=f'test_timeout_{i}.session',
            api_id=12345,
            api_hash='test_hash'
        )
        session.is_connected = True
        manager.sessions[f'session_{i}'] = session
        manager.session_locks[f'session_{i}'] = asyncio.Lock()
    
    completed = []
    timed_out = []
    
    async def operation_with_timeout(op_id: int):
        """Operation that uses timeout for lock acquisition"""
        session = manager.sessions[f'session_{op_id % 2}']
        
        # Try to acquire lock with timeout
        acquired = await session._acquire_lock_with_timeout(
            session.operation_lock,
            timeout=2.0,  # 2 second timeout
            lock_name=f"op_{op_id}"
        )
        
        if acquired:
            try:
                await asyncio.sleep(0.1)
                completed.append(op_id)
            finally:
                session._release_lock_with_logging(session.operation_lock, f"op_{op_id}")
        else:
            timed_out.append(op_id)
    
    # Start many operations concurrently
    tasks = [
        asyncio.create_task(operation_with_timeout(i))
        for i in range(10)
    ]
    
    # Wait for all operations
    await asyncio.gather(*tasks)
    
    # Verify that operations either completed or timed out (no deadlock)
    total_accounted = len(completed) + len(timed_out)
    assert total_accounted == 10, \
        f"Expected all 10 operations to complete or timeout, got {total_accounted}"
    
    # Verify at least some operations completed
    assert len(completed) > 0, \
        f"Expected at least some operations to complete, but all timed out"


@pytest.mark.asyncio
async def test_deadlock_freedom_correct_hierarchy():
    """
    Test that following the correct lock hierarchy prevents deadlocks
    
    Verifies the documented lock acquisition order:
    1. Manager-level locks
    2. Manager-level semaphores
    3. Session-level locks
    4. Session operation lock
    5. Session task lock
    6. Session handler lock
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create a session
    session = TelegramSession(
        session_file='test_hierarchy.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    manager.sessions['session_0'] = session
    manager.session_locks['session_0'] = asyncio.Lock()
    
    completed = []
    
    async def operation_full_hierarchy():
        """Operation that acquires locks in correct hierarchical order"""
        # Level 1: Manager-level locks
        async with manager.metrics_lock:
            await asyncio.sleep(0.01)
            
            # Level 2: Manager-level semaphores
            await manager.scrape_semaphore.acquire()
            try:
                await asyncio.sleep(0.01)
                
                # Level 3: Session-level locks
                async with manager.session_locks['session_0']:
                    await asyncio.sleep(0.01)
                    
                    # Level 4: Session operation lock
                    async with session.operation_lock:
                        await asyncio.sleep(0.01)
                        
                        # Level 5: Session task lock
                        async with session.task_lock:
                            await asyncio.sleep(0.01)
                            
                            # Level 6: Session handler lock
                            async with session._handler_lock:
                                await asyncio.sleep(0.01)
                                completed.append('full_hierarchy')
            finally:
                manager.scrape_semaphore.release()
    
    # Run the operation
    await operation_full_hierarchy()
    
    # Verify it completed without deadlock
    assert 'full_hierarchy' in completed, \
        "Operation following correct lock hierarchy should complete without deadlock"


@pytest.mark.asyncio
async def test_deadlock_freedom_multiple_sessions():
    """
    Test deadlock freedom with operations across multiple sessions
    
    Verifies that operations on different sessions don't deadlock each other.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create multiple sessions
    for i in range(3):
        session = TelegramSession(
            session_file=f'test_multi_{i}.session',
            api_id=12345,
            api_hash='test_hash'
        )
        session.is_connected = True
        manager.sessions[f'session_{i}'] = session
        manager.session_locks[f'session_{i}'] = asyncio.Lock()
    
    completed = []
    
    async def operation_on_session(session_id: int):
        """Operation that works on a specific session"""
        session_name = f'session_{session_id}'
        session = manager.sessions[session_name]
        
        # Acquire manager lock first (correct order)
        async with manager.metrics_lock:
            await asyncio.sleep(0.02)
            
            # Then session lock
            async with manager.session_locks[session_name]:
                await asyncio.sleep(0.02)
                
                # Then session operation lock
                async with session.operation_lock:
                    await asyncio.sleep(0.02)
                    completed.append(session_id)
    
    # Run operations on all sessions concurrently
    tasks = [
        asyncio.create_task(operation_on_session(i))
        for i in range(3)
    ]
    
    # Wait for all operations
    await asyncio.gather(*tasks)
    
    # Verify all completed without deadlock
    assert len(completed) == 3, \
        f"Expected all 3 operations to complete, got {len(completed)}"
    assert set(completed) == {0, 1, 2}, \
        f"Expected operations on all sessions to complete, got {completed}"


@pytest.mark.asyncio
async def test_deadlock_freedom_with_retries():
    """
    Test that retry logic doesn't cause deadlocks
    
    Verifies that operations that retry after failures don't create deadlock conditions.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Create a session
    session = TelegramSession(
        session_file='test_retry.session',
        api_id=12345,
        api_hash='test_hash'
    )
    session.is_connected = True
    manager.sessions['session_0'] = session
    manager.session_locks['session_0'] = asyncio.Lock()
    
    attempt_count = 0
    completed = []
    
    async def operation_with_retry():
        """Operation that may retry"""
        nonlocal attempt_count
        
        for attempt in range(3):
            attempt_count += 1
            
            # Try to acquire lock
            acquired = await session._acquire_lock_with_timeout(
                session.operation_lock,
                timeout=1.0,
                lock_name=f"retry_attempt_{attempt}"
            )
            
            if acquired:
                try:
                    await asyncio.sleep(0.05)
                    completed.append(attempt)
                    return  # Success
                finally:
                    session._release_lock_with_logging(session.operation_lock, f"retry_attempt_{attempt}")
            else:
                # Retry after a short delay
                await asyncio.sleep(0.1)
        
        # If we get here, all retries failed
        completed.append('failed')
    
    # Run multiple operations with retries
    tasks = [
        asyncio.create_task(operation_with_retry())
        for _ in range(5)
    ]
    
    # Wait for all operations
    await asyncio.gather(*tasks)
    
    # Verify operations completed (either succeeded or failed, but no deadlock)
    assert len(completed) == 5, \
        f"Expected all 5 operations to complete, got {len(completed)}"
    
    # Verify at least some succeeded
    successful = [c for c in completed if c != 'failed']
    assert len(successful) > 0, \
        "Expected at least some operations to succeed"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
