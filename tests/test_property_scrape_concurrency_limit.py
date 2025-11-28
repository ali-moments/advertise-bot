"""
Property-Based Test for Scrape Concurrency Limit

**Feature: telegram-concurrency-fix, Property 4: Scrape concurrency limit**

Tests that for any point in time, the number of actively running scraping operations 
across all sessions should never exceed 5.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings, assume
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.session import TelegramSession


# Strategy for generating number of concurrent scrape requests
scrape_request_counts = st.integers(min_value=6, max_value=20)

# Strategy for generating scrape durations
scrape_durations = st.floats(min_value=0.05, max_value=0.3)


@pytest.mark.asyncio
@given(
    num_scrapes=scrape_request_counts,
    scrape_duration=scrape_durations
)
@settings(max_examples=20, deadline=None)
async def test_property_scrape_concurrency_limit(num_scrapes, scrape_duration):
    """
    Property Test: Scrape concurrency limit
    
    For any point in time, the number of actively running scraping operations 
    across all sessions should never exceed 5.
    
    Test Strategy:
    1. Create a manager with multiple sessions
    2. Submit more than 5 scraping operations concurrently
    3. Track the number of concurrent scrapes at any point in time
    4. Verify that the maximum concurrent scrapes never exceeds 5
    5. Verify all scrapes eventually complete
    """
    # Ensure we have enough scrapes to test the limit
    assume(num_scrapes >= 6)
    
    # Create a test manager
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Track concurrent scrape count
    concurrent_count = 0
    max_concurrent = 0
    count_lock = asyncio.Lock()
    
    # Track all observed concurrent counts
    observed_counts = []
    
    async def mock_scrape_operation(scrape_id: int):
        """Mock scraping operation that tracks concurrency"""
        nonlocal concurrent_count, max_concurrent
        
        # Acquire the scrape semaphore (this is what limits concurrency)
        async with manager.scrape_semaphore:
            # Increment concurrent count
            async with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                observed_counts.append(concurrent_count)
            
            # Simulate scraping work
            await asyncio.sleep(scrape_duration)
            
            # Decrement concurrent count
            async with count_lock:
                concurrent_count -= 1
                observed_counts.append(concurrent_count)
        
        return f"scrape_{scrape_id}_complete"
    
    # Start all scraping operations concurrently
    tasks = [
        asyncio.create_task(mock_scrape_operation(i))
        for i in range(num_scrapes)
    ]
    
    # Wait for all scrapes to complete
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        pytest.fail(f"Scraping operations timed out. Max concurrent: {max_concurrent}, "
                   f"Completed: {sum(1 for r in results if not isinstance(r, Exception))}/{num_scrapes}")
    
    # Property verification: Maximum concurrent scrapes should never exceed 5
    assert max_concurrent <= 5, \
        f"Scrape concurrency limit violated: {max_concurrent} concurrent scrapes observed, " \
        f"but limit is 5. Requested {num_scrapes} scrapes. Observed counts: {observed_counts}"
    
    # Verify all scrapes completed successfully
    assert all(isinstance(r, str) and r.startswith('scrape_') for r in results), \
        f"Some scrapes failed: {[r for r in results if not isinstance(r, str)]}"
    
    # Verify final concurrent count is 0 (all completed)
    assert concurrent_count == 0, \
        f"Not all scrapes completed properly. Final concurrent count: {concurrent_count}"
    
    # Additional verification: At least some scrapes should have been queued
    # (if we requested more than 5, some must have waited)
    if num_scrapes > 5:
        # The max should be exactly 5 (or less if operations complete very quickly)
        assert max_concurrent >= min(5, num_scrapes), \
            f"Expected at least {min(5, num_scrapes)} concurrent scrapes, got {max_concurrent}"


@pytest.mark.asyncio
async def test_scrape_concurrency_limit_simple_example():
    """
    Simple example test to verify scrape concurrency limit with specific values
    
    This is a concrete example that demonstrates the property with known values.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    concurrent_count = 0
    max_concurrent = 0
    count_lock = asyncio.Lock()
    
    async def mock_scrape():
        """Mock scraping operation"""
        nonlocal concurrent_count, max_concurrent
        
        async with manager.scrape_semaphore:
            async with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            await asyncio.sleep(0.1)
            
            async with count_lock:
                concurrent_count -= 1
    
    # Start 10 scraping operations
    tasks = [asyncio.create_task(mock_scrape()) for _ in range(10)]
    
    # Wait for all to complete
    await asyncio.gather(*tasks)
    
    # Verify max concurrent was limited to 5
    assert max_concurrent <= 5, \
        f"Expected max 5 concurrent scrapes, got {max_concurrent}"
    
    # Verify all completed
    assert concurrent_count == 0, \
        f"Expected all scrapes to complete, but {concurrent_count} still running"


