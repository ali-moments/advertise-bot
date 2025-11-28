"""
Test API return value structures - Verify that return values maintain the same structure
after concurrency fixes.

Requirements: 8.3, 8.5
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager


class TestTelegramSessionReturnValues:
    """Test that TelegramSession return values maintain expected structure"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock TelegramSession for testing"""
        session = TelegramSession("test.session", 12345, "test_hash")
        session.client = AsyncMock()
        session.is_connected = True
        return session
    
    @pytest.mark.asyncio
    async def test_connect_returns_bool(self, mock_session):
        """Verify connect returns bool"""
        with patch.object(mock_session, 'client') as mock_client:
            mock_client.start = AsyncMock()
            result = await mock_session.connect()
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_start_monitoring_returns_bool(self, mock_session):
        """Verify start_monitoring returns bool"""
        targets = [{'chat_id': 'test', 'reaction': '👍', 'cooldown': 2.0}]
        
        with patch.object(mock_session, '_setup_event_handler', new_callable=AsyncMock):
            result = await mock_session.start_monitoring(targets)
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_send_message_returns_bool(self, mock_session):
        """Verify send_message returns bool"""
        mock_session.client.get_entity = AsyncMock(return_value=Mock())
        mock_session.client.send_message = AsyncMock()
        
        result = await mock_session.send_message("test_target", "test message")
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_join_chat_returns_bool(self, mock_session):
        """Verify join_chat returns bool"""
        mock_session.client.get_entity = AsyncMock(return_value=Mock())
        
        with patch('telegram_manager.session.JoinChannelRequest'):
            result = await mock_session.join_chat("test_target")
            assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_get_members_returns_list(self, mock_session):
        """Verify get_members returns list of dicts"""
        mock_user = Mock()
        mock_user.id = 123
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone = None
        
        mock_session.client.get_entity = AsyncMock(return_value=Mock())
        mock_session.client.get_participants = AsyncMock(return_value=[mock_user])
        
        result = await mock_session.get_members("test_target", limit=10)
        
        assert isinstance(result, list)
        if len(result) > 0:
            assert isinstance(result[0], dict)
            assert 'id' in result[0]
            assert 'username' in result[0]
            assert 'first_name' in result[0]
            assert 'last_name' in result[0]
            assert 'phone' in result[0]
    
    def test_get_status_returns_dict(self, mock_session):
        """Verify get_status returns dict with expected keys"""
        result = mock_session.get_status()
        
        assert isinstance(result, dict)
        assert 'connected' in result
        assert 'monitoring' in result
        assert 'monitoring_targets_count' in result
        assert 'active_tasks' in result
        
        assert isinstance(result['connected'], bool)
        assert isinstance(result['monitoring'], bool)
        assert isinstance(result['monitoring_targets_count'], int)
        assert isinstance(result['active_tasks'], int)
    
    @pytest.mark.asyncio
    async def test_scrape_group_members_returns_dict(self, mock_session):
        """Verify scrape_group_members returns dict with expected structure"""
        from telethon.tl.types import Channel
        
        mock_entity = Mock(spec=Channel)
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
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
        
        result = await mock_session.scrape_group_members("test_group")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert isinstance(result['success'], bool)
        
        if result['success']:
            assert 'file_path' in result
            assert 'members_count' in result
            assert 'group_name' in result
            assert 'source' in result
        else:
            assert 'error' in result
            assert 'file_path' in result
    
    @pytest.mark.asyncio
    async def test_join_and_scrape_members_returns_dict(self, mock_session):
        """Verify join_and_scrape_members returns dict with expected structure"""
        from telethon.tl.types import Channel
        
        mock_entity = Mock(spec=Channel)
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        mock_session.join_chat = AsyncMock(return_value=True)
        mock_session.client.get_participants = AsyncMock(return_value=[])
        
        result = await mock_session.join_and_scrape_members("test_group")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'joined' in result
        assert isinstance(result['success'], bool)
        assert isinstance(result['joined'], bool)
        
        if result['success']:
            assert 'file_path' in result
        else:
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_scrape_members_from_messages_returns_dict(self, mock_session):
        """Verify scrape_members_from_messages returns dict with expected structure"""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.username = "testgroup"
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        mock_session._check_daily_limits = Mock(return_value=True)
        mock_session._get_messages_with_reactions = AsyncMock(return_value=[])
        mock_session._extract_users_from_messages = AsyncMock(return_value=[])
        
        result = await mock_session.scrape_members_from_messages("test_group")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'file_path' in result
        assert 'members_count' in result
        assert isinstance(result['success'], bool)
        assert isinstance(result['members_count'], int)
    
    @pytest.mark.asyncio
    async def test_extract_group_links_returns_dict(self, mock_session):
        """Verify extract_group_links returns dict with expected structure"""
        mock_entity = Mock()
        mock_entity.id = 123
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        mock_session._extract_links_from_messages = AsyncMock(return_value=[])
        mock_session._filter_telegram_links = Mock(return_value=[])
        
        result = await mock_session.extract_group_links("test_channel")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'source_channel' in result
        assert 'telegram_links' in result
        assert 'telegram_links_count' in result
        assert isinstance(result['success'], bool)
        assert isinstance(result['telegram_links'], list)
        assert isinstance(result['telegram_links_count'], int)
    
    @pytest.mark.asyncio
    async def test_check_target_type_returns_dict(self, mock_session):
        """Verify check_target_type returns dict with expected structure"""
        from telethon.tl.types import Channel
        
        mock_entity = Mock(spec=Channel)
        mock_entity.title = "Test Group"
        mock_entity.username = "testgroup"
        mock_entity.participants_count = 100
        mock_entity.megagroup = True
        mock_entity.broadcast = False
        
        mock_session.client.get_entity = AsyncMock(return_value=mock_entity)
        
        result = await mock_session.check_target_type("test_target")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'target' in result
        assert 'type' in result
        assert 'scrapable' in result
        assert 'reason' in result
        assert isinstance(result['success'], bool)
        assert isinstance(result['scrapable'], bool)


