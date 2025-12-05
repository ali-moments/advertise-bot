"""
Rate Limiter for Telegram Bot Panel

This module provides rate limiting functionality to prevent abuse and
manage Telegram API rate limits effectively.

Requirements: AC-10.3 - Concurrent request handling with rate limiting
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from functools import wraps


@dataclass
class RateLimitBucket:
    """
    Token bucket for rate limiting
    
    Attributes:
        capacity: Maximum number of tokens
        tokens: Current number of tokens
        refill_rate: Tokens added per second
        last_refill: Last refill timestamp
        requests: Recent request timestamps (for tracking)
    """
    capacity: int
    tokens: float
    refill_rate: float
    last_refill: float = field(default_factory=time.time)
    requests: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self.refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            self.requests.append(time.time())
            return True
        
        return False
    
    def time_until_available(self, tokens: float = 1.0) -> float:
        """
        Calculate time until tokens are available
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time in seconds until tokens are available
        """
        self.refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate
    
    def get_request_rate(self, window: int = 60) -> float:
        """
        Get request rate over time window
        
        Args:
            window: Time window in seconds
            
        Returns:
            Requests per second
        """
        now = time.time()
        cutoff = now - window
        
        # Count requests in window
        recent_requests = [
            req_time for req_time in self.requests
            if req_time >= cutoff
        ]
        
        if not recent_requests:
            return 0.0
        
        return len(recent_requests) / window


class RateLimiter:
    """
    Rate limiter for bot operations
    
    Features:
    - Per-user rate limiting
    - Per-operation rate limiting
    - Token bucket algorithm
    - Automatic token refill
    - Rate limit statistics
    
    Requirements: AC-10.3
    """
    
    def __init__(self):
        """Initialize rate limiter"""
        self.logger = logging.getLogger("RateLimiter")
        
        # Rate limit buckets
        self._user_buckets: Dict[int, RateLimitBucket] = {}
        self._operation_buckets: Dict[str, RateLimitBucket] = {}
        self._global_bucket: Optional[RateLimitBucket] = None
        
        # Configuration
        self._user_limits = {
            'capacity': 10,  # 10 requests
            'refill_rate': 1.0  # 1 request per second
        }
        
        self._operation_limits = {
            'command': {'capacity': 30, 'refill_rate': 2.0},  # 2 commands/sec
            'button': {'capacity': 50, 'refill_rate': 5.0},  # 5 buttons/sec
            'progress': {'capacity': 10, 'refill_rate': 0.5},  # 1 update per 2 sec
            'message': {'capacity': 30, 'refill_rate': 1.0}  # 1 message/sec
        }
        
        # Telegram API limits
        self._telegram_limits = {
            'capacity': 30,  # 30 messages per second
            'refill_rate': 30.0  # 30 messages per second
        }
        
        # Initialize global bucket for Telegram API
        self._global_bucket = RateLimitBucket(
            capacity=self._telegram_limits['capacity'],
            tokens=self._telegram_limits['capacity'],
            refill_rate=self._telegram_limits['refill_rate']
        )
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'allowed_requests': 0,
            'blocked_requests': 0,
            'total_wait_time': 0.0
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger.info("RateLimiter initialized")
    
    def _get_user_bucket(self, user_id: int) -> RateLimitBucket:
        """
        Get or create rate limit bucket for user
        
        Args:
            user_id: User ID
            
        Returns:
            RateLimitBucket for the user
        """
        if user_id not in self._user_buckets:
            self._user_buckets[user_id] = RateLimitBucket(
                capacity=self._user_limits['capacity'],
                tokens=self._user_limits['capacity'],
                refill_rate=self._user_limits['refill_rate']
            )
        
        return self._user_buckets[user_id]
    
    def _get_operation_bucket(self, operation: str) -> Optional[RateLimitBucket]:
        """
        Get or create rate limit bucket for operation
        
        Args:
            operation: Operation type
            
        Returns:
            RateLimitBucket for the operation or None if no limit
        """
        if operation not in self._operation_limits:
            return None
        
        if operation not in self._operation_buckets:
            limits = self._operation_limits[operation]
            self._operation_buckets[operation] = RateLimitBucket(
                capacity=limits['capacity'],
                tokens=limits['capacity'],
                refill_rate=limits['refill_rate']
            )
        
        return self._operation_buckets[operation]
    
    async def check_rate_limit(
        self,
        user_id: int,
        operation: str = 'command',
        tokens: float = 1.0
    ) -> Tuple[bool, float]:
        """
        Check if request is allowed under rate limits
        
        Args:
            user_id: User ID
            operation: Operation type
            tokens: Number of tokens to consume
            
        Returns:
            Tuple of (allowed, wait_time)
            - allowed: True if request is allowed
            - wait_time: Time to wait in seconds if not allowed
        """
        async with self._lock:
            self._stats['total_requests'] += 1
            
            # Check user rate limit
            user_bucket = self._get_user_bucket(user_id)
            if not user_bucket.consume(tokens):
                wait_time = user_bucket.time_until_available(tokens)
                self._stats['blocked_requests'] += 1
                self.logger.debug(
                    f"User {user_id} rate limited, wait {wait_time:.2f}s"
                )
                return False, wait_time
            
            # Check operation rate limit
            operation_bucket = self._get_operation_bucket(operation)
            if operation_bucket and not operation_bucket.consume(tokens):
                wait_time = operation_bucket.time_until_available(tokens)
                self._stats['blocked_requests'] += 1
                self.logger.debug(
                    f"Operation '{operation}' rate limited, wait {wait_time:.2f}s"
                )
                return False, wait_time
            
            # Check global Telegram API limit
            if self._global_bucket and not self._global_bucket.consume(tokens):
                wait_time = self._global_bucket.time_until_available(tokens)
                self._stats['blocked_requests'] += 1
                self.logger.debug(
                    f"Global API rate limited, wait {wait_time:.2f}s"
                )
                return False, wait_time
            
            # Request allowed
            self._stats['allowed_requests'] += 1
            return True, 0.0
    
    async def wait_for_rate_limit(
        self,
        user_id: int,
        operation: str = 'command',
        tokens: float = 1.0,
        max_wait: float = 10.0
    ) -> bool:
        """
        Wait until rate limit allows request
        
        Args:
            user_id: User ID
            operation: Operation type
            tokens: Number of tokens to consume
            max_wait: Maximum time to wait in seconds
            
        Returns:
            True if request was allowed, False if max_wait exceeded
        """
        start_time = time.time()
        
        while True:
            allowed, wait_time = await self.check_rate_limit(
                user_id, operation, tokens
            )
            
            if allowed:
                return True
            
            # Check if we've exceeded max wait time
            elapsed = time.time() - start_time
            if elapsed + wait_time > max_wait:
                self.logger.warning(
                    f"Rate limit wait exceeded max_wait ({max_wait}s) "
                    f"for user {user_id}"
                )
                return False
            
            # Wait for tokens to be available
            self._stats['total_wait_time'] += wait_time
            await asyncio.sleep(wait_time)
    
    async def acquire(
        self,
        user_id: int,
        operation: str = 'command',
        tokens: float = 1.0,
        wait: bool = True,
        max_wait: float = 10.0
    ) -> bool:
        """
        Acquire rate limit permission
        
        Args:
            user_id: User ID
            operation: Operation type
            tokens: Number of tokens to consume
            wait: Whether to wait if rate limited
            max_wait: Maximum time to wait in seconds
            
        Returns:
            True if permission acquired, False otherwise
        """
        if wait:
            return await self.wait_for_rate_limit(
                user_id, operation, tokens, max_wait
            )
        else:
            allowed, _ = await self.check_rate_limit(user_id, operation, tokens)
            return allowed
    
    def get_user_rate(self, user_id: int, window: int = 60) -> float:
        """
        Get request rate for user
        
        Args:
            user_id: User ID
            window: Time window in seconds
            
        Returns:
            Requests per second
        """
        bucket = self._user_buckets.get(user_id)
        if bucket is None:
            return 0.0
        
        return bucket.get_request_rate(window)
    
    def get_operation_rate(self, operation: str, window: int = 60) -> float:
        """
        Get request rate for operation
        
        Args:
            operation: Operation type
            window: Time window in seconds
            
        Returns:
            Requests per second
        """
        bucket = self._operation_buckets.get(operation)
        if bucket is None:
            return 0.0
        
        return bucket.get_request_rate(window)
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get rate limiter statistics
        
        Returns:
            Dictionary with statistics
        """
        total_requests = self._stats['total_requests']
        allowed_rate = (
            (self._stats['allowed_requests'] / total_requests * 100)
            if total_requests > 0 else 0.0
        )
        
        avg_wait_time = (
            (self._stats['total_wait_time'] / self._stats['blocked_requests'])
            if self._stats['blocked_requests'] > 0 else 0.0
        )
        
        return {
            'total_requests': total_requests,
            'allowed_requests': self._stats['allowed_requests'],
            'blocked_requests': self._stats['blocked_requests'],
            'allowed_rate': allowed_rate,
            'total_wait_time': self._stats['total_wait_time'],
            'avg_wait_time': avg_wait_time,
            'active_users': len(self._user_buckets),
            'active_operations': len(self._operation_buckets)
        }
    
    def reset_stats(self) -> None:
        """Reset rate limiter statistics"""
        self._stats = {
            'total_requests': 0,
            'allowed_requests': 0,
            'blocked_requests': 0,
            'total_wait_time': 0.0
        }
        self.logger.info("Rate limiter statistics reset")
    
    async def cleanup_inactive_buckets(self, inactive_time: int = 3600) -> int:
        """
        Clean up inactive user buckets
        
        Args:
            inactive_time: Time in seconds to consider bucket inactive
            
        Returns:
            Number of buckets cleaned up
        """
        current_time = time.time()
        count = 0
        
        async with self._lock:
            # Find inactive user buckets
            inactive_users = [
                user_id for user_id, bucket in self._user_buckets.items()
                if bucket.requests and
                current_time - bucket.requests[-1] > inactive_time
            ]
            
            # Remove inactive buckets
            for user_id in inactive_users:
                del self._user_buckets[user_id]
                count += 1
        
        if count > 0:
            self.logger.debug(f"Cleaned up {count} inactive user buckets")
        
        return count


