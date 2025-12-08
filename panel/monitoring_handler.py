"""
Monitoring Handler - Manages channel monitoring operations through bot interface

This module handles:
- Channel list display with pagination
- Adding new channels to monitoring
- Removing channels from monitoring
- Editing reaction configurations
- Editing cooldown periods
- Global monitoring control (start/stop all)
- Per-channel monitoring control
- Monitoring statistics display

Requirements: AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5, AC-3.6, AC-3.7, AC-3.8, AC-3.9, AC-3.10
"""

import asyncio
import logging
import re
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from telegram_manager.manager import TelegramSessionManager
from .state_manager import StateManager, MonitoringConfig
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .error_handler import BotErrorHandler, ErrorContext
from .validators import InputValidator, ValidationErrorHandler
from .persian_text import (
    MONITORING_MENU_TEXT, BTN_LIST_CHANNELS, BTN_ADD_CHANNEL,
    BTN_REMOVE_CHANNEL, BTN_EDIT_REACTIONS, BTN_EDIT_COOLDOWN,
    BTN_START_MONITORING, BTN_STOP_MONITORING, BTN_MONITORING_STATS,
    PROMPT_CHANNEL_LINK, PROMPT_REACTIONS, PROMPT_COOLDOWN,
    SUCCESS_MONITORING_ADDED, CONFIRM_DELETE, ERROR_INVALID_INPUT
)


# Conversation states
SELECT_MONITORING_ACTION = 0
GET_CHANNEL_ID = 1
GET_REACTIONS = 2
GET_COOLDOWN = 3
CONFIRM_REMOVE = 4
EDIT_REACTIONS_STATE = 5
EDIT_COOLDOWN_STATE = 6


