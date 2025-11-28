"""
TelegramSession class - Individual session management
"""

import os
import csv
import time
import asyncio
import logging

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Callable, Any

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import Message, MessageReactions, MessageActionChatAddUser

from .config import MonitoringTarget
from .constants import (
    DAILY_MESSAGES_LIMIT,
    DAILY_GROUPS_LIMIT,
    MONITORING_COOLDOWN,
    MESSAGE_SCRAPING_DAYS
)


@dataclass
class QueuedOperation:
    """Represents an operation waiting in queue"""
    operation_type: str  # 'scraping', 'sending', 'monitoring', etc.
    operation_func: Callable  # The actual operation to execute
    args: tuple
    kwargs: dict
    priority: int = 0  # Higher priority executes first (monitoring=10, scraping=5)
    queued_at: float = field(default_factory=time.time)
    timeout: float = 300.0  # Operation timeout in seconds
    result_future: Optional[asyncio.Future] = None
    _sequence: int = field(default=0, init=False)  # For FIFO within same priority
    
    # Class variable to track sequence numbers
    _sequence_counter: int = 0
    
    def __post_init__(self):
        """Initialize result_future and sequence number after instance creation"""
        if self.result_future is None:
            self.result_future = asyncio.Future()
        # Assign sequence number for FIFO ordering within same priority
        QueuedOperation._sequence_counter += 1
        object.__setattr__(self, '_sequence', QueuedOperation._sequence_counter)
    
    def __lt__(self, other):
        """
        Comparison for PriorityQueue ordering
        Lower value = higher priority in queue
        So we negate priority (higher priority value = lower queue value)
        Within same priority, use sequence for FIFO
        """
        if not isinstance(other, QueuedOperation):
            return NotImplemented
        # Compare priorities first (negate so higher priority values come first)
        # In PriorityQueue, lower values have higher priority
        # So -10 < -5 < -1 means monitoring(10) > scraping(5) > sending(1)
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority value = higher actual priority
        # Within same priority, use sequence for FIFO (lower sequence = earlier)
        return self._sequence < other._sequence
    
    def __le__(self, other):
        """Less than or equal comparison"""
        if not isinstance(other, QueuedOperation):
            return NotImplemented
        return self < other or self == other
    
    def __gt__(self, other):
        """Greater than comparison"""
        if not isinstance(other, QueuedOperation):
            return NotImplemented
        return not self <= other
    
    def __ge__(self, other):
        """Greater than or equal comparison"""
        if not isinstance(other, QueuedOperation):
            return NotImplemented
        return not self < other
    
    def __eq__(self, other):
        """Equality comparison"""
        if not isinstance(other, QueuedOperation):
            return NotImplemented
        return self.priority == other.priority and self._sequence == other._sequence


@dataclass
class OperationContext:
    """Context for tracking an operation"""
    operation_type: str  # 'monitoring', 'scraping', 'sending', etc.
    session_name: str
    start_time: float
    task: Optional[asyncio.Task] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRegistryEntry:
    """Entry in the task registry"""
    task: asyncio.Task
    task_type: str  # 'monitoring', 'scraping', 'event_handler', etc.
    session_name: str
    created_at: float
    parent_operation: Optional[str] = None


