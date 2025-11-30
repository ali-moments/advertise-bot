"""
Tests for retry logic with exponential backoff (Task 8)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram_manager.manager import TelegramSessionManager


@pytest.mark.asyncio
async def test_retry_configuration_initialization():
    """Test that retry configuration is properly initialized"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Check retry config exists
    assert hasattr(manager, 'retry_config')
    assert hasattr(manager, 'retry_backoff_base')
    
    # Check retry counts per operation type
    assert manager.retry_config['scraping'] == 2
    assert manager.retry_config['monitoring'] == 0
    assert manager.retry_config['sending'] == 3  # Updated in Task 12 for better reliability
    
    # Check backoff base
    assert manager.retry_backoff_base == 2.0


@pytest.mark.asyncio
async def test_is_transient_error_detects_transient():
    """Test that transient errors are correctly identified"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Transient errors
    assert manager._is_transient_error(Exception("Connection timeout"))
    assert manager._is_transient_error(Exception("Network error"))
    assert manager._is_transient_error(Exception("Flood wait"))
    assert manager._is_transient_error(Exception("Too many requests"))
    assert manager._is_transient_error(TimeoutError("Operation timed out"))


@pytest.mark.asyncio
async def test_is_transient_error_detects_permanent():
    """Test that permanent errors are correctly identified"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Permanent errors
    assert not manager._is_transient_error(Exception("Unauthorized"))
    assert not manager._is_transient_error(Exception("Not found"))
    assert not manager._is_transient_error(Exception("Invalid credentials"))
    assert not manager._is_transient_error(Exception("User banned"))
    assert not manager._is_transient_error(Exception("Access denied"))


@pytest.mark.asyncio
async def test_execute_with_retry_success_first_attempt():
    """Test that operation succeeds on first attempt without retry"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that succeeds
    mock_operation = AsyncMock(return_value="success")
    
    result = await manager._execute_with_retry(
        'scraping',
        mock_operation,
        'arg1',
        kwarg1='value1'
    )
    
    assert result == "success"
    assert mock_operation.call_count == 1
    mock_operation.assert_called_once_with('arg1', kwarg1='value1')


@pytest.mark.asyncio
async def test_execute_with_retry_succeeds_after_transient_error():
    """Test that operation retries and succeeds after transient error"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that fails once then succeeds
    mock_operation = AsyncMock(
        side_effect=[
            Exception("Connection timeout"),  # First attempt fails
            "success"  # Second attempt succeeds
        ]
    )
    
    result = await manager._execute_with_retry(
        'scraping',
        mock_operation
    )
    
    assert result == "success"
    assert mock_operation.call_count == 2


@pytest.mark.asyncio
async def test_execute_with_retry_fails_after_max_retries():
    """Test that operation fails after exhausting all retries"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that always fails with transient error
    mock_operation = AsyncMock(
        side_effect=Exception("Connection timeout")
    )
    
    with pytest.raises(Exception, match="Connection timeout"):
        await manager._execute_with_retry(
            'scraping',  # 2 retries
            mock_operation
        )
    
    # Should try 3 times total (initial + 2 retries)
    assert mock_operation.call_count == 3


@pytest.mark.asyncio
async def test_execute_with_retry_no_retry_on_permanent_error():
    """Test that permanent errors are not retried"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that fails with permanent error
    mock_operation = AsyncMock(
        side_effect=Exception("Unauthorized")
    )
    
    with pytest.raises(Exception, match="Unauthorized"):
        await manager._execute_with_retry(
            'scraping',
            mock_operation
        )
    
    # Should only try once (no retries for permanent errors)
    assert mock_operation.call_count == 1


@pytest.mark.asyncio
async def test_execute_with_retry_respects_operation_type_retry_count():
    """Test that different operation types have different retry counts"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Test scraping (2 retries)
    mock_scrape = AsyncMock(side_effect=Exception("Connection timeout"))
    with pytest.raises(Exception):
        await manager._execute_with_retry('scraping', mock_scrape)
    assert mock_scrape.call_count == 3  # initial + 2 retries
    
    # Test sending (3 retries - updated in Task 12)
    mock_send = AsyncMock(side_effect=Exception("Connection timeout"))
    with pytest.raises(Exception):
        await manager._execute_with_retry('sending', mock_send)
    assert mock_send.call_count == 4  # initial + 3 retries
    
    # Test monitoring (0 retries)
    mock_monitor = AsyncMock(side_effect=Exception("Connection timeout"))
    with pytest.raises(Exception):
        await manager._execute_with_retry('monitoring', mock_monitor)
    assert mock_monitor.call_count == 1  # initial only, no retries


@pytest.mark.asyncio
async def test_execute_with_retry_exponential_backoff():
    """Test that retry uses exponential backoff"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that fails twice then succeeds
    mock_operation = AsyncMock(
        side_effect=[
            Exception("Connection timeout"),
            Exception("Connection timeout"),
            "success"
        ]
    )
    
    # Track sleep calls to verify backoff
    sleep_calls = []
    original_sleep = asyncio.sleep
    
    async def mock_sleep(delay):
        sleep_calls.append(delay)
        await original_sleep(0.01)  # Use very short delay for test
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        result = await manager._execute_with_retry(
            'scraping',
            mock_operation
        )
    
    assert result == "success"
    assert mock_operation.call_count == 3
    
    # Check exponential backoff: 2^0=1, 2^1=2
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 1.0  # 2^0
    assert sleep_calls[1] == 2.0  # 2^1


@pytest.mark.asyncio
async def test_scrape_operations_use_retry():
    """Test that scraping operations use retry wrapper"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Create a mock session
    mock_session = MagicMock()
    mock_session.is_connected = True
    mock_session.scrape_group_members = AsyncMock(
        side_effect=[
            Exception("Connection timeout"),
            {'success': True, 'file_path': 'test.csv'}
        ]
    )
    
    manager.sessions = {'test_session': mock_session}
    manager.session_locks = {'test_session': asyncio.Lock()}
    manager.session_load = {'test_session': 0}
    
    # Call scrape method
    result = await manager.scrape_group_members_random_session('test_group')
    
    # Should succeed after retry
    assert result['success'] == True
    assert mock_session.scrape_group_members.call_count == 2


@pytest.mark.asyncio
async def test_retry_logs_attempts():
    """Test that retry logic logs each attempt"""
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Mock operation that fails once then succeeds
    mock_operation = AsyncMock(
        side_effect=[
            Exception("Connection timeout"),
            "success"
        ]
    )
    
    # Capture log messages
    with patch.object(manager.logger, 'info') as mock_log_info:
        with patch.object(manager.logger, 'warning') as mock_log_warning:
            result = await manager._execute_with_retry(
                'scraping',
                mock_operation
            )
    
    # Check that retry was logged
    assert any('Retry attempt' in str(call) for call in mock_log_info.call_args_list)
    assert any('succeeded on retry' in str(call) for call in mock_log_info.call_args_list)
    assert any('failed' in str(call) for call in mock_log_warning.call_args_list)