def rate_limited(
    operation: str = 'command',
    tokens: float = 1.0,
    wait: bool = True,
    max_wait: float = 10.0
):
    """
    Decorator for rate limiting function calls
    
    Args:
        operation: Operation type
        tokens: Number of tokens to consume
        wait: Whether to wait if rate limited
        max_wait: Maximum time to wait in seconds
        
    Example:
        @rate_limited('command', tokens=1.0, wait=True)
        async def handle_command(self, update, context):
            # Command handler code
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, *args, **kwargs):
            # Get rate limiter from self
            rate_limiter = getattr(self, 'rate_limiter', None)
            if rate_limiter is None:
                # No rate limiter, call function directly
                return await func(self, update, *args, **kwargs)
            
            # Get user ID
            user_id = update.effective_user.id if update.effective_user else 0
            
            # Acquire rate limit permission
            allowed = await rate_limiter.acquire(
                user_id, operation, tokens, wait, max_wait
            )
            
            if not allowed:
                # Rate limited
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(
                        "⚠️ لطفاً کمی صبر کنید",
                        show_alert=True
                    )
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(
                        "⚠️ تعداد درخواست‌های شما زیاد است. لطفاً کمی صبر کنید."
                    )
                return None
            
            # Call function
            return await func(self, update, *args, **kwargs)
        
        return wrapper
    return decorator


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance
    
    Returns:
        Global RateLimiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    
    return _global_rate_limiter


def set_rate_limiter(rate_limiter: RateLimiter) -> None:
    """
    Set global rate limiter instance
    
    Args:
        rate_limiter: RateLimiter instance to set as global
    """
    global _global_rate_limiter
    _global_rate_limiter = rate_limiter
