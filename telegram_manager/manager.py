"""
TelegramSessionManager class - Multi-session management
"""

import asyncio
import logging
import os
import random
import time
from typing import List, Dict, Optional, Callable
from .session import TelegramSession
from .config import SessionConfig
from .database import DatabaseManager
from .load_balancer import LoadBalancer
from .constants import (
    API_ID, 
    API_HASH, 
    DB_PATH, 
    SESSION_COUNT,
    MAX_CONCURRENT_OPERATIONS,
    DAILY_MESSAGES_LIMIT,
    DAILY_GROUPS_LIMIT,
    BLACKLIST_ENABLED,
    BLACKLIST_STORAGE_PATH,
    BLACKLIST_FAILURE_THRESHOLD,
    BLACKLIST_AUTO_ADD
)


class TelegramSessionManager:
    """
    Manages multiple Telegram sessions with load balancing and coordinated operations
    
    LOCK ACQUISITION ORDER (to prevent deadlocks):
    =====================================================
    Locks must ALWAYS be acquired in this strict order:
    
    1. Manager-level locks (global_task_lock, metrics_lock) - THIS CLASS
    2. Manager-level semaphores (scrape_semaphore, operation_semaphore) - THIS CLASS
    3. Session-level locks (session_locks) - THIS CLASS
    4. Session operation lock (operation_lock in TelegramSession)
    5. Session task lock (task_lock in TelegramSession)
    6. Session handler lock (_handler_lock in TelegramSession)
    
    NEVER acquire locks in reverse order!
    If a lower-level lock is held, NEVER attempt to acquire a higher-level lock.
    
    Example correct order:
        async with self.metrics_lock:  # Manager lock (level 1)
            async with self.scrape_semaphore:  # Manager semaphore (level 2)
                async with self.session_locks[name]:  # Session lock (level 3)
                    async with session.operation_lock:  # Session operation lock (level 4)
                        # ... do work ...
    
    Example INCORRECT order (will cause deadlock):
        async with session.operation_lock:  # Session operation lock (level 4)
            async with self.metrics_lock:  # Manager lock (level 1) - WRONG! Higher level after lower
                # ... this can deadlock ...
    =====================================================
    """
    
    def __init__(self, max_concurrent_operations: int = 3, load_balancing_strategy: str = "round_robin"):
        """
        Initialize session manager
        
        Args:
            max_concurrent_operations: Maximum concurrent operations across all sessions
            load_balancing_strategy: Load balancing strategy ('round_robin' or 'least_loaded')
        """
        self.sessions: Dict[str, TelegramSession] = {}
        self.session_locks: Dict[str, asyncio.Lock] = {}
        self.operation_semaphore = asyncio.Semaphore(max_concurrent_operations)
        self.logger = logging.getLogger("SessionManager")
        
        # Lock acquisition timeout (default 30 seconds)
        self.lock_timeout: float = 30.0
        
        # Global monitoring configuration
        self.global_monitoring_config: Optional[List[Dict]] = None
        
        # Manager-level concurrency controls (Task 6.1)
        self.scrape_semaphore = asyncio.Semaphore(5)  # Limit concurrent scrapes to 5
        self.active_scrape_count: int = 0  # Track active scrape operations
        
        # Global task tracking (Task 6.2)
        self.global_tasks: Dict[str, set] = {}  # Tasks by session name
        self.global_task_lock = asyncio.Lock()  # Protect global task registry
        
        # Operation metrics tracking (Task 6.3)
        self.operation_metrics: Dict[str, int] = {
            'scraping': 0,
            'monitoring': 0,
            'sending': 0,
            'other': 0
        }
        self.metrics_lock = asyncio.Lock()  # Protect metrics updates
        
        # Session load balancing (Task 7.1, Task 10)
        self.session_load: Dict[str, int] = {}  # Active operations per session
        self.load_balancer = LoadBalancer(strategy=load_balancing_strategy)
        
        # Operation retry configuration (Task 8.1, Task 12)
        self.retry_config: Dict[str, int] = {
            'scraping': 2,  # Retry scraping operations twice (total 3 attempts)
            'monitoring': 0,  # Don't retry monitoring
            'sending': 3  # Retry sending up to 3 times (total 4 attempts) - Requirement 5.1
        }
        self.retry_backoff_base: float = 2.0  # Exponential backoff base (seconds) - Requirement 5.3
        
        # Session health monitoring (Task 7, Task 14)
        from .health_monitor import SessionHealthMonitor
        self.health_monitor = SessionHealthMonitor()
        
        # Operation queue for when all sessions are unavailable (Task 14, Requirement 23.4)
        from .models import OperationQueue
        self.operation_queue = OperationQueue()
        self.queue_lock = asyncio.Lock()  # Protect queue operations
        
        # Pending operations per session (for redistribution on failure) (Requirement 23.1, 23.5)
        self.pending_operations: Dict[str, List] = {}  # session_name -> list of operations
        self.pending_ops_lock = asyncio.Lock()  # Protect pending operations
        
        # Blacklist management (user-blocking-detection feature)
        from .blacklist import BlocklistManager
        from .models import DeliveryTracker
        self.blacklist_manager = BlocklistManager(storage_path=BLACKLIST_STORAGE_PATH)
        self.delivery_tracker = DeliveryTracker()
        self.blacklist_enabled = BLACKLIST_ENABLED
        self.blacklist_failure_threshold = BLACKLIST_FAILURE_THRESHOLD
        self.blacklist_auto_add = BLACKLIST_AUTO_ADD

    async def load_sessions_from_db(self) -> Dict[str, bool]:
        """
        Load sessions from database instead of config file
        
        Returns:
            Dict mapping session names to load success status
        """
        try:
            # Load blacklist from storage on system startup (Requirement 3.1)
            # This should happen regardless of whether accounts are found
            if self.blacklist_enabled:
                try:
                    await self.blacklist_manager.load()
                    self.logger.info("✅ Loaded blacklist from storage")
                except Exception as e:
                    self.logger.error(f"❌ Failed to load blacklist: {e}")
            
            # Reset failure counts on system startup (Requirement 4.5)
            # This should happen regardless of whether accounts are found
            self.delivery_tracker.reset_all()
            self.logger.info("✅ Reset delivery failure counts")
            
            # Initialize database manager
            db_manager = DatabaseManager(DB_PATH)
            
            # Get all accounts from database
            accounts = db_manager.get_all_accounts()
            # Get only the number of accounts needed
            accounts = accounts[-SESSION_COUNT:]
            
            if not accounts:
                self.logger.error("❌ No accounts found in database")
                return {}
            
            # Convert to session configs
            session_configs = db_manager.convert_to_session_configs(accounts, API_ID, API_HASH)
            
            # Load sessions using the existing method
            return await self.load_sessions(session_configs)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load sessions from database: {e}")
            return {}

    async def load_sessions(self, session_configs: List[SessionConfig]) -> Dict[str, bool]:
        """
        Load multiple sessions from configuration
        
        Args:
            session_configs: List of SessionConfig objects
            
        Returns:
            Dict mapping session names to load success status
        """
        results = {}
        
        for config in session_configs:
            try:
                session = TelegramSession(
                    config.session_file, 
                    config.api_id, 
                    config.api_hash
                )
                
                if await session.connect():
                    self.sessions[config.name] = session
                    self.session_locks[config.name] = asyncio.Lock()
                    # Initialize global task tracking for this session (Task 6.2)
                    async with self.global_task_lock:
                        self.global_tasks[config.name] = set()
                    # Initialize session load tracking (Task 7.1)
                    async with self.metrics_lock:
                        self.session_load[config.name] = 0
                    results[config.name] = True
                    self.logger.info(f"✅ Loaded session: {config.name}")
                else:
                    # Check if session is corrupted and should be removed
                    if hasattr(session, '_is_corrupted') and session._is_corrupted:
                        self.logger.warning(f"🗑️ Removing corrupted session file: {config.session_file}")
                        try:
                            if os.path.exists(config.session_file):
                                os.remove(config.session_file)
                            # Also remove .session-journal if it exists
                            journal_file = config.session_file + "-journal"
                            if os.path.exists(journal_file):
                                os.remove(journal_file)
                        except Exception as remove_error:
                            self.logger.error(f"❌ Failed to remove corrupted session file: {remove_error}")
                    
                    results[config.name] = False
                    self.logger.error(f"❌ Failed to load session: {config.name}")
                    
            except Exception as e:
                results[config.name] = False
                self.logger.error(f"❌ Error loading session {config.name}: {e}")
        
        # Start health monitoring if any sessions were loaded successfully (Task 18, Requirement 16.1, 16.2)
        if any(results.values()):
            try:
                await self.start_health_monitoring()
                self.logger.info(f"✅ Started health monitoring for {sum(results.values())} sessions")
            except Exception as e:
                self.logger.error(f"❌ Failed to start health monitoring: {e}")
        
        return results

    async def start_global_monitoring(self, targets: List[Dict]):
        """
        Start monitoring on all sessions
        
        Args:
            targets: List of monitoring target configurations
        """
        self.global_monitoring_config = targets
        
        tasks = []
        for session_name in self.sessions:
            task = asyncio.create_task(
                self._start_session_monitoring(session_name, targets)
            )
            # Track monitoring tasks globally (Task 6.2)
            await self.register_task_globally(session_name, task)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if result is True)
        self.logger.info(f"🌐 Started monitoring on {success_count}/{len(self.sessions)} sessions")

    async def _start_session_monitoring(self, session_name: str, targets: List[Dict]) -> bool:
        """Start monitoring for a specific session"""
        # Use context manager to ensure lock is always released (Requirement 7.1)
        async with self.session_locks[session_name]:
            session = self.sessions[session_name]
            await self.increment_operation_metric('monitoring')  # Task 6.3
            try:
                result = await session.start_monitoring(targets)
                if not result:
                    # If monitoring failed to start, decrement the metric
                    await self.decrement_operation_metric('monitoring')
                return result
            except Exception as e:
                # Ensure metric is decremented on error (Requirement 7.1)
                await self.decrement_operation_metric('monitoring')
                # Log error with context (Requirement 7.1)
                self.logger.error(
                    f"❌ Failed to start monitoring on session {session_name}: {e}"
                )
                raise

    async def stop_global_monitoring(self):
        """
        Stop monitoring on all sessions with timeout and cleanup (Task 10.4)
        
        Requirements: 6.1, 6.2
        """
        self.logger.info("🛑 Stopping global monitoring...")
        
        # Collect all monitoring tasks from global registry
        monitoring_tasks = []
        async with self.global_task_lock:
            for session_name in self.sessions:
                if session_name in self.global_tasks:
                    # Get tasks that are monitoring-related
                    for task in list(self.global_tasks[session_name]):
                        if not task.done():
                            monitoring_tasks.append((session_name, task))
        
        # Stop monitoring on all sessions
        stop_tasks = []
        for session_name in self.sessions:
            task = asyncio.create_task(self.sessions[session_name].stop_monitoring())
            stop_tasks.append((session_name, task))
        
        # Wait for all stop operations with timeout (5 seconds per requirement 6.2)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[t for _, t in stop_tasks], return_exceptions=True),
                timeout=5.0
            )
            
            # Decrement monitoring metrics for successfully stopped sessions (Task 6.3)
            for result in results:
                if not isinstance(result, Exception):
                    await self.decrement_operation_metric('monitoring')
                    
        except asyncio.TimeoutError:
            self.logger.warning("⏱️ Some monitoring operations did not stop within 5 seconds")
            # Still decrement metrics for sessions that might have stopped
            for session_name in self.sessions:
                # Check if session is still monitoring
                session = self.sessions[session_name]
                if not session.is_monitoring:
                    await self.decrement_operation_metric('monitoring')
        
        # Cancel any remaining monitoring tasks with timeout
        if monitoring_tasks:
            self.logger.info(f"🔄 Cancelling {len(monitoring_tasks)} monitoring tasks...")
            for session_name, task in monitoring_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[t for _, t in monitoring_tasks], return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("⏱️ Some monitoring tasks did not cancel within 5 seconds")
        
        # Clean up monitoring tasks from global registry (Task 6.2)
        async with self.global_task_lock:
            for session_name in list(self.global_tasks.keys()):
                # Remove completed/cancelled tasks
                if session_name in self.global_tasks:
                    self.global_tasks[session_name] = {
                        task for task in self.global_tasks[session_name]
                        if not task.done()
                    }
                    # Remove empty sets
                    if not self.global_tasks[session_name]:
                        del self.global_tasks[session_name]
        
        self.global_monitoring_config = None
        self.logger.info("✅ Global monitoring stopped and cleaned up")

    async def send_text_messages_bulk(
        self,
        recipients: List[str],
        message: str,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send text messages to multiple recipients with load balancing
        
        Each recipient is assigned to exactly ONE session to prevent duplicate messages.
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            message: Text message to send
            delay: Delay between sends within each session (seconds)
            skip_invalid: Whether to skip invalid recipients or fail early
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 4.1, 4.2, 4.3, 11.1, 11.2, 21.1, 21.2
        """
        from .models import MessageResult, RecipientValidator
        
        results = {}
        
        # Validate recipients before sending (Requirement 6.1)
        validation_result = RecipientValidator.validate_recipients(recipients)
        
        if not validation_result.valid:
            if skip_invalid:
                # Filter to valid recipients only (Requirement 6.5)
                valid_recipients, invalid_recipients = RecipientValidator.filter_valid_recipients(recipients)
                
                # Log warnings for invalid recipients
                for invalid in invalid_recipients:
                    self.logger.warning(f"⚠️ Skipping invalid recipient: {invalid}")
                    results[invalid] = MessageResult(
                        recipient=invalid,
                        success=False,
                        session_used='',
                        error='Invalid recipient identifier'
                    )
                
                # Continue with valid recipients
                recipients = valid_recipients
                
                if not recipients:
                    self.logger.error("❌ No valid recipients after filtering")
                    return results
            else:
                # Fail early with validation errors
                self.logger.error(f"❌ Recipient validation failed: {validation_result.errors}")
                for recipient in recipients:
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used='',
                        error='Validation failed'
                    )
                return results
        
        if not self.sessions:
            self.logger.error("❌ No sessions available for sending messages")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='No sessions available'
                )
            return results
        
        # Get list of connected sessions
        connected_sessions = [name for name, session in self.sessions.items() if session.is_connected]
        
        if not connected_sessions:
            self.logger.error("❌ No connected sessions available")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='No connected sessions available'
                )
            return results
        
        # Distribute recipients across sessions (Requirement 1.2)
        # Each recipient is assigned to exactly ONE session (Requirement 1.3)
        recipient_assignments = {}
        for i, recipient in enumerate(recipients):
            # Use load balancer to select session for this recipient
            session_name = self._get_available_session()
            if session_name:
                recipient_assignments[recipient] = session_name
            else:
                # No session available, assign to least loaded
                session_name = min(
                    connected_sessions,
                    key=lambda s: self.session_load.get(s, 0)
                )
                recipient_assignments[recipient] = session_name
        
        # Group recipients by assigned session
        session_recipients = {}
        for recipient, session_name in recipient_assignments.items():
            if session_name not in session_recipients:
                session_recipients[session_name] = []
            session_recipients[session_name].append(recipient)
        
        # Log distribution with structured logging (Requirement 13.1)
        self.logger.info(
            f"📊 Distributing {len(recipients)} recipients across {len(session_recipients)} sessions",
            extra={
                'operation_type': 'text_message_send',
                'recipient_count': len(recipients),
                'session_count': len(session_recipients),
                'session_distribution': {name: len(recips) for name, recips in session_recipients.items()},
                'priority': priority,
                'delay': delay
            }
        )
        for session_name, session_recips in session_recipients.items():
            self.logger.debug(
                f"  - {session_name}: {len(session_recips)} recipients",
                extra={
                    'session_name': session_name,
                    'recipient_count': len(session_recips)
                }
            )
        
        # Send messages from each session concurrently
        send_tasks = []
        for session_name, session_recips in session_recipients.items():
            task = asyncio.create_task(
                self._send_text_from_session(
                    session_name,
                    session_recips,
                    message,
                    delay
                )
            )
            send_tasks.append(task)
        
        # Wait for all sends to complete and aggregate results
        task_results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger.error(f"❌ Send task failed: {task_result}")
            elif isinstance(task_result, dict):
                results.update(task_result)
        
        # Log summary with structured logging (Requirement 1.6, 13.5)
        succeeded = sum(1 for r in results.values() if r.success)
        failed = len(results) - succeeded
        self.logger.info(
            f"✅ Bulk send complete: {succeeded} succeeded, {failed} failed out of {len(results)} total",
            extra={
                'operation_type': 'text_message_send',
                'total_messages': len(results),
                'succeeded': succeeded,
                'failed': failed,
                'success_rate': (succeeded / len(results) * 100) if results else 0,
                'session_count': len(session_recipients)
            }
        )
        
        return results
    
    async def _send_text_from_session(
        self,
        session_name: str,
        recipients: List[str],
        message: str,
        delay: float
    ) -> Dict[str, 'MessageResult']:
        """
        Send text messages from a specific session
        
        Args:
            session_name: Name of the session to use
            recipients: List of recipients for this session
            message: Message to send
            delay: Delay between sends
            
        Returns:
            Dict mapping recipients to MessageResult objects
        """
        from .models import MessageResult
        import time
        
        results = {}
        session = self.sessions[session_name]
        
        # Increment session load (Requirement 4.2)
        await self.increment_session_load(session_name)
        
        # Increment operation metric (Requirement 11.1)
        await self.increment_operation_metric('sending')
        
        try:
            for i, recipient in enumerate(recipients):
                # Check blacklist before attempting delivery (Requirement 2.1)
                is_blacklisted = await self.blacklist_manager.is_blacklisted(recipient)
                
                if is_blacklisted:
                    # Skip delivery and log event (Requirement 2.2, 2.3)
                    self.logger.info(
                        f"⏭️ Skipping blacklisted user {recipient}",
                        extra={
                            'operation_type': 'text_message_send',
                            'recipient': recipient,
                            'blacklisted': True,
                            'session_name': session_name
                        }
                    )
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used=session_name,
                        error='User is blacklisted',
                        blacklisted=True
                    )
                    
                    # Apply delay even for skipped recipients to maintain rate limiting
                    if i < len(recipients) - 1:
                        await asyncio.sleep(delay)
                    
                    continue
                
                try:
                    # Send message with retry logic (Requirement 5.1)
                    result_dict = await self._execute_with_retry(
                        'sending',
                        session.send_text_message,
                        recipient,
                        message
                    )
                    
                    # Create MessageResult (Requirement 1.4, 1.5)
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=result_dict.get('success', False),
                        session_used=session_name,
                        error=result_dict.get('error')
                    )
                    
                    # Track delivery result (Requirement 4.1, 4.2)
                    if results[recipient].success:
                        # Record success - resets failure count
                        self.delivery_tracker.record_success(recipient)
                        
                        # Log success with structured logging (Requirement 13.2, 13.3)
                        self.logger.debug(
                            f"✅ Sent to {recipient} via {session_name}",
                            extra={
                                'operation_type': 'text_message_send',
                                'recipient': recipient,
                                'session_used': session_name,
                                'success': True
                            }
                        )
                    else:
                        # Record failure and check for block detection (Requirement 1.1, 1.2, 1.3, 1.4)
                        error = Exception(results[recipient].error) if results[recipient].error else Exception("Unknown error")
                        await self._handle_delivery_failure(recipient, error, session_name)
                        
                        # Log failure with structured logging (Requirement 13.2, 13.3)
                        self.logger.warning(
                            f"❌ Failed to send to {recipient} via {session_name}: {results[recipient].error}",
                            extra={
                                'operation_type': 'text_message_send',
                                'recipient': recipient,
                                'session_used': session_name,
                                'success': False,
                                'error': results[recipient].error
                            }
                        )
                    
                except Exception as e:
                    # Record failure (Requirement 1.5)
                    self.logger.error(f"❌ Error sending to {recipient}: {e}")
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used=session_name,
                        error=str(e)
                    )
                    
                    # Handle delivery failure for block detection (Requirement 1.1, 1.2, 1.3, 1.4)
                    await self._handle_delivery_failure(recipient, e, session_name)
                
                # Apply delay between sends (Requirement 3.1, 3.5)
                if i < len(recipients) - 1:
                    self.logger.debug(
                        f"⏳ Applying delay of {delay}s before next send",
                        extra={
                            'operation_type': 'text_message_send',
                            'delay_seconds': delay,
                            'session_name': session_name,
                            'current_recipient': i + 1,
                            'total_recipients': len(recipients)
                        }
                    )
                    await asyncio.sleep(delay)
        
        finally:
            # Always decrement counters (Requirement 4.3, 11.2)
            await self.decrement_session_load(session_name)
            await self.decrement_operation_metric('sending')
        
        return results
    
    async def send_media_messages_bulk(
        self,
        recipients: List[str],
        media_path: str,
        media_type: str,
        caption: Optional[str] = None,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send media messages to multiple recipients with load balancing
        
        Each recipient is assigned to exactly ONE session to prevent duplicate messages.
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            media_path: Path to media file
            media_type: Type of media ('image', 'video', 'document')
            caption: Optional caption for the media
            delay: Delay between sends within each session (seconds)
            skip_invalid: Whether to skip invalid recipients or fail early
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 4.1, 4.2, 4.3, 11.1, 11.2, 21.1, 21.2
        """
        from .models import MessageResult, RecipientValidator, MediaHandler
        
        results = {}
        
        # Validate media file (Requirement 2.2, 2.3)
        format_validation = MediaHandler.validate_format(media_path, media_type)
        if not format_validation.valid:
            error_msg = '; '.join([e.message for e in format_validation.errors])
            self.logger.error(f"❌ Media format validation failed: {error_msg}")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=f'Media validation failed: {error_msg}'
                )
            return results
        
        size_validation = MediaHandler.validate_size(media_path, media_type)
        if not size_validation.valid:
            error_msg = '; '.join([e.message for e in size_validation.errors])
            self.logger.error(f"❌ Media size validation failed: {error_msg}")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=f'Media validation failed: {error_msg}'
                )
            return results
        
        # Validate recipients before sending (Requirement 6.1)
        validation_result = RecipientValidator.validate_recipients(recipients)
        
        if not validation_result.valid:
            if skip_invalid:
                # Filter to valid recipients only (Requirement 6.5)
                valid_recipients, invalid_recipients = RecipientValidator.filter_valid_recipients(recipients)
                
                # Log warnings for invalid recipients
                for invalid in invalid_recipients:
                    self.logger.warning(f"⚠️ Skipping invalid recipient: {invalid}")
                    results[invalid] = MessageResult(
                        recipient=invalid,
                        success=False,
                        session_used='',
                        error='Invalid recipient identifier'
                    )
                
                # Continue with valid recipients
                recipients = valid_recipients
                
                if not recipients:
                    self.logger.error("❌ No valid recipients after filtering")
                    return results
            else:
                # Fail early with validation errors
                self.logger.error(f"❌ Recipient validation failed: {validation_result.errors}")
                for recipient in recipients:
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used='',
                        error='Validation failed'
                    )
                return results
        
        if not self.sessions:
            self.logger.error("❌ No sessions available for sending media")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='No sessions available'
                )
            return results
        
        # Get list of connected sessions
        connected_sessions = [name for name, session in self.sessions.items() if session.is_connected]
        
        if not connected_sessions:
            self.logger.error("❌ No connected sessions available")
            for recipient in recipients:
                results[recipient] = MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='No connected sessions available'
                )
            return results
        
        # Distribute recipients across sessions (Requirement 2.4)
        # Each recipient is assigned to exactly ONE session (Requirement 2.5)
        recipient_assignments = {}
        for i, recipient in enumerate(recipients):
            # Use load balancer to select session for this recipient
            session_name = self._get_available_session()
            if session_name:
                recipient_assignments[recipient] = session_name
            else:
                # No session available, assign to least loaded
                session_name = min(
                    connected_sessions,
                    key=lambda s: self.session_load.get(s, 0)
                )
                recipient_assignments[recipient] = session_name
        
        # Group recipients by assigned session
        session_recipients = {}
        for recipient, session_name in recipient_assignments.items():
            if session_name not in session_recipients:
                session_recipients[session_name] = []
            session_recipients[session_name].append(recipient)
        
        # Log distribution with structured logging (Requirement 13.1)
        self.logger.info(
            f"📊 Distributing {len(recipients)} recipients across {len(session_recipients)} sessions for {media_type}",
            extra={
                'operation_type': 'media_message_send',
                'media_type': media_type,
                'recipient_count': len(recipients),
                'session_count': len(session_recipients),
                'session_distribution': {name: len(recips) for name, recips in session_recipients.items()},
                'priority': priority,
                'delay': delay,
                'has_caption': caption is not None
            }
        )
        for session_name, session_recips in session_recipients.items():
            self.logger.debug(
                f"  - {session_name}: {len(session_recips)} recipients",
                extra={
                    'session_name': session_name,
                    'recipient_count': len(session_recips),
                    'media_type': media_type
                }
            )
        
        # Send media from each session concurrently
        send_tasks = []
        for session_name, session_recips in session_recipients.items():
            task = asyncio.create_task(
                self._send_media_from_session(
                    session_name,
                    session_recips,
                    media_path,
                    media_type,
                    caption,
                    delay
                )
            )
            send_tasks.append(task)
        
        # Wait for all sends to complete and aggregate results
        task_results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger.error(f"❌ Send task failed: {task_result}")
            elif isinstance(task_result, dict):
                results.update(task_result)
        
        # Log summary with structured logging (Requirement 2.6, 13.5)
        succeeded = sum(1 for r in results.values() if r.success)
        failed = len(results) - succeeded
        self.logger.info(
            f"✅ Bulk media send complete: {succeeded} succeeded, {failed} failed out of {len(results)} total",
            extra={
                'operation_type': 'media_message_send',
                'media_type': media_type,
                'total_messages': len(results),
                'succeeded': succeeded,
                'failed': failed,
                'success_rate': (succeeded / len(results) * 100) if results else 0,
                'session_count': len(session_recipients),
                'has_caption': caption is not None
            }
        )
        
        return results
    
    async def _send_media_from_session(
        self,
        session_name: str,
        recipients: List[str],
        media_path: str,
        media_type: str,
        caption: Optional[str],
        delay: float
    ) -> Dict[str, 'MessageResult']:
        """
        Send media messages from a specific session
        
        Args:
            session_name: Name of the session to use
            recipients: List of recipients for this session
            media_path: Path to media file
            media_type: Type of media ('image', 'video', 'document')
            caption: Optional caption
            delay: Delay between sends
            
        Returns:
            Dict mapping recipients to MessageResult objects
        """
        from .models import MessageResult
        import time
        
        results = {}
        session = self.sessions[session_name]
        
        # Increment session load (Requirement 4.2)
        await self.increment_session_load(session_name)
        
        # Increment operation metric (Requirement 11.1)
        await self.increment_operation_metric('sending')
        
        try:
            for i, recipient in enumerate(recipients):
                # Check blacklist before attempting delivery (Requirement 2.1)
                is_blacklisted = await self.blacklist_manager.is_blacklisted(recipient)
                
                if is_blacklisted:
                    # Skip delivery and log event (Requirement 2.2, 2.3)
                    self.logger.info(
                        f"⏭️ Skipping blacklisted user {recipient}",
                        extra={
                            'operation_type': 'media_message_send',
                            'media_type': media_type,
                            'recipient': recipient,
                            'blacklisted': True,
                            'session_name': session_name
                        }
                    )
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used=session_name,
                        error='User is blacklisted',
                        blacklisted=True
                    )
                    
                    # Apply delay even for skipped recipients to maintain rate limiting
                    if i < len(recipients) - 1:
                        await asyncio.sleep(delay)
                    
                    continue
                
                try:
                    # Select appropriate send method based on media type
                    if media_type == 'image':
                        send_method = session.send_image_message
                    elif media_type == 'video':
                        send_method = session.send_video_message
                    elif media_type == 'document':
                        send_method = session.send_document_message
                    else:
                        raise ValueError(f"Unsupported media type: {media_type}")
                    
                    # Send media with retry logic (Requirement 5.1)
                    result_dict = await self._execute_with_retry(
                        'sending',
                        send_method,
                        recipient,
                        media_path,
                        caption
                    )
                    
                    # Create MessageResult
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=result_dict.get('success', False),
                        session_used=session_name,
                        error=result_dict.get('error')
                    )
                    
                    # Track delivery result (Requirement 4.1, 4.2)
                    if results[recipient].success:
                        # Record success - resets failure count
                        self.delivery_tracker.record_success(recipient)
                        
                        # Log success with structured logging (Requirement 13.2, 13.3)
                        self.logger.debug(
                            f"✅ Sent {media_type} to {recipient} via {session_name}",
                            extra={
                                'operation_type': 'media_message_send',
                                'media_type': media_type,
                                'recipient': recipient,
                                'session_used': session_name,
                                'success': True,
                                'has_caption': caption is not None
                            }
                        )
                    else:
                        # Record failure and check for block detection (Requirement 1.1, 1.2, 1.3, 1.4)
                        error = Exception(results[recipient].error) if results[recipient].error else Exception("Unknown error")
                        await self._handle_delivery_failure(recipient, error, session_name)
                        
                        # Log failure with structured logging (Requirement 13.2, 13.3)
                        self.logger.warning(
                            f"❌ Failed to send {media_type} to {recipient} via {session_name}: {results[recipient].error}",
                            extra={
                                'operation_type': 'media_message_send',
                                'media_type': media_type,
                                'recipient': recipient,
                                'session_used': session_name,
                                'success': False,
                                'error': results[recipient].error
                            }
                        )
                    
                except Exception as e:
                    # Record failure
                    self.logger.error(f"❌ Error sending {media_type} to {recipient}: {e}")
                    results[recipient] = MessageResult(
                        recipient=recipient,
                        success=False,
                        session_used=session_name,
                        error=str(e)
                    )
                    
                    # Handle delivery failure for block detection (Requirement 1.1, 1.2, 1.3, 1.4)
                    await self._handle_delivery_failure(recipient, e, session_name)
                
                # Apply delay between sends (Requirement 3.1, 3.5)
                if i < len(recipients) - 1:
                    self.logger.debug(
                        f"⏳ Applying delay of {delay}s before next send",
                        extra={
                            'operation_type': 'media_message_send',
                            'media_type': media_type,
                            'delay_seconds': delay,
                            'session_name': session_name,
                            'current_recipient': i + 1,
                            'total_recipients': len(recipients)
                        }
                    )
                    await asyncio.sleep(delay)
        
        finally:
            # Always decrement counters (Requirement 4.3, 11.2)
            await self.decrement_session_load(session_name)
            await self.decrement_operation_metric('sending')
        
        return results
    
    async def send_from_csv(
        self,
        csv_path: str,
        message: str,
        batch_size: int = 1000,
        delay: float = 2.0,
        resumable: bool = True,
        operation_id: Optional[str] = None,
        priority: str = "normal"
    ) -> 'BulkSendResult':
        """
        Send messages to recipients from a CSV file with batch processing and progress tracking
        
        Implements:
        - CSV parsing with automatic streaming for large files (Requirement 12.1, 20.1, 20.2)
        - Batch processing with configurable batch size (Requirement 24.1, 24.2)
        - Progress tracking and resumable operations (Requirement 25.1, 25.2, 25.3, 25.4, 25.5)
        - Progress updates after each batch (Requirement 20.5, 24.3)
        - Graceful error handling for CSV parsing errors (Requirement 12.3, 12.5, 20.4, 24.4)
        
        Args:
            csv_path: Path to CSV file containing recipient identifiers
            message: Text message to send
            batch_size: Number of recipients to process per batch (default 1000)
            delay: Delay between sends within each session (seconds)
            resumable: Whether to enable checkpoint-based resumption (default True)
            operation_id: Optional operation ID for resuming (auto-generated if not provided)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            BulkSendResult with complete operation results
            
        Requirements: 12.1, 12.4, 12.5, 20.2, 20.5, 24.1, 24.3, 24.4, 21.1, 21.2
        """
        from .models import BulkSendResult, MessageResult, CSVProcessor, ProgressTracker
        import time
        import uuid
        
        start_time = time.time()
        
        # Generate operation ID if not provided
        if operation_id is None:
            operation_id = f"csv_send_{uuid.uuid4().hex[:8]}"
        
        # Initialize progress tracker if resumable
        progress_tracker = None
        completed_recipients = set()
        
        if resumable:
            progress_tracker = ProgressTracker()
            
            # Try to load existing checkpoint (Requirement 25.4)
            try:
                completed_recipients = await progress_tracker.load_checkpoint(operation_id)
                self.logger.info(
                    f"📂 Resuming operation {operation_id}: "
                    f"{len(completed_recipients)} recipients already completed"
                )
            except FileNotFoundError:
                # No existing checkpoint, create new one (Requirement 25.1)
                # We'll create it after we know the total count
                pass
        
        # Parse CSV file (Requirement 12.1)
        self.logger.info(f"📄 Parsing CSV file: {csv_path}")
        
        try:
            csv_processor = CSVProcessor()
            
            # Check if we should use streaming (Requirement 20.1)
            use_streaming = csv_processor.should_use_streaming(csv_path)
            if use_streaming:
                self.logger.info(f"📊 Large file detected, using streaming parser")
            
            # Collect all recipients and process in batches
            all_results = {}
            total_recipients = 0
            processed_recipients = 0
            batch_number = 0
            
            # Parse CSV in batches (Requirement 20.2, 24.1)
            async for batch in csv_processor.parse_csv(csv_path, batch_size):
                batch_number += 1
                
                # Filter out already completed recipients if resuming (Requirement 25.4)
                if resumable and completed_recipients:
                    original_batch_size = len(batch)
                    batch = [r for r in batch if r not in completed_recipients]
                    skipped = original_batch_size - len(batch)
                    if skipped > 0:
                        self.logger.info(
                            f"⏭️  Skipping {skipped} already completed recipients in batch {batch_number}"
                        )
                
                if not batch:
                    # All recipients in this batch were already completed
                    continue
                
                # Create checkpoint on first batch if resumable (Requirement 25.1)
                if resumable and progress_tracker and batch_number == 1:
                    # We need to count total recipients first
                    # For now, we'll update the checkpoint as we go
                    pass
                
                total_recipients += len(batch)
                
                # Log batch processing start with structured logging (Requirement 20.5, 24.3, 13.1)
                self.logger.info(
                    f"📦 Processing batch {batch_number}: {len(batch)} recipients "
                    f"(total processed: {processed_recipients})",
                    extra={
                        'operation_type': 'csv_batch_send',
                        'operation_id': operation_id,
                        'batch_number': batch_number,
                        'batch_size': len(batch),
                        'total_processed': processed_recipients,
                        'resumable': resumable
                    }
                )
                
                try:
                    # Send messages to batch (Requirement 12.4)
                    batch_results = await self.send_text_messages_bulk(
                        recipients=batch,
                        message=message,
                        delay=delay,
                        skip_invalid=True  # Skip invalid recipients (Requirement 12.5)
                    )
                    
                    # Aggregate results
                    all_results.update(batch_results)
                    
                    # Update progress tracking (Requirement 25.2)
                    if resumable and progress_tracker:
                        # Collect successfully completed recipients
                        batch_completed = [
                            r for r, result in batch_results.items()
                            if result.success
                        ]
                        batch_failed = [
                            r for r, result in batch_results.items()
                            if not result.success
                        ]
                        
                        # Create checkpoint if this is the first batch
                        if batch_number == 1:
                            # Estimate total based on first batch
                            # We'll update this as we process more batches
                            await progress_tracker.create_checkpoint(
                                operation_id=operation_id,
                                total_items=len(batch)  # Will be updated
                            )
                        
                        # Update checkpoint with completed recipients
                        await progress_tracker.update_checkpoint(
                            operation_id=operation_id,
                            completed=batch_completed,
                            failed=batch_failed
                        )
                    
                    processed_recipients += len(batch)
                    
                    # Log batch completion with progress and structured logging (Requirement 20.5, 24.3, 13.5)
                    succeeded = sum(1 for r in batch_results.values() if r.success)
                    failed = len(batch_results) - succeeded
                    self.logger.info(
                        f"✅ Batch {batch_number} complete: "
                        f"{succeeded} succeeded, {failed} failed "
                        f"(total processed: {processed_recipients})",
                        extra={
                            'operation_type': 'csv_batch_send',
                            'operation_id': operation_id,
                            'batch_number': batch_number,
                            'batch_succeeded': succeeded,
                            'batch_failed': failed,
                            'batch_success_rate': (succeeded / len(batch_results) * 100) if batch_results else 0,
                            'total_processed': processed_recipients
                        }
                    )
                    
                    # Get progress if available
                    if resumable and progress_tracker:
                        progress = progress_tracker.get_progress(operation_id)
                        if progress:
                            self.logger.info(
                                f"📊 Progress: {progress.percentage_complete():.1f}% complete, "
                                f"estimated time remaining: {progress.estimated_time_remaining():.1f}s"
                            )
                    
                except Exception as e:
                    # Batch failure - log and continue with next batch (Requirement 24.4)
                    self.logger.error(
                        f"❌ Batch {batch_number} failed: {e}. Continuing with next batch..."
                    )
                    
                    # Mark all recipients in failed batch as failed
                    for recipient in batch:
                        all_results[recipient] = MessageResult(
                            recipient=recipient,
                            success=False,
                            session_used='',
                            error=f'Batch processing error: {str(e)}'
                        )
                    
                    # Continue with next batch (Requirement 24.4)
                    continue
                
                # Release memory between batches (Requirement 20.3, 24.2)
                # Python's garbage collector will handle this, but we can help by clearing references
                batch = None
                batch_results = None
            
            # Calculate final statistics
            duration = time.time() - start_time
            succeeded = sum(1 for r in all_results.values() if r.success)
            failed = len(all_results) - succeeded
            
            # Remove checkpoint on successful completion (Requirement 25.5)
            if resumable and progress_tracker:
                await progress_tracker.remove_checkpoint(operation_id)
                self.logger.info(f"🗑️  Removed checkpoint for completed operation {operation_id}")
            
            # Log final summary with structured logging (Requirement 13.5)
            self.logger.info(
                f"✅ CSV send operation complete: "
                f"{succeeded} succeeded, {failed} failed out of {len(all_results)} total "
                f"(duration: {duration:.1f}s, batches: {batch_number})",
                extra={
                    'operation_type': 'csv_send_complete',
                    'operation_id': operation_id,
                    'total_messages': len(all_results),
                    'succeeded': succeeded,
                    'failed': failed,
                    'success_rate': (succeeded / len(all_results) * 100) if all_results else 0,
                    'duration_seconds': duration,
                    'batch_count': batch_number,
                    'csv_path': csv_path
                }
            )
            
            # Return bulk send result
            return BulkSendResult(
                total=len(all_results),
                succeeded=succeeded,
                failed=failed,
                results=all_results,
                duration=duration,
                operation_id=operation_id
            )
            
        except FileNotFoundError as e:
            # CSV file not found (Requirement 12.2)
            self.logger.error(f"❌ CSV file not found: {csv_path}")
            raise ValueError(f"CSV file does not exist: {csv_path}") from e
            
        except ValueError as e:
            # CSV format invalid (Requirement 12.3)
            self.logger.error(f"❌ Invalid CSV format: {e}")
            raise ValueError(f"Failed to parse CSV file: {str(e)}") from e
            
        except Exception as e:
            # Unexpected error
            self.logger.error(f"❌ Unexpected error during CSV send operation: {e}")
            raise

    async def preview_send(
        self,
        recipients: List[str],
        message: Optional[str] = None,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        delay: float = 2.0
    ) -> 'SendPreview':
        """
        Preview a message sending operation without actually sending
        
        Validates all inputs and calculates session distribution and estimated duration
        without sending any messages.
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            message: Text message (for text sends)
            media_path: Path to media file (for media sends)
            media_type: Type of media ('image', 'video', 'document')
            delay: Delay between sends within each session (seconds)
            
        Returns:
            SendPreview with validation results, distribution plan, and time estimate
            
        Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
        """
        from .models import SendPreview, RecipientValidator, MediaHandler, ValidationResult, ValidationError
        
        # Validate recipients (Requirement 15.2, 15.5)
        validation_result = RecipientValidator.validate_recipients(recipients)
        
        # If media send, validate media file (Requirement 15.5)
        if media_path and media_type:
            format_validation = MediaHandler.validate_format(media_path, media_type)
            if not format_validation.valid:
                # Merge validation errors
                validation_result.valid = False
                validation_result.errors.extend(format_validation.errors)
            
            size_validation = MediaHandler.validate_size(media_path, media_type)
            if not size_validation.valid:
                # Merge validation errors
                validation_result.valid = False
                validation_result.errors.extend(size_validation.errors)
        
        # Calculate session distribution plan (Requirement 15.3)
        session_distribution = {}
        
        if not self.sessions:
            # No sessions available
            validation_result.valid = False
            validation_result.errors.append(
                ValidationError(
                    field='sessions',
                    value=None,
                    rule='availability',
                    message='No sessions available'
                )
            )
        else:
            # Get list of connected sessions
            connected_sessions = [name for name, session in self.sessions.items() if session.is_connected]
            
            if not connected_sessions:
                # No connected sessions
                validation_result.valid = False
                validation_result.errors.append(
                    ValidationError(
                        field='sessions',
                        value=None,
                        rule='connectivity',
                        message='No connected sessions available'
                    )
                )
            else:
                # Simulate distribution across sessions (same logic as actual send)
                # Each recipient is assigned to exactly ONE session
                # We need to simulate the load balancing without actually modifying session loads
                
                # Create a copy of session loads for simulation
                simulated_loads = {name: self.session_load.get(name, 0) for name in connected_sessions}
                
                recipient_assignments = {}
                for i, recipient in enumerate(recipients):
                    # Simulate load balancer selection
                    if self.load_balancer.strategy == "least_loaded":
                        # Select session with minimum simulated load
                        session_name = min(connected_sessions, key=lambda s: simulated_loads[s])
                    else:
                        # Round-robin: cycle through connected sessions
                        session_name = connected_sessions[i % len(connected_sessions)]
                    
                    recipient_assignments[recipient] = session_name
                    
                    # Increment simulated load for this session
                    simulated_loads[session_name] += 1
                
                # Count recipients per session
                for recipient, session_name in recipient_assignments.items():
                    if session_name not in session_distribution:
                        session_distribution[session_name] = 0
                    session_distribution[session_name] += 1
        
        # Calculate estimated duration (Requirement 15.4)
        # Duration = (recipients_per_session - 1) * delay for each session
        # We take the maximum duration across all sessions since they run concurrently
        estimated_duration = 0.0
        if session_distribution:
            max_recipients_per_session = max(session_distribution.values())
            # Time = (N - 1) * delay, where N is recipients per session
            # The -1 is because there's no delay after the last message
            estimated_duration = max(0, (max_recipients_per_session - 1) * delay)
        
        # Return preview (Requirement 15.1 - no messages sent)
        return SendPreview(
            recipients=recipients,
            recipient_count=len(recipients),
            session_distribution=session_distribution,
            estimated_duration=estimated_duration,
            validation_result=validation_result
        )

    async def bulk_send_messages(self, targets: List[str], message: str, delay: float = 2.0) -> Dict:
        """
        Send messages using all sessions (load balancing) - DEPRECATED
        
        Use send_text_messages_bulk instead for better functionality.
        
        Args:
            targets: List of target identifiers
            message: Message to send
            delay: Delay between sends in seconds
            
        Returns:
            Dict with send results for each target
        """
        self.logger.warning("⚠️ bulk_send_messages is deprecated, use send_text_messages_bulk instead")
        
        # Convert to new format
        results = await self.send_text_messages_bulk(targets, message, delay)
        
        # Convert MessageResult objects to old dict format for backward compatibility
        old_format_results = {}
        for recipient, result in results.items():
            old_format_results[recipient] = {
                'session': result.session_used,
                'success': result.success,
                'error': result.error
            }
        
        return old_format_results

    async def bulk_get_members(self, chats: List[str], limit: int = 100) -> Dict[str, List]:
        """
        Get members from multiple chats using all sessions
        
        Args:
            chats: List of chat identifiers
            limit: Maximum members to fetch per chat
            
        Returns:
            Dict mapping chat identifiers to member lists
        """
        all_members = {}
        
        if not self.sessions:
            return all_members
        
        # Distribute chats among sessions
        sessions_list = list(self.sessions.values())
        chats_per_session = max(1, len(chats) // len(sessions_list))
        
        tasks = []
        for i, session in enumerate(sessions_list):
            start_idx = i * chats_per_session
            end_idx = start_idx + chats_per_session if i < len(sessions_list) - 1 else len(chats)
            session_chats = chats[start_idx:end_idx]
            
            for chat in session_chats:
                task = asyncio.create_task(session.get_members(chat, limit))
                tasks.append((chat, task))
        
        # Collect results
        for chat, task in tasks:
            try:
                members = await task
                all_members[chat] = members
            except Exception as e:
                self.logger.error(f"❌ Failed to get members from {chat}: {e}")
                all_members[chat] = []
        
        return all_members

    async def join_chats(self, chats: List[str]) -> Dict[str, bool]:
        """
        Join multiple chats using all sessions
        
        Args:
            chats: List of chat identifiers to join
            
        Returns:
            Dict mapping chat identifiers to join success status
        """
        results = {}
        
        if not self.sessions:
            return results
        
        # Distribute chats among sessions
        sessions_list = list(self.sessions.values())
        chats_per_session = max(1, len(chats) // len(sessions_list))
        
        tasks = []
        for i, session in enumerate(sessions_list):
            start_idx = i * chats_per_session
            end_idx = start_idx + chats_per_session if i < len(sessions_list) - 1 else len(chats)
            session_chats = chats[start_idx:end_idx]
            
            for chat in session_chats:
                task = asyncio.create_task(session.join_chat(chat))
                tasks.append((chat, task))
        
        # Collect results
        for chat, task in tasks:
            try:
                success = await task
                results[chat] = success
            except Exception as e:
                self.logger.error(f"❌ Failed to join {chat}: {e}")
                results[chat] = False
        
        return results

    async def get_session_stats(self) -> Dict:
        """
        Get statistics for all sessions
        
        Returns:
            Dict with session statistics
        """
        stats = {}
        
        for name, session in self.sessions.items():
            stats[name] = session.get_status()
        
        return stats
    
    async def join_channel_all_sessions(self, channel_id: str) -> Dict[str, bool]:
        """
        Attempt to join channel with all active sessions
        
        Each session attempts to join the channel independently. Failures in one
        session do not affect other sessions (Requirement 2.3).
        
        Args:
            channel_id: Channel username (@channel), ID, or invite link
            
        Returns:
            Dict mapping session_name to join success status (True/False)
            
        Requirements: 2.1, 2.2, 2.3
        """
        results = {}
        
        if not self.sessions:
            self.logger.warning("⚠️ No sessions available for joining channel")
            return results
        
        # Create join tasks for all sessions
        join_tasks = []
        for session_name, session in self.sessions.items():
            if session.is_connected:
                task = asyncio.create_task(
                    self._join_channel_single_session(session_name, session, channel_id)
                )
                join_tasks.append((session_name, task))
            else:
                self.logger.warning(f"⚠️ Session {session_name} is not connected, skipping join")
                results[session_name] = False
        
        # Wait for all join attempts to complete
        for session_name, task in join_tasks:
            try:
                success = await task
                results[session_name] = success
            except Exception as e:
                # Log failure but continue with other sessions (Requirement 2.3)
                self.logger.error(f"❌ Exception during join for session {session_name}: {e}")
                results[session_name] = False
        
        # Log summary
        succeeded = sum(1 for success in results.values() if success)
        failed = len(results) - succeeded
        self.logger.info(
            f"📊 Channel join complete: {succeeded} succeeded, {failed} failed out of {len(results)} sessions"
        )
        
        return results
    
    async def _join_channel_single_session(
        self, 
        session_name: str, 
        session: TelegramSession, 
        channel_id: str
    ) -> bool:
        """
        Helper method to join channel with a single session
        
        Args:
            session_name: Name of the session
            session: TelegramSession instance
            channel_id: Channel identifier
            
        Returns:
            True if join succeeded, False otherwise
        """
        try:
            # Use retry logic for joining (Requirement 5.5)
            success, error = await session.join_channel_with_retry(channel_id)
            
            if success:
                # Log successful join (Requirement 2.2)
                self.logger.info(
                    f"✅ Session {session_name} successfully joined channel {channel_id}",
                    extra={
                        'operation_type': 'channel_join',
                        'session_name': session_name,
                        'channel_id': channel_id,
                        'success': True
                    }
                )
                return True
            else:
                # Log failure (Requirement 2.3)
                self.logger.warning(
                    f"❌ Session {session_name} failed to join channel {channel_id}: {error}",
                    extra={
                        'operation_type': 'channel_join',
                        'session_name': session_name,
                        'channel_id': channel_id,
                        'success': False,
                        'error': error
                    }
                )
                return False
                
        except Exception as e:
            # Log exception (Requirement 2.3)
            self.logger.error(
                f"❌ Exception during join for session {session_name}: {e}",
                extra={
                    'operation_type': 'channel_join',
                    'session_name': session_name,
                    'channel_id': channel_id,
                    'success': False,
                    'error': str(e)
                }
            )
            return False
    
    async def verify_channel_membership(self, channel_id: str) -> Dict[str, bool]:
        """
        Verify which sessions are members of a channel
        
        Checks membership status for all active sessions without attempting to join.
        
        Args:
            channel_id: Channel username (@channel), ID, or invite link
            
        Returns:
            Dict mapping session_name to membership status (True if member, False otherwise)
            
        Requirements: 2.4
        """
        results = {}
        
        if not self.sessions:
            self.logger.warning("⚠️ No sessions available for membership verification")
            return results
        
        # Create verification tasks for all sessions
        verify_tasks = []
        for session_name, session in self.sessions.items():
            if session.is_connected:
                task = asyncio.create_task(
                    self._verify_membership_single_session(session_name, session, channel_id)
                )
                verify_tasks.append((session_name, task))
            else:
                self.logger.debug(f"Session {session_name} is not connected, marking as non-member")
                results[session_name] = False
        
        # Wait for all verification tasks to complete
        for session_name, task in verify_tasks:
            try:
                is_member = await task
                results[session_name] = is_member
            except Exception as e:
                self.logger.error(f"❌ Exception during membership verification for session {session_name}: {e}")
                results[session_name] = False
        
        # Log summary
        members = sum(1 for is_member in results.values() if is_member)
        non_members = len(results) - members
        self.logger.info(
            f"📊 Membership verification complete: {members} members, {non_members} non-members out of {len(results)} sessions"
        )
        
        return results
    
    async def _verify_membership_single_session(
        self,
        session_name: str,
        session: TelegramSession,
        channel_id: str
    ) -> bool:
        """
        Helper method to verify membership for a single session
        
        Args:
            session_name: Name of the session
            session: TelegramSession instance
            channel_id: Channel identifier
            
        Returns:
            True if session is a member, False otherwise
        """
        try:
            is_member = await session.is_channel_member(channel_id)
            self.logger.debug(
                f"Session {session_name} membership for {channel_id}: {is_member}"
            )
            return is_member
        except Exception as e:
            self.logger.error(
                f"❌ Exception during membership check for session {session_name}: {e}"
            )
            return False
    
    async def get_channel_join_status(self, channel_id: str) -> Dict[str, Dict]:
        """
        Get detailed join status for a channel across all sessions
        
        Returns comprehensive status information including membership status
        and any errors encountered during verification.
        
        Args:
            channel_id: Channel username (@channel), ID, or invite link
            
        Returns:
            Dict mapping session_name to status dict with keys:
                - 'joined': bool (True if member, False otherwise)
                - 'error': Optional[str] (error message if verification failed)
                
        Requirements: 4.1
        """
        results = {}
        
        if not self.sessions:
            self.logger.warning("⚠️ No sessions available for join status check")
            return results
        
        # Create status check tasks for all sessions
        status_tasks = []
        for session_name, session in self.sessions.items():
            if session.is_connected:
                task = asyncio.create_task(
                    self._get_join_status_single_session(session_name, session, channel_id)
                )
                status_tasks.append((session_name, task))
            else:
                results[session_name] = {
                    'joined': False,
                    'error': 'Session not connected'
                }
        
        # Wait for all status checks to complete
        for session_name, task in status_tasks:
            try:
                status = await task
                results[session_name] = status
            except Exception as e:
                self.logger.error(f"❌ Exception during status check for session {session_name}: {e}")
                results[session_name] = {
                    'joined': False,
                    'error': f'Exception: {str(e)}'
                }
        
        # Log summary
        joined_count = sum(1 for status in results.values() if status['joined'])
        self.logger.info(
            f"📊 Join status check complete: {joined_count}/{len(results)} sessions are members of {channel_id}"
        )
        
        return results
    
    async def _get_join_status_single_session(
        self,
        session_name: str,
        session: TelegramSession,
        channel_id: str
    ) -> Dict:
        """
        Helper method to get join status for a single session
        
        Args:
            session_name: Name of the session
            session: TelegramSession instance
            channel_id: Channel identifier
            
        Returns:
            Dict with 'joined' (bool) and 'error' (Optional[str]) keys
        """
        try:
            is_member = await session.is_channel_member(channel_id)
            return {
                'joined': is_member,
                'error': None
            }
        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"❌ Error checking join status for session {session_name}: {error_msg}"
            )
            return {
                'joined': False,
                'error': error_msg
            }
    
    def get_monitoring_statistics(self, channel_id: Optional[str] = None) -> Dict:
        """
        Get aggregated monitoring statistics across all sessions
        
        Args:
            channel_id: Optional channel ID to get stats for. If None, returns stats for all channels.
            
        Returns:
            Dict with aggregated monitoring statistics (Requirement 4.3)
        """
        if channel_id:
            # Get stats for specific channel across all sessions
            total_reactions_sent = 0
            total_messages_processed = 0
            total_reaction_failures = 0
            active_sessions = 0
            
            for session_name, session in self.sessions.items():
                if session.is_connected:
                    stats = session.get_monitoring_statistics(channel_id)
                    if stats.get('monitoring_active', False):
                        active_sessions += 1
                        total_reactions_sent += stats.get('reactions_sent', 0)
                        total_messages_processed += stats.get('messages_processed', 0)
                        total_reaction_failures += stats.get('reaction_failures', 0)
            
            return {
                'channel_id': channel_id,
                'active_sessions': active_sessions,
                'total_reactions_sent': total_reactions_sent,
                'total_messages_processed': total_messages_processed,
                'total_reaction_failures': total_reaction_failures
            }
        else:
            # Get stats for all channels across all sessions
            channel_stats = {}
            
            for session_name, session in self.sessions.items():
                if session.is_connected:
                    session_stats = session.get_monitoring_statistics()
                    
                    for ch_id, stats in session_stats.items():
                        if ch_id not in channel_stats:
                            channel_stats[ch_id] = {
                                'active_sessions': 0,
                                'total_reactions_sent': 0,
                                'total_messages_processed': 0,
                                'total_reaction_failures': 0
                            }
                        
                        channel_stats[ch_id]['active_sessions'] += 1
                        channel_stats[ch_id]['total_reactions_sent'] += stats.get('reactions_sent', 0)
                        channel_stats[ch_id]['total_messages_processed'] += stats.get('messages_processed', 0)
                        channel_stats[ch_id]['total_reaction_failures'] += stats.get('reaction_failures', 0)
            
            return channel_stats
    
    def get_active_scrape_count(self) -> int:
        """
        Get the current number of active scraping operations (Task 6.1)
        
        Returns:
            Number of active scrape operations
        """
        return self.active_scrape_count
    
    async def register_task_globally(self, session_name: str, task: asyncio.Task):
        """
        Register a task in the global task registry (Task 6.2)
        
        Args:
            session_name: Name of the session that owns the task
            task: The asyncio task to register
        """
        async with self.global_task_lock:
            if session_name not in self.global_tasks:
                self.global_tasks[session_name] = set()
            self.global_tasks[session_name].add(task)
            self.logger.debug(f"Registered task for session {session_name}, total: {len(self.global_tasks[session_name])}")
    
    async def unregister_task_globally(self, session_name: str, task: asyncio.Task):
        """
        Unregister a task from the global task registry (Task 6.2)
        
        Args:
            session_name: Name of the session that owns the task
            task: The asyncio task to unregister
        """
        async with self.global_task_lock:
            if session_name in self.global_tasks:
                self.global_tasks[session_name].discard(task)
                if not self.global_tasks[session_name]:
                    del self.global_tasks[session_name]
                self.logger.debug(f"Unregistered task for session {session_name}")
    
    async def get_global_task_count(self, session_name: Optional[str] = None) -> int:
        """
        Get the count of active tasks globally or for a specific session (Task 6.2)
        
        Args:
            session_name: Optional session name to filter by
            
        Returns:
            Number of active tasks
        """
        async with self.global_task_lock:
            if session_name:
                return len(self.global_tasks.get(session_name, set()))
            else:
                return sum(len(tasks) for tasks in self.global_tasks.values())
    
    async def cleanup_session_tasks(self, session_name: str):
        """
        Clean up all tasks for a specific session (Task 6.2)
        
        Args:
            session_name: Name of the session to clean up
        """
        async with self.global_task_lock:
            if session_name in self.global_tasks:
                tasks = list(self.global_tasks[session_name])
                self.logger.info(f"Cleaning up {len(tasks)} tasks for session {session_name}")
                
                # Cancel all tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait for cancellation with timeout
                if tasks:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*tasks, return_exceptions=True),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"Some tasks for session {session_name} did not cancel within 5 seconds")
                
                # Remove from registry
                del self.global_tasks[session_name]
                self.logger.info(f"Cleaned up tasks for session {session_name}")
    
    async def increment_operation_metric(self, operation_type: str):
        """
        Increment the count for a specific operation type (Task 6.3)
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending', 'other')
        """
        async with self.metrics_lock:
            if operation_type in self.operation_metrics:
                self.operation_metrics[operation_type] += 1
            else:
                self.operation_metrics['other'] += 1
    
    async def decrement_operation_metric(self, operation_type: str):
        """
        Decrement the count for a specific operation type (Task 6.3)
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending', 'other')
        """
        async with self.metrics_lock:
            if operation_type in self.operation_metrics:
                self.operation_metrics[operation_type] = max(0, self.operation_metrics[operation_type] - 1)
            else:
                self.operation_metrics['other'] = max(0, self.operation_metrics['other'] - 1)
    
    async def get_operation_metrics(self) -> Dict[str, int]:
        """
        Get current operation metrics (Task 6.3)
        
        Returns:
            Dict mapping operation types to active counts
        """
        async with self.metrics_lock:
            return self.operation_metrics.copy()
    
    def _parse_priority(self, priority_str: str) -> 'OperationPriority':
        """
        Parse priority string to OperationPriority enum
        
        Args:
            priority_str: Priority string ('high', 'normal', or 'low')
            
        Returns:
            OperationPriority enum value
            
        Requirements: 21.1, 21.2
        """
        from .models import OperationPriority
        
        priority_map = {
            'high': OperationPriority.HIGH,
            'normal': OperationPriority.NORMAL,
            'low': OperationPriority.LOW
        }
        
        priority_lower = priority_str.lower()
        if priority_lower not in priority_map:
            self.logger.warning(
                f"⚠️ Invalid priority '{priority_str}', defaulting to 'normal'"
            )
            return OperationPriority.NORMAL
        
        return priority_map[priority_lower]
    
    async def _queue_operation_if_busy(
        self,
        operation_func: Callable,
        priority_str: str,
        *args,
        **kwargs
    ) -> bool:
        """
        Queue operation if all sessions are busy
        
        Args:
            operation_func: Function to execute
            priority_str: Priority string ('high', 'normal', or 'low')
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func
            
        Returns:
            True if operation was queued, False if it can be executed immediately
            
        Requirements: 21.1, 21.3, 21.5
        """
        from .models import QueuedOperation, OperationPriority
        import uuid
        
        # Check if any sessions are available
        available_sessions = self.health_monitor.get_available_sessions()
        connected_available = [
            name for name in available_sessions
            if name in self.sessions and self.sessions[name].is_connected
        ]
        
        # If sessions are available, don't queue
        if connected_available:
            return False
        
        # All sessions busy, queue the operation (Requirement 21.1)
        priority = self._parse_priority(priority_str)
        operation_id = f"op_{uuid.uuid4().hex[:8]}"
        
        queued_op = QueuedOperation(
            operation_id=operation_id,
            priority=priority,
            operation_func=operation_func,
            args=args,
            kwargs=kwargs
        )
        
        async with self.queue_lock:
            self.operation_queue.enqueue(queued_op)
            queue_size = self.operation_queue.size()
        
        self.logger.info(
            f"📥 Queued operation {operation_id} with priority {priority_str} "
            f"(queue size: {queue_size})"
        )
        
        return True
    
    async def _process_priority_queue(self):
        """
        Process operations from priority queue when sessions become available
        
        High-priority operations are processed before normal-priority,
        and normal before low-priority. Within same priority, FIFO order is maintained.
        
        Requirements: 21.3, 21.4, 21.5
        """
        async with self.queue_lock:
            if self.operation_queue.is_empty():
                return
            
            # Get available sessions
            available_sessions = self.health_monitor.get_available_sessions()
            connected_available = [
                name for name in available_sessions
                if name in self.sessions and self.sessions[name].is_connected
            ]
            
            if not connected_available:
                # No sessions available yet
                return
            
            processed_count = 0
            
            # Process operations in priority order (Requirement 21.3, 21.5)
            while not self.operation_queue.is_empty():
                # Check if sessions are still available
                available_sessions = self.health_monitor.get_available_sessions()
                connected_available = [
                    name for name in available_sessions
                    if name in self.sessions and self.sessions[name].is_connected
                ]
                
                if not connected_available:
                    break
                
                # Dequeue highest priority operation (Requirement 21.3)
                op = self.operation_queue.dequeue()
                if not op:
                    break
                
                # Execute the operation
                self.logger.info(
                    f"🔄 Processing queued operation {op.operation_id} "
                    f"with priority {op.priority.name}"
                )
                
                try:
                    # Execute operation asynchronously
                    asyncio.create_task(
                        op.operation_func(*op.args, **op.kwargs)
                    )
                    processed_count += 1
                except Exception as e:
                    self.logger.error(
                        f"❌ Failed to execute queued operation {op.operation_id}: {e}"
                    )
            
            if processed_count > 0:
                self.logger.info(
                    f"✅ Processed {processed_count} queued operations "
                    f"(remaining: {self.operation_queue.size()})"
                )
    
    async def get_operation_metrics(self) -> Dict[str, int]:
        """
        Get current operation metrics (Task 6.3)
        
        Returns:
            Dict mapping operation types to active counts
        """
        async with self.metrics_lock:
            return self.operation_metrics.copy()
    
    async def get_operation_count(self, operation_type: str) -> int:
        """
        Get the count of active operations for a specific type (Task 6.3)
        
        Args:
            operation_type: Type of operation to query
            
        Returns:
            Number of active operations of that type
        """
        async with self.metrics_lock:
            return self.operation_metrics.get(operation_type, 0)
    
    async def increment_session_load(self, session_name: str):
        """
        Increment the active operation count for a session (Task 7.1)
        
        Args:
            session_name: Name of the session
        """
        async with self.metrics_lock:
            if session_name not in self.session_load:
                self.session_load[session_name] = 0
            self.session_load[session_name] += 1
            self.logger.debug(f"📈 Session {session_name} load: {self.session_load[session_name]}")
    
    async def decrement_session_load(self, session_name: str):
        """
        Decrement the active operation count for a session (Task 7.1)
        
        Args:
            session_name: Name of the session
        """
        async with self.metrics_lock:
            if session_name in self.session_load:
                self.session_load[session_name] = max(0, self.session_load[session_name] - 1)
                self.logger.debug(f"📉 Session {session_name} load: {self.session_load[session_name]}")
    
    async def get_session_load(self, session_name: str) -> int:
        """
        Get the current load for a specific session (Task 7.1)
        
        Args:
            session_name: Name of the session
            
        Returns:
            Number of active operations on that session
        """
        async with self.metrics_lock:
            return self.session_load.get(session_name, 0)
    
    def set_load_balancing_strategy(self, strategy: str):
        """
        Change the load balancing strategy at runtime (Task 10)
        
        Args:
            strategy: New strategy ('round_robin' or 'least_loaded')
        """
        self.load_balancer.set_strategy(strategy)
    
    def get_load_balancing_strategy(self) -> str:
        """
        Get the current load balancing strategy (Task 10)
        
        Returns:
            Current strategy name
        """
        return self.load_balancer.get_strategy()
    
    def _get_available_session(self) -> Optional[str]:
        """
        Get an available session using configured strategy (Task 7.4, Task 10, Task 14)
        
        Excludes failed sessions from selection (Requirement 23.2)
        
        Returns:
            Session name or None if no sessions available
        """
        # Get available (non-failed) sessions
        # If health monitor has sessions registered, use its filtering
        # Otherwise, use all sessions (for backward compatibility with tests)
        if self.health_monitor.sessions:
            available_session_names = self.health_monitor.get_available_sessions()
        else:
            # Health monitor not initialized, use all sessions
            available_session_names = list(self.sessions.keys())
        
        # Filter to only include sessions that exist and are connected
        available_sessions = {
            name: session for name, session in self.sessions.items()
            if name in available_session_names and session.is_connected
        }
        
        if not available_sessions:
            return None
        
        # Use load balancer to select from available sessions
        return self.load_balancer.select_session(available_sessions, self.session_load)
    
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried
        
        Classifies errors into two categories:
        - Transient: Network issues, timeouts, rate limiting - should retry (Requirement 5.1)
        - Permanent: Auth failures, not found, permissions - should not retry (Requirement 5.2)
        
        Args:
            error: The exception to check
            
        Returns:
            True if error is transient (should retry), False if permanent (should not retry)
            
        Requirements: 5.1, 5.2
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Transient errors (network, timeout, rate limiting)
        transient_indicators = [
            'timeout',
            'network',
            'connection',
            'flood',
            'slowmode',
            'too many requests',
            'temporarily',
            'try again',
            'rate limit',
            'service unavailable',
            'internal server error',
        ]
        
        # Permanent errors (auth, not found, permissions)
        permanent_indicators = [
            'auth',
            'unauthorized',
            'forbidden',
            'not found',
            'invalid',
            'banned',
            'restricted',
            'deleted',
            'privacy',
            'access denied',
            'no rights',
            'permission',
        ]
        
        # Check for permanent errors first
        for indicator in permanent_indicators:
            if indicator in error_str:
                self.logger.debug(f"Permanent error detected: {indicator}")
                return False
        
        # Check for transient errors
        for indicator in transient_indicators:
            if indicator in error_str:
                self.logger.debug(f"Transient error detected: {indicator}")
                return True
        
        # TimeoutError is always transient
        if 'TimeoutError' in error_type or 'asyncio.TimeoutError' in error_type:
            return True
        
        # Default: treat as transient to be safe
        self.logger.debug(f"Unknown error type, treating as transient: {error_type}")
        return True
    
    async def _handle_delivery_failure(
        self,
        recipient: str,
        error: Exception,
        session_name: str
    ) -> None:
        """
        Handle delivery failure by tracking failures and detecting blocks
        
        This method:
        1. Records the failure in the delivery tracker
        2. Classifies the error to determine if it's a block
        3. If it's the second consecutive failure with a block error, adds user to blacklist
        4. Logs blocking events with user ID, timestamp, and session name
        
        Args:
            recipient: User identifier that failed
            error: Exception that occurred during delivery
            session_name: Session that attempted the delivery
            
        Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.2, 4.4, 6.5
        """
        from .models import ErrorClassifier
        
        # Record failure and get current count (Requirement 4.1)
        failure_count = self.delivery_tracker.record_failure(recipient)
        
        # Classify the error (Requirement 1.5, 6.1, 6.2, 6.3, 6.4)
        error_classification = ErrorClassifier.classify_error(error)
        is_block_error = ErrorClassifier.is_block_error(error)
        
        # Log error classification (Requirement 6.5)
        self.logger.debug(
            f"🔍 Error classified for {recipient}: {error_classification}",
            extra={
                'operation_type': 'error_classification',
                'recipient': recipient,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'classification': error_classification,
                'is_block_error': is_block_error,
                'failure_count': failure_count,
                'session_name': session_name
            }
        )
        
        # Check if this is the second consecutive failure with a block error (Requirement 1.1, 4.4)
        if failure_count >= 2 and is_block_error:
            # Add user to blacklist (Requirement 1.2, 1.3)
            await self.blacklist_manager.add(
                user_id=recipient,
                reason="block_detected",
                session_name=session_name
            )
            
            # Log blocking event with user ID, timestamp, and session name (Requirement 1.4)
            self.logger.warning(
                f"🚫 User {recipient} added to blacklist after {failure_count} consecutive failures",
                extra={
                    'operation_type': 'block_detection',
                    'recipient': recipient,
                    'failure_count': failure_count,
                    'error_classification': error_classification,
                    'session_name': session_name,
                    'reason': 'block_detected',
                    'timestamp': time.time()
                }
            )
    
    async def _execute_with_retry(
        self,
        operation_type: str,
        operation_func: Callable,
        *args,
        **kwargs
    ):
        """
        Execute an operation with retry logic and exponential backoff
        
        Implements comprehensive retry logic with:
        - Transient vs permanent error classification (Requirement 5.2)
        - Exponential backoff between retries (Requirement 5.3)
        - Configurable retry counts per operation type (Requirement 5.1)
        - Detailed logging of retry attempts (Requirement 5.5)
        - Proper error propagation when retries exhausted (Requirement 5.4)
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending')
            operation_func: The operation function to execute
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func
            
        Returns:
            Result from the operation
            
        Raises:
            Exception: The final exception if all retries fail or if error is permanent
            
        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
        """
        import time
        max_retries = self.retry_config.get(operation_type, 0)
        attempt = 0
        last_error = None
        start_time = time.time()
        
        while attempt <= max_retries:
            try:
                if attempt > 0:
                    # Enhanced retry logging with attempt count (Requirement 5.5)
                    self.logger.info(
                        f"🔄 Retry attempt {attempt}/{max_retries} for {operation_type} "
                        f"(total elapsed: {time.time() - start_time:.1f}s)"
                    )
                
                # Execute the operation (Requirement 5.1)
                result = await operation_func(*args, **kwargs)
                
                if attempt > 0:
                    # Log successful retry with attempt count (Requirement 5.5)
                    self.logger.info(
                        f"✅ {operation_type} succeeded on retry {attempt} "
                        f"(total elapsed: {time.time() - start_time:.1f}s)"
                    )
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Check if we should retry (Requirement 5.4)
                if attempt >= max_retries:
                    # Maximum retries exhausted - mark as failed (Requirement 5.4)
                    # Enhanced error logging with full context (Requirement 5.5)
                    self.logger.error(
                        f"❌ {operation_type} failed after {max_retries} retries: {e} "
                        f"(total elapsed: {time.time() - start_time:.1f}s, "
                        f"error_type: {type(e).__name__})"
                    )
                    # Note: Metrics are decremented by caller in finally block
                    raise
                
                # Check if error is transient (Requirement 5.2)
                is_transient = self._is_transient_error(e)
                if not is_transient:
                    # Permanent error - don't retry (Requirement 5.2)
                    # Log permanent error with context (Requirement 5.5)
                    self.logger.warning(
                        f"⚠️ Permanent error detected for {operation_type}, not retrying: {e} "
                        f"(error_type: {type(e).__name__})"
                    )
                    # Note: Metrics are decremented by caller in finally block
                    raise
                
                # Calculate exponential backoff delay (Requirement 5.3)
                # Formula: backoff_delay = base^attempt (e.g., 2^0=1s, 2^1=2s, 2^2=4s, 2^3=8s)
                backoff_delay = self.retry_backoff_base ** attempt
                
                # Enhanced retry attempt logging (Requirement 5.5)
                self.logger.warning(
                    f"⚠️ {operation_type} failed (attempt {attempt + 1}/{max_retries + 1}): {e} "
                    f"(error_type: {type(e).__name__}, is_transient: {is_transient})"
                )
                self.logger.info(
                    f"⏳ Waiting {backoff_delay}s before retry "
                    f"(total elapsed: {time.time() - start_time:.1f}s)..."
                )
                
                # Wait before retrying
                await asyncio.sleep(backoff_delay)
                
                attempt += 1
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        else:
            raise Exception(f"{operation_type} failed with unknown error")

    async def _acquire_lock_with_timeout(self, lock: asyncio.Lock, timeout: float = 30.0, lock_name: str = "unknown") -> bool:
        """
        Acquire lock with timeout to prevent deadlocks
        
        Args:
            lock: Lock to acquire
            timeout: Timeout in seconds (default 30s)
            lock_name: Name of lock for logging
            
        Returns:
            True if lock acquired, False if timeout
            
        Note:
            Caller is responsible for releasing all held locks on timeout.
            This method only attempts to acquire the specified lock.
        """
        import time
        try:
            # Log acquisition attempt at DEBUG level with timestamp
            self.logger.debug(
                f"🔒 [{time.time():.3f}] Attempting to acquire {lock_name} lock "
                f"(timeout: {timeout}s, manager)"
            )
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            # Log successful acquisition at DEBUG level with timestamp
            self.logger.debug(
                f"✅ [{time.time():.3f}] Acquired {lock_name} lock (manager)"
            )
            return True
        except asyncio.TimeoutError:
            # Log timeout at WARNING level with lock state (Requirement 7.3)
            lock_state = {
                'lock_name': lock_name,
                'is_locked': lock.locked(),
                'active_scrape_count': self.active_scrape_count,
                'operation_metrics': self.operation_metrics.copy(),
                'session_count': len(self.sessions),
                'connected_sessions': sum(1 for s in self.sessions.values() if s.is_connected)
            }
            self.logger.warning(
                f"⏱️ [{time.time():.3f}] TIMEOUT acquiring {lock_name} lock after {timeout}s - "
                f"Possible deadlock or contention in manager. Lock state: {lock_state}"
            )
            return False
    
    def _release_lock_with_logging(self, lock: asyncio.Lock, lock_name: str = "unknown"):
        """
        Release lock with logging
        
        Args:
            lock: Lock to release
            lock_name: Name of lock for logging
        """
        import time
        if lock.locked():
            lock.release()
            # Log release at DEBUG level with timestamp
            self.logger.debug(
                f"🔓 [{time.time():.3f}] Released {lock_name} lock (manager)"
            )
        else:
            self.logger.warning(
                f"⚠️ [{time.time():.3f}] Attempted to release unlocked {lock_name} lock (manager)"
            )

    def get_session(self, name: str) -> Optional[TelegramSession]:
        """
        Get a session by name
        
        Args:
            name: Session name
            
        Returns:
            TelegramSession or None if not found
        """
        return self.sessions.get(name)
    
    async def _handle_session_failure(self, session_name: str):
        """
        Handle session failure by redistributing pending operations
        
        This is called when a session fails and cannot be reconnected.
        All pending operations for the failed session are redistributed
        to other available sessions.
        
        Args:
            session_name: Name of the failed session
            
        Requirements: 23.1, 23.2, 23.5
        """
        self.logger.warning(f"🔄 Handling failure for session {session_name}")
        
        # Get pending operations for this session
        async with self.pending_ops_lock:
            pending_ops = self.pending_operations.get(session_name, [])
            
            if not pending_ops:
                self.logger.info(f"No pending operations to redistribute for {session_name}")
                return
            
            self.logger.info(
                f"📦 Redistributing {len(pending_ops)} pending operations from failed session {session_name}"
            )
            
            # Get available sessions (excluding failed ones)
            available_sessions = self.health_monitor.get_available_sessions()
            connected_available = [
                name for name in available_sessions
                if name in self.sessions and self.sessions[name].is_connected
            ]
            
            if not connected_available:
                # No available sessions - queue operations (Requirement 23.4)
                self.logger.warning(
                    f"⚠️ No available sessions to redistribute operations. "
                    f"Queuing {len(pending_ops)} operations..."
                )
                
                async with self.queue_lock:
                    for op in pending_ops:
                        self.operation_queue.enqueue(op)
                
                # Clear pending operations for failed session
                self.pending_operations[session_name] = []
                
                self.logger.info(
                    f"✅ Queued {len(pending_ops)} operations "
                    f"(total queue size: {self.operation_queue.size()})"
                )
            else:
                # Redistribute to available sessions (Requirement 23.1)
                # Preserve operation order within priority levels (Requirement 23.5)
                redistributed_count = 0
                
                for op in pending_ops:
                    # Select a session for this operation
                    target_session = self._get_available_session()
                    
                    if target_session:
                        # Add to target session's pending operations
                        if target_session not in self.pending_operations:
                            self.pending_operations[target_session] = []
                        self.pending_operations[target_session].append(op)
                        redistributed_count += 1
                        
                        self.logger.debug(
                            f"Redistributed operation {op.operation_id} "
                            f"from {session_name} to {target_session}"
                        )
                    else:
                        # No session available, queue it
                        async with self.queue_lock:
                            self.operation_queue.enqueue(op)
                
                # Clear pending operations for failed session
                self.pending_operations[session_name] = []
                
                self.logger.info(
                    f"✅ Redistributed {redistributed_count} operations to available sessions"
                )
    
    async def _handle_session_recovery(self, session_name: str):
        """
        Handle session recovery by reintegrating it into the load balancer
        
        This is called when a failed session successfully reconnects.
        The session becomes available for new operations.
        
        Args:
            session_name: Name of the recovered session
            
        Requirements: 23.3, 21.1
        """
        self.logger.info(f"✅ Handling recovery for session {session_name}")
        
        # Session is automatically reintegrated into load balancer
        # because health_monitor.get_available_sessions() will now include it
        
        # Process queued operations if any (for session failure recovery)
        await self._process_queued_operations()
        
        # Process priority queue operations (for priority queue integration)
        await self._process_priority_queue()
        
        self.logger.info(f"✅ Session {session_name} reintegrated into load balancer")
    
    async def _process_queued_operations(self):
        """
        Process queued operations when sessions become available
        
        This is called when a session recovers or when checking if
        queued operations can be executed.
        
        Requirements: 23.4
        """
        async with self.queue_lock:
            if self.operation_queue.is_empty():
                return
            
            queue_size = self.operation_queue.size()
            self.logger.info(f"📦 Processing {queue_size} queued operations...")
            
            processed = 0
            failed_to_process = []
            
            while not self.operation_queue.is_empty():
                # Get available sessions
                available_sessions = self.health_monitor.get_available_sessions()
                connected_available = [
                    name for name in available_sessions
                    if name in self.sessions and self.sessions[name].is_connected
                ]
                
                if not connected_available:
                    # No sessions available, stop processing
                    self.logger.warning(
                        f"⚠️ No available sessions to process queued operations. "
                        f"Remaining: {self.operation_queue.size()}"
                    )
                    break
                
                # Dequeue operation
                op = self.operation_queue.dequeue()
                if not op:
                    break
                
                # Select a session for this operation
                target_session = self._get_available_session()
                
                if target_session:
                    # Add to target session's pending operations
                    async with self.pending_ops_lock:
                        if target_session not in self.pending_operations:
                            self.pending_operations[target_session] = []
                        self.pending_operations[target_session].append(op)
                    
                    processed += 1
                    self.logger.debug(f"Assigned queued operation {op.operation_id} to {target_session}")
                else:
                    # Could not assign, re-queue
                    failed_to_process.append(op)
            
            # Re-queue operations that couldn't be processed
            for op in failed_to_process:
                self.operation_queue.enqueue(op)
            
            if processed > 0:
                self.logger.info(f"✅ Processed {processed} queued operations")
    
    async def start_health_monitoring(self):
        """
        Start session health monitoring with failure/recovery callbacks
        
        Requirements: 16.1, 16.2, 23.1, 23.3
        """
        if not self.sessions:
            self.logger.warning("⚠️ No sessions to monitor")
            return
        
        # Start health monitoring with callbacks
        await self.health_monitor.start_monitoring(
            sessions=self.sessions,
            failure_callback=self._handle_session_failure,
            recovery_callback=self._handle_session_recovery
        )
        
        self.logger.info("✅ Started session health monitoring with failure recovery")
    
    async def stop_health_monitoring(self):
        """
        Stop session health monitoring
        
        Requirements: 16.2
        """
        await self.health_monitor.stop_monitoring()
        self.logger.info("✅ Stopped session health monitoring")

    async def shutdown(self):
        """
        Graceful shutdown of all sessions with timeout and cleanup (Task 10.5, Task 14)
        
        Requirements: 5.4, 6.2, 16.2
        """
        self.logger.info("🔴 Shutting down session manager...")
        
        # Stop health monitoring first
        try:
            await self.stop_health_monitoring()
        except Exception as e:
            self.logger.error(f"❌ Error stopping health monitoring during shutdown: {e}")
        
        # Stop monitoring
        try:
            await self.stop_global_monitoring()
        except Exception as e:
            self.logger.error(f"❌ Error stopping monitoring during shutdown: {e}")
        
        # Cancel all tasks across all sessions with timeout (Task 10.5)
        session_names = list(self.sessions.keys())
        self.logger.info(f"🔄 Cancelling tasks for {len(session_names)} sessions...")
        
        for session_name in session_names:
            try:
                await self.cleanup_session_tasks(session_name)
            except Exception as e:
                self.logger.error(f"❌ Error cleaning up tasks for {session_name}: {e}")
        
        # Disconnect all sessions with timeout
        self.logger.info("🔌 Disconnecting all sessions...")
        disconnect_tasks = []
        for session_name, session in self.sessions.items():
            disconnect_tasks.append(asyncio.create_task(session.disconnect()))
        
        # Wait for disconnection with timeout (5 seconds per session)
        try:
            await asyncio.wait_for(
                asyncio.gather(*disconnect_tasks, return_exceptions=True),
                timeout=5.0 * len(self.sessions)
            )
        except asyncio.TimeoutError:
            self.logger.warning("⏱️ Some sessions did not disconnect within timeout")
        
        # Clean up all resources (Task 10.5)
        self.sessions.clear()
        self.session_locks.clear()
        self.global_tasks.clear()
        self.session_load.clear()
        self.operation_metrics = {
            'scraping': 0,
            'monitoring': 0,
            'sending': 0,
            'other': 0
        }
        self.active_scrape_count = 0
        
        self.logger.info("✅ Session manager shutdown complete")
        
    async def scrape_group_members_random_session(self, group_identifier: str, max_members: int = 10000, fallback_to_messages: bool = True, message_days_back: int = 10) -> Dict:
        """
        Scrape group members using load-balanced session selection
        
        Args:
            group_identifier: Group username, invite link, or ID
            max_members: Maximum number of members to scrape
            fallback_to_messages: Whether to fallback to message scraping
            message_days_back: Days to look back for message scraping
            
        Returns:
            Dict with scrape results
        """
        if not self.sessions:
            return {
                'success': False,
                'error': 'No active sessions available',
                'file_path': None,
                'session_used': None
            }
        
        # Use load balancing to select session (Task 7.4)
        session_name = self._get_available_session()
        
        if not session_name:
            return {
                'success': False,
                'error': 'No connected sessions available',
                'file_path': None,
                'session_used': None
            }
        
        session = self.sessions[session_name]
        
        self.logger.info(f"🎯 Using session '{session_name}' to scrape {group_identifier}")
        
        # Track session load (Task 7.1)
        await self.increment_session_load(session_name)
        
        # Use try-finally to ensure session load is always decremented (Requirement 7.1)
        try:
            # Use scrape semaphore to limit concurrent scrapes (Task 6.1)
            # Context manager ensures semaphore is always released (Requirement 7.1)
            async with self.scrape_semaphore:
                self.active_scrape_count += 1
                await self.increment_operation_metric('scraping')  # Task 6.3
                try:
                    # Wrap scraping operation with retry logic (Task 8.3)
                    result = await self._execute_with_retry(
                        'scraping',
                        session.scrape_group_members,
                        group_identifier, 
                        max_members, 
                        fallback_to_messages=fallback_to_messages,
                        message_days_back=message_days_back
                    )
                    result['session_used'] = session_name
                    return result
                except Exception as e:
                    # Log error with operation context (Requirement 7.1)
                    self.logger.error(
                        f"❌ Error scraping {group_identifier} with session {session_name}: {e}"
                    )
                    return {
                        'success': False,
                        'error': str(e),
                        'file_path': None,
                        'session_used': session_name
                    }
                finally:
                    # Always decrement counters (Requirement 7.1)
                    self.active_scrape_count -= 1
                    await self.decrement_operation_metric('scraping')  # Task 6.3
        finally:
            # Always decrement session load (Requirement 7.1)
            await self.decrement_session_load(session_name)  # Task 7.1

    async def join_and_scrape_group_random_session(self, group_identifier: str, max_members: int = 10000, fallback_to_messages: bool = True, message_days_back: int = 10) -> Dict:
        """
        Join group and scrape members using load-balanced session selection
        """
        if not self.sessions:
            return {
                'success': False,
                'error': 'No active sessions available',
                'file_path': None,
                'session_used': None,
                'joined': False
            }
        
        # Use load balancing to select session (Task 7.4)
        session_name = self._get_available_session()
        
        if not session_name:
            return {
                'success': False,
                'error': 'No connected sessions available',
                'file_path': None,
                'session_used': None,
                'joined': False
            }
        
        session = self.sessions[session_name]
        
        self.logger.info(f"🎯 Using session '{session_name}' to join and scrape {group_identifier}")
        
        # Track session load (Task 7.1)
        await self.increment_session_load(session_name)
        
        # Use scrape semaphore to limit concurrent scrapes (Task 6.1)
        async with self.scrape_semaphore:
            self.active_scrape_count += 1
            await self.increment_operation_metric('scraping')  # Task 6.3
            try:
                # Define the join and scrape operation as a single unit for retry
                async def join_and_scrape_operation():
                    # First join the group
                    join_success = await session.join_chat(group_identifier)
                    
                    if not join_success:
                        raise Exception('Failed to join group')
                    
                    # Wait for join to process
                    await asyncio.sleep(5)
                    
                    # Then scrape with fallback option
                    result = await session.scrape_group_members(
                        group_identifier, 
                        max_members, 
                        fallback_to_messages=fallback_to_messages,
                        message_days_back=message_days_back
                    )
                    return result
                
                # Wrap join and scrape operation with retry logic (Task 8.3)
                result = await self._execute_with_retry(
                    'scraping',
                    join_and_scrape_operation
                )
                result['session_used'] = session_name
                result['joined'] = True
                return result
                
            except Exception as e:
                self.logger.error(f"❌ Error joining and scraping with session {session_name}: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'file_path': None,
                    'session_used': session_name,
                    'joined': False
                }
            finally:
                self.active_scrape_count -= 1
                await self.decrement_operation_metric('scraping')  # Task 6.3
                await self.decrement_session_load(session_name)  # Task 7.1

    async def bulk_scrape_groups(self, groups: List[str], join_first: bool = False, max_members: int = 10000) -> Dict[str, Dict]:
        """
        Scrape multiple groups using load-balanced session selection
        
        Args:
            groups: List of group identifiers
            join_first: Whether to join group first before scraping
            max_members: Maximum members per group
            
        Returns:
            Dict mapping group identifiers to scrape results
        """
        if not self.sessions:
            return {}
        
        results = {}
        
        for i, group in enumerate(groups):
            # Use load balancing to select session (Task 7.4)
            session_name = self._get_available_session()
            
            if not session_name:
                self.logger.warning(f"⚠️ No available session for {group}")
                results[group] = {
                    'success': False,
                    'error': 'No connected sessions available',
                    'file_path': None,
                    'session_used': None
                }
                continue
            
            session = self.sessions[session_name]
            
            self.logger.info(f"🔄 Scraping {group} with session '{session_name}'")
            
            # Track session load (Task 7.1)
            await self.increment_session_load(session_name)
            
            # Use scrape semaphore to limit concurrent scrapes (Task 6.1)
            async with self.scrape_semaphore:
                self.active_scrape_count += 1
                await self.increment_operation_metric('scraping')  # Task 6.3
                try:
                    # Wrap scraping operation with retry logic (Task 8.3)
                    if join_first:
                        result = await self._execute_with_retry(
                            'scraping',
                            session.join_and_scrape_members,
                            group,
                            max_members
                        )
                    else:
                        result = await self._execute_with_retry(
                            'scraping',
                            session.scrape_group_members,
                            group,
                            max_members
                        )
                    
                    result['session_used'] = session_name
                    results[group] = result
                    
                    # Add delay between scrapes to avoid rate limiting
                    if i < len(groups) - 1:
                        await asyncio.sleep(5)
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to scrape {group}: {e}")
                    results[group] = {
                        'success': False,
                        'error': str(e),
                        'file_path': None,
                        'session_used': session_name
                    }
                finally:
                    self.active_scrape_count -= 1
                    await self.decrement_operation_metric('scraping')  # Task 6.3
                    await self.decrement_session_load(session_name)  # Task 7.1
        
        return results
    
    async def safe_bulk_scrape_with_rotation(self, groups: List[str], join_first: bool = False, max_members: int = 10000) -> Dict[str, Dict]:
        """
        Scrape multiple groups with load-balanced session selection and daily limits enforcement
        """
        if not self.sessions:
            return {}
        
        results = {}
        
        for i, group in enumerate(groups):
            # Use load balancing to select session (Task 7.4)
            session_name = self._get_available_session()
            
            if not session_name:
                self.logger.warning(f"⚠️ No available session for {group}")
                results[group] = {
                    'success': False,
                    'error': 'No connected sessions available',
                    'file_path': None,
                    'session_used': None
                }
                continue
            
            session = self.sessions[session_name]
            
            # Check if session has daily quota remaining
            session._reset_daily_counters_if_needed()
            if (session.daily_stats['groups_scraped_today'] >= session.daily_limits['max_groups_per_day'] or
                session.daily_stats['messages_read'] >= session.daily_limits['max_messages_per_day']):
                self.logger.warning(f"⏸️  Session {session_name} has no daily quota, skipping...")
                results[group] = {
                    'success': False,
                    'error': 'Daily quota exhausted for this session',
                    'file_path': None,
                    'session_used': session_name
                }
                continue
            
            self.logger.info(f"🔄 Scraping {group} with session '{session_name}' (rotation {i+1}/{len(groups)})")
            
            # Track session load (Task 7.1)
            await self.increment_session_load(session_name)
            
            # Use scrape semaphore to limit concurrent scrapes (Task 6.1)
            async with self.scrape_semaphore:
                self.active_scrape_count += 1
                await self.increment_operation_metric('scraping')  # Task 6.3
                try:
                    # Wrap scraping operation with retry logic (Task 8.3)
                    if join_first:
                        result = await self._execute_with_retry(
                            'scraping',
                            session.join_and_scrape_members,
                            group,
                            max_members
                        )
                    else:
                        result = await self._execute_with_retry(
                            'scraping',
                            session.scrape_group_members,
                            group,
                            max_members
                        )
                    
                    result['session_used'] = session_name
                    results[group] = result
                    
                    # Enhanced delay between scrapes
                    if i < len(groups) - 1:
                        delay = 10 if join_first else 5  # Longer delay if joining
                        self.logger.info(f"⏳ Waiting {delay} seconds before next scrape...")
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to scrape {group}: {e}")
                    results[group] = {
                        'success': False,
                        'error': str(e),
                        'file_path': None,
                        'session_used': session_name
                    }
                finally:
                    self.active_scrape_count -= 1
                    await self.decrement_operation_metric('scraping')  # Task 6.3
                    await self.decrement_session_load(session_name)  # Task 7.1
        
        return results
    
    async def extract_links_from_channels(self, channels: List[str], limit_messages: int = 100) -> Dict[str, Dict]:
        """
        Extract group links from multiple 'لینک دونی' channels
        
        Args:
            channels: List of channel identifiers
            limit_messages: Messages to scan per channel
            
        Returns:
            Dict mapping channel to extracted links
        """
        if not self.sessions:
            return {}
        
        results = {}
        session_names = list(self.sessions.keys())
        
        for i, channel in enumerate(channels):
            # Rotate sessions
            session_name = session_names[i % len(session_names)]
            session = self.sessions[session_name]
            
            self.logger.info(f"🔍 Extracting links from {channel} with session '{session_name}'")
            
            try:
                result = await session.extract_group_links(channel, limit_messages)
                results[channel] = result
                
                # Rate limiting between channels
                if i < len(channels) - 1:
                    await asyncio.sleep(3)
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to extract links from {channel}: {e}")
                results[channel] = {
                    'success': False,
                    'error': str(e),
                    'source_channel': channel,
                    'telegram_links': []
                }
        
        return results

    async def bulk_scrape_from_link_channels(self, link_channels: List[str], join_first: bool = False, 
                                        limit_messages: int = 100, max_members: int = 10000) -> Dict:
        """
        Complete workflow: Extract links from 'لینک دونی' channels, then scrape all found groups
        """
        # Step 1: Extract links from source channels
        self.logger.info("🔗 Step 1: Extracting group links from source channels...")
        links_results = await self.extract_links_from_channels(link_channels, limit_messages)
        
        # Step 2: Collect all unique Telegram links
        all_telegram_links = []
        for channel, result in links_results.items():
            if result['success']:
                all_telegram_links.extend(result['telegram_links'])
        
        # Remove duplicates
        unique_links = list(set(all_telegram_links))
        self.logger.info(f"📋 Step 1 Complete: Found {len(unique_links)} unique group links")
        
        if not unique_links:
            return {
                'link_extraction': links_results,
                'scraping_results': {},
                'total_groups_found': 0,
                'total_groups_scraped': 0
            }
        
        # Step 3: Scrape all found groups
        self.logger.info("🔍 Step 2: Scraping all found groups...")
        scraping_results = await self.bulk_scrape_groups(
            groups=unique_links,
            join_first=join_first,
            max_members=max_members,
            enforce_daily_limits=True
        )
        
        return {
            'link_extraction': links_results,
            'scraping_results': scraping_results,
            'total_groups_found': len(unique_links),
            'total_groups_scraped': len([r for r in scraping_results.values() if r.get('success')])
        }
        
    async def check_target_type(self, target: str) -> Dict:
        """
        Check target type using a random session
        """
        if not self.sessions:
            return {
                'success': False,
                'target': target,
                'error': 'No active sessions available',
                'scrapable': False
            }
        
        # Get random session
        session_names = list(self.sessions.keys())
        random_session_name = random.choice(session_names)
        session = self.sessions[random_session_name]
        
        result = await session.check_target_type(target)
        result['session_used'] = random_session_name
        return result

    async def bulk_check_targets(self, targets: List[str]) -> Dict[str, Dict]:
        """
        Check multiple targets with session rotation
        """
        if not self.sessions:
            return {}
        
        results = {}
        session_names = list(self.sessions.keys())
        
        for i, target in enumerate(targets):
            session_name = session_names[i % len(session_names)]
            session = self.sessions[session_name]
            
            results[target] = await session.check_target_type(target)
            results[target]['session_used'] = session_name
            
            # Rate limiting
            if i < len(targets) - 1:
                await asyncio.sleep(0.5)
        
        return results

    async def filter_scrapable_targets(self, targets: List[str]) -> List[str]:
        """
        Filter targets to only scrapable groups/supergroups
        """
        checked_targets = await self.bulk_check_targets(targets)
        
        scrapable = []
        for target, result in checked_targets.items():
            if result.get('scrapable', False):
                scrapable.append(target)
            else:
                self.logger.info(f"⏭️  Skipping {target}: {result.get('reason', 'Not scrapable')}")
        
        self.logger.info(f"🎯 Filtered {len(scrapable)}/{len(targets)} scrapable targets")
        return scrapable

    async def safe_bulk_scrape_with_filter(self, targets: List[str], join_first: bool = False, 
                                        max_members: int = 10000) -> Dict[str, Dict]:
        """
        Complete safe workflow: Check targets → Filter scrapable → Scrape
        """
        # Step 1: Check all targets
        self.logger.info("🔍 Step 1: Checking target types...")
        checked_targets = await self.bulk_check_targets(targets)
        
        # Step 2: Filter only scrapable targets
        scrapable_targets = []
        for target, result in checked_targets.items():
            if result.get('scrapable', False):
                scrapable_targets.append(target)
            else:
                self.logger.info(f"⏭️  Skipping {target}: {result.get('reason', 'Not scrapable')}")
        
        self.logger.info(f"🎯 Step 1 Complete: {len(scrapable_targets)}/{len(targets)} targets are scrapable")
        
        if not scrapable_targets:
            return {
                'target_checks': checked_targets,
                'scraping_results': {},
                'total_checked': len(targets),
                'total_scrapable': 0,
                'total_scraped': 0
            }
        
        # Step 3: Scrape only scrapable targets
        self.logger.info("🔍 Step 2: Scraping scrapable targets...")
        scraping_results = await self.bulk_scrape_groups(
            groups=scrapable_targets,
            join_first=join_first,
            max_members=max_members
        )
        
        return {
            'target_checks': checked_targets,
            'scraping_results': scraping_results,
            'total_checked': len(targets),
            'total_scrapable': len(scrapable_targets),
            'total_scraped': len([r for r in scraping_results.values() if r.get('success')])
        }

    # Manual Blacklist Management Interface (Task 6)
    # Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    
    async def add_to_blacklist(self, user_id: str, reason: str = "manual") -> Dict[str, any]:
        """
        Manually add a user to the blacklist
        
        Args:
            user_id: User identifier to add
            reason: Reason for blacklisting (default: "manual")
            
        Returns:
            Dict with success status and message
            
        Requirements: 5.1, 5.5
        """
        from .models import RecipientValidator
        
        # Validate user identifier format (Requirement 5.5)
        validation_result = RecipientValidator.validate_recipient(user_id)
        
        if not validation_result.valid:
            error_messages = [error.message for error in validation_result.errors]
            self.logger.warning(
                f"❌ Invalid user identifier for blacklist addition: {user_id}",
                extra={
                    'operation_type': 'manual_blacklist_add',
                    'user_id': user_id,
                    'validation_errors': error_messages
                }
            )
            return {
                'success': False,
                'user_id': user_id,
                'error': f"Invalid user identifier: {'; '.join(error_messages)}"
            }
        
        try:
            # Add to blacklist and persist (Requirement 5.1)
            await self.blacklist_manager.add(user_id, reason=reason, session_name=None)
            
            # Log manual operation (Requirement 1.4, 2.2, 6.5)
            self.logger.info(
                f"✅ Manually added user {user_id} to blacklist",
                extra={
                    'operation_type': 'manual_blacklist_add',
                    'user_id': user_id,
                    'reason': reason,
                    'admin_action': True
                }
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'message': f"User {user_id} added to blacklist"
            }
            
        except Exception as e:
            self.logger.error(
                f"❌ Failed to add user {user_id} to blacklist: {e}",
                extra={
                    'operation_type': 'manual_blacklist_add',
                    'user_id': user_id,
                    'error': str(e)
                }
            )
            return {
                'success': False,
                'user_id': user_id,
                'error': str(e)
            }
    
    async def remove_from_blacklist(self, user_id: str) -> Dict[str, any]:
        """
        Manually remove a user from the blacklist
        
        Args:
            user_id: User identifier to remove
            
        Returns:
            Dict with success status and message
            
        Requirements: 5.2, 5.5
        """
        from .models import RecipientValidator
        
        # Validate user identifier format (Requirement 5.5)
        validation_result = RecipientValidator.validate_recipient(user_id)
        
        if not validation_result.valid:
            error_messages = [error.message for error in validation_result.errors]
            self.logger.warning(
                f"❌ Invalid user identifier for blacklist removal: {user_id}",
                extra={
                    'operation_type': 'manual_blacklist_remove',
                    'user_id': user_id,
                    'validation_errors': error_messages
                }
            )
            return {
                'success': False,
                'user_id': user_id,
                'error': f"Invalid user identifier: {'; '.join(error_messages)}"
            }
        
        try:
            # Remove from blacklist and persist (Requirement 5.2)
            removed = await self.blacklist_manager.remove(user_id)
            
            if removed:
                # Log manual operation (Requirement 1.4, 2.2, 6.5)
                self.logger.info(
                    f"✅ Manually removed user {user_id} from blacklist",
                    extra={
                        'operation_type': 'manual_blacklist_remove',
                        'user_id': user_id,
                        'admin_action': True
                    }
                )
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': f"User {user_id} removed from blacklist"
                }
            else:
                self.logger.info(
                    f"⚠️ User {user_id} not found in blacklist",
                    extra={
                        'operation_type': 'manual_blacklist_remove',
                        'user_id': user_id,
                        'found': False
                    }
                )
                
                return {
                    'success': False,
                    'user_id': user_id,
                    'error': f"User {user_id} not found in blacklist"
                }
            
        except Exception as e:
            self.logger.error(
                f"❌ Failed to remove user {user_id} from blacklist: {e}",
                extra={
                    'operation_type': 'manual_blacklist_remove',
                    'user_id': user_id,
                    'error': str(e)
                }
            )
            return {
                'success': False,
                'user_id': user_id,
                'error': str(e)
            }
    
    async def get_blacklist(self) -> Dict[str, any]:
        """
        Get all blacklisted users with their metadata
        
        Returns:
            Dict with success status and list of blacklist entries
            
        Requirements: 5.3
        """
        try:
            # Get all entries (Requirement 5.3)
            entries = await self.blacklist_manager.get_all()
            
            # Log view operation (Requirement 1.4, 2.2, 6.5)
            self.logger.info(
                f"📋 Retrieved blacklist with {len(entries)} entries",
                extra={
                    'operation_type': 'manual_blacklist_view',
                    'entry_count': len(entries),
                    'admin_action': True
                }
            )
            
            return {
                'success': True,
                'count': len(entries),
                'entries': entries
            }
            
        except Exception as e:
            self.logger.error(
                f"❌ Failed to retrieve blacklist: {e}",
                extra={
                    'operation_type': 'manual_blacklist_view',
                    'error': str(e)
                }
            )
            return {
                'success': False,
                'error': str(e),
                'entries': []
            }
    
    async def clear_blacklist(self) -> Dict[str, any]:
        """
        Clear the entire blacklist
        
        Returns:
            Dict with success status and number of entries removed
            
        Requirements: 5.4
        """
        try:
            # Clear blacklist and persist (Requirement 5.4)
            count = await self.blacklist_manager.clear()
            
            # Log clear operation (Requirement 1.4, 2.2, 6.5)
            self.logger.info(
                f"🗑️ Cleared blacklist ({count} entries removed)",
                extra={
                    'operation_type': 'manual_blacklist_clear',
                    'entries_removed': count,
                    'admin_action': True
                }
            )
            
            return {
                'success': True,
                'entries_removed': count,
                'message': f"Blacklist cleared ({count} entries removed)"
            }
            
        except Exception as e:
            self.logger.error(
                f"❌ Failed to clear blacklist: {e}",
                extra={
                    'operation_type': 'manual_blacklist_clear',
                    'error': str(e)
                }
            )
            return {
                'success': False,
                'error': str(e)
            }
