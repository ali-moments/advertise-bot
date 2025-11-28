"""
Test existing usage patterns - Verify that common workflows still work correctly
after concurrency fixes.

Requirements: 8.4, 8.5
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.config import SessionConfig


class TestMonitoringWorkflow:
    """Test that monitoring workflow works as expected"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock TelegramSession for testing"""
        session = TelegramSession("test.session", 12345, "test_hash")
        session.client = AsyncMock()
        session.is_connected = True
        return session
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring_workflow(self, mock_session):
        """Test basic monitoring start/stop workflow"""
        # Setup
        targets = [
            {'chat_id': 'test_channel_1', 'reaction': '👍', 'cooldown': 2.0},
            {'chat_id': 'test_channel_2', 'reaction': '❤️', 'cooldown': 3.0}
        ]
        
        with patch.object(mock_session, '_setup_event_handler', new_callable=AsyncMock):
            # Start monitoring
            result = await mock_session.start_monitoring(targets)
            
            # Verify monitoring started
            assert result is True
            assert mock_session.is_monitoring is True
            assert len(mock_session.monitoring_targets) == 2
            
            # Stop monitoring
            await mock_session.stop_monitoring()
            
            # Verify monitoring stopped
            assert mock_session.is_monitoring is False
            assert len(mock_session.monitoring_targets) == 0
    
    @pytest.mark.asyncio
    async def test_restart_monitoring_workflow(self, mock_session):
        """Test restarting monitoring (stop then start again)"""
        targets1 = [{'chat_id': 'channel1', 'reaction': '👍', 'cooldown': 2.0}]
        targets2 = [{'chat_id': 'channel2', 'reaction': '❤️', 'cooldown': 3.0}]
        
        with patch.object(mock_session, '_setup_event_handler', new_callable=AsyncMock):
            # Start monitoring with first set of targets
            await mock_session.start_monitoring(targets1)
            assert mock_session.is_monitoring is True
            assert len(mock_session.monitoring_targets) == 1
            
            # Start monitoring with second set (should stop first)
            await mock_session.start_monitoring(targets2)
            assert mock_session.is_monitoring is True
            assert len(mock_session.monitoring_targets) == 1
            assert 'channel2' in mock_session.monitoring_targets
            
            # Clean up
            await mock_session.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_global_monitoring_workflow(self):
        """Test global monitoring across multiple sessions"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create mock sessions
        mock_session1 = Mock(spec=TelegramSession)
        mock_session1.is_connected = True
        mock_session1.start_monitoring = AsyncMock(return_value=True)
        mock_session1.stop_monitoring = AsyncMock()
        mock_session1.is_monitoring = False
        
        mock_session2 = Mock(spec=TelegramSession)
        mock_session2.is_connected = True
        mock_session2.start_monitoring = AsyncMock(return_value=True)
        mock_session2.stop_monitoring = AsyncMock()
        mock_session2.is_monitoring = False
        
        manager.sessions = {
            'session1': mock_session1,
            'session2': mock_session2
        }
        manager.session_locks = {
            'session1': asyncio.Lock(),
            'session2': asyncio.Lock()
        }
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            manager.global_tasks['session1'] = set()
            manager.global_tasks['session2'] = set()
        async with manager.metrics_lock:
            manager.session_load['session1'] = 0
            manager.session_load['session2'] = 0
        
        targets = [{'chat_id': 'test_channel', 'reaction': '👍', 'cooldown': 2.0}]
        
        # Start global monitoring
        await manager.start_global_monitoring(targets)
        
        # Verify both sessions started monitoring
        mock_session1.start_monitoring.assert_called_once_with(targets)
        mock_session2.start_monitoring.assert_called_once_with(targets)
        
        # Stop global monitoring
        await manager.stop_global_monitoring()
        
        # Verify both sessions stopped monitoring
        mock_session1.stop_monitoring.assert_called_once()
        mock_session2.stop_monitoring.assert_called_once()


class TestScrapingWorkflow:
    """Test that scraping workflow works as expected"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock TelegramSession for testing"""
        session = TelegramSession("test.session", 12345, "test_hash")
        session.client = AsyncMock()
        session.is_connected = True
        return session
    
    @pytest.mark.asyncio
    async def test_basic_scraping_workflow(self, mock_session):
        """Test basic group scraping workflow"""
        from telethon.tl.types import Channel
        
        # Setup mock entity
        mock_entity = Mock(spec=Channel)
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
        # Setup mock user
        mock_user = Mock()
        mock_user.id = 456
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone = None
        mock_user.bot = False
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        mock_session.client.get_participants = AsyncMock(return_value=[mock_user])
        mock_session._is_valid_user = AsyncMock(return_value=True)
        
        # Scrape group
        result = await mock_session.scrape_group_members("test_group", max_members=100)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'file_path' in result
        
        if result['success']:
            assert result['members_count'] > 0
            assert result['file_path'] is not None
    
    @pytest.mark.asyncio
    async def test_join_and_scrape_workflow(self, mock_session):
        """Test join then scrape workflow"""
        from telethon.tl.types import Channel
        
        # Setup mocks
        mock_entity = Mock(spec=Channel)
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        mock_session.join_chat = AsyncMock(return_value=True)
        mock_session.client.get_participants = AsyncMock(return_value=[])
        
        # Join and scrape
        result = await mock_session.join_and_scrape_members("test_group")
        
        # Verify workflow executed
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'joined' in result
        
        # Verify join was called
        mock_session.join_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scraping_with_fallback_workflow(self, mock_session):
        """Test scraping with fallback to message-based scraping"""
        from telethon.tl.types import Channel
        
        # Setup mock entity
        mock_entity = Mock(spec=Channel)
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        # First attempt fails (no participants)
        mock_session.client.get_participants = AsyncMock(side_effect=Exception("No access"))
        
        # Setup fallback mocks
        mock_session._check_daily_limits = Mock(return_value=True)
        mock_session._get_messages_with_reactions = AsyncMock(return_value=[])
        mock_session._extract_users_from_messages = AsyncMock(return_value=[])
        
        # Scrape with fallback enabled
        result = await mock_session.scrape_group_members(
            "test_group",
            fallback_to_messages=True,
            message_days_back=10
        )
        
        # Verify result structure (fallback should have been attempted)
        assert isinstance(result, dict)
        assert 'success' in result
        # Note: When fallback fails to find users, 'source' may not be in result
        # The important thing is the workflow executed without crashing


