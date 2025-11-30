"""
SessionHandler - Handles session management operations
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from telegram_manager.main import TelegramManagerApp
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .persian_text import (
    OPERATION_CANCELLED, PLEASE_WAIT, ERROR_TEMPLATE,
    SESSION_LIST_HEADER, SESSION_DETAILS_HEADER, LOAD_DISTRIBUTION_HEADER
)


# Conversation states
(
    SELECT_SESSION_ACTION,
    SELECT_SESSION,
    VIEW_SESSION_DETAILS
) = range(3)


@dataclass
class SessionUserSession:
    """User session data for session management operations"""
    user_id: int
    action: str  # 'list', 'details', 'load_distribution'
    selected_session: Optional[str] = None
    page: int = 0  # For pagination
    started_at: float = field(default_factory=time.time)


class SessionHandler:
    """Handle session management operations"""
    
    def __init__(self, session_manager: TelegramManagerApp):
        """
        Initialize session handler
        
        Args:
            session_manager: TelegramManagerApp instance
        """
        self.session_manager = session_manager
        self.user_sessions: Dict[int, SessionUserSession] = {}
        self.sessions_per_page = 10  # AC-4.1 requirement
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get the conversation handler for session management
        
        Returns:
            ConversationHandler configured for session operations
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_session_menu, pattern='^session:menu$'),
                CallbackQueryHandler(self.show_session_list, pattern='^session:list$'),
                CallbackQueryHandler(self.show_load_distribution, pattern='^session:load_distribution$'),
            ],
            states={
                SELECT_SESSION_ACTION: [
                    CallbackQueryHandler(self.show_session_list, pattern='^session:list$'),
                    CallbackQueryHandler(self.show_load_distribution, pattern='^session:load_distribution$'),
                    CallbackQueryHandler(self.cancel_operation, pattern='^session:cancel$'),
                ],
                SELECT_SESSION: [
                    CallbackQueryHandler(self.show_session_details, pattern='^session:details:'),
                    CallbackQueryHandler(self.show_session_list, pattern='^session:list:page:'),
                    CallbackQueryHandler(self.cancel_operation, pattern='^session:cancel$'),
                ],
                VIEW_SESSION_DETAILS: [
                    CallbackQueryHandler(self.show_session_list, pattern='^session:back_to_list$'),
                    CallbackQueryHandler(self.refresh_session_details, pattern='^session:refresh:'),
                    CallbackQueryHandler(self.cancel_operation, pattern='^session:cancel$'),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_operation),
                CallbackQueryHandler(self.cancel_operation, pattern='^nav:main$'),
            ],
            name="session_management",
            persistent=False
        )
    
    async def show_session_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show session management menu
        
        Requirements: AC-4.1
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = SessionUserSession(
            user_id=user_id,
            action='menu'
        )
        
        message = """
👥 **مدیریت سشن‌ها**

از این بخش می‌توانید:
🔹 لیست تمام سشن‌ها را مشاهده کنید
🔹 جزئیات هر سشن را ببینید
🔹 توزیع بار را بررسی کنید
🔹 وضعیت سلامت سشن‌ها را چک کنید

