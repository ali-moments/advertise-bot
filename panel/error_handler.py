"""
Error Handling System for Telegram Bot Panel

This module provides comprehensive error handling including:
- Error classification
- Error translation to Persian
- Error recovery options
- Admin notifications

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 15.1, 15.3, 15.4
"""

import logging
import traceback
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any, Dict
from enum import Enum
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError,
    NetworkError,
    TimedOut,
    BadRequest,
    Forbidden,
    ChatMigrated,
    RetryAfter,
    Conflict
)

from panel.persian_text import (
    ERROR_GENERIC,
    ERROR_NETWORK,
    ERROR_TELEGRAM_API,
    ERROR_TIMEOUT,
    ERROR_PERMISSION_DENIED,
    BTN_MAIN_MENU,
    BTN_CANCEL,
    RECOVERY_RETRY,
    RECOVERY_SKIP
)


class ErrorType(Enum):
    """Error classification types"""
    USER_INPUT = "user_input"
    NETWORK = "network"
    TELEGRAM_API = "telegram_api"
    OPERATION = "operation"
    SYSTEM = "system"
    PERMISSION = "permission"
    TIMEOUT = "timeout"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"  # Minor issues, user can continue
    MEDIUM = "medium"  # Recoverable errors
    HIGH = "high"  # Operation failed but system stable
    CRITICAL = "critical"  # System-level issues


@dataclass
class ErrorContext:
    """
    Context information for error handling
    
    Attributes:
        user_id: User who encountered the error
        operation: Operation being performed
        details: Additional context details
        timestamp: When error occurred
    """
    user_id: Optional[int]
    operation: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class ErrorRecoveryOption:
    """
    Recovery option for an error
    
    Attributes:
        label: Button label
        callback_data: Callback data for button
        action: Optional async function to execute
    """
    label: str
    callback_data: str
    action: Optional[Callable] = None


