"""
Test error handling functionality

Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4, AC-9.5
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, CallbackQuery
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError,
    NetworkError,
    TimedOut,
    BadRequest,
    Forbidden,
    RetryAfter
)

from panel.error_handler import BotErrorHandler, ErrorContext, with_error_handling


class TestErrorClassification:
    """Test error classification"""
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = RetryAfter(30)
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'rate_limit'
        assert classification['show_retry'] is True
        assert classification['retry_after'] == 30
        assert 'محدودیت' in classification['user_message']
    
    def test_classify_timeout_error(self):
        """Test classification of timeout errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = TimedOut()
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'timeout'
        assert classification['show_retry'] is True
        assert 'زمان' in classification['user_message']
    
    def test_classify_network_error(self):
        """Test classification of network errors (AC-9.1, AC-9.2)"""
        handler = BotErrorHandler()
        error = NetworkError("Connection failed")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'network'
        assert classification['show_retry'] is True
        assert 'شبکه' in classification['user_message']
    
    def test_classify_bad_request_error(self):
        """Test classification of bad request errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = BadRequest("Invalid message")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'bad_request'
        assert classification['show_retry'] is False
        assert 'نامعتبر' in classification['user_message']
    
    def test_classify_forbidden_error(self):
        """Test classification of forbidden errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = Forbidden("Bot was blocked")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'forbidden'
        assert classification['show_retry'] is False
        assert 'دسترسی' in classification['user_message']
    
    def test_classify_file_not_found_error(self):
        """Test classification of file errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = FileNotFoundError("File not found")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'file_not_found'
        assert classification['show_retry'] is False
        assert 'فایل' in classification['user_message']
    
    def test_classify_value_error(self):
        """Test classification of validation errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = ValueError("Invalid value")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'validation'
        assert classification['show_retry'] is False
        assert 'نامعتبر' in classification['user_message']
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors (AC-9.2)"""
        handler = BotErrorHandler()
        error = Exception("Unknown error")
        
        classification = handler.classify_error(error)
        
        assert classification['type'] == 'unknown'
        assert classification['show_retry'] is True
        assert 'غیرمنتظره' in classification['user_message']


class TestErrorLogging:
    """Test error logging with context"""
    
    def test_log_error_with_context(self):
        """Test error logging includes context (AC-9.4)"""
        handler = BotErrorHandler()
        error = ValueError("Test error")
        context = ErrorContext(
            user_id=12345,
            operation="test_operation",
            details={'key': 'value'}
        )
        
        # ValueError is classified as 'validation' with log_level 'warning'
        with patch.object(handler.logger, 'warning') as mock_log:
            handler.log_error(error, context, include_traceback=False)
            
            # Verify logging was called
            assert mock_log.called
            call_args = mock_log.call_args
            
            # Check log message contains operation name
            assert 'test_operation' in call_args[0][0]
    
    def test_log_error_includes_traceback(self):
        """Test error logging includes traceback when requested (AC-9.4)"""
        handler = BotErrorHandler()
        error = ValueError("Test error")
        context = ErrorContext(user_id=12345, operation="test")
        
        # ValueError is classified as 'validation' with log_level 'warning'
        with patch.object(handler.logger, 'warning') as mock_log:
            handler.log_error(error, context, include_traceback=True)
            
            # Verify traceback is in extra data
            assert mock_log.called
            extra_data = mock_log.call_args[1].get('extra', {})
            assert 'traceback' in extra_data


class TestErrorHandling:
    """Test error handling and user notification"""
    
    @pytest.mark.asyncio
    async def test_handle_error_with_message(self):
        """Test error handling sends user-friendly message (AC-9.3)"""
        handler = BotErrorHandler()
        error = NetworkError("Connection failed")
        
        # Create mock update with message
        update = Mock(spec=Update)
        update.callback_query = None
        update.message = AsyncMock(spec=Message)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        error_context = ErrorContext(user_id=12345, operation="test")
        
        await handler.handle_error(
            error=error,
            update=update,
            context=context,
            error_context=error_context,
            retry_callback="action:retry"
        )
        
        # Verify message was sent
        assert update.message.reply_text.called
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        
        # Check message contains error info
        assert 'خطا' in message_text
        assert 'شبکه' in message_text
    
    @pytest.mark.asyncio
    async def test_handle_error_with_callback_query(self):
        """Test error handling with callback query (AC-9.3)"""
        handler = BotErrorHandler()
        error = TimedOut()
        
        # Create mock update with callback query
        update = Mock(spec=Update)
        update.callback_query = AsyncMock(spec=CallbackQuery)
        update.message = None
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        error_context = ErrorContext(user_id=12345, operation="test")
        
        await handler.handle_error(
            error=error,
            update=update,
            context=context,
            error_context=error_context,
            retry_callback=None
        )
        
        # Verify message was edited
        assert update.callback_query.edit_message_text.called
        call_args = update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        
        # Check message contains error info
        assert 'خطا' in message_text
    
    @pytest.mark.asyncio
    async def test_handle_error_with_retry_button(self):
        """Test error handling includes retry button when appropriate (AC-9.5)"""
        handler = BotErrorHandler()
        error = NetworkError("Connection failed")
        
        # Create mock update
        update = Mock(spec=Update)
        update.callback_query = None
        update.message = AsyncMock(spec=Message)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        error_context = ErrorContext(user_id=12345, operation="test")
        
        await handler.handle_error(
            error=error,
            update=update,
            context=context,
            error_context=error_context,
            retry_callback="action:retry"
        )
        
        # Verify keyboard was provided
        call_kwargs = update.message.reply_text.call_args[1]
        assert 'reply_markup' in call_kwargs
        assert call_kwargs['reply_markup'] is not None


class TestGlobalErrorHandler:
    """Test global error handler"""
    
    @pytest.mark.asyncio
    async def test_global_error_handler_logs_error(self):
        """Test global error handler logs errors (AC-9.4)"""
        handler = BotErrorHandler()
        
        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.callback_query = None
        update.message = AsyncMock(spec=Message)
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = ValueError("Test error")
        
        with patch.object(handler, 'log_error') as mock_log:
            await handler.global_error_handler(update, context)
            
            # Verify error was logged
            assert mock_log.called
    
    @pytest.mark.asyncio
    async def test_global_error_handler_notifies_user(self):
        """Test global error handler notifies user (AC-9.3)"""
        handler = BotErrorHandler()
        
        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.callback_query = None
        update.message = AsyncMock(spec=Message)
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = ValueError("Test error")
        
        await handler.global_error_handler(update, context)
        
        # Verify user was notified
        assert update.message.reply_text.called


class TestErrorHandlingDecorator:
    """Test error handling decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_catches_errors(self):
        """Test decorator catches and handles errors (AC-9.1)"""
        
        class MockHandler:
            pass
        
        handler = MockHandler()
        
        @with_error_handling("test_operation", retry_callback="action:retry")
        async def failing_handler(self, update, context):
            raise ValueError("Test error")
        
        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.callback_query = None
        update.message = AsyncMock(spec=Message)
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Call decorated function
        result = await failing_handler(handler, update, context)
        
        # Verify error was handled (returns ConversationHandler.END)
        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        
        # Verify user was notified
        assert update.message.reply_text.called
    
    @pytest.mark.asyncio
    async def test_decorator_allows_success(self):
        """Test decorator allows successful execution"""
        
        class MockHandler:
            pass
        
        handler = MockHandler()
        
        @with_error_handling("test_operation")
        async def successful_handler(self, update, context):
            return "success"
        
        # Create mock update and context
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Call decorated function
        result = await successful_handler(handler, update, context)
        
        # Verify success value is returned
        assert result == "success"


class TestErrorContext:
    """Test ErrorContext class"""
    
    def test_error_context_to_dict(self):
        """Test ErrorContext converts to dict for logging"""
        context = ErrorContext(
            user_id=12345,
            operation="test_operation",
            details={'key': 'value'}
        )
        
        context_dict = context.to_dict()
        
        assert context_dict['user_id'] == 12345
        assert context_dict['operation'] == "test_operation"
        assert context_dict['details']['key'] == 'value'
    
    def test_error_context_optional_fields(self):
        """Test ErrorContext with optional fields"""
        context = ErrorContext()
        
        context_dict = context.to_dict()
        
        assert context_dict['user_id'] is None
        assert context_dict['operation'] is None
        assert context_dict['details'] == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
