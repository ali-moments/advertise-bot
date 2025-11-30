"""
Telegram Bot Panel with Persian UI and Glass Buttons
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ConversationHandler
)

from telegram_manager.main import TelegramManagerApp
from .config import (
    ADMIN_USERS, 
    BOT_TOKEN, 
    PAGE_SIZE,
    MAX_GROUPS_PER_BULK,
    BOT_MAX_CONCURRENT_SCRAPES,
    BOT_REQUEST_TIMEOUT
)
from .sending_handler import SendingHandler
from .monitoring_handler import MonitoringHandler
from .session_handler import SessionHandler
from .scraping_handler import ScrapingHandler
from .operation_history_handler import OperationHistoryHandler
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .navigation import get_navigation_manager
from .state_manager import StateManager
from .error_handler import BotErrorHandler

# Conversation states
SELECT_OPERATION, GET_GROUP_LINK, GET_CHANNEL_LINK, GET_BULK_LINKS, CONFIRM_OPERATION = range(5)

class TelegramBotPanel:
    def __init__(self, session_manager: TelegramManagerApp):
        self.session_manager = session_manager
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.logger = logging.getLogger("TelegramBotPanel")
        
        # User session data
        self.user_sessions: Dict[int, Dict] = {}
        
        # Initialize navigation manager
        self.nav_manager = get_navigation_manager()
        
        # Initialize state manager for operation tracking
        self.state_manager = StateManager()
        
        # Initialize error handler
        self.error_handler = BotErrorHandler(logger_name="TelegramBotPanel")
        
        # Initialize sending handler
        self.sending_handler = SendingHandler(session_manager)
        
        # Initialize monitoring handler
        self.monitoring_handler = MonitoringHandler(session_manager)
        
        # Initialize session handler
        self.session_handler = SessionHandler(session_manager)
        
        # Initialize scraping handler
        self.scraping_handler = ScrapingHandler(session_manager)
        
        # Initialize operation history handler
        self.operation_history_handler = OperationHistoryHandler(self.state_manager)
        
        self.setup_handlers()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_USERS
    
    async def send_not_authorized(self, update: Update):
        """Send not authorized message"""
        message = """
        ⚠️ **دسترسی محدود**
        
        شما دسترسی لازم برای استفاده از این ربات را ندارید.
        """
        await update.message.reply_text(message)
    
    def create_glass_keyboard(self, buttons: List[List[Dict]]) -> InlineKeyboardMarkup:
        """
        Create glass-style keyboard buttons
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button in row:
                keyboard_row.append(
                    InlineKeyboardButton(
                        text=button['text'],
                        callback_data=button['callback_data']
                    )
                )
            keyboard.append(keyboard_row)
        return InlineKeyboardMarkup(keyboard)
    
    def setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("admins", self.admins_command))
        
        # Add sending conversation handler
        self.application.add_handler(self.sending_handler.get_conversation_handler())
        
        # Add monitoring conversation handler
        self.application.add_handler(self.monitoring_handler.get_conversation_handler())
        
        # Add session conversation handler
        self.application.add_handler(self.session_handler.get_conversation_handler())
        
        # Add scraping conversation handler
        self.application.add_handler(self.scraping_handler.get_conversation_handler())
        
        # Add operation history conversation handler
        self.application.add_handler(self.operation_history_handler.get_conversation_handler())
        
        # Conversation handler for operations
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("scrape", self.scrape_command)],
            states={
                SELECT_OPERATION: [CallbackQueryHandler(self.select_operation, pattern='^(scrape_single|scrape_bulk|extract_links|monitor)$')],
                GET_GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_group_link)],
                GET_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_channel_link)],
                GET_BULK_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_bulk_links)],
                CONFIRM_OPERATION: [CallbackQueryHandler(self.confirm_operation, pattern='^(confirm|cancel)$')],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_operation)],
        )
        
        self.application.add_handler(conv_handler)
        
        # Navigation callback handlers (must be before other handlers)
        self.application.add_handler(CallbackQueryHandler(self.handle_navigation, pattern='^nav:'))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.show_send_menu, pattern='^menu:sending$'))
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^(main_menu|system_status|nav:main)$'))
        
        # Error handler - use the global error handler from BotErrorHandler
        self.application.add_error_handler(self.error_handler.global_error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Start command with admin check
        
        Requirements: AC-9.1, AC-9.2, AC-9.3
        """
        try:
            user_id = update.effective_user.id
            
            if not self.is_admin(user_id):
                await self.send_not_authorized(update)
                return
            
            welcome_message = """
🌟 **به پنل مدیریت سشن‌های تلگرام خوش آمدید**

**دسترسی‌های موجود:**
🔹 مدیریت ۲۵۰ سشن فعال
🔹 اسکرپ اعضای گروه‌ها
🔹 استخراج لینک از کانال‌ها
🔹 مانیتورینگ کانال‌ها

**دستورات اصلی:**
/scrape - شروع عملیات اسکرپ
/status - وضعیت سیستم
/admins - مشاهده ادمین‌ها

برای شروع از دکمه‌های زیر استفاده کنید:
"""
            
            keyboard = self.create_glass_keyboard([
                [
                    {"text": "🔍 اسکرپ اعضا", "callback_data": "scrape_menu"},
                    {"text": "📤 ارسال پیام", "callback_data": "menu:sending"}
                ],
                [
                    {"text": "👁️ مانیتورینگ", "callback_data": "monitor:menu"},
                    {"text": "📊 وضعیت سیستم", "callback_data": "system_status"}
                ],
                [
                    {"text": "👥 مدیریت سشن‌ها", "callback_data": "session:menu"},
                    {"text": "🔄 منوی اصلی", "callback_data": "main_menu"}
                ]
            ])
            
            await update.message.reply_text(welcome_message, reply_markup=keyboard, parse_mode='Markdown')
            
        except Exception as e:
            from .error_handler import ErrorContext
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="start_command"
                ),
                retry_callback=None
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        System status command - show comprehensive system statistics
        
        Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.5
        """
        try:
            user_id = update.effective_user.id
            
            if not self.is_admin(user_id):
                await self.send_not_authorized(update)
                return
            
            # Get comprehensive system status
            status_data = await self._get_system_status()
            
            # Format using MessageFormatter
            status_message = MessageFormatter.format_system_status(status_data)
            
            # Create keyboard with refresh button
            keyboard = KeyboardBuilder.refresh_back(
                refresh_data="action:refresh_status",
                back_data="nav:main"
            )
            
            await update.message.reply_text(
                status_message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            from .error_handler import ErrorContext
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="status_command"
                ),
                retry_callback="action:refresh_status"
            )
    
    async def admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show admin list
        
        Requirements: AC-8.2, AC-9.1, AC-9.2, AC-9.3
        """
        try:
            user_id = update.effective_user.id
            
            if not self.is_admin(user_id):
                await self.send_not_authorized(update)
                return
            
            admins_list = "\n".join([f"🔹 {admin_id}" for admin_id in ADMIN_USERS])
            
            message = f"""
👥 **لیست ادمین‌های ربات**

{admins_list}

**تعداد کل:** {len(ADMIN_USERS)} ادمین
"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            from .error_handler import ErrorContext
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="admins_command"
                ),
                retry_callback=None
            )
    
    async def scrape_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scrape conversation"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await self.send_not_authorized(update)
            return ConversationHandler.END
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'operation_type': None,
            'targets': [],
            'step': SELECT_OPERATION
        }
        
        operation_message = """
        🔍 **عملیات اسکرپ و استخراج**
        
        لطفاً نوع عملیات مورد نظر را انتخاب کنید:
        
        **گزینه‌های موجود:**
        🔸 اسکرپ تک گروه - استخراج اعضای یک گروه
        🔸 اسکرپ گروه‌های multiple - اسکرپ چندین گروه
        🔸 استخراج لینک - استخراج لینک‌های گروه از کانال
        🔸 مانیتورینگ - تنظیم مانیتورینگ کانال
        """
        
        keyboard = self.create_glass_keyboard([
            [
                {"text": "🔸 اسکرپ تک گروه", "callback_data": "scrape_single"},
                {"text": "🔸 اسکرپ چندگانه", "callback_data": "scrape_bulk"}
            ],
            [
                {"text": "🔸 استخراج لینک", "callback_data": "extract_links"},
                {"text": "🔸 مانیتورینگ", "callback_data": "monitor"}
            ],
            [
                {"text": "❌ انصراف", "callback_data": "cancel"}
            ]
        ])
        
        await update.message.reply_text(operation_message, reply_markup=keyboard, parse_mode='Markdown')
        
        return SELECT_OPERATION
    
    async def select_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle operation selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        operation_type = query.data
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        self.user_sessions[user_id]['operation_type'] = operation_type
        
        if operation_type == 'scrape_single':
            message = """
            🔸 **اسکرپ تک گروه**
            
            لطفاً لینک گروه را ارسال کنید:
            
            **فرمت‌های قابل قبول:**
            • https://t.me/groupname
            • @groupname  
            • https://t.me/+invitehash
            
            مثال: 
            `https://t.me/+ABC123def456`
            """
            next_state = GET_GROUP_LINK
            
        elif operation_type == 'scrape_bulk':
            message = """
            🔸 **اسکرپ گروه‌های multiple**
            
            لطفاً لینک گروه‌ها را به صورت خط به خط ارسال کنید:
            
            **فرمت:**
            ```
            https://t.me/group1
            @group2  
            https://t.me/+invite1
            https://t.me/group3
            ```
            
            حداکثر ۱۰ گروه در هر درخواست
            """
            next_state = GET_BULK_LINKS
            
        elif operation_type == 'extract_links':
            message = """
            🔸 **استخراج لینک از کانال**
            
            لطفاً لینک کانال را ارسال کنید:
            
            **فرمت‌های قابل قبول:**
            • https://t.me/channelname
            • @channelname
            
            مثال:
            `@linkdoni`
            """
            next_state = GET_CHANNEL_LINK
            
        elif operation_type == 'monitor':
            message = """
            🔸 **تنظیم مانیتورینگ**
            
            این قابلیت به زودی اضافه خواهد شد.
            """
            await query.edit_message_text(message)
            return ConversationHandler.END
        
        else:
            await query.edit_message_text("❌ عملیات نامعتبر")
            return ConversationHandler.END
        
        keyboard = self.create_glass_keyboard([
            [{"text": "❌ انصراف", "callback_data": "cancel"}]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
        return next_state
    
    async def get_group_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get single group link"""
        user_id = update.effective_user.id
        group_link = update.message.text.strip()
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        self.user_sessions[user_id]['targets'] = [group_link]
        
        confirm_message = f"""
        ✅ **تأیید عملیات**
        
        **نوع عملیات:** اسکرپ تک گروه
        **گروه هدف:** `{group_link}`
        
        آیا می‌خواهید عملیات شروع شود؟
        """
        
        keyboard = self.create_glass_keyboard([
            [
                {"text": "✅ بله، شروع کن", "callback_data": "confirm"},
                {"text": "❌ انصراف", "callback_data": "cancel"}
            ]
        ])
        
        await update.message.reply_text(confirm_message, reply_markup=keyboard, parse_mode='Markdown')
        return CONFIRM_OPERATION
    
    async def get_bulk_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get bulk group links"""
        user_id = update.effective_user.id
        links_text = update.message.text.strip()
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        # Parse links
        links = [link.strip() for link in links_text.split('\n') if link.strip()]
        links = links[:10]  # Limit to 10 groups
        
        self.user_sessions[user_id]['targets'] = links
        
        links_preview = "\n".join([f"• `{link}`" for link in links[:3]])
        if len(links) > 3:
            links_preview += f"\n• و {len(links) - 3} گروه دیگر..."
        
        confirm_message = f"""
        ✅ **تأیید عملیات**
        
        **نوع عملیات:** اسکرپ گروه‌های multiple
        **تعداد گروه‌ها:** {len(links)}
        
        **گروه‌ها:**
        {links_preview}
        
        آیا می‌خواهید عملیات شروع شود؟
        """
        
        keyboard = self.create_glass_keyboard([
            [
                {"text": "✅ بله، شروع کن", "callback_data": "confirm"},
                {"text": "❌ انصراف", "callback_data": "cancel"}
            ]
        ])
        
        await update.message.reply_text(confirm_message, reply_markup=keyboard, parse_mode='Markdown')
        return CONFIRM_OPERATION
    
    async def get_channel_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get channel link for link extraction"""
        user_id = update.effective_user.id
        channel_link = update.message.text.strip()
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        self.user_sessions[user_id]['targets'] = [channel_link]
        
        confirm_message = f"""
        ✅ **تأیید عملیات**
        
        **نوع عملیات:** استخراج لینک از کانال
        **کانال هدف:** `{channel_link}`
        
        آیا می‌خواهید عملیات شروع شود؟
        """
        
        keyboard = self.create_glass_keyboard([
            [
                {"text": "✅ بله، شروع کن", "callback_data": "confirm"},
                {"text": "❌ انصراف", "callback_data": "cancel"}
            ]
        ])
        
        await update.message.reply_text(confirm_message, reply_markup=keyboard, parse_mode='Markdown')
        return CONFIRM_OPERATION
    
    async def confirm_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and execute operation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        if action == 'cancel':
            await query.edit_message_text("❌ عملیات لغو شد")
            return ConversationHandler.END
        
        user_session = self.user_sessions.get(user_id, {})
        operation_type = user_session.get('operation_type')
        targets = user_session.get('targets', [])
        
        # Show processing message
        processing_message = """
        ⏳ **در حال پردازش...**
        
        لطفاً چند لحظه صبر کنید.
        """
        await query.edit_message_text(processing_message, parse_mode='Markdown')
        
        try:
            if operation_type == 'scrape_single':
                result = await self.session_manager.scrape_group_members(targets[0], join_first=True)
                
                if result['success']:
                    message = f"""
                    ✅ **عملیات موفق**
                    
                    **گروه:** `{targets[0]}`
                    **تعداد اعضا:** {result['members_count']}
                    **فایل:** `{result.get('file_path', 'N/A')}`
                    **منبع داده:** {result.get('source', 'N/A')}
                    """
                else:
                    message = f"""
                    ❌ **خطا در عملیات**
                    
                    **گروه:** `{targets[0]}`
                    **خطا:** {result['error']}
                    """
            
            elif operation_type == 'scrape_bulk':
                results = await self.session_manager.bulk_scrape_groups(targets, join_first=True)
                
                success_count = sum(1 for r in results.values() if r.get('success'))
                total_count = len(results)
                
                message = f"""
                📊 **نتیجه اسکرپ گروه‌های multiple**
                
                **تعداد کل:** {total_count} گروه
                **موفق:** {success_count} گروه
                **ناموفق:** {total_count - success_count} گروه
                
                برای مشاهده جزئیات بیشتر از دستور /status استفاده کنید.
                """
            
            elif operation_type == 'extract_links':
                result = await self.session_manager.extract_group_links(targets[0])
                
                if result['success']:
                    links_preview = "\n".join([f"• `{link}`" for link in result['telegram_links'][:5]])
                    if len(result['telegram_links']) > 5:
                        links_preview += f"\n• و {len(result['telegram_links']) - 5} لینک دیگر..."
                    
                    message = f"""
                    ✅ **استخراج موفق**
                    
                    **کانال:** `{targets[0]}`
                    **تعداد لینک‌ها:** {result['telegram_links_count']}
                    
                    **لینک‌های یافت شده:**
                    {links_preview}
                    """
                else:
                    message = f"""
                    ❌ **خطا در استخراج**
                    
                    **کانال:** `{targets[0]}`
                    **خطا:** {result['error']}
                    """
            
            else:
                message = "❌ عملیات نامعتبر"
            
        except Exception as e:
            message = f"""
            ❌ **خطای سیستمی**
            
            خطا در اجرای عملیات:
            `{str(e)}`
            """
        
        # Add navigation buttons
        keyboard = self.create_glass_keyboard([
            [{"text": "🔍 عملیات جدید", "callback_data": "scrape_menu"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "main_menu"}]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
        return ConversationHandler.END
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel operation"""
        user_id = update.effective_user.id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        await update.message.reply_text("❌ عملیات لغو شد")
        return ConversationHandler.END
    
    async def show_send_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show sending menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return
        
        from .persian_text import SENDING_MENU_TEXT
        
        keyboard = KeyboardBuilder.send_menu()
        
        await query.edit_message_text(
            SENDING_MENU_TEXT,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle navigation callbacks (nav:*)
        
        Provides consistent navigation behavior across all menus.
        
        Requirements: AC-6.6, AC-9.1, AC-9.2, AC-9.3
        """
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            if not self.is_admin(user_id):
                await query.edit_message_text("⚠️ دسترسی محدود")
                return
            
            action = query.data
            
            # Handle main menu navigation
            if action == 'nav:main':
                # Clear navigation state
                self.nav_manager.clear_state(user_id)
                
                # Show main menu
                welcome_message = """
🌟 **به پنل مدیریت سشن‌های تلگرام خوش آمدید**

**دسترسی‌های موجود:**
🔹 مدیریت ۲۵۰ سشن فعال
🔹 اسکرپ اعضای گروه‌ها
🔹 ارسال پیام به کاربران
🔹 مانیتورینگ کانال‌ها
🔹 استخراج لینک از کانال‌ها

برای شروع از دکمه‌های زیر استفاده کنید:
"""
                
                keyboard = self.create_glass_keyboard([
                    [
                        {"text": "🔍 اسکرپ اعضا", "callback_data": "scrape_menu"},
                        {"text": "📤 ارسال پیام", "callback_data": "menu:sending"}
                    ],
                    [
                        {"text": "👁️ مانیتورینگ", "callback_data": "monitor:menu"},
                        {"text": "📊 وضعیت سیستم", "callback_data": "system_status"}
                    ],
                    [
                        {"text": "👥 مدیریت سشن‌ها", "callback_data": "session:menu"},
                        {"text": "🔄 منوی اصلی", "callback_data": "main_menu"}
                    ]
                ])
                
                await query.edit_message_text(welcome_message, reply_markup=keyboard, parse_mode='Markdown')
            
            # Handle back navigation
            elif action == 'nav:back':
                # Pop navigation and go to previous menu
                previous_target = self.nav_manager.pop_navigation(user_id)
                if previous_target:
                    # Trigger the previous menu callback
                    query.data = previous_target
                    await self.button_handler(update, context)
                else:
                    # No history, go to main menu
                    query.data = 'nav:main'
                    await self.handle_navigation(update, context)
            
            # Handle specific menu navigation
            elif action == 'nav:scrape_menu':
                self.nav_manager.push_navigation(user_id, "اسکرپ اعضا", "scrape_menu")
                await self.scraping_handler.show_scrape_menu(update, context)
            
            elif action == 'nav:send_menu':
                self.nav_manager.push_navigation(user_id, "ارسال پیام", "menu:sending")
                await self.show_send_menu(update, context)
            
            elif action == 'nav:monitor_menu':
                self.nav_manager.push_navigation(user_id, "مانیتورینگ", "monitor:menu")
                await self.monitoring_handler.show_monitoring_menu(update, context)
            
            elif action == 'nav:session_menu':
                self.nav_manager.push_navigation(user_id, "مدیریت سشن‌ها", "session:menu")
                await self.session_handler.show_session_menu(update, context)
            
            # Handle no-op navigation (for pagination indicators)
            elif action == 'nav:noop':
                # Do nothing, just answer the callback
                pass
            
            else:
                # Unknown navigation action
                self.logger.warning(f"Unknown navigation action: {action}")
        
        except Exception as e:
            from .error_handler import ErrorContext
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=update.effective_user.id if update.effective_user else None,
                    operation="handle_navigation",
                    details={'action': query.data if 'query' in locals() else 'unknown'}
                ),
                retry_callback=None
            )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return
        
        action = query.data
        
        if action == 'main_menu' or action == 'nav:main':
            # Show main menu
            welcome_message = """
🌟 **به پنل مدیریت سشن‌های تلگرام خوش آمدید**

**دسترسی‌های موجود:**
🔹 مدیریت ۲۵۰ سشن فعال
🔹 اسکرپ اعضای گروه‌ها
🔹 ارسال پیام به کاربران
🔹 مانیتورینگ کانال‌ها
🔹 استخراج لینک از کانال‌ها

برای شروع از دکمه‌های زیر استفاده کنید:
"""
            
            keyboard = self.create_glass_keyboard([
                [
                    {"text": "🔍 اسکرپ اعضا", "callback_data": "scrape_menu"},
                    {"text": "📤 ارسال پیام", "callback_data": "menu:sending"}
                ],
                [
                    {"text": "👁️ مانیتورینگ", "callback_data": "monitor:menu"},
                    {"text": "📊 وضعیت سیستم", "callback_data": "system_status"}
                ],
                [
                    {"text": "👥 مدیریت سشن‌ها", "callback_data": "session:menu"},
                    {"text": "📜 تاریخچه عملیات", "callback_data": "operation:history:page:0"}
                ]
            ])
            
            await query.edit_message_text(welcome_message, reply_markup=keyboard, parse_mode='Markdown')
        elif action == 'system_status' or action == 'action:refresh_status':
            # Show or refresh system status
            await self._show_system_status(query)
        elif action == 'scrape_menu':
            await self.scrape_command(update, context)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        self.logger.error(f"Bot error: {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ خطای سیستمی رخ داد. لطفاً دوباره تلاش کنید."
                )
            except:
                pass
    
    async def _get_system_status(self) -> Dict:
        """
        Get comprehensive system status data
        
        Returns:
            Dict with all system statistics
            
        Requirements: AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.5
        """
        try:
            # Get session stats
            stats = await self.session_manager.get_session_stats()
            
            # Calculate session statistics
            total_sessions = len(stats)
            connected_sessions = sum(1 for s in stats.values() if s.get('connected', False))
            monitoring_sessions = sum(1 for s in stats.values() if s.get('monitoring', False))
            
            # Calculate active operations
            active_scrapes = sum(
                1 for s in stats.values() 
                if s.get('current_operation') == 'scraping'
            )
            active_sends = sum(
                1 for s in stats.values() 
                if s.get('current_operation') == 'sending'
            )
            active_monitoring = monitoring_sessions
            
            # Calculate today's statistics
            messages_read = sum(
                s.get('daily_stats', {}).get('messages_read', 0) 
                for s in stats.values()
            )
            groups_scraped = sum(
                s.get('daily_stats', {}).get('groups_scraped_today', 0) 
                for s in stats.values()
            )
            messages_sent = 0  # TODO: Add when sending tracking is implemented
            
            # Get monitoring statistics
            monitoring_targets = getattr(self.session_manager, 'monitoring_targets', [])
            active_channels = len([
                t for t in monitoring_targets 
                if (isinstance(t, dict) and t.get('enabled', True)) or 
                   (hasattr(t, 'enabled') and t.enabled)
            ])
            
            # Calculate reactions sent today (from monitoring stats)
            reactions_sent = 0
            reactions_today = 0
            # TODO: Add reaction tracking when monitoring stats are available
            
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
    
    async def _show_system_status(self, query):
        """
        Show system status in response to callback query
        
        Args:
            query: CallbackQuery object
            
        Requirements: AC-5.6
        """
        try:
            # Get comprehensive system status
            status_data = await self._get_system_status()
            
            # Format using MessageFormatter
            status_message = MessageFormatter.format_system_status(status_data)
            
            # Create keyboard with refresh button
            keyboard = KeyboardBuilder.refresh_back(
                refresh_data="action:refresh_status",
                back_data="nav:main"
            )
            
            await query.edit_message_text(
                status_message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(f"Error showing system status: {e}")
            await query.edit_message_text(f"❌ خطا در دریافت وضعیت: {str(e)}")
    
    async def run(self):
        """Start the bot"""
        await self.application.run_polling()