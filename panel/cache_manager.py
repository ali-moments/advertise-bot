"""
Cache Manager for Telegram Bot Panel

This module provides caching functionality for frequently accessed data
to optimize response times and reduce load on the backend system.

Requirements: AC-10.1 - Response time optimization through caching
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import json


T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """
    Cache entry with value and metadata
    
    Attributes:
        value: Cached value
        created_at: Timestamp when entry was created
        expires_at: Timestamp when entry expires
        hits: Number of cache hits
        last_accessed: Last access timestamp
    """
    value: T
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at
    
    def access(self) -> T:
        """Access the cached value and update metadata"""
        self.hits += 1
        self.last_accessed = time.time()
        return self.value
    
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds"""
        return time.time() - self.created_at


class CacheManager:
    """
    Cache manager for frequently accessed data
    
    Features:
    - TTL-based expiration
    - LRU eviction when cache is full
    - Automatic cleanup of expired entries
    - Cache statistics tracking
    - Thread-safe operations
    
    Requirements: AC-10.1
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        cleanup_interval: int = 60
    ):
        """
        Initialize cache manager
        
        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default TTL in seconds (0 = no expiration)
            cleanup_interval: Cleanup interval in seconds
        """
        self.logger = logging.getLogger("CacheManager")
        
        # Cache storage
        self._cache: Dict[str, CacheEntry] = {}
        
        # Configuration
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'invalidations': 0
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger.info(
            f"CacheManager initialized: max_size={max_size}, "
            f"default_ttl={default_ttl}s, cleanup_interval={cleanup_interval}s"
        )
    
    def _make_key(self, namespace: str, key: str) -> str:
        """
        Create cache key from namespace and key
        
        Args:
            namespace: Cache namespace
            key: Cache key
            
        Returns:
            Combined cache key
        """
        return f"{namespace}:{key}"
    
    def _hash_key(self, data: Any) -> str:
        """
        Create hash key from data
        
        Args:
            data: Data to hash
            
        Returns:
            Hash string
        """
        # Convert data to JSON string and hash it
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    async def get(
        self,
        namespace: str,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """
        Get value from cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        cache_key = self._make_key(namespace, key)
        
        async with self._lock:
            entry = self._cache.get(cache_key)
            
            if entry is None:
                self._stats['misses'] += 1
                return default
            
            if entry.is_expired():
                # Remove expired entry
                del self._cache[cache_key]
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return default
            
            # Cache hit
            self._stats['hits'] += 1
            return entry.access()
    
    async def set(
        self,
        namespace: str,
        key: str,
        value: T,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set value in cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default, 0 = no expiration)
        """
        cache_key = self._make_key(namespace, key)
        
        # Calculate expiration time
        if ttl is None:
            ttl = self.default_ttl
        
        expires_at = time.time() + ttl if ttl > 0 else 0.0
        
        async with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self.max_size and cache_key not in self._cache:
                await self._evict_lru()
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                expires_at=expires_at
            )
            
            self._cache[cache_key] = entry
    
    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        cache_key = self._make_key(namespace, key)
        
        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._stats['invalidations'] += 1
                return True
            return False
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all entries in a namespace
        
        Args:
            namespace: Cache namespace
            
        Returns:
            Number of entries invalidated
        """
        prefix = f"{namespace}:"
        count = 0
        
        async with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(prefix)
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
            
            self._stats['invalidations'] += count
        
        if count > 0:
            self.logger.debug(f"Invalidated {count} entries in namespace '{namespace}'")
        
        return count
    
    async def clear(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats['invalidations'] += count
        
        self.logger.info(f"Cleared {count} cache entries")
        return count
    
    async def _evict_lru(self) -> None:
        """
        Evict least recently used entry
        
        This is called when cache is full and we need to make space.
        """
        if not self._cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        
        del self._cache[lru_key]
        self._stats['evictions'] += 1
        
        self.logger.debug(f"Evicted LRU entry: {lru_key}")
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries
        
        Returns:
            Number of entries cleaned up
        """
        current_time = time.time()
        count = 0
        
        async with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.expires_at > 0 and current_time > entry.expires_at
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
            
            self._stats['expirations'] += count
        
        if count > 0:
            self.logger.debug(f"Cleaned up {count} expired cache entries")
        
        return count
    
    async def start_cleanup_task(self) -> None:
        """Start automatic cleanup task"""
        if self._cleanup_task is not None:
            self.logger.warning("Cleanup task already running")
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Started cache cleanup task")
    
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
        self.logger.info("Stopped cache cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """Cleanup loop that runs periodically"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (
            (self._stats['hits'] / total_requests * 100)
            if total_requests > 0 else 0.0
        )
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self._stats['evictions'],
            'expirations': self._stats['expirations'],
            'invalidations': self._stats['invalidations'],
            'total_requests': total_requests
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics"""
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'invalidations': 0
        }
        self.logger.info("Cache statistics reset")


def cached(
    namespace: str,
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results
    
    Args:
        namespace: Cache namespace
        ttl: TTL in seconds (None = use default)
        key_func: Function to generate cache key from args/kwargs
        
    Example:
        @cached('sessions', ttl=60)
        async def get_session_list():
            # Expensive operation
            return sessions
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get cache manager from self
            cache_manager = getattr(self, 'cache_manager', None)
            if cache_manager is None:
                # No cache manager, call function directly
                return await func(self, *args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash args and kwargs
                cache_key = cache_manager._hash_key((args, kwargs))
            
            # Try to get from cache
            cached_value = await cache_manager.get(namespace, cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(self, *args, **kwargs)
            
            # Store in cache
            await cache_manager.set(namespace, cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """
    Get global cache manager instance
    
    Returns:
        Global CacheManager instance
    """
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    
    return _global_cache_manager


def set_cache_manager(cache_manager: CacheManager) -> None:
    """
    Set global cache manager instance
    
    Args:
        cache_manager: CacheManager instance to set as global
    """
    global _global_cache_manager
    _global_cache_manager = cache_manager
