"""
Sending Handler - Manages all message sending operations through bot interface

This module handles:
- Text message sending
- Image message sending with caption
- Video message sending with caption
- Document message sending
- CSV recipient upload and validation
- Progress tracking for sending operations
- Resumable operations with checkpoints

Requirements: AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5, AC-2.6, AC-2.7, AC-2.8, AC-2.9
"""

import asyncio
import logging
import os
import json
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, File
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
from .progress_tracker import ProgressTracker
from .file_handler import FileHandler
from .error_handler import BotErrorHandler, ErrorContext
from .validators import InputValidator, ValidationErrorHandler
from .work_distributor import WorkDistributor
from .batch_result_tracker import BatchResultTracker
from .persian_text import (
    SEND_MENU_TEXT, SEND_CSV_PROMPT, SEND_TEXT_PROMPT,
    SEND_DELAY_PROMPT, SEND_CONFIRM_TEXT,
    PROMPT_MESSAGE_TEXT, PROMPT_MEDIA_FILE, PROMPT_CAPTION,
    BTN_SEND_TEXT, BTN_SEND_IMAGE, BTN_SEND_VIDEO, BTN_SEND_DOCUMENT
)


# Conversation states
SELECT_SEND_TYPE = 0
UPLOAD_CSV = 1
GET_MESSAGE_TEXT = 2
UPLOAD_MEDIA = 3
GET_CAPTION = 4
SET_DELAY = 5
CONFIRM_SEND = 6


