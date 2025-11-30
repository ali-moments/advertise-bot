"""
Scraping Handler - Enhanced scraping operations with progress tracking
"""

import asyncio
import logging
import os
import csv
from typing import Dict, List, Optional, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from telegram_manager.main import TelegramManagerApp
from .config import ADMIN_USERS, MAX_GROUPS_PER_BULK
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .progress_tracker import ProgressTracker, ProgressTrackerFactory
from .persian_text import (
    SCRAPING_MENU_TEXT,
    SCRAPE_SINGLE_PROMPT,
    SCRAPE_BULK_PROMPT,
    EXTRACT_LINKS_PROMPT,
    BATCH_SCRAPE_PROMPT
)

# Conversation states
(
    SELECT_SCRAPE_TYPE,
    GET_SINGLE_GROUP,
    GET_BULK_GROUPS,
    GET_CHANNEL_LINK,
    GET_BATCH_CHANNELS,
    CONFIRM_SCRAPE,
    ASK_AUTO_SCRAPE
) = range(7)


class ScrapingHandler:
    """Handle all scraping-related operations"""
    
    def __init__(self, session_manager: TelegramManagerApp):
        """
        Initialize scraping handler
        
        Args:
            session_manager: TelegramManagerApp instance
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger("ScrapingHandler")
        
        # User session data
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_USERS
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for scraping operations
        
        Returns:
            ConversationHandler configured for scraping
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_scrape_menu, pattern='^scrape_menu$')
            ],
            states={
                SELECT_SCRAPE_TYPE: [
                    CallbackQueryHandler(self.select_scrape_type, pattern='^scrape:')
                ],
                GET_SINGLE_GROUP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_single_group)
                ],
                GET_BULK_GROUPS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_bulk_groups)
                ],
                GET_CHANNEL_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_channel_link)
                ],
                GET_BATCH_CHANNELS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_batch_channels)
                ],
                CONFIRM_SCRAPE: [
                    CallbackQueryHandler(self.confirm_scrape, pattern='^(confirm_scrape|cancel_scrape)$')
                ],
                ASK_AUTO_SCRAPE: [
                    CallbackQueryHandler(self.handle_auto_scrape, pattern='^(auto_scrape_yes|auto_scrape_no)$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_scrape, pattern='^cancel_scrape$'),
                CallbackQueryHandler(self.show_scrape_menu, pattern='^nav:scrape_menu$')
            ],
            name="scraping_conversation",
            persistent=False
        )
    
    async def show_scrape_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show scraping menu
        
        Requirements: AC-1.1, AC-1.2, AC-1.3, AC-1.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        
        keyboard = KeyboardBuilder.scrape_menu()
        
        await query.edit_message_text(
            SCRAPING_MENU_TEXT,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_SCRAPE_TYPE
    
    async def select_scrape_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle scrape type selection
        
        Requirements: AC-1.1, AC-1.2, AC-1.3, AC-1.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        scrape_type = query.data.replace('scrape:', '')
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'scrape_type': scrape_type,
            'targets': [],
            'extracted_links': []
        }
        
        if scrape_type == 'single':
            await query.edit_message_text(
                SCRAPE_SINGLE_PROMPT,
                parse_mode='Markdown'
            )
            return GET_SINGLE_GROUP
        
        elif scrape_type == 'bulk':
            await query.edit_message_text(
                SCRAPE_BULK_PROMPT,
                parse_mode='Markdown'
            )
            return GET_BULK_GROUPS
        
        elif scrape_type == 'extract':
            await query.edit_message_text(
                EXTRACT_LINKS_PROMPT,
                parse_mode='Markdown'
            )
            return GET_CHANNEL_LINK
        
        elif scrape_type == 'batch':
            await query.edit_message_text(
                BATCH_SCRAPE_PROMPT,
                parse_mode='Markdown'
            )
            return GET_BATCH_CHANNELS
        
        else:
            await query.edit_message_text("❌ نوع عملیات نامعتبر")
            return ConversationHandler.END
    
    async def get_single_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Get single group link
        
        Requirements: AC-1.1
        """
        user_id = update.effective_user.id
        group_link = update.message.text.strip()
        
        self.user_sessions[user_id]['targets'] = [group_link]
        
        # Show confirmation
        confirm_message = MessageFormatter.format_confirm_scrape(
            operation_type="اسکرپ تک گروه",
            target_count=1,
            preview=f"`{group_link}`"
        )
        
        keyboard = KeyboardBuilder.confirm_cancel(
            confirm_data="confirm_scrape",
            cancel_data="cancel_scrape"
        )
        
        await update.message.reply_text(
            confirm_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def get_bulk_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Get bulk group links
        
        Requirements: AC-1.2
        """
        user_id = update.effective_user.id
        links_text = update.message.text.strip()
        
        # Parse links
        links = [link.strip() for link in links_text.split('\n') if link.strip()]
        links = links[:MAX_GROUPS_PER_BULK]
        
        self.user_sessions[user_id]['targets'] = links
        
        # Create preview
        links_preview = "\n".join([f"• `{link}`" for link in links[:3]])
        if len(links) > 3:
            links_preview += f"\n• و {len(links) - 3} گروه دیگر..."
        
        confirm_message = MessageFormatter.format_confirm_scrape(
            operation_type="اسکرپ چندگانه",
            target_count=len(links),
            preview=links_preview
        )
        
        keyboard = KeyboardBuilder.confirm_cancel(
            confirm_data="confirm_scrape",
            cancel_data="cancel_scrape"
        )
        
        await update.message.reply_text(
            confirm_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def get_channel_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Get channel link for link extraction
        
        Requirements: AC-1.3
        """
        user_id = update.effective_user.id
        channel_link = update.message.text.strip()
        
        self.user_sessions[user_id]['targets'] = [channel_link]
        
        confirm_message = MessageFormatter.format_confirm_scrape(
            operation_type="استخراج لینک از کانال",
            target_count=1,
            preview=f"`{channel_link}`"
        )
        
        keyboard = KeyboardBuilder.confirm_cancel(
            confirm_data="confirm_scrape",
            cancel_data="cancel_scrape"
        )
        
        await update.message.reply_text(
            confirm_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def get_batch_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Get batch channel links for link extraction
        
        Requirements: AC-1.4
        """
        user_id = update.effective_user.id
        channels_text = update.message.text.strip()
        
        # Parse channel links
        channels = [ch.strip() for ch in channels_text.split('\n') if ch.strip()]
        channels = channels[:10]  # Limit to 10 channels
        
        self.user_sessions[user_id]['targets'] = channels
        
        # Create preview
        channels_preview = "\n".join([f"• `{ch}`" for ch in channels[:3]])
        if len(channels) > 3:
            channels_preview += f"\n• و {len(channels) - 3} کانال دیگر..."
        
        confirm_message = MessageFormatter.format_confirm_scrape(
            operation_type="اسکرپ از لینک‌دونی‌ها",
            target_count=len(channels),
            preview=channels_preview
        )
        
        keyboard = KeyboardBuilder.confirm_cancel(
            confirm_data="confirm_scrape",
            cancel_data="cancel_scrape"
        )
        
        await update.message.reply_text(
            confirm_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE

    
    async def confirm_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Confirm and execute scraping operation
        
        Requirements: AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-1.6, AC-1.7
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        if action == 'cancel_scrape':
            await query.edit_message_text("❌ عملیات لغو شد")
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            return ConversationHandler.END
        
        user_session = self.user_sessions.get(user_id, {})
        scrape_type = user_session.get('scrape_type')
        targets = user_session.get('targets', [])
        
        if not targets:
            await query.edit_message_text("❌ هیچ هدفی انتخاب نشده است")
            return ConversationHandler.END
        
        # Show processing message
        processing_msg = await query.edit_message_text(
            "⏳ **در حال پردازش...**\n\nلطفاً چند لحظه صبر کنید.",
            parse_mode='Markdown'
        )
        
        try:
            if scrape_type == 'single':
                result = await self._execute_single_scrape(
                    query.message.chat_id,
                    processing_msg.message_id,
                    targets[0],
                    context
                )
                
            elif scrape_type == 'bulk':
                result = await self._execute_bulk_scrape(
                    query.message.chat_id,
                    processing_msg.message_id,
                    targets,
                    context
                )
                
            elif scrape_type == 'extract':
                result = await self._execute_link_extraction(
                    query.message.chat_id,
                    processing_msg.message_id,
                    targets[0],
                    context,
                    user_id
                )
                
                # Store extracted links for potential auto-scrape
                if result.get('success') and result.get('telegram_links'):
                    self.user_sessions[user_id]['extracted_links'] = result['telegram_links']
                    
                    # Ask if user wants to scrape these groups
                    return await self._ask_auto_scrape(query, result)
                
            elif scrape_type == 'batch':
                result = await self._execute_batch_scrape(
                    query.message.chat_id,
                    processing_msg.message_id,
                    targets,
                    context
                )
            
            # Clean up user session
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            return ConversationHandler.END
            
        except Exception as e:
            self.logger.error(f"Error executing scrape: {e}")
            error_message = MessageFormatter.format_error(
                error_type="اسکرپ",
                description=str(e),
                show_retry=False
            )
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=processing_msg.message_id,
                text=error_message,
                parse_mode='Markdown'
            )
            
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            return ConversationHandler.END
    
    async def _ask_auto_scrape(self, query, extraction_result: Dict) -> int:
        """
        Ask user if they want to auto-scrape extracted links
        
        Requirements: AC-1.3, AC-1.4
        """
        links_count = len(extraction_result.get('telegram_links', []))
        
        # Show extraction results with auto-scrape option
        links_preview = "\n".join([
            f"• `{link}`" 
            for link in extraction_result['telegram_links'][:5]
        ])
        if links_count > 5:
            links_preview += f"\n• و {links_count - 5} لینک دیگر..."
        
        message = f"""
✅ **استخراج موفق**

**کانال:** `{extraction_result.get('source_channel', 'نامشخص')}`
**تعداد لینک‌ها:** {links_count}

**لینک‌های یافت شده:**
{links_preview}

**آیا می‌خواهید این گروه‌ها را اسکرپ کنید؟**
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، اسکرپ کن", callback_data="auto_scrape_yes"),
                InlineKeyboardButton("❌ خیر", callback_data="auto_scrape_no")
            ]
        ])
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return ASK_AUTO_SCRAPE
    
    async def handle_auto_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle auto-scrape decision
        
        Requirements: AC-1.3, AC-1.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        if action == 'auto_scrape_no':
            await query.edit_message_text("✅ عملیات تکمیل شد")
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            return ConversationHandler.END
        
        # Get extracted links
        user_session = self.user_sessions.get(user_id, {})
        extracted_links = user_session.get('extracted_links', [])
        
        if not extracted_links:
            await query.edit_message_text("❌ هیچ لینکی برای اسکرپ یافت نشد")
            return ConversationHandler.END
        
        # Show processing message
        processing_msg = await query.edit_message_text(
            "⏳ **شروع اسکرپ گروه‌ها...**\n\nلطفاً چند لحظه صبر کنید.",
            parse_mode='Markdown'
        )
        
        try:
            # Execute bulk scrape on extracted links
            result = await self._execute_bulk_scrape(
                query.message.chat_id,
                processing_msg.message_id,
                extracted_links,
                context
            )
            
            # Clean up user session
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            return ConversationHandler.END
            
        except Exception as e:
            self.logger.error(f"Error in auto-scrape: {e}")
            error_message = MessageFormatter.format_error(
                error_type="اسکرپ خودکار",
                description=str(e),
                show_retry=False
            )
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=processing_msg.message_id,
                text=error_message,
                parse_mode='Markdown'
            )
            
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            return ConversationHandler.END
    
    async def _execute_single_scrape(
        self,
        chat_id: int,
        message_id: int,
        group: str,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Dict:
        """
        Execute single group scrape with progress tracking
        
        Requirements: AC-1.1, AC-1.5, AC-1.6, AC-1.7
        """
        # Create progress tracker
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=chat_id,
            message_id=message_id,
            operation_name="اسکرپ تک گروه"
        )
        
        await tracker.start(total=1, initial_message="⏳ **اسکرپ تک گروه**\n\nشروع عملیات...")
        
        start_time = datetime.now()
        
        try:
            # Execute scrape
            result = await self.session_manager.scrape_group_members(
                group_identifier=group,
                join_first=True,
                max_members=10000
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.get('success'):
                await tracker.increment(success=True, force=True)
                
                # Format result with statistics
                final_message = f"""
✅ **اسکرپ موفق**

**گروه:** `{group}`
**تعداد اعضا:** {result.get('members_count', 0)}
**منبع داده:** {result.get('source', 'نامشخص')}
**زمان:** {MessageFormatter._format_duration(duration)}
**فایل:** `{result.get('file_path', 'ذخیره نشد')}`
"""
                
                # Send CSV file if available
                if result.get('file_path') and os.path.exists(result['file_path']):
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=open(result['file_path'], 'rb'),
                        caption=f"📄 فایل اعضای {group}"
                    )
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=final_message,
                    parse_mode='Markdown'
                )
            else:
                await tracker.error(result.get('error', 'خطای نامشخص'))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in single scrape: {e}")
            await tracker.error(str(e))
            return {'success': False, 'error': str(e)}
    
    async def _execute_bulk_scrape(
        self,
        chat_id: int,
        message_id: int,
        groups: List[str],
        context: ContextTypes.DEFAULT_TYPE
    ) -> Dict:
        """
        Execute bulk group scrape with progress tracking
        
        Requirements: AC-1.2, AC-1.5, AC-1.6, AC-1.7
        """
        # Create progress tracker
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=chat_id,
            message_id=message_id,
            operation_name="اسکرپ چندگانه"
        )
        
        await tracker.start(
            total=len(groups),
            initial_message=f"⏳ **اسکرپ چندگانه**\n\nشروع اسکرپ {len(groups)} گروه..."
        )
        
        start_time = datetime.now()
        results = {}
        success_count = 0
        failed_count = 0
        total_members = 0
        csv_files = []
        
        try:
            # Execute scrapes one by one with progress updates
            for i, group in enumerate(groups):
                try:
                    result = await self.session_manager.scrape_group_members(
                        group_identifier=group,
                        join_first=True,
                        max_members=10000
                    )
                    
                    results[group] = result
                    
                    if result.get('success'):
                        success_count += 1
                        total_members += result.get('members_count', 0)
                        
                        # Collect CSV file path
                        if result.get('file_path'):
                            csv_files.append(result['file_path'])
                    else:
                        failed_count += 1
                    
                    # Update progress
                    await tracker.update(
                        current=i + 1,
                        success=success_count,
                        failed=failed_count,
                        force=False
                    )
                    
                    # Add delay between scrapes
                    if i < len(groups) - 1:
                        await asyncio.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Error scraping {group}: {e}")
                    results[group] = {'success': False, 'error': str(e)}
                    failed_count += 1
                    
                    await tracker.update(
                        current=i + 1,
                        success=success_count,
                        failed=failed_count,
                        force=False
                    )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Format final message with statistics
            final_message = f"""
📊 **نتیجه اسکرپ چندگانه**

**تعداد کل:** {len(groups)} گروه
**موفق:** {success_count} گروه
**ناموفق:** {failed_count} گروه
**کل اعضا:** {total_members} نفر
**زمان:** {MessageFormatter._format_duration(duration)}
**فایل‌ها:** {len(csv_files)} فایل CSV
"""
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_message,
                parse_mode='Markdown'
            )
            
            # Send CSV files
            for csv_file in csv_files[:5]:  # Limit to 5 files
                if os.path.exists(csv_file):
                    try:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=open(csv_file, 'rb'),
                            caption=f"📄 {os.path.basename(csv_file)}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error sending CSV file: {e}")
            
            if len(csv_files) > 5:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"ℹ️ {len(csv_files) - 5} فایل دیگر در پوشه data ذخیره شده است."
                )
            
            return {
                'success': True,
                'results': results,
                'total': len(groups),
                'success_count': success_count,
                'failed_count': failed_count,
                'total_members': total_members,
                'duration': duration
            }
            
        except Exception as e:
            self.logger.error(f"Error in bulk scrape: {e}")
            await tracker.error(str(e))
            return {'success': False, 'error': str(e)}
    
    async def _execute_link_extraction(
        self,
        chat_id: int,
        message_id: int,
        channel: str,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> Dict:
        """
        Execute link extraction from channel
        
        Requirements: AC-1.3, AC-1.7
        """
        # Create progress tracker
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=chat_id,
            message_id=message_id,
            operation_name="استخراج لینک"
        )
        
        await tracker.start(
            total=1,
            initial_message="⏳ **استخراج لینک**\n\nدر حال اسکن کانال..."
        )
        
        start_time = datetime.now()
        
        try:
            # Execute link extraction
            result = await self.session_manager.extract_group_links(
                target=channel,
                limit_messages=100
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.get('success'):
                links_count = len(result.get('telegram_links', []))
                
                # Don't show final message here - will be shown in _ask_auto_scrape
                result['duration'] = duration
                return result
            else:
                await tracker.error(result.get('error', 'خطای نامشخص'))
                return result
            
        except Exception as e:
            self.logger.error(f"Error in link extraction: {e}")
            await tracker.error(str(e))
            return {'success': False, 'error': str(e)}
    
    async def _execute_batch_scrape(
        self,
        chat_id: int,
        message_id: int,
        channels: List[str],
        context: ContextTypes.DEFAULT_TYPE
    ) -> Dict:
        """
        Execute batch scrape from multiple link channels
        
        Requirements: AC-1.4, AC-1.5, AC-1.6, AC-1.7
        """
        # Create progress tracker
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=chat_id,
            message_id=message_id,
            operation_name="اسکرپ از لینک‌دونی‌ها"
        )
        
        # Phase 1: Extract links
        await tracker.set_message(
            f"⏳ **مرحله ۱: استخراج لینک‌ها**\n\nدر حال اسکن {len(channels)} کانال..."
        )
        
        start_time = datetime.now()
        
        try:
            # Extract links from all channels
            extraction_results = await self.session_manager.extract_links_from_channels(
                channels=channels,
                limit_messages=100
            )
            
            # Collect all unique links
            all_links = []
            for channel, result in extraction_results.items():
                if result.get('success'):
                    all_links.extend(result.get('telegram_links', []))
            
            unique_links = list(set(all_links))
            
            if not unique_links:
                await tracker.error("هیچ لینکی یافت نشد")
                return {
                    'success': False,
                    'error': 'No links found',
                    'extraction_results': extraction_results
                }
            
            # Phase 2: Scrape all found groups
            await tracker.set_message(
                f"⏳ **مرحله ۲: اسکرپ گروه‌ها**\n\nیافت شد: {len(unique_links)} گروه\nشروع اسکرپ..."
            )
            
            await tracker.start(
                total=len(unique_links),
                initial_message=f"⏳ **اسکرپ {len(unique_links)} گروه**\n\nشروع عملیات..."
            )
            
            success_count = 0
            failed_count = 0
            total_members = 0
            csv_files = []
            scrape_results = {}
            
            # Execute scrapes with progress tracking
            for i, group in enumerate(unique_links):
                try:
                    result = await self.session_manager.scrape_group_members(
                        group_identifier=group,
                        join_first=True,
                        max_members=10000
                    )
                    
                    scrape_results[group] = result
                    
                    if result.get('success'):
                        success_count += 1
                        total_members += result.get('members_count', 0)
                        
                        if result.get('file_path'):
                            csv_files.append(result['file_path'])
                    else:
                        failed_count += 1
                    
                    # Update progress
                    await tracker.update(
                        current=i + 1,
                        success=success_count,
                        failed=failed_count,
                        force=False
                    )
                    
                    # Add delay
                    if i < len(unique_links) - 1:
                        await asyncio.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Error scraping {group}: {e}")
                    scrape_results[group] = {'success': False, 'error': str(e)}
                    failed_count += 1
                    
                    await tracker.update(
                        current=i + 1,
                        success=success_count,
                        failed=failed_count,
                        force=False
                    )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Format final message with combined statistics
            final_message = f"""
📊 **نتیجه اسکرپ از لینک‌دونی‌ها**

**مرحله ۱ - استخراج لینک:**
• کانال‌های اسکن شده: {len(channels)}
• لینک‌های یافت شده: {len(unique_links)}

**مرحله ۲ - اسکرپ گروه‌ها:**
• تعداد کل: {len(unique_links)} گروه
• موفق: {success_count} گروه
• ناموفق: {failed_count} گروه
• کل اعضا: {total_members} نفر

**زمان کل:** {MessageFormatter._format_duration(duration)}
**فایل‌ها:** {len(csv_files)} فایل CSV
"""
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_message,
                parse_mode='Markdown'
            )
            
            # Send CSV files
            for csv_file in csv_files[:5]:
                if os.path.exists(csv_file):
                    try:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=open(csv_file, 'rb'),
                            caption=f"📄 {os.path.basename(csv_file)}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error sending CSV file: {e}")
            
            if len(csv_files) > 5:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"ℹ️ {len(csv_files) - 5} فایل دیگر در پوشه data ذخیره شده است."
                )
            
            return {
                'success': True,
                'extraction_results': extraction_results,
                'scrape_results': scrape_results,
                'total_links': len(unique_links),
                'success_count': success_count,
                'failed_count': failed_count,
                'total_members': total_members,
                'duration': duration
            }
            
        except Exception as e:
            self.logger.error(f"Error in batch scrape: {e}")
            await tracker.error(str(e))
            return {'success': False, 'error': str(e)}
    
    async def cancel_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel scraping operation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        await query.edit_message_text("❌ عملیات لغو شد")
        return ConversationHandler.END
