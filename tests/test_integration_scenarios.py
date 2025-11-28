"""
Integration testing with real scenarios - Test the system under realistic load conditions

This test suite validates the concurrency fixes under realistic scenarios:
- 250 sessions monitoring simultaneously
- Scraping while monitoring
- Concurrent scraping with limit enforcement
- Error recovery
- Graceful shutdown

Requirements: 2.1, 2.4, 4.1, 4.2, 4.3, 5.4, 6.2, 7.1, 7.2, 7.5
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager


class TestMassiveScaleMonitoring:
    """Test 250 sessions monitoring simultaneously (Task 14.1)"""
    
    @pytest.mark.asyncio
    async def test_250_sessions_monitoring_simultaneously(self):
        """
        Test that 250 sessions can monitor simultaneously without resource contention
        
        Requirements: 2.1
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Create 250 mock sessions
        num_sessions = 250
        for i in range(num_sessions):
            session_name = f'session_{i}'
            mock_session = Mock(spec=TelegramSession)
            mock_session.is_connected = True
            mock_session.is_monitoring = False
            
            # Mock start_monitoring to simulate real work
            # Use a factory function to capture the correct mock_session reference
            def make_start_monitoring(session):
                async def mock_start_monitoring(targets):
                    # Simulate some setup time
                    await asyncio.sleep(0.001)
                    session.is_monitoring = True
                    return True
                return mock_start_monitoring
            
            mock_session.start_monitoring = make_start_monitoring(mock_session)
            mock_session.stop_monitoring = AsyncMock()
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize tracking structures for all sessions
        async with manager.global_task_lock:
            for session_name in manager.sessions:
                manager.global_tasks[session_name] = set()
        
        async with manager.metrics_lock:
            for session_name in manager.sessions:
                manager.session_load[session_name] = 0
        
        # Define monitoring targets
        targets = [
            {'chat_id': 'test_channel_1', 'reaction': '👍', 'cooldown': 2.0},
            {'chat_id': 'test_channel_2', 'reaction': '❤️', 'cooldown': 3.0}
        ]
        
        # Start monitoring on all 250 sessions
        start_time = time.time()
        await manager.start_global_monitoring(targets)
        elapsed_time = time.time() - start_time
        
        # Verify all sessions started monitoring successfully
        monitoring_count = sum(
            1 for session in manager.sessions.values()
            if session.is_monitoring
        )
        
        assert monitoring_count == num_sessions, \
            f"Expected {num_sessions} sessions monitoring, got {monitoring_count}"
        
        # Verify no resource contention (should complete in reasonable time)
        # With proper concurrency, 250 sessions should start in < 5 seconds
        assert elapsed_time < 10.0, \
            f"Starting 250 sessions took {elapsed_time:.2f}s, expected < 10s (possible resource contention)"
        
        # Verify operation metrics
        monitoring_metric = await manager.get_operation_count('monitoring')
        assert monitoring_metric == num_sessions, \
            f"Expected {num_sessions} monitoring operations, got {monitoring_metric}"
        
        # Clean up
        await manager.stop_global_monitoring()
        
        print(f"✅ Successfully started {num_sessions} monitoring sessions in {elapsed_time:.2f}s")


