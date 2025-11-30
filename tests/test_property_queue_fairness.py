"""
Property-Based Test for FIFO within Priority

**Feature: message-sending-and-multi-reaction, Property 33: FIFO within priority**

Tests that for any set of operations with equal priority, they should be 
processed in the order they were enqueued (First-In-First-Out).

**Validates: Requirements 21.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from telegram_manager.models import OperationQueue, QueuedOperation, OperationPriority
import time


# Strategies for generating test data

@st.composite
def operations_with_same_priority(draw, priority=None, min_size=2, max_size=50):
    """Generate a list of operations with the same priority"""
    if priority is None:
        priority = draw(st.sampled_from([
            OperationPriority.HIGH,
            OperationPriority.NORMAL,
            OperationPriority.LOW
        ]))
    
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    operations = []
    
    for i in range(size):
        operation_id = f"op_{priority.name}_{i}"
        operations.append(QueuedOperation(
            operation_id=operation_id,
            priority=priority,
            operation_func=lambda: None,
            args=(),
            kwargs={},
            timestamp=time.time() + i * 0.001  # Ensure unique timestamps
        ))
    
    return operations, priority


@st.composite
def mixed_operations_per_priority(draw, min_per_priority=2, max_per_priority=30):
    """
    Generate operations with multiple operations at each priority level.
    Returns dict mapping priority to list of operations.
    """
    result = {}
    
    for priority in [OperationPriority.HIGH, OperationPriority.NORMAL, OperationPriority.LOW]:
        count = draw(st.integers(min_value=min_per_priority, max_value=max_per_priority))
        operations = []
        
        for i in range(count):
            operations.append(QueuedOperation(
                operation_id=f"op_{priority.name}_{i}",
                priority=priority,
                operation_func=lambda: None,
                args=(),
                kwargs={},
                timestamp=time.time() + i * 0.001
            ))
        
        result[priority] = operations
    
    return result


class TestFIFOWithinPriorityProperty:
    """Property tests for FIFO ordering within same priority level"""
    
    @given(ops_data=operations_with_same_priority(min_size=2, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_same_priority(self, ops_data):
        """
        Property: Operations with same priority are dequeued in FIFO order
        
        For any sequence of operations with the same priority level, when all
        operations are enqueued and then dequeued, they should be returned in
        the exact same order they were enqueued (First-In-First-Out).
        
        **Validates: Requirements 21.4**
        """
        operations, priority = ops_data
        assume(len(operations) >= 2)
        
        # Create queue and enqueue all operations
        queue = OperationQueue()
        for op in operations:
            queue.enqueue(op)
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Verify all operations were dequeued
        assert len(dequeued) == len(operations), \
            f"Expected {len(operations)} operations, got {len(dequeued)}"
        
        # Verify FIFO order: dequeued order should match enqueued order
        for i, (original, dequeued_op) in enumerate(zip(operations, dequeued)):
            assert original.operation_id == dequeued_op.operation_id, \
                f"FIFO violation at position {i}: expected {original.operation_id}, " \
                f"got {dequeued_op.operation_id}"
            assert original.priority == dequeued_op.priority, \
                f"Priority mismatch at position {i}"
    
    @given(ops_by_priority=mixed_operations_per_priority(min_per_priority=2, max_per_priority=30))
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_within_each_priority_level(self, ops_by_priority):
        """
        Property: FIFO ordering is maintained within each priority level independently
        
        For any set of operations with mixed priorities, when operations are
        enqueued and dequeued, the relative order of operations within each
        priority level should be preserved (FIFO).
        
        **Validates: Requirements 21.4**
        """
        # Flatten all operations into a single list for enqueueing
        all_operations = []
        for priority in [OperationPriority.HIGH, OperationPriority.NORMAL, OperationPriority.LOW]:
            all_operations.extend(ops_by_priority[priority])
        
        assume(len(all_operations) >= 6)  # At least 2 per priority
        
        # Create queue and enqueue all operations
        queue = OperationQueue()
        for op in all_operations:
            queue.enqueue(op)
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Verify all operations were dequeued
        assert len(dequeued) == len(all_operations)
        
        # Extract operations by priority from dequeued list
        dequeued_by_priority = {
            OperationPriority.HIGH: [],
            OperationPriority.NORMAL: [],
            OperationPriority.LOW: []
        }
        
        for op in dequeued:
            dequeued_by_priority[op.priority].append(op)
        
        # Verify FIFO order within each priority level
        for priority in [OperationPriority.HIGH, OperationPriority.NORMAL, OperationPriority.LOW]:
            original_ops = ops_by_priority[priority]
            dequeued_ops = dequeued_by_priority[priority]
            
            assert len(original_ops) == len(dequeued_ops), \
                f"Count mismatch for {priority}: expected {len(original_ops)}, " \
                f"got {len(dequeued_ops)}"
            
            # Verify FIFO order for this priority level
            for i, (original, dequeued_op) in enumerate(zip(original_ops, dequeued_ops)):
                assert original.operation_id == dequeued_op.operation_id, \
                    f"FIFO violation for {priority} at position {i}: " \
                    f"expected {original.operation_id}, got {dequeued_op.operation_id}"
    
    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_high_priority_operations(self, data):
        """
        Property: HIGH priority operations maintain FIFO order
        
        For any sequence of HIGH priority operations, regardless of when they
        are enqueued relative to other priorities, they should be dequeued in
        the order they were enqueued.
        
        **Validates: Requirements 21.4**
        """
        # Generate HIGH priority operations
        high_count = data.draw(st.integers(min_value=3, max_value=20))
        high_ops = [
            QueuedOperation(
                operation_id=f"high_{i}",
                priority=OperationPriority.HIGH,
                operation_func=lambda: None,
                args=(),
                kwargs={},
                timestamp=time.time() + i * 0.001
            )
            for i in range(high_count)
        ]
        
        # Generate some NORMAL and LOW priority operations to mix in
        normal_count = data.draw(st.integers(min_value=1, max_value=10))
        low_count = data.draw(st.integers(min_value=1, max_value=10))
        
        normal_ops = [
            QueuedOperation(
                operation_id=f"normal_{i}",
                priority=OperationPriority.NORMAL,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(normal_count)
        ]
        
        low_ops = [
            QueuedOperation(
                operation_id=f"low_{i}",
                priority=OperationPriority.LOW,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(low_count)
        ]
        
        # Create queue and enqueue operations in interleaved manner
        queue = OperationQueue()
        
        # Enqueue in a mixed pattern
        for i in range(max(high_count, normal_count, low_count)):
            if i < high_count:
                queue.enqueue(high_ops[i])
            if i < normal_count:
                queue.enqueue(normal_ops[i])
            if i < low_count:
                queue.enqueue(low_ops[i])
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Extract HIGH priority operations from dequeued list
        dequeued_high = [op for op in dequeued if op.priority == OperationPriority.HIGH]
        
        # Verify FIFO order for HIGH priority operations
        assert len(dequeued_high) == len(high_ops), \
            f"Expected {len(high_ops)} HIGH priority operations, got {len(dequeued_high)}"
        
        for i, (original, dequeued_op) in enumerate(zip(high_ops, dequeued_high)):
            assert original.operation_id == dequeued_op.operation_id, \
                f"FIFO violation for HIGH priority at position {i}: " \
                f"expected {original.operation_id}, got {dequeued_op.operation_id}"
    
    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_normal_priority_operations(self, data):
        """
        Property: NORMAL priority operations maintain FIFO order
        
        For any sequence of NORMAL priority operations, they should be dequeued
        in the order they were enqueued, after all HIGH priority operations.
        
        **Validates: Requirements 21.4**
        """
        # Generate NORMAL priority operations
        normal_count = data.draw(st.integers(min_value=3, max_value=20))
        normal_ops = [
            QueuedOperation(
                operation_id=f"normal_{i}",
                priority=OperationPriority.NORMAL,
                operation_func=lambda: None,
                args=(),
                kwargs={},
                timestamp=time.time() + i * 0.001
            )
            for i in range(normal_count)
        ]
        
        # Generate some HIGH and LOW priority operations
        high_count = data.draw(st.integers(min_value=1, max_value=10))
        low_count = data.draw(st.integers(min_value=1, max_value=10))
        
        high_ops = [
            QueuedOperation(
                operation_id=f"high_{i}",
                priority=OperationPriority.HIGH,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(high_count)
        ]
        
        low_ops = [
            QueuedOperation(
                operation_id=f"low_{i}",
                priority=OperationPriority.LOW,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(low_count)
        ]
        
        # Create queue and enqueue operations in interleaved manner
        queue = OperationQueue()
        
        for i in range(max(high_count, normal_count, low_count)):
            if i < high_count:
                queue.enqueue(high_ops[i])
            if i < normal_count:
                queue.enqueue(normal_ops[i])
            if i < low_count:
                queue.enqueue(low_ops[i])
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Extract NORMAL priority operations from dequeued list
        dequeued_normal = [op for op in dequeued if op.priority == OperationPriority.NORMAL]
        
        # Verify FIFO order for NORMAL priority operations
        assert len(dequeued_normal) == len(normal_ops), \
            f"Expected {len(normal_ops)} NORMAL priority operations, got {len(dequeued_normal)}"
        
        for i, (original, dequeued_op) in enumerate(zip(normal_ops, dequeued_normal)):
            assert original.operation_id == dequeued_op.operation_id, \
                f"FIFO violation for NORMAL priority at position {i}: " \
                f"expected {original.operation_id}, got {dequeued_op.operation_id}"
    
    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_low_priority_operations(self, data):
        """
        Property: LOW priority operations maintain FIFO order
        
        For any sequence of LOW priority operations, they should be dequeued
        in the order they were enqueued, after all HIGH and NORMAL priority operations.
        
        **Validates: Requirements 21.4**
        """
        # Generate LOW priority operations
        low_count = data.draw(st.integers(min_value=3, max_value=20))
        low_ops = [
            QueuedOperation(
                operation_id=f"low_{i}",
                priority=OperationPriority.LOW,
                operation_func=lambda: None,
                args=(),
                kwargs={},
                timestamp=time.time() + i * 0.001
            )
            for i in range(low_count)
        ]
        
        # Generate some HIGH and NORMAL priority operations
        high_count = data.draw(st.integers(min_value=1, max_value=10))
        normal_count = data.draw(st.integers(min_value=1, max_value=10))
        
        high_ops = [
            QueuedOperation(
                operation_id=f"high_{i}",
                priority=OperationPriority.HIGH,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(high_count)
        ]
        
        normal_ops = [
            QueuedOperation(
                operation_id=f"normal_{i}",
                priority=OperationPriority.NORMAL,
                operation_func=lambda: None,
                args=(),
                kwargs={}
            )
            for i in range(normal_count)
        ]
        
        # Create queue and enqueue operations in interleaved manner
        queue = OperationQueue()
        
        for i in range(max(high_count, normal_count, low_count)):
            if i < high_count:
                queue.enqueue(high_ops[i])
            if i < normal_count:
                queue.enqueue(normal_ops[i])
            if i < low_count:
                queue.enqueue(low_ops[i])
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Extract LOW priority operations from dequeued list
        dequeued_low = [op for op in dequeued if op.priority == OperationPriority.LOW]
        
        # Verify FIFO order for LOW priority operations
        assert len(dequeued_low) == len(low_ops), \
            f"Expected {len(low_ops)} LOW priority operations, got {len(dequeued_low)}"
        
        for i, (original, dequeued_op) in enumerate(zip(low_ops, dequeued_low)):
            assert original.operation_id == dequeued_op.operation_id, \
                f"FIFO violation for LOW priority at position {i}: " \
                f"expected {original.operation_id}, got {dequeued_op.operation_id}"
    
    @given(ops_data=operations_with_same_priority(min_size=5, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_partial_dequeue(self, ops_data):
        """
        Property: FIFO order is maintained even with partial dequeuing
        
        For any sequence of operations with the same priority, if we dequeue
        some operations, then enqueue more, then dequeue again, the overall
        order should still respect FIFO for operations at the same priority.
        
        **Validates: Requirements 21.4**
        """
        operations, priority = ops_data
        assume(len(operations) >= 5)
        
        # Split operations into two batches
        split_point = len(operations) // 2
        first_batch = operations[:split_point]
        second_batch = operations[split_point:]
        
        # Create queue and enqueue first batch
        queue = OperationQueue()
        for op in first_batch:
            queue.enqueue(op)
        
        # Dequeue half of first batch
        partial_dequeue_count = len(first_batch) // 2
        first_dequeued = []
        for _ in range(partial_dequeue_count):
            op = queue.dequeue()
            if op is not None:
                first_dequeued.append(op)
        
        # Enqueue second batch
        for op in second_batch:
            queue.enqueue(op)
        
        # Dequeue remaining operations
        remaining_dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                remaining_dequeued.append(op)
        
        # Combine all dequeued operations
        all_dequeued = first_dequeued + remaining_dequeued
        
        # Verify FIFO order is maintained
        assert len(all_dequeued) == len(operations), \
            f"Expected {len(operations)} operations, got {len(all_dequeued)}"
        
        for i, (original, dequeued_op) in enumerate(zip(operations, all_dequeued)):
            assert original.operation_id == dequeued_op.operation_id, \
                f"FIFO violation at position {i}: expected {original.operation_id}, " \
                f"got {dequeued_op.operation_id}"
    
    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_timestamp_order(self, data):
        """
        Property: Operations are dequeued in timestamp order within same priority
        
        For any sequence of operations with the same priority and sequential
        timestamps, they should be dequeued in timestamp order (which is FIFO).
        
        **Validates: Requirements 21.4**
        """
        priority = data.draw(st.sampled_from([
            OperationPriority.HIGH,
            OperationPriority.NORMAL,
            OperationPriority.LOW
        ]))
        
        count = data.draw(st.integers(min_value=3, max_value=30))
        
        # Create operations with sequential timestamps
        base_time = time.time()
        operations = []
        for i in range(count):
            operations.append(QueuedOperation(
                operation_id=f"op_{i}",
                priority=priority,
                operation_func=lambda: None,
                args=(),
                kwargs={},
                timestamp=base_time + i * 0.01  # 10ms apart
            ))
        
        # Create queue and enqueue all operations
        queue = OperationQueue()
        for op in operations:
            queue.enqueue(op)
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Verify operations are dequeued in timestamp order
        assert len(dequeued) == len(operations)
        
        for i in range(len(dequeued) - 1):
            assert dequeued[i].timestamp <= dequeued[i + 1].timestamp, \
                f"Timestamp order violation: operation at index {i} has timestamp " \
                f"{dequeued[i].timestamp}, but operation at index {i+1} has timestamp " \
                f"{dequeued[i+1].timestamp}"
    
    @given(ops_data=operations_with_same_priority(min_size=2, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_property_fifo_no_reordering(self, ops_data):
        """
        Property: No reordering occurs within same priority
        
        For any sequence of operations with the same priority, the dequeue
        order should be a permutation that preserves the original order
        (i.e., no inversions).
        
        **Validates: Requirements 21.4**
        """
        operations, priority = ops_data
        assume(len(operations) >= 2)
        
        # Create queue and enqueue all operations
        queue = OperationQueue()
        for op in operations:
            queue.enqueue(op)
        
        # Dequeue all operations
        dequeued = []
        while not queue.is_empty():
            op = queue.dequeue()
            if op is not None:
                dequeued.append(op)
        
        # Create mapping of operation_id to original index
        original_indices = {op.operation_id: i for i, op in enumerate(operations)}
        
        # Verify no inversions in dequeued order
        for i in range(len(dequeued) - 1):
            current_original_idx = original_indices[dequeued[i].operation_id]
            next_original_idx = original_indices[dequeued[i + 1].operation_id]
            
            assert current_original_idx < next_original_idx, \
                f"Inversion detected: operation '{dequeued[i].operation_id}' " \
                f"(original index {current_original_idx}) comes before " \
                f"'{dequeued[i+1].operation_id}' (original index {next_original_idx}), " \
                f"but should come after"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
