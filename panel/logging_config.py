"""
Logging Configuration for Telegram Bot Panel

This module provides structured logging with user ID and operation context.
It sets up log levels, formatters, and handlers for consistent logging across the bot.

Production features:
- Log rotation with size and time-based rotation
- Separate error log file
- Configurable log levels per environment
- Error alerting support

Requirements: 8.3, 9.4 - Logging infrastructure with proper formatters
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pathlib import Path


class ContextualFormatter(logging.Formatter):
    """
    Custom formatter that includes user ID and operation context in log messages.
    
    Format: [timestamp] [level] [user:user_id] [operation:op_name] message
    
    Requirements:
        - AC-8.3: Log admin actions with timestamp, user ID, and operation details
        - AC-9.4: Log errors with full context for debugging
    """
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """
        Initialize the contextual formatter.
        
        Args:
            fmt: Log format string (optional)
            datefmt: Date format string (optional)
        """
        if fmt is None:
            fmt = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        if datefmt is None:
            datefmt = '%Y-%m-%d %H:%M:%S'
        
        super().__init__(fmt=fmt, datefmt=datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with contextual information.
        
        Args:
            record: LogRecord to format
            
        Returns:
            Formatted log string
        """
        # Add user_id if available in record
        if hasattr(record, 'user_id') and record.user_id:
            user_context = f"[user:{record.user_id}]"
        else:
            user_context = ""
        
        # Add operation if available in record
        if hasattr(record, 'operation') and record.operation:
            operation_context = f"[operation:{record.operation}]"
        else:
            operation_context = ""
        
        # Build the contextual prefix
        context_prefix = f"{user_context} {operation_context}".strip()
        
        # Add context to the message if present
        if context_prefix:
            record.msg = f"{context_prefix} {record.msg}"
        
        return super().format(record)


