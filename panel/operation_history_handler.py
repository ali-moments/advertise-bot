"""
OperationHistoryHandler - Handles operation history viewing with pagination

This handler provides functionality to view the history of operations
(scraping, sending, monitoring) with pagination support.

Requirements: AC-6.7
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
)

from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .state_manager import StateManager
from .persian_text import OPERATION_CANCELLED, PLEASE_WAIT


# Conversation states
(
    VIEW_HISTORY,
    VIEW_DETAILS
) = range(2)


@dataclass
class HistoryUserSession:
    """User session data for operation history viewing"""
    user_id: int
    page: int = 0
    selected_operation: Optional[str] = None
    started_at: float = field(default_factory=time.time)


class OperationHistoryHandler:
    """Handle operation history viewing with pagination"""
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize operation history handler
        
        Args:
            state_manager: StateManager instance for accessing operation data
        """
        self.state_manager = state_manager
        self.user_sessions: Dict[int, HistoryUserSession] = {}
        self.operations_per_page = 10  # AC-6.7 requirement
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get the conversation handler for operation history
        
        Returns:
            ConversationHandler configured for operation history viewing
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_operation_history, pattern='^operation:history'),
                CommandHandler('history', self.show_operation_history_command),
            ],
            states={
                VIEW_HISTORY: [
                    CallbackQueryHandler(self.show_operation_history, pattern='^operation:history:page:'),
                    CallbackQueryHandler(self.show_operation_details, pattern='^operation:details:'),
                    CallbackQueryHandler(self.cancel_operation, pattern='^nav:main$'),
                ],
                VIEW_DETAILS: [
                    CallbackQueryHandler(self.show_operation_details, pattern='^operation:details:'),
                    CallbackQueryHandler(self.show_operation_history, pattern='^operation:history:page:'),
                    CallbackQueryHandler(self.cancel_operation, pattern='^nav:main$'),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_operation),
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$'),
            ],
            name="operation_history",
            persistent=False
        )
    
    async def show_operation_history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show operation history from command
        
        Requirements: AC-6.7
        """
        # Create a fake callback query for consistency
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = HistoryUserSession(
            user_id=user_id,
            page=0
        )
        
        # Get all operations for this user
        operations = self.state_manager.get_user_operations(user_id)
        
        if not operations:
            message = "📜 **تاریخچه عملیات**\n\nهیچ عملیاتی یافت نشد."
            keyboard = KeyboardBuilder.back_to_main()
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
            return ConversationHandler.END
        
        # Sort by start time (newest first)
        operations.sort(key=lambda x: x.started_at, reverse=True)
        
        # Paginate
        total_ops = len(operations)
        total_pages = (total_ops + self.operations_per_page - 1) // self.operations_per_page
        page = 0
        
        start_idx = page * self.operations_per_page
        end_idx = min(start_idx + self.operations_per_page, total_ops)
        page_operations = operations[start_idx:end_idx]
        
        # Convert to dict format for formatting
        ops_data = []
        for op in page_operations:
            ops_data.append({
                'operation_id': op.operation_id,
                'operation_type': op.operation_type,
                'status': op.status,
                'total': op.total,
                'completed': op.completed,
                'failed': op.failed,
                'started_at': op.started_at
            })
        
        # Format message
        message = MessageFormatter.format_operation_history(
            operations=ops_data,
            page=page + 1,
            total_pages=total_pages
        )
        
        # Build keyboard
        keyboard = KeyboardBuilder.operation_history_list(
            operations=ops_data,
            page=page,
            total_pages=total_pages
        )
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return VIEW_HISTORY
    
    async def show_operation_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show paginated operation history
        
        Requirements: AC-6.7
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Parse page number from callback data
        page = 0
        if ':page:' in query.data:
            try:
                page = int(query.data.split(':page:')[1])
            except (IndexError, ValueError):
                page = 0
        
        # Update user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = HistoryUserSession(
                user_id=user_id,
                page=page
            )
        else:
            self.user_sessions[user_id].page = page
        
        # Show loading message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Get all operations for this user
            operations = self.state_manager.get_user_operations(user_id)
            
            if not operations:
                message = "📜 **تاریخچه عملیات**\n\nهیچ عملیاتی یافت نشد."
                keyboard = KeyboardBuilder.back_to_main()
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
                return ConversationHandler.END
            
            # Sort by start time (newest first)
            operations.sort(key=lambda x: x.started_at, reverse=True)
            
            # Paginate
            total_ops = len(operations)
            total_pages = (total_ops + self.operations_per_page - 1) // self.operations_per_page
            page = max(0, min(page, total_pages - 1))
            
            start_idx = page * self.operations_per_page
            end_idx = min(start_idx + self.operations_per_page, total_ops)
            page_operations = operations[start_idx:end_idx]
            
            # Convert to dict format for formatting
            ops_data = []
            for op in page_operations:
                ops_data.append({
                    'operation_id': op.operation_id,
                    'operation_type': op.operation_type,
                    'status': op.status,
                    'total': op.total,
                    'completed': op.completed,
                    'failed': op.failed,
                    'started_at': op.started_at
                })
            
            # Format message
            message = MessageFormatter.format_operation_history(
                operations=ops_data,
                page=page + 1,
                total_pages=total_pages
            )
            
            # Build keyboard
            keyboard = KeyboardBuilder.operation_history_list(
                operations=ops_data,
                page=page,
                total_pages=total_pages
            )
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return VIEW_HISTORY
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="دریافت تاریخچه عملیات",
                description=str(e),
                show_retry=True
            )
            keyboard = KeyboardBuilder.back_to_main()
            await query.edit_message_text(error_msg, reply_markup=keyboard, parse_mode='Markdown')
            return ConversationHandler.END
    
    async def show_operation_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show detailed information for a specific operation
        
        Requirements: AC-6.7
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Extract operation ID from callback data
        # Format: operation:details:operation_id
        try:
            operation_id = query.data.split('operation:details:')[1]
        except IndexError:
            await query.edit_message_text("❌ خطا در شناسایی عملیات")
            return ConversationHandler.END
        
        # Update user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = HistoryUserSession(
                user_id=user_id
            )
        self.user_sessions[user_id].selected_operation = operation_id
        
        # Show loading message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Get operation progress
            operation = self.state_manager.get_operation_progress(operation_id)
            
            if not operation:
                message = f"❌ عملیات `{operation_id}` یافت نشد."
                keyboard = KeyboardBuilder.back_to_main()
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
                return VIEW_HISTORY
            
            # Convert to dict format for formatting
            op_data = {
                'operation_id': operation.operation_id,
                'operation_type': operation.operation_type,
                'status': operation.status,
                'total': operation.total,
                'completed': operation.completed,
                'failed': operation.failed,
                'started_at': operation.started_at,
                'error_message': operation.error_message,
                'result_data': operation.result_data
            }
            
            # Format message
            message = MessageFormatter.format_operation_details(op_data)
            
            # Build keyboard
            page = self.user_sessions[user_id].page
            keyboard = KeyboardBuilder.operation_details(operation_id, page)
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return VIEW_DETAILS
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="دریافت جزئیات عملیات",
                description=str(e),
                show_retry=True
            )
            keyboard = KeyboardBuilder.back_to_main()
            await query.edit_message_text(error_msg, reply_markup=keyboard, parse_mode='Markdown')
            return VIEW_HISTORY
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Cancel current operation
        """
        query = update.callback_query if update.callback_query else None
        
        if query:
            await query.answer()
            user_id = query.from_user.id
        else:
            user_id = update.effective_user.id
        
        # Clean up user session
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        message = OPERATION_CANCELLED
        keyboard = KeyboardBuilder.back_to_main()
        
        if query:
            await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        
        return ConversationHandler.END
