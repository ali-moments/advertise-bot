"""
Statistics Handler for Telegram Bot Panel

This module provides bot interface for viewing comprehensive statistics
for all operation types.

Requirements: AC-17.1, AC-17.2, AC-17.3, AC-17.4
"""

import logging
from typing import Optional
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)

from .statistics_manager import StatisticsManager
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .auth import admin_only
from .error_handler import BotErrorHandler, ErrorContext


# Conversation states
SELECT_STATS_TYPE = 0


class StatisticsHandler:
    """
    Handler for statistics display operations
    
    Provides access to:
    - Scraping statistics (AC-17.1)
    - Sending statistics (AC-17.2)
    - Monitoring statistics (AC-17.3)
    - Session statistics (AC-17.4)
    """
    
    def __init__(
        self,
        statistics_manager: StatisticsManager,
        error_handler: BotErrorHandler
    ):
        """
        Initialize statistics handler
        
        Args:
            statistics_manager: StatisticsManager instance
            error_handler: BotErrorHandler instance
        """
        self.statistics_manager = statistics_manager
        self.error_handler = error_handler
        self.logger = logging.getLogger("StatisticsHandler")
        
        self.logger.info("StatisticsHandler initialized")

    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for statistics operations
        
        Returns:
            ConversationHandler configured for statistics flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_statistics_menu, pattern='^menu:statistics$'),
                CallbackQueryHandler(self.show_scraping_stats, pattern='^stats:scraping$'),
                CallbackQueryHandler(self.show_sending_stats, pattern='^stats:sending$'),
                CallbackQueryHandler(self.show_monitoring_stats, pattern='^stats:monitoring$'),
                CallbackQueryHandler(self.show_session_stats, pattern='^stats:sessions$'),
                CallbackQueryHandler(self.show_comprehensive_stats, pattern='^stats:comprehensive$'),
            ],
            states={
                SELECT_STATS_TYPE: [
                    CallbackQueryHandler(self.show_scraping_stats, pattern='^stats:scraping$'),
                    CallbackQueryHandler(self.show_sending_stats, pattern='^stats:sending$'),
                    CallbackQueryHandler(self.show_monitoring_stats, pattern='^stats:monitoring$'),
                    CallbackQueryHandler(self.show_session_stats, pattern='^stats:sessions$'),
                    CallbackQueryHandler(self.show_comprehensive_stats, pattern='^stats:comprehensive$'),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.show_statistics_menu, pattern='^menu:statistics$'),
                CallbackQueryHandler(self.handle_back, pattern='^nav:main$'),
            ],
            name="statistics_conversation",
            persistent=False,
            per_message=True
        )
    
    @admin_only
    async def show_statistics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show statistics menu with options
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        menu_text = (
            "📊 **آمار و تحلیل**\n\n"
            "لطفاً نوع آماری که می‌خواهید مشاهده کنید را انتخاب کنید:"
        )
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [
                InlineKeyboardButton("📥 آمار اسکرپینگ", callback_data="stats:scraping"),
                InlineKeyboardButton("📤 آمار ارسال", callback_data="stats:sending")
            ],
            [
                InlineKeyboardButton("📡 آمار مانیتورینگ", callback_data="stats:monitoring"),
                InlineKeyboardButton("💻 آمار سشن‌ها", callback_data="stats:sessions")
            ],
            [
                InlineKeyboardButton("📈 آمار جامع", callback_data="stats:comprehensive")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="nav:main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return SELECT_STATS_TYPE
    
    @admin_only
    async def show_scraping_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display scraping statistics
        
        Requirements: AC-17.1
        """
        query = update.callback_query
        await query.answer()
        
        try:
            # Get scraping statistics
            stats = self.statistics_manager.get_scraping_statistics()
            
            # Format message
            message_text = self._format_scraping_statistics(stats)
            
            # Build keyboard
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats:scraping")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="menu:statistics"),
                    InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECT_STATS_TYPE
        
        except Exception as e:
            self.logger.error(f"Error showing scraping stats: {e}")
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id,
                    operation="show_scraping_stats"
                )
            )
            return ConversationHandler.END

    
    @admin_only
    async def show_sending_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display sending statistics
        
        Requirements: AC-17.2
        """
        query = update.callback_query
        await query.answer()
        
        try:
            # Get sending statistics
            stats = self.statistics_manager.get_sending_statistics()
            
            # Format message
            message_text = self._format_sending_statistics(stats)
            
            # Build keyboard
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats:sending")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="menu:statistics"),
                    InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECT_STATS_TYPE
        
        except Exception as e:
            self.logger.error(f"Error showing sending stats: {e}")
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id,
                    operation="show_sending_stats"
                )
            )
            return ConversationHandler.END
    
    @admin_only
    async def show_monitoring_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display monitoring statistics
        
        Requirements: AC-17.3
        """
        query = update.callback_query
        await query.answer()
        
        try:
            # Get monitoring statistics
            stats = self.statistics_manager.get_monitoring_statistics()
            
            # Format message
            message_text = self._format_monitoring_statistics(stats)
            
            # Build keyboard
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats:monitoring")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="menu:statistics"),
                    InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECT_STATS_TYPE
        
        except Exception as e:
            self.logger.error(f"Error showing monitoring stats: {e}")
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id,
                    operation="show_monitoring_stats"
                )
            )
            return ConversationHandler.END
    
    @admin_only
    async def show_session_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display session statistics
        
        Requirements: AC-17.4
        """
        query = update.callback_query
        await query.answer()
        
        try:
            # Get session statistics
            all_stats = self.statistics_manager.get_all_session_statistics()
            
            # Format message
            message_text = self._format_session_statistics(all_stats)
            
            # Build keyboard
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats:sessions")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="menu:statistics"),
                    InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECT_STATS_TYPE
        
        except Exception as e:
            self.logger.error(f"Error showing session stats: {e}")
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id,
                    operation="show_session_stats"
                )
            )
            return ConversationHandler.END
    
    @admin_only
    async def show_comprehensive_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display comprehensive statistics for all operations
        """
        query = update.callback_query
        await query.answer()
        
        try:
            # Get comprehensive statistics
            stats = self.statistics_manager.get_comprehensive_statistics()
            
            # Format message
            message_text = self._format_comprehensive_statistics(stats)
            
            # Build keyboard
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats:comprehensive")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="menu:statistics"),
                    InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECT_STATS_TYPE
        
        except Exception as e:
            self.logger.error(f"Error showing comprehensive stats: {e}")
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id,
                    operation="show_comprehensive_stats"
                )
            )
            return ConversationHandler.END
    
    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle back navigation"""
        query = update.callback_query
        await query.answer()
        return ConversationHandler.END

    
    # Formatting Methods
    
    def _format_scraping_statistics(self, stats: dict) -> str:
        """
        Format scraping statistics message
        
        Requirements: AC-17.1
        """
        message = "📥 **آمار اسکرپینگ**\n\n"
        
        message += "**آمار کلی:**\n"
        message += f"• کل اعضای اسکرپ شده: {stats['total_members_scraped']:,}\n"
        message += f"• کل گروه‌های پردازش شده: {stats['total_groups_processed']}\n"
        message += f"• اسکرپ‌های موفق: {stats['successful_scrapes']}\n"
        message += f"• اسکرپ‌های ناموفق: {stats['failed_scrapes']}\n"
        message += f"• نرخ موفقیت: {stats['success_rate']:.1f}%\n\n"
        
        message += "**آمار امروز:**\n"
        message += f"• اعضای اسکرپ شده: {stats['daily_members_scraped']:,}\n"
        message += f"• گروه‌های پردازش شده: {stats['daily_groups_processed']}\n\n"
        
        if stats['last_scrape_time']:
            last_scrape = datetime.fromtimestamp(stats['last_scrape_time'])
            message += f"⏰ آخرین اسکرپ: {last_scrape.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message += f"\n🕐 بروزرسانی: {now}"
        
        return message
    
    def _format_sending_statistics(self, stats: dict) -> str:
        """
        Format sending statistics message
        
        Requirements: AC-17.2
        """
        message = "📤 **آمار ارسال پیام**\n\n"
        
        message += "**آمار کلی:**\n"
        message += f"• کل پیام‌های ارسال شده: {stats['total_messages_sent']:,}\n"
        message += f"• ارسال‌های موفق: {stats['successful_sends']:,}\n"
        message += f"• ارسال‌های ناموفق: {stats['failed_sends']:,}\n"
        message += f"• نرخ تحویل: {stats['delivery_rate']:.1f}%\n\n"
        
        message += "**آمار امروز:**\n"
        message += f"• پیام‌های ارسال شده: {stats['daily_messages_sent']:,}\n"
        message += f"• ارسال‌های موفق: {stats['daily_successful_sends']:,}\n\n"
        
        # Top failure reasons
        if stats['top_failure_reasons']:
            message += "**دلایل اصلی خطا:**\n"
            for reason, count in stats['top_failure_reasons']:
                message += f"• {reason}: {count}\n"
            message += "\n"
        
        if stats['last_send_time']:
            last_send = datetime.fromtimestamp(stats['last_send_time'])
            message += f"⏰ آخرین ارسال: {last_send.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message += f"\n🕐 بروزرسانی: {now}"
        
        return message
    
    def _format_monitoring_statistics(self, stats: dict) -> str:
        """
        Format monitoring statistics message
        
        Requirements: AC-17.3
        """
        message = "📡 **آمار مانیتورینگ**\n\n"
        
        message += "**آمار کلی:**\n"
        message += f"• کل ری‌اکشن‌های ارسال شده: {stats['total_reactions_sent']:,}\n"
        message += f"• کل پیام‌های پردازش شده: {stats['total_messages_processed']:,}\n"
        
        # Calculate uptime
        uptime_hours = stats['uptime_seconds'] / 3600
        message += f"• زمان فعالیت: {uptime_hours:.1f} ساعت\n\n"
        
        message += "**آمار امروز:**\n"
        message += f"• ری‌اکشن‌های ارسال شده: {stats['daily_reactions_sent']:,}\n"
        message += f"• پیام‌های پردازش شده: {stats['daily_messages_processed']:,}\n\n"
        
        # Per-channel statistics
        if stats['channel_details']:
            message += "**آمار به تفکیک کانال:**\n\n"
            for channel in stats['channel_details'][:5]:  # Show top 5
                message += f"📢 **{channel['channel_id']}**\n"
                message += f"   • ری‌اکشن‌ها: {channel['reactions_sent']}\n"
                message += f"   • پیام‌ها: {channel['messages_processed']}\n"
                message += f"   • نرخ تعامل: {channel['engagement_rate']:.1f}%\n\n"
            
            if len(stats['channel_details']) > 5:
                message += f"... و {len(stats['channel_details']) - 5} کانال دیگر\n\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message += f"🕐 بروزرسانی: {now}"
        
        return message
    
    def _format_session_statistics(self, all_stats: list) -> str:
        """
        Format session statistics message
        
        Requirements: AC-17.4
        """
        message = "💻 **آمار سشن‌ها**\n\n"
        
        if not all_stats:
            message += "هیچ آماری برای سشن‌ها یافت نشد."
            return message
        
        # Calculate totals
        total_messages_read = sum(s['messages_read'] for s in all_stats)
        total_groups_scraped = sum(s['groups_scraped'] for s in all_stats)
        total_messages_sent = sum(s['messages_sent'] for s in all_stats)
        total_reactions_sent = sum(s['reactions_sent'] for s in all_stats)
        
        message += "**خلاصه کلی:**\n"
        message += f"• کل سشن‌ها: {len(all_stats)}\n"
        message += f"• کل پیام‌های خوانده شده: {total_messages_read:,}\n"
        message += f"• کل گروه‌های اسکرپ شده: {total_groups_scraped}\n"
        message += f"• کل پیام‌های ارسال شده: {total_messages_sent:,}\n"
        message += f"• کل ری‌اکشن‌های ارسال شده: {total_reactions_sent:,}\n\n"
        
        # Show top sessions by activity
        message += "**سشن‌های پرفعالیت:**\n\n"
        
        # Sort by total activity
        sorted_stats = sorted(
            all_stats,
            key=lambda s: s['messages_read'] + s['messages_sent'] + s['reactions_sent'],
            reverse=True
        )
        
        for stats in sorted_stats[:5]:  # Show top 5
            message += f"📱 **{stats['phone']}**\n"
            message += f"   • پیام‌های خوانده شده: {stats['messages_read']}\n"
            message += f"   • گروه‌های اسکرپ شده: {stats['groups_scraped']}\n"
            message += f"   • پیام‌های ارسال شده: {stats['messages_sent']}\n"
            message += f"   • ری‌اکشن‌ها: {stats['reactions_sent']}\n"
            
            # Show limit usage
            if stats['message_limit_usage_percent'] > 0:
                message += f"   • استفاده از محدودیت پیام: {stats['message_limit_usage_percent']:.1f}%\n"
            
            message += "\n"
        
        if len(sorted_stats) > 5:
            message += f"... و {len(sorted_stats) - 5} سشن دیگر\n\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message += f"🕐 بروزرسانی: {now}"
        
        return message
    
    def _format_comprehensive_statistics(self, stats: dict) -> str:
        """Format comprehensive statistics message"""
        message = "📈 **آمار جامع سیستم**\n\n"
        
        # Scraping summary
        scraping = stats['scraping']
        message += "**📥 اسکرپینگ:**\n"
        message += f"• اعضا: {scraping['total_members_scraped']:,}\n"
        message += f"• گروه‌ها: {scraping['total_groups_processed']}\n"
        message += f"• نرخ موفقیت: {scraping['success_rate']:.1f}%\n\n"
        
        # Sending summary
        sending = stats['sending']
        message += "**📤 ارسال:**\n"
        message += f"• پیام‌ها: {sending['total_messages_sent']:,}\n"
        message += f"• نرخ تحویل: {sending['delivery_rate']:.1f}%\n\n"
        
        # Monitoring summary
        monitoring = stats['monitoring']
        message += "**📡 مانیتورینگ:**\n"
        message += f"• ری‌اکشن‌ها: {monitoring['total_reactions_sent']:,}\n"
        message += f"• پیام‌های پردازش شده: {monitoring['total_messages_processed']:,}\n"
        uptime_hours = monitoring['uptime_seconds'] / 3600
        message += f"• زمان فعالیت: {uptime_hours:.1f} ساعت\n\n"
        
        # Session summary
        sessions = stats['sessions']
        message += f"**💻 سشن‌ها:** {len(sessions)} سشن فعال\n\n"
        
        # Add timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message += f"🕐 بروزرسانی: {now}"
        
        return message
