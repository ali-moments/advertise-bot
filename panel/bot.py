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

# Conversation states
SELECT_OPERATION, GET_GROUP_LINK, GET_CHANNEL_LINK, GET_BULK_LINKS, CONFIRM_OPERATION = range(5)

class TelegramBotPanel:
    def __init__(self, session_manager: TelegramManagerApp):
        self.session_manager = session_manager
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.logger = logging.getLogger("TelegramBotPanel")
        
        # User session data
        self.user_sessions: Dict[int, Dict] = {}
        
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
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^(main_menu|session_stats|system_status)$'))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with admin check"""
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
                {"text": "📊 وضعیت سیستم", "callback_data": "system_status"}
            ],
            [
                {"text": "👥 مدیریت سشن‌ها", "callback_data": "session_stats"},
                {"text": "🔄 منوی اصلی", "callback_data": "main_menu"}
            ]
        ])
        
        await update.message.reply_text(welcome_message, reply_markup=keyboard, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """System status command"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await self.send_not_authorized(update)
            return
        
        try:
            stats = await self.session_manager.get_session_stats()
            
            status_message = """
            📊 **وضعیت سیستم**
            
            **آمار کلی:**
            """
            
            total_sessions = len(stats)
            connected_sessions = sum(1 for s in stats.values() if s.get('connected', False))
            monitoring_sessions = sum(1 for s in stats.values() if s.get('monitoring', False))
            
            status_message += f"""
            🔹 تعداد سشن‌ها: {total_sessions}
            🔹 سشن‌های متصل: {connected_sessions}
            🔹 سشن‌های در حال مانیتور: {monitoring_sessions}
            
            **آمار امروز:**
            """
            
            total_messages_today = sum(s.get('daily_stats', {}).get('messages_read', 0) for s in stats.values())
            total_groups_today = sum(s.get('daily_stats', {}).get('groups_scraped_today', 0) for s in stats.values())
            
            status_message += f"""
            🔸 پیام‌های خوانده شده: {total_messages_today}
            🔸 گروه‌های اسکرپ شده: {total_groups_today}
            
            _آخرین بروزرسانی: {datetime.now().strftime("%Y-%m-%d %H:%M")}_
            """
            
            keyboard = self.create_glass_keyboard([
                [{"text": "🔄 بروزرسانی", "callback_data": "system_status"}],
                [{"text": "🏠 منوی اصلی", "callback_data": "main_menu"}]
            ])
            
            await update.message.reply_text(status_message, reply_markup=keyboard, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در دریافت وضعیت: {str(e)}")
    
    async def admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin list"""
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
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return
        
        action = query.data
        
        if action == 'main_menu':
            await self.start_command(update, context)
        elif action == 'system_status':
            await self.status_command(update, context)
        elif action == 'scrape_menu':
            await self.scrape_command(update, context)
        elif action == 'session_stats':
            # Implement session statistics
            await query.edit_message_text("📊 این قابلیت به زودی اضافه خواهد شد")
    
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
    
    async def run(self):
        """Start the bot"""
        await self.application.run_polling()