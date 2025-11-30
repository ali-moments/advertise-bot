"""
Property-Based Test for API Compatibility

**Feature: telegram-concurrency-fix, Property 7: API compatibility**

Tests that for any existing public method call with valid parameters, 
the method signature, return type, and return value structure remain 
identical after applying concurrency fixes.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
"""

import asyncio
import pytest
import inspect
from typing import Dict, List, Optional, Any
from hypothesis import given, strategies as st, settings, assume
from telegram_manager.session import TelegramSession
from telegram_manager.manager import TelegramSessionManager


# Strategies for generating test data
session_names = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
api_ids = st.integers(min_value=1, max_value=999999)
api_hashes = st.text(min_size=32, max_size=32, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
group_identifiers = st.text(min_size=1, max_size=50)
max_members_values = st.integers(min_value=1, max_value=1000)
message_texts = st.text(min_size=1, max_size=500)
target_lists = st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=10)


class TestTelegramSessionAPICompatibility:
    """Property tests for TelegramSession API compatibility"""
    
    @pytest.mark.asyncio
    @given(
        session_file=session_names,
        api_id=api_ids,
        api_hash=api_hashes
    )
    @settings(max_examples=100, deadline=None)
    async def test_property_init_signature_compatibility(self, session_file, api_id, api_hash):
        """
        Property: TelegramSession.__init__ signature remains unchanged
        
        For any valid session_file, api_id, and api_hash, the __init__ method
        should accept exactly these parameters and create a valid instance.
        """
        # Verify signature
        sig = inspect.signature(TelegramSession.__init__)
        params = list(sig.parameters.keys())
        
        # Expected parameters (Requirements 8.1)
        assert params == ['self', 'session_file', 'api_id', 'api_hash'], \
            f"__init__ signature changed. Expected ['self', 'session_file', 'api_id', 'api_hash'], got {params}"
        
        # Verify we can create instance with these parameters
        try:
            session = TelegramSession(
                session_file=f"test_{session_file}.session",
                api_id=api_id,
                api_hash=api_hash
            )
            
            # Verify instance attributes are set correctly (Requirements 8.3)
            assert session.session_file == f"test_{session_file}.session"
            assert session.api_id == api_id
            assert session.api_hash == api_hash
            assert session.is_connected == False
            assert session.client is None
            
        except TypeError as e:
            pytest.fail(f"__init__ signature incompatible: {e}")
    
    @pytest.mark.asyncio
    async def test_property_get_status_return_structure(self):
        """
        Property: get_status returns Dict with expected structure
        
        For any TelegramSession, get_status should return a Dict with
        consistent structure (Requirements 8.3, 8.5).
        
        Updated to include new fields from concurrent operations architecture:
        - current_operation: tracks active scraping/sending operation
        - operation_start_time: tracks when operation started
        """
        session = TelegramSession(
            session_file='test_status.session',
            api_id=12345,
            api_hash='test_hash'
        )
        
        # Call get_status
        status = session.get_status()
        
        # Verify return type (Requirements 8.3)
        assert isinstance(status, dict), \
            f"get_status should return Dict, got {type(status)}"
        
        # Verify expected keys are present (Requirements 8.5)
        # Updated to include new operation tracking fields (AC-7.1, AC-7.2)
        expected_keys = {
            'connected', 
            'monitoring', 
            'monitoring_targets_count', 
            'active_tasks',
            'current_operation',  # New: tracks scraping/sending operations
            'operation_start_time'  # New: tracks operation timing
        }
        actual_keys = set(status.keys())
        
        assert expected_keys == actual_keys, \
            f"get_status return structure changed. Expected keys {expected_keys}, got {actual_keys}"
    
    @pytest.mark.asyncio
    @given(
        group_id=group_identifiers,
        max_members=max_members_values
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_scrape_methods_signature(self, group_id, max_members):
        """
        Property: Scraping method signatures remain unchanged
        
        For any valid parameters, scraping methods should have consistent
        signatures and return Dict structures (Requirements 8.1, 8.3).
        """
        # Test scrape_group_members signature
        sig = inspect.signature(TelegramSession.scrape_group_members)
        params = list(sig.parameters.keys())
        
        expected_params = ['self', 'group_identifier', 'max_members', 'fallback_to_messages', 'message_days_back']
        assert params == expected_params, \
            f"scrape_group_members signature changed. Expected {expected_params}, got {params}"
        
        # Verify return annotation is Dict or empty (Requirements 8.3)
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty, \
            f"scrape_group_members return type changed: {sig.return_annotation}"
        
        # Test join_and_scrape_members signature
        sig2 = inspect.signature(TelegramSession.join_and_scrape_members)
        params2 = list(sig2.parameters.keys())
        
        expected_params2 = ['self', 'group_identifier', 'max_members']
        assert params2 == expected_params2, \
            f"join_and_scrape_members signature changed. Expected {expected_params2}, got {params2}"
        
        # Verify return annotation
        assert sig2.return_annotation == Dict or sig2.return_annotation == inspect.Signature.empty, \
            f"join_and_scrape_members return type changed: {sig2.return_annotation}"


class TestTelegramSessionManagerAPICompatibility:
    """Property tests for TelegramSessionManager API compatibility"""
    
    @pytest.mark.asyncio
    @given(max_concurrent=st.integers(min_value=1, max_value=20))
    @settings(max_examples=100, deadline=None)
    async def test_property_manager_init_signature(self, max_concurrent):
        """
        Property: TelegramSessionManager.__init__ signature remains unchanged
        
        For any valid max_concurrent_operations value, the __init__ method
        should accept this parameter and create a valid instance (Requirements 8.2).
        
        Note: load_balancing_strategy parameter was added in Task 10 (Requirement 19.1-19.5)
        """
        # Verify signature
        sig = inspect.signature(TelegramSessionManager.__init__)
        params = list(sig.parameters.keys())
        
        # Expected parameters (Requirements 8.2, 19.1-19.5)
        # load_balancing_strategy was added in Task 10
        assert params == ['self', 'max_concurrent_operations', 'load_balancing_strategy'], \
            f"TelegramSessionManager.__init__ signature changed. Expected ['self', 'max_concurrent_operations', 'load_balancing_strategy'], got {params}"
        
        # Verify we can create instance
        try:
            manager = TelegramSessionManager(max_concurrent_operations=max_concurrent)
            
            # Verify instance attributes (Requirements 8.3)
            assert isinstance(manager.sessions, dict)
            assert isinstance(manager.session_locks, dict)
            assert manager.operation_semaphore._value == max_concurrent
            
        except TypeError as e:
            pytest.fail(f"TelegramSessionManager.__init__ signature incompatible: {e}")
    
    @pytest.mark.asyncio
    async def test_property_get_session_stats_return_structure(self):
        """
        Property: get_session_stats returns Dict with expected structure
        
        For any TelegramSessionManager, get_session_stats should return
        a Dict mapping session names to status dicts (Requirements 8.3, 8.5).
        """
        manager = TelegramSessionManager(max_concurrent_operations=3)
        
        # Call get_session_stats
        stats = await manager.get_session_stats()
        
        # Verify return type (Requirements 8.3)
        assert isinstance(stats, dict), \
            f"get_session_stats should return Dict, got {type(stats)}"
        
        # For empty manager, should return empty dict
        assert stats == {}, \
            f"get_session_stats should return empty dict for manager with no sessions, got {stats}"
    
    @pytest.mark.asyncio
    @given(
        group_id=group_identifiers,
        max_members=max_members_values
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_scrape_random_session_signature(self, group_id, max_members):
        """
        Property: scrape_group_members_random_session signature remains unchanged
        
        For any valid parameters, the method should have consistent signature
        and return Dict structure (Requirements 8.2, 8.3).
        """
        # Verify signature
        sig = inspect.signature(TelegramSessionManager.scrape_group_members_random_session)
        params = list(sig.parameters.keys())
        
        expected_params = ['self', 'group_identifier', 'max_members', 'fallback_to_messages', 'message_days_back']
        assert params == expected_params, \
            f"scrape_group_members_random_session signature changed. Expected {expected_params}, got {params}"
        
        # Verify return annotation is Dict or empty (Requirements 8.3)
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty, \
            f"scrape_group_members_random_session return type changed: {sig.return_annotation}"
    
    @pytest.mark.asyncio
    @given(
        message=message_texts,
        delay=st.floats(min_value=0.1, max_value=10.0)
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_bulk_send_messages_signature(self, message, delay):
        """
        Property: bulk_send_messages signature remains unchanged
        
        For any valid parameters, the method should have consistent signature
        and return Dict structure (Requirements 8.2, 8.3).
        """
        # Verify signature
        sig = inspect.signature(TelegramSessionManager.bulk_send_messages)
        params = list(sig.parameters.keys())
        
        expected_params = ['self', 'targets', 'message', 'delay']
        assert params == expected_params, \
            f"bulk_send_messages signature changed. Expected {expected_params}, got {params}"
        
        # Verify return annotation is Dict or empty (Requirements 8.3)
        assert sig.return_annotation == Dict or sig.return_annotation == inspect.Signature.empty, \
            f"bulk_send_messages return type changed: {sig.return_annotation}"


class TestAPICompatibilityIntegration:
    """Integration tests for API compatibility across both classes"""
    
    @pytest.mark.asyncio
    async def test_property_monitoring_api_unchanged(self):
        """
        Property: Monitoring API remains unchanged
        
        The monitoring workflow (start/stop) should work with the same
        API as before concurrency fixes (Requirements 8.4).
        """
        # Create session
        session = TelegramSession(
            session_file='test_monitoring_api.session',
            api_id=12345,
            api_hash='test_hash'
        )
        
        # Verify start_monitoring signature
        # Note: inspect.signature doesn't include 'self' for instance methods
        sig = inspect.signature(session.start_monitoring)
        params = list(sig.parameters.keys())
        assert params == ['targets'], \
            f"start_monitoring signature changed: {params}"
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty
        
        # Verify stop_monitoring signature
        sig2 = inspect.signature(session.stop_monitoring)
        params2 = list(sig2.parameters.keys())
        assert params2 == [], \
            f"stop_monitoring signature changed: {params2}"
    
    @pytest.mark.asyncio
    async def test_property_all_public_methods_preserved(self):
        """
        Property: All public methods are preserved
        
        Verify that no public methods were removed and all expected
        methods still exist (Requirements 8.1, 8.2).
        """
        # Expected TelegramSession public methods (excluding __init__ which is special)
        expected_session_methods = {
            'connect', 'disconnect', 'start_monitoring', 'stop_monitoring',
            'send_message', 'join_chat', 'get_members', 'bulk_send_messages',
            'get_status', 'scrape_group_members', 'join_and_scrape_members',
            'scrape_members_from_messages', 'extract_group_links',
            'check_target_type', 'bulk_check_targets'
        }
        
        # Get actual public methods
        actual_session_methods = {
            name for name in dir(TelegramSession)
            if not name.startswith('_') and callable(getattr(TelegramSession, name))
        }
        
        # Verify all expected methods exist
        missing_methods = expected_session_methods - actual_session_methods
        assert not missing_methods, \
            f"TelegramSession missing public methods: {missing_methods}"
        
        # Expected TelegramSessionManager public methods (excluding __init__ which is special)
        expected_manager_methods = {
            'load_sessions', 'load_sessions_from_db',
            'start_global_monitoring', 'stop_global_monitoring',
            'bulk_send_messages', 'bulk_get_members', 'join_chats',
            'get_session_stats', 'get_session', 'shutdown',
            'scrape_group_members_random_session', 'bulk_scrape_groups',
            'extract_links_from_channels', 'check_target_type', 'bulk_check_targets'
        }
        
        # Get actual public methods
        actual_manager_methods = {
            name for name in dir(TelegramSessionManager)
            if not name.startswith('_') and callable(getattr(TelegramSessionManager, name))
        }
        
        # Verify all expected methods exist
        missing_manager_methods = expected_manager_methods - actual_manager_methods
        assert not missing_manager_methods, \
            f"TelegramSessionManager missing public methods: {missing_manager_methods}"
    
    @pytest.mark.asyncio
    @given(
        session_file=session_names,
        api_id=api_ids,
        api_hash=api_hashes
    )
    @settings(max_examples=100, deadline=None)
    async def test_property_session_creation_idempotent(self, session_file, api_id, api_hash):
        """
        Property: Session creation is idempotent
        
        Creating multiple sessions with the same parameters should produce
        consistent results (Requirements 8.3, 8.5).
        """
        # Create first session
        session1 = TelegramSession(
            session_file=f"test_{session_file}_1.session",
            api_id=api_id,
            api_hash=api_hash
        )
        
        # Create second session with same parameters
        session2 = TelegramSession(
            session_file=f"test_{session_file}_1.session",
            api_id=api_id,
            api_hash=api_hash
        )
        
        # Verify both sessions have identical initial state
        assert session1.session_file == session2.session_file
        assert session1.api_id == session2.api_id
        assert session1.api_hash == session2.api_hash
        assert session1.is_connected == session2.is_connected == False
        assert session1.is_monitoring == session2.is_monitoring == False
        
        # Verify get_status returns same structure for both
        status1 = session1.get_status()
        status2 = session2.get_status()
        
        assert set(status1.keys()) == set(status2.keys()), \
            f"get_status structure differs between identical sessions"
    
    @pytest.mark.asyncio
    async def test_property_parameter_defaults_unchanged(self):
        """
        Property: Default parameter values remain unchanged
        
        Methods with default parameters should maintain the same defaults
        (Requirements 8.1, 8.2).
        """
        # Check scrape_group_members defaults
        sig = inspect.signature(TelegramSession.scrape_group_members)
        
        # Verify fallback_to_messages default
        fallback_param = sig.parameters['fallback_to_messages']
        assert fallback_param.default == True, \
            f"scrape_group_members fallback_to_messages default changed: {fallback_param.default}"
        
        # Verify message_days_back default (actual default is 10)
        days_param = sig.parameters['message_days_back']
        assert days_param.default == 10, \
            f"scrape_group_members message_days_back default changed: {days_param.default}"
        
        # Check bulk_send_messages defaults (actual default is 1.0)
        sig2 = inspect.signature(TelegramSession.bulk_send_messages)
        delay_param = sig2.parameters['delay']
        assert delay_param.default == 1.0, \
            f"bulk_send_messages delay default changed: {delay_param.default}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