class MonitoringHandler:
    """
    Handler for all monitoring operations
    
    Manages conversation flows for:
    - Displaying channel list with pagination
    - Adding new channels to monitoring
    - Removing channels from monitoring
    - Editing reaction configurations
    - Editing cooldown periods
    - Starting/stopping global monitoring
    - Toggling per-channel monitoring
    - Displaying monitoring statistics
    
    Requirements: AC-3.1 through AC-3.10
    """
    
    # Pagination settings
    CHANNELS_PER_PAGE = 5
    
    def __init__(
        self,
        session_manager: TelegramSessionManager,
        state_manager: StateManager,
        error_handler: BotErrorHandler
    ):
        """
        Initialize monitoring handler
        
        Args:
            session_manager: TelegramSessionManager instance
            state_manager: StateManager instance
            error_handler: BotErrorHandler instance
        """
        self.session_manager = session_manager
        self.state_manager = state_manager
        self.error_handler = error_handler
        self.logger = logging.getLogger("MonitoringHandler")
        
        self.logger.info("MonitoringHandler initialized")

    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for monitoring operations
        
        Returns:
            ConversationHandler configured for monitoring flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_monitoring_menu, pattern='^menu:monitoring$'),
                CallbackQueryHandler(self.list_channels, pattern='^monitor:list'),
                CallbackQueryHandler(self.start_add_channel, pattern='^monitor:add$'),
                CallbackQueryHandler(self.show_statistics, pattern='^monitor:stats$'),
                CallbackQueryHandler(self.start_global_monitoring, pattern='^monitor:start$'),
                CallbackQueryHandler(self.stop_global_monitoring, pattern='^monitor:stop$'),
            ],
            states={
                SELECT_MONITORING_ACTION: [
                    CallbackQueryHandler(self.list_channels, pattern='^monitor:list'),
                    CallbackQueryHandler(self.start_add_channel, pattern='^monitor:add$'),
                    CallbackQueryHandler(self.show_statistics, pattern='^monitor:stats$'),
                    CallbackQueryHandler(self.start_global_monitoring, pattern='^monitor:start$'),
                    CallbackQueryHandler(self.stop_global_monitoring, pattern='^monitor:stop$'),
                ],
                GET_CHANNEL_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_channel_id_input)
                ],
                GET_REACTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_reactions_input)
                ],
                GET_COOLDOWN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_cooldown_input)
                ],
                CONFIRM_REMOVE: [
                    CallbackQueryHandler(self.execute_remove_channel, pattern='^confirm:remove'),
                    CallbackQueryHandler(self.cancel_remove, pattern='^cancel:remove')
                ],
                EDIT_REACTIONS_STATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_reactions_input)
                ],
                EDIT_COOLDOWN_STATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_cooldown_input)
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$'),
                CallbackQueryHandler(self.show_monitoring_menu, pattern='^menu:monitoring$'),
            ],
            name="monitoring_conversation",
            persistent=False
        )

    
    async def show_monitoring_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show monitoring menu with operation options
        
        Requirements: AC-3.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Create or update user session
        self.state_manager.create_user_session(
            user_id=user_id,
            operation='monitoring',
            step='menu'
        )
        
        # Build keyboard
        keyboard = KeyboardBuilder.monitor_menu(user_id=user_id)
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=MONITORING_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=MONITORING_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
        return SELECT_MONITORING_ACTION

    
    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> int:
        """
        Display list of monitored channels with pagination
        
        Requirements: AC-3.1, AC-3.6, AC-6.7
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        # Extract page from callback data if present
        if query and 'page:' in query.data:
            page = int(query.data.split(':')[-1])
        
        # Get all monitoring configurations
        all_configs = self.state_manager.get_all_monitoring_configs()
        
        # Calculate pagination
        total_channels = len(all_configs)
        total_pages = (total_channels + self.CHANNELS_PER_PAGE - 1) // self.CHANNELS_PER_PAGE
        total_pages = max(1, total_pages)
        page = max(0, min(page, total_pages - 1))
        
        # Get channels for current page
        start_idx = page * self.CHANNELS_PER_PAGE
        end_idx = start_idx + self.CHANNELS_PER_PAGE
        page_configs = all_configs[start_idx:end_idx]
        
        # Format channel list
        channels_data = []
        for config in page_configs:
            channels_data.append({
                'chat_id': config.chat_id,
                'reactions': config.reactions,
                'cooldown': config.cooldown,
                'enabled': config.enabled,
                'stats': config.stats
            })
        
        message_text = MessageFormatter.format_channel_list(
            channels=channels_data,
            page=page + 1,
            total_pages=total_pages
        )
        
        # Build keyboard with channel actions
        keyboard = []
        
        # Add channel buttons
        for config in page_configs:
            status_icon = "✅" if config.enabled else "❌"
            button_text = f"{status_icon} {config.chat_id}"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"monitor:channel:{config.chat_id}"
                )
            ])
        
        # Add pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                "⏮️ قبلی",
                callback_data=f"monitor:list:page:{page-1}"
            ))
        
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(
                f"صفحه {page+1}/{total_pages}",
                callback_data="nav:noop"
            ))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                "⏭️ بعدی",
                callback_data=f"monitor:list:page:{page+1}"
            ))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add action buttons
        keyboard.append([
            InlineKeyboardButton("➕ افزودن کانال", callback_data="monitor:add"),
            InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"monitor:list:page:{page}")
        ])
        
        # Add navigation buttons
        keyboard.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu:monitoring"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return SELECT_MONITORING_ACTION

    
    async def start_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start add channel flow
        
        Requirements: AC-3.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Create or update session
        session = self.state_manager.get_user_session(user_id)
        if not session:
            self.state_manager.create_user_session(
                user_id=user_id,
                operation='monitoring',
                step='get_channel_id',
                data={'action': 'add'}
            )
        else:
            self.state_manager.update_user_session(
                user_id=user_id,
                step='get_channel_id',
                data={'action': 'add'}
            )
        
        # Prompt for channel identifier
        await query.edit_message_text(
            text=PROMPT_CHANNEL_LINK,
            parse_mode='Markdown'
        )
        
        return GET_CHANNEL_ID
    
    async def handle_channel_id_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle channel identifier input
        
        Requirements: AC-3.2, AC-13.1
        """
        user_id = update.effective_user.id
        channel_id = update.message.text.strip()
        
        # Validate channel identifier
        if not self._validate_channel_identifier(channel_id):
            await update.message.reply_text(
                text="❌ شناسه کانال نامعتبر است. لطفاً یک شناسه معتبر وارد کنید.\n\n"
                     "فرمت‌های معتبر:\n"
                     "• @channelname\n"
                     "• https://t.me/channelname\n"
                     "• شناسه عددی کانال",
                parse_mode='Markdown'
            )
            return GET_CHANNEL_ID
        
        # Store channel identifier
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'channel_id': channel_id}
        )
        
        # Prompt for reactions
        await update.message.reply_text(
            text=PROMPT_REACTIONS,
            parse_mode='Markdown'
        )
        
        return GET_REACTIONS

    
    async def handle_reactions_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle reactions input
        
        Requirements: AC-3.2, AC-13.3
        """
        user_id = update.effective_user.id
        reactions_text = update.message.text.strip()
        
        # Parse reactions
        success, reactions = self._parse_reactions(reactions_text)
        
        if not success:
            await update.message.reply_text(
                text=f"❌ فرمت ری‌اکشن‌ها نامعتبر است.\n\n{reactions}\n\n"
                     "فرمت صحیح: `👍:5 ❤️:3 🔥:2`",
                parse_mode='Markdown'
            )
            return GET_REACTIONS
        
        # Store reactions
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'reactions': reactions}
        )
        
        # Prompt for cooldown
        await update.message.reply_text(
            text=PROMPT_COOLDOWN,
            parse_mode='Markdown'
        )
        
        return GET_COOLDOWN
    
    async def handle_cooldown_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle cooldown input
        
        Requirements: AC-3.2, AC-13.4, AC-13.5
        """
        user_id = update.effective_user.id
        cooldown_text = update.message.text.strip()
        
        # Validate cooldown using centralized validator
        validation_result = InputValidator.validate_cooldown(cooldown_text)
        
        if not validation_result.valid:
            error_message = ValidationErrorHandler.format_validation_error(
                validation_result,
                context="📡 مانیتورینگ کانال"
            )
            await update.message.reply_text(
                text=error_message,
                parse_mode='Markdown'
            )
            # Preserve session state and allow retry
            return GET_COOLDOWN
        
        # Get validated cooldown value
        cooldown = float(validation_result.normalized_value)
        
        # Get session data
        session = self.state_manager.get_user_session(user_id)
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        channel_id = session.get_data('channel_id')
        reactions = session.get_data('reactions')
        
        # Create monitoring configuration
        config = self.state_manager.create_monitoring_config(
            chat_id=channel_id,
            reactions=reactions,
            cooldown=cooldown,
            enabled=True
        )
        
        # Format success message
        success_msg = SUCCESS_MONITORING_ADDED.format(
            channel=channel_id,
            reactions=" ".join([f"{r['emoji']}({r['weight']})" for r in reactions]),
            cooldown=cooldown
        )
        
        await update.message.reply_text(
            text=success_msg,
            parse_mode='Markdown'
        )
        
        # Clean up session
        self.state_manager.delete_user_session(user_id)
        
        # Show monitoring menu
        keyboard = KeyboardBuilder.monitor_menu(user_id=user_id)
        await update.message.reply_text(
            text=MONITORING_MENU_TEXT,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    
    async def start_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> int:
        """
        Start remove channel flow
        
        Requirements: AC-3.3, AC-6.8
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Check if channel exists
        config = self.state_manager.get_monitoring_config(chat_id)
        if not config:
            await query.edit_message_text(
                text="❌ کانال یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='confirm_remove',
            data={'channel_id': chat_id}
        )
        
        # Show confirmation dialog
        confirm_text = CONFIRM_DELETE.format(item=f"کانال {chat_id}")
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:remove'),
                InlineKeyboardButton("❌ انصراف", callback_data='cancel:remove')
            ]
        ])
        
        await query.edit_message_text(
            text=confirm_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_REMOVE
    
    async def execute_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Execute channel removal
        
        Requirements: AC-3.3
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await query.edit_message_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        channel_id = session.get_data('channel_id')
        
        # Remove monitoring configuration
        success = self.state_manager.delete_monitoring_config(channel_id)
        
        if success:
            await query.edit_message_text(
                text=f"✅ کانال {channel_id} از مانیتورینگ حذف شد.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                text=f"❌ خطا در حذف کانال {channel_id}.",
                parse_mode='Markdown'
            )
        
        # Clean up session
        self.state_manager.delete_user_session(user_id)
        
        return ConversationHandler.END
    
    async def cancel_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel channel removal"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.state_manager.delete_user_session(user_id)
        
        await query.edit_message_text(
            text="❌ عملیات لغو شد.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    
    async def start_edit_reactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> int:
        """
        Start edit reactions flow
        
        Requirements: AC-3.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Get current configuration
        config = self.state_manager.get_monitoring_config(chat_id)
        if not config:
            await query.edit_message_text(
                text="❌ کانال یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='edit_reactions',
            data={'channel_id': chat_id}
        )
        
        # Show current reactions
        current_reactions = " ".join([f"{r['emoji']}:{r['weight']}" for r in config.reactions])
        
        prompt_text = f"😊 **ویرایش ری‌اکشن‌ها**\n\n" \
                     f"**کانال:** {chat_id}\n" \
                     f"**ری‌اکشن‌های فعلی:** {current_reactions}\n\n" \
                     f"لطفاً ری‌اکشن‌های جدید را وارد کنید:\n\n" \
                     f"**فرمت:** `👍:5 ❤️:3 🔥:2`"
        
        await query.edit_message_text(
            text=prompt_text,
            parse_mode='Markdown'
        )
        
        return EDIT_REACTIONS_STATE
    
    async def handle_edit_reactions_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle edit reactions input
        
        Requirements: AC-3.4
        """
        user_id = update.effective_user.id
        reactions_text = update.message.text.strip()
        
        # Parse reactions
        success, reactions = self._parse_reactions(reactions_text)
        
        if not success:
            await update.message.reply_text(
                text=f"❌ فرمت ری‌اکشن‌ها نامعتبر است.\n\n{reactions}\n\n"
                     "فرمت صحیح: `👍:5 ❤️:3 🔥:2`",
                parse_mode='Markdown'
            )
            return EDIT_REACTIONS_STATE
        
        # Get session data
        session = self.state_manager.get_user_session(user_id)
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        channel_id = session.get_data('channel_id')
        
        # Update monitoring configuration
        config = self.state_manager.update_monitoring_config(
            chat_id=channel_id,
            reactions=reactions
        )
        
        if config:
            await update.message.reply_text(
                text=f"✅ ری‌اکشن‌های کانال {channel_id} بروزرسانی شد.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=f"❌ خطا در بروزرسانی ری‌اکشن‌ها.",
                parse_mode='Markdown'
            )
        
        # Clean up session
        self.state_manager.delete_user_session(user_id)
        
        return ConversationHandler.END

    
    async def start_edit_cooldown(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> int:
        """
        Start edit cooldown flow
        
        Requirements: AC-3.5
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Get current configuration
        config = self.state_manager.get_monitoring_config(chat_id)
        if not config:
            await query.edit_message_text(
                text="❌ کانال یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='edit_cooldown',
            data={'channel_id': chat_id}
        )
        
        # Show current cooldown
        prompt_text = f"⏱️ **ویرایش کولداون**\n\n" \
                     f"**کانال:** {chat_id}\n" \
                     f"**کولداون فعلی:** {config.cooldown} ثانیه\n\n" \
                     f"لطفاً کولداون جدید را وارد کنید (0.5-60 ثانیه):\n\n" \
                     f"مثال: `2.5`"
        
        await query.edit_message_text(
            text=prompt_text,
            parse_mode='Markdown'
        )
        
        return EDIT_COOLDOWN_STATE
    
    async def handle_edit_cooldown_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle edit cooldown input
        
        Requirements: AC-3.5, AC-13.4
        """
        user_id = update.effective_user.id
        cooldown_text = update.message.text.strip()
        
        # Parse and validate cooldown
        try:
            cooldown = float(cooldown_text)
            
            # Validate range (0.5-60 seconds)
            if not (0.5 <= cooldown <= 60):
                await update.message.reply_text(
                    text="❌ کولداون باید بین 0.5 تا 60 ثانیه باشد.\n\n"
                         "مثال: `2.5`",
                    parse_mode='Markdown'
                )
                return EDIT_COOLDOWN_STATE
        
        except ValueError:
            await update.message.reply_text(
                text="❌ مقدار کولداون نامعتبر است. لطفاً یک عدد وارد کنید.\n\n"
                     "مثال: `2.5`",
                parse_mode='Markdown'
            )
            return EDIT_COOLDOWN_STATE
        
        # Get session data
        session = self.state_manager.get_user_session(user_id)
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        channel_id = session.get_data('channel_id')
        
        # Update monitoring configuration
        config = self.state_manager.update_monitoring_config(
            chat_id=channel_id,
            cooldown=cooldown
        )
        
        if config:
            await update.message.reply_text(
                text=f"✅ کولداون کانال {channel_id} به {cooldown} ثانیه تغییر یافت.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=f"❌ خطا در بروزرسانی کولداون.",
                parse_mode='Markdown'
            )
        
        # Clean up session
        self.state_manager.delete_user_session(user_id)
        
        return ConversationHandler.END

    
    async def start_global_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start global monitoring for all enabled channels
        
        Requirements: AC-3.7
        """
        query = update.callback_query
        await query.answer()
        
        # Get all enabled monitoring configurations
        enabled_configs = self.state_manager.get_enabled_monitoring_configs()
        
        if not enabled_configs:
            await query.edit_message_text(
                text="⚠️ هیچ کانال فعالی برای مانیتورینگ یافت نشد.\n\n"
                     "ابتدا کانال‌ها را اضافه کنید.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Prepare all targets for monitoring
        targets = []
        for config in enabled_configs:
            # Convert reactions to proper format for telegram_manager
            reactions_list = [
                {'emoji': r['emoji'], 'weight': r['weight']}
                for r in config.reactions
            ]
            
            targets.append({
                'chat_id': config.chat_id,
                'reaction_pool': {
                    'reactions': reactions_list
                },
                'cooldown': config.cooldown
            })
        
        # Call session manager to start monitoring for all channels at once
        try:
            await self.session_manager.start_global_monitoring(targets=targets)
            started_count = len(targets)
            failed_channels = []
            self.logger.info(f"Started monitoring for {started_count} channels")
        except Exception as e:
            self.logger.error(f"Failed to start global monitoring: {e}")
            started_count = 0
            failed_channels = [config.chat_id for config in enabled_configs]
        
        # Format result message
        result_text = f"✅ **مانیتورینگ سراسری شروع شد**\n\n" \
                     f"**کانال‌های فعال:** {started_count}\n"
        
        if failed_channels:
            result_text += f"**کانال‌های ناموفق:** {len(failed_channels)}\n"
            result_text += "\n".join([f"• {ch}" for ch in failed_channels[:5]])
            if len(failed_channels) > 5:
                result_text += f"\n... و {len(failed_channels) - 5} کانال دیگر"
        
        await query.edit_message_text(
            text=result_text,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def stop_global_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Stop global monitoring for all channels
        
        Requirements: AC-3.8
        """
        query = update.callback_query
        await query.answer()
        
        # Get all monitoring configurations
        all_configs = self.state_manager.get_all_monitoring_configs()
        
        if not all_configs:
            await query.edit_message_text(
                text="ℹ️ هیچ کانالی برای توقف مانیتورینگ یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Stop monitoring for each channel
        stopped_count = 0
        failed_channels = []
        
        for config in all_configs:
            try:
                # Call session manager to stop monitoring
                success = await self.session_manager.stop_global_monitoring()
                
                if success:
                    stopped_count += 1
                    self.logger.info(f"Stopped monitoring for channel {config.chat_id}")
                else:
                    failed_channels.append(config.chat_id)
                    self.logger.error(f"Failed to stop monitoring for {config.chat_id}")
            except Exception as e:
                self.logger.error(f"Failed to stop monitoring for {config.chat_id}: {e}")
                failed_channels.append(config.chat_id)
        
        # Format result message
        result_text = f"⏸️ **مانیتورینگ سراسری متوقف شد**\n\n" \
                     f"**کانال‌های متوقف شده:** {stopped_count}\n"
        
        if failed_channels:
            result_text += f"**کانال‌های ناموفق:** {len(failed_channels)}\n"
            result_text += "\n".join([f"• {ch}" for ch in failed_channels[:5]])
            if len(failed_channels) > 5:
                result_text += f"\n... و {len(failed_channels) - 5} کانال دیگر"
        
        await query.edit_message_text(
            text=result_text,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    
    async def toggle_channel_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> int:
        """
        Toggle monitoring for a specific channel
        
        Requirements: AC-3.9
        """
        query = update.callback_query
        await query.answer()
        
        # Get current configuration
        config = self.state_manager.get_monitoring_config(chat_id)
        if not config:
            await query.edit_message_text(
                text="❌ کانال یافت نشد.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Toggle enabled status
        new_status = not config.enabled
        self.state_manager.update_monitoring_config(
            chat_id=chat_id,
            enabled=new_status
        )
        
        # Format result message
        status_text = "فعال" if new_status else "غیرفعال"
        result_text = f"✅ مانیتورینگ کانال {chat_id} {status_text} شد."
        
        await query.edit_message_text(
            text=result_text,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Display monitoring statistics
        
        Requirements: AC-3.10
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        # Get all monitoring configurations
        all_configs = self.state_manager.get_all_monitoring_configs()
        
        if not all_configs:
            message_text = "📊 **آمار مانیتورینگ**\n\nهیچ کانالی برای نمایش آمار یافت نشد."
        else:
            # Calculate statistics
            total_channels = len(all_configs)
            active_channels = sum(1 for c in all_configs if c.enabled)
            total_reactions = sum(c.stats['reactions_sent'] for c in all_configs)
            total_messages = sum(c.stats['messages_processed'] for c in all_configs)
            total_errors = sum(c.stats['errors'] for c in all_configs)
            
            # Format statistics message
            message_text = f"📊 **آمار مانیتورینگ**\n\n" \
                          f"**خلاصه کلی:**\n" \
                          f"• کل کانال‌ها: {total_channels}\n" \
                          f"• کانال‌های فعال: {active_channels}\n" \
                          f"• کل ری‌اکشن‌های ارسالی: {total_reactions}\n" \
                          f"• کل پیام‌های پردازش شده: {total_messages}\n" \
                          f"• کل خطاها: {total_errors}\n\n" \
                          f"**آمار به تفکیک کانال:**\n\n"
            
            # Add per-channel statistics
            for config in all_configs[:10]:  # Show top 10
                status_icon = "✅" if config.enabled else "❌"
                message_text += f"{status_icon} **{config.chat_id}**\n" \
                               f"   • ری‌اکشن‌ها: {config.stats['reactions_sent']}\n" \
                               f"   • پیام‌ها: {config.stats['messages_processed']}\n" \
                               f"   • خطاها: {config.stats['errors']}\n\n"
            
            if len(all_configs) > 10:
                message_text += f"... و {len(all_configs) - 10} کانال دیگر"
        
        # Build keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 بروزرسانی", callback_data="monitor:stats"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="menu:monitoring")
            ],
            [
                InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")
            ]
        ])
        
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
        
        return SELECT_MONITORING_ACTION

    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel operation and return to main menu"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        self.state_manager.delete_user_session(user_id)
        
        message = "❌ عملیات لغو شد."
        
        if query:
            await query.edit_message_text(text=message)
        else:
            await update.message.reply_text(text=message)
        
        return ConversationHandler.END
    
    def _validate_channel_identifier(self, identifier: str) -> bool:
        """
        Validate channel identifier format
        
        Args:
            identifier: Channel identifier to validate
        
        Returns:
            True if valid, False otherwise
            
        Requirements: AC-13.1
        """
        if not identifier:
            return False
        
        # Check for username format (@channelname)
        if identifier.startswith('@') and len(identifier) > 1:
            return True
        
        # Check for t.me links
        if 't.me/' in identifier:
            return True
        
        # Check for numeric ID
        if identifier.lstrip('-').isdigit():
            return True
        
        return False
    
    def _parse_reactions(self, reactions_text: str) -> tuple[bool, Any]:
        """
        Parse reactions from text input
        
        Args:
            reactions_text: Text containing reactions in format "emoji:weight emoji:weight"
        
        Returns:
            Tuple of (success, reactions_list or error_message)
            
        Requirements: AC-13.3, AC-13.5
        """
        try:
            reactions = []
            parts = reactions_text.split()
            
            for part in parts:
                if ':' not in part:
                    return False, f"فرمت نامعتبر: {part}"
                
                emoji, weight_str = part.rsplit(':', 1)
                
                # Validate emoji using centralized validator
                validation_result = InputValidator.validate_reaction_emoji(emoji)
                if not validation_result.valid:
                    return False, f"ایموجی نامعتبر: {emoji}"
                
                # Parse weight
                try:
                    weight = int(weight_str)
                    if weight < 1:
                        return False, f"وزن باید مثبت باشد: {weight}"
                except ValueError:
                    return False, f"وزن نامعتبر: {weight_str}"
                
                reactions.append({
                    'emoji': emoji,
                    'weight': weight
                })
            
            if not reactions:
                return False, "حداقل یک ری‌اکشن وارد کنید"
            
            return True, reactions
        
        except Exception as e:
            return False, f"خطا در پردازش: {str(e)}"
    
    def _is_valid_emoji(self, text: str) -> bool:
        """
        Check if text contains valid Unicode emoji
        
        Args:
            text: Text to check
        
        Returns:
            True if valid emoji, False otherwise
            
        Requirements: AC-13.3
        """
        # Basic emoji validation - check if it contains emoji Unicode ranges
        # This is a simplified check
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        
        return bool(emoji_pattern.search(text))