class BotErrorHandler:
    """
    Comprehensive error handler for the bot panel
    
    Handles error classification, translation, logging, and recovery options.
    Provides admin notifications for critical errors.
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
    """
    
    def __init__(self, logger_name: str = "TelegramBotPanel", admin_user_ids: Optional[List[int]] = None):
        """
        Initialize error handler
        
        Args:
            logger_name: Logger name to use
            admin_user_ids: List of admin user IDs for notifications
        """
        self.logger = logging.getLogger(logger_name)
        self.admin_user_ids = admin_user_ids or []
        
        # Error statistics
        self.error_counts: Dict[ErrorType, int] = {error_type: 0 for error_type in ErrorType}
        self.last_errors: List[Dict[str, Any]] = []
        self.max_last_errors = 50
    
    def classify_error(self, error: Exception) -> tuple[ErrorType, ErrorSeverity]:
        """
        Classify error by type and severity
        
        Args:
            error: Exception to classify
            
        Returns:
            Tuple of (ErrorType, ErrorSeverity)
            
        Requirements: 9.1, 9.3
        """
        # Telegram API errors (check before network errors since some inherit from both)
        if isinstance(error, RetryAfter):
            return ErrorType.TELEGRAM_API, ErrorSeverity.MEDIUM
        
        if isinstance(error, (BadRequest, ChatMigrated)):
            return ErrorType.TELEGRAM_API, ErrorSeverity.LOW
        
        # Network errors
        if isinstance(error, (NetworkError, TimedOut, ConnectionError)):
            return ErrorType.NETWORK, ErrorSeverity.MEDIUM
        
        if isinstance(error, Forbidden):
            return ErrorType.PERMISSION, ErrorSeverity.HIGH
        
        if isinstance(error, Conflict):
            return ErrorType.TELEGRAM_API, ErrorSeverity.CRITICAL
        
        if isinstance(error, TelegramError):
            return ErrorType.TELEGRAM_API, ErrorSeverity.MEDIUM
        
        # Timeout errors
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return ErrorType.TIMEOUT, ErrorSeverity.MEDIUM
        
        # Permission errors
        if isinstance(error, PermissionError):
            return ErrorType.PERMISSION, ErrorSeverity.HIGH
        
        # Value errors (usually user input)
        if isinstance(error, ValueError):
            return ErrorType.USER_INPUT, ErrorSeverity.LOW
        
        # System errors
        if isinstance(error, (OSError, IOError, MemoryError)):
            return ErrorType.SYSTEM, ErrorSeverity.CRITICAL
        
        # Default: operation error
        return ErrorType.OPERATION, ErrorSeverity.MEDIUM
    
    def translate_error(self, error: Exception, error_type: ErrorType) -> str:
        """
        Translate error to user-friendly Persian message
        
        Args:
            error: Exception to translate
            error_type: Classified error type
            
        Returns:
            Persian error message
            
        Requirements: 9.2
        """
        error_str = str(error)
        
        # Network errors
        if error_type == ErrorType.NETWORK:
            if isinstance(error, TimedOut):
                return "⏱️ زمان اتصال به سرور تلگرام به پایان رسید. لطفاً دوباره تلاش کنید."
            return f"{ERROR_NETWORK}\n\nلطفاً اتصال اینترنت خود را بررسی کنید."
        
        # Telegram API errors
        if error_type == ErrorType.TELEGRAM_API:
            if isinstance(error, RetryAfter):
                retry_after = getattr(error, 'retry_after', 30)
                return f"⏳ محدودیت نرخ تلگرام\n\nلطفاً {retry_after} ثانیه صبر کنید و دوباره تلاش کنید."
            
            if isinstance(error, BadRequest):
                if "chat not found" in error_str.lower():
                    return "❌ گروه یا کانال یافت نشد\n\nلطفاً لینک را بررسی کنید."
                if "message is not modified" in error_str.lower():
                    return "⚠️ پیام قبلاً بروزرسانی شده است"
                if "message to edit not found" in error_str.lower():
                    return "⚠️ پیام برای ویرایش یافت نشد"
                return f"❌ درخواست نامعتبر\n\n{error_str}"
            
            if isinstance(error, Forbidden):
                if "blocked" in error_str.lower():
                    return "🚫 ربات توسط کاربر بلاک شده است"
                if "deactivated" in error_str.lower():
                    return "🚫 حساب کاربری غیرفعال است"
                if "rights" in error_str.lower():
                    return "🚫 دسترسی کافی نیست\n\nربات باید ادمین باشد."
                return f"🚫 دسترسی محدود\n\n{error_str}"
            
            if isinstance(error, ChatMigrated):
                return "⚠️ گروه به سوپرگروه تبدیل شده است\n\nلطفاً لینک جدید را استفاده کنید."
            
            if isinstance(error, Conflict):
                return "⚠️ تداخل در اجرای ربات\n\nلطفاً مطمئن شوید که فقط یک نمونه از ربات در حال اجرا است."
            
            return f"{ERROR_TELEGRAM_API}\n\n{error_str}"
        
        # Timeout errors
        if error_type == ErrorType.TIMEOUT:
            return f"{ERROR_TIMEOUT}\n\nعملیات بیش از حد طول کشید. لطفاً دوباره تلاش کنید."
        
        # Permission errors
        if error_type == ErrorType.PERMISSION:
            return f"{ERROR_PERMISSION_DENIED}\n\nدسترسی لازم برای این عملیات وجود ندارد."
        
        # User input errors
        if error_type == ErrorType.USER_INPUT:
            return f"❌ ورودی نامعتبر\n\n{error_str}\n\nلطفاً فرمت صحیح را وارد کنید."
        
        # System errors
        if error_type == ErrorType.SYSTEM:
            return f"❌ خطای سیستمی\n\nلطفاً با مدیر سیستم تماس بگیرید."
        
        # Operation errors
        return f"❌ خطا در عملیات\n\n{error_str}"
    
    def get_recovery_options(
        self,
        error_type: ErrorType,
        error_severity: ErrorSeverity,
        retry_callback: Optional[str] = None,
        skip_callback: Optional[str] = None
    ) -> List[ErrorRecoveryOption]:
        """
        Get recovery options for an error
        
        Args:
            error_type: Type of error
            error_severity: Severity of error
            retry_callback: Callback data for retry button
            skip_callback: Callback data for skip button
            
        Returns:
            List of ErrorRecoveryOption
            
        Requirements: 9.5
        """
        options = []
        
        # Retry option for recoverable errors
        if error_severity in (ErrorSeverity.LOW, ErrorSeverity.MEDIUM):
            if error_type in (ErrorType.NETWORK, ErrorType.TELEGRAM_API, ErrorType.TIMEOUT):
                if retry_callback:
                    options.append(ErrorRecoveryOption(
                        label="🔄 تلاش مجدد",
                        callback_data=retry_callback
                    ))
        
        # Skip option for batch operations
        if skip_callback and error_severity != ErrorSeverity.CRITICAL:
            options.append(ErrorRecoveryOption(
                label="⏭️ رد شدن",
                callback_data=skip_callback
            ))
        
        # Cancel/Main menu option (always available)
        options.append(ErrorRecoveryOption(
            label=BTN_CANCEL,
            callback_data="nav:cancel"
        ))
        
        options.append(ErrorRecoveryOption(
            label=BTN_MAIN_MENU,
            callback_data="nav:main_menu"
        ))
        
        return options
    
    def create_recovery_keyboard(
        self,
        recovery_options: List[ErrorRecoveryOption]
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard with recovery options
        
        Args:
            recovery_options: List of recovery options
            
        Returns:
            InlineKeyboardMarkup
        """
        keyboard = []
        
        # Add buttons in rows of 2
        for i in range(0, len(recovery_options), 2):
            row = []
            for j in range(i, min(i + 2, len(recovery_options))):
                option = recovery_options[j]
                row.append(InlineKeyboardButton(
                    text=option.label,
                    callback_data=option.callback_data
                ))
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    async def handle_error(
        self,
        error: Exception,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_context: ErrorContext,
        retry_callback: Optional[str] = None,
        skip_callback: Optional[str] = None
    ) -> None:
        """
        Handle an error with full processing
        
        Args:
            error: Exception that occurred
            update: Telegram update
            context: Bot context
            error_context: Error context information
            retry_callback: Callback data for retry option
            skip_callback: Callback data for skip option
            
        Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
        """
        # Classify error
        error_type, error_severity = self.classify_error(error)
        
        # Log error with full context (also updates statistics)
        self.log_error(error, error_context, error_type, error_severity)
        
        # Translate error to Persian
        user_message = self.translate_error(error, error_type)
        
        # Get recovery options
        recovery_options = self.get_recovery_options(
            error_type,
            error_severity,
            retry_callback,
            skip_callback
        )
        
        # Create keyboard
        keyboard = self.create_recovery_keyboard(recovery_options)
        
        # Send error message to user
        try:
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.message.reply_text(
                    text=user_message,
                    reply_markup=keyboard
                )
            elif update.message:
                await update.message.reply_text(
                    text=user_message,
                    reply_markup=keyboard
                )
        except Exception as send_error:
            self.logger.error(f"Failed to send error message: {send_error}")
        
        # Send admin notification for critical errors
        if error_severity == ErrorSeverity.CRITICAL:
            await self.send_admin_notification(
                error=error,
                error_context=error_context,
                error_type=error_type,
                error_severity=error_severity,
                context=context
            )
    
    async def global_error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Global error handler for the bot application
        
        This is registered with the bot to catch all unhandled errors.
        
        Args:
            update: Telegram update (may be None)
            context: Bot context with error information
            
        Requirements: 9.1, 9.3, 9.4
        """
        error = context.error
        
        if error is None:
            return
        
        # Extract user ID if available
        user_id = None
        if isinstance(update, Update):
            if update.effective_user:
                user_id = update.effective_user.id
        
        # Create error context
        error_context = ErrorContext(
            user_id=user_id,
            operation="unknown",
            details={
                'update_type': type(update).__name__ if update else 'None',
                'has_message': hasattr(update, 'message') if update else False,
                'has_callback_query': hasattr(update, 'callback_query') if update else False
            }
        )
        
        # Classify and log (also updates statistics)
        error_type, error_severity = self.classify_error(error)
        self.log_error(error, error_context, error_type, error_severity)
        
        # Try to notify user
        if isinstance(update, Update):
            try:
                user_message = self.translate_error(error, error_type)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main_menu")
                ]])
                
                if update.callback_query:
                    await update.callback_query.answer()
                    await update.callback_query.message.reply_text(
                        text=user_message,
                        reply_markup=keyboard
                    )
                elif update.message:
                    await update.message.reply_text(
                        text=user_message,
                        reply_markup=keyboard
                    )
            except Exception as send_error:
                self.logger.error(f"Failed to send error message in global handler: {send_error}")
        
        # Notify admins for critical errors
        if error_severity == ErrorSeverity.CRITICAL:
            await self.send_admin_notification(
                error=error,
                error_context=error_context,
                error_type=error_type,
                error_severity=error_severity,
                context=context
            )
    
    def log_error(
        self,
        error: Exception,
        error_context: ErrorContext,
        error_type: ErrorType,
        error_severity: ErrorSeverity
    ) -> None:
        """
        Log error with full context
        
        Args:
            error: Exception that occurred
            error_context: Error context
            error_type: Classified error type
            error_severity: Error severity
            
        Requirements: 9.3, 9.4
        """
        # Update statistics
        self.error_counts[error_type] += 1
        
        # Build log message
        log_msg = (
            f"Error occurred\n"
            f"Type: {error_type.value}\n"
            f"Severity: {error_severity.value}\n"
            f"User: {error_context.user_id}\n"
            f"Operation: {error_context.operation}\n"
            f"Details: {error_context.details}\n"
            f"Error: {type(error).__name__}: {str(error)}"
        )
        
        # Log with appropriate level
        if error_severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_msg, exc_info=True)
        elif error_severity == ErrorSeverity.HIGH:
            self.logger.error(log_msg, exc_info=True)
        elif error_severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)
        
        # Store in recent errors
        error_record = {
            'timestamp': error_context.timestamp,
            'type': error_type.value,
            'severity': error_severity.value,
            'user_id': error_context.user_id,
            'operation': error_context.operation,
            'error_class': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }
        
        self.last_errors.append(error_record)
        
        # Keep only last N errors
        if len(self.last_errors) > self.max_last_errors:
            self.last_errors = self.last_errors[-self.max_last_errors:]
    
    async def send_admin_notification(
        self,
        error: Exception,
        error_context: ErrorContext,
        error_type: ErrorType,
        error_severity: ErrorSeverity,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send error notification to all admins
        
        Args:
            error: Exception that occurred
            error_context: Error context
            error_type: Error type
            error_severity: Error severity
            context: Bot context
            
        Requirements: 15.1, 15.3, 15.4
        """
        if not self.admin_user_ids:
            return
        
        # Build notification message
        notification = (
            f"🚨 **هشدار خطای سیستم**\n\n"
            f"**نوع:** {error_type.value}\n"
            f"**شدت:** {error_severity.value}\n"
            f"**کاربر:** {error_context.user_id or 'نامشخص'}\n"
            f"**عملیات:** {error_context.operation}\n"
            f"**خطا:** {type(error).__name__}\n"
            f"**پیام:** {str(error)[:200]}\n\n"
            f"⏰ زمان: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Send to all admins
        for admin_id in self.admin_user_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as send_error:
                self.logger.error(f"Failed to send admin notification to {admin_id}: {send_error}")
    
    async def send_session_disconnect_notification(
        self,
        session_name: str,
        reason: str,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send notification when a session disconnects
        
        Args:
            session_name: Name of disconnected session
            reason: Reason for disconnection
            context: Bot context
            
        Requirements: 15.1
        """
        if not self.admin_user_ids:
            return
        
        notification = (
            f"⚠️ **قطع اتصال سشن**\n\n"
            f"**سشن:** {session_name}\n"
            f"**دلیل:** {reason}\n\n"
            f"⏰ زمان: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for admin_id in self.admin_user_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as e:
                self.logger.error(f"Failed to send disconnect notification to {admin_id}: {e}")
    
    async def send_operation_failure_notification(
        self,
        operation_type: str,
        operation_id: str,
        user_id: int,
        error_message: str,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send notification when an operation fails critically
        
        Args:
            operation_type: Type of operation
            operation_id: Operation ID
            user_id: User who initiated operation
            error_message: Error message
            context: Bot context
            
        Requirements: 15.3
        """
        if not self.admin_user_ids:
            return
        
        notification = (
            f"❌ **شکست عملیات**\n\n"
            f"**نوع:** {operation_type}\n"
            f"**شناسه:** {operation_id}\n"
            f"**کاربر:** {user_id}\n"
            f"**خطا:** {error_message[:200]}\n\n"
            f"⏰ زمان: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for admin_id in self.admin_user_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as e:
                self.logger.error(f"Failed to send operation failure notification to {admin_id}: {e}")
    
    async def send_monitoring_stop_notification(
        self,
        reason: str,
        affected_channels: List[str],
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send notification when monitoring stops unexpectedly
        
        Args:
            reason: Reason for stopping
            affected_channels: List of affected channel IDs
            context: Bot context
            
        Requirements: 15.4
        """
        if not self.admin_user_ids:
            return
        
        channels_str = "\n".join([f"• {ch}" for ch in affected_channels[:10]])
        if len(affected_channels) > 10:
            channels_str += f"\n• ... و {len(affected_channels) - 10} کانال دیگر"
        
        notification = (
            f"⚠️ **توقف مانیتورینگ**\n\n"
            f"**دلیل:** {reason}\n"
            f"**کانال‌های تحت تأثیر:**\n{channels_str}\n\n"
            f"⏰ زمان: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for admin_id in self.admin_user_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as e:
                self.logger.error(f"Failed to send monitoring stop notification to {admin_id}: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics
        
        Returns:
            Dictionary with error statistics
        """
        return {
            'total_errors': sum(self.error_counts.values()),
            'errors_by_type': {k.value: v for k, v in self.error_counts.items()},
            'recent_errors_count': len(self.last_errors),
            'last_error': self.last_errors[-1] if self.last_errors else None
        }
    
    def reset_statistics(self) -> None:
        """Reset error statistics"""
        self.error_counts = {error_type: 0 for error_type in ErrorType}
        self.last_errors.clear()



class RetryMechanism:
    """
    Retry mechanism with exponential backoff
    
    Provides automatic retry logic for operations that may fail temporarily.
    Uses exponential backoff to avoid overwhelming services.
    
    Requirements: 9.5
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        """
        Initialize retry mechanism
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.logger = logging.getLogger("RetryMechanism")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a retry attempt using exponential backoff
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
    
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        operation_name: str = "operation",
        retry_on: tuple = (NetworkError, TimedOut, RetryAfter),
        **kwargs
    ) -> Any:
        """
        Execute an operation with automatic retry on failure
        
        Args:
            operation: Async function to execute
            *args: Positional arguments for operation
            operation_name: Name for logging
            retry_on: Tuple of exception types to retry on
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of operation
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Executing {operation_name}, attempt {attempt + 1}/{self.max_retries}")
                result = await operation(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"{operation_name} succeeded after {attempt + 1} attempts")
                
                return result
                
            except retry_on as e:
                last_exception = e
                
                # Check if this is a RetryAfter error with specific wait time
                if isinstance(e, RetryAfter):
                    wait_time = e.retry_after
                else:
                    wait_time = self.calculate_delay(attempt)
                
                if attempt < self.max_retries - 1:
                    self.logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        f"{operation_name} failed after {self.max_retries} attempts: {e}"
                    )
            
            except Exception as e:
                # Don't retry on unexpected exceptions
                self.logger.error(f"{operation_name} failed with non-retryable error: {e}")
                raise
        
        # All retries exhausted
        if last_exception:
            raise last_exception
    
    async def execute_with_retry_callback(
        self,
        operation: Callable,
        *args,
        operation_name: str = "operation",
        retry_on: tuple = (NetworkError, TimedOut, RetryAfter),
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation with retry and callback on each retry
        
        Args:
            operation: Async function to execute
            *args: Positional arguments for operation
            operation_name: Name for logging
            retry_on: Tuple of exception types to retry on
            on_retry: Callback function called on each retry (attempt_num, exception)
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of operation
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                result = await operation(*args, **kwargs)
                return result
                
            except retry_on as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    wait_time = self.calculate_delay(attempt)
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            await on_retry(attempt + 1, e)
                        except Exception as callback_error:
                            self.logger.error(f"Error in retry callback: {callback_error}")
                    
                    await asyncio.sleep(wait_time)
            
            except Exception as e:
                raise
        
        if last_exception:
            raise last_exception


class BatchOperationHandler:
    """
    Handler for batch operations with error continuation
    
    Allows batch operations to continue even when individual items fail,
    collecting results and errors for final reporting.
    
    Requirements: 9.5, 12.4
    """
    
    def __init__(self, operation_name: str = "batch_operation"):
        """
        Initialize batch operation handler
        
        Args:
            operation_name: Name of the batch operation
        """
        self.operation_name = operation_name
        self.logger = logging.getLogger(f"BatchOperation.{operation_name}")
        
        self.total_items = 0
        self.successful_items: List[Any] = []
        self.failed_items: List[tuple[Any, Exception]] = []
        self.skipped_items: List[Any] = []
    
    async def process_batch(
        self,
        items: List[Any],
        process_func: Callable,
        continue_on_error: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Process a batch of items with error handling
        
        Args:
            items: List of items to process
            process_func: Async function to process each item
            continue_on_error: Whether to continue on individual failures
            progress_callback: Optional callback for progress updates (current, total)
            
        Returns:
            Dictionary with results:
                - total: Total items
                - successful: Number of successful items
                - failed: Number of failed items
                - skipped: Number of skipped items
                - success_rate: Success rate percentage
                - results: List of successful results
                - errors: List of (item, exception) tuples
        """
        self.total_items = len(items)
        self.successful_items = []
        self.failed_items = []
        self.skipped_items = []
        
        self.logger.info(f"Starting batch operation: {self.total_items} items")
        
        for index, item in enumerate(items):
            try:
                result = await process_func(item)
                self.successful_items.append(result)
                
            except Exception as e:
                self.logger.warning(f"Failed to process item {index + 1}/{self.total_items}: {e}")
                self.failed_items.append((item, e))
                
                if not continue_on_error:
                    self.logger.error("Stopping batch operation due to error")
                    break
            
            # Progress callback
            if progress_callback:
                try:
                    await progress_callback(index + 1, self.total_items)
                except Exception as callback_error:
                    self.logger.error(f"Error in progress callback: {callback_error}")
        
        # Calculate statistics
        processed = len(self.successful_items) + len(self.failed_items)
        success_rate = (len(self.successful_items) / processed * 100) if processed > 0 else 0
        
        self.logger.info(
            f"Batch operation completed: {len(self.successful_items)} successful, "
            f"{len(self.failed_items)} failed, {len(self.skipped_items)} skipped"
        )
        
        return {
            'total': self.total_items,
            'successful': len(self.successful_items),
            'failed': len(self.failed_items),
            'skipped': len(self.skipped_items),
            'success_rate': success_rate,
            'results': self.successful_items,
            'errors': self.failed_items
        }
    
    def get_summary(self) -> str:
        """
        Get a summary of the batch operation
        
        Returns:
            Summary string
        """
        processed = len(self.successful_items) + len(self.failed_items)
        success_rate = (len(self.successful_items) / processed * 100) if processed > 0 else 0
        
        return (
            f"✅ موفق: {len(self.successful_items)}\n"
            f"❌ ناموفق: {len(self.failed_items)}\n"
            f"⏭️ رد شده: {len(self.skipped_items)}\n"
            f"📊 نرخ موفقیت: {success_rate:.1f}%"
        )
    
    def get_failed_items_summary(self, max_items: int = 10) -> str:
        """
        Get summary of failed items
        
        Args:
            max_items: Maximum number of items to include
            
        Returns:
            Summary string
        """
        if not self.failed_items:
            return "هیچ خطایی رخ نداد"
        
        summary_lines = ["❌ **موارد ناموفق:**\n"]
        
        for i, (item, error) in enumerate(self.failed_items[:max_items]):
            summary_lines.append(f"{i + 1}. {item}: {str(error)[:100]}")
        
        if len(self.failed_items) > max_items:
            summary_lines.append(f"\n... و {len(self.failed_items) - max_items} مورد دیگر")
        
        return "\n".join(summary_lines)
