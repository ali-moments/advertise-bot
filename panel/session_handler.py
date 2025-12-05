"""
Session Handler - Manages session display and statistics through bot interface

This module handles:
- Session list display with pagination
- Session details view
- Daily usage statistics
- Session health status display
- Load distribution visualization

Requirements: AC-4.1, AC-4.2, AC-4.3, AC-4.4, AC-4.5, AC-4.6
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from telegram_manager.manager import TelegramSessionManager
from .state_manager import StateManager
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .error_handler import BotErrorHandler, ErrorContext
from .persian_text import (
    SESSION_MENU_TEXT, BTN_LIST_SESSIONS, BTN_SESSION_DETAILS,
    BTN_DAILY_STATS, BTN_HEALTH_STATUS, BTN_LOAD_DISTRIBUTION,
    STATUS_CONNECTED, STATUS_DISCONNECTED, STATUS_ACTIVE, STATUS_INACTIVE
)


# Conversation states
SELECT_SESSION_ACTION = 0
VIEW_SESSION_DETAILS = 1


class SessionHandler:
    """
    Handler for all session management operations
    
    Manages:
    - Displaying session list with pagination
    - Showing detailed session information
    - Displaying daily usage statistics
    - Showing session health status
    - Visualizing load distribution
    
    Requirements: AC-4.1 through AC-4.6
    """
    
    # Pagination settings
    SESSIONS_PER_PAGE = 5
    
    def __init__(
        self,
        session_manager: TelegramSessionManager,
        state_manager: StateManager,
        error_handler: BotErrorHandler
    ):
        """
        Initialize session handler
        
        Args:
            session_manager: TelegramSessionManager instance
            state_manager: StateManager instance
            error_handler: BotErrorHandler instance
        """
        self.session_manager = session_manager
        self.state_manager = state_manager
        self.error_handler = error_handler
        self.logger = logging.getLogger("SessionHandler")
        
        self.logger.info("SessionHandler initialized")
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for session operations
        
        Returns:
            ConversationHandler configured for session flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_session_menu, pattern='^menu:sessions$'),
                CallbackQueryHandler(self.list_sessions, pattern='^session:list'),
                CallbackQueryHandler(self.show_daily_stats, pattern='^session:daily_stats$'),
                CallbackQueryHandler(self.show_health_status, pattern='^session:health$'),
                CallbackQueryHandler(self.show_load_distribution, pattern='^session:load$'),
            ],
            states={
                SELECT_SESSION_ACTION: [
                    CallbackQueryHandler(self.list_sessions, pattern='^session:list'),
                    CallbackQueryHandler(self.show_daily_stats, pattern='^session:daily_stats$'),
                    CallbackQueryHandler(self.show_health_status, pattern='^session:health$'),
                    CallbackQueryHandler(self.show_load_distribution, pattern='^session:load$'),
                    CallbackQueryHandler(self.show_session_details, pattern='^session:details:'),
                    CallbackQueryHandler(self.refresh_session_details, pattern='^session:refresh:'),
                ],
                VIEW_SESSION_DETAILS: [
                    CallbackQueryHandler(self.refresh_session_details, pattern='^session:refresh:'),
                    CallbackQueryHandler(self.list_sessions, pattern='^session:back_to_list$'),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$'),
                CallbackQueryHandler(self.show_session_menu, pattern='^session:menu$'),
                CallbackQueryHandler(self.list_sessions, pattern='^session:back_to_list$'),
            ],
            name="session_conversation",
            persistent=False
        )
    
    async def show_session_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show session management menu with operation options
        
        Requirements: AC-4.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Create or update user session
        self.state_manager.create_user_session(
            user_id=user_id,
            operation='session_management',
            step='menu'
        )
        
        # Build keyboard
        keyboard = KeyboardBuilder.session_menu(user_id=user_id)
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=SESSION_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=SESSION_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
        return SELECT_SESSION_ACTION
    
    async def list_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> int:
        """
        Display list of sessions with pagination
        
        Requirements: AC-4.1, AC-6.7
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        # Extract page from callback data if present
        if query and 'page:' in query.data:
            page = int(query.data.split(':')[-1])
        
        # Get all sessions
        all_sessions = await self._get_all_sessions()
        
        # Calculate pagination
        total_sessions = len(all_sessions)
        total_pages = (total_sessions + self.SESSIONS_PER_PAGE - 1) // self.SESSIONS_PER_PAGE
        total_pages = max(1, total_pages)
        page = max(0, min(page, total_pages - 1))
        
        # Get sessions for current page
        start_idx = page * self.SESSIONS_PER_PAGE
        end_idx = start_idx + self.SESSIONS_PER_PAGE
        page_sessions = all_sessions[start_idx:end_idx]
        
        # Format session list
        message_text = MessageFormatter.format_session_list(
            sessions=page_sessions,
            page=page + 1,
            total_pages=total_pages
        )
        
        # Build keyboard with session buttons
        keyboard = KeyboardBuilder.session_list(
            sessions=page_sessions,
            page=page,
            total_pages=total_pages
        )
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
        return SELECT_SESSION_ACTION
    
    async def show_session_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show detailed information for a specific session
        
        Requirements: AC-4.2
        """
        query = update.callback_query
        await query.answer()
        
        # Extract session name from callback data
        session_name = query.data.split(':', 2)[-1]
        
        # Get session details
        session_stats = await self._get_session_details(session_name)
        
        if not session_stats:
            await query.edit_message_text(
                text="❌ سشن یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Format session details
        message_text = MessageFormatter.format_session_stats(session_stats)
        
        # Build keyboard with refresh and back buttons
        keyboard = KeyboardBuilder.session_details(session_name)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return VIEW_SESSION_DETAILS
    
    async def refresh_session_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Refresh session details display
        
        Requirements: AC-4.2, AC-10.1
        """
        query = update.callback_query
        await query.answer("🔄 در حال بروزرسانی...")
        
        # Extract session name from callback data
        session_name = query.data.split(':', 2)[-1]
        
        # Get updated session details
        session_stats = await self._get_session_details(session_name)
        
        if not session_stats:
            await query.edit_message_text(
                text="❌ سشن یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Format session details
        message_text = MessageFormatter.format_session_stats(session_stats)
        
        # Build keyboard with refresh and back buttons
        keyboard = KeyboardBuilder.session_details(session_name)
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return VIEW_SESSION_DETAILS
    
    async def show_daily_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display daily usage statistics for all sessions
        
        Requirements: AC-4.3
        """
        query = update.callback_query
        await query.answer()
        
        # Get daily statistics
        daily_stats = await self._get_daily_statistics()
        
        # Format statistics message
        message_text = self._format_daily_statistics(daily_stats)
        
        # Build keyboard
        keyboard = KeyboardBuilder.back_to_session_menu()
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_SESSION_ACTION
    
    async def show_health_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display health status for all sessions
        
        Requirements: AC-4.4
        """
        query = update.callback_query
        await query.answer()
        
        # Get health status
        health_status = await self._get_health_status()
        
        # Format health status message
        message_text = self._format_health_status(health_status)
        
        # Build keyboard
        keyboard = KeyboardBuilder.back_to_session_menu()
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_SESSION_ACTION
    
    async def show_load_distribution(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display load distribution across sessions
        
        Requirements: AC-4.5, AC-4.6
        """
        query = update.callback_query
        await query.answer()
        
        # Get load distribution
        load_distribution = await self._get_load_distribution()
        
        # Format load distribution message
        message_text = MessageFormatter.format_load_distribution(load_distribution)
        
        # Build keyboard
        keyboard = KeyboardBuilder.load_distribution_menu()
        
        await query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_SESSION_ACTION
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel current operation"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.state_manager.delete_user_session(user_id)
        
        await query.edit_message_text(
            text="❌ عملیات لغو شد.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    # Helper methods
    
    async def _get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Get list of all sessions with basic info
        
        Returns:
            List of session dicts with basic information
        """
        sessions_list = []
        
        for session_name, session in self.session_manager.sessions.items():
            try:
                # Get basic session info
                is_connected = session.is_connected()
                
                # Get phone number
                phone = "نامشخص"
                if is_connected and hasattr(session, 'client') and session.client:
                    try:
                        me = await session.client.get_me()
                        if me and me.phone:
                            phone = f"+{me.phone}"
                    except Exception as e:
                        self.logger.debug(f"Could not get phone for {session_name}: {e}")
                
                # Check if monitoring
                monitoring = False
                monitoring_channels = []
                # TODO: Get actual monitoring status from session
                
                # Get queue depth
                queue_depth = 0
                if hasattr(session, 'operation_queue'):
                    queue_depth = len(session.operation_queue)
                
                # Get daily stats
                daily_stats = {
                    'messages_read': 0,
                    'groups_scraped': 0,
                    'messages_sent': 0
                }
                # TODO: Get actual daily stats from session
                
                sessions_list.append({
                    'session_name': session_name,
                    'phone': phone,
                    'connected': is_connected,
                    'monitoring': monitoring,
                    'monitoring_channels': monitoring_channels,
                    'queue_depth': queue_depth,
                    'daily_stats': daily_stats
                })
            
            except Exception as e:
                self.logger.error(f"Error getting info for session {session_name}: {e}")
                # Add session with minimal info
                sessions_list.append({
                    'session_name': session_name,
                    'phone': 'خطا',
                    'connected': False,
                    'monitoring': False,
                    'monitoring_channels': [],
                    'queue_depth': 0,
                    'daily_stats': {}
                })
        
        return sessions_list
    
    async def _get_session_details(self, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific session
        
        Args:
            session_name: Name of the session
            
        Returns:
            Dict with detailed session information or None if not found
        """
        session = self.session_manager.sessions.get(session_name)
        if not session:
            return None
        
        try:
            # Get connection status
            is_connected = session.is_connected()
            
            # Get phone number
            phone = "نامشخص"
            if is_connected and hasattr(session, 'client') and session.client:
                try:
                    me = await session.client.get_me()
                    if me and me.phone:
                        phone = f"+{me.phone}"
                except Exception as e:
                    self.logger.debug(f"Could not get phone for {session_name}: {e}")
            
            # Get monitoring status
            monitoring = False
            monitoring_channels = []
            # TODO: Get actual monitoring status from session
            
            # Get active operations
            active_operations = []
            # TODO: Get actual active operations from session
            
            # Get queue depth
            queue_depth = 0
            if hasattr(session, 'operation_queue'):
                queue_depth = len(session.operation_queue)
            
            # Get daily stats
            daily_stats = {
                'messages_read': 0,
                'daily_limit': 500,
                'groups_scraped': 0,
                'scrape_limit': 10,
                'messages_sent': 0
            }
            # TODO: Get actual daily stats from session
            
            # Get health status
            health = {
                'healthy': is_connected,
                'last_check': datetime.now().timestamp()
            }
            # TODO: Get actual health status from health monitor
            
            return {
                'session_name': session_name,
                'phone': phone,
                'connected': is_connected,
                'monitoring': monitoring,
                'monitoring_channels': monitoring_channels,
                'active_operations': active_operations,
                'queue_depth': queue_depth,
                'daily_stats': daily_stats,
                'health': health
            }
        
        except Exception as e:
            self.logger.error(f"Error getting details for session {session_name}: {e}")
            return None
    
    async def _get_daily_statistics(self) -> Dict[str, Any]:
        """
        Get daily statistics for all sessions
        
        Returns:
            Dict with daily statistics
        """
        total_messages_read = 0
        total_groups_scraped = 0
        total_messages_sent = 0
        
        session_stats = []
        
        for session_name, session in self.session_manager.sessions.items():
            try:
                # Get phone number
                phone = "نامشخص"
                if session.is_connected() and hasattr(session, 'client') and session.client:
                    try:
                        me = await session.client.get_me()
                        if me and me.phone:
                            phone = f"+{me.phone}"
                    except:
                        pass
                
                # TODO: Get actual daily stats from session
                messages_read = 0
                groups_scraped = 0
                messages_sent = 0
                
                total_messages_read += messages_read
                total_groups_scraped += groups_scraped
                total_messages_sent += messages_sent
                
                session_stats.append({
                    'phone': phone,
                    'messages_read': messages_read,
                    'groups_scraped': groups_scraped,
                    'messages_sent': messages_sent
                })
            
            except Exception as e:
                self.logger.error(f"Error getting daily stats for {session_name}: {e}")
        
        return {
            'total_messages_read': total_messages_read,
            'total_groups_scraped': total_groups_scraped,
            'total_messages_sent': total_messages_sent,
            'session_stats': session_stats
        }
    
    async def _get_health_status(self) -> List[Dict[str, Any]]:
        """
        Get health status for all sessions
        
        Returns:
            List of session health status dicts
        """
        health_status = []
        
        for session_name, session in self.session_manager.sessions.items():
            try:
                # Get phone number
                phone = "نامشخص"
                if session.is_connected() and hasattr(session, 'client') and session.client:
                    try:
                        me = await session.client.get_me()
                        if me and me.phone:
                            phone = f"+{me.phone}"
                    except:
                        pass
                
                # Get connection status
                is_connected = session.is_connected()
                
                # TODO: Get actual health metrics from health monitor
                health_indicators = {
                    'connection': is_connected,
                    'response_time': 'نامشخص',
                    'error_rate': 0
                }
                
                last_check = datetime.now().timestamp()
                
                health_status.append({
                    'phone': phone,
                    'session_name': session_name,
                    'healthy': is_connected,
                    'indicators': health_indicators,
                    'last_check': last_check
                })
            
            except Exception as e:
                self.logger.error(f"Error getting health status for {session_name}: {e}")
        
        return health_status
    
    async def _get_load_distribution(self) -> List[Dict[str, Any]]:
        """
        Get load distribution across sessions
        
        Returns:
            List of session load dicts
        """
        load_distribution = []
        
        for session_name, session in self.session_manager.sessions.items():
            try:
                # Get phone number
                phone = "نامشخص"
                if session.is_connected() and hasattr(session, 'client') and session.client:
                    try:
                        me = await session.client.get_me()
                        if me and me.phone:
                            phone = f"+{me.phone}"
                    except:
                        pass
                
                # Get current load
                current_load = self.session_manager.session_load.get(session_name, 0)
                
                # Get queue depth
                queue_depth = 0
                if hasattr(session, 'operation_queue'):
                    queue_depth = len(session.operation_queue)
                
                load_distribution.append({
                    'phone': phone,
                    'session_name': session_name,
                    'current_load': current_load,
                    'queue_depth': queue_depth
                })
            
            except Exception as e:
                self.logger.error(f"Error getting load for {session_name}: {e}")
        
        return load_distribution
    
    def _format_daily_statistics(self, stats: Dict[str, Any]) -> str:
        """
        Format daily statistics message
        
        Args:
            stats: Daily statistics dict
            
        Returns:
            Formatted message string
        """
        result = "📊 **آمار روزانه**\n\n"
        result += f"**کل عملیات امروز:**\n"
        result += f"• پیام‌های خوانده شده: {stats['total_messages_read']}\n"
        result += f"• گروه‌های اسکرپ شده: {stats['total_groups_scraped']}\n"
        result += f"• پیام‌های ارسال شده: {stats['total_messages_sent']}\n\n"
        
        if stats['session_stats']:
            result += "**آمار به تفکیک سشن:**\n\n"
            for session_stat in stats['session_stats']:
                result += f"📱 {session_stat['phone']}\n"
                result += f"   • پیام‌ها: {session_stat['messages_read']}\n"
                result += f"   • گروه‌ها: {session_stat['groups_scraped']}\n"
                result += f"   • ارسال: {session_stat['messages_sent']}\n\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        result += f"\n⏰ آخرین بروزرسانی: {now}"
        
        return result
    
    def _format_health_status(self, health_status: List[Dict[str, Any]]) -> str:
        """
        Format health status message
        
        Args:
            health_status: List of health status dicts
            
        Returns:
            Formatted message string
        """
        result = "💚 **وضعیت سلامت سشن‌ها**\n\n"
        
        if not health_status:
            result += "هیچ سشنی یافت نشد."
            return result
        
        healthy_count = sum(1 for s in health_status if s['healthy'])
        total_count = len(health_status)
        
        result += f"**خلاصه:** {healthy_count}/{total_count} سشن سالم\n\n"
        
        for session in health_status:
            status_icon = "✅" if session['healthy'] else "❌"
            status_text = "سالم" if session['healthy'] else "مشکل دارد"
            
            result += f"{status_icon} **{session['phone']}**\n"
            result += f"   وضعیت: {status_text}\n"
            
            # Format last check time
            last_check = session.get('last_check')
            if last_check:
                time_ago = MessageFormatter._format_time_ago(last_check)
                result += f"   آخرین بررسی: {time_ago}\n"
            
            result += "\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        result += f"\n⏰ آخرین بروزرسانی: {now}"
        
        return result
