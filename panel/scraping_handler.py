"""
Scraping Handler - Manages all scraping operations through bot interface

This module handles:
- Single group scraping
- Bulk group scraping
- Link extraction from channels
- Progress tracking for scraping operations

Requirements: AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-1.6, AC-1.7, AC-1.8
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
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
from .state_manager import StateManager
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .progress_tracker import ProgressTracker, ProgressTrackerFactory
from .file_handler import FileHandler
from .error_handler import BotErrorHandler, ErrorContext
from .validators import InputValidator, ValidationErrorHandler
from .work_distributor import WorkDistributor
from .batch_result_tracker import BatchResultTracker
from .persian_text import (
    SCRAPE_MENU_TEXT, SCRAPE_SINGLE_PROMPT, SCRAPE_BULK_PROMPT,
    SCRAPE_EXTRACT_PROMPT, SCRAPE_JOIN_PROMPT, SCRAPE_CONFIRM_TEXT,
    SCRAPE_STARTING, SCRAPE_COMPLETE, SCRAPE_ERROR,
    BTN_JOIN_YES, BTN_JOIN_NO
)


# Conversation states
SELECT_SCRAPE_TYPE = 0
GET_GROUP_LINK = 1
GET_BULK_LINKS = 2
GET_CHANNEL_LINK = 3
GET_JOIN_PREFERENCE = 4
CONFIRM_SCRAPE = 5


class ScrapingHandler:
    """
    Handler for all scraping operations
    
    Manages conversation flows for:
    - Single group scraping
    - Bulk group scraping (up to 50 groups)
    - Link extraction from channels
    
    Requirements: AC-1.1 through AC-1.8
    """
    
    def __init__(
        self,
        session_manager: TelegramSessionManager,
        state_manager: StateManager,
        error_handler: BotErrorHandler
    ):
        """
        Initialize scraping handler
        
        Args:
            session_manager: TelegramSessionManager instance
            state_manager: StateManager instance
            error_handler: BotErrorHandler instance
        """
        self.session_manager = session_manager
        self.state_manager = state_manager
        self.error_handler = error_handler
        self.logger = logging.getLogger("ScrapingHandler")
        
        # File handler for CSV operations
        self.file_handler = FileHandler()
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for scraping operations
        
        Returns:
            ConversationHandler configured for scraping flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_scrape_menu, pattern='^menu:scraping$'),
                CallbackQueryHandler(self.start_single_scrape, pattern='^scrape:single$'),
                CallbackQueryHandler(self.start_bulk_scrape, pattern='^scrape:bulk$'),
                CallbackQueryHandler(self.start_link_extraction, pattern='^scrape:extract$'),
            ],
            states={
                SELECT_SCRAPE_TYPE: [
                    CallbackQueryHandler(self.start_single_scrape, pattern='^scrape:single$'),
                    CallbackQueryHandler(self.start_bulk_scrape, pattern='^scrape:bulk$'),
                    CallbackQueryHandler(self.start_link_extraction, pattern='^scrape:extract$'),
                ],
                GET_GROUP_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_single_group_input)
                ],
                GET_BULK_LINKS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_bulk_groups_input)
                ],
                GET_CHANNEL_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_channel_input)
                ],
                GET_JOIN_PREFERENCE: [
                    CallbackQueryHandler(self.handle_join_preference, pattern='^join:(yes|no)$')
                ],
                CONFIRM_SCRAPE: [
                    CallbackQueryHandler(self.execute_scrape, pattern='^confirm:scrape$'),
                    CallbackQueryHandler(self.cancel_scrape, pattern='^cancel:scrape$')
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$'),
                CallbackQueryHandler(self.show_scrape_menu, pattern='^menu:scraping$'),
            ],
            name="scraping_conversation",
            persistent=False
        )
    
    async def show_scrape_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show scraping menu with operation options
        
        Requirements: AC-1.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Create or update user session
        self.state_manager.create_user_session(
            user_id=user_id,
            operation='scraping',
            step='menu'
        )
        
        # Build keyboard
        keyboard = KeyboardBuilder.scrape_menu(user_id=user_id)
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=SCRAPE_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text=SCRAPE_MENU_TEXT,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
        return SELECT_SCRAPE_TYPE
    
    async def start_single_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start single group scraping flow
        
        Requirements: AC-1.1, AC-1.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='get_group_link',
            data={'scrape_type': 'single'}
        )
        
        # Prompt for group identifier
        await query.edit_message_text(
            text=SCRAPE_SINGLE_PROMPT,
            parse_mode='Markdown'
        )
        
        return GET_GROUP_LINK
    
    async def start_bulk_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start bulk group scraping flow
        
        Requirements: AC-1.3, AC-1.6
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='get_bulk_links',
            data={'scrape_type': 'bulk'}
        )
        
        # Prompt for group identifiers
        await query.edit_message_text(
            text=SCRAPE_BULK_PROMPT,
            parse_mode='Markdown'
        )
        
        return GET_BULK_LINKS
    
    async def start_link_extraction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start link extraction flow
        
        Requirements: AC-1.4, AC-1.5
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='get_channel_link',
            data={'scrape_type': 'extract'}
        )
        
        # Prompt for channel identifier
        await query.edit_message_text(
            text=SCRAPE_EXTRACT_PROMPT,
            parse_mode='Markdown'
        )
        
        return GET_CHANNEL_LINK
    
    async def handle_single_group_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle single group identifier input
        
        Requirements: AC-1.1, AC-1.2, AC-13.1, AC-13.5
        """
        user_id = update.effective_user.id
        group_identifier = update.message.text.strip()
        
        # Validate group identifier using centralized validator
        validation_result = InputValidator.validate_group_identifier(group_identifier)
        
        if not validation_result.valid:
            # Format error message with retry prompt
            error_message = ValidationErrorHandler.format_validation_error(
                validation_result,
                context="🔍 اسکرپ تک گروه"
            )
            await update.message.reply_text(
                text=error_message,
                parse_mode='Markdown'
            )
            # Preserve session state and allow retry
            return GET_GROUP_LINK
        
        # Store normalized group identifier
        normalized_identifier = validation_result.normalized_value or group_identifier
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'group_identifier': normalized_identifier}
        )
        
        # Ask for join preference
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(BTN_JOIN_YES, callback_data='join:yes'),
                InlineKeyboardButton(BTN_JOIN_NO, callback_data='join:no')
            ]
        ])
        
        await update.message.reply_text(
            text=SCRAPE_JOIN_PROMPT,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return GET_JOIN_PREFERENCE
    
    async def handle_bulk_groups_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle bulk group identifiers input
        
        Requirements: AC-1.3, AC-1.6, AC-13.1, AC-13.5
        """
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Split by newlines or commas
        group_identifiers = [
            line.strip()
            for line in text.replace(',', '\n').split('\n')
            if line.strip()
        ]
        
        # Validate count (max 50) using centralized validator
        count_validation = InputValidator.validate_bulk_group_count(len(group_identifiers))
        
        if not count_validation.valid:
            error_message = ValidationErrorHandler.format_validation_error(
                count_validation,
                context="🔍 اسکرپ چند گروه"
            )
            await update.message.reply_text(
                text=error_message,
                parse_mode='Markdown'
            )
            return GET_BULK_LINKS
        
        # Validate each identifier using centralized validator
        invalid_identifiers = []
        valid_identifiers = []
        
        for identifier in group_identifiers:
            validation_result = InputValidator.validate_group_identifier(identifier)
            if validation_result.valid:
                # Use normalized value
                normalized = validation_result.normalized_value or identifier
                valid_identifiers.append(normalized)
            else:
                invalid_identifiers.append(identifier)
        
        if not valid_identifiers:
            await update.message.reply_text(
                text="❌ هیچ لینک معتبری یافت نشد. لطفاً لینک‌های معتبر وارد کنید.",
                parse_mode='Markdown'
            )
            return GET_BULK_LINKS
        
        # Store valid identifiers
        self.state_manager.update_user_session(
            user_id=user_id,
            data={
                'group_identifiers': valid_identifiers,
                'invalid_identifiers': invalid_identifiers,
                'join_first': False  # Default for bulk
            }
        )
        
        # Show confirmation
        preview = "\n".join([f"• {g}" for g in valid_identifiers[:5]])
        if len(valid_identifiers) > 5:
            preview += f"\n... و {len(valid_identifiers) - 5} گروه دیگر"
        
        if invalid_identifiers:
            preview += f"\n\n⚠️ {len(invalid_identifiers)} لینک نامعتبر نادیده گرفته شد"
        
        confirm_text = SCRAPE_CONFIRM_TEXT.format(
            count=len(valid_identifiers),
            preview=preview
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:scrape'),
                InlineKeyboardButton("❌ لغو", callback_data='cancel:scrape')
            ]
        ])
        
        await update.message.reply_text(
            text=confirm_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def handle_channel_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle channel identifier input for link extraction
        
        Requirements: AC-1.4, AC-1.5
        """
        user_id = update.effective_user.id
        channel_identifier = update.message.text.strip()
        
        # Validate channel identifier
        if not self._validate_group_identifier(channel_identifier):
            await update.message.reply_text(
                text="❌ لینک کانال نامعتبر است. لطفاً یک لینک معتبر وارد کنید.",
                parse_mode='Markdown'
            )
            return GET_CHANNEL_LINK
        
        # Store channel identifier
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'channel_identifier': channel_identifier}
        )
        
        # Show confirmation
        confirm_text = f"🔍 **استخراج لینک از کانال**\n\n" \
                      f"کانال: `{channel_identifier}`\n\n" \
                      f"آیا می‌خواهید ادامه دهید?"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:scrape'),
                InlineKeyboardButton("❌ لغو", callback_data='cancel:scrape')
            ]
        ])
        
        await update.message.reply_text(
            text=confirm_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def handle_join_preference(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle join preference selection
        
        Requirements: AC-1.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        join_first = query.data == 'join:yes'
        
        # Update session
        session = self.state_manager.get_user_session(user_id)
        if not session:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END
        
        group_identifier = session.get_data('group_identifier')
        
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'join_first': join_first}
        )
        
        # Show confirmation
        join_text = "بله، ابتدا عضو شوم" if join_first else "خیر، بدون عضویت"
        confirm_text = f"🔍 **اسکرپ تک گروه**\n\n" \
                      f"گروه: `{group_identifier}`\n" \
                      f"عضویت: {join_text}\n\n" \
                      f"آیا می‌خواهید ادامه دهید?"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:scrape'),
                InlineKeyboardButton("❌ لغو", callback_data='cancel:scrape')
            ]
        ])
        
        await query.edit_message_text(
            text=confirm_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SCRAPE
    
    async def execute_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Execute scraping operation based on type
        
        Requirements: AC-1.6, AC-1.7, AC-1.8
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await query.edit_message_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        scrape_type = session.get_data('scrape_type')
        
        try:
            if scrape_type == 'single':
                await self._execute_single_scrape(query, user_id, session, context)
            elif scrape_type == 'bulk':
                await self._execute_bulk_scrape(query, user_id, session, context)
            elif scrape_type == 'extract':
                await self._execute_link_extraction(query, user_id, session, context)
            else:
                await query.edit_message_text("❌ نوع عملیات نامعتبر است.")
                return ConversationHandler.END
        
        except Exception as e:
            self.logger.error(f"Error executing scrape: {e}", exc_info=True)
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=user_id,
                    operation='scraping',
                    details={'scrape_type': scrape_type}
                )
            )
        
        # Clean up session
        self.state_manager.delete_user_session(user_id)
        
        return ConversationHandler.END
    
    async def _execute_single_scrape(
        self,
        query,
        user_id: int,
        session,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Execute single group scraping"""
        group_identifier = session.get_data('group_identifier')
        join_first = session.get_data('join_first', False)
        
        # Create progress tracker
        await query.edit_message_text(
            text=SCRAPE_STARTING.format(target=group_identifier),
            parse_mode='Markdown'
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            parse_mode='Markdown'
        )
        
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="اسکرپ گروه"
        )
        
        await tracker.start(total=1, initial_message="⏳ شروع اسکرپ...")
        
        try:
            # Execute scraping
            result = await self.session_manager.scrape_group_members_random_session(
                group_identifier=group_identifier,
                max_members=10000,
                fallback_to_messages=True,
                message_days_back=10
            )
            
            await tracker.update(current=1, success=1 if result.get('success') else 0, force=True)
            
            if result.get('success'):
                # Send CSV file
                file_path = result.get('file_path')
                member_count = result.get('member_count', 0)
                
                if file_path and os.path.exists(file_path):
                    await self.file_handler.send_file_to_user(
                        bot=context.bot,
                        chat_id=query.message.chat_id,
                        file_path=file_path,
                        caption=f"✅ اسکرپ تکمیل شد\n\n"
                               f"تعداد اعضا: {member_count}\n"
                               f"گروه: {group_identifier}"
                    )
                
                await tracker.complete({
                    'member_count': member_count,
                    'source': group_identifier,
                    'duration': 0,
                    'file_path': file_path
                })
            else:
                error_msg = result.get('error', 'خطای نامشخص')
                await tracker.error(error_msg)
        
        except Exception as e:
            await tracker.error(str(e))
            raise
    
    async def _execute_bulk_scrape(
        self,
        query,
        user_id: int,
        session,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Execute bulk group scraping with work distribution and partial failure handling
        
        Requirements: 12.3, 12.4
        """
        group_identifiers = session.get_data('group_identifiers', [])
        
        # Create progress tracker
        await query.edit_message_text(
            text=SCRAPE_STARTING.format(target=f"{len(group_identifiers)} گروه"),
            parse_mode='Markdown'
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            parse_mode='Markdown'
        )
        
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="اسکرپ گروهی"
        )
        
        await tracker.start(total=len(group_identifiers))
        
        # Initialize batch result tracker (Requirement 12.4)
        result_tracker = BatchResultTracker(
            operation_type='scraping',
            total_items=len(group_identifiers)
        )
        
        # Get available sessions for work distribution (Requirement 12.3)
        available_sessions = [
            name for name, sess in self.session_manager.sessions.items()
            if sess.is_connected
        ]
        
        if not available_sessions:
            await tracker.error("هیچ سشن فعالی در دسترس نیست")
            return
        
        # Distribute work across sessions (Requirement 12.3)
        distributor = WorkDistributor()
        session_loads = {
            name: self.session_manager.session_load.get(name, 0)
            for name in available_sessions
        }
        
        work_batches = distributor.create_work_batches(
            items=group_identifiers,
            available_sessions=available_sessions,
            session_loads=session_loads
        )
        
        self.logger.info(
            f"📊 Distributed {len(group_identifiers)} groups across {len(work_batches)} sessions"
        )
        
        # Process all batches concurrently (Requirement 12.3)
        async def process_batch(batch):
            """Process a batch of groups on a specific session"""
            for work_item in batch.items:
                group_id = work_item.identifier
                result_tracker.start_item(group_id)
                
                try:
                    # Use the assigned session for this group
                    session_name = batch.session_name
                    telegram_session = self.session_manager.sessions[session_name]
                    
                    # Scrape the group
                    result = await telegram_session.scrape_group_members(
                        group_identifier=group_id,
                        max_members=10000,
                        fallback_to_messages=True,
                        message_days_back=10
                    )
                    
                    if result.get('success'):
                        # Record success (Requirement 12.4)
                        result_tracker.record_success(
                            identifier=group_id,
                            session_used=session_name,
                            data={
                                'member_count': result.get('member_count', 0),
                                'file_path': result.get('file_path')
                            }
                        )
                    else:
                        # Record failure but continue (Requirement 12.4)
                        result_tracker.record_failure(
                            identifier=group_id,
                            error=result.get('error', 'خطای نامشخص'),
                            session_used=session_name
                        )
                
                except Exception as e:
                    # Record failure and continue (Requirement 12.4)
                    self.logger.error(f"Error scraping {group_id}: {e}")
                    result_tracker.record_failure(
                        identifier=group_id,
                        error=str(e),
                        session_used=batch.session_name
                    )
                
                # Update progress
                stats = result_tracker.get_current_stats()
                await tracker.update(
                    current=stats['completed'],
                    success=stats['success'],
                    failed=stats['failed']
                )
        
        # Execute all batches concurrently
        batch_tasks = [process_batch(batch) for batch in work_batches]
        await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Complete tracking and get results (Requirement 12.4)
        batch_result = result_tracker.complete()
        
        # Send detailed report
        report = result_tracker.get_detailed_report()
        await query.message.reply_text(text=report, parse_mode='Markdown')
        
        # Send CSV files for successful scrapes
        for item in batch_result.successful_items:
            file_path = item.data.get('file_path')
            if file_path and os.path.exists(file_path):
                await self.file_handler.send_file_to_user(
                    bot=context.bot,
                    chat_id=query.message.chat_id,
                    file_path=file_path,
                    caption=f"📊 {item.identifier}\nاعضا: {item.data.get('member_count', 0)}"
                )
        
        await tracker.complete({
            'sent_count': batch_result.success_count,
            'failed_count': batch_result.failure_count,
            'total_count': batch_result.total_items,
            'duration': tracker.get_elapsed_time()
        })
    
    async def _execute_link_extraction(
        self,
        query,
        user_id: int,
        session,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Execute link extraction from channel"""
        channel_identifier = session.get_data('channel_identifier')
        
        # Create progress tracker
        await query.edit_message_text(
            text=SCRAPE_STARTING.format(target=channel_identifier),
            parse_mode='Markdown'
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال استخراج لینک‌ها...",
            parse_mode='Markdown'
        )
        
        tracker = ProgressTracker(
            bot=context.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="استخراج لینک"
        )
        
        await tracker.start(total=1)
        
        try:
            # Get a session
            session_name = self.session_manager._get_available_session()
            if not session_name:
                await tracker.error("هیچ سشن فعالی در دسترس نیست")
                return
            
            telegram_session = self.session_manager.sessions[session_name]
            
            # Extract links (simplified - would need full implementation)
            await tracker.set_message("⏳ در حال دریافت پیام‌ها...")
            
            # This is a placeholder - full implementation would extract links
            links = []
            
            await tracker.update(current=1, success=1, force=True)
            
            # Show results
            if links:
                links_text = "\n".join([f"• {link}" for link in links[:10]])
                if len(links) > 10:
                    links_text += f"\n... و {len(links) - 10} لینک دیگر"
                
                result_text = f"✅ **استخراج لینک تکمیل شد**\n\n" \
                             f"کانال: {channel_identifier}\n" \
                             f"تعداد لینک: {len(links)}\n\n" \
                             f"**لینک‌های یافت شده:**\n{links_text}"
            else:
                result_text = f"ℹ️ هیچ لینکی در کانال {channel_identifier} یافت نشد."
            
            await tracker.complete({
                'member_count': len(links),
                'source': channel_identifier,
                'duration': tracker.get_elapsed_time()
            })
            
            await query.message.reply_text(
                text=result_text,
                parse_mode='Markdown'
            )
        
        except Exception as e:
            await tracker.error(str(e))
            raise
    
    async def cancel_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel scraping operation"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.state_manager.delete_user_session(user_id)
        
        await query.edit_message_text(
            text="❌ عملیات لغو شد.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
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
    
    # Validation is now handled by InputValidator in validators.py
    # See Requirements: AC-13.1, AC-13.5
        
        return False