لطفاً یک گزینه را انتخاب کنید:
"""
        
        keyboard = KeyboardBuilder.session_menu()
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_SESSION_ACTION
    
    async def show_session_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show paginated list of sessions with status indicators
        
        Requirements: AC-4.1, AC-4.2, AC-4.3
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
            self.user_sessions[user_id] = SessionUserSession(
                user_id=user_id,
                action='list'
            )
        self.user_sessions[user_id].action = 'list'
        self.user_sessions[user_id].page = page
        
        # Show loading message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Get session statistics
            stats = await self.session_manager.get_session_stats()
            
            if not stats:
                message = "👥 **لیست سشن‌ها**\n\nهیچ سشنی یافت نشد."
                keyboard = KeyboardBuilder.back_to_main()
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
                return ConversationHandler.END
            
            # Convert stats to list format
            session_list = []
            for session_name, session_data in stats.items():
                # Extract phone number from session name
                phone = session_name.replace('sessions/', '').replace('.session', '')
                
                # Get daily stats
                daily_stats = session_data.get('daily_stats', {})
                
                # Get monitoring info
                monitoring_channels = []
                if session_data.get('monitoring'):
                    monitoring_channels = session_data.get('monitoring_channels', [])
                
                session_info = {
                    'session_name': session_name,
                    'phone': phone,
                    'connected': session_data.get('connected', False),
                    'monitoring': session_data.get('monitoring', False),
                    'monitoring_channels': monitoring_channels,
                    'queue_depth': session_data.get('queue_depth', 0),
                    'daily_stats': {
                        'messages_read': daily_stats.get('messages_read', 0),
                        'groups_scraped': daily_stats.get('groups_scraped_today', 0),
                    }
                }
                session_list.append(session_info)
            
            # Paginate sessions
            total_sessions = len(session_list)
            total_pages = (total_sessions + self.sessions_per_page - 1) // self.sessions_per_page
            start_idx = page * self.sessions_per_page
            end_idx = min(start_idx + self.sessions_per_page, total_sessions)
            page_sessions = session_list[start_idx:end_idx]
            
            # Format session list
            message = MessageFormatter.format_session_list(page_sessions, page + 1, total_pages)
            
            # Build keyboard with session buttons and pagination
            keyboard = KeyboardBuilder.session_list(
                sessions=page_sessions,
                page=page,
                total_pages=total_pages
            )
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return SELECT_SESSION
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="دریافت لیست سشن‌ها",
                description=str(e),
                show_retry=True
            )
            keyboard = KeyboardBuilder.back_to_main()
            await query.edit_message_text(error_msg, reply_markup=keyboard, parse_mode='Markdown')
            return ConversationHandler.END
    
    async def show_session_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show detailed information for a specific session
        
        Requirements: AC-4.2, AC-4.3, AC-4.4, AC-4.5
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Extract session name from callback data
        # Format: session:details:session_name
        try:
            session_name = query.data.split('session:details:')[1]
        except IndexError:
            await query.edit_message_text("❌ خطا در شناسایی سشن")
            return ConversationHandler.END
        
        # Update user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = SessionUserSession(
                user_id=user_id,
                action='details'
            )
        self.user_sessions[user_id].action = 'details'
        self.user_sessions[user_id].selected_session = session_name
        
        # Show loading message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Get session statistics
            stats = await self.session_manager.get_session_stats()
            
            if session_name not in stats:
                message = f"❌ سشن `{session_name}` یافت نشد."
                keyboard = KeyboardBuilder.back_to_session_list()
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
                return SELECT_SESSION
            
            session_data = stats[session_name]
            
            # Extract phone number
            phone = session_name.replace('sessions/', '').replace('.session', '')
            
            # Get monitoring channels
            monitoring_channels = []
            if session_data.get('monitoring'):
                # Get monitoring targets from session manager
                try:
                    # Access the session directly to get monitoring targets
                    session = self.session_manager.manager.sessions.get(session_name)
                    if session and hasattr(session, 'monitoring_targets'):
                        monitoring_channels = list(session.monitoring_targets.keys())
                except Exception:
                    pass
            
            # Get active operations
            active_operations = []
            current_op = session_data.get('current_operation')
            if current_op:
                op_start = session_data.get('operation_start_time')
                if op_start:
                    duration = time.time() - op_start
                    active_operations.append({
                        'type': current_op,
                        'progress': f'در حال اجرا ({int(duration)}s)'
                    })
            
            # Get daily stats
            daily_stats = session_data.get('daily_stats', {})
            
            # Get health status (placeholder - will be enhanced later)
            health = {
                'healthy': session_data.get('connected', False),
                'last_check': time.time()
            }
            
            # Format session details
            session_info = {
                'phone': phone,
                'connected': session_data.get('connected', False),
                'monitoring': session_data.get('monitoring', False),
                'monitoring_channels': monitoring_channels,
                'active_operations': active_operations,
                'daily_stats': {
                    'messages_read': daily_stats.get('messages_read', 0),
                    'daily_limit': 500,
                    'groups_scraped': daily_stats.get('groups_scraped_today', 0),
                    'scrape_limit': 10,
                    'messages_sent': 0  # Placeholder
                },
                'health': health,
                'queue_depth': session_data.get('queue_depth', 0)
            }
            
            message = MessageFormatter.format_session_stats(session_info)
            
            # Build keyboard
            keyboard = KeyboardBuilder.session_details(session_name)
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return VIEW_SESSION_DETAILS
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="دریافت جزئیات سشن",
                description=str(e),
                show_retry=True
            )
            keyboard = KeyboardBuilder.back_to_session_list()
            await query.edit_message_text(error_msg, reply_markup=keyboard, parse_mode='Markdown')
            return SELECT_SESSION
    
    async def refresh_session_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Refresh session details view
        
        Requirements: AC-5.6
        """
        # Simply call show_session_details again
        return await self.show_session_details(update, context)
    
    async def show_load_distribution(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show load distribution across sessions with text-based visualization
        
        Requirements: AC-4.6
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Update user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = SessionUserSession(
                user_id=user_id,
                action='load_distribution'
            )
        self.user_sessions[user_id].action = 'load_distribution'
        
        # Show loading message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Get session statistics
            stats = await self.session_manager.get_session_stats()
            
            if not stats:
                message = "⚖️ **توزیع بار**\n\nهیچ سشنی یافت نشد."
                keyboard = KeyboardBuilder.back_to_session_menu()
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
                return SELECT_SESSION_ACTION
            
            # Prepare session load data
            session_load_data = []
            for session_name, session_data in stats.items():
                phone = session_name.replace('sessions/', '').replace('.session', '')
                
                # Calculate current load
                # Load = active tasks + queue depth
                current_load = session_data.get('active_tasks', 0)
                queue_depth = session_data.get('queue_depth', 0)
                
                session_load_data.append({
                    'phone': phone,
                    'current_load': current_load,
                    'queue_depth': queue_depth,
                    'connected': session_data.get('connected', False)
                })
            
            # Sort by load (highest first)
            session_load_data.sort(key=lambda x: x['current_load'], reverse=True)
            
            # Format load distribution
            message = MessageFormatter.format_load_distribution(session_load_data)
            
            # Build keyboard
            keyboard = KeyboardBuilder.load_distribution_menu()
            
            await query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return SELECT_SESSION_ACTION
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="دریافت توزیع بار",
                description=str(e),
                show_retry=True
            )
            keyboard = KeyboardBuilder.back_to_session_menu()
            await query.edit_message_text(error_msg, reply_markup=keyboard, parse_mode='Markdown')
            return SELECT_SESSION_ACTION
    
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
