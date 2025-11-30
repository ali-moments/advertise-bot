"""
ProgressTracker - Real-time progress updates for long operations
"""

import asyncio
import time
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError

from .message_formatter import MessageFormatter


class ProgressTracker:
    """Track and display progress for long-running operations"""
    
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        operation_name: str = "عملیات",
        update_interval: float = 2.0
    ):
        """
        Initialize progress tracker
        
        Args:
            bot: Telegram bot instance
            chat_id: Chat ID to send updates to
            message_id: Message ID to edit
            operation_name: Name of the operation
            update_interval: Minimum seconds between updates (default: 2.0)
        """
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.operation_name = operation_name
        self.update_interval = update_interval
        
        self.last_update = 0.0
        self.start_time = time.time()
        self.total = 0
        self.current = 0
        self.success = 0
        self.failed = 0
        self._is_complete = False
        self._update_lock = asyncio.Lock()
    
    async def start(self, total: int, initial_message: Optional[str] = None):
        """
        Start tracking progress
        
        Args:
            total: Total number of items to process
            initial_message: Optional initial message to display
        """
        self.total = total
        self.current = 0
        self.success = 0
        self.failed = 0
        self.start_time = time.time()
        self._is_complete = False
        
        if initial_message:
            message = initial_message
        else:
            message = f"⏳ **{self.operation_name}**\n\nشروع عملیات..."
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=message,
                parse_mode='Markdown'
            )
            self.last_update = time.time()
        except TelegramError as e:
            # Log error but don't fail
            print(f"Error updating progress: {e}")
    
    async def update(
        self,
        current: Optional[int] = None,
        success: Optional[int] = None,
        failed: Optional[int] = None,
        force: bool = False
    ):
        """
        Update progress
        
        Args:
            current: Current progress count (if None, increment by 1)
            success: Success count (if None, keep current)
            failed: Failed count (if None, keep current)
            force: Force update even if interval hasn't passed
        """
        if self._is_complete:
            return
        
        # Update counters
        if current is not None:
            self.current = current
        else:
            self.current += 1
        
        if success is not None:
            self.success = success
        
        if failed is not None:
            self.failed = failed
        
        # Check if enough time has passed
        now = time.time()
        if not force and (now - self.last_update) < self.update_interval:
            return
        
        # Use lock to prevent concurrent updates
        async with self._update_lock:
            # Double-check after acquiring lock
            if not force and (time.time() - self.last_update) < self.update_interval:
                return
            
            elapsed = time.time() - self.start_time
            
            message = MessageFormatter.format_progress(
                current=self.current,
                total=self.total,
                operation=self.operation_name,
                success=self.success,
                failed=self.failed,
                elapsed=elapsed,
                show_detailed=True
            )
            
            try:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=message,
                    parse_mode='Markdown'
                )
                self.last_update = time.time()
            except TelegramError as e:
                # Log error but don't fail
                print(f"Error updating progress: {e}")
    
    async def increment(self, success: bool = True, force: bool = False):
        """
        Increment progress by 1
        
        Args:
            success: Whether the operation was successful
            force: Force update even if interval hasn't passed
        """
        self.current += 1
        if success:
            self.success += 1
        else:
            self.failed += 1
        
        await self.update(
            current=self.current,
            success=self.success,
            failed=self.failed,
            force=force
        )
    
    async def complete(self, result: Dict[str, Any]):
        """
        Mark operation as complete and show final message
        
        Args:
            result: Result dictionary with operation details
        """
        if self._is_complete:
            return
        
        self._is_complete = True
        elapsed = time.time() - self.start_time
        
        # Format final message based on result type
        if 'member_count' in result:
            # Scraping result
            message = MessageFormatter.format_scrape_result(result)
        elif 'sent_count' in result:
            # Sending result
            message = MessageFormatter.format_send_result(result)
        else:
            # Generic completion
            message = f"""
✅ **{self.operation_name} تکمیل شد**

**کل:** {self.total}
**موفق:** {self.success}
**ناموفق:** {self.failed}
**زمان:** {MessageFormatter._format_duration(elapsed)}
"""
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=message,
                parse_mode='Markdown'
            )
        except TelegramError as e:
            print(f"Error showing completion: {e}")
    
    async def error(self, error_message: str, error_type: str = "خطا"):
        """
        Show error message
        
        Args:
            error_message: Error description
            error_type: Type of error
        """
        if self._is_complete:
            return
        
        self._is_complete = True
        
        message = MessageFormatter.format_error(
            error_type=error_type,
            description=error_message,
            show_retry=True
        )
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=message,
                parse_mode='Markdown'
            )
        except TelegramError as e:
            print(f"Error showing error: {e}")
    
    async def set_message(self, message: str):
        """
        Set custom message (useful for intermediate steps)
        
        Args:
            message: Message to display
        """
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=message,
                parse_mode='Markdown'
            )
            self.last_update = time.time()
        except TelegramError as e:
            print(f"Error setting message: {e}")
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        return time.time() - self.start_time
    
    def get_progress_percentage(self) -> int:
        """Get progress as percentage"""
        if self.total == 0:
            return 0
        return int((self.current / self.total) * 100)
    
    def get_eta(self) -> Optional[float]:
        """
        Get estimated time to completion in seconds
        
        Returns:
            Estimated seconds remaining, or None if cannot calculate
        """
        if self.current == 0 or self.total == 0:
            return None
        
        elapsed = self.get_elapsed_time()
        avg_time_per_item = elapsed / self.current
        remaining_items = self.total - self.current
        
        return avg_time_per_item * remaining_items
    
    @property
    def is_complete(self) -> bool:
        """Check if operation is complete"""
        return self._is_complete
    
    @property
    def progress_info(self) -> Dict[str, Any]:
        """Get current progress information"""
        return {
            'operation': self.operation_name,
            'total': self.total,
            'current': self.current,
            'success': self.success,
            'failed': self.failed,
            'percentage': self.get_progress_percentage(),
            'elapsed': self.get_elapsed_time(),
            'eta': self.get_eta(),
            'is_complete': self._is_complete
        }


class ProgressTrackerFactory:
    """Factory for creating progress trackers"""
    
    @staticmethod
    async def create(
        bot: Bot,
        chat_id: int,
        operation_name: str = "عملیات",
        initial_message: Optional[str] = None
    ) -> ProgressTracker:
        """
        Create and initialize a progress tracker
        
        Args:
            bot: Telegram bot instance
            chat_id: Chat ID to send updates to
            operation_name: Name of the operation
            initial_message: Optional initial message
        
        Returns:
            Initialized ProgressTracker instance
        """
        # Send initial message
        if initial_message is None:
            initial_message = f"⏳ **{operation_name}**\n\nآماده‌سازی..."
        
        message = await bot.send_message(
            chat_id=chat_id,
            text=initial_message,
            parse_mode='Markdown'
        )
        
        return ProgressTracker(
            bot=bot,
            chat_id=chat_id,
            message_id=message.message_id,
            operation_name=operation_name
        )