class ErrorCallbackHandler(logging.Handler):
    """
    Custom handler that calls a callback function for ERROR and CRITICAL logs.
    
    This handler is used for error alerting in production environments.
    The callback can send notifications, trigger alerts, or perform other actions.
    
    Requirements:
        - Task 23.3: Error alerting for production
    """
    
    def __init__(self, callback: Callable[[logging.LogRecord], None]):
        """
        Initialize the error callback handler.
        
        Args:
            callback: Function to call with LogRecord for each error
        """
        super().__init__()
        self.callback = callback
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record by calling the callback.
        
        Args:
            record: LogRecord to process
        """
        try:
            self.callback(record)
        except Exception:
            # Don't let callback errors break logging
            self.handleError(record)


class BotLogger:
    """
    Centralized logger for the bot panel with contextual logging support.
    
    This class provides methods for logging with user and operation context,
    making it easy to track admin actions and debug issues.
    
    Requirements:
        - AC-8.3: Admin action logging
        - AC-9.4: Error logging with full context
    """
    
    def __init__(self, name: str = "TelegramBotPanel"):
        """
        Initialize the bot logger.
        
        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ):
        """
        Log a message with contextual information.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
            exc_info: Include exception info (optional)
        """
        # Create extra dict for context
        extra = {}
        if user_id is not None:
            extra['user_id'] = user_id
        if operation is not None:
            extra['operation'] = operation
        
        # Append details to message if provided
        if details:
            details_str = ", ".join([f"{k}={v}" for k, v in details.items()])
            message = f"{message} | {details_str}"
        
        # Log with context
        self.logger.log(level, message, extra=extra, exc_info=exc_info)
    
    def debug(
        self,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log a DEBUG level message.
        
        Args:
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
        """
        self._log_with_context(logging.DEBUG, message, user_id, operation, details)
    
    def info(
        self,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log an INFO level message.
        
        Args:
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
        """
        self._log_with_context(logging.INFO, message, user_id, operation, details)
    
    def warning(
        self,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log a WARNING level message.
        
        Args:
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
        """
        self._log_with_context(logging.WARNING, message, user_id, operation, details)
    
    def error(
        self,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ):
        """
        Log an ERROR level message.
        
        Args:
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
            exc_info: Include exception info (default: True)
        """
        self._log_with_context(logging.ERROR, message, user_id, operation, details, exc_info)
    
    def critical(
        self,
        message: str,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ):
        """
        Log a CRITICAL level message.
        
        Args:
            message: Log message
            user_id: User ID for context (optional)
            operation: Operation name for context (optional)
            details: Additional details dictionary (optional)
            exc_info: Include exception info (default: True)
        """
        self._log_with_context(logging.CRITICAL, message, user_id, operation, details, exc_info)
    
    def log_admin_action(
        self,
        user_id: int,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log an admin action with full context.
        
        This is a convenience method specifically for logging admin actions
        as required by AC-8.3.
        
        Args:
            user_id: Admin user ID
            action: Action performed
            details: Additional action details (optional)
            
        Requirements:
            - AC-8.3: Log admin actions with timestamp, user ID, and operation details
        """
        self.info(
            f"Admin action: {action}",
            user_id=user_id,
            operation="admin_action",
            details=details
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    enable_rotation: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 7,
    error_log_file: Optional[str] = None,
    error_callback: Optional[Callable[[logging.LogRecord], None]] = None
) -> None:
    """
    Set up logging configuration for the bot panel.
    
    This function configures the root logger with appropriate handlers and formatters.
    It supports logging to console and/or file with structured formatting.
    
    Production features:
    - Log rotation based on file size
    - Separate error log file
    - Error callback for alerting
    - Configurable backup retention
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional, if None only console logging)
        log_to_console: Whether to log to console (default: True)
        enable_rotation: Enable log rotation (default: True)
        max_bytes: Maximum log file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 7)
        error_log_file: Separate file for ERROR and CRITICAL logs (optional)
        error_callback: Callback function for error alerting (optional)
        
    Requirements:
        - AC-8.3: Structured logging with user ID and operation context
        - AC-9.4: Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - Task 23.3: Production logging with rotation and error alerting
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = ContextualFormatter()
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        if enable_rotation:
            # Use rotating file handler for production
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            # Use simple file handler for development
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Add separate error log file if specified
    if error_log_file:
        error_path = Path(error_log_file)
        error_path.parent.mkdir(parents=True, exist_ok=True)
        
        if enable_rotation:
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        
        # Only log ERROR and CRITICAL to error file
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    # Add error callback handler if specified
    if error_callback:
        callback_handler = ErrorCallbackHandler(error_callback)
        callback_handler.setLevel(logging.ERROR)
        callback_handler.setFormatter(formatter)
        root_logger.addHandler(callback_handler)
    
    # Log the configuration
    logger = logging.getLogger("TelegramBotPanel")
    logger.info(
        f"Logging configured: level={log_level}, file={log_file}, "
        f"console={log_to_console}, rotation={enable_rotation}, "
        f"error_file={error_log_file}"
    )


def get_logger(name: str = "TelegramBotPanel") -> BotLogger:
    """
    Get a BotLogger instance.
    
    Args:
        name: Logger name
        
    Returns:
        BotLogger instance
    """
    return BotLogger(name)



def setup_production_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    error_callback: Optional[Callable[[logging.LogRecord], None]] = None
) -> None:
    """
    Set up production-ready logging configuration.
    
    This is a convenience function that configures logging with production best practices:
    - Main log file with rotation (10MB, 7 backups)
    - Separate error log file
    - Console logging disabled (use systemd/docker logs instead)
    - Error callback for alerting
    
    Args:
        log_dir: Directory for log files (default: "logs")
        log_level: Logging level (default: "INFO")
        error_callback: Callback for error alerting (optional)
        
    Example:
        >>> def alert_on_error(record):
        ...     # Send alert to admins
        ...     send_telegram_alert(f"Error: {record.getMessage()}")
        >>> setup_production_logging(error_callback=alert_on_error)
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    main_log = log_dir_path / "bot.log"
    error_log = log_dir_path / "error.log"
    
    setup_logging(
        log_level=log_level,
        log_file=str(main_log),
        log_to_console=False,  # Use systemd/docker logs
        enable_rotation=True,
        max_bytes=10 * 1024 * 1024,  # 10MB
        backup_count=7,  # Keep 7 days of logs
        error_log_file=str(error_log),
        error_callback=error_callback
    )


def setup_development_logging(log_level: str = "DEBUG") -> None:
    """
    Set up development logging configuration.
    
    This is a convenience function for development environments:
    - Console logging only
    - DEBUG level
    - No rotation
    - No error callback
    
    Args:
        log_level: Logging level (default: "DEBUG")
    """
    setup_logging(
        log_level=log_level,
        log_file=None,
        log_to_console=True,
        enable_rotation=False
    )


def get_log_stats(log_file: str) -> Dict[str, Any]:
    """
    Get statistics about a log file.
    
    Args:
        log_file: Path to log file
        
    Returns:
        Dictionary with log statistics:
        - size: File size in bytes
        - lines: Number of lines
        - errors: Number of ERROR lines
        - warnings: Number of WARNING lines
        - last_modified: Last modification timestamp
    """
    log_path = Path(log_file)
    
    if not log_path.exists():
        return {
            'size': 0,
            'lines': 0,
            'errors': 0,
            'warnings': 0,
            'last_modified': None
        }
    
    stats = {
        'size': log_path.stat().st_size,
        'lines': 0,
        'errors': 0,
        'warnings': 0,
        'last_modified': datetime.fromtimestamp(log_path.stat().st_mtime)
    }
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                stats['lines'] += 1
                if '[ERROR]' in line:
                    stats['errors'] += 1
                elif '[WARNING]' in line:
                    stats['warnings'] += 1
    except Exception:
        pass
    
    return stats


def cleanup_old_logs(log_dir: str, days: int = 30) -> int:
    """
    Clean up log files older than specified days.
    
    Args:
        log_dir: Directory containing log files
        days: Delete files older than this many days (default: 30)
        
    Returns:
        Number of files deleted
    """
    log_dir_path = Path(log_dir)
    
    if not log_dir_path.exists():
        return 0
    
    deleted = 0
    cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
    
    for log_file in log_dir_path.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                deleted += 1
            except Exception:
                pass
    
    return deleted
