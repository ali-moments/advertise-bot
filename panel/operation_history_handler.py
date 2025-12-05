"""
Operation History Handler for Telegram Bot Panel

This module provides operation history tracking and display functionality,
allowing admins to view past operations with filtering and pagination.

Requirements: AC-11.1, AC-11.2, AC-11.3, AC-11.4
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from .state_manager import StateManager, OperationProgress
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .persian_text import (
    OPERATION_HISTORY_TITLE,
    OPERATION_HISTORY_EMPTY,
    OPERATION_DETAILS_TITLE,
    BTN_FILTER_TYPE,
    BTN_FILTER_STATUS,
    BTN_CLEAR_FILTERS,
    BTN_BACK,
    BTN_MAIN_MENU
)


class OperationHistoryHandler:
    """
    Handler for operation history display and management
    
    Provides functionality to:
    - Display operation history with pagination
    - Show detailed operation information
    - Filter operations by type and status
    - Automatically clean up old operations (24 hour retention)
    
    Requirements: AC-11.1, AC-11.2, AC-11.3, AC-11.4
    """
    
    # Conversation states
    SHOW_HISTORY = 0
    SHOW_DETAILS = 1
    FILTER_MENU = 2
    
    # Configuration
    ITEMS_PER_PAGE = 10
    RETENTION_HOURS = 24
    CLEANUP_INTERVAL = 3600  # 1 hour
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize operation history handler
        
        Args:
            state_manager: State manager instance for accessing operation data
        """
        self.state_manager = state_manager
        self.logger = logging.getLogger("OperationHistoryHandler")
        
        # Storage for operation history (persisted beyond state_manager)
        self.operation_history: List[Dict[str, Any]] = []
        
        # Filters per user
        self.user_filters: Dict[int, Dict[str, Any]] = {}
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        self.logger.info("OperationHistoryHandler initialized")
    
    async def start_cleanup_task(self) -> None:
        """
        Start automatic cleanup task for old operations
        
        Requirements: AC-11.3
        """
        if self._cleanup_task is not None:
            self.logger.warning("Cleanup task already running")
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Started operation history cleanup task")
    
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
        self.logger.info("Stopped operation history cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """
        Cleanup loop that runs periodically
        
        Requirements: AC-11.3
        """
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                await self.cleanup_old_operations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def cleanup_old_operations(self) -> int:
        """
        Clean up operations older than retention period
        
        Returns:
            Number of operations cleaned up
            
        Requirements: AC-11.3
        """
        current_time = time.time()
        retention_seconds = self.RETENTION_HOURS * 3600
        
        initial_count = len(self.operation_history)
        
        # Filter out old operations
        self.operation_history = [
            op for op in self.operation_history
            if current_time - op.get('started_at', 0) < retention_seconds
        ]
        
        cleaned_count = initial_count - len(self.operation_history)
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old operations")
        
        return cleaned_count
    
    def add_operation(self, operation: OperationProgress) -> None:
        """
        Add operation to history
        
        Args:
            operation: OperationProgress instance to add
        """
        # Convert to dict for storage
        op_dict = {
            'operation_id': operation.operation_id,
            'operation_type': operation.operation_type,
            'total': operation.total,
            'completed': operation.completed,
            'failed': operation.failed,
            'started_at': operation.started_at,
            'user_id': operation.user_id,
            'status': operation.status,
            'error_message': operation.error_message,
            'result_data': operation.result_data.copy() if operation.result_data else {}
        }
        
        # Check if operation already exists (update instead of add)
        for i, existing_op in enumerate(self.operation_history):
            if existing_op['operation_id'] == operation.operation_id:
                self.operation_history[i] = op_dict
                self.logger.debug(f"Updated operation in history: {operation.operation_id}")
                return
        
        # Add new operation
        self.operation_history.append(op_dict)
        self.logger.debug(f"Added operation to history: {operation.operation_id}")
        
        # Keep only last 50 operations to prevent unbounded growth
        if len(self.operation_history) > 50:
            self.operation_history = self.operation_history[-50:]
    
    def get_filtered_operations(
        self,
        user_id: int,
        operation_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get filtered operations
        
        Args:
            user_id: User ID (for user-specific filters)
            operation_type: Filter by operation type (optional)
            status: Filter by status (optional)
        
        Returns:
            List of filtered operations
            
        Requirements: AC-11.4
        """
        # Get user filters if not specified
        if operation_type is None and status is None:
            filters = self.user_filters.get(user_id, {})
            operation_type = filters.get('type')
            status = filters.get('status')
        
        # Filter operations
        filtered = self.operation_history.copy()
        
        if operation_type:
            filtered = [op for op in filtered if op['operation_type'] == operation_type]
        
        if status:
            filtered = [op for op in filtered if op['status'] == status]
        
        # Sort by started_at descending (newest first)
        filtered.sort(key=lambda x: x.get('started_at', 0), reverse=True)
        
        return filtered
    
    def set_user_filter(
        self,
        user_id: int,
        filter_type: Optional[str] = None,
        filter_status: Optional[str] = None
    ) -> None:
        """
        Set filters for a user
        
        Args:
            user_id: User ID
            filter_type: Operation type filter
            filter_status: Status filter
            
        Requirements: AC-11.4
        """
        if user_id not in self.user_filters:
            self.user_filters[user_id] = {}
        
        if filter_type is not None:
            self.user_filters[user_id]['type'] = filter_type
        
        if filter_status is not None:
            self.user_filters[user_id]['status'] = filter_status
    
    def clear_user_filters(self, user_id: int) -> None:
        """
        Clear all filters for a user
        
        Args:
            user_id: User ID
            
        Requirements: AC-11.4
        """
        if user_id in self.user_filters:
            del self.user_filters[user_id]
    
    def get_user_filters(self, user_id: int) -> Dict[str, Any]:
        """
        Get current filters for a user
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with 'type' and 'status' keys
        """
        return self.user_filters.get(user_id, {})
    
    async def show_history(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        page: int = 0
    ) -> int:
        """
        Display operation history list with pagination
        
        Args:
            update: Telegram update
            context: Callback context
            page: Page number (0-indexed)
        
        Returns:
            Conversation state
            
        Requirements: AC-11.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Get filtered operations
        operations = self.get_filtered_operations(user_id)
        
        if not operations:
            # No operations found
            keyboard = KeyboardBuilder.back_to_main()
            
            message_text = OPERATION_HISTORY_EMPTY
            
            # Add filter info if filters are active
            filters = self.get_user_filters(user_id)
            if filters:
                message_text += "\n\n🔍 فیلترهای فعال:"
                if filters.get('type'):
                    message_text += f"\n• نوع: {filters['type']}"
                if filters.get('status'):
                    message_text += f"\n• وضعیت: {filters['status']}"
            
            if query:
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    text=message_text,
                    reply_markup=keyboard
                )
            
            return ConversationHandler.END
        
        # Pagination
        total_pages = (len(operations) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_operations = operations[start_idx:end_idx]
        
        # Format message
        message_text = MessageFormatter.format_operation_history(
            operations=page_operations,
            page=page + 1,
            total_pages=total_pages
        )
        
        # Add filter info if filters are active
        filters = self.get_user_filters(user_id)
        if filters:
            message_text += "\n\n🔍 فیلترهای فعال:"
            if filters.get('type'):
                message_text += f"\n• نوع: {filters['type']}"
            if filters.get('status'):
                message_text += f"\n• وضعیت: {filters['status']}"
        
        # Build keyboard
        keyboard = KeyboardBuilder.operation_history_list(
            operations=page_operations,
            page=page,
            total_pages=total_pages
        )
        
        # Add filter button
        filter_row = [
            InlineKeyboardButton("🔍 فیلتر", callback_data="operation:filter"),
        ]
        if filters:
            filter_row.append(
                InlineKeyboardButton(BTN_CLEAR_FILTERS, callback_data="operation:clear_filters")
            )
        
        # Insert filter row before navigation buttons
        keyboard_buttons = list(keyboard.inline_keyboard)
        keyboard_buttons.insert(-1, filter_row)
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        if query:
            await query.edit_message_text(
                text=message_text,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=keyboard
            )
        
        return self.SHOW_HISTORY
    
    async def show_details(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        operation_id: str,
        page: int = 0
    ) -> int:
        """
        Display detailed operation information
        
        Args:
            update: Telegram update
            context: Callback context
            operation_id: Operation ID to display
            page: Page number to return to
        
        Returns:
            Conversation state
            
        Requirements: AC-11.2
        """
        query = update.callback_query
        await query.answer()
        
        # Find operation
        operation = None
        for op in self.operation_history:
            if op['operation_id'] == operation_id:
                operation = op
                break
        
        if not operation:
            await query.edit_message_text(
                text="❌ عملیات یافت نشد.",
                reply_markup=KeyboardBuilder.back_to_main()
            )
            return ConversationHandler.END
        
        # Format details
        message_text = MessageFormatter.format_operation_details(operation)
        
        # Build keyboard
        keyboard = KeyboardBuilder.operation_details(operation_id, page)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard
        )
        
        return self.SHOW_DETAILS
    
    async def show_filter_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Display filter menu
        
        Args:
            update: Telegram update
            context: Callback context
        
        Returns:
            Conversation state
            
        Requirements: AC-11.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        filters = self.get_user_filters(user_id)
        
        message_text = "🔍 **فیلتر تاریخچه عملیات**\n\n"
        message_text += "فیلترهای فعال:\n"
        
        if filters.get('type'):
            message_text += f"• نوع: {filters['type']}\n"
        else:
            message_text += "• نوع: همه\n"
        
        if filters.get('status'):
            message_text += f"• وضعیت: {filters['status']}\n"
        else:
            message_text += "• وضعیت: همه\n"
        
        message_text += "\n یک فیلتر را انتخاب کنید:"
        
        # Build filter keyboard
        keyboard = [
            [
                InlineKeyboardButton("📋 فیلتر نوع", callback_data="operation:filter:type"),
                InlineKeyboardButton("📊 فیلتر وضعیت", callback_data="operation:filter:status")
            ],
            [
                InlineKeyboardButton(BTN_CLEAR_FILTERS, callback_data="operation:clear_filters")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data="operation:history:page:0"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.FILTER_MENU
    
    async def show_type_filter(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Display operation type filter options
        
        Args:
            update: Telegram update
            context: Callback context
        
        Returns:
            Conversation state
            
        Requirements: AC-11.4
        """
        query = update.callback_query
        await query.answer()
        
        message_text = "📋 **فیلتر بر اساس نوع عملیات**\n\nنوع عملیات را انتخاب کنید:"
        
        # Get unique operation types
        operation_types = set(op['operation_type'] for op in self.operation_history)
        
        keyboard = []
        for op_type in sorted(operation_types):
            keyboard.append([
                InlineKeyboardButton(
                    op_type,
                    callback_data=f"operation:set_filter:type:{op_type}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("همه", callback_data="operation:set_filter:type:all")
        ])
        keyboard.append([
            InlineKeyboardButton(BTN_BACK, callback_data="operation:filter")
        ])
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.FILTER_MENU
    
    async def show_status_filter(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Display operation status filter options
        
        Args:
            update: Telegram update
            context: Callback context
        
        Returns:
            Conversation state
            
        Requirements: AC-11.4
        """
        query = update.callback_query
        await query.answer()
        
        message_text = "📊 **فیلتر بر اساس وضعیت**\n\nوضعیت را انتخاب کنید:"
        
        keyboard = [
            [InlineKeyboardButton("⏳ در حال اجرا", callback_data="operation:set_filter:status:running")],
            [InlineKeyboardButton("✅ تکمیل شده", callback_data="operation:set_filter:status:completed")],
            [InlineKeyboardButton("❌ ناموفق", callback_data="operation:set_filter:status:failed")],
            [InlineKeyboardButton("⏸️ لغو شده", callback_data="operation:set_filter:status:cancelled")],
            [InlineKeyboardButton("همه", callback_data="operation:set_filter:status:all")],
            [InlineKeyboardButton(BTN_BACK, callback_data="operation:filter")]
        ]
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.FILTER_MENU
    
    async def set_filter(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        filter_type: str,
        filter_value: str
    ) -> int:
        """
        Set a filter and return to history
        
        Args:
            update: Telegram update
            context: Callback context
            filter_type: 'type' or 'status'
            filter_value: Filter value or 'all' to clear
        
        Returns:
            Conversation state
            
        Requirements: AC-11.4
        """
        query = update.callback_query
        await query.answer("✅ فیلتر اعمال شد")
        
        user_id = update.effective_user.id
        
        if filter_value == 'all':
            # Clear this specific filter
            if user_id in self.user_filters:
                if filter_type in self.user_filters[user_id]:
                    del self.user_filters[user_id][filter_type]
        else:
            # Set filter
            if filter_type == 'type':
                self.set_user_filter(user_id, filter_type=filter_value)
            elif filter_type == 'status':
                self.set_user_filter(user_id, filter_status=filter_value)
        
        # Return to history list
        return await self.show_history(update, context, page=0)
    
    async def clear_filters(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Clear all filters and return to history
        
        Args:
            update: Telegram update
            context: Callback context
        
        Returns:
            Conversation state
            
        Requirements: AC-11.4
        """
        query = update.callback_query
        await query.answer("✅ فیلترها پاک شدند")
        
        user_id = update.effective_user.id
        self.clear_user_filters(user_id)
        
        # Return to history list
        return await self.show_history(update, context, page=0)
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for operation history
        
        Returns:
            ConversationHandler configured for operation history
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    lambda u, c: self.show_history(u, c, page=0),
                    pattern=r'^operation:history$'
                )
            ],
            states={
                self.SHOW_HISTORY: [
                    CallbackQueryHandler(
                        lambda u, c: self.show_history(u, c, page=int(u.callback_query.data.split(':')[-1])),
                        pattern=r'^operation:history:page:\d+$'
                    ),
                    CallbackQueryHandler(
                        lambda u, c: self.show_details(u, c, u.callback_query.data.split(':')[-1], page=0),
                        pattern=r'^operation:details:.+$'
                    ),
                    CallbackQueryHandler(
                        self.show_filter_menu,
                        pattern=r'^operation:filter$'
                    ),
                    CallbackQueryHandler(
                        self.clear_filters,
                        pattern=r'^operation:clear_filters$'
                    ),
                ],
                self.SHOW_DETAILS: [
                    CallbackQueryHandler(
                        lambda u, c: self.show_details(u, c, u.callback_query.data.split(':')[-1], page=0),
                        pattern=r'^operation:details:.+$'
                    ),
                    CallbackQueryHandler(
                        lambda u, c: self.show_history(u, c, page=int(u.callback_query.data.split(':')[-1])),
                        pattern=r'^operation:history:page:\d+$'
                    ),
                ],
                self.FILTER_MENU: [
                    CallbackQueryHandler(
                        self.show_type_filter,
                        pattern=r'^operation:filter:type$'
                    ),
                    CallbackQueryHandler(
                        self.show_status_filter,
                        pattern=r'^operation:filter:status$'
                    ),
                    CallbackQueryHandler(
                        lambda u, c: self.set_filter(
                            u, c,
                            u.callback_query.data.split(':')[3],
                            u.callback_query.data.split(':')[4]
                        ),
                        pattern=r'^operation:set_filter:(type|status):.+$'
                    ),
                    CallbackQueryHandler(
                        self.clear_filters,
                        pattern=r'^operation:clear_filters$'
                    ),
                    CallbackQueryHandler(
                        self.show_filter_menu,
                        pattern=r'^operation:filter$'
                    ),
                    CallbackQueryHandler(
                        lambda u, c: self.show_history(u, c, page=int(u.callback_query.data.split(':')[-1])),
                        pattern=r'^operation:history:page:\d+$'
                    ),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(
                    lambda u, c: ConversationHandler.END,
                    pattern=r'^nav:main$'
                )
            ],
            name="operation_history",
            persistent=False
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get operation history statistics
        
        Returns:
            Dict with statistics
        """
        total_operations = len(self.operation_history)
        
        # Count by status
        status_counts = {}
        for op in self.operation_history:
            status = op.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by type
        type_counts = {}
        for op in self.operation_history:
            op_type = op.get('operation_type', 'unknown')
            type_counts[op_type] = type_counts.get(op_type, 0) + 1
        
        return {
            'total_operations': total_operations,
            'by_status': status_counts,
            'by_type': type_counts,
            'active_filters': len(self.user_filters)
        }