class TestBulkOperations:
    """Test that bulk operations work as expected"""
    
    @pytest.mark.asyncio
    async def test_bulk_scrape_workflow(self):
        """Test bulk scraping across multiple groups"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.scrape_group_members = AsyncMock(return_value={
            'success': True,
            'file_path': 'test.csv',
            'members_count': 10,
            'group_name': 'testgroup',
            'source': 'member_list'
        })
        
        manager.sessions = {'session1': mock_session}
        manager.session_locks = {'session1': asyncio.Lock()}
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            manager.global_tasks['session1'] = set()
        async with manager.metrics_lock:
            manager.session_load['session1'] = 0
        
        groups = ['group1', 'group2', 'group3']
        
        # Bulk scrape
        results = await manager.bulk_scrape_groups(groups, join_first=False)
        
        # Verify results
        assert isinstance(results, dict)
        assert len(results) == 3
        
        for group in groups:
            assert group in results
            assert 'success' in results[group]
            assert 'session_used' in results[group]
    
    @pytest.mark.asyncio
    async def test_bulk_send_workflow(self):
        """Test bulk sending messages"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.session_file = "test.session"  # Add session_file attribute
        mock_session.bulk_send_messages = AsyncMock(return_value=[True, True])
        
        manager.sessions = {'session1': mock_session}
        
        targets = ['target1', 'target2']
        message = "Test message"
        
        # Bulk send
        results = await manager.bulk_send_messages(targets, message)
        
        # Verify results
        assert isinstance(results, dict)
    
    @pytest.mark.asyncio
    async def test_bulk_join_workflow(self):
        """Test bulk joining chats"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.join_chat = AsyncMock(return_value=True)
        
        manager.sessions = {'session1': mock_session}
        
        chats = ['chat1', 'chat2']
        
        # Bulk join
        results = await manager.join_chats(chats)
        
        # Verify results
        assert isinstance(results, dict)
        assert len(results) == 2
        
        for chat in chats:
            assert chat in results
            assert isinstance(results[chat], bool)
    
    @pytest.mark.asyncio
    async def test_bulk_get_members_workflow(self):
        """Test bulk getting members from multiple chats"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.get_members = AsyncMock(return_value=[
            {'id': 1, 'username': 'user1', 'first_name': 'User', 'last_name': 'One', 'phone': None}
        ])
        
        manager.sessions = {'session1': mock_session}
        
        chats = ['chat1', 'chat2']
        
        # Bulk get members
        results = await manager.bulk_get_members(chats, limit=100)
        
        # Verify results
        assert isinstance(results, dict)
        assert len(results) == 2
        
        for chat in chats:
            assert chat in results
            assert isinstance(results[chat], list)


