# Task 2.4: Property Test for Operation Queue Fairness

## Summary

Successfully implemented property-based test for operation queue fairness and fixed the implementation to support priority-based queuing as specified in the design document.

## Test Implementation

**File:** `tests/test_property_queue_fairness.py`

**Property Tested:** Property 8 - Operation queue fairness

**Validates:** Requirements 1.4

### Test Cases

1. **`test_property_operation_queue_fairness`** (Property-Based Test)
   - Uses Hypothesis to generate random sequences of operations
   - Verifies operations execute in priority order: monitoring (10) > scraping (5) > sending (1)
   - Verifies FIFO ordering within the same priority level
   - Runs 100 examples to ensure comprehensive coverage

2. **`test_queue_fairness_simple_example`**
   - Concrete example with known values
   - Submits operations in reverse priority order
   - Verifies they execute in correct priority order

3. **`test_queue_fairness_fifo_within_priority`**
   - Tests FIFO ordering for operations with the same priority
   - Submits 3 scraping operations
   - Verifies they execute in submission order

4. **`test_queue_timeout_handling`**
   - Tests queue wait timeout mechanism
   - Verifies operations timeout if they wait too long in queue

## Implementation Fixes

### 1. Changed Queue Type
**File:** `telegram_manager/session.py`

Changed from `asyncio.Queue` to `asyncio.PriorityQueue`:
```python
self.operation_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=100)
```

### 2. Added Comparison Methods to QueuedOperation

Added `__lt__`, `__le__`, `__gt__`, `__ge__`, and `__eq__` methods to enable priority queue sorting:
- Higher priority values execute first (monitoring=10 > scraping=5 > sending=1)
- Within same priority, FIFO order maintained using sequence numbers
- Sequence counter tracks submission order

### 3. Fixed Queue Processor Logic

**Critical Fix:** Changed queue processor to acquire lock BEFORE pulling from queue:

**Before:**
```python
# Pull from queue first
queued_op = await self.operation_queue.get()
# Then try to acquire lock
lock_acquired = await self._acquire_lock_with_timeout(...)
```

**After:**
```python
# Acquire lock first
lock_acquired = await self._acquire_lock_with_timeout(...)
if lock_acquired:
    # Then pull from queue
    queued_op = await self.operation_queue.get()
```

This ensures operations are pulled in priority order, not submission order.

## Test Results

✅ **All tests passing:**
- `test_property_operation_queue_fairness`: PASSED (100 hypothesis examples)
- `test_queue_fairness_simple_example`: PASSED
- `test_queue_fairness_fifo_within_priority`: PASSED
- `test_queue_timeout_handling`: PASSED

✅ **Existing tests still passing:**
- All 6 operation queuing tests: PASSED
- All 3 session exclusivity property tests: PASSED

## Property Validation

**Property 8: Operation queue fairness**

*For any* session with queued operations, operations should be processed in priority order (monitoring=10 > scraping=5 > sending=1), and within the same priority, in FIFO order, with each operation timing out if not started within the queue wait timeout.

**Status:** ✅ VALIDATED

The implementation now correctly enforces priority-based queue processing as specified in the design document.
