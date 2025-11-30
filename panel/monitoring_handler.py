"""
MonitoringHandler - Handles monitoring management operations with conversation flows
"""

import asyncio
import json
import os
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
from telegram_manager.config import MonitoringTarget
from telegram_manager.models import ReactionPool, ReactionConfig
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .persian_text import (
    OPERATION_CANCELLED, PLEASE_WAIT, ERROR_TEMPLATE
)


# Conversation states
(
    SELECT_MONITOR_ACTION,
    GET_CHANNEL_LINK,
    GET_REACTIONS,
    GET_COOLDOWN,
    CONFIRM_ADD,
    CONFIRM_REMOVE,
    SELECT_CHANNEL_TO_EDIT,
    SELECT_EDIT_TYPE,
    GET_NEW_REACTIONS,
    GET_NEW_COOLDOWN,
    CONFIRM_EDIT
) = range(11)


@dataclass
class MonitoringSession:
    """User session data for monitoring operations"""
    user_id: int
    action: str  # 'add', 'remove', 'edit_reactions', 'edit_cooldown', 'list'
    channel_link: Optional[str] = None
    reactions: List[Dict[str, Any]] = field(default_factory=list)
    cooldown: float = 2.0
    selected_channel: Optional[str] = None
    edit_type: Optional[str] = None  # 'reactions' or 'cooldown'
    started_at: float = field(default_factory=time.time)
    page: int = 0  # For pagination


class MonitoringHandler:
    """Handle monitoring management operations"""
    
    def __init__(self, session_manager: TelegramManagerApp, config_file: str = "./monitoring_config.json"):
        """
        Initialize monitoring handler
        
        Args:
            session_manager: TelegramManagerApp instance
            config_file: Path to monitoring configuration file
        """
        self.session_manager = session_manager
        self.config_file = config_file
        self.user_sessions: Dict[int, MonitoringSession] = {}
        self.monitoring_config: Dict[str, Dict] = {}  # chat_id -> config
        self.monitoring_stats: Dict[str, Dict] = {}  # chat_id -> stats
        
        # Load existing configuration
        self._load_config()
    
    def _load_config(self):
        """Load monitoring configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.monitoring_config = data.get('channels', {})
                    self.monitoring_stats = data.get('stats', {})
            except Exception as e:
                print(f"Warning: Failed to load monitoring config: {e}")
                self.monitoring_config = {}
                self.monitoring_stats = {}
    
    def _save_config(self):
        """Save monitoring configuration to file"""
        try:
            data = {
                'channels': self.monitoring_config,
                'stats': self.monitoring_stats
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error: Failed to save monitoring config: {e}")
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for monitoring operations
        
        Returns:
            ConversationHandler configured for monitoring flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_monitoring_menu, pattern='^monitor:menu$'),
                CallbackQueryHandler(self.list_channels, pattern='^monitor:list'),
                CallbackQueryHandler(self.start_add_channel, pattern='^monitor:add$'),
                CallbackQueryHandler(self.start_remove_channel, pattern='^monitor:remove'),
                CallbackQueryHandler(self.start_edit_channel, pattern='^monitor:edit'),
                CallbackQueryHandler(self.toggle_monitoring_global, pattern='^monitor:toggle_global'),
                CallbackQueryHandler(self.toggle_monitoring_channel, pattern='^monitor:toggle_channel:'),
                CallbackQueryHandler(self.show_channel_statistics, pattern='^monitor:stats:'),
                CallbackQueryHandler(self.handle_remove_confirmation, pattern='^remove_channel:'),
                CallbackQueryHandler(self.confirm_remove_channel, pattern='^confirm_remove:'),
            ],
            states={
                GET_CHANNEL_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_channel_link)
                ],
                GET_REACTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_reactions)
                ],
                GET_COOLDOWN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_cooldown)
                ],
                CONFIRM_ADD: [
                    CallbackQueryHandler(self.handle_add_confirmation, pattern='^(confirm_add|cancel_add)$')
                ],
                CONFIRM_REMOVE: [
                    CallbackQueryHandler(self.handle_remove_confirmation, pattern='^(confirm_remove|cancel_remove)$')
                ],
                SELECT_CHANNEL_TO_EDIT: [
                    CallbackQueryHandler(self.handle_channel_selection, pattern='^select_channel:')
                ],
                SELECT_EDIT_TYPE: [
                    CallbackQueryHandler(self.handle_edit_type_selection, pattern='^edit_type:')
                ],
                GET_NEW_REACTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_new_reactions)
                ],
                GET_NEW_COOLDOWN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_new_cooldown)
                ],
                CONFIRM_EDIT: [
                    CallbackQueryHandler(self.handle_edit_confirmation, pattern='^(confirm_edit|cancel_edit)$')
                ],
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_operation),
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$')
            ],
        )
    
    async def show_monitoring_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show monitoring management menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Get monitoring status
        is_monitoring = self.session_manager.global_monitoring_config is not None
        channel_count = len(self.monitoring_config)
        
        message = f"""
