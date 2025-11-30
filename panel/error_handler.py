"""
Error Handler - Comprehensive error handling for Telegram Bot Panel

This module provides:
- Centralized error handling
- User-friendly error messages
- Detailed logging with context
- Retry mechanisms
- Telegram API error handling

Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4, AC-9.5
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError,
    NetworkError,
    TimedOut,
    BadRequest,
    Forbidden,
    Conflict,
    RetryAfter,
    InvalidToken
)

from .message_formatter import MessageFormatter
from .keyboard_builder import KeyboardBuilder


class ErrorContext:
    """Context information for error logging"""
    
    def __init__(
        self,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.operation = operation
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'user_id': self.user_id,
            'operation': self.operation,
            'details': self.details
        }


class BotErrorHandler:
    """
    Centralized error handler for the bot
    
    Provides:
    - Error classification
    - User-friendly messages
    - Detailed logging
    - Retry mechanisms
    
    Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4, AC-9.5
    """
    
    def __init__(self, logger_name: str = "BotErrorHandler"):
        self.logger = logging.getLogger(logger_name)
    
    def classify_error(self, error: Exception) -> Dict[str, Any]:
        """
        Classify error and determine appropriate response
        
        Args:
            error: The exception that occurred
        
        Returns:
            Dict with error classification and response info
            
        Requirements: AC-9.2
        """
        # Telegram API errors - check specific errors before general ones
        if isinstance(error, RetryAfter):
            return {
                'type': 'rate_limit',
                'user_message': 'محدودیت تعداد درخواست. لطفاً چند لحظه صبر کنید.',
                'retry_after': error.retry_after,
                'show_retry': True,
                'log_level': 'warning'
            }
        
        elif isinstance(error, TimedOut):
            return {
                'type': 'timeout',
                'user_message': 'زمان اتصال به پایان رسید. لطفاً دوباره تلاش کنید.',
                'show_retry': True,
                'log_level': 'warning'
            }
        
        elif isinstance(error, BadRequest):
            return {
                'type': 'bad_request',
                'user_message': f'درخواست نامعتبر: {str(error)}',
                'show_retry': False,
                'log_level': 'error'
            }
        
        elif isinstance(error, Forbidden):
            return {
                'type': 'forbidden',
                'user_message': 'دسترسی مجاز نیست. ممکن است ربات بلاک شده باشد.',
                'show_retry': False,
                'log_level': 'error'
            }
        
        elif isinstance(error, Conflict):
            return {
                'type': 'conflict',
                'user_message': 'ربات در حال اجرا در جای دیگری است.',
                'show_retry': False,
                'log_level': 'critical'
            }
        
        elif isinstance(error, InvalidToken):
            return {
                'type': 'invalid_token',
                'user_message': 'توکن ربات نامعتبر است.',
                'show_retry': False,
                'log_level': 'critical'
            }
        
        elif isinstance(error, NetworkError):
            return {
                'type': 'network',
                'user_message': 'خطای شبکه. لطفاً اتصال اینترنت خود را بررسی کنید.',
                'show_retry': True,
                'log_level': 'warning'
            }
        
        elif isinstance(error, TelegramError):
            return {
                'type': 'telegram_api',
                'user_message': f'خطای تلگرام: {str(error)}',
                'show_retry': True,
                'log_level': 'error'
            }
        
        # File operation errors
        elif isinstance(error, FileNotFoundError):
            return {
                'type': 'file_not_found',
                'user_message': 'فایل مورد نظر یافت نشد.',
                'show_retry': False,
                'log_level': 'error'
            }
        
        elif isinstance(error, PermissionError):
            return {
                'type': 'permission',
                'user_message': 'خطای دسترسی به فایل.',
                'show_retry': False,
                'log_level': 'error'
            }
        
        # Value errors (validation)
        elif isinstance(error, ValueError):
            return {
                'type': 'validation',
                'user_message': f'داده نامعتبر: {str(error)}',
                'show_retry': False,
                'log_level': 'warning'
            }
        
        # Generic errors
        else:
            return {
                'type': 'unknown',
                'user_message': 'خطای غیرمنتظره رخ داد. لطفاً دوباره تلاش کنید.',
                'show_retry': True,
                'log_level': 'error'
            }
    
    def log_error(
        self,
        error: Exception,
        context: ErrorContext,
        include_traceback: bool = True
    ):
        """
        Log error with full context
        
        Args:
            error: The exception
            context: Error context information
            include_traceback: Whether to include full traceback
            
        Requirements: AC-9.4
        """
        classification = self.classify_error(error)
        log_level = classification.get('log_level', 'error')
        
        # Build log message
        log_data = {
            'error_type': classification['type'],
            'error_message': str(error),
            'context': context.to_dict()
        }
        
        if include_traceback:
            log_data['traceback'] = traceback.format_exc()
        
        # Log at appropriate level
        log_method = getattr(self.logger, log_level)
        log_method(
            f"Error in {context.operation or 'unknown operation'}: {str(error)}",
            extra=log_data
        )
    
    async def handle_error(
        self,
        error: Exception,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_context: ErrorContext,
        retry_callback: Optional[str] = None
    ):
        """
        Handle error and send user-friendly message
        
        Args:
            error: The exception
            update: Telegram update
            context: Bot context
            error_context: Error context for logging
            retry_callback: Optional callback data for retry button
            
        Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.5
        """
        # Log the error
        self.log_error(error, error_context)
        
        # Classify error
        classification = self.classify_error(error)
        
        # Format user message
        error_msg = MessageFormatter.format_error(
            error_type=classification['type'],
            description=classification['user_message'],
            show_retry=classification['show_retry'] and retry_callback is not None
        )
        
        # Build keyboard
        keyboard = None
        if classification['show_retry'] and retry_callback:
            keyboard = KeyboardBuilder.retry_back(
                retry_data=retry_callback,
                back_data="nav:main"
            )
        else:
            keyboard = KeyboardBuilder.back_to_main()
        
        # Send error message
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    error_msg,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            elif update.message:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as send_error:
            # If we can't send the error message, just log it
            self.logger.error(f"Failed to send error message: {send_error}")
    
    async def global_error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Global error handler for the application
        
        This catches all unhandled errors in the bot
        
        Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4
        """
        # Extract error
        error = context.error
        
        # Build error context
        error_context = ErrorContext(
            user_id=update.effective_user.id if update and hasattr(update, 'effective_user') else None,
            operation='global_handler',
            details={
                'update_type': type(update).__name__ if update else 'None',
                'error_type': type(error).__name__
            }
        )
        
        # Log error
        self.log_error(error, error_context)
        
        # Try to notify user
        if update and isinstance(update, Update):
            try:
                classification = self.classify_error(error)
                error_msg = MessageFormatter.format_error(
                    error_type='سیستمی',
                    description=classification['user_message'],
                    show_retry=False
                )
                
                keyboard = KeyboardBuilder.back_to_main()
                
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        error_msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                elif update.message:
                    await update.message.reply_text(
                        error_msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
            except Exception as notify_error:
                self.logger.error(f"Failed to notify user of error: {notify_error}")


def with_error_handling(operation_name: str, retry_callback: Optional[str] = None):
    """
    Decorator for adding error handling to handler functions
    
    Args:
        operation_name: Name of the operation for logging
        retry_callback: Optional callback data for retry button
    
    Usage:
        @with_error_handling("scraping", retry_callback="scrape:retry")
        async def my_handler(self, update, context):
            # handler code
    
    Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.5
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            error_handler = BotErrorHandler(logger_name=self.__class__.__name__)
            
            try:
                return await func(self, update, context, *args, **kwargs)
            except Exception as e:
                # Build error context
                error_context = ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation=operation_name,
                    details={
                        'function': func.__name__,
                        'class': self.__class__.__name__
                    }
                )
                
                # Handle error
                await error_handler.handle_error(
                    error=e,
                    update=update,
                    context=context,
                    error_context=error_context,
                    retry_callback=retry_callback
                )
                
                # Return appropriate conversation state
                from telegram.ext import ConversationHandler
                return ConversationHandler.END
        
        return wrapper
    return decorator
