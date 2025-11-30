"""
Blacklist Management Module

This module provides persistent blacklist management for users who have blocked
the system's Telegram sessions. It automatically detects blocks after consecutive
delivery failures and maintains a persistent storage of blacklisted users.

Key Features:
- Persistent JSON-based storage with versioning
- Thread-safe operations using asyncio locks
- Automatic error handling with in-memory fallback
- Graceful handling of corrupted storage files
- Support for manual blacklist management

Classes:
    BlocklistManager: Main class for managing the blacklist

Usage:
    manager = BlocklistManager(storage_path='sessions/blacklist.json')
    await manager.load()
    
    # Check if user is blacklisted
    is_blocked = await manager.is_blacklisted('user123')
    
    # Add user to blacklist
    await manager.add('user123', reason='block_detected', session_name='+1234567890')
    
    # Remove user from blacklist
    removed = await manager.remove('user123')
    
    # Get all entries
    entries = await manager.get_all()
    
    # Clear blacklist
    count = await manager.clear()
"""

import json
import asyncio
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from telegram_manager.models import BlacklistEntry

logger = logging.getLogger(__name__)


class BlocklistManager:
    """
    Manages persistent blacklist of users who have blocked the system.
    
    This class provides thread-safe operations for managing a blacklist of users
    who have blocked the system's Telegram sessions. The blacklist is persisted
    to a JSON file and automatically loaded on initialization.
    
    Features:
    - Persistent JSON storage with atomic writes
    - Thread-safe operations using asyncio locks
    - Automatic error handling with in-memory fallback
    - Graceful handling of corrupted storage files
    - Version-aware storage format
    
    Storage Format:
        {
            "version": "1.0",
            "entries": {
                "user123": {
                    "user_id": "user123",
                    "timestamp": 1701360000.0,
                    "reason": "block_detected",
                    "session_name": "+1234567890"
                }
            }
        }
    
    Thread Safety:
        All public methods are thread-safe and can be called concurrently.
        Internal locking ensures data consistency.
    
    Error Handling:
        - If storage fails to load, starts with empty in-memory blacklist
        - If storage fails to write, maintains in-memory state and retries
        - Never blocks operations due to storage failures
    
    Attributes:
        STORAGE_VERSION (str): Current storage format version
        storage_path (str): Path to the blacklist storage file
    
    Example:
        >>> manager = BlocklistManager()
        >>> await manager.load()
        >>> await manager.add('user123', reason='block_detected')
        >>> is_blocked = await manager.is_blacklisted('user123')
        >>> print(is_blocked)  # True
    """
    
    STORAGE_VERSION = "1.0"
    
    def __init__(self, storage_path: str = 'sessions/blacklist.json'):
        """
        Initialize blacklist manager.
        
        Creates a new blacklist manager with the specified storage path.
        The blacklist is not loaded until load() is called.
        
        Args:
            storage_path: Path to blacklist storage file. Defaults to
                'sessions/blacklist.json'. The directory will be created
                automatically if it doesn't exist.
        
        Note:
            Call load() after initialization to load existing blacklist data.
        """
        self.storage_path = storage_path
        self._blacklist: Dict[str, BlacklistEntry] = {}
        self._lock = asyncio.Lock()
        self._storage_available = True
    
    async def load(self) -> None:
        """
        Load blacklist from persistent storage.
        
        Reads the blacklist from the storage file and populates the in-memory
        blacklist. If the file doesn't exist, starts with an empty blacklist.
        If the file is corrupted, logs an error and starts with an empty
        in-memory blacklist.
        
        This method should be called once during system initialization, typically
        in TelegramSessionManager.load_sessions_from_db().
        
        Raises:
            No exceptions are raised. All errors are logged and handled gracefully.
        
        Side Effects:
            - Populates self._blacklist with entries from storage
            - Sets self._storage_available based on load success
            - Logs information about loaded entries or errors
        
        Example:
            >>> manager = BlocklistManager()
            >>> await manager.load()
            >>> # Blacklist is now loaded and ready to use
        """
        async with self._lock:
            try:
                path = Path(self.storage_path)
                
                # If file doesn't exist, start with empty blacklist
                if not path.exists():
                    logger.info(f"Blacklist file not found at {self.storage_path}, starting with empty blacklist")
                    self._blacklist = {}
                    self._storage_available = True
                    return
                
                # Read and parse JSON
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate version
                version = data.get('version', '1.0')
                if version != self.STORAGE_VERSION:
                    logger.warning(f"Blacklist version mismatch: expected {self.STORAGE_VERSION}, got {version}")
                
                # Load entries
                entries = data.get('entries', {})
                self._blacklist = {}
                
                for user_id, entry_data in entries.items():
                    try:
                        entry = BlacklistEntry(
                            user_id=entry_data['user_id'],
                            timestamp=entry_data['timestamp'],
                            reason=entry_data['reason'],
                            session_name=entry_data.get('session_name')
                        )
                        self._blacklist[user_id] = entry
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Skipping invalid blacklist entry for {user_id}: {e}")
                        continue
                
                logger.info(f"Loaded {len(self._blacklist)} entries from blacklist")
                self._storage_available = True
                
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted blacklist file at {self.storage_path}: {e}")
                logger.info("Starting with empty in-memory blacklist")
                self._blacklist = {}
                self._storage_available = False
                
            except Exception as e:
                logger.error(f"Failed to load blacklist from {self.storage_path}: {e}")
                logger.info("Starting with empty in-memory blacklist")
                self._blacklist = {}
                self._storage_available = False
    
    async def _persist(self) -> None:
        """
        Persist blacklist to storage
        
        Note: This is an internal method. Lock should be held by caller.
        """
        try:
            # Prepare data structure
            data = {
                'version': self.STORAGE_VERSION,
                'entries': {}
            }
            
            for user_id, entry in self._blacklist.items():
                data['entries'][user_id] = {
                    'user_id': entry.user_id,
                    'timestamp': entry.timestamp,
                    'reason': entry.reason,
                    'session_name': entry.session_name
                }
            
            # Ensure directory exists
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            Path(temp_path).replace(path)
            
            self._storage_available = True
            logger.debug(f"Persisted {len(self._blacklist)} entries to blacklist")
            
        except Exception as e:
            logger.error(f"Failed to persist blacklist to {self.storage_path}: {e}")
            self._storage_available = False
            # Don't raise - maintain in-memory state and retry on next modification
    
    async def is_blacklisted(self, user_id: str) -> bool:
        """
        Check if user is in blacklist.
        
        This is a fast O(1) lookup operation that checks if the given user
        identifier exists in the blacklist. This method is called before
        every message send operation to prevent delivery to blocked users.
        
        Args:
            user_id: User identifier to check. Can be a username (without @)
                or a numeric user ID as a string.
        
        Returns:
            True if user is blacklisted, False otherwise. Returns False on
            any error to allow operations to continue.
        
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        
        Performance:
            O(1) lookup time. Completes in <1ms for typical blacklist sizes.
        
        Example:
            >>> is_blocked = await manager.is_blacklisted('user123')
            >>> if is_blocked:
            ...     print("User is blacklisted, skipping delivery")
        """
        try:
            async with self._lock:
                return user_id in self._blacklist
        except Exception as e:
            logger.error(f"Error checking blacklist for user {user_id}: {e}")
            # On error, return False to allow operation to continue
            return False
    
    async def add(self, user_id: str, reason: str = "block_detected", session_name: Optional[str] = None) -> None:
        """
        Add user to blacklist.
        
        Adds a user to the blacklist with the specified reason and immediately
        persists the change to storage. If the user is already blacklisted,
        updates the entry with new information.
        
        This method is called automatically when the system detects a block
        (after 2 consecutive failures), or manually by administrators.
        
        Args:
            user_id: User identifier to add. Can be a username (without @)
                or a numeric user ID as a string.
            reason: Reason for blacklisting. Common values:
                - "block_detected": Automatic detection after failures
                - "manual": Manual addition by administrator
                - "spam": User flagged as spam
                - "abusive_behavior": User flagged for abuse
            session_name: Name of the session that detected the block.
                Typically the phone number (e.g., "+1234567890").
                None for manual additions.
        
        Side Effects:
            - Adds entry to in-memory blacklist
            - Persists blacklist to storage file
            - Logs the addition with structured logging
        
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        
        Example:
            >>> # Automatic addition after block detection
            >>> await manager.add('user123', reason='block_detected', 
            ...                   session_name='+1234567890')
            >>> 
            >>> # Manual addition by administrator
            >>> await manager.add('spam_user', reason='spam')
        """
        async with self._lock:
            # Create entry
            entry = BlacklistEntry(
                user_id=user_id,
                timestamp=time.time(),
                reason=reason,
                session_name=session_name
            )
            
            # Add to in-memory blacklist
            self._blacklist[user_id] = entry
            
            # Persist to storage
            await self._persist()
            
            logger.info(f"Added user {user_id} to blacklist (reason: {reason}, session: {session_name})")
    
    async def remove(self, user_id: str) -> bool:
        """
        Remove user from blacklist.
        
        Removes a user from the blacklist and immediately persists the change
        to storage. This is typically used when a user unblocks the system
        or when an administrator wants to give a user another chance.
        
        Args:
            user_id: User identifier to remove. Can be a username (without @)
                or a numeric user ID as a string.
        
        Returns:
            True if user was found and removed, False if user was not in
            the blacklist.
        
        Side Effects:
            - Removes entry from in-memory blacklist (if found)
            - Persists blacklist to storage file (if found)
            - Logs the removal with structured logging
        
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        
        Example:
            >>> removed = await manager.remove('user123')
            >>> if removed:
            ...     print("User removed from blacklist")
            ... else:
            ...     print("User was not in blacklist")
        """
        async with self._lock:
            if user_id not in self._blacklist:
                return False
            
            # Remove from in-memory blacklist
            del self._blacklist[user_id]
            
            # Persist to storage
            await self._persist()
            
            logger.info(f"Removed user {user_id} from blacklist")
            return True
    
    async def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all blacklisted users with metadata.
        
        Returns a list of all blacklist entries with complete metadata.
        This is useful for administrators to review the blacklist and
        understand why users were blacklisted.
        
        Returns:
            List of dictionaries, each containing:
                - user_id (str): User identifier
                - timestamp (float): Unix timestamp when added
                - reason (str): Reason for blacklisting
                - session_name (str | None): Session that detected the block
        
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        
        Example:
            >>> entries = await manager.get_all()
            >>> for entry in entries:
            ...     print(f"{entry['user_id']}: {entry['reason']}")
            ...     print(f"  Added: {entry['timestamp']}")
            ...     if entry['session_name']:
            ...         print(f"  Detected by: {entry['session_name']}")
        """
        async with self._lock:
            return [
                {
                    'user_id': entry.user_id,
                    'timestamp': entry.timestamp,
                    'reason': entry.reason,
                    'session_name': entry.session_name
                }
                for entry in self._blacklist.values()
            ]
    
    async def clear(self) -> int:
        """
        Clear entire blacklist.
        
        Removes all entries from the blacklist and persists the empty state
        to storage. This is a destructive operation that cannot be undone.
        Use with caution.
        
        This is typically used for testing or when starting fresh with a
        clean blacklist.
        
        Returns:
            Number of entries that were removed.
        
        Side Effects:
            - Clears all entries from in-memory blacklist
            - Persists empty blacklist to storage file
            - Logs the clear operation with count
        
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        
        Warning:
            This operation cannot be undone. All blacklist data will be lost.
        
        Example:
            >>> count = await manager.clear()
            >>> print(f"Removed {count} entries from blacklist")
        """
        async with self._lock:
            count = len(self._blacklist)
            self._blacklist.clear()
            
            # Persist empty state
            await self._persist()
            
            logger.info(f"Cleared blacklist ({count} entries removed)")
            return count