👁️ **مدیریت مانیتورینگ**

**وضعیت:** {'✅ فعال' if is_monitoring else '❌ غیرفعال'}
**تعداد کانال‌ها:** {channel_count}

لطفاً یک گزینه را انتخاب کنید:
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
            [InlineKeyboardButton("➕ افزودن کانال", callback_data="monitor:add")],
        ]
        
        if channel_count > 0:
            keyboard.append([
                InlineKeyboardButton("❌ حذف کانال", callback_data="monitor:remove:0"),
                InlineKeyboardButton("✏️ ویرایش کانال", callback_data="monitor:edit:0")
            ])
            
            # Global start/stop button
            if is_monitoring:
                keyboard.append([InlineKeyboardButton("⏸️ توقف مانیتورینگ کلی", callback_data="monitor:toggle_global")])
            else:
                keyboard.append([InlineKeyboardButton("▶️ شروع مانیتورینگ کلی", callback_data="monitor:toggle_global")])
        
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """List monitored channels with pagination (AC-3.1, AC-6.7)"""
        query = update.callback_query
        await query.answer()
        
        # Extract page number from callback data
        page = 0
        if ':' in query.data:
            parts = query.data.split(':')
            if len(parts) > 2:
                try:
                    page = int(parts[2])
                except:
                    page = 0
        
        channels = list(self.monitoring_config.items())
        
        if not channels:
            message = """
📋 **لیست کانال‌های مانیتور شده**

هیچ کانالی برای مانیتورینگ تنظیم نشده است.

از دکمه "افزودن کانال" برای شروع استفاده کنید.
"""
            keyboard = [
                [InlineKeyboardButton("➕ افزودن کانال", callback_data="monitor:add")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Pagination: 5 channels per page (AC-6.7)
        page_size = 5
        total_pages = (len(channels) + page_size - 1) // page_size
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(channels))
        page_channels = channels[start_idx:end_idx]
        
        message = f"📋 **لیست کانال‌های مانیتور شده** (صفحه {page + 1}/{total_pages})\n\n"
        
        for i, (chat_id, config) in enumerate(page_channels, start=start_idx + 1):
            # Get status
            is_active = config.get('enabled', True)
            status_icon = "✅" if is_active else "❌"
            
            # Format reactions
            reactions_list = config.get('reactions', [])
            reactions_str = " ".join([f"{r['emoji']}({r['weight']})" for r in reactions_list])
            
            # Get stats
            stats = self.monitoring_stats.get(chat_id, {})
            reactions_sent = stats.get('reactions_sent', 0)
            messages_processed = stats.get('messages_processed', 0)
            
            message += f"""
{i}. **{chat_id}**
   وضعیت: {status_icon} {'فعال' if is_active else 'غیرفعال'}
   ری‌اکشن‌ها: {reactions_str}
   کولداون: {config.get('cooldown', 2.0)}s
   آمار: {reactions_sent} ری‌اکشن، {messages_processed} پیام
"""
        
        # Build keyboard with pagination
        keyboard = []
        
        # Navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"monitor:list:{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"monitor:list:{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        # Action buttons
        keyboard.append([
            InlineKeyboardButton("➕ افزودن", callback_data="monitor:add"),
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"monitor:edit:{page}")
        ])
        keyboard.append([
            InlineKeyboardButton("❌ حذف", callback_data=f"monitor:remove:{page}"),
            InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"monitor:list:{page}")
        ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def start_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start add channel flow (AC-3.2)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize session
        self.user_sessions[user_id] = MonitoringSession(
            user_id=user_id,
            action='add'
        )
        
        message = """
➕ **افزودن کانال جدید**

لطفاً لینک یا آیدی کانال را ارسال کنید:

**فرمت‌های قابل قبول:**
• `@channelname`
• `https://t.me/channelname`

**مثال:**
`@mychannel`
"""
        
        keyboard = KeyboardBuilder.back_main(back_data="monitor:menu", main_data="nav:main")
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return GET_CHANNEL_LINK
    
    async def handle_channel_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle channel link input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        channel_link = update.message.text.strip()
        
        # Normalize channel link
        if channel_link.startswith('https://t.me/'):
            channel_link = '@' + channel_link.split('/')[-1]
        elif not channel_link.startswith('@'):
            channel_link = '@' + channel_link
        
        session.channel_link = channel_link
        
        message = """
✅ **کانال ثبت شد**

حالا لطفاً ری‌اکشن‌ها را با وزن آن‌ها وارد کنید:

**فرمت:**
`emoji:weight emoji:weight ...`

**مثال:**
`👍:5 ❤️:3 🔥:2`

این به معنای:
• 👍 با وزن 5 (احتمال بیشتر)
• ❤️ با وزن 3
• 🔥 با وزن 2

**نکته:** وزن بالاتر = احتمال انتخاب بیشتر
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        return GET_REACTIONS
    
    async def handle_reactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle reactions input (AC-3.4)"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        reactions_text = update.message.text.strip()
        
        # Parse reactions
        try:
            reactions = self._parse_reactions(reactions_text)
            if not reactions:
                raise ValueError("هیچ ری‌اکشنی یافت نشد")
            
            session.reactions = reactions
            
            message = """
✅ **ری‌اکشن‌ها ثبت شدند**

حالا لطفاً کولداون (فاصله زمانی بین ری‌اکشن‌ها) را به ثانیه وارد کنید:

**مثال:**
`2.0` (2 ثانیه)
`3.5` (3.5 ثانیه)

**پیشنهاد:** 2.0 تا 5.0 ثانیه
"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            return GET_COOLDOWN
            
        except Exception as e:
            error_msg = f"""
❌ **خطا در پردازش ری‌اکشن‌ها**

{str(e)}

لطفاً دوباره تلاش کنید با فرمت صحیح:
`👍:5 ❤️:3 🔥:2`
"""
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return GET_REACTIONS
    
    async def handle_cooldown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle cooldown input (AC-3.5)"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        cooldown_text = update.message.text.strip()
        
        try:
            cooldown = float(cooldown_text)
            if cooldown < 0.5 or cooldown > 60:
                raise ValueError("کولداون باید بین 0.5 تا 60 ثانیه باشد")
            
            session.cooldown = cooldown
            
            # Show preview
            preview_msg = self._generate_add_preview(session)
            
            keyboard = KeyboardBuilder.confirm_cancel(
                confirm_data="confirm_add",
                cancel_data="cancel_add"
            )
            
            await update.message.reply_text(
                preview_msg,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return CONFIRM_ADD
            
        except Exception as e:
            error_msg = f"""
❌ **خطا در پردازش کولداون**

{str(e)}

لطفاً یک عدد معتبر وارد کنید (مثال: 2.0)
"""
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return GET_COOLDOWN
    
    async def handle_add_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle add channel confirmation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        if query.data == 'cancel_add':
            await self._cleanup_session(user_id)
            await query.edit_message_text(OPERATION_CANCELLED)
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Show processing message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            # Add channel to configuration
            self.monitoring_config[session.channel_link] = {
                'chat_id': session.channel_link,
                'reactions': session.reactions,
                'cooldown': session.cooldown,
                'enabled': True,
                'added_at': time.time()
            }
            
            # Initialize stats
            self.monitoring_stats[session.channel_link] = {
                'reactions_sent': 0,
                'messages_processed': 0,
                'started_at': time.time()
            }
            
            # Save configuration
            self._save_config()
            
            # If monitoring is active, restart it with new configuration
            if self.session_manager.global_monitoring_config is not None:
                await self._restart_monitoring()
            
            success_msg = f"""
✅ **کانال با موفقیت اضافه شد**

**کانال:** {session.channel_link}
**ری‌اکشن‌ها:** {self._format_reactions(session.reactions)}
**کولداون:** {session.cooldown}s

{'مانیتورینگ مجدداً راه‌اندازی شد.' if self.session_manager.global_monitoring_config else 'برای شروع مانیتورینگ، از دکمه "شروع مانیتورینگ کلی" استفاده کنید.'}
"""
            
            keyboard = [
                [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")]
            ]
            
            await query.edit_message_text(
                success_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="افزودن کانال",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        
        finally:
            await self._cleanup_session(user_id)
        
        return ConversationHandler.END
    
    async def start_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start remove channel flow (AC-3.3)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Extract page number
        page = 0
        if ':' in query.data:
            parts = query.data.split(':')
            if len(parts) > 2:
                try:
                    page = int(parts[2])
                except:
                    page = 0
        
        channels = list(self.monitoring_config.keys())
        
        if not channels:
            await query.edit_message_text(
                "❌ هیچ کانالی برای حذف وجود ندارد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]])
            )
            return ConversationHandler.END
        
        # Pagination
        page_size = 5
        total_pages = (len(channels) + page_size - 1) // page_size
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(channels))
        page_channels = channels[start_idx:end_idx]
        
        message = f"❌ **حذف کانال** (صفحه {page + 1}/{total_pages})\n\nلطفاً کانال مورد نظر را انتخاب کنید:\n"
        
        keyboard = []
        for channel in page_channels:
            keyboard.append([InlineKeyboardButton(
                f"❌ {channel}",
                callback_data=f"remove_channel:{channel}"
            )])
        
        # Navigation
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"monitor:remove:{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"monitor:remove:{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def handle_remove_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle remove channel confirmation"""
        query = update.callback_query
        await query.answer()
        
        # Extract channel from callback data
        channel = query.data.replace('remove_channel:', '')
        
        if channel not in self.monitoring_config:
            await query.edit_message_text("❌ کانال یافت نشد.")
            return ConversationHandler.END
        
        # Show confirmation
        config = self.monitoring_config[channel]
        message = f"""
⚠️ **تأیید حذف کانال**

**کانال:** {channel}
**ری‌اکشن‌ها:** {self._format_reactions(config.get('reactions', []))}

آیا مطمئن هستید که می‌خواهید این کانال را حذف کنید؟
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"confirm_remove:{channel}"),
                InlineKeyboardButton("❌ انصراف", callback_data="monitor:menu")
            ]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def confirm_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Confirm and execute channel removal"""
        query = update.callback_query
        await query.answer()
        
        # Extract channel from callback data
        channel = query.data.replace('confirm_remove:', '')
        
        if channel not in self.monitoring_config:
            await query.edit_message_text("❌ کانال یافت نشد.")
            return ConversationHandler.END
        
        try:
            # Remove from configuration
            del self.monitoring_config[channel]
            
            # Remove stats
            if channel in self.monitoring_stats:
                del self.monitoring_stats[channel]
            
            # Save configuration
            self._save_config()
            
            # If monitoring is active, restart it
            if self.session_manager.global_monitoring_config is not None:
                await self._restart_monitoring()
            
            success_msg = f"""
✅ **کانال با موفقیت حذف شد**

**کانال:** {channel}

{'مانیتورینگ مجدداً راه‌اندازی شد.' if self.session_manager.global_monitoring_config else ''}
"""
            
            keyboard = [
                [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")]
            ]
            
            await query.edit_message_text(
                success_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="حذف کانال",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        
        return ConversationHandler.END
    
    async def start_edit_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start edit channel flow (AC-3.4, AC-3.5)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Extract page number
        page = 0
        if ':' in query.data:
            parts = query.data.split(':')
            if len(parts) > 2:
                try:
                    page = int(parts[2])
                except:
                    page = 0
        
        channels = list(self.monitoring_config.keys())
        
        if not channels:
            await query.edit_message_text(
                "❌ هیچ کانالی برای ویرایش وجود ندارد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]])
            )
            return ConversationHandler.END
        
        # Pagination
        page_size = 5
        total_pages = (len(channels) + page_size - 1) // page_size
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(channels))
        page_channels = channels[start_idx:end_idx]
        
        message = f"✏️ **ویرایش کانال** (صفحه {page + 1}/{total_pages})\n\nلطفاً کانال مورد نظر را انتخاب کنید:\n"
        
        keyboard = []
        for channel in page_channels:
            keyboard.append([InlineKeyboardButton(
                f"✏️ {channel}",
                callback_data=f"select_channel:{channel}"
            )])
        
        # Navigation
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"monitor:edit:{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"monitor:edit:{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SELECT_CHANNEL_TO_EDIT
    
    async def handle_channel_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle channel selection for editing"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Extract channel from callback data
        channel = query.data.replace('select_channel:', '')
        
        if channel not in self.monitoring_config:
            await query.edit_message_text("❌ کانال یافت نشد.")
            return ConversationHandler.END
        
        # Initialize session
        self.user_sessions[user_id] = MonitoringSession(
            user_id=user_id,
            action='edit',
            selected_channel=channel
        )
        
        config = self.monitoring_config[channel]
        
        message = f"""
✏️ **ویرایش کانال**

**کانال:** {channel}
**ری‌اکشن‌های فعلی:** {self._format_reactions(config.get('reactions', []))}
**کولداون فعلی:** {config.get('cooldown', 2.0)}s

چه چیزی را می‌خواهید ویرایش کنید؟
"""
        
        keyboard = [
            [InlineKeyboardButton("🎭 ویرایش ری‌اکشن‌ها", callback_data="edit_type:reactions")],
            [InlineKeyboardButton("⏱️ ویرایش کولداون", callback_data="edit_type:cooldown")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SELECT_EDIT_TYPE
    
    async def handle_edit_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle edit type selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        edit_type = query.data.replace('edit_type:', '')
        session.edit_type = edit_type
        
        if edit_type == 'reactions':
            message = """
🎭 **ویرایش ری‌اکشن‌ها**

لطفاً ری‌اکشن‌های جدید را با وزن آن‌ها وارد کنید:

**فرمت:**
`emoji:weight emoji:weight ...`

**مثال:**
`👍:5 ❤️:3 🔥:2`
"""
            await query.edit_message_text(message, parse_mode='Markdown')
            return GET_NEW_REACTIONS
            
        elif edit_type == 'cooldown':
            message = """
⏱️ **ویرایش کولداون**

لطفاً کولداون جدید را به ثانیه وارد کنید:

**مثال:**
`2.0` (2 ثانیه)
`3.5` (3.5 ثانیه)

**پیشنهاد:** 2.0 تا 5.0 ثانیه
"""
            await query.edit_message_text(message, parse_mode='Markdown')
            return GET_NEW_COOLDOWN
        
        return ConversationHandler.END
    
    async def handle_new_reactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle new reactions input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        reactions_text = update.message.text.strip()
        
        try:
            reactions = self._parse_reactions(reactions_text)
            if not reactions:
                raise ValueError("هیچ ری‌اکشنی یافت نشد")
            
            session.reactions = reactions
            
            # Show preview
            preview_msg = self._generate_edit_preview(session)
            
            keyboard = KeyboardBuilder.confirm_cancel(
                confirm_data="confirm_edit",
                cancel_data="cancel_edit"
            )
            
            await update.message.reply_text(
                preview_msg,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return CONFIRM_EDIT
            
        except Exception as e:
            error_msg = f"""
❌ **خطا در پردازش ری‌اکشن‌ها**

{str(e)}

لطفاً دوباره تلاش کنید با فرمت صحیح:
`👍:5 ❤️:3 🔥:2`
"""
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return GET_NEW_REACTIONS
    
    async def handle_new_cooldown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle new cooldown input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        cooldown_text = update.message.text.strip()
        
        try:
            cooldown = float(cooldown_text)
            if cooldown < 0.5 or cooldown > 60:
                raise ValueError("کولداون باید بین 0.5 تا 60 ثانیه باشد")
            
            session.cooldown = cooldown
            
            # Show preview
            preview_msg = self._generate_edit_preview(session)
            
            keyboard = KeyboardBuilder.confirm_cancel(
                confirm_data="confirm_edit",
                cancel_data="cancel_edit"
            )
            
            await update.message.reply_text(
                preview_msg,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            return CONFIRM_EDIT
            
        except Exception as e:
            error_msg = f"""
❌ **خطا در پردازش کولداون**

{str(e)}

لطفاً یک عدد معتبر وارد کنید (مثال: 2.0)
"""
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return GET_NEW_COOLDOWN
    
    async def handle_edit_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle edit confirmation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        if query.data == 'cancel_edit':
            await self._cleanup_session(user_id)
            await query.edit_message_text(OPERATION_CANCELLED)
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Show processing message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        try:
            channel = session.selected_channel
            config = self.monitoring_config[channel]
            
            # Update configuration based on edit type
            if session.edit_type == 'reactions':
                config['reactions'] = session.reactions
            elif session.edit_type == 'cooldown':
                config['cooldown'] = session.cooldown
            
            # Save configuration
            self._save_config()
            
            # If monitoring is active, restart it
            if self.session_manager.global_monitoring_config is not None:
                await self._restart_monitoring()
            
            success_msg = f"""
✅ **کانال با موفقیت ویرایش شد**

**کانال:** {channel}
"""
            
            if session.edit_type == 'reactions':
                success_msg += f"**ری‌اکشن‌های جدید:** {self._format_reactions(session.reactions)}\n"
            elif session.edit_type == 'cooldown':
                success_msg += f"**کولداون جدید:** {session.cooldown}s\n"
            
            success_msg += f"\n{'مانیتورینگ مجدداً راه‌اندازی شد.' if self.session_manager.global_monitoring_config else ''}"
            
            keyboard = [
                [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")]
            ]
            
            await query.edit_message_text(
                success_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="ویرایش کانال",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        
        finally:
            await self._cleanup_session(user_id)
        
        return ConversationHandler.END
    
    async def toggle_monitoring_global(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Toggle global monitoring on/off (AC-3.7, AC-3.6)"""
        query = update.callback_query
        await query.answer()
        
        is_monitoring = self.session_manager.global_monitoring_config is not None
        
        try:
            if is_monitoring:
                # Stop monitoring
                await query.edit_message_text("⏳ در حال توقف مانیتورینگ...", parse_mode='Markdown')
                await self.session_manager.stop_global_monitoring()
                
                message = """
⏸️ **مانیتورینگ متوقف شد**

مانیتورینگ کلی با موفقیت متوقف شد.
"""
            else:
                # Start monitoring
                if not self.monitoring_config:
                    await query.edit_message_text(
                        "❌ هیچ کانالی برای مانیتورینگ تنظیم نشده است.\n\nابتدا کانال اضافه کنید.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ افزودن کانال", callback_data="monitor:add")]])
                    )
                    return ConversationHandler.END
                
                await query.edit_message_text("⏳ در حال شروع مانیتورینگ...", parse_mode='Markdown')
                
                # Convert config to monitoring targets
                targets = []
                for chat_id, config in self.monitoring_config.items():
                    if config.get('enabled', True):
                        targets.append({
                            'chat_id': chat_id,
                            'reaction_pool': {
                                'reactions': config.get('reactions', [])
                            },
                            'cooldown': config.get('cooldown', 2.0)
                        })
                
                await self.session_manager.start_global_monitoring(targets)
                
                message = f"""
▶️ **مانیتورینگ شروع شد**

مانیتورینگ کلی با موفقیت شروع شد.

**تعداد کانال‌های فعال:** {len(targets)}
"""
            
            keyboard = [
                [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="تغییر وضعیت مانیتورینگ",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        
        return ConversationHandler.END
    
    async def toggle_monitoring_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Toggle monitoring for a specific channel (AC-3.8, AC-3.6)"""
        query = update.callback_query
        await query.answer()
        
        # Extract channel from callback data
        channel = query.data.replace('monitor:toggle_channel:', '')
        
        if channel not in self.monitoring_config:
            await query.edit_message_text("❌ کانال یافت نشد.")
            return ConversationHandler.END
        
        try:
            config = self.monitoring_config[channel]
            current_status = config.get('enabled', True)
            new_status = not current_status
            
            # Update configuration
            config['enabled'] = new_status
            self._save_config()
            
            # If global monitoring is active, restart it
            if self.session_manager.global_monitoring_config is not None:
                await self._restart_monitoring()
            
            status_text = "فعال" if new_status else "غیرفعال"
            icon = "✅" if new_status else "❌"
            
            message = f"""
{icon} **وضعیت مانیتورینگ تغییر کرد**

**کانال:** {channel}
**وضعیت جدید:** {status_text}

{'مانیتورینگ مجدداً راه‌اندازی شد.' if self.session_manager.global_monitoring_config else ''}
"""
            
            keyboard = [
                [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="nav:main")]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="تغییر وضعیت کانال",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        
        return ConversationHandler.END
    
    async def show_channel_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show statistics for a specific channel (AC-3.9)"""
        query = update.callback_query
        await query.answer()
        
        # Extract channel from callback data
        channel = query.data.replace('monitor:stats:', '')
        
        if channel not in self.monitoring_config:
            await query.edit_message_text("❌ کانال یافت نشد.")
            return ConversationHandler.END
        
        config = self.monitoring_config[channel]
        stats = self.monitoring_stats.get(channel, {})
        
        # Calculate uptime
        started_at = stats.get('started_at', time.time())
        uptime_seconds = time.time() - started_at
        uptime_str = MessageFormatter._format_duration(uptime_seconds)
        
        message = f"""
📊 **آمار مانیتورینگ**

**کانال:** {channel}
**وضعیت:** {'✅ فعال' if config.get('enabled', True) else '❌ غیرفعال'}

**تنظیمات:**
• ری‌اکشن‌ها: {self._format_reactions(config.get('reactions', []))}
• کولداون: {config.get('cooldown', 2.0)}s

**آمار:**
• ری‌اکشن‌های ارسالی: {stats.get('reactions_sent', 0)}
• پیام‌های پردازش شده: {stats.get('messages_processed', 0)}
• مدت زمان فعالیت: {uptime_str}

**آخرین بروزرسانی:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"monitor:stats:{channel}")],
            [InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="monitor:list:0")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="monitor:menu")]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def _restart_monitoring(self):
        """Restart monitoring with current configuration"""
        # Stop current monitoring
        if self.session_manager.global_monitoring_config is not None:
            await self.session_manager.stop_global_monitoring()
        
        # Start with new configuration
        targets = []
        for chat_id, config in self.monitoring_config.items():
            if config.get('enabled', True):
                targets.append({
                    'chat_id': chat_id,
                    'reaction_pool': {
                        'reactions': config.get('reactions', [])
                    },
                    'cooldown': config.get('cooldown', 2.0)
                })
        
        if targets:
            await self.session_manager.start_global_monitoring(targets)
    
    def _parse_reactions(self, reactions_text: str) -> List[Dict[str, Any]]:
        """
        Parse reactions from text format
        
        Format: emoji:weight emoji:weight ...
        Example: 👍:5 ❤️:3 🔥:2
        
        Returns:
            List of reaction dicts with 'emoji' and 'weight' keys
        """
        reactions = []
        parts = reactions_text.split()
        
        for part in parts:
            if ':' in part:
                emoji, weight_str = part.rsplit(':', 1)
                try:
                    weight = int(weight_str)
                    if weight < 1:
                        raise ValueError(f"وزن باید حداقل 1 باشد، دریافت شد: {weight}")
                    reactions.append({
                        'emoji': emoji.strip(),
                        'weight': weight
                    })
                except ValueError as e:
                    raise ValueError(f"خطا در پردازش '{part}': {str(e)}")
            else:
                # Default weight of 1 if not specified
                reactions.append({
                    'emoji': part.strip(),
                    'weight': 1
                })
        
        return reactions
    
    def _format_reactions(self, reactions: List[Dict[str, Any]]) -> str:
        """Format reactions list for display"""
        if not reactions:
            return "هیچ ری‌اکشنی"
        return " ".join([f"{r['emoji']}({r['weight']})" for r in reactions])
    
    def _generate_add_preview(self, session: MonitoringSession) -> str:
        """Generate preview for add channel confirmation"""
        return f"""
✅ **پیش‌نمایش افزودن کانال**

**کانال:** {session.channel_link}
**ری‌اکشن‌ها:** {self._format_reactions(session.reactions)}
**کولداون:** {session.cooldown}s

آیا می‌خواهید این کانال اضافه شود؟
"""
    
    def _generate_edit_preview(self, session: MonitoringSession) -> str:
        """Generate preview for edit channel confirmation"""
        config = self.monitoring_config.get(session.selected_channel, {})
        
        message = f"""
✅ **پیش‌نمایش ویرایش**

**کانال:** {session.selected_channel}
"""
        
        if session.edit_type == 'reactions':
            message += f"""
**ری‌اکشن‌های قبلی:** {self._format_reactions(config.get('reactions', []))}
**ری‌اکشن‌های جدید:** {self._format_reactions(session.reactions)}
"""
        elif session.edit_type == 'cooldown':
            message += f"""
**کولداون قبلی:** {config.get('cooldown', 2.0)}s
**کولداون جدید:** {session.cooldown}s
"""
        
        message += "\nآیا می‌خواهید این تغییرات اعمال شود؟"
        
        return message
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel monitoring operation"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            await self._cleanup_session(user_id)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(OPERATION_CANCELLED)
        else:
            await update.message.reply_text(OPERATION_CANCELLED)
        
        return ConversationHandler.END
    
    async def _cleanup_session(self, user_id: int):
        """Clean up user session"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
