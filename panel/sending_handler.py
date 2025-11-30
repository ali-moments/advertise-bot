"""
SendingHandler - Handles message sending operations with conversation flows
"""

import asyncio
import csv
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
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
from .progress_tracker import ProgressTracker, ProgressTrackerFactory
from .file_handler import FileHandler
from .persian_text import (
    PROMPT_CSV_FILE, PROMPT_MESSAGE_TEXT, PROMPT_MEDIA_FILE,
    PROMPT_CAPTION, PROMPT_DELAY, ERROR_TEMPLATE,
    FILE_UPLOAD_SUCCESS, FILE_VALIDATION_FAILED,
    CSV_VALID, CSV_INVALID_FORMAT, CSV_EMPTY,
    OPERATION_CANCELLED, PLEASE_WAIT
)


# Conversation states
(
    SELECT_SEND_TYPE,
    UPLOAD_CSV,
    UPLOAD_MEDIA,
    GET_MESSAGE_TEXT,
    GET_CAPTION,
    SELECT_DELAY,
    CONFIRM_SEND
) = range(7)


@dataclass
class SendingSession:
    """User session data for sending operations"""
    user_id: int
    send_type: str  # 'text', 'image', 'video', 'document'
    csv_file_path: Optional[str] = None
    recipients: List[str] = None
    message_text: Optional[str] = None
    media_file_path: Optional[str] = None
    caption: Optional[str] = None
    delay: float = 2.0
    started_at: float = 0.0
    
    def __post_init__(self):
        if self.recipients is None:
            self.recipients = []
        if self.started_at == 0.0:
            self.started_at = time.time()