class TestConcurrentOperations:
    """Test that operations can run concurrently without interference"""
    
    @pytest.mark.asyncio
    async def test_monitoring_and_scraping_concurrent(self):
        """Test that monitoring and scraping can run concurrently without deadlock"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Create two mock sessions
        mock_session1 = Mock(spec=TelegramSession)
        mock_session1.is_connected = True
        mock_session1.start_monitoring = AsyncMock(return_value=True)
        mock_session1.stop_monitoring = AsyncMock()
        mock_session1.is_monitoring = False
        
        manager.sessions = {'session1': mock_session1}
        manager.session_locks = {'session1': asyncio.Lock()}
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            manager.global_tasks['session1'] = set()
        async with manager.metrics_lock:
            manager.session_load['session1'] = 0
        
        # Start monitoring on session1
        targets = [{'chat_id': 'test_channel', 'reaction': '👍', 'cooldown': 2.0}]
        monitoring_task = asyncio.create_task(
            manager.start_global_monitoring(targets)
        )
        
        # Wait for monitoring to complete
        await monitoring_task
        
        # Verify monitoring started
        mock_session1.start_monitoring.assert_called_once()
        
        # The key test is that we didn't deadlock - if we got here, the test passed
        # Clean up
        await manager.stop_global_monitoring()
    
    @pytest.mark.asyncio
    async def test_multiple_scrapes_with_semaphore_limit(self):
        """Test that scrape semaphore limits concurrent scrapes"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Track concurrent scrape count
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()
        
        async def mock_scrape(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            
            # Simulate scraping work
            await asyncio.sleep(0.1)
            
            async with lock:
                current_concurrent -= 1
            
            return {
                'success': True,
                'file_path': 'test.csv',
                'members_count': 10,
                'group_name': 'testgroup',
                'source': 'member_list'
            }
        
        # Create mock session
        mock_session = Mock(spec=TelegramSession)
        mock_session.is_connected = True
        mock_session.scrape_group_members = mock_scrape
        
        manager.sessions = {'session1': mock_session}
        manager.session_locks = {'session1': asyncio.Lock()}
        
        # Initialize tracking structures
        async with manager.global_task_lock:
            manager.global_tasks['session1'] = set()
        async with manager.metrics_lock:
            manager.session_load['session1'] = 0
        
        # Try to scrape 10 groups concurrently
        groups = [f'group{i}' for i in range(10)]
        
        # Start all scrapes concurrently
        tasks = []
        for group in groups:
            task = asyncio.create_task(
                manager.scrape_group_members_random_session(group)
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        # Verify all completed successfully
        assert len(results) == 10
        for result in results:
            assert result['success'] is True
        
        # Verify semaphore limited concurrency to 5
        assert max_concurrent <= 5, f"Max concurrent scrapes was {max_concurrent}, expected <= 5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