class TestTelegramSessionManagerReturnValues:
    """Test that TelegramSessionManager return values maintain expected structure"""
    
    @pytest.fixture
    def mock_manager(self):
        """Create a mock TelegramSessionManager for testing"""
        manager = TelegramSessionManager(max_concurrent_operations=3)
        return manager
    
    @pytest.mark.asyncio
    async def test_load_sessions_returns_dict(self, mock_manager):
        """Verify load_sessions returns dict mapping names to bool"""
        result = await mock_manager.load_sessions([])
        
        assert isinstance(result, dict)
        # Empty list should return empty dict
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_bulk_send_messages_returns_dict(self, mock_manager):
        """Verify bulk_send_messages returns dict"""
        result = await mock_manager.bulk_send_messages([], "test message")
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_bulk_get_members_returns_dict(self, mock_manager):
        """Verify bulk_get_members returns dict mapping chats to member lists"""
        result = await mock_manager.bulk_get_members([])
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_join_chats_returns_dict(self, mock_manager):
        """Verify join_chats returns dict mapping chats to bool"""
        result = await mock_manager.join_chats([])
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_get_session_stats_returns_dict(self, mock_manager):
        """Verify get_session_stats returns dict"""
        result = await mock_manager.get_session_stats()
        
        assert isinstance(result, dict)
    
    def test_get_session_returns_optional_session(self, mock_manager):
        """Verify get_session returns TelegramSession or None"""
        result = mock_manager.get_session("nonexistent")
        
        assert result is None or isinstance(result, TelegramSession)
    
    @pytest.mark.asyncio
    async def test_scrape_group_members_random_session_returns_dict(self, mock_manager):
        """Verify scrape_group_members_random_session returns dict with expected structure"""
        result = await mock_manager.scrape_group_members_random_session("test_group")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'file_path' in result
        assert 'session_used' in result
        assert isinstance(result['success'], bool)
        
        if not result['success']:
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_bulk_scrape_groups_returns_dict(self, mock_manager):
        """Verify bulk_scrape_groups returns dict mapping groups to results"""
        result = await mock_manager.bulk_scrape_groups([])
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_extract_links_from_channels_returns_dict(self, mock_manager):
        """Verify extract_links_from_channels returns dict"""
        result = await mock_manager.extract_links_from_channels([])
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_check_target_type_returns_dict(self, mock_manager):
        """Verify check_target_type returns dict with expected structure"""
        result = await mock_manager.check_target_type("test_target")
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'target' in result
        assert 'scrapable' in result
        assert isinstance(result['success'], bool)
        assert isinstance(result['scrapable'], bool)
    
    @pytest.mark.asyncio
    async def test_bulk_check_targets_returns_dict(self, mock_manager):
        """Verify bulk_check_targets returns dict"""
        result = await mock_manager.bulk_check_targets([])
        
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