class SendingHandler:
    """Handle message sending operations"""
    
    def __init__(self, session_manager: TelegramManagerApp, temp_dir: str = "./temp"):
        """
        Initialize sending handler
        
        Args:
            session_manager: TelegramManagerApp instance
            temp_dir: Directory for temporary files
        """
        self.session_manager = session_manager
        self.temp_dir = temp_dir
        self.user_sessions: Dict[int, SendingSession] = {}
        
        # Initialize file handler
        self.file_handler = FileHandler(temp_dir=temp_dir)
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for sending operations
        
        Returns:
            ConversationHandler configured for sending flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start_send_text, pattern='^send:text$'),
                CallbackQueryHandler(self.start_send_image, pattern='^send:image$'),
                CallbackQueryHandler(self.start_send_video, pattern='^send:video$'),
                CallbackQueryHandler(self.start_send_document, pattern='^send:document$'),
            ],
            states={
                UPLOAD_CSV: [
                    MessageHandler(filters.Document.ALL, self.handle_csv_upload)
                ],
                GET_MESSAGE_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message_text)
                ],
                UPLOAD_MEDIA: [
                    MessageHandler(
                        filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                        self.handle_media_upload
                    )
                ],
                GET_CAPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_caption),
                    CommandHandler('skip', self.skip_caption)
                ],
                SELECT_DELAY: [
                    CallbackQueryHandler(self.handle_delay_selection, pattern='^delay:')
                ],
                CONFIRM_SEND: [
                    CallbackQueryHandler(self.handle_send_confirmation, pattern='^(confirm_send|cancel_send)$')
                ],
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_send),
                CallbackQueryHandler(self.cancel_send, pattern='^action:cancel$')
            ],
        )
    
    async def start_send_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start text message sending flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize session
        self.user_sessions[user_id] = SendingSession(
            user_id=user_id,
            send_type='text'
        )
        
        message = PROMPT_CSV_FILE
        keyboard = KeyboardBuilder.back_main(back_data="nav:send_menu", main_data="nav:main")
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return UPLOAD_CSV
    
    async def start_send_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start image sending flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize session
        self.user_sessions[user_id] = SendingSession(
            user_id=user_id,
            send_type='image'
        )
        
        message = PROMPT_CSV_FILE
        keyboard = KeyboardBuilder.back_main(back_data="nav:send_menu", main_data="nav:main")
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return UPLOAD_CSV
    
    async def start_send_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start video sending flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize session
        self.user_sessions[user_id] = SendingSession(
            user_id=user_id,
            send_type='video'
        )
        
        message = PROMPT_CSV_FILE
        keyboard = KeyboardBuilder.back_main(back_data="nav:send_menu", main_data="nav:main")
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return UPLOAD_CSV
    
    async def start_send_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start document sending flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Initialize session
        self.user_sessions[user_id] = SendingSession(
            user_id=user_id,
            send_type='document'
        )
        
        message = PROMPT_CSV_FILE
        keyboard = KeyboardBuilder.back_main(back_data="nav:send_menu", main_data="nav:main")
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return UPLOAD_CSV
    
    async def handle_csv_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle CSV file upload and validation
        
        Requirements: AC-7.1, AC-7.2
        """
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Download file
        file = await update.message.document.get_file()
        file_path = self.file_handler.get_temp_file_path(user_id, 'csv', '.csv')
        await file.download_to_drive(file_path)
        
        # Validate CSV using FileHandler
        validation_result = self.file_handler.validate_csv(file_path)
        
        if not validation_result.valid:
            self.file_handler.cleanup_file(file_path)
            error_msg = MessageFormatter.format_error(
                error_type="فایل CSV",
                description=validation_result.error,
                show_retry=True
            )
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return UPLOAD_CSV
        
        # Store CSV info
        session.csv_file_path = file_path
        session.recipients = validation_result.recipients
        
        # Show CSV preview
        preview_msg = MessageFormatter.format_csv_preview(
            row_count=len(session.recipients),
            columns=validation_result.columns if validation_result.columns else ['recipient'],
            sample_data=validation_result.sample_data[:3]
        )
        
        await update.message.reply_text(
            f"{FILE_UPLOAD_SUCCESS}\n\n{preview_msg}",
            parse_mode='Markdown'
        )
        
        # Next step depends on send type
        if session.send_type == 'text':
            message = PROMPT_MESSAGE_TEXT
            await update.message.reply_text(message, parse_mode='Markdown')
            return GET_MESSAGE_TEXT
        else:
            # Media types need media file
            media_type_map = {
                'image': 'تصویر',
                'video': 'ویدیو',
                'document': 'فایل'
            }
            message = PROMPT_MEDIA_FILE.format(
                media_type=media_type_map.get(session.send_type, 'رسانه'),
                max_size='50MB',
                formats='همه فرمت‌ها'
            )
            await update.message.reply_text(message, parse_mode='Markdown')
            return UPLOAD_MEDIA
    
    async def handle_message_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle message text input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        session.message_text = update.message.text
        
        # Show delay selection
        message = PROMPT_DELAY
        keyboard = KeyboardBuilder.delay_options()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_DELAY
    
    async def handle_media_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle media file upload and validation
        
        Requirements: AC-7.4, AC-7.5
        """
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Get file based on type
        if session.send_type == 'image' and update.message.photo:
            file = await update.message.photo[-1].get_file()
            ext = 'jpg'
        elif session.send_type == 'video' and update.message.video:
            file = await update.message.video.get_file()
            ext = 'mp4'
        elif session.send_type == 'document' and update.message.document:
            file = await update.message.document.get_file()
            ext = update.message.document.file_name.split('.')[-1] if '.' in update.message.document.file_name else 'bin'
        else:
            await update.message.reply_text(
                "❌ نوع فایل نامعتبر است. لطفاً فایل مناسب را ارسال کنید."
            )
            return UPLOAD_MEDIA
        
        # Download file
        file_path = self.file_handler.get_temp_file_path(user_id, 'media', ext)
        await file.download_to_drive(file_path)
        
        # Validate media file using FileHandler
        validation_result = self.file_handler.validate_media(file_path, session.send_type)
        
        if not validation_result.valid:
            self.file_handler.cleanup_file(file_path)
            error_msg = MessageFormatter.format_error(
                error_type="فایل رسانه",
                description=validation_result.error,
                show_retry=True
            )
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return UPLOAD_MEDIA
        
        session.media_file_path = file_path
        
        # Show file info
        size_mb = validation_result.metadata.get('size_mb', 0)
        await update.message.reply_text(
            f"{FILE_UPLOAD_SUCCESS}\n\n📁 حجم فایل: {size_mb} MB"
        )
        
        # Ask for caption
        message = PROMPT_CAPTION
        await update.message.reply_text(message, parse_mode='Markdown')
        
        return GET_CAPTION
    
    async def handle_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle caption input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        session.caption = update.message.text
        
        # Show delay selection
        message = PROMPT_DELAY
        keyboard = KeyboardBuilder.delay_options()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_DELAY
    
    async def skip_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Skip caption input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        session.caption = None
        
        # Show delay selection
        message = PROMPT_DELAY
        keyboard = KeyboardBuilder.delay_options()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return SELECT_DELAY
    
    async def handle_delay_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle delay selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Extract delay value
        delay_str = query.data.split(':')[1]
        session.delay = float(delay_str)
        
        # Show preview and confirmation
        preview_msg = self._generate_send_preview(session)
        
        keyboard = KeyboardBuilder.confirm_cancel(
            confirm_data="confirm_send",
            cancel_data="cancel_send"
        )
        
        await query.edit_message_text(
            preview_msg,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        return CONFIRM_SEND
    
    async def handle_send_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle send confirmation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        if query.data == 'cancel_send':
            await self._cleanup_session(user_id)
            await query.edit_message_text(OPERATION_CANCELLED)
            return ConversationHandler.END
        
        session = self.user_sessions[user_id]
        
        # Show processing message
        await query.edit_message_text(PLEASE_WAIT, parse_mode='Markdown')
        
        # Execute sending operation
        try:
            await self._execute_send(query, session)
        except Exception as e:
            error_msg = MessageFormatter.format_error(
                error_type="ارسال",
                description=str(e),
                show_retry=False
            )
            await query.edit_message_text(error_msg, parse_mode='Markdown')
        finally:
            await self._cleanup_session(user_id)
        
        return ConversationHandler.END
    
    async def cancel_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel sending operation"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            await self._cleanup_session(user_id)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(OPERATION_CANCELLED)
        else:
            await update.message.reply_text(OPERATION_CANCELLED)
        
        return ConversationHandler.END
    

    
    def _generate_send_preview(self, session: SendingSession) -> str:
        """
        Generate preview message for sending confirmation
        
        Shows:
        - Recipient count from CSV
        - Calculated estimated time
        - Session distribution
        - Confirmation prompt
        
        Requirements: AC-2.9, AC-6.8
        """
        message_type_map = {
            'text': 'متن',
            'image': 'تصویر',
            'video': 'ویدیو',
            'document': 'فایل'
        }
        
        message_type = message_type_map.get(session.send_type, 'پیام')
        recipient_count = len(session.recipients)
        
        # Calculate estimated time
        # Account for parallel sending across sessions
        sessions_count = len(self.session_manager.sessions) if hasattr(self.session_manager, 'sessions') else 1
        connected_sessions = 0
        if hasattr(self.session_manager, 'sessions'):
            connected_sessions = sum(1 for s in self.session_manager.sessions.values() if s.is_connected)
        
        if connected_sessions == 0:
            connected_sessions = 1
        
        # Estimate time considering parallel execution
        recipients_per_session = recipient_count / connected_sessions
        estimated_seconds = recipients_per_session * session.delay
        estimated_time = MessageFormatter._format_duration(estimated_seconds)
        
        # Calculate session distribution
        avg_per_session = recipient_count // max(connected_sessions, 1)
        remainder = recipient_count % max(connected_sessions, 1)
        
        preview = f"""
✅ **پیش‌نمایش ارسال**

**نوع پیام:** {message_type}
**تعداد گیرنده:** {recipient_count}
**تأخیر بین پیام‌ها:** {session.delay} ثانیه
**زمان تخمینی:** {estimated_time}

**توزیع سشن‌ها:**
• سشن‌های متصل: {connected_sessions}
• میانگین هر سشن: {avg_per_session} پیام
"""
        
        if remainder > 0:
            preview += f"• {remainder} پیام اضافی به سشن‌های اول\n"
        
        preview += "\n"
        
        # Show sample recipients
        if len(session.recipients) > 0:
            sample_recipients = session.recipients[:3]
            preview += "**نمونه گیرندگان:**\n"
            for recipient in sample_recipients:
                preview += f"• {recipient}\n"
            if len(session.recipients) > 3:
                preview += f"• و {len(session.recipients) - 3} گیرنده دیگر...\n"
            preview += "\n"
        
        if session.send_type == 'text' and session.message_text:
            preview += f"**متن پیام:**\n```\n{session.message_text[:100]}{'...' if len(session.message_text) > 100 else ''}\n```\n\n"
        
        if session.caption:
            preview += f"**کپشن:**\n```\n{session.caption[:100]}{'...' if len(session.caption) > 100 else ''}\n```\n\n"
        
        preview += "آیا می‌خواهید ارسال شروع شود?"
        
        return preview
    
    async def _execute_send(self, query, session: SendingSession):
        """Execute the sending operation with progress tracking"""
        # Create progress tracker
        progress_tracker = await ProgressTrackerFactory.create(
            bot=query.bot,
            chat_id=query.message.chat_id,
            operation_name="ارسال پیام"
        )
        
        await progress_tracker.start(
            total=len(session.recipients),
            initial_message=f"⏳ **ارسال پیام**\n\nشروع ارسال به {len(session.recipients)} گیرنده..."
        )
        
        start_time = time.time()
        
        # Create a task to monitor progress
        progress_task = asyncio.create_task(
            self._monitor_send_progress(progress_tracker, session.recipients)
        )
        
        try:
            if session.send_type == 'text':
                # Send text messages
                results = await self.session_manager.send_text_messages_bulk(
                    recipients=session.recipients,
                    message=session.message_text,
                    delay=session.delay
                )
            else:
                # Send media messages
                results = await self.session_manager.send_media_messages_bulk(
                    recipients=session.recipients,
                    media_path=session.media_file_path,
                    media_type=session.send_type,
                    caption=session.caption,
                    delay=session.delay
                )
            
            # Cancel progress monitoring
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            # Count results
            sent_count = sum(1 for r in results.values() if r.success)
            failed_count = len(results) - sent_count
            duration = time.time() - start_time
            
            # Show completion with detailed statistics
            await progress_tracker.complete({
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_count': len(results),
                'duration': duration
            })
        
        except Exception as e:
            # Cancel progress monitoring
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            await progress_tracker.error(str(e), "ارسال")
            raise
    
    async def _monitor_send_progress(self, progress_tracker: ProgressTracker, recipients: List[str]):
        """
        Monitor sending progress and update tracker
        
        This runs in the background and updates progress every 2 seconds
        """
        try:
            while not progress_tracker.is_complete:
                await asyncio.sleep(2.0)
                
                # Force update to show current progress
                await progress_tracker.update(force=True)
        except asyncio.CancelledError:
            # Task was cancelled, which is expected
            pass
    
    async def _cleanup_session(self, user_id: int):
        """
        Clean up user session and temporary files
        
        Uses FileHandler for proper cleanup
        """
        if user_id not in self.user_sessions:
            return
        
        session = self.user_sessions[user_id]
        
        # Delete temporary files using FileHandler
        if session.csv_file_path:
            self.file_handler.cleanup_file(session.csv_file_path)
        
        if session.media_file_path:
            self.file_handler.cleanup_file(session.media_file_path)
        
        # Remove session
        del self.user_sessions[user_id]