@pytest.mark.asyncio
async def test_scrape_concurrency_limit_with_manager_methods():
    """
    Test scrape concurrency limit using actual manager scraping methods
    
    Verifies that the manager's scraping methods respect the semaphore limit.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    # Track concurrent scrapes using the manager's counter
    max_observed = 0
    observations = []
    observation_lock = asyncio.Lock()
    
    # Mock the actual scraping by patching the session's scrape method
    async def mock_session_scrape(*args, **kwargs):
        """Mock session scrape that tracks concurrency"""
        nonlocal max_observed
        
        # Record current active scrape count
        async with observation_lock:
            current = manager.active_scrape_count
            observations.append(current)
            max_observed = max(max_observed, current)
        
        # Simulate scraping work
        await asyncio.sleep(0.1)
        
        return {
            'success': True,
            'file_path': '/tmp/test.csv',
            'members_count': 100
        }
    
    # Create mock sessions
    for i in range(3):
        session = TelegramSession(
            session_file=f'test_session_{i}.session',
            api_id=12345,
            api_hash='test_hash'
        )
        session.is_connected = True
        # Patch the scrape method
        session.scrape_group_members = mock_session_scrape
        manager.sessions[f'session_{i}'] = session
        manager.session_locks[f'session_{i}'] = asyncio.Lock()
    
    # Start 12 scraping operations (more than the limit of 5)
    tasks = []
    for i in range(12):
        task = asyncio.create_task(
            manager.scrape_group_members_random_session(f'group_{i}')
        )
        tasks.append(task)
    
    # Wait for all to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify max concurrent scrapes never exceeded 5
    assert max_observed <= 5, \
        f"Scrape concurrency limit violated: {max_observed} concurrent scrapes observed. " \
        f"All observations: {observations}"
    
    # Verify all scrapes completed
    assert all(isinstance(r, dict) for r in results), \
        f"Some scrapes failed: {[r for r in results if not isinstance(r, dict)]}"
    
    # Verify final count is 0
    assert manager.active_scrape_count == 0, \
        f"Expected active scrape count to be 0, got {manager.active_scrape_count}"


@pytest.mark.asyncio
async def test_scrape_semaphore_releases_on_error():
    """
    Test that scrape semaphore is released even when operations fail
    
    Verifies that failed scrapes don't leak semaphore slots.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    concurrent_count = 0
    max_concurrent = 0
    count_lock = asyncio.Lock()
    
    async def failing_scrape(should_fail: bool):
        """Mock scraping operation that may fail"""
        nonlocal concurrent_count, max_concurrent
        
        async with manager.scrape_semaphore:
            async with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            try:
                await asyncio.sleep(0.05)
                
                if should_fail:
                    raise Exception("Scrape failed")
            finally:
                async with count_lock:
                    concurrent_count -= 1
    
    # Start 10 operations, half will fail
    tasks = [
        asyncio.create_task(failing_scrape(i % 2 == 0))
        for i in range(10)
    ]
    
    # Wait for all to complete (with exceptions)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify max concurrent was still limited to 5
    assert max_concurrent <= 5, \
        f"Expected max 5 concurrent scrapes even with failures, got {max_concurrent}"
    
    # Verify semaphore was released (can acquire it 5 times)
    acquired = []
    for _ in range(5):
        acquired.append(await manager.scrape_semaphore.acquire())
    
    assert all(acquired), "Semaphore should be fully available after all operations complete"
    
    # Release all
    for _ in range(5):
        manager.scrape_semaphore.release()


@pytest.mark.asyncio
async def test_scrape_concurrency_with_varying_durations():
    """
    Test scrape concurrency limit with operations of varying durations
    
    Verifies that the limit holds even when operations complete at different times.
    """
    manager = TelegramSessionManager(max_concurrent_operations=10)
    
    concurrent_count = 0
    max_concurrent = 0
    count_lock = asyncio.Lock()
    
    async def variable_duration_scrape(duration: float):
        """Mock scraping operation with variable duration"""
        nonlocal concurrent_count, max_concurrent
        
        async with manager.scrape_semaphore:
            async with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            
            await asyncio.sleep(duration)
            
            async with count_lock:
                concurrent_count -= 1
    
    # Create operations with varying durations
    durations = [0.05, 0.1, 0.15, 0.2, 0.05, 0.1, 0.15, 0.2, 0.05, 0.1]
    tasks = [
        asyncio.create_task(variable_duration_scrape(d))
        for d in durations
    ]
    
    # Wait for all to complete
    await asyncio.gather(*tasks)
    
    # Verify max concurrent was limited to 5
    assert max_concurrent <= 5, \
        f"Expected max 5 concurrent scrapes with varying durations, got {max_concurrent}"
    
    # Verify all completed
    assert concurrent_count == 0, \
        f"Expected all scrapes to complete, but {concurrent_count} still running"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