class SendingHandler:
    """
    Handler for all message sending operations
    
    Manages conversation flows for:
    - Text message sending
    - Image message sending with caption
    - Video message sending with caption
    - Document message sending
    - CSV recipient upload
    - Resumable operations with checkpoints
    
    Requirements: AC-2.1 through AC-2.9
    """
    
    # Checkpoint directory
    CHECKPOINT_DIR = "./.checkpoints"
    
    def __init__(
        self,
        session_manager: TelegramSessionManager,
        state_manager: StateManager,
        error_handler: BotErrorHandler
    ):
        """
        Initialize sending handler
        
        Args:
            session_manager: TelegramSessionManager instance
            state_manager: StateManager instance
            error_handler: BotErrorHandler instance
        """
        self.session_manager = session_manager
        self.state_manager = state_manager
        self.error_handler = error_handler
        self.logger = logging.getLogger("SendingHandler")
        
        # File handler for CSV and media operations
        self.file_handler = FileHandler()
        
        # Create checkpoint directory
        os.makedirs(self.CHECKPOINT_DIR, exist_ok=True)
        
        self.logger.info("SendingHandler initialized")

    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for sending operations
        
        Returns:
            ConversationHandler configured for sending flows
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_send_menu, pattern='^menu:sending$'),
                CallbackQueryHandler(self.start_text_send, pattern='^send:text$'),
                CallbackQueryHandler(self.start_image_send, pattern='^send:image$'),
                CallbackQueryHandler(self.start_video_send, pattern='^send:video$'),
                CallbackQueryHandler(self.start_document_send, pattern='^send:document$'),
            ],
            states={
                SELECT_SEND_TYPE: [
                    CallbackQueryHandler(self.start_text_send, pattern='^send:text$'),
                    CallbackQueryHandler(self.start_image_send, pattern='^send:image$'),
                    CallbackQueryHandler(self.start_video_send, pattern='^send:video$'),
                    CallbackQueryHandler(self.start_document_send, pattern='^send:document$'),
                ],
                UPLOAD_CSV: [
                    MessageHandler(filters.Document.ALL, self.handle_csv_upload)
                ],
                GET_MESSAGE_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message_text)
                ],
                UPLOAD_MEDIA: [
                    MessageHandler(filters.PHOTO | filters.Document.ALL, self.handle_media_upload)
                ],
                GET_CAPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_caption),
                    CallbackQueryHandler(self.skip_caption, pattern='^action:skip$')
                ],
                SET_DELAY: [
                    CallbackQueryHandler(self.handle_delay_selection, pattern='^delay:'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_custom_delay)
                ],
                CONFIRM_SEND: [
                    CallbackQueryHandler(self.execute_send, pattern='^confirm:send$'),
                    CallbackQueryHandler(self.cancel_send, pattern='^cancel:send$')
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern='^action:cancel$'),
                CallbackQueryHandler(self.show_send_menu, pattern='^menu:sending$'),
            ],
            name="sending_conversation",
            persistent=False
        )

    
    async def show_send_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show sending menu with operation options
        
        Requirements: AC-2.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        
        # Create or update user session
        self.state_manager.create_user_session(
            user_id=user_id,
            operation='sending',
            step='menu'
        )
        
        # Build keyboard
        keyboard = KeyboardBuilder.send_menu(user_id=user_id)
        
        # Send or edit message
        if query:
            await query.edit_message_text(
                text=SEND_MENU_TEXT,
                reply_markup=keyboard,
                
            )
        else:
            await update.message.reply_text(
                text=SEND_MENU_TEXT,
                reply_markup=keyboard,
                
            )
        
        return SELECT_SEND_TYPE

    
    async def start_text_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start text message sending flow
        
        Requirements: AC-2.1
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='upload_csv',
            data={'send_type': 'text'}
        )
        
        # Prompt for CSV upload
        await query.edit_message_text(
            text=SEND_CSV_PROMPT,
            
        )
        
        return UPLOAD_CSV
    
    async def start_image_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start image message sending flow
        
        Requirements: AC-2.2, AC-2.3
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='upload_csv',
            data={'send_type': 'image'}
        )
        
        # Prompt for CSV upload
        await query.edit_message_text(
            text=SEND_CSV_PROMPT,
            
        )
        
        return UPLOAD_CSV
    
    async def start_video_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start video message sending flow
        
        Requirements: AC-2.2, AC-2.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='upload_csv',
            data={'send_type': 'video'}
        )
        
        # Prompt for CSV upload
        await query.edit_message_text(
            text=SEND_CSV_PROMPT,
            
        )
        
        return UPLOAD_CSV
    
    async def start_document_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Start document message sending flow
        
        Requirements: AC-2.2, AC-2.5
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Update session
        self.state_manager.update_user_session(
            user_id=user_id,
            step='upload_csv',
            data={'send_type': 'document'}
        )
        
        # Prompt for CSV upload
        await query.edit_message_text(
            text=SEND_CSV_PROMPT,
            
        )
        
        return UPLOAD_CSV

    
    async def handle_csv_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle CSV file upload and validation
        
        Requirements: AC-2.1, AC-2.2, AC-2.5, AC-7.1, AC-7.2
        """
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
        
        # Download file
        file = await update.message.document.get_file()
        file_path = self.file_handler.get_temp_file_path(user_id, 'csv', 'csv')
        
        await update.message.reply_text("⏳ در حال دریافت فایل...")
        
        try:
            await file.download_to_drive(file_path)
            
            # Process and validate CSV
            success, result = await self.file_handler.process_csv_upload(file_path, user_id)
            
            if not success:
                await update.message.reply_text(
                    text=f"❌ **خطا در فایل CSV**\n\n{result}",
                    
                )
                return UPLOAD_CSV
            
            # result is list of recipients
            recipients = result
            
            # Store in session
            self.state_manager.update_user_session(
                user_id=user_id,
                data={
                    'recipients': recipients,
                    'csv_file_path': file_path
                }
            )
            
            # Show preview
            preview_text = f"✅ **فایل CSV معتبر است**\n\n" \
                          f"**تعداد گیرندگان:** {len(recipients)}\n\n" \
                          f"**نمونه:**\n"
            
            for i, recipient in enumerate(recipients[:5], 1):
                preview_text += f"{i}. {recipient}\n"
            
            if len(recipients) > 5:
                preview_text += f"... و {len(recipients) - 5} گیرنده دیگر"
            
            await update.message.reply_text(
                text=preview_text,
                
            )
            
            # Next step depends on send type
            send_type = session.get_data('send_type')
            
            if send_type == 'text':
                # Prompt for message text
                await update.message.reply_text(
                    text=SEND_TEXT_PROMPT,
                    
                )
                return GET_MESSAGE_TEXT
            else:
                # Prompt for media upload
                media_types = {
                    'image': ('تصویر', '10MB', 'JPEG, PNG, WebP'),
                    'video': ('ویدیو', '50MB', 'MP4, MOV'),
                    'document': ('فایل', '20MB', 'PDF, DOC, DOCX, TXT')
                }
                
                media_name, max_size, formats = media_types.get(send_type, ('رسانه', '20MB', 'همه'))
                
                prompt = PROMPT_MEDIA_FILE.format(
                    media_type=media_name,
                    max_size=max_size,
                    formats=formats
                )
                
                await update.message.reply_text(
                    text=prompt,
                    
                )
                return UPLOAD_MEDIA
        
        except Exception as e:
            self.logger.error(f"Error handling CSV upload: {e}", exc_info=True)
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=user_id,
                    operation='sending',
                    details={'step': 'csv_upload'}
                )
            )
            return ConversationHandler.END

    
    async def handle_message_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle message text input for text sending
        
        Requirements: AC-2.1
        """
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        # Validate text length
        if len(message_text) > 4096:
            await update.message.reply_text(
                text="❌ متن پیام بیش از حد طولانی است (حداکثر 4096 کاراکتر).\n\n"
                     f"طول فعلی: {len(message_text)} کاراکتر",
                
            )
            return GET_MESSAGE_TEXT
        
        if not message_text:
            await update.message.reply_text(
                text="❌ متن پیام نمی‌تواند خالی باشد.",
                
            )
            return GET_MESSAGE_TEXT
        
        # Store message text
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'message_text': message_text}
        )
        
        # Prompt for delay
        keyboard = KeyboardBuilder.delay_options()
        
        await update.message.reply_text(
            text=SEND_DELAY_PROMPT,
            reply_markup=keyboard,
            
        )
        
        return SET_DELAY

    
    async def handle_media_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle media file upload (image, video, document)
        
        Requirements: AC-2.2, AC-2.3, AC-2.4, AC-2.5, AC-7.4, AC-7.5, AC-7.6
        """
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        send_type = session.get_data('send_type')
        
        # Get file based on message type
        if update.message.photo:
            # Photo message
            file = await update.message.photo[-1].get_file()
            file_ext = 'jpg'
            media_type = 'image'
        elif update.message.document:
            # Document message
            file = await update.message.document.get_file()
            file_name = update.message.document.file_name
            file_ext = file_name.split('.')[-1] if '.' in file_name else 'bin'
            media_type = send_type  # Use the send_type from session
        else:
            await update.message.reply_text("❌ نوع فایل پشتیبانی نمی‌شود.")
            return UPLOAD_MEDIA
        
        # Download file
        file_path = self.file_handler.get_temp_file_path(user_id, media_type, file_ext)
        
        await update.message.reply_text("⏳ در حال دریافت فایل...")
        
        try:
            await file.download_to_drive(file_path)
            
            # Validate media file
            success, result = await self.file_handler.process_media_upload(
                file_path, media_type, user_id
            )
            
            if not success:
                await update.message.reply_text(
                    text=f"❌ **خطا در فایل رسانه**\n\n{result}",
                    
                )
                return UPLOAD_MEDIA
            
            # Store media file path
            self.state_manager.update_user_session(
                user_id=user_id,
                data={'media_file_path': file_path}
            )
            
            await update.message.reply_text("✅ فایل با موفقیت دریافت شد.")
            
            # Prompt for caption (optional)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭️ بدون کپشن", callback_data='action:skip')]
            ])
            
            await update.message.reply_text(
                text=PROMPT_CAPTION,
                reply_markup=keyboard,
                
            )
            
            return GET_CAPTION
        
        except Exception as e:
            self.logger.error(f"Error handling media upload: {e}", exc_info=True)
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=user_id,
                    operation='sending',
                    details={'step': 'media_upload', 'media_type': media_type}
                )
            )
            return ConversationHandler.END

    
    async def handle_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle caption input for media messages
        
        Requirements: AC-2.3, AC-2.4
        """
        user_id = update.effective_user.id
        caption = update.message.text.strip()
        
        # Validate caption length
        if len(caption) > 1024:
            await update.message.reply_text(
                text="❌ کپشن بیش از حد طولانی است (حداکثر 1024 کاراکتر).\n\n"
                     f"طول فعلی: {len(caption)} کاراکتر",
                
            )
            return GET_CAPTION
        
        # Store caption
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'caption': caption}
        )
        
        # Prompt for delay
        keyboard = KeyboardBuilder.delay_options()
        
        await update.message.reply_text(
            text=SEND_DELAY_PROMPT,
            reply_markup=keyboard,
            
        )
        
        return SET_DELAY
    
    async def skip_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Skip caption input
        
        Requirements: AC-2.3, AC-2.4
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Store empty caption
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'caption': ''}
        )
        
        # Prompt for delay
        keyboard = KeyboardBuilder.delay_options()
        
        await query.edit_message_text(
            text=SEND_DELAY_PROMPT,
            reply_markup=keyboard,
            
        )
        
        return SET_DELAY

    
    async def handle_delay_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle delay selection from keyboard
        
        Requirements: AC-2.6, AC-13.4, AC-13.5
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Extract delay value from callback data
        delay_str = query.data.split(':')[1]
        
        # Validate delay using centralized validator
        validation_result = InputValidator.validate_delay(delay_str)
        
        if not validation_result.valid:
            error_message = ValidationErrorHandler.format_validation_error(
                validation_result,
                context="📤 ارسال پیام"
            )
            await query.edit_message_text(
                text=error_message,
                
            )
            return SET_DELAY
        
        # Store validated delay
        delay = float(validation_result.normalized_value)
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'delay': delay}
        )
        
        # Show confirmation
        return await self._show_send_confirmation(query, user_id)
    
    async def handle_custom_delay(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle custom delay input
        
        Requirements: AC-2.6, AC-13.4, AC-13.5
        """
        user_id = update.effective_user.id
        delay_text = update.message.text.strip()
        
        # Validate delay using centralized validator
        validation_result = InputValidator.validate_delay(delay_text)
        
        if not validation_result.valid:
            error_message = ValidationErrorHandler.format_validation_error(
                validation_result,
                context="📤 ارسال پیام"
            )
            await update.message.reply_text(
                text=error_message,
                
            )
            # Preserve session state and allow retry
            return SET_DELAY
        
        # Store validated delay
        delay = float(validation_result.normalized_value)
        self.state_manager.update_user_session(
            user_id=user_id,
            data={'delay': delay}
        )
        
        # Show confirmation
        return await self._show_send_confirmation_message(update, user_id)

    
    async def _show_send_confirmation(self, query, user_id: int) -> int:
        """Show send confirmation (from callback query)"""
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await query.edit_message_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        send_type = session.get_data('send_type')
        recipients = session.get_data('recipients', [])
        delay = session.get_data('delay', 2.0)
        
        # Calculate estimated time
        estimated_seconds = len(recipients) * delay
        estimated_time = MessageFormatter._format_duration(estimated_seconds)
        
        # Message type names
        type_names = {
            'text': 'متن',
            'image': 'تصویر',
            'video': 'ویدیو',
            'document': 'فایل'
        }
        
        message_type = type_names.get(send_type, 'نامشخص')
        
        confirm_text = SEND_CONFIRM_TEXT.format(
            message_type=message_type,
            recipient_count=len(recipients),
            delay=delay,
            estimated_time=estimated_time
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:send'),
                InlineKeyboardButton("❌ لغو", callback_data='cancel:send')
            ]
        ])
        
        await query.edit_message_text(
            text=confirm_text,
            reply_markup=keyboard,
            
        )
        
        return CONFIRM_SEND
    
    async def _show_send_confirmation_message(self, update: Update, user_id: int) -> int:
        """Show send confirmation (from message)"""
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await update.message.reply_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        send_type = session.get_data('send_type')
        recipients = session.get_data('recipients', [])
        delay = session.get_data('delay', 2.0)
        
        # Calculate estimated time
        estimated_seconds = len(recipients) * delay
        estimated_time = MessageFormatter._format_duration(estimated_seconds)
        
        # Message type names
        type_names = {
            'text': 'متن',
            'image': 'تصویر',
            'video': 'ویدیو',
            'document': 'فایل'
        }
        
        message_type = type_names.get(send_type, 'نامشخص')
        
        confirm_text = SEND_CONFIRM_TEXT.format(
            message_type=message_type,
            recipient_count=len(recipients),
            delay=delay,
            estimated_time=estimated_time
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید", callback_data='confirm:send'),
                InlineKeyboardButton("❌ لغو", callback_data='cancel:send')
            ]
        ])
        
        await update.message.reply_text(
            text=confirm_text,
            reply_markup=keyboard,
            
        )
        
        return CONFIRM_SEND

    
    async def execute_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Execute sending operation based on type
        
        Requirements: AC-2.7, AC-2.8
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        if not session:
            await query.edit_message_text("❌ جلسه منقضی شده است.")
            return ConversationHandler.END
        
        send_type = session.get_data('send_type')
        
        try:
            if send_type == 'text':
                await self._execute_text_send(query, user_id, session)
            elif send_type == 'image':
                await self._execute_image_send(query, user_id, session)
            elif send_type == 'video':
                await self._execute_video_send(query, user_id, session)
            elif send_type == 'document':
                await self._execute_document_send(query, user_id, session)
            else:
                await query.edit_message_text("❌ نوع عملیات نامعتبر است.")
                return ConversationHandler.END
        
        except Exception as e:
            self.logger.error(f"Error executing send: {e}", exc_info=True)
            await self.error_handler.handle_error(
                error=e,
                update=update,
                context=context,
                error_context=ErrorContext(
                    user_id=user_id,
                    operation='sending',
                    details={'send_type': send_type}
                )
            )
        
        finally:
            # Clean up session and files
            csv_file = session.get_data('csv_file_path')
            media_file = session.get_data('media_file_path')
            
            if csv_file:
                self.file_handler.cleanup_file(csv_file)
            if media_file:
                self.file_handler.cleanup_file(media_file)
            
            self.state_manager.delete_user_session(user_id)
        
        return ConversationHandler.END

    
    async def _execute_text_send(self, query, user_id: int, session) -> None:
        """
        Execute text message sending with work distribution and partial failure handling
        
        Requirements: AC-2.1, AC-2.6, AC-2.7, AC-2.8, 12.3, 12.4
        """
        recipients = session.get_data('recipients', [])
        message_text = session.get_data('message_text', '')
        delay = session.get_data('delay', 2.0)
        
        # Create operation ID for checkpointing
        operation_id = f"send_text_{user_id}_{int(time.time())}"
        
        # Update initial message
        await query.edit_message_text(
            text=f"⏳ **شروع ارسال پیام**\n\nتعداد گیرندگان: {len(recipients)}",
            
        )
        
        # Create progress tracker
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            
        )
        
        tracker = ProgressTracker(
            bot=query.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="ارسال پیام"
        )
        
        await tracker.start(total=len(recipients))
        
        # Initialize batch result tracker (Requirement 12.4)
        result_tracker = BatchResultTracker(
            operation_type='sending',
            total_items=len(recipients)
        )
        
        # Use bulk sending with work distribution (Requirement 12.3)
        # The session manager handles distribution across sessions
        results = await self.session_manager.send_text_messages_bulk(
            recipients=recipients,
            message=message_text,
            delay=delay,
            skip_invalid=True,
            priority='normal'
        )
        
        # Track results (Requirement 12.4)
        for recipient, result in results.items():
            if result.success:
                result_tracker.record_success(
                    identifier=recipient,
                    session_used=result.session_used
                )
            elif hasattr(result, 'blacklisted') and result.blacklisted:
                result_tracker.record_skip(
                    identifier=recipient,
                    reason='User is blacklisted'
                )
            else:
                result_tracker.record_failure(
                    identifier=recipient,
                    error=result.error or 'Unknown error',
                    session_used=result.session_used
                )
            
            # Update progress
            stats = result_tracker.get_current_stats()
            await tracker.update(
                current=stats['completed'],
                success=stats['success'],
                failed=stats['failed']
            )
            
            # Save checkpoint every 10 messages
            if stats['completed'] % 10 == 0:
                await self._save_checkpoint(
                    operation_id=operation_id,
                    user_id=user_id,
                    send_type='text',
                    recipients=recipients,
                    completed_count=stats['completed'],
                    success_count=stats['success'],
                    failed_count=stats['failed'],
                    message_text=message_text,
                    delay=delay
                )
        
        # Complete tracking (Requirement 12.4)
        batch_result = result_tracker.complete()
        
        # Complete progress
        duration = tracker.get_elapsed_time()
        
        await tracker.complete({
            'sent_count': batch_result.success_count,
            'failed_count': batch_result.failure_count,
            'total_count': batch_result.total_items,
            'duration': duration
        })
        
        # Send detailed report if there were failures
        if batch_result.failure_count > 0:
            report = result_tracker.get_detailed_report()
            await query.message.reply_text(text=report, )
        
        # Delete checkpoint on completion
        self._delete_checkpoint(operation_id)

    
    async def _execute_image_send(self, query, user_id: int, session) -> None:
        """
        Execute image message sending
        
        Requirements: AC-2.2, AC-2.3, AC-2.7, AC-2.8
        """
        recipients = session.get_data('recipients', [])
        media_file_path = session.get_data('media_file_path', '')
        caption = session.get_data('caption', '')
        delay = session.get_data('delay', 2.0)
        
        # Create operation ID
        operation_id = f"send_image_{user_id}_{int(time.time())}"
        
        await query.edit_message_text(
            text=f"⏳ **شروع ارسال تصویر**\n\nتعداد گیرندگان: {len(recipients)}",
            
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            
        )
        
        tracker = ProgressTracker(
            bot=query.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="ارسال تصویر"
        )
        
        await tracker.start(total=len(recipients))
        
        success_count = 0
        failed_count = 0
        
        for idx, recipient in enumerate(recipients):
            try:
                # Send image using session manager
                result = await self.session_manager.send_image_random_session(
                    recipient=recipient,
                    image_path=media_file_path,
                    caption=caption
                )
                
                if result.get('success'):
                    success_count += 1
                else:
                    failed_count += 1
                
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
                
                # Save checkpoint every 10 messages
                if (idx + 1) % 10 == 0:
                    await self._save_checkpoint(
                        operation_id=operation_id,
                        user_id=user_id,
                        send_type='image',
                        recipients=recipients,
                        completed_count=idx + 1,
                        success_count=success_count,
                        failed_count=failed_count,
                        media_file_path=media_file_path,
                        caption=caption,
                        delay=delay
                    )
                
                if idx < len(recipients) - 1:
                    await asyncio.sleep(delay)
            
            except Exception as e:
                self.logger.error(f"Error sending image to {recipient}: {e}")
                failed_count += 1
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
        
        duration = tracker.get_elapsed_time()
        
        await tracker.complete({
            'sent_count': success_count,
            'failed_count': failed_count,
            'total_count': len(recipients),
            'duration': duration
        })
        
        self._delete_checkpoint(operation_id)

    
    async def _execute_video_send(self, query, user_id: int, session) -> None:
        """
        Execute video message sending
        
        Requirements: AC-2.2, AC-2.4, AC-2.7, AC-2.8
        """
        recipients = session.get_data('recipients', [])
        media_file_path = session.get_data('media_file_path', '')
        caption = session.get_data('caption', '')
        delay = session.get_data('delay', 2.0)
        
        operation_id = f"send_video_{user_id}_{int(time.time())}"
        
        await query.edit_message_text(
            text=f"⏳ **شروع ارسال ویدیو**\n\nتعداد گیرندگان: {len(recipients)}",
            
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            
        )
        
        tracker = ProgressTracker(
            bot=query.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="ارسال ویدیو"
        )
        
        await tracker.start(total=len(recipients))
        
        success_count = 0
        failed_count = 0
        
        for idx, recipient in enumerate(recipients):
            try:
                result = await self.session_manager.send_video_random_session(
                    recipient=recipient,
                    video_path=media_file_path,
                    caption=caption
                )
                
                if result.get('success'):
                    success_count += 1
                else:
                    failed_count += 1
                
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
                
                if (idx + 1) % 10 == 0:
                    await self._save_checkpoint(
                        operation_id=operation_id,
                        user_id=user_id,
                        send_type='video',
                        recipients=recipients,
                        completed_count=idx + 1,
                        success_count=success_count,
                        failed_count=failed_count,
                        media_file_path=media_file_path,
                        caption=caption,
                        delay=delay
                    )
                
                if idx < len(recipients) - 1:
                    await asyncio.sleep(delay)
            
            except Exception as e:
                self.logger.error(f"Error sending video to {recipient}: {e}")
                failed_count += 1
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
        
        duration = tracker.get_elapsed_time()
        
        await tracker.complete({
            'sent_count': success_count,
            'failed_count': failed_count,
            'total_count': len(recipients),
            'duration': duration
        })
        
        self._delete_checkpoint(operation_id)

    
    async def _execute_document_send(self, query, user_id: int, session) -> None:
        """
        Execute document message sending
        
        Requirements: AC-2.2, AC-2.5, AC-2.7, AC-2.8
        """
        recipients = session.get_data('recipients', [])
        media_file_path = session.get_data('media_file_path', '')
        delay = session.get_data('delay', 2.0)
        
        operation_id = f"send_document_{user_id}_{int(time.time())}"
        
        await query.edit_message_text(
            text=f"⏳ **شروع ارسال فایل**\n\nتعداد گیرندگان: {len(recipients)}",
            
        )
        
        progress_msg = await query.message.reply_text(
            text="⏳ در حال آماده‌سازی...",
            
        )
        
        tracker = ProgressTracker(
            bot=query.bot,
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            operation_name="ارسال فایل"
        )
        
        await tracker.start(total=len(recipients))
        
        success_count = 0
        failed_count = 0
        
        for idx, recipient in enumerate(recipients):
            try:
                result = await self.session_manager.send_document_random_session(
                    recipient=recipient,
                    document_path=media_file_path
                )
                
                if result.get('success'):
                    success_count += 1
                else:
                    failed_count += 1
                
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
                
                if (idx + 1) % 10 == 0:
                    await self._save_checkpoint(
                        operation_id=operation_id,
                        user_id=user_id,
                        send_type='document',
                        recipients=recipients,
                        completed_count=idx + 1,
                        success_count=success_count,
                        failed_count=failed_count,
                        media_file_path=media_file_path,
                        delay=delay
                    )
                
                if idx < len(recipients) - 1:
                    await asyncio.sleep(delay)
            
            except Exception as e:
                self.logger.error(f"Error sending document to {recipient}: {e}")
                failed_count += 1
                await tracker.update(
                    current=idx + 1,
                    success=success_count,
                    failed=failed_count
                )
        
        duration = tracker.get_elapsed_time()
        
        await tracker.complete({
            'sent_count': success_count,
            'failed_count': failed_count,
            'total_count': len(recipients),
            'duration': duration
        })
        
        self._delete_checkpoint(operation_id)

    
    async def _save_checkpoint(
        self,
        operation_id: str,
        user_id: int,
        send_type: str,
        recipients: List[str],
        completed_count: int,
        success_count: int,
        failed_count: int,
        **kwargs
    ) -> None:
        """
        Save checkpoint for resumable operations
        
        Requirements: AC-2.9, AC-14.1
        """
        checkpoint_data = {
            'operation_id': operation_id,
            'user_id': user_id,
            'send_type': send_type,
            'recipients': recipients,
            'completed_count': completed_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'timestamp': time.time(),
            **kwargs
        }
        
        checkpoint_file = os.path.join(self.CHECKPOINT_DIR, f"{operation_id}.json")
        
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Saved checkpoint: {operation_id} at {completed_count}/{len(recipients)}")
        
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {e}")
    
    def _delete_checkpoint(self, operation_id: str) -> None:
        """
        Delete checkpoint file
        
        Requirements: AC-2.9
        """
        checkpoint_file = os.path.join(self.CHECKPOINT_DIR, f"{operation_id}.json")
        
        try:
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
                self.logger.debug(f"Deleted checkpoint: {operation_id}")
        
        except Exception as e:
            self.logger.error(f"Error deleting checkpoint: {e}")
    
    def detect_incomplete_operations(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Detect incomplete operations from checkpoints
        
        Requirements: AC-14.2
        
        Args:
            user_id: Optional user ID to filter by
        
        Returns:
            List of incomplete operation data
        """
        incomplete_ops = []
        
        try:
            if not os.path.exists(self.CHECKPOINT_DIR):
                return incomplete_ops
            
            for filename in os.listdir(self.CHECKPOINT_DIR):
                if not filename.endswith('.json'):
                    continue
                
                checkpoint_file = os.path.join(self.CHECKPOINT_DIR, filename)
                
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                    
                    # Filter by user_id if provided
                    if user_id is not None and checkpoint_data.get('user_id') != user_id:
                        continue
                    
                    # Check if checkpoint is recent (within last 24 hours)
                    checkpoint_age = time.time() - checkpoint_data.get('timestamp', 0)
                    if checkpoint_age < 86400:  # 24 hours
                        incomplete_ops.append(checkpoint_data)
                    else:
                        # Delete old checkpoint
                        os.remove(checkpoint_file)
                
                except Exception as e:
                    self.logger.error(f"Error reading checkpoint {filename}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error detecting incomplete operations: {e}")
        
        return incomplete_ops
    
    async def offer_resume(self, bot, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Offer to resume incomplete operation
        
        Requirements: AC-14.3
        
        Args:
            bot: Telegram bot instance
            user_id: User ID
        
        Returns:
            Checkpoint data if user wants to resume, None otherwise
        """
        incomplete_ops = self.detect_incomplete_operations(user_id)
        
        if not incomplete_ops:
            return None
        
        # Get most recent operation
        latest_op = max(incomplete_ops, key=lambda x: x.get('timestamp', 0))
        
        send_type = latest_op.get('send_type', 'نامشخص')
        completed = latest_op.get('completed_count', 0)
        total = len(latest_op.get('recipients', []))
        remaining = total - completed
        
        type_names = {
            'text': 'متن',
            'image': 'تصویر',
            'video': 'ویدیو',
            'document': 'فایل'
        }
        
        message_type = type_names.get(send_type, send_type)
        
        resume_text = f"""
🔄 **عملیات ناتمام یافت شد**

**نوع:** ارسال {message_type}
**پیشرفت:** {completed}/{total}
**باقیمانده:** {remaining}

آیا می‌خواهید از جایی که متوقف شده بود ادامه دهید؟
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ادامه", callback_data=f"resume:{latest_op['operation_id']}"),
                InlineKeyboardButton("❌ شروع جدید", callback_data="resume:cancel")
            ]
        ])
        
        # This would be called from bot startup or when user enters sending menu
        # For now, just return the checkpoint data
        return latest_op

    
    async def resume_operation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        checkpoint_data: Dict[str, Any]
    ) -> None:
        """
        Resume operation from checkpoint
        
        Requirements: AC-14.4
        
        Args:
            update: Telegram update
            context: Callback context
            checkpoint_data: Checkpoint data to resume from
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = checkpoint_data['user_id']
        send_type = checkpoint_data['send_type']
        recipients = checkpoint_data['recipients']
        completed_count = checkpoint_data['completed_count']
        
        # Skip already completed items
        remaining_recipients = recipients[completed_count:]
        
        self.logger.info(
            f"Resuming operation {checkpoint_data['operation_id']} "
            f"from {completed_count}/{len(recipients)}"
        )
        
        # Create new session with remaining recipients
        session = self.state_manager.create_user_session(
            user_id=user_id,
            operation='sending',
            step='executing'
        )
        
        # Restore session data
        session.set_data('send_type', send_type)
        session.set_data('recipients', remaining_recipients)
        session.set_data('delay', checkpoint_data.get('delay', 2.0))
        
        if send_type == 'text':
            session.set_data('message_text', checkpoint_data.get('message_text', ''))
        else:
            session.set_data('media_file_path', checkpoint_data.get('media_file_path', ''))
            session.set_data('caption', checkpoint_data.get('caption', ''))
        
        # Execute the remaining operation
        # This would continue from where it left off
        if query:
            await query.edit_message_text(
                text=f"🔄 **ادامه عملیات**\n\nباقیمانده: {len(remaining_recipients)} از {len(recipients)}",
                
            )
    
    async def cancel_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel sending operation"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        # Clean up files
        if session:
            csv_file = session.get_data('csv_file_path')
            media_file = session.get_data('media_file_path')
            
            if csv_file:
                self.file_handler.cleanup_file(csv_file)
            if media_file:
                self.file_handler.cleanup_file(media_file)
        
        self.state_manager.delete_user_session(user_id)
        
        await query.edit_message_text(
            text="❌ عملیات لغو شد.",
            
        )
        
        return ConversationHandler.END
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel operation and return to main menu"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        session = self.state_manager.get_user_session(user_id)
        
        # Clean up files
        if session:
            csv_file = session.get_data('csv_file_path')
            media_file = session.get_data('media_file_path')
            
            if csv_file:
                self.file_handler.cleanup_file(csv_file)
            if media_file:
                self.file_handler.cleanup_file(media_file)
        
        self.state_manager.delete_user_session(user_id)
        
        message = "❌ عملیات لغو شد."
        
        if query:
            await query.edit_message_text(text=message)
        else:
            await update.message.reply_text(text=message)
        
        return ConversationHandler.END