class TelegramSession:
    """
    Manages a single Telegram session with monitoring and messaging capabilities
    
    LOCK ACQUISITION ORDER (to prevent deadlocks):
    =====================================================
    Locks must ALWAYS be acquired in this strict order:
    
    1. Manager-level locks (global_task_lock, metrics_lock) - acquired in TelegramSessionManager
    2. Manager-level semaphores (scrape_semaphore, operation_semaphore) - acquired in TelegramSessionManager
    3. Session-level locks (session_locks in TelegramSessionManager) - acquired in TelegramSessionManager
    4. Session operation lock (operation_lock) - THIS CLASS
    5. Session task lock (task_lock) - THIS CLASS
    6. Session handler lock (_handler_lock) - THIS CLASS
    
    NEVER acquire locks in reverse order!
    If a lower-level lock is held, NEVER attempt to acquire a higher-level lock.
    =====================================================
    """
    
    def __init__(self, session_file: str, api_id: int, api_hash: str):
        """
        Initialize Telegram Session
        
        Args:
            session_file: Path to .session file
            api_id: Telegram API ID
            api_hash: Telegram API Hash
        """
        self.session_file = session_file
        self.api_id = api_id
        self.api_hash = api_hash
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        
        # Monitoring system
        self.monitoring_targets: Dict[str, MonitoringTarget] = {}
        self.is_monitoring = False
        self._event_handler = None
        self._handler_error_count = 0  # Track error count per session
        
        # Task management
        self.active_tasks: Set[asyncio.Task] = set()
        self.task_lock = asyncio.Lock()
        
        # Operation synchronization (existing lock, now properly used)
        self.operation_lock = asyncio.Lock()
        self.current_operation: Optional[str] = None
        self.operation_start_time: Optional[float] = None
        
        # Operation queuing system
        self.operation_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=100)
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.operation_timeout: float = 300.0  # Default operation timeout (5 minutes)
        self.queue_wait_timeout: float = 60.0  # Max time to wait in queue (1 minute)
        
        # Enhanced task tracking
        self.monitoring_task: Optional[asyncio.Task] = None
        self.task_registry: Dict[asyncio.Task, TaskRegistryEntry] = {}  # Track task metadata
        
        # Event handler isolation
        self._handler_lock: asyncio.Lock = asyncio.Lock()
        
        # Limits for not getting banned
        self.daily_stats = {
            'messages_read': 0,
            'last_reset_date': datetime.now().date(),
            'groups_scraped_today': 0
        }
        self.daily_limits = {
            'max_messages_per_day': 500,  # READING messages limit
            'max_groups_per_day': 10      # Groups to scrape per day
        }
        
        # Setup logging
        self.logger = logging.getLogger(f"TelegramSession_{session_file}")

    def _get_operation_timeout(self, operation_type: str) -> float:
        """
        Get timeout for specific operation type
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending')
            
        Returns:
            Timeout in seconds
        """
        timeouts = {
            'scraping': 300.0,  # 5 minutes
            'monitoring': 3600.0,  # 1 hour
            'sending': 60.0,  # 1 minute
        }
        return timeouts.get(operation_type, self.operation_timeout)

    def _get_operation_priority(self, operation_type: str) -> int:
        """
        Get priority for specific operation type
        
        Args:
            operation_type: Type of operation
            
        Returns:
            Priority (higher = more important)
        """
        priorities = {
            'monitoring': 10,
            'scraping': 5,
            'sending': 1,
        }
        return priorities.get(operation_type, 0)

    async def _execute_with_timeout(
        self,
        operation_type: str,
        operation_func: Callable,
        *args,
        **kwargs
    ):
        """
        Execute an operation with timeout and proper error handling
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending')
            operation_func: The operation function to execute
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func
            
        Returns:
            Result from the operation
            
        Raises:
            TimeoutError: If operation exceeds timeout
            Exception: Any exception from the operation
        """
        timeout = self._get_operation_timeout(operation_type)
        
        try:
            self.logger.debug(f"⏱️ Executing {operation_type} with {timeout}s timeout")
            
            # Execute operation with timeout
            result = await asyncio.wait_for(
                operation_func(*args, **kwargs),
                timeout=timeout
            )
            
            self.logger.debug(f"✅ {operation_type} completed within timeout")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"{operation_type} operation timed out after {timeout}s"
            self.logger.warning(f"⏱️ {error_msg}")
            
            # Cancel the operation task if possible
            # Note: The task is already cancelled by asyncio.wait_for
            
            raise TimeoutError(error_msg)
            
        except Exception as e:
            self.logger.error(f"❌ {operation_type} operation failed: {e}")
            raise

    async def _submit_operation(
        self,
        operation_type: str,
        operation_func: Callable,
        *args,
        **kwargs
    ):
        """
        Submit an operation to the queue or execute immediately if idle
        
        Args:
            operation_type: Type of operation ('scraping', 'monitoring', 'sending')
            operation_func: The actual operation function to execute
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func
            
        Returns:
            Result from the operation
        """
        # Check if we can execute immediately (operation lock is free)
        if not self.operation_lock.locked():
            # Try to acquire lock immediately
            lock_acquired = await self._acquire_lock_with_timeout(
                self.operation_lock,
                timeout=0.1,  # Very short timeout for immediate check
                lock_name="operation"
            )
            
            if lock_acquired:
                # Use try-finally to ensure lock is always released (Requirement 7.1)
                try:
                    # Execute immediately without queuing
                    self.current_operation = operation_type
                    self.operation_start_time = time.time()
                    
                    self.logger.debug(f"▶️ Executing {operation_type} immediately (no queue)")
                    
                    # Use the timeout wrapper
                    result = await self._execute_with_timeout(
                        operation_type,
                        operation_func,
                        *args,
                        **kwargs
                    )
                    
                    operation_duration = time.time() - self.operation_start_time
                    self.logger.debug(f"✅ {operation_type} completed in {operation_duration:.1f}s")
                    
                    return result
                    
                except Exception as e:
                    # Log error with operation context (Requirement 7.1)
                    self.logger.error(
                        f"❌ Operation {operation_type} failed: {e} "
                        f"(session: {self.session_file}, duration: {time.time() - self.operation_start_time:.1f}s)"
                    )
                    raise
                    
                finally:
                    # Always release lock and clear operation context (Requirement 7.1)
                    self.current_operation = None
                    self.operation_start_time = None
                    self._release_lock_with_logging(self.operation_lock, "operation")
        
        # Queue is busy, add to queue
        self.logger.debug(f"📥 Queuing {operation_type} operation")
        
        # Check queue depth before adding (Requirement 1.4)
        queue_depth = self.get_queue_depth()
        if queue_depth >= 100:  # Max queue size
            error_msg = f"Operation queue is full ({queue_depth}/100), cannot submit operation"
            self.logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Create queued operation
        priority = self._get_operation_priority(operation_type)
        timeout = self._get_operation_timeout(operation_type)
        
        queued_op = QueuedOperation(
            operation_type=operation_type,
            operation_func=operation_func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout
        )
        
        # Add to queue with timeout (Requirement 1.4)
        try:
            await asyncio.wait_for(
                self.operation_queue.put(queued_op),
                timeout=5.0  # Timeout for adding to queue
            )
            self.logger.debug(
                f"📥 Operation queued successfully (queue depth: {queue_depth + 1}/100)"
            )
        except asyncio.TimeoutError:
            error_msg = "Operation queue is full, cannot submit operation (timeout)"
            self.logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        except asyncio.QueueFull:
            error_msg = f"Operation queue is full ({queue_depth}/100), cannot submit operation"
            self.logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Wait for result
        try:
            result = await asyncio.wait_for(
                queued_op.result_future,
                timeout=self.queue_wait_timeout + timeout
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out (queue wait + execution)")

    async def _process_operation_queue(self):
        """
        Process operations from queue in priority order
        Runs continuously until session disconnects
        """
        self.logger.debug("🔄 Queue processor started")
        
        while self.is_connected:
            lock_acquired = False
            try:
                # First, acquire the operation lock
                # This ensures we only pull from queue when we can execute
                lock_acquired = await self._acquire_lock_with_timeout(
                    self.operation_lock,
                    timeout=1.0,  # Short timeout to allow checking is_connected
                    lock_name="operation"
                )
                
                if not lock_acquired:
                    # Lock not available, try again
                    continue
                
                # Use try-finally to ensure lock is always released (Requirement 7.1)
                try:
                    # Now that we have the lock, get next operation from queue
                    # Use short timeout to avoid holding lock while waiting for queue
                    try:
                        queued_op = await asyncio.wait_for(
                            self.operation_queue.get(),
                            timeout=0.1
                        )
                    except asyncio.TimeoutError:
                        # No operation available, release lock and continue
                        continue
                    
                    # Check if operation has timed out while waiting in queue
                    queue_wait_time = time.time() - queued_op.queued_at
                    if queue_wait_time > self.queue_wait_timeout:
                        error_msg = f"Operation timed out in queue after {queue_wait_time:.1f}s"
                        self.logger.warning(f"⏱️ {error_msg}")
                        if not queued_op.result_future.done():
                            queued_op.result_future.set_exception(TimeoutError(error_msg))
                        continue
                    
                    # Set current operation context
                    self.current_operation = queued_op.operation_type
                    self.operation_start_time = time.time()
                    
                    self.logger.debug(
                        f"▶️ Executing {queued_op.operation_type} operation "
                        f"(waited {queue_wait_time:.1f}s in queue)"
                    )
                    
                    # Execute operation with timeout
                    try:
                        result = await self._execute_with_timeout(
                            queued_op.operation_type,
                            queued_op.operation_func,
                            *queued_op.args,
                            **queued_op.kwargs
                        )
                        
                        # Set result if future not already done
                        if not queued_op.result_future.done():
                            queued_op.result_future.set_result(result)
                        
                        operation_duration = time.time() - self.operation_start_time
                        self.logger.debug(
                            f"✅ {queued_op.operation_type} completed in {operation_duration:.1f}s"
                        )
                        
                    except TimeoutError as e:
                        # Log error with operation context (Requirement 7.1)
                        self.logger.warning(
                            f"⏱️ {e} (session: {self.session_file}, "
                            f"operation: {queued_op.operation_type})"
                        )
                        if not queued_op.result_future.done():
                            queued_op.result_future.set_exception(e)
                    
                    except Exception as e:
                        # Log error with operation context (Requirement 7.1)
                        self.logger.error(
                            f"❌ Operation {queued_op.operation_type} failed: {e} "
                            f"(session: {self.session_file})"
                        )
                        if not queued_op.result_future.done():
                            queued_op.result_future.set_exception(e)
                
                finally:
                    # Always release lock and clear operation context (Requirement 7.1)
                    self.current_operation = None
                    self.operation_start_time = None
                    if lock_acquired:
                        self._release_lock_with_logging(self.operation_lock, "operation")
                    
            except Exception as e:
                # Log error with context (Requirement 7.1)
                self.logger.error(
                    f"❌ Error in queue processor: {e} (session: {self.session_file})"
                )
                # Ensure lock is released even on unexpected errors (Requirement 7.1)
                if lock_acquired:
                    self._release_lock_with_logging(self.operation_lock, "operation")
                await asyncio.sleep(1)  # Brief delay before continuing
        
        self.logger.debug("🛑 Queue processor stopped")

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
        try:
            # Log acquisition attempt at DEBUG level with timestamp
            self.logger.debug(
                f"🔒 [{time.time():.3f}] Attempting to acquire {lock_name} lock "
                f"(timeout: {timeout}s, session: {self.session_file})"
            )
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            # Log successful acquisition at DEBUG level with timestamp
            self.logger.debug(
                f"✅ [{time.time():.3f}] Acquired {lock_name} lock "
                f"(session: {self.session_file})"
            )
            return True
        except asyncio.TimeoutError:
            # Log timeout at WARNING level with lock state (Requirement 7.3)
            lock_state = {
                'lock_name': lock_name,
                'is_locked': lock.locked(),
                'current_operation': self.current_operation,
                'operation_start_time': self.operation_start_time,
                'operation_duration': time.time() - self.operation_start_time if self.operation_start_time else None,
                'queue_depth': self.get_queue_depth(),
                'active_tasks': len(self.active_tasks),
                'session': str(self.session_file)
            }
            self.logger.warning(
                f"⏱️ [{time.time():.3f}] TIMEOUT acquiring {lock_name} lock after {timeout}s - "
                f"Possible deadlock or contention. Lock state: {lock_state}"
            )
            return False
    
    def _release_lock_with_logging(self, lock: asyncio.Lock, lock_name: str = "unknown"):
        """
        Release lock with logging
        
        Args:
            lock: Lock to release
            lock_name: Name of lock for logging
        """
        if lock.locked():
            lock.release()
            # Log release at DEBUG level with timestamp
            self.logger.debug(
                f"🔓 [{time.time():.3f}] Released {lock_name} lock "
                f"(session: {self.session_file})"
            )
        else:
            self.logger.warning(
                f"⚠️ [{time.time():.3f}] Attempted to release unlocked {lock_name} lock "
                f"(session: {self.session_file})"
            )

    def _create_operation_context(self, operation_type: str, metadata: Optional[Dict] = None) -> OperationContext:
        """
        Create operation context for tracking
        
        Args:
            operation_type: Type of operation
            metadata: Additional metadata
            
        Returns:
            OperationContext object
        """
        return OperationContext(
            operation_type=operation_type,
            session_name=str(self.session_file),
            start_time=time.time(),
            metadata=metadata or {}
        )

    async def connect(self) -> bool:
        """
        Connect to Telegram
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
            await self.client.start()
            self.is_connected = True
            
            # Start queue processor
            self.queue_processor_task = self._create_task(
                self._process_operation_queue(),
                task_type="queue_processor"
            )
            
            self.logger.info("✅ Successfully connected to Telegram")
            return True
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Telegram and cleanup resources"""
        await self.stop_monitoring()
        
        # Stop queue processor first
        self.is_connected = False  # This will signal queue processor to stop
        if self.queue_processor_task and not self.queue_processor_task.done():
            self.queue_processor_task.cancel()
            try:
                await asyncio.wait_for(self.queue_processor_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                self.logger.warning("⏱️ Queue processor did not cancel cleanly within 5 seconds")
        
        # Cancel all active tasks with timeout
        await self._cancel_all_tasks_with_timeout(timeout=5.0)
        
        if self.client:
            await self.client.disconnect()
            self.logger.info("🔌 Disconnected from Telegram")
    
    async def _cancel_all_tasks_with_timeout(self, timeout: float = 5.0):
        """
        Cancel all session tasks with timeout and log tasks that don't cancel cleanly
        
        Args:
            timeout: Timeout in seconds for task cancellation
        """
        async with self.task_lock:
            if not self.active_tasks:
                self.logger.debug("No active tasks to cancel")
                return
            
            self.logger.info(f"🛑 Cancelling {len(self.active_tasks)} active tasks...")
            
            # Cancel all tasks
            tasks_to_cancel = list(self.active_tasks)
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation with timeout
            if tasks_to_cancel:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                        timeout=timeout
                    )
                    self.logger.info("✅ All tasks cancelled successfully")
                except asyncio.TimeoutError:
                    # Log tasks that didn't cancel cleanly
                    still_running = [t for t in tasks_to_cancel if not t.done()]
                    self.logger.warning(
                        f"⏱️ {len(still_running)} tasks did not cancel within {timeout}s timeout"
                    )
                    
                    # Log details of tasks that didn't cancel
                    for task in still_running:
                        entry = self.task_registry.get(task)
                        if entry:
                            self.logger.warning(
                                f"   - Task type: {entry.task_type}, "
                                f"parent: {entry.parent_operation}, "
                                f"age: {time.time() - entry.created_at:.1f}s"
                            )
                        else:
                            self.logger.warning(f"   - Unknown task: {task}")
            
            # Clear the task sets
            self.active_tasks.clear()
            self.task_registry.clear()

    def _create_task(
        self, 
        coro, 
        task_type: str = "unknown",
        parent_operation: Optional[str] = None
    ) -> asyncio.Task:
        """
        Safely create and track an async task with metadata
        
        Args:
            coro: Coroutine to run
            task_type: Type of task ('monitoring', 'scraping', 'event_handler', 'queue_processor', etc.)
            parent_operation: Parent operation type if this task is part of a larger operation
            
        Returns:
            asyncio.Task: Created task
        """
        task = asyncio.create_task(coro)
        
        # Create registry entry with metadata
        entry = TaskRegistryEntry(
            task=task,
            task_type=task_type,
            session_name=str(self.session_file),
            created_at=time.time(),
            parent_operation=parent_operation
        )
        
        # Add to both tracking structures
        self.active_tasks.add(task)
        self.task_registry[task] = entry
        
        # Auto-remove from both registries on completion
        def cleanup_callback(t):
            self.active_tasks.discard(t)
            self.task_registry.pop(t, None)
            self.logger.debug(f"🧹 Task cleanup: {task_type} (parent: {parent_operation})")
        
        task.add_done_callback(cleanup_callback)
        
        self.logger.debug(f"📝 Created task: {task_type} (parent: {parent_operation})")
        return task

    async def start_monitoring(self, targets: List[Dict]) -> bool:
        """
        Start monitoring channels/groups and react to new messages
        
        Args:
            targets: List of dicts with 'chat_id', 'reaction', and 'cooldown'
            
        Returns:
            bool: True if monitoring started successfully
        """
        return await self._submit_operation(
            'monitoring',
            self._start_monitoring_impl,
            targets
        )

    async def _start_monitoring_impl(self, targets: List[Dict]) -> bool:
        """
        Internal implementation of start_monitoring
        This is the actual work that gets queued/executed
        
        Args:
            targets: List of dicts with 'chat_id', 'reaction', and 'cooldown'
            
        Returns:
            bool: True if monitoring started successfully
        """
        if self.is_monitoring:
            await self.stop_monitoring()

        try:
            # Setup monitoring targets
            for target in targets:
                monitoring_target = MonitoringTarget(
                    chat_id=target['chat_id'],
                    reaction=target.get('reaction', '👍'),
                    cooldown=target.get('cooldown', 2.0)
                )
                self.monitoring_targets[target['chat_id']] = monitoring_target

            # Setup event handler (now async)
            await self._setup_event_handler()
            
            # Create monitoring task to track the monitoring operation
            # The event handler itself runs in the background, but we track it as a monitoring task
            async def monitoring_keepalive():
                """Keep monitoring active and track it as a task"""
                try:
                    while self.is_monitoring:
                        await asyncio.sleep(60)  # Check every minute
                except asyncio.CancelledError:
                    self.logger.debug("Monitoring keepalive cancelled")
                    raise
            
            self.monitoring_task = self._create_task(
                monitoring_keepalive(),
                task_type="monitoring",
                parent_operation="monitoring"
            )
            
            self.is_monitoring = True
            self.logger.info(f"🎯 Started monitoring {len(targets)} targets")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start monitoring: {e}")
            return False

    async def stop_monitoring(self):
        """Stop monitoring and cleanup event handlers"""
        # Acquire handler lock to ensure only one handler setup/teardown at a time
        async with self._handler_lock:
            # Cancel monitoring task if it exists
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await asyncio.wait_for(self.monitoring_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    self.logger.debug("Monitoring task cancelled")
                self.monitoring_task = None
            
            # Remove event handler
            if self._event_handler and self.client:
                self.client.remove_event_handler(self._event_handler)
                self._event_handler = None
            
            self.monitoring_targets.clear()
            self.is_monitoring = False
            self.logger.info("🛑 Stopped monitoring")

    async def _setup_event_handler(self):
        """Setup isolated event handler for this session"""
        if not self.client:
            return

        # Acquire handler lock to ensure only one handler setup/teardown at a time
        async with self._handler_lock:
            # Remove existing handler if present
            if self._event_handler:
                self.client.remove_event_handler(self._event_handler)
                self._event_handler = None

            # Track error count per session
            if not hasattr(self, '_handler_error_count'):
                self._handler_error_count = 0

            @self.client.on(events.NewMessage)
            async def message_handler(event):
                # Skip our own messages
                if event.out:
                    return
                    
                try:
                    chat = await event.get_chat()
                    chat_identifier = self._get_chat_identifier(chat)
                    
                    # Check if we're monitoring this chat
                    target = self.monitoring_targets.get(chat_identifier)
                    if not target:
                        return
                    
                    # Rate limiting check
                    current_time = time.time()
                    if current_time - target.last_reaction_time < target.cooldown:
                        return
                    
                    # React to the message
                    success = await self._safe_react_to_message(chat, event.message.id, target.reaction)
                    if success:
                        target.last_reaction_time = current_time
                        self.logger.debug(f"🔔 Reacted to new message in {chat_identifier}")
                    
                except Exception as e:
                    # Track error count per session
                    self._handler_error_count += 1
                    # Log errors without crashing event loop
                    self.logger.error(f"❌ Error in message handler (count: {self._handler_error_count}): {e}")

            self._event_handler = message_handler

    def _get_chat_identifier(self, chat) -> str:
        """
        Get unique identifier for chat
        
        Args:
            chat: Telegram chat object
            
        Returns:
            str: Chat identifier (username or ID)
        """
        return getattr(chat, 'username', None) or f"id_{chat.id}"

    async def _safe_react_to_message(self, chat, message_id: int, reaction: str) -> bool:
        """
        Safely react to message with error handling
        
        Args:
            chat: Chat object
            message_id: ID of message to react to
            reaction: Emoji reaction
            
        Returns:
            bool: True if reaction successful
        """
        try:
            await self.client(SendReactionRequest(
                peer=chat,
                msg_id=message_id,
                reaction=reaction
            ))
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to react to message: {e}")
            return False

    async def send_message(self, target: str, message: str, reply_to: int = None) -> bool:
        """
        Send message to chat/group/channel
        
        Args:
            target: chat ID, @username, or invite link
            message: text message to send
            reply_to: message ID to reply to
            
        Returns:
            bool: Success status
        """
        return await self._submit_operation(
            'sending',
            self._send_message_impl,
            target,
            message,
            reply_to
        )

    async def _send_message_impl(self, target: str, message: str, reply_to: int = None) -> bool:
        """
        Internal implementation of send_message
        This is the actual work that gets queued/executed
        
        Args:
            target: chat ID, @username, or invite link
            message: text message to send
            reply_to: message ID to reply to
            
        Returns:
            bool: Success status
        """
        try:
            entity = await self.client.get_entity(target)
            await self.client.send_message(entity, message, reply_to=reply_to)
            self.logger.info(f"📤 Message sent to {target}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to send message to {target}: {e}")
            return False

    async def join_chat(self, target: str) -> bool:
        """
        Simplified join_chat method using correct Telegram methods
        """
        try:
            # Handle private invite links
            if target.startswith('https://t.me/+') or target.startswith('t.me/+'):
                # Extract invite hash
                invite_hash = target.split('/')[-1]
                if invite_hash.startswith('+'):
                    invite_hash = invite_hash[1:]
                
                self.logger.info(f"🔑 Joining private group with hash: {invite_hash}")
                
                # Use ImportChatInviteRequest for private links
                from telethon.tl.functions.messages import ImportChatInviteRequest
                await self.client(ImportChatInviteRequest(invite_hash))
                self.logger.info(f"✅ Successfully joined private group")
                return True
                
            else:
                # For public groups/channels
                entity = await self.client.get_entity(target)
                from telethon.tl.functions.channels import JoinChannelRequest
                await self.client(JoinChannelRequest(entity))
                self.logger.info(f"✅ Successfully joined {target}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Failed to join {target}: {e}")
            return False

    async def get_members(self, target: str, limit: int = 100) -> List[Dict]:
        """
        Get member list of group or channel
        
        Args:
            target: @username, chat ID, or invite link
            limit: maximum number of members to fetch
            
        Returns:
            List of member dictionaries
        """
        try:
            entity = await self.client.get_entity(target)
            
            participants = await self.client.get_participants(entity, limit=limit)
            
            members = []
            for participant in participants:
                members.append({
                    'id': participant.id,
                    'username': getattr(participant, 'username', None),
                    'first_name': getattr(participant, 'first_name', None),
                    'last_name': getattr(participant, 'last_name', None),
                    'phone': getattr(participant, 'phone', None)
                })
            
            self.logger.info(f"👥 Retrieved {len(members)} members from {target}")
            return members
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get members from {target}: {e}")
            return []

    async def bulk_send_messages(self, targets: List[str], message: str, delay: float = 1.0) -> List:
        """
        Send messages to multiple targets with rate limiting
        
        Args:
            targets: List of target identifiers
            message: Message to send
            delay: Delay between sends in seconds
            
        Returns:
            List of results
        """
        tasks = []
        for i, target in enumerate(targets):
            task = self._create_task(
                self._send_with_delay(target, message, i * delay),
                task_type="sending",
                parent_operation="bulk_send"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def _send_with_delay(self, target: str, message: str, delay: float):
        """Send message with delay for rate limiting"""
        await asyncio.sleep(delay)
        # send_message now uses _submit_operation which includes timeout
        return await self.send_message(target, message)

    def get_status(self) -> Dict:
        """
        Get current session status
        
        Returns:
            Dict with session status information
        """
        return {
            'connected': self.is_connected,
            'monitoring': self.is_monitoring,
            'monitoring_targets_count': len(self.monitoring_targets),
            'active_tasks': len(self.active_tasks)
        }
    
    def get_active_task_count(self) -> int:
        """
        Get total count of active tasks for this session
        
        Returns:
            Number of active tasks
        """
        return len(self.active_tasks)
    
    def get_active_task_count_by_type(self, task_type: str) -> int:
        """
        Get count of active tasks of a specific type
        
        Args:
            task_type: Type of task to count ('monitoring', 'scraping', 'event_handler', etc.)
            
        Returns:
            Number of active tasks of the specified type
        """
        count = 0
        for task, entry in self.task_registry.items():
            if not task.done() and entry.task_type == task_type:
                count += 1
        return count
    
    def get_task_details(self) -> List[Dict]:
        """
        Get detailed information about all active tasks for debugging
        
        Returns:
            List of dicts with task details
        """
        details = []
        current_time = time.time()
        
        for task, entry in self.task_registry.items():
            if not task.done():
                details.append({
                    'task_type': entry.task_type,
                    'parent_operation': entry.parent_operation,
                    'session_name': entry.session_name,
                    'age_seconds': current_time - entry.created_at,
                    'created_at': entry.created_at,
                    'done': task.done(),
                    'cancelled': task.cancelled() if task.done() else False
                })
        
        return details
    
    def get_queue_depth(self) -> int:
        """
        Get the current depth of the operation queue (Requirement 1.4)
        
        Returns:
            Number of operations waiting in queue
        """
        return self.operation_queue.qsize()
    
    def get_queue_status(self) -> Dict:
        """
        Get detailed queue status information (Requirement 1.4)
        
        Returns:
            Dict with queue status details
        """
        queue_depth = self.get_queue_depth()
        return {
            'queue_depth': queue_depth,
            'max_queue_size': 100,
            'queue_utilization': queue_depth / 100.0,
            'is_full': queue_depth >= 100,
            'current_operation': self.current_operation,
            'operation_start_time': self.operation_start_time
        }
    
    async def scrape_group_members(self, group_identifier: str, max_members: int = 10000, fallback_to_messages: bool = True, message_days_back: int = 10) -> Dict:
        """
        Scrape members from a group/channel with fallback to message-based scraping
        
        Args:
            group_identifier: Group username, invite link, or ID
            max_members: Maximum number of members to scrape
            fallback_to_messages: Whether to fallback to message scraping if member list fails
            message_days_back: Days to look back for message scraping fallback
            
        Returns:
            Dict with scrape results and file path
        """
        return await self._submit_operation(
            'scraping',
            self._scrape_group_members_impl,
            group_identifier,
            max_members,
            fallback_to_messages,
            message_days_back
        )

    async def _scrape_group_members_impl(self, group_identifier: str, max_members: int = 10000, fallback_to_messages: bool = True, message_days_back: int = 10) -> Dict:
        """
        Internal implementation of scrape_group_members
        This is the actual work that gets queued/executed
        
        Args:
            group_identifier: Group username, invite link, or ID
            max_members: Maximum number of members to scrape
            fallback_to_messages: Whether to fallback to message scraping if member list fails
            message_days_back: Days to look back for message scraping fallback
            
        Returns:
            Dict with scrape results and file path
        """
        try:
            # Get the entity
            entity = await self.client.get_entity(group_identifier)
            
            # Check if it's a group/channel
            if not isinstance(entity, (Channel, Chat)):
                return {
                    'success': False,
                    'error': 'Target is not a group or channel',
                    'file_path': None,
                    'source': 'direct'
                }
            
            # First try: Get participants directly
            try:
                participants = await self.client.get_participants(entity, limit=max_members)
                
                if participants:
                    # Create data directory if it doesn't exist
                    os.makedirs('data', exist_ok=True)
                    
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    group_name = getattr(entity, 'username', f"group_{entity.id}")
                    filename = f"data/members_{group_name}_{timestamp}.csv"
                    
                    # Ensure unique filename
                    counter = 1
                    base_filename = filename
                    while os.path.exists(filename):
                        name, ext = os.path.splitext(base_filename)
                        filename = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    # Write to CSV
                    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['user_id', 'username', 'first_name', 'last_name', 'phone', 'scraped_at', 'source']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        
                        writer.writeheader()
                        for participant in participants:
                            # Filter out bots and deleted accounts
                            if await self._is_valid_user(participant):
                                writer.writerow({
                                    'user_id': participant.id,
                                    'username': getattr(participant, 'username', ''),
                                    'first_name': getattr(participant, 'first_name', ''),
                                    'last_name': getattr(participant, 'last_name', ''),
                                    'phone': getattr(participant, 'phone', ''),
                                    'scraped_at': datetime.now().isoformat(),
                                    'source': 'member_list'
                                })
                    
                    valid_members = [p for p in participants if await self._is_valid_user(p)]
                    self.logger.info(f"📊 Scraped {len(valid_members)} valid members from {group_identifier} -> {filename}")
                    
                    return {
                        'success': True,
                        'file_path': filename,
                        'members_count': len(valid_members),
                        'group_name': group_name,
                        'source': 'member_list'
                    }
                else:
                    raise Exception("No members found in member list")
                    
            except Exception as direct_error:
                self.logger.warning(f"⚠️ Direct member scraping failed: {direct_error}")
                
                # Second try: Fallback to message-based scraping
                if fallback_to_messages:
                    self.logger.info("🔄 Falling back to message-based user scraping...")
                    message_result = await self.scrape_members_from_messages(
                        group_identifier, 
                        days_back=message_days_back,
                        limit_messages=1000
                    )
                    return message_result
                else:
                    return {
                        'success': False,
                        'error': f"Direct member scraping failed: {str(direct_error)}",
                        'file_path': None,
                        'source': 'direct'
                    }
                
        except Exception as e:
            self.logger.error(f"❌ Failed to scrape members from {group_identifier}: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_path': None,
                'source': 'direct'
            }

    async def join_and_scrape_members(self, group_identifier: str, max_members: int = 10000) -> Dict:
        """
        Join group and then scrape members with better error handling
        """
        return await self._submit_operation(
            'scraping',
            self._join_and_scrape_members_impl,
            group_identifier,
            max_members
        )

    async def _join_and_scrape_members_impl(self, group_identifier: str, max_members: int = 10000) -> Dict:
        """
        Internal implementation of join_and_scrape_members
        This is the actual work that gets queued/executed
        """
        try:
            # First try to join the group
            self.logger.info(f"🚪 Attempting to join group: {group_identifier}")
            join_success = await self.join_chat(group_identifier)
            
            if not join_success:
                return {
                    'success': False,
                    'error': 'Failed to join group - may be private or requires approval',
                    'file_path': None,
                    'joined': False
                }
            
            # Wait longer for the join to process and get permissions
            self.logger.info("⏳ Waiting for join to process...")
            await asyncio.sleep(5)
            
            # Then scrape members - call the internal implementation directly
            scrape_result = await self._scrape_group_members_impl(group_identifier, max_members)
            scrape_result['joined'] = True
            
            return scrape_result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to join and scrape {group_identifier}: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_path': None,
                'joined': False
            }
    
    async def scrape_members_from_messages(self, group_identifier: str, days_back: int = 10, limit_messages: int = 1000) -> Dict:
        """
        Scrape users from recent messages and reactions when member list is not accessible
        """
        # Check daily group scrape limit
        if not self._check_daily_limits('groups_scraped'):
            return {
                'success': False,
                'error': 'Daily group scrape limit reached',
                'file_path': None,
                'members_count': 0
            }
        
        try:
            # Get the entity
            entity = await self.client.get_entity(group_identifier)
            
            # Increment group counter
            self.daily_stats['groups_scraped_today'] += 1
            
            # ... rest of the existing method remains the same ...
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            self.logger.info(f"📨 Scraping users from messages in last {days_back} days (max {limit_messages} messages)")
            
            # Get messages with reactions
            messages = await self._get_messages_with_reactions(entity, days_back, limit_messages)
            users = await self._extract_users_from_messages(messages)
            
            if not users:
                return {
                    'success': False,
                    'error': 'No valid users found in messages',
                    'file_path': None,
                    'members_count': 0
                }
            
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            group_name = getattr(entity, 'username', f"group_{entity.id}")
            filename = f"data/message_users_{group_name}_{timestamp}.csv"
            
            # Ensure unique filename
            counter = 1
            base_filename = filename
            while os.path.exists(filename):
                name, ext = os.path.splitext(base_filename)
                filename = f"{name}_{counter}{ext}"
                counter += 1
            
            # Write to CSV (same format as member scraping)
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_id', 'username', 'first_name', 'last_name', 'phone', 'scraped_at', 'source']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for user_data in users:
                    writer.writerow(user_data)
            
            self.logger.info(f"📊 Extracted {len(users)} users from {len(messages)} messages -> {filename}")
            
            return {
                'success': True,
                'file_path': filename,
                'members_count': len(users),
                'group_name': group_name,
                'messages_processed': len(messages),
                'source': 'message_scraping'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to scrape users from messages in {group_identifier}: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_path': None,
                'members_count': 0
            }
    
    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if it's a new day"""
        today = datetime.now().date()
        if self.daily_stats['last_reset_date'] != today:
            self.daily_stats = {
                'messages_read': 0,
                'last_reset_date': today,
                'groups_scraped_today': 0
            }
            self.logger.info("🔄 Daily counters reset")

    def _check_daily_limits(self, operation_type: str) -> bool:
        """Check if daily limits are exceeded"""
        self._reset_daily_counters_if_needed()
        
        if operation_type == 'messages_read':
            if self.daily_stats['messages_read'] >= self.daily_limits['max_messages_per_day']:
                self.logger.warning(f"📅 Daily message read limit reached: {self.daily_stats['messages_read']}/{self.daily_limits['max_messages_per_day']}")
                return False
        
        elif operation_type == 'groups_scraped':
            if self.daily_stats['groups_scraped_today'] >= self.daily_limits['max_groups_per_day']:
                self.logger.warning(f"📅 Daily group scrape limit reached: {self.daily_stats['groups_scraped_today']}/{self.daily_limits['max_groups_per_day']}")
                return False
        
        return True

    async def _safe_message_iteration(self, entity, days_back: int, limit: int):
        """
        Extra-safe message iteration with comprehensive rate limiting and error handling
        """
        messages = []
        offset_date = datetime.now() - timedelta(days=days_back)
        
        # Check daily limits first
        if not self._check_daily_limits('messages_read'):
            return []
        
        # Calculate safe limit based on daily quota
        remaining_messages = self.daily_limits['max_messages_per_day'] - self.daily_stats['messages_read']
        safe_limit = min(limit, remaining_messages, 1000)  # Additional safety cap
        
        if safe_limit <= 0:
            self.logger.warning("📅 No message quota remaining for today")
            return []
        
        self.logger.info(f"📊 Safe message iteration: limit={safe_limit}, remaining today={remaining_messages}")
        
        try:
            total_fetched = 0
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            async for message in self.client.iter_messages(
                entity,
                offset_date=offset_date,
                limit=safe_limit
            ):
                try:
                    messages.append(message)
                    total_fetched += 1
                    self.daily_stats['messages_read'] += 1  # Track daily count
                    consecutive_errors = 0  # Reset error counter on success
                    
                    # Enhanced rate limiting:
                    if total_fetched % 10 == 0:  # Every 10 messages
                        await asyncio.sleep(1)   # 1-second delay
                    elif total_fetched % 30 == 0: # Every 30 messages  
                        await asyncio.sleep(3)   # 3-second delay
                        self.logger.info(f"⏸️  Rate limiting: processed {total_fetched}/{safe_limit} messages...")
                    elif total_fetched % 100 == 0: # Every 100 messages
                        await asyncio.sleep(5)   # 5-second delay
                    
                    # Stop if we hit the safe limit
                    if total_fetched >= safe_limit:
                        self.logger.info(f"🏁 Reached safe message limit: {safe_limit}")
                        break
                        
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"⚠️  Error processing message {total_fetched}: {e}")
                    
                    # Stop if too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error("🚨 Too many consecutive errors, stopping message iteration")
                        break
                    
                    await asyncio.sleep(3)  # Longer delay after errors
                    
        except Exception as e:
            self.logger.error(f"❌ Fatal error in message iteration: {e}")
        
        self.logger.info(f"✅ Message iteration complete: {len(messages)} messages processed")
        return messages

    async def _safe_message_iteration(self, entity, days_back: int, limit: int):
        """
        Extra-safe message iteration with comprehensive rate limiting and error handling
        """
        messages = []
        offset_date = datetime.now() - timedelta(days=days_back)
        
        # Check daily limits first
        if not self._check_daily_limits('messages_read'):
            return []
        
        # Calculate safe limit based on daily quota
        remaining_messages = self.daily_limits['max_messages_per_day'] - self.daily_stats['messages_read']
        safe_limit = min(limit, remaining_messages, 1000)  # Additional safety cap
        
        if safe_limit <= 0:
            self.logger.warning("📅 No message quota remaining for today")
            return []
        
        self.logger.info(f"📊 Safe message iteration: limit={safe_limit}, remaining today={remaining_messages}")
        
        try:
            total_fetched = 0
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            async for message in self.client.iter_messages(
                entity,
                offset_date=offset_date,
                limit=safe_limit
            ):
                try:
                    messages.append(message)
                    total_fetched += 1
                    self.daily_stats['messages_read'] += 1  # Track daily count
                    consecutive_errors = 0  # Reset error counter on success
                    
                    # Enhanced rate limiting:
                    if total_fetched % 10 == 0:  # Every 10 messages
                        await asyncio.sleep(1)   # 1-second delay
                    elif total_fetched % 30 == 0: # Every 30 messages  
                        await asyncio.sleep(3)   # 3-second delay
                        self.logger.info(f"⏸️  Rate limiting: processed {total_fetched}/{safe_limit} messages...")
                    elif total_fetched % 100 == 0: # Every 100 messages
                        await asyncio.sleep(5)   # 5-second delay
                    
                    # Stop if we hit the safe limit
                    if total_fetched >= safe_limit:
                        self.logger.info(f"🏁 Reached safe message limit: {safe_limit}")
                        break
                        
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"⚠️  Error processing message {total_fetched}: {e}")
                    
                    # Stop if too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error("🚨 Too many consecutive errors, stopping message iteration")
                        break
                    
                    await asyncio.sleep(3)  # Longer delay after errors
                    
        except Exception as e:
            self.logger.error(f"❌ Fatal error in message iteration: {e}")
        
        self.logger.info(f"✅ Message iteration complete: {len(messages)} messages processed")
        return messages
    
    async def _get_messages_with_reactions(self, entity, days_back: int, limit: int):
        """
        Fetch messages with reactions using enhanced safety measures
        """
        return await self._safe_message_iteration(entity, days_back, limit)

    async def _extract_users_from_messages(self, messages):
        """
        Extract unique users from messages and reactions, excluding bots and deleted accounts
        """
        users_map = {}  # user_id -> user_data
        
        for message in messages:
            try:
                # Skip forwarded messages
                if message.fwd_from:
                    continue
                    
                # Extract sender
                if message.sender_id:
                    try:
                        sender = await self.client.get_entity(message.sender_id)
                        if await self._is_valid_user(sender):
                            user_id = sender.id
                            if user_id not in users_map:
                                users_map[user_id] = {
                                    'user_id': user_id,
                                    'username': getattr(sender, 'username', ''),
                                    'first_name': getattr(sender, 'first_name', ''),
                                    'last_name': getattr(sender, 'last_name', ''),
                                    'phone': getattr(sender, 'phone', ''),
                                    'scraped_at': datetime.now().isoformat(),
                                    'source': 'message_sender'
                                }
                    except Exception as e:
                        self.logger.debug(f"⚠️ Could not get sender entity: {e}")
                
                # Extract users from reactions
                if message.reactions:
                    try:
                        reaction_users = await self._extract_reaction_users(message)
                        for user in reaction_users:
                            if await self._is_valid_user(user):
                                user_id = user.id
                                if user_id not in users_map:
                                    users_map[user_id] = {
                                        'user_id': user_id,
                                        'username': getattr(user, 'username', ''),
                                        'first_name': getattr(user, 'first_name', ''),
                                        'last_name': getattr(user, 'last_name', ''),
                                        'phone': getattr(user, 'phone', ''),
                                        'scraped_at': datetime.now().isoformat(),
                                        'source': 'reaction'
                                    }
                    except Exception as e:
                        self.logger.debug(f"⚠️ Could not extract reaction users: {e}")
                        
            except Exception as e:
                self.logger.debug(f"⚠️ Error processing message {message.id}: {e}")
                continue
        
        return list(users_map.values())

    async def _extract_reaction_users(self, message):
        """
        Extract users who reacted to a message
        """
        reaction_users = []
        
        try:
            # Get message reactions details
            if hasattr(message.reactions, 'results'):
                for reaction in message.reactions.results:
                    if hasattr(reaction, 'reaction') and hasattr(reaction, 'count') and reaction.count > 0:
                        # For some reaction types we might be able to get users
                        # This is limited by Telegram API restrictions
                        pass
            
            # Alternative: Try to get recent reactors (if available in future Telethon versions)
            # Note: Getting specific reaction users may require premium or has limitations
            
        except Exception as e:
            self.logger.debug(f"⚠️ Could not extract reaction users from message {message.id}: {e}")
        
        return reaction_users

    async def _is_valid_user(self, user):
        """
        Check if user is valid (not bot, not deleted, etc.)
        """
        try:
            # Check if user is a bot
            if getattr(user, 'bot', False):
                return False
                
            # Check if user is deleted (no username, first_name, last_name)
            if not any([getattr(user, 'username', None), 
                    getattr(user, 'first_name', None), 
                    getattr(user, 'last_name', None)]):
                return False
                
            # Check if user has been inactive for too long (optional)
            # if hasattr(user, 'status') and hasattr(user.status, 'was_online'):
            #     last_online = user.status.was_online
            #     if (datetime.now() - last_online).days > 365:  # 1 year inactive
            #         return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"⚠️ Error validating user: {e}")
            return False
    
    async def extract_group_links(self, target: str, limit_messages: int = 100) -> Dict:
        """
        Extract group/channel links from a 'لینک دونی' type channel
        """
        try:
            # Get the entity
            entity = await self.client.get_entity(target)
            
            self.logger.info(f"🔗 Scanning {target} for group links (last {limit_messages} messages)")
            
            # Extract links from recent messages
            links = await self._extract_links_from_messages(entity, limit_messages)
            
            self.logger.info(f"📋 Found {len(links)} total links in messages")
            
            # Filter for Telegram group/channel links only
            telegram_links = self._filter_telegram_links(links)
            
            self.logger.info(f"📋 Found {len(telegram_links)} Telegram group links in {target}")
            
            # Debug: Show what was filtered out
            if len(telegram_links) == 0 and len(links) > 0:
                self.logger.info("🔍 Raw links found (before filtering):")
                for link in links[:10]:  # Show first 10 raw links
                    self.logger.info(f"   - {link}")
            
            return {
                'success': True,
                'source_channel': target,
                'total_links_found': len(links),
                'telegram_links': telegram_links,
                'telegram_links_count': len(telegram_links),
                'messages_scanned': limit_messages
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to extract links from {target}: {e}")
            return {
                'success': False,
                'error': str(e),
                'source_channel': target,
                'telegram_links': [],
                'telegram_links_count': 0
            }

    async def _extract_links_from_messages(self, entity, limit: int) -> List[str]:
        """
        Extract all links from recent messages including buttons
        """
        import re
        
        links = []
        url_pattern = re.compile(r'https?://[^\s]+|t\.me/[^\s]+|@[a-zA-Z0-9_]+')
        
        try:
            async for message in self.client.iter_messages(entity, limit=limit):
                # Extract from message text
                if message.text:
                    found_links = url_pattern.findall(message.text)
                    links.extend(found_links)
                
                # Extract from message buttons
                if message.buttons:
                    for button_row in message.buttons:
                        for button in button_row:
                            if hasattr(button, 'url') and button.url:
                                links.append(button.url)
                            if hasattr(button, 'text') and button.text:
                                # Check if button text contains links
                                text_links = url_pattern.findall(button.text)
                                links.extend(text_links)
                
                # Extract from web preview
                if hasattr(message, 'web_preview') and message.web_preview:
                    if message.web_preview.url:
                        links.append(message.web_preview.url)
                
                # Extract from media caption
                if message.media and hasattr(message.media, 'caption'):
                    caption_links = url_pattern.findall(message.media.caption or '')
                    links.extend(caption_links)
            
            # Remove duplicates and clean links
            unique_links = list(set(links))
            return unique_links
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting links from messages: {e}")
            return []

    def _filter_telegram_links(self, links: List[str]) -> List[str]:
        """
        Filter and normalize Telegram group/channel links
        """
        telegram_links = []
        
        # Common non-group URLs to exclude
        excluded_keywords = [
            'telegram.org', 't.me/telegram', 't.me/share', 't.me/addstickers',
            't.me/addtheme', 't.me/setlanguage', 't.me/iv', 't.me/bg',
            't.me/contact', 't.me/login', 't.me/download'
        ]
        
        for link in links:
            try:
                # Skip excluded URLs
                if any(keyword in link.lower() for keyword in excluded_keywords):
                    continue
                    
                normalized = self._normalize_telegram_link(link)
                if normalized:
                    telegram_links.append(normalized)
            except:
                continue
        
        # Remove duplicates after normalization
        return list(set(telegram_links))

    def _normalize_telegram_link(self, link: str) -> str:
        """
        Normalize Telegram link to standard format
        """
        import re
        
        # Remove any extra spaces or quotes
        link = link.strip(' "\'')
        
        # Pattern for different Telegram link formats
        patterns = [
            r'https?://t\.me/(joinchat/[a-zA-Z0-9_-]+)',  # https://t.me/joinchat/abc123
            r'https?://t\.me/(\+[a-zA-Z0-9]+)',           # https://t.me/+invitehash
            r'https?://t\.me/([a-zA-Z0-9_]{5,32})',       # https://t.me/username (5-32 chars)
            r't\.me/(joinchat/[a-zA-Z0-9_-]+)',           # t.me/joinchat/abc123
            r't\.me/(\+[a-zA-Z0-9]+)',                    # t.me/+invitehash
            r't\.me/([a-zA-Z0-9_]{5,32})',                # t.me/username
            r'@([a-zA-Z0-9_]{5,32})',                     # @username
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                if pattern.startswith('@'):
                    return f"@{match.group(1)}"
                elif 'joinchat' in pattern:
                    return f"https://t.me/{match.group(1)}"
                elif '+' in pattern:
                    return f"https://t.me/{match.group(1)}"
                else:
                    username = match.group(1)
                    # Skip common non-group words
                    if username.lower() in ['joinchat', 'telegram', 'contact', 'share', 'addstickers']:
                        continue
                    return f"https://t.me/{username}"
        
        return None
    
    async def check_target_type(self, target: str) -> Dict:
        """
        Check if target is a group, supergroup, channel, or invalid
        
        Returns:
            Dict with type information and scrapability
        """
        try:
            entity = await self.client.get_entity(target)
            
            result = {
                'success': True,
                'target': target,
                'type': self._get_entity_type(entity),
                'title': getattr(entity, 'title', ''),
                'username': getattr(entity, 'username', ''),
                'participants_count': getattr(entity, 'participants_count', 0),
                'scrapable': False,
                'reason': ''
            }
            
            # Determine if scrapable
            if result['type'] in ['group', 'supergroup', 'megagroup']:
                result['scrapable'] = True
                result['reason'] = 'Can scrape members'
            elif result['type'] == 'channel':
                result['scrapable'] = False
                result['reason'] = 'Channels do not have member lists'
            elif result['type'] == 'user':
                result['scrapable'] = False
                result['reason'] = 'Cannot scrape individual users'
            elif result['type'] == 'bot':
                result['scrapable'] = False
                result['reason'] = 'Cannot scrape bots'
            else:
                result['scrapable'] = False
                result['reason'] = 'Unknown entity type'
            
            self.logger.info(f"🔍 Target check: {target} -> {result['type']} ({result['reason']})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to check target type {target}: {e}")
            return {
                'success': False,
                'target': target,
                'error': str(e),
                'scrapable': False,
                'reason': f'Invalid target: {e}'
            }

    def _get_entity_type(self, entity) -> str:
        """
        Determine the type of Telegram entity
        """
        from telethon.tl.types import (
            Channel, Chat, User, ChatEmpty, ChatForbidden,
            ChannelForbidden, UserEmpty, UserFull
        )
        
        if isinstance(entity, Channel):
            if entity.megagroup:
                return 'megagroup'
            elif entity.broadcast:
                return 'channel'
            else:
                return 'supergroup'
        elif isinstance(entity, Chat):
            return 'group'
        elif isinstance(entity, User):
            if entity.bot:
                return 'bot'
            else:
                return 'user'
        elif isinstance(entity, (ChatEmpty, ChatForbidden, ChannelForbidden, UserEmpty)):
            return 'invalid'
        else:
            return 'unknown'

    async def bulk_check_targets(self, targets: List[str]) -> Dict[str, Dict]:
        """
        Check multiple targets for type and scrapability
        """
        results = {}
        
        for target in targets:
            results[target] = await self.check_target_type(target)
            # Small delay between checks to avoid rate limiting
            await asyncio.sleep(0.5)
        
        return results