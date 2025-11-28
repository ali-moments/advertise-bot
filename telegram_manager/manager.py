"""
TelegramSessionManager class - Multi-session management
"""

import asyncio
import logging
import random
from typing import List, Dict, Optional, Callable
from .session import TelegramSession
from .config import SessionConfig
from .database import DatabaseManager 
from .constants import (
    APP_ID, 
    APP_HASH, 
    DB_PATH, 
    SESSION_COUNT,
    MAX_CONCURRENT_OPERATIONS,
    DAILY_MESSAGES_LIMIT,
    DAILY_GROUPS_LIMIT
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
    
    def __init__(self, max_concurrent_operations: int = 3):
        """
        Initialize session manager
        
        Args:
            max_concurrent_operations: Maximum concurrent operations across all sessions
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
        
        # Session load balancing (Task 7.1)
        self.session_load: Dict[str, int] = {}  # Active operations per session
        self.session_selection_index: int = 0  # Round-robin index
        self.load_balancing_strategy: str = "round_robin"  # or "least_loaded"
        
        # Operation retry configuration (Task 8.1)
        self.retry_config: Dict[str, int] = {
            'scraping': 2,  # Retry scraping operations twice
            'monitoring': 0,  # Don't retry monitoring
            'sending': 1  # Retry sending once
        }
        self.retry_backoff_base: float = 2.0  # Exponential backoff base (seconds)

    async def load_sessions_from_db(self) -> Dict[str, bool]:
        """
        Load sessions from database instead of config file
        
        Returns:
            Dict mapping session names to load success status
        """
        try:
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
            session_configs = db_manager.convert_to_session_configs(accounts, APP_ID, APP_HASH)
            
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
                    results[config.name] = False
                    self.logger.error(f"❌ Failed to load session: {config.name}")
                    
            except Exception as e:
                results[config.name] = False
                self.logger.error(f"❌ Error loading session {config.name}: {e}")
        
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

    async def bulk_send_messages(self, targets: List[str], message: str, delay: float = 2.0) -> Dict:
        """
        Send messages using all sessions (load balancing)
        
        Args:
            targets: List of target identifiers
            message: Message to send
            delay: Delay between sends in seconds
            
        Returns:
            Dict with send results for each target
        """
        all_results = {}
        
        if not self.sessions:
            self.logger.warning("❌ No sessions available for sending messages")
            return all_results
        
        # Distribute targets among sessions
        sessions_list = list(self.sessions.values())
        targets_per_session = max(1, len(targets) // len(sessions_list))
        
        tasks = []
        for i, session in enumerate(sessions_list):
            start_idx = i * targets_per_session
            end_idx = start_idx + targets_per_session if i < len(sessions_list) - 1 else len(targets)
            session_targets = targets[start_idx:end_idx]
            
            if session_targets:
                # Wrap bulk send with retry logic (Task 8.3)
                async def send_with_retry():
                    return await self._execute_with_retry(
                        'sending',
                        session.bulk_send_messages,
                        session_targets,
                        message,
                        delay
                    )
                
                task = asyncio.create_task(send_with_retry())
                tasks.append((session, session_targets, task))
        
        # Wait for all sends to complete and collect results
        for session, session_targets, task in tasks:
            try:
                results = await task
                for target, result in zip(session_targets, results):
                    all_results[target] = {
                        'session': str(session.session_file),
                        'success': not isinstance(result, Exception),
                        'error': str(result) if isinstance(result, Exception) else None
                    }
            except Exception as e:
                self.logger.error(f"❌ Bulk send error: {e}")
                for target in session_targets:
                    all_results[target] = {
                        'session': str(session.session_file),
                        'success': False,
                        'error': str(e)
                    }
        
        return all_results

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
    
    def _get_session_round_robin(self) -> Optional[str]:
        """
        Get next available session using round-robin strategy (Task 7.2)
        
        Returns:
            Session name or None if no sessions available
        """
        if not self.sessions:
            return None
        
        session_names = list(self.sessions.keys())
        attempts = 0
        
        # Try to find a connected session
        while attempts < len(session_names):
            # Get next session in round-robin order
            session_name = session_names[self.session_selection_index % len(session_names)]
            self.session_selection_index += 1
            
            # Check if session is connected
            session = self.sessions[session_name]
            if session.is_connected:
                self.logger.debug(f"🔄 Round-robin selected: {session_name}")
                return session_name
            
            attempts += 1
        
        # No connected sessions found
        self.logger.warning("⚠️ No connected sessions available for round-robin selection")
        return None
    
    def _get_session_least_loaded(self) -> Optional[str]:
        """
        Get session with minimum active operations (Task 7.3)
        Break ties with round-robin
        
        Returns:
            Session name or None if no sessions available
        """
        if not self.sessions:
            return None
        
        # Find connected sessions with their loads
        connected_sessions = []
        for session_name, session in self.sessions.items():
            if session.is_connected:
                load = self.session_load.get(session_name, 0)
                connected_sessions.append((session_name, load))
        
        if not connected_sessions:
            self.logger.warning("⚠️ No connected sessions available for least-loaded selection")
            return None
        
        # Find minimum load
        min_load = min(load for _, load in connected_sessions)
        
        # Get all sessions with minimum load
        least_loaded = [name for name, load in connected_sessions if load == min_load]
        
        # If multiple sessions have same load, use round-robin to break tie
        if len(least_loaded) > 1:
            selected = least_loaded[self.session_selection_index % len(least_loaded)]
            self.session_selection_index += 1
            self.logger.debug(f"⚖️ Least-loaded selected (tie-break): {selected} (load: {min_load})")
        else:
            selected = least_loaded[0]
            self.logger.debug(f"⚖️ Least-loaded selected: {selected} (load: {min_load})")
        
        return selected
    
    def _get_available_session(self) -> Optional[str]:
        """
        Get an available session using configured strategy (Task 7.4)
        
        Returns:
            Session name or None if no sessions available
        """
        if self.load_balancing_strategy == "least_loaded":
            return self._get_session_least_loaded()
        else:
            # Default to round-robin
            return self._get_session_round_robin()
    
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried
        
        Args:
            error: The exception to check
            
        Returns:
            True if error is transient, False if permanent
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
    
    async def _execute_with_retry(
        self,
        operation_type: str,
        operation_func: Callable,
        *args,
        **kwargs
    ):
        """
        Execute an operation with retry logic and exponential backoff
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending')
            operation_func: The operation function to execute
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func
            
        Returns:
            Result from the operation
            
        Raises:
            Exception: The final exception if all retries fail
        """
        import time
        max_retries = self.retry_config.get(operation_type, 0)
        attempt = 0
        last_error = None
        start_time = time.time()
        
        while attempt <= max_retries:
            try:
                if attempt > 0:
                    # Enhanced retry logging (Requirement 7.3)
                    self.logger.info(
                        f"🔄 Retry attempt {attempt}/{max_retries} for {operation_type} "
                        f"(total elapsed: {time.time() - start_time:.1f}s)"
                    )
                
                # Execute the operation
                result = await operation_func(*args, **kwargs)
                
                if attempt > 0:
                    # Log successful retry with context (Requirement 7.3)
                    self.logger.info(
                        f"✅ {operation_type} succeeded on retry {attempt} "
                        f"(total elapsed: {time.time() - start_time:.1f}s)"
                    )
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Check if we should retry
                if attempt >= max_retries:
                    # Enhanced error logging with full context (Requirement 7.3)
                    self.logger.error(
                        f"❌ {operation_type} failed after {max_retries} retries: {e} "
                        f"(total elapsed: {time.time() - start_time:.1f}s, "
                        f"error_type: {type(e).__name__})"
                    )
                    raise
                
                # Check if error is transient
                is_transient = self._is_transient_error(e)
                if not is_transient:
                    # Log permanent error with context (Requirement 7.3)
                    self.logger.warning(
                        f"⚠️ Permanent error detected for {operation_type}, not retrying: {e} "
                        f"(error_type: {type(e).__name__})"
                    )
                    raise
                
                # Calculate backoff delay
                backoff_delay = self.retry_backoff_base ** attempt
                
                # Enhanced retry attempt logging (Requirement 7.3)
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

    async def shutdown(self):
        """
        Graceful shutdown of all sessions with timeout and cleanup (Task 10.5)
        
        Requirements: 5.4, 6.2
        """
        self.logger.info("🔴 Shutting down session manager...")
        
        # Stop monitoring first
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
            max_members=max_members,
            enforce_daily_limits=True
        )
        
        return {
            'target_checks': checked_targets,
            'scraping_results': scraping_results,
            'total_checked': len(targets),
            'total_scrapable': len(scrapable_targets),
            'total_scraped': len([r for r in scraping_results.values() if r.get('success')])
        }