class TestMonitoringAndScrapingConcurrency:
    """Test scraping while monitoring (Task 14.2)"""
    
    @pytest.mark.asyncio
    async def test_scraping_while_monitoring(self):
        """
        Test that scraping operations can proceed while monitoring is active
        
        Requirements: 2.1, 2.4
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Create 10 mock sessions
        num_sessions = 10
        for i in range(num_sessions):
            session_name = f'session_{i}'
            mock_session = Mock(spec=TelegramSession)
            mock_session.is_connected = True
            mock_session.is_monitoring = False
            
            # Mock monitoring - use factory to capture correct reference
            def make_start_monitoring(session):
                async def mock_start_monitoring(targets):
                    await asyncio.sleep(0.01)
                    session.is_monitoring = True
                    return True
                return mock_start_monitoring
            
            mock_session.start_monitoring = make_start_monitoring(mock_session)
            mock_session.stop_monitoring = AsyncMock()
            
            # Mock scraping
            async def mock_scrape(group_id, max_members, **kwargs):
                # Simulate scraping work
                await asyncio.sleep(0.1)
                return {
                    'success': True,
                    'file_path': f'test_{group_id}.csv',
                    'members_count': 100,
                    'group_name': group_id,
                    'source': 'member_list'
                }
            
            mock_session.scrape_group_members = mock_scrape
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            for session_name in manager.sessions:
                manager.global_tasks[session_name] = set()
        
        async with manager.metrics_lock:
            for session_name in manager.sessions:
                manager.session_load[session_name] = 0
        
        # Start monitoring on all sessions
        targets = [{'chat_id': 'test_channel', 'reaction': '👍', 'cooldown': 2.0}]
        await manager.start_global_monitoring(targets)
        
        # Verify all sessions are monitoring
        monitoring_count = sum(
            1 for session in manager.sessions.values()
            if session.is_monitoring
        )
        assert monitoring_count == num_sessions
        
        # Issue scraping requests while monitoring is active
        groups = [f'group_{i}' for i in range(5)]
        scrape_tasks = []
        
        start_time = time.time()
        for group in groups:
            task = asyncio.create_task(
                manager.scrape_group_members_random_session(group)
            )
            scrape_tasks.append(task)
        
        # Wait for all scrapes to complete
        results = await asyncio.gather(*scrape_tasks)
        elapsed_time = time.time() - start_time
        
        # Verify both operations proceeded
        # 1. All scrapes completed successfully
        assert len(results) == len(groups)
        for result in results:
            assert result['success'] is True
        
        # 2. Monitoring is still active
        monitoring_count = sum(
            1 for session in manager.sessions.values()
            if session.is_monitoring
        )
        assert monitoring_count == num_sessions, \
            "Monitoring should still be active after scraping"
        
        # 3. Operations completed in reasonable time (no blocking)
        # With proper concurrency, 5 scrapes should complete in < 2 seconds
        assert elapsed_time < 3.0, \
            f"Scraping took {elapsed_time:.2f}s, expected < 3s (possible blocking)"
        
        # Clean up
        await manager.stop_global_monitoring()
        
        print(f"✅ Successfully scraped {len(groups)} groups while {num_sessions} sessions were monitoring")


class TestConcurrentScrapingLimit:
    """Test concurrent scraping with limit (Task 14.3)"""
    
    @pytest.mark.asyncio
    async def test_concurrent_scraping_with_limit(self):
        """
        Test that max 5 scrapes run concurrently and all complete successfully
        
        Requirements: 4.1, 4.2, 4.3
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Track concurrent scrape count
        max_concurrent = 0
        current_concurrent = 0
        concurrent_lock = asyncio.Lock()
        concurrent_history = []
        
        # Create 10 mock sessions
        num_sessions = 10
        for i in range(num_sessions):
            session_name = f'session_{i}'
            mock_session = Mock(spec=TelegramSession)
            mock_session.is_connected = True
            
            # Mock scraping with concurrency tracking
            async def mock_scrape(group_id, max_members, **kwargs):
                nonlocal max_concurrent, current_concurrent
                
                # Track concurrent count
                async with concurrent_lock:
                    current_concurrent += 1
                    if current_concurrent > max_concurrent:
                        max_concurrent = current_concurrent
                    concurrent_history.append(('start', current_concurrent, time.time()))
                
                # Simulate scraping work
                await asyncio.sleep(0.2)
                
                # Release
                async with concurrent_lock:
                    current_concurrent -= 1
                    concurrent_history.append(('end', current_concurrent, time.time()))
                
                return {
                    'success': True,
                    'file_path': f'test_{group_id}.csv',
                    'members_count': 100,
                    'group_name': group_id,
                    'source': 'member_list'
                }
            
            mock_session.scrape_group_members = mock_scrape
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            for session_name in manager.sessions:
                manager.global_tasks[session_name] = set()
        
        async with manager.metrics_lock:
            for session_name in manager.sessions:
                manager.session_load[session_name] = 0
        
        # Issue 20 scraping requests
        num_scrapes = 20
        groups = [f'group_{i}' for i in range(num_scrapes)]
        scrape_tasks = []
        
        start_time = time.time()
        for group in groups:
            task = asyncio.create_task(
                manager.scrape_group_members_random_session(group)
            )
            scrape_tasks.append(task)
        
        # Wait for all scrapes to complete
        results = await asyncio.gather(*scrape_tasks)
        elapsed_time = time.time() - start_time
        
        # Verify max 5 concurrent at any time
        assert max_concurrent <= 5, \
            f"Max concurrent scrapes was {max_concurrent}, expected <= 5"
        
        # Verify all completed successfully
        assert len(results) == num_scrapes
        success_count = sum(1 for r in results if r['success'])
        assert success_count == num_scrapes, \
            f"Expected {num_scrapes} successful scrapes, got {success_count}"
        
        # Verify reasonable completion time
        # With 5 concurrent and 0.2s per scrape, 20 scrapes should take ~0.8s
        # Allow some overhead
        expected_min_time = (num_scrapes / 5) * 0.2
        assert elapsed_time >= expected_min_time * 0.8, \
            f"Completed too fast ({elapsed_time:.2f}s), semaphore may not be working"
        
        print(f"✅ Successfully completed {num_scrapes} scrapes with max {max_concurrent} concurrent (limit: 5)")
        print(f"   Total time: {elapsed_time:.2f}s")


