"""
System Status Handler for Telegram Bot Panel

This module provides comprehensive system status display with auto-refresh functionality.

Requirements: AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.5, AC-5.6
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)

from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .auth import admin_only
from .logging_config import get_logger
from .error_handler import BotErrorHandler, ErrorContext


class SystemStatusHandler:
    """
    Handler for system status display and management
    
    Provides comprehensive system statistics including:
    - Session statistics (total, connected, monitoring)
    - Active operations by type
    - Today's statistics (messages, groups, reactions)
    - Monitoring status
    - Auto-refresh functionality
    
    Requirements:
        - AC-5.1: Display total sessions and connection status
        - AC-5.2: Display active operations by type
        - AC-5.3: Display today's statistics
        - AC-5.4: Display monitoring status
        - AC-5.5: Auto-refresh within 2 seconds
        - AC-5.6: Include timestamp
    """
    
    def __init__(self, session_manager):
        """
        Initialize system status handler
        
        Args:
            session_manager: TelegramManagerApp instance for backend operations
        """
        self.session_manager = session_manager
        self.logger = get_logger("SystemStatusHandler")
        self.error_handler = BotErrorHandler(logger_name="SystemStatusHandler")
        
        self.logger.info("SystemStatusHandler initialized")
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for system status
        
        Returns:
            ConversationHandler configured for system status operations
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_system_status, pattern='^system_status$'),
                CallbackQueryHandler(self.show_system_status, pattern='^action:status$'),
            ],
            states={},
            fallbacks=[
                CallbackQueryHandler(self.refresh_status, pattern='^action:refresh_status$'),
                CallbackQueryHandler(self.handle_back, pattern='^nav:main$'),
            ],
            name="system_status_handler",
            persistent=False
        )
    
    @admin_only
    async def show_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Display comprehensive system status
        
        Shows:
        - Total sessions and connection status
        - Active operations by type
        - Today's statistics
        - Monitoring status
        - Timestamp
        
        Requirements: AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.6
        """
        try:
            query = update.callback_query
            if query:
                await query.answer()
            
            user_id = update.effective_user.id
            
            # Log admin action
            self.logger.log_admin_action(
                user_id=user_id,
                action="show_system_status",
                details={'source': 'callback' if query else 'command'}
            )
            
            # Start timing for performance requirement (AC-5.5)
            start_time = time.time()
            
            # Get comprehensive system status
            status_data = await self._get_system_status()
            
            # Format using MessageFormatter
            status_message = MessageFormatter.format_system_status(status_data)
            
            # Create keyboard with refresh button
            keyboard = KeyboardBuilder.refresh_back(
                refresh_data="action:refresh_status",
                back_data="nav:main"
            )
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            self.logger.debug(f"System status retrieved in {elapsed_time:.2f}s")
            
            # Send or edit message
            if query:
                await query.edit_message_text(
                    status_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    status_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            self.logger.error(
                "Error in show_system_status",
                user_id=update.effective_user.id if update.effective_user else None,
                operation="show_system_status",
                error=str(e)
            )
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="show_system_status"
                ),
                retry_callback="action:refresh_status"
            )
    
    @admin_only
    async def refresh_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Refresh system status display
        
        Updates all statistics and ensures refresh completes within 2 seconds.
        
        Requirements: AC-5.5
        """
        try:
            query = update.callback_query
            await query.answer("🔄 در حال بروزرسانی...")
            
            user_id = update.effective_user.id
            
            # Log admin action
            self.logger.log_admin_action(
                user_id=user_id,
                action="refresh_system_status",
                details={'source': 'refresh_button'}
            )
            
            # Start timing for performance requirement (AC-5.5: within 2 seconds)
            start_time = time.time()
            
            # Get fresh system status
            status_data = await self._get_system_status()
            
            # Format using MessageFormatter
            status_message = MessageFormatter.format_system_status(status_data)
            
            # Create keyboard with refresh button
            keyboard = KeyboardBuilder.refresh_back(
                refresh_data="action:refresh_status",
                back_data="nav:main"
            )
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            self.logger.debug(f"System status refreshed in {elapsed_time:.2f}s")
            
            # Verify performance requirement
            if elapsed_time > 2.0:
                self.logger.warning(
                    f"System status refresh took {elapsed_time:.2f}s (exceeds 2s requirement)",
                    user_id=user_id,
                    operation="refresh_status"
                )
            
            # Update message
            await query.edit_message_text(
                status_message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(
                "Error in refresh_status",
                user_id=update.effective_user.id if update.effective_user else None,
                operation="refresh_status",
                error=str(e)
            )
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="refresh_status"
                ),
                retry_callback="action:refresh_status"
            )
    
    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back navigation to main menu"""
        query = update.callback_query
        await query.answer()
        
        # This will be handled by the main bot's navigation handler
        # Just acknowledge the callback here
        pass
    
    async def _get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status data
        
        Collects all system statistics including:
        - Session counts and connection status
        - Active operations by type
        - Today's statistics
        - Monitoring status
        
        Returns:
            Dict with all system statistics
            
        Requirements: AC-5.1, AC-5.2, AC-5.3, AC-5.4
        """
        try:
            # Get session stats from session manager
            stats = await self.session_manager.get_session_stats()
            
            # Calculate session statistics (AC-5.1)
            total_sessions = len(stats)
            connected_sessions = sum(1 for s in stats.values() if s.get('connected', False))
            monitoring_sessions = sum(1 for s in stats.values() if s.get('monitoring', False))
            
            # Calculate active operations by type (AC-5.2)
            active_scrapes = sum(
                1 for s in stats.values() 
                if s.get('current_operation') == 'scraping'
            )
            active_sends = sum(
                1 for s in stats.values() 
                if s.get('current_operation') == 'sending'
            )
            active_monitoring = monitoring_sessions
            
            # Calculate today's statistics (AC-5.3)
            messages_read = sum(
                s.get('daily_stats', {}).get('messages_read', 0) 
                for s in stats.values()
            )
            groups_scraped = sum(
                s.get('daily_stats', {}).get('groups_scraped_today', 0) 
                for s in stats.values()
            )
            messages_sent = sum(
                s.get('daily_stats', {}).get('messages_sent', 0) 
                for s in stats.values()
            )
            
            # Get monitoring statistics (AC-5.4)
            monitoring_targets = getattr(self.session_manager, 'monitoring_targets', [])
            active_channels = len([
                t for t in monitoring_targets 
                if (isinstance(t, dict) and t.get('enabled', True)) or 
                   (hasattr(t, 'enabled') and t.enabled)
            ])
            
            # Calculate reactions sent today
            reactions_sent = 0
            reactions_today = 0
            
            # Try to get reaction stats from monitoring targets
            for target in monitoring_targets:
                if isinstance(target, dict):
                    stats_dict = target.get('stats', {})
                    reactions_sent += stats_dict.get('reactions_sent', 0)
                    reactions_today += stats_dict.get('reactions_today', 0)
                elif hasattr(target, 'stats'):
                    reactions_sent += getattr(target.stats, 'reactions_sent', 0)
                    reactions_today += getattr(target.stats, 'reactions_today', 0)
            
            return {
                'total_sessions': total_sessions,
                'connected_sessions': connected_sessions,
                'monitoring_sessions': monitoring_sessions,
                'active_scrapes': active_scrapes,
                'active_sends': active_sends,
                'active_monitoring': active_monitoring,
                'messages_read': messages_read,
                'groups_scraped': groups_scraped,
                'messages_sent': messages_sent,
                'reactions_sent': reactions_sent,
                'active_channels': active_channels,
                'reactions_today': reactions_today
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            # Return empty stats on error
            return {
                'total_sessions': 0,
                'connected_sessions': 0,
                'monitoring_sessions': 0,
                'active_scrapes': 0,
                'active_sends': 0,
                'active_monitoring': 0,
                'messages_read': 0,
                'groups_scraped': 0,
                'messages_sent': 0,
                'reactions_sent': 0,
                'active_channels': 0,
                'reactions_today': 0
            }
    
    def _format_status_message(self, status_data: Dict[str, Any]) -> str:
        """
        Format system status message (deprecated - use MessageFormatter instead)
        
        This method is kept for backward compatibility but delegates to MessageFormatter.
        
        Args:
            status_data: Dictionary with system statistics
            
        Returns:
            Formatted status message string
        """
        return MessageFormatter.format_system_status(status_data)
