"""
Test API compatibility - Verify that all public method signatures remain unchanged
after concurrency fixes.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import pytest
import inspect
import asyncio
from typing import Dict, List, Optional
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager


class TestTelegramSessionAPISignatures:
    """Test that TelegramSession public method signatures are unchanged"""
    
    def test_init_signature(self):
        """Verify __init__ signature"""
        sig = inspect.signature(TelegramSession.__init__)
        params = list(sig.parameters.keys())
        
        # Expected parameters
        assert 'self' in params
        assert 'session_file' in params
        assert 'api_id' in params
        assert 'api_hash' in params
        assert len(params) == 4, f"Expected 4 parameters, got {len(params)}: {params}"
    
    def test_connect_signature(self):
        """Verify connect signature"""
        sig = inspect.signature(TelegramSession.connect)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty
    
    def test_disconnect_signature(self):
        """Verify disconnect signature"""
        sig = inspect.signature(TelegramSession.disconnect)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
    
    def test_start_monitoring_signature(self):
        """Verify start_monitoring signature"""
        sig = inspect.signature(TelegramSession.start_monitoring)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert len(params) == 2
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty
    
    def test_stop_monitoring_signature(self):
        """Verify stop_monitoring signature"""
        sig = inspect.signature(TelegramSession.stop_monitoring)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
    
    def test_send_message_signature(self):
        """Verify send_message signature"""
        sig = inspect.signature(TelegramSession.send_message)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert 'message' in params
        assert 'reply_to' in params
        assert len(params) == 4
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty
    
    def test_join_chat_signature(self):
        """Verify join_chat signature"""
        sig = inspect.signature(TelegramSession.join_chat)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert len(params) == 2
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty
    
    def test_get_members_signature(self):
        """Verify get_members signature"""
        sig = inspect.signature(TelegramSession.get_members)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert 'limit' in params
        assert len(params) == 3
    
    def test_bulk_send_messages_signature(self):
        """Verify bulk_send_messages signature"""
        sig = inspect.signature(TelegramSession.bulk_send_messages)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert 'message' in params
        assert 'delay' in params
        assert len(params) == 4
    
    def test_get_status_signature(self):
        """Verify get_status signature"""
        sig = inspect.signature(TelegramSession.get_status)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_scrape_group_members_signature(self):
        """Verify scrape_group_members signature"""
        sig = inspect.signature(TelegramSession.scrape_group_members)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'group_identifier' in params
        assert 'max_members' in params
        assert 'fallback_to_messages' in params
        assert 'message_days_back' in params
        assert len(params) == 5
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_join_and_scrape_members_signature(self):
        """Verify join_and_scrape_members signature"""
        sig = inspect.signature(TelegramSession.join_and_scrape_members)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'group_identifier' in params
        assert 'max_members' in params
        assert len(params) == 3
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_scrape_members_from_messages_signature(self):
        """Verify scrape_members_from_messages signature"""
        sig = inspect.signature(TelegramSession.scrape_members_from_messages)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'group_identifier' in params
        assert 'days_back' in params
        assert 'limit_messages' in params
        assert len(params) == 4
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_extract_group_links_signature(self):
        """Verify extract_group_links signature"""
        sig = inspect.signature(TelegramSession.extract_group_links)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert 'limit_messages' in params
        assert len(params) == 3
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_check_target_type_signature(self):
        """Verify check_target_type signature"""
        sig = inspect.signature(TelegramSession.check_target_type)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert len(params) == 2
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_bulk_check_targets_signature(self):
        """Verify bulk_check_targets signature"""
        sig = inspect.signature(TelegramSession.bulk_check_targets)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert len(params) == 2


class TestTelegramSessionManagerAPISignatures:
    """Test that TelegramSessionManager public method signatures are unchanged"""
    
    def test_init_signature(self):
        """Verify __init__ signature"""
        sig = inspect.signature(TelegramSessionManager.__init__)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'max_concurrent_operations' in params
        assert len(params) == 2
    
    def test_load_sessions_signature(self):
        """Verify load_sessions signature"""
        sig = inspect.signature(TelegramSessionManager.load_sessions)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'session_configs' in params
        assert len(params) == 2
    
    def test_load_sessions_from_db_signature(self):
        """Verify load_sessions_from_db signature"""
        sig = inspect.signature(TelegramSessionManager.load_sessions_from_db)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
    
    def test_start_global_monitoring_signature(self):
        """Verify start_global_monitoring signature"""
        sig = inspect.signature(TelegramSessionManager.start_global_monitoring)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert len(params) == 2
    
    def test_stop_global_monitoring_signature(self):
        """Verify stop_global_monitoring signature"""
        sig = inspect.signature(TelegramSessionManager.stop_global_monitoring)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
    
    def test_bulk_send_messages_signature(self):
        """Verify bulk_send_messages signature"""
        sig = inspect.signature(TelegramSessionManager.bulk_send_messages)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert 'message' in params
        assert 'delay' in params
        assert len(params) == 4
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_bulk_get_members_signature(self):
        """Verify bulk_get_members signature"""
        sig = inspect.signature(TelegramSessionManager.bulk_get_members)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'chats' in params
        assert 'limit' in params
        assert len(params) == 3
    
    def test_join_chats_signature(self):
        """Verify join_chats signature"""
        sig = inspect.signature(TelegramSessionManager.join_chats)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'chats' in params
        assert len(params) == 2
    
    def test_get_session_stats_signature(self):
        """Verify get_session_stats signature"""
        sig = inspect.signature(TelegramSessionManager.get_session_stats)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_get_session_signature(self):
        """Verify get_session signature"""
        sig = inspect.signature(TelegramSessionManager.get_session)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'name' in params
        assert len(params) == 2
    
    def test_shutdown_signature(self):
        """Verify shutdown signature"""
        sig = inspect.signature(TelegramSessionManager.shutdown)
        params = list(sig.parameters.keys())
        
        assert params == ['self']
    
    def test_scrape_group_members_random_session_signature(self):
        """Verify scrape_group_members_random_session signature"""
        sig = inspect.signature(TelegramSessionManager.scrape_group_members_random_session)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'group_identifier' in params
        assert 'max_members' in params
        assert 'fallback_to_messages' in params
        assert 'message_days_back' in params
        assert len(params) == 5
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_bulk_scrape_groups_signature(self):
        """Verify bulk_scrape_groups signature"""
        sig = inspect.signature(TelegramSessionManager.bulk_scrape_groups)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'groups' in params
        assert 'join_first' in params
        assert 'max_members' in params
        assert len(params) == 4
    
    def test_extract_links_from_channels_signature(self):
        """Verify extract_links_from_channels signature"""
        sig = inspect.signature(TelegramSessionManager.extract_links_from_channels)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'channels' in params
        assert 'limit_messages' in params
        assert len(params) == 3
    
    def test_check_target_type_signature(self):
        """Verify check_target_type signature"""
        sig = inspect.signature(TelegramSessionManager.check_target_type)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'target' in params
        assert len(params) == 2
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty
    
    def test_bulk_check_targets_signature(self):
        """Verify bulk_check_targets signature"""
        sig = inspect.signature(TelegramSessionManager.bulk_check_targets)
        params = list(sig.parameters.keys())
        
        assert 'self' in params
        assert 'targets' in params
        assert len(params) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
