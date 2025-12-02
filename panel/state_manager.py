"""
State Management for Telegram Bot Panel

This module provides centralized state management for user sessions,
operation progress tracking, and monitoring configuration.

Requirements: AC-6.3, AC-6.4
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging


@dataclass
class UserSession:
    """
    User session data for tracking multi-step operations
    
    Attributes:
        user_id: Telegram user ID
        operation: Current operation type ('scraping', 'sending', 'monitoring', etc.)
        step: Current conversation step
        data: Operation-specific data storage
        progress_msg_id: Message ID for progress updates
        started_at: Timestamp when session started
        files: Uploaded files (csv, media) with their paths
        
    Requirements: AC-6.3
    """
    user_id: int
    operation: str
    step: str
    data: Dict[str, Any] = field(default_factory=dict)
    progress_msg_id: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    files: Dict[str, str] = field(default_factory=dict)
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value with default"""
        return self.data.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """Set data value"""
        self.data[key] = value
    
    def clear_data(self) -> None:
        """Clear all session data"""
        self.data.clear()
        self.files.clear()
    
    def age_seconds(self) -> float:
        """Get session age in seconds"""
        return time.time() - self.started_at


@dataclass
class OperationProgress:
    """
    Progress tracking for long-running operations
    
    Attributes:
        operation_id: Unique operation identifier
        operation_type: Type of operation ('scraping', 'sending', etc.)
        total: Total items to process
        completed: Number of completed items
        failed: Number of failed items
        started_at: Timestamp when operation started
        message_id: Message ID for progress updates
        user_id: User who initiated the operation
        status: Current status ('running', 'completed', 'failed', 'cancelled')
        error_message: Error message if operation failed
        result_data: Final result data when operation completes
        
    Requirements: AC-6.4
    """
    operation_id: str
    operation_type: str
    total: int
    completed: int = 0
    failed: int = 0
    started_at: float = field(default_factory=time.time)
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    status: str = 'running'
    error_message: Optional[str] = None
    result_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def remaining(self) -> int:
        """Get remaining items"""
        return max(0, self.total - self.completed - self.failed)
    
    @property
    def progress_percent(self) -> float:
        """Get progress percentage"""
        if self.total == 0:
            return 0.0
        return ((self.completed + self.failed) / self.total) * 100
    
    @property
    def success_rate(self) -> float:
        """Get success rate percentage"""
        processed = self.completed + self.failed
        if processed == 0:
            return 0.0
        return (self.completed / processed) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds"""
        return time.time() - self.started_at
    
    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """Estimate remaining time in seconds"""
        if self.completed == 0:
            return None
        
        avg_time_per_item = self.elapsed_seconds / self.completed
        return avg_time_per_item * self.remaining
    
    def increment_completed(self) -> None:
        """Increment completed count"""
        self.completed += 1
    
    def increment_failed(self) -> None:
        """Increment failed count"""
        self.failed += 1
    
    def mark_completed(self, result_data: Optional[Dict[str, Any]] = None) -> None:
        """Mark operation as completed"""
        self.status = 'completed'
        if result_data:
            self.result_data = result_data
    
    def mark_failed(self, error_message: str) -> None:
        """Mark operation as failed"""
        self.status = 'failed'
        self.error_message = error_message
    
    def mark_cancelled(self) -> None:
        """Mark operation as cancelled"""
        self.status = 'cancelled'


@dataclass
class MonitoringConfig:
    """
    Configuration for monitoring a channel
    
    Attributes:
        chat_id: Channel chat ID or username
        reactions: List of reaction configurations with emoji and weight
        cooldown: Cooldown period in seconds between reactions
        enabled: Whether monitoring is enabled for this channel
        added_at: Timestamp when channel was added
        stats: Statistics for this channel
        
    Requirements: AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5
    """
    chat_id: str
    reactions: List[Dict[str, Any]] = field(default_factory=list)
    cooldown: float = 1.0
    enabled: bool = True
    added_at: float = field(default_factory=time.time)
    stats: Dict[str, int] = field(default_factory=lambda: {
        'reactions_sent': 0,
        'messages_processed': 0,
        'errors': 0
    })
    
    def add_reaction(self, emoji: str, weight: int = 1) -> None:
        """Add or update a reaction"""
        # Check if reaction already exists
        for reaction in self.reactions:
            if reaction['emoji'] == emoji:
                reaction['weight'] = weight
                return
        
        # Add new reaction
        self.reactions.append({'emoji': emoji, 'weight': weight})
    
    def remove_reaction(self, emoji: str) -> bool:
        """Remove a reaction, returns True if found and removed"""
        for i, reaction in enumerate(self.reactions):
            if reaction['emoji'] == emoji:
                self.reactions.pop(i)
                return True
        return False
    
    def get_reaction_weight(self, emoji: str) -> Optional[int]:
        """Get weight for a specific reaction"""
        for reaction in self.reactions:
            if reaction['emoji'] == emoji:
                return reaction['weight']
        return None
    
    def increment_reactions_sent(self, count: int = 1) -> None:
        """Increment reactions sent counter"""
        self.stats['reactions_sent'] += count
    
    def increment_messages_processed(self, count: int = 1) -> None:
        """Increment messages processed counter"""
        self.stats['messages_processed'] += count
    
    def increment_errors(self, count: int = 1) -> None:
        """Increment error counter"""
        self.stats['errors'] += count
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            'reactions_sent': 0,
            'messages_processed': 0,
            'errors': 0
        }


class StateManager:
    """
    Centralized state management for the bot panel
    
    Manages user sessions, operation progress, and monitoring configurations
    with automatic cleanup and persistence support.
    
    Requirements: AC-6.3, AC-6.4
    """
    
    def __init__(self, session_timeout: int = 3600, cleanup_interval: int = 300):
        """
        Initialize state manager
        
        Args:
            session_timeout: Session timeout in seconds (default: 1 hour)
            cleanup_interval: Cleanup interval in seconds (default: 5 minutes)
        """
        self.logger = logging.getLogger("StateManager")
        
        # Storage
        self.user_sessions: Dict[int, UserSession] = {}
        self.operation_progress: Dict[str, OperationProgress] = {}
        self.monitoring_configs: Dict[str, MonitoringConfig] = {}
        
        # Configuration
        self.session_timeout = session_timeout
        self.cleanup_interval = cleanup_interval
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    # User Session Management
    
    def create_user_session(
        self,
        user_id: int,
        operation: str,
        step: str,
        data: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """
        Create a new user session
        
        Args:
            user_id: Telegram user ID
            operation: Operation type
            step: Initial step
            data: Initial data
            
        Returns:
            Created UserSession
        """
        session = UserSession(
            user_id=user_id,
            operation=operation,
            step=step,
            data=data or {}
        )
        self.user_sessions[user_id] = session
        self.logger.debug(f"Created session for user {user_id}: {operation}")
        return session
    
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """Get user session by user ID"""
        return self.user_sessions.get(user_id)
    
    def update_user_session(
        self,
        user_id: int,
        step: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        progress_msg_id: Optional[int] = None
    ) -> Optional[UserSession]:
        """
        Update user session
        
        Args:
            user_id: User ID
            step: New step (optional)
            data: Data to merge (optional)
            progress_msg_id: Progress message ID (optional)
            
        Returns:
            Updated UserSession or None if not found
        """
        session = self.user_sessions.get(user_id)
        if not session:
            return None
        
        if step is not None:
            session.step = step
        
        if data is not None:
            session.data.update(data)
        
        if progress_msg_id is not None:
            session.progress_msg_id = progress_msg_id
        
        return session
    
    def delete_user_session(self, user_id: int) -> bool:
        """
        Delete user session
        
        Args:
            user_id: User ID
            
        Returns:
            True if session was deleted, False if not found
        """
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            self.logger.debug(f"Deleted session for user {user_id}")
            return True
        return False
    
    def clear_all_user_sessions(self) -> int:
        """
        Clear all user sessions
        
        Returns:
            Number of sessions cleared
        """
        count = len(self.user_sessions)
        self.user_sessions.clear()
        self.logger.info(f"Cleared {count} user sessions")
        return count
    
    # Operation Progress Management
    
    def create_operation_progress(
        self,
        operation_id: str,
        operation_type: str,
        total: int,
        user_id: Optional[int] = None,
        message_id: Optional[int] = None
    ) -> OperationProgress:
        """
        Create operation progress tracker
        
        Args:
            operation_id: Unique operation ID
            operation_type: Type of operation
            total: Total items to process
            user_id: User who initiated operation
            message_id: Message ID for updates
            
        Returns:
            Created OperationProgress
        """
        progress = OperationProgress(
            operation_id=operation_id,
            operation_type=operation_type,
            total=total,
            user_id=user_id,
            message_id=message_id
        )
        self.operation_progress[operation_id] = progress
        self.logger.debug(f"Created progress tracker for operation {operation_id}")
        return progress
    
    def get_operation_progress(self, operation_id: str) -> Optional[OperationProgress]:
        """Get operation progress by ID"""
        return self.operation_progress.get(operation_id)
    
    def update_operation_progress(
        self,
        operation_id: str,
        completed: Optional[int] = None,
        failed: Optional[int] = None,
        increment_completed: bool = False,
        increment_failed: bool = False
    ) -> Optional[OperationProgress]:
        """
        Update operation progress
        
        Args:
            operation_id: Operation ID
            completed: Set completed count (optional)
            failed: Set failed count (optional)
            increment_completed: Increment completed by 1
            increment_failed: Increment failed by 1
            
        Returns:
            Updated OperationProgress or None if not found
        """
        progress = self.operation_progress.get(operation_id)
        if not progress:
            return None
        
        if completed is not None:
            progress.completed = completed
        
        if failed is not None:
            progress.failed = failed
        
        if increment_completed:
            progress.increment_completed()
        
        if increment_failed:
            progress.increment_failed()
        
        return progress
    
    def delete_operation_progress(self, operation_id: str) -> bool:
        """
        Delete operation progress
        
        Args:
            operation_id: Operation ID
            
        Returns:
            True if deleted, False if not found
        """
        if operation_id in self.operation_progress:
            del self.operation_progress[operation_id]
            self.logger.debug(f"Deleted progress for operation {operation_id}")
            return True
        return False
    
    def get_user_operations(self, user_id: int) -> List[OperationProgress]:
        """
        Get all operations for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of OperationProgress for the user
        """
        return [
            progress for progress in self.operation_progress.values()
            if progress.user_id == user_id
        ]
    
    def get_active_operations(self) -> List[OperationProgress]:
        """
        Get all active operations
        
        Returns:
            List of active OperationProgress
        """
        return [
            progress for progress in self.operation_progress.values()
            if progress.status == 'running'
        ]
    
    # Monitoring Configuration Management
    
    def create_monitoring_config(
        self,
        chat_id: str,
        reactions: Optional[List[Dict[str, Any]]] = None,
        cooldown: float = 1.0,
        enabled: bool = True
    ) -> MonitoringConfig:
        """
        Create monitoring configuration
        
        Args:
            chat_id: Channel chat ID or username
            reactions: List of reaction configs
            cooldown: Cooldown in seconds
            enabled: Whether enabled
            
        Returns:
            Created MonitoringConfig
        """
        config = MonitoringConfig(
            chat_id=chat_id,
            reactions=reactions or [],
            cooldown=cooldown,
            enabled=enabled
        )
        self.monitoring_configs[chat_id] = config
        self.logger.debug(f"Created monitoring config for {chat_id}")
        return config
    
    def get_monitoring_config(self, chat_id: str) -> Optional[MonitoringConfig]:
        """Get monitoring configuration by chat ID"""
        return self.monitoring_configs.get(chat_id)
    
    def update_monitoring_config(
        self,
        chat_id: str,
        reactions: Optional[List[Dict[str, Any]]] = None,
        cooldown: Optional[float] = None,
        enabled: Optional[bool] = None
    ) -> Optional[MonitoringConfig]:
        """
        Update monitoring configuration
        
        Args:
            chat_id: Channel chat ID
            reactions: New reactions list (optional)
            cooldown: New cooldown (optional)
            enabled: New enabled status (optional)
            
        Returns:
            Updated MonitoringConfig or None if not found
        """
        config = self.monitoring_configs.get(chat_id)
        if not config:
            return None
        
        if reactions is not None:
            config.reactions = reactions
        
        if cooldown is not None:
            config.cooldown = cooldown
        
        if enabled is not None:
            config.enabled = enabled
        
        return config
    
    def delete_monitoring_config(self, chat_id: str) -> bool:
        """
        Delete monitoring configuration
        
        Args:
            chat_id: Channel chat ID
            
        Returns:
            True if deleted, False if not found
        """
        if chat_id in self.monitoring_configs:
            del self.monitoring_configs[chat_id]
            self.logger.debug(f"Deleted monitoring config for {chat_id}")
            return True
        return False
    
    def get_all_monitoring_configs(self) -> List[MonitoringConfig]:
        """Get all monitoring configurations"""
        return list(self.monitoring_configs.values())
    
    def get_enabled_monitoring_configs(self) -> List[MonitoringConfig]:
        """Get all enabled monitoring configurations"""
        return [
            config for config in self.monitoring_configs.values()
            if config.enabled
        ]
    
    # Cleanup and Maintenance
    
    async def start_cleanup_task(self) -> None:
        """Start automatic cleanup task"""
        if self._cleanup_task is not None:
            self.logger.warning("Cleanup task already running")
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Started cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop automatic cleanup task"""
        if self._cleanup_task is None:
            return
        
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        
        self._cleanup_task = None
        self.logger.info("Stopped cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """Cleanup loop that runs periodically"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
                await self.cleanup_completed_operations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired user sessions
        
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        expired_users = []
        
        for user_id, session in self.user_sessions.items():
            if current_time - session.started_at > self.session_timeout:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_sessions[user_id]
        
        if expired_users:
            self.logger.info(f"Cleaned up {len(expired_users)} expired sessions")
        
        return len(expired_users)
    
    async def cleanup_completed_operations(self, max_age: int = 3600) -> int:
        """
        Clean up completed operations older than max_age
        
        Args:
            max_age: Maximum age in seconds (default: 1 hour)
            
        Returns:
            Number of operations cleaned up
        """
        current_time = time.time()
        completed_ops = []
        
        for op_id, progress in self.operation_progress.items():
            if progress.status in ('completed', 'failed', 'cancelled'):
                if current_time - progress.started_at > max_age:
                    completed_ops.append(op_id)
        
        for op_id in completed_ops:
            del self.operation_progress[op_id]
        
        if completed_ops:
            self.logger.info(f"Cleaned up {len(completed_ops)} completed operations")
        
        return len(completed_ops)
    
    # Statistics
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get state manager statistics
        
        Returns:
            Dictionary with statistics
        """
        active_ops = self.get_active_operations()
        
        return {
            'user_sessions': len(self.user_sessions),
            'total_operations': len(self.operation_progress),
            'active_operations': len(active_ops),
            'monitoring_configs': len(self.monitoring_configs),
            'enabled_monitoring': len(self.get_enabled_monitoring_configs()),
            'operations_by_type': self._count_operations_by_type(),
            'sessions_by_operation': self._count_sessions_by_operation()
        }
    
    def _count_operations_by_type(self) -> Dict[str, int]:
        """Count operations by type"""
        counts: Dict[str, int] = {}
        for progress in self.operation_progress.values():
            counts[progress.operation_type] = counts.get(progress.operation_type, 0) + 1
        return counts
    
    def _count_sessions_by_operation(self) -> Dict[str, int]:
        """Count sessions by operation"""
        counts: Dict[str, int] = {}
        for session in self.user_sessions.values():
            counts[session.operation] = counts.get(session.operation, 0) + 1
        return counts