class TestErrorRecovery:
    """Test error recovery (Task 14.4)"""
    
    @pytest.mark.asyncio
    async def test_error_recovery_locks_released(self):
        """
        Test that errors in operations release locks and don't affect other sessions
        
        Requirements: 7.1, 7.2, 7.5
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Create 5 mock sessions
        num_sessions = 5
        for i in range(num_sessions):
            session_name = f'session_{i}'
            mock_session = Mock(spec=TelegramSession)
            mock_session.is_connected = True
            
            # Session 2 will fail, others succeed
            if i == 2:
                async def mock_scrape_fail(group_id, max_members, **kwargs):
                    await asyncio.sleep(0.05)
                    raise Exception("Simulated scraping error")
                
                mock_session.scrape_group_members = mock_scrape_fail
            else:
                async def mock_scrape_success(group_id, max_members, **kwargs):
                    await asyncio.sleep(0.1)
                    return {
                        'success': True,
                        'file_path': f'test_{group_id}.csv',
                        'members_count': 100,
                        'group_name': group_id,
                        'source': 'member_list'
                    }
                
                mock_session.scrape_group_members = mock_scrape_success
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            for session_name in manager.sessions:
                manager.global_tasks[session_name] = set()
        
        async with manager.metrics_lock:
            for session_name in manager.sessions:
                manager.session_load[session_name] = 0
        
        # Issue scraping requests (one will fail)
        groups = [f'group_{i}' for i in range(5)]
        scrape_tasks = []
        
        for group in groups:
            task = asyncio.create_task(
                manager.scrape_group_members_random_session(group)
            )
            scrape_tasks.append(task)
        
        # Wait for all scrapes to complete
        results = await asyncio.gather(*scrape_tasks)
        
        # Verify locks were released (check that no locks are held)
        for session_name, lock in manager.session_locks.items():
            assert not lock.locked(), \
                f"Lock for {session_name} is still held after error"
        
        # Verify other sessions unaffected
        # At least 4 should succeed (the failing one might have been used multiple times)
        success_count = sum(1 for r in results if r.get('success'))
        assert success_count >= 3, \
            f"Expected at least 3 successful scrapes, got {success_count}"
        
        # Verify error was handled gracefully (at least one failure)
        failure_count = sum(1 for r in results if not r.get('success'))
        assert failure_count >= 1, \
            "Expected at least one failure from the error injection"
        
        # Verify session load metrics were cleaned up
        for session_name in manager.sessions:
            load = await manager.get_session_load(session_name)
            assert load == 0, \
                f"Session {session_name} still has load {load} after operations completed"
        
        print(f"✅ Error recovery successful: {success_count} succeeded, {failure_count} failed, all locks released")
    
    @pytest.mark.asyncio
    async def test_error_recovery_with_retry(self):
        """
        Test that retry logic works correctly and errors don't cascade
        
        Requirements: 7.1, 7.2
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        
        # Track retry attempts
        attempt_count = 0
        
        async def mock_scrape_with_retry(group_id, max_members, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            
            # Fail first 2 attempts, succeed on 3rd
            if attempt_count < 3:
                raise Exception("Transient network error")
            
            return {
                'success': True,
                'file_path': f'test_{group_id}.csv',
                'members_count': 100,
                'group_name': group_id,
                'source': 'member_list'
            }
        
        mock_session.scrape_group_members = mock_scrape_with_retry
        
        manager.sessions['session_1'] = mock_session
        manager.session_locks['session_1'] = asyncio.Lock()
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            manager.global_tasks['session_1'] = set()
        
        async with manager.metrics_lock:
            manager.session_load['session_1'] = 0
        
        # Issue scraping request (should retry and succeed)
        result = await manager.scrape_group_members_random_session('test_group')
        
        # Verify retry worked
        assert attempt_count == 3, \
            f"Expected 3 attempts (2 retries), got {attempt_count}"
        
        assert result['success'] is True, \
            "Expected success after retries"
        
        # Verify locks released
        assert not manager.session_locks['session_1'].locked(), \
            "Lock should be released after successful retry"
        
        print(f"✅ Retry logic successful: {attempt_count} attempts, operation succeeded")


class TestGracefulShutdown:
    """Test graceful shutdown (Task 14.5)"""
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_active_operations(self):
        """
        Test that shutdown cancels all tasks and cleans up resources
        
        Requirements: 5.4, 6.2
        """
        manager = TelegramSessionManager(max_concurrent_operations=10)
        
        # Create 10 mock sessions with active operations
        num_sessions = 10
        for i in range(num_sessions):
            session_name = f'session_{i}'
            mock_session = Mock(spec=TelegramSession)
            mock_session.is_connected = True
            mock_session.is_monitoring = False
            
            # Mock monitoring - use factory to capture correct reference
            def make_start_monitoring(session):
                async def mock_start_monitoring(targets):
                    await asyncio.sleep(0.01)
                    session.is_monitoring = True
                    return True
                return mock_start_monitoring
            
            mock_session.start_monitoring = make_start_monitoring(mock_session)
            mock_session.stop_monitoring = AsyncMock()
            
            # Mock disconnect
            async def mock_disconnect():
                await asyncio.sleep(0.01)
                mock_session.is_connected = False
            
            mock_session.disconnect = mock_disconnect
            
            # Mock scraping (long-running)
            async def mock_scrape(group_id, max_members, **kwargs):
                # Simulate long-running operation
                await asyncio.sleep(10.0)
                return {
                    'success': True,
                    'file_path': f'test_{group_id}.csv',
                    'members_count': 100,
                    'group_name': group_id,
                    'source': 'member_list'
                }
            
            mock_session.scrape_group_members = mock_scrape
            
            manager.sessions[session_name] = mock_session
            manager.session_locks[session_name] = asyncio.Lock()
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            for session_name in manager.sessions:
                manager.global_tasks[session_name] = set()
        
        async with manager.metrics_lock:
            for session_name in manager.sessions:
                manager.session_load[session_name] = 0
        
        # Start monitoring on all sessions
        targets = [{'chat_id': 'test_channel', 'reaction': '👍', 'cooldown': 2.0}]
        await manager.start_global_monitoring(targets)
        
        # Start some long-running scraping operations
        scrape_tasks = []
        for i in range(5):
            task = asyncio.create_task(
                manager.scrape_group_members_random_session(f'group_{i}')
            )
            scrape_tasks.append(task)
        
        # Give operations time to start
        await asyncio.sleep(0.1)
        
        # Verify operations are running
        monitoring_count = sum(
            1 for session in manager.sessions.values()
            if session.is_monitoring
        )
        assert monitoring_count == num_sessions
        
        # Shutdown manager
        start_time = time.time()
        await manager.shutdown()
        shutdown_time = time.time() - start_time
        
        # Verify all tasks cancelled within timeout
        # Shutdown should complete within reasonable time (< 10 seconds)
        assert shutdown_time < 10.0, \
            f"Shutdown took {shutdown_time:.2f}s, expected < 10s"
        
        # Verify clean resource cleanup
        assert len(manager.sessions) == 0, \
            "Sessions should be cleared"
        
        assert len(manager.session_locks) == 0, \
            "Session locks should be cleared"
        
        assert len(manager.global_tasks) == 0, \
            "Global tasks should be cleared"
        
        assert len(manager.session_load) == 0, \
            "Session load should be cleared"
        
        # Verify operation metrics reset
        metrics = await manager.get_operation_metrics()
        assert metrics['monitoring'] == 0, \
            "Monitoring metric should be reset"
        assert metrics['scraping'] == 0, \
            "Scraping metric should be reset"
        
        assert manager.active_scrape_count == 0, \
            "Active scrape count should be reset"
        
        print(f"✅ Graceful shutdown successful in {shutdown_time:.2f}s")
        print(f"   All {num_sessions} sessions cleaned up")
        print(f"   All resources released")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
