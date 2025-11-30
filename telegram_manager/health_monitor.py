"""
SessionHealthMonitor - Monitors session health and handles reconnection
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set, List, Callable
from dataclasses import dataclass, field


@dataclass
class SessionHealthStatus:
    """Health status for a session"""
    session_name: str
    is_healthy: bool
    last_check_time: float
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    reconnection_attempts: int = 0
    last_reconnection_time: Optional[float] = None


class SessionHealthMonitor:
    """
    Monitors session health and handles automatic reconnection
    
    Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 23.1, 23.2, 23.3, 23.4, 23.5
    """
    
    # Health check interval (30 seconds per requirement 16.1)
    CHECK_INTERVAL = 30.0
    
    # Maximum reconnection attempts (5 per requirement 16.3)
    MAX_RECONNECT_ATTEMPTS = 5
    
    # Exponential backoff base for reconnection (2.0 seconds)
    RECONNECT_BACKOFF_BASE = 2.0
    
    def __init__(self):
        """Initialize session health monitor"""
        self.logger = logging.getLogger("SessionHealthMonitor")
        
        # Session health tracking
        self.session_health: Dict[str, SessionHealthStatus] = {}
        
        # Monitoring control
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Sessions being monitored
        self.sessions: Dict[str, any] = {}  # Will store TelegramSession objects
        
        # Lock for thread-safe operations
        self.health_lock = asyncio.Lock()
        
        # Reconnection tracking
        self.reconnecting_sessions: Set[str] = set()
        
        # Session failure tracking (Requirement 23.2)
        self.failed_sessions: Set[str] = set()
        
        # Callback for session failure events (Requirement 23.1)
        self.failure_callback: Optional[Callable] = None
        
        # Callback for session recovery events (Requirement 23.3)
        self.recovery_callback: Optional[Callable] = None
    
    async def start_monitoring(self, sessions: Dict[str, any], failure_callback: Optional[Callable] = None, recovery_callback: Optional[Callable] = None):
        """
        Start monitoring session health
        
        Args:
            sessions: Dict mapping session names to TelegramSession objects
            failure_callback: Optional callback for session failure events (Requirement 23.1)
            recovery_callback: Optional callback for session recovery events (Requirement 23.3)
            
        Requirements: 16.1, 16.2, 23.1, 23.3
        """
        if self.is_monitoring:
            self.logger.warning("⚠️ Health monitoring is already running")
            return
        
        self.sessions = sessions
        self.is_monitoring = True
        self.failure_callback = failure_callback
        self.recovery_callback = recovery_callback
        
        # Initialize health status for all sessions
        async with self.health_lock:
            for session_name in sessions.keys():
                if session_name not in self.session_health:
                    self.session_health[session_name] = SessionHealthStatus(
                        session_name=session_name,
                        is_healthy=True,
                        last_check_time=time.time()
                    )
        
        # Start background monitoring task
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(
            f"✅ Started health monitoring for {len(sessions)} sessions "
            f"(check interval: {self.CHECK_INTERVAL}s)"
        )
    
    async def stop_monitoring(self):
        """
        Stop monitoring session health
        
        Requirements: 16.2
        """
        if not self.is_monitoring:
            self.logger.debug("Health monitoring is not running")
            return
        
        self.logger.info("🛑 Stopping health monitoring...")
        
        # Signal monitoring to stop
        self.is_monitoring = False
        
        # Cancel monitoring task
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await asyncio.wait_for(self.monitor_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                self.logger.warning("⏱️ Monitoring task did not stop cleanly within 5 seconds")
        
        self.monitor_task = None
        self.logger.info("✅ Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """
        Background loop that periodically checks session health
        
        Requirements: 16.1
        """
        self.logger.debug("🔄 Health monitoring loop started")
        
        while self.is_monitoring:
            try:
                # Check health of all sessions
                await self._check_all_sessions()
                
                # Wait for next check interval
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                self.logger.debug("Health monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"❌ Error in health monitoring loop: {e}")
                # Continue monitoring despite errors
                await asyncio.sleep(self.CHECK_INTERVAL)
        
        self.logger.debug("🛑 Health monitoring loop stopped")
    
    async def _check_all_sessions(self):
        """
        Check health of all monitored sessions
        
        Requirements: 16.1
        """
        check_tasks = []
        
        for session_name in list(self.sessions.keys()):
            task = asyncio.create_task(
                self._check_and_handle_session(session_name)
            )
            check_tasks.append(task)
        
        # Wait for all checks to complete
        if check_tasks:
            await asyncio.gather(*check_tasks, return_exceptions=True)
    
    async def _check_and_handle_session(self, session_name: str):
        """
        Check a single session and handle disconnection if needed
        
        Args:
            session_name: Name of the session to check
            
        Requirements: 16.1, 16.2
        """
        try:
            # Skip if already reconnecting
            if session_name in self.reconnecting_sessions:
                self.logger.debug(f"Skipping health check for {session_name} - already reconnecting")
                return
            
            # Check session health
            is_healthy = await self.check_session_health(session_name)
            
            # Update health status
            async with self.health_lock:
                if session_name in self.session_health:
                    status = self.session_health[session_name]
                    status.last_check_time = time.time()
                    
                    if is_healthy:
                        # Session is healthy
                        if not status.is_healthy:
                            # Session recovered - enhanced logging (Requirement 16.2)
                            self.logger.info(
                                f"✅ Session {session_name} is now healthy "
                                f"(was unhealthy for {status.consecutive_failures} checks)",
                                extra={
                                    'operation_type': 'session_health_recovery',
                                    'session_name': session_name,
                                    'previous_consecutive_failures': status.consecutive_failures,
                                    'last_error': status.last_error,
                                    'recovery_time': time.time()
                                }
                            )
                        status.is_healthy = True
                        status.consecutive_failures = 0
                        status.last_error = None
                    else:
                        # Session is unhealthy
                        status.is_healthy = False
                        status.consecutive_failures += 1
                        
                        # Enhanced logging for health check failures (Requirement 16.1)
                        self.logger.warning(
                            f"⚠️ Session {session_name} health check failed "
                            f"(consecutive failures: {status.consecutive_failures})",
                            extra={
                                'operation_type': 'session_health_check_failed',
                                'session_name': session_name,
                                'consecutive_failures': status.consecutive_failures,
                                'last_error': status.last_error,
                                'check_time': time.time()
                            }
                        )
                        
                        # Handle disconnection (only if not already reconnecting)
                        if session_name not in self.reconnecting_sessions:
                            await self.handle_disconnection(session_name)
            
        except Exception as e:
            self.logger.error(f"❌ Error checking session {session_name}: {e}")
    
    async def check_session_health(self, session_name: str) -> bool:
        """
        Check if a session is healthy (connected and responsive)
        
        Args:
            session_name: Name of the session to check
            
        Returns:
            True if session is healthy, False otherwise
            
        Requirements: 16.1
        """
        if session_name not in self.sessions:
            self.logger.warning(f"⚠️ Session {session_name} not found in monitored sessions")
            return False
        
        session = self.sessions[session_name]
        
        try:
            # Check if session is connected
            if not session.is_connected:
                self.logger.debug(f"Session {session_name} is not connected")
                return False
            
            # Check if client exists and is connected
            if not session.client or not session.client.is_connected():
                self.logger.debug(f"Session {session_name} client is not connected")
                return False
            
            # Try a simple operation to verify session is responsive
            # Use a timeout to avoid hanging
            try:
                # Get "me" is a lightweight operation to verify connectivity
                await asyncio.wait_for(
                    session.client.get_me(),
                    timeout=10.0
                )
                return True
            except asyncio.TimeoutError:
                self.logger.warning(f"⏱️ Session {session_name} health check timed out")
                return False
            except Exception as e:
                self.logger.warning(f"⚠️ Session {session_name} health check failed: {e}")
                
                # Update error in health status
                async with self.health_lock:
                    if session_name in self.session_health:
                        self.session_health[session_name].last_error = str(e)
                
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error checking health of session {session_name}: {e}")
            return False
    
    def is_session_healthy(self, session_name: str) -> bool:
        """
        Query if a session is currently healthy (synchronous)
        
        Args:
            session_name: Name of the session to query
            
        Returns:
            True if session is healthy, False otherwise
            
        Requirements: 16.1
        """
        if session_name not in self.session_health:
            return False
        
        return self.session_health[session_name].is_healthy
    
    async def handle_disconnection(self, session_name: str):
        """
        Handle session disconnection by attempting reconnection
        
        Args:
            session_name: Name of the disconnected session
            
        Requirements: 16.2, 16.3, 16.4, 16.5, 23.1, 23.2, 23.3
        """
        # Check if already reconnecting
        if session_name in self.reconnecting_sessions:
            self.logger.debug(f"Session {session_name} is already being reconnected")
            return
        
        # Mark as reconnecting
        self.reconnecting_sessions.add(session_name)
        
        try:
            # Enhanced logging for disconnection handling (Requirement 16.2)
            self.logger.warning(
                f"🔄 Handling disconnection for session {session_name}",
                extra={
                    'operation_type': 'session_disconnection_handling',
                    'session_name': session_name,
                    'max_reconnect_attempts': self.MAX_RECONNECT_ATTEMPTS,
                    'backoff_base': self.RECONNECT_BACKOFF_BASE
                }
            )
            
            # Attempt reconnection
            success = await self.reconnect_session(session_name)
            
            if success:
                # Enhanced logging for successful reconnection (Requirement 16.4)
                self.logger.info(
                    f"✅ Successfully reconnected session {session_name}",
                    extra={
                        'operation_type': 'session_reconnection_success',
                        'session_name': session_name,
                        'reconnection_time': time.time()
                    }
                )
                
                # Update health status
                async with self.health_lock:
                    if session_name in self.session_health:
                        status = self.session_health[session_name]
                        status.is_healthy = True
                        status.consecutive_failures = 0
                        status.reconnection_attempts = 0
                        status.last_error = None
                
                # Mark session as recovered (Requirement 23.3)
                await self.mark_session_as_recovered(session_name)
            else:
                # Enhanced logging for failed reconnection (Requirement 16.5)
                self.logger.error(
                    f"❌ Failed to reconnect session {session_name} "
                    f"after {self.MAX_RECONNECT_ATTEMPTS} attempts",
                    extra={
                        'operation_type': 'session_reconnection_failed',
                        'session_name': session_name,
                        'max_attempts': self.MAX_RECONNECT_ATTEMPTS,
                        'failure_time': time.time()
                    }
                )
                
                # Update health status
                async with self.health_lock:
                    if session_name in self.session_health:
                        status = self.session_health[session_name]
                        status.is_healthy = False
                        status.last_error = "Max reconnection attempts exhausted"
                
                # Mark session as failed (Requirement 23.2)
                await self.mark_session_as_failed(session_name)
        
        finally:
            # Remove from reconnecting set
            self.reconnecting_sessions.discard(session_name)
    
    async def reconnect_session(self, session_name: str) -> bool:
        """
        Attempt to reconnect a session with exponential backoff
        
        Args:
            session_name: Name of the session to reconnect
            
        Returns:
            True if reconnection successful, False otherwise
            
        Requirements: 16.3, 16.4, 16.5
        """
        if session_name not in self.sessions:
            self.logger.error(f"❌ Session {session_name} not found")
            return False
        
        session = self.sessions[session_name]
        
        # Try reconnection with exponential backoff
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            try:
                # Enhanced logging for reconnection attempts (Requirement 16.3, 5.5)
                self.logger.info(
                    f"🔄 Reconnection attempt {attempt}/{self.MAX_RECONNECT_ATTEMPTS} "
                    f"for session {session_name}",
                    extra={
                        'operation_type': 'session_reconnection_attempt',
                        'session_name': session_name,
                        'attempt_number': attempt,
                        'max_attempts': self.MAX_RECONNECT_ATTEMPTS,
                        'attempt_time': time.time()
                    }
                )
                
                # Update reconnection tracking
                async with self.health_lock:
                    if session_name in self.session_health:
                        status = self.session_health[session_name]
                        status.reconnection_attempts = attempt
                        status.last_reconnection_time = time.time()
                
                # Disconnect first if still connected
                try:
                    if session.client and session.client.is_connected():
                        await asyncio.wait_for(
                            session.client.disconnect(),
                            timeout=5.0
                        )
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    self.logger.debug(f"Disconnect timed out for session {session_name}")
                except Exception as e:
                    self.logger.debug(f"Error during disconnect: {e}")
                
                # Attempt to reconnect
                success = await session.connect()
                
                if success:
                    # Enhanced logging for successful reconnection attempt (Requirement 16.3, 5.5)
                    self.logger.info(
                        f"✅ Session {session_name} reconnected successfully "
                        f"on attempt {attempt}",
                        extra={
                            'operation_type': 'session_reconnection_attempt_success',
                            'session_name': session_name,
                            'successful_attempt': attempt,
                            'max_attempts': self.MAX_RECONNECT_ATTEMPTS,
                            'success_time': time.time()
                        }
                    )
                    return True
                else:
                    self.logger.warning(
                        f"⚠️ Reconnection attempt {attempt} failed for session {session_name}"
                    )
                    
                    # Update error in health status when connection returns False
                    async with self.health_lock:
                        if session_name in self.session_health:
                            self.session_health[session_name].last_error = "Connection attempt returned False"
                
            except Exception as e:
                self.logger.error(
                    f"❌ Reconnection attempt {attempt} failed for session {session_name}: {e}"
                )
                
                # Update error in health status
                async with self.health_lock:
                    if session_name in self.session_health:
                        self.session_health[session_name].last_error = str(e)
            
            # If not the last attempt, wait with exponential backoff
            if attempt < self.MAX_RECONNECT_ATTEMPTS:
                backoff_delay = self.RECONNECT_BACKOFF_BASE ** attempt
                # Enhanced logging for backoff delays (Requirement 5.5, 3.5)
                self.logger.info(
                    f"⏳ Waiting {backoff_delay}s before next reconnection attempt "
                    f"for session {session_name}",
                    extra={
                        'operation_type': 'session_reconnection_backoff',
                        'session_name': session_name,
                        'backoff_delay_seconds': backoff_delay,
                        'backoff_base': self.RECONNECT_BACKOFF_BASE,
                        'attempt_number': attempt,
                        'next_attempt': attempt + 1
                    }
                )
                await asyncio.sleep(backoff_delay)
        
        # All attempts failed
        self.logger.error(
            f"❌ Failed to reconnect session {session_name} "
            f"after {self.MAX_RECONNECT_ATTEMPTS} attempts"
        )
        return False
    
    def get_health_status(self, session_name: str) -> Optional[SessionHealthStatus]:
        """
        Get health status for a session
        
        Args:
            session_name: Name of the session
            
        Returns:
            SessionHealthStatus or None if session not found
        """
        return self.session_health.get(session_name)
    
    def get_all_health_statuses(self) -> Dict[str, SessionHealthStatus]:
        """
        Get health statuses for all monitored sessions
        
        Returns:
            Dict mapping session names to health statuses
        """
        return self.session_health.copy()
    
    async def add_session(self, session_name: str, session: any):
        """
        Add a new session to monitoring
        
        Args:
            session_name: Name of the session
            session: TelegramSession object
        """
        async with self.health_lock:
            self.sessions[session_name] = session
            
            if session_name not in self.session_health:
                self.session_health[session_name] = SessionHealthStatus(
                    session_name=session_name,
                    is_healthy=True,
                    last_check_time=time.time()
                )
        
        self.logger.info(f"➕ Added session {session_name} to health monitoring")
    
    async def remove_session(self, session_name: str):
        """
        Remove a session from monitoring
        
        Args:
            session_name: Name of the session to remove
        """
        async with self.health_lock:
            self.sessions.pop(session_name, None)
            self.session_health.pop(session_name, None)
        
        self.reconnecting_sessions.discard(session_name)
        self.failed_sessions.discard(session_name)
        
        self.logger.info(f"➖ Removed session {session_name} from health monitoring")
    
    async def mark_session_as_failed(self, session_name: str):
        """
        Mark a session as failed and unavailable for operations
        
        This is called when a session fails and cannot be reconnected.
        The session will be excluded from load balancing until it recovers.
        
        Args:
            session_name: Name of the failed session
            
        Requirements: 23.2
        """
        async with self.health_lock:
            if session_name not in self.failed_sessions:
                self.failed_sessions.add(session_name)
                self.logger.warning(f"❌ Marked session {session_name} as FAILED")
                
                # Update health status
                if session_name in self.session_health:
                    self.session_health[session_name].is_healthy = False
                
                # Trigger failure callback if registered (Requirement 23.1)
                if self.failure_callback:
                    try:
                        await self.failure_callback(session_name)
                    except Exception as e:
                        self.logger.error(f"❌ Error in failure callback for {session_name}: {e}")
    
    async def mark_session_as_recovered(self, session_name: str):
        """
        Mark a session as recovered and available for operations
        
        This is called when a failed session successfully reconnects.
        The session will be reintegrated into the load balancer.
        
        Args:
            session_name: Name of the recovered session
            
        Requirements: 23.3
        """
        async with self.health_lock:
            was_failed = session_name in self.failed_sessions
            
            if was_failed:
                self.failed_sessions.remove(session_name)
                self.logger.info(f"✅ Marked session {session_name} as RECOVERED")
            
            # Update health status
            if session_name in self.session_health:
                self.session_health[session_name].is_healthy = True
                self.session_health[session_name].consecutive_failures = 0
                self.session_health[session_name].reconnection_attempts = 0
            
            # Trigger recovery callback if registered and session was previously failed (Requirement 23.3)
            if was_failed and self.recovery_callback:
                try:
                    await self.recovery_callback(session_name)
                except Exception as e:
                    self.logger.error(f"❌ Error in recovery callback for {session_name}: {e}")
    
    def is_session_failed(self, session_name: str) -> bool:
        """
        Check if a session is marked as failed
        
        Args:
            session_name: Name of the session to check
            
        Returns:
            True if session is failed, False otherwise
            
        Requirements: 23.2
        """
        return session_name in self.failed_sessions
    
    def get_available_sessions(self) -> List[str]:
        """
        Get list of available (not failed) session names
        
        Returns:
            List of session names that are not marked as failed
            
        Requirements: 23.2
        """
        return [name for name in self.sessions.keys() if name not in self.failed_sessions]
    
    def get_failed_sessions(self) -> List[str]:
        """
        Get list of failed session names
        
        Returns:
            List of session names that are marked as failed
            
        Requirements: 23.2
        """
        return list(self.failed_sessions)
