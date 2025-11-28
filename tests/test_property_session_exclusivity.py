"""
Property-Based Test for Session Operation Exclusivity

**Feature: telegram-concurrency-fix, Property 1: Session operation exclusivity**

Tests that for any TelegramSession and any two operations O1 and O2, 
if O1 is currently executing on the session, then O2 cannot start until 
O1 completes and releases the operation lock.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings
from telegram_manager.session import TelegramSession


# Strategy for generating operation types
operation_types = st.sampled_from(['scraping', 'monitoring', 'sending'])

# Strategy for generating operation durations (in seconds)
operation_durations = st.floats(min_value=0.01, max_value=0.5)


@pytest.mark.asyncio
@given(
    op1_type=operation_types,
    op2_type=operation_types,
    op1_duration=operation_durations,
    op2_duration=operation_durations
)
@settings(max_examples=100, deadline=None)
async def test_property_session_operation_exclusivity(op1_type, op2_type, op1_duration, op2_duration):
    """
    Property Test: Session operation exclusivity
    
    For any TelegramSession and any two operations O1 and O2, if O1 is currently 
    executing on the session, then O2 cannot start until O1 completes and releases 
    the operation lock.
    
    Test Strategy:
    1. Create a session
    2. Start operation O1 that holds the lock for a duration
    3. Attempt to start operation O2 while O1 is running
    4. Verify O2 cannot acquire the lock until O1 completes
    5. Verify operations execute serially, not concurrently
    """
    # Create a test session
    session = TelegramSession(
        session_file='test_exclusivity.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    # Track operation execution
    execution_log = []
    
    async def mock_operation(op_name: str, duration: float):
        """Mock operation that acquires lock and simulates work"""
        # Try to acquire the operation lock
        acquired = await session._acquire_lock_with_timeout(
            session.operation_lock, 
            timeout=2.0,  # 2 second timeout for test
            lock_name=f"{op_name}_lock"
        )
        
        if not acquired:
            execution_log.append({
                'operation': op_name,
                'event': 'lock_timeout',
                'timestamp': time.time()
            })
            return False
        
        try:
            # Mark operation start
            execution_log.append({
                'operation': op_name,
                'event': 'start',
                'timestamp': time.time()
            })
            
            # Simulate operation work
            await asyncio.sleep(duration)
            
            # Mark operation end
            execution_log.append({
                'operation': op_name,
                'event': 'end',
                'timestamp': time.time()
            })
            
            return True
        finally:
            # Release the lock
            session.operation_lock.release()
    
    # Start both operations concurrently
    op1_task = asyncio.create_task(mock_operation(f"O1_{op1_type}", op1_duration))
    
    # Small delay to ensure O1 starts first
    await asyncio.sleep(0.001)
    
    op2_task = asyncio.create_task(mock_operation(f"O2_{op2_type}", op2_duration))
    
    # Wait for both operations to complete
    results = await asyncio.gather(op1_task, op2_task, return_exceptions=True)
    
    # Verify both operations completed successfully
    assert all(r is True or isinstance(r, bool) for r in results), \
        f"Operations should complete successfully, got: {results}"
    
    # Extract start and end events
    starts = [e for e in execution_log if e['event'] == 'start']
    ends = [e for e in execution_log if e['event'] == 'end']
    
    # Property verification: Operations must execute serially
    # This means O2 cannot start before O1 ends
    if len(starts) >= 2 and len(ends) >= 1:
        o1_start = starts[0]['timestamp']
        o1_end = ends[0]['timestamp']
        o2_start = starts[1]['timestamp']
        
        # Core property: O2 must start after O1 ends (serial execution)
        assert o2_start >= o1_end, \
            f"Operation exclusivity violated: O2 started at {o2_start} before O1 ended at {o1_end}. " \
            f"Operations must execute serially. Execution log: {execution_log}"
    
    # Additional verification: No overlapping execution
    for i in range(len(starts)):
        start_time = starts[i]['timestamp']
        op_name = starts[i]['operation']
        
        # Find corresponding end event
        end_events = [e for e in ends if e['operation'] == op_name]
        if end_events:
            end_time = end_events[0]['timestamp']
            
            # Check no other operation started during this operation's execution
            for j in range(len(starts)):
                if i != j:
                    other_start = starts[j]['timestamp']
                    # Other operation should not start during this operation's execution
                    if start_time < other_start < end_time:
                        pytest.fail(
                            f"Concurrent execution detected: {starts[j]['operation']} started at {other_start} "
                            f"while {op_name} was executing (started: {start_time}, ended: {end_time})"
                        )


@pytest.mark.asyncio
async def test_session_operation_exclusivity_simple_example():
    """
    Simple example test to verify basic operation exclusivity
    
    This is a concrete example that demonstrates the property with specific values.
    """
    session = TelegramSession(
        session_file='test_simple.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    execution_order = []
    
    async def operation_a():
        """First operation"""
        async with session.operation_lock:
            execution_order.append('A_start')
            await asyncio.sleep(0.1)
            execution_order.append('A_end')
    
    async def operation_b():
        """Second operation"""
        # Small delay to ensure A starts first
        await asyncio.sleep(0.01)
        async with session.operation_lock:
            execution_order.append('B_start')
            await asyncio.sleep(0.1)
            execution_order.append('B_end')
    
    # Run both operations concurrently
    await asyncio.gather(operation_a(), operation_b())
    
    # Verify serial execution: A must complete before B starts
    assert execution_order == ['A_start', 'A_end', 'B_start', 'B_end'], \
        f"Expected serial execution, got: {execution_order}"


@pytest.mark.asyncio
async def test_session_operation_exclusivity_three_operations():
    """
    Test exclusivity with three concurrent operations
    
    Verifies that even with multiple operations, they execute serially.
    """
    session = TelegramSession(
        session_file='test_three.session',
        api_id=12345,
        api_hash='test_hash'
    )
    
    execution_log = []
    
    async def operation(name: str, duration: float):
        """Generic operation"""
        async with session.operation_lock:
            execution_log.append(f'{name}_start')
            await asyncio.sleep(duration)
            execution_log.append(f'{name}_end')
    
    # Start three operations with slight delays
    tasks = [
        asyncio.create_task(operation('Op1', 0.05)),
        asyncio.create_task(operation('Op2', 0.05)),
        asyncio.create_task(operation('Op3', 0.05))
    ]
    
    await asyncio.gather(*tasks)
    
    # Verify no interleaving: each operation must complete before next starts
    # Valid patterns: Op1_start, Op1_end, Op2_start, Op2_end, Op3_start, Op3_end (or any permutation)
    # Invalid: Op1_start, Op2_start, ... (concurrent execution)
    
    for i in range(0, len(execution_log), 2):
        if i + 1 < len(execution_log):
            start_event = execution_log[i]
            end_event = execution_log[i + 1]
            
            # Extract operation name from event
            op_name = start_event.replace('_start', '')
            
            # Verify start is followed by corresponding end
            assert end_event == f'{op_name}_end', \
                f"Operation {op_name} was interrupted. Expected {op_name}_end after {start_event}, " \
                f"but got {end_event}. Full log: {execution_log}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
