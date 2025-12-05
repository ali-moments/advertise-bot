"""
Admin Authentication Decorator and Utilities

This module provides authentication and authorization functionality for the bot panel.
It implements admin-only access control through decorators and validation functions.

Requirements: 8.1 - Admin access control
"""

import logging
from functools import wraps
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .config import ADMIN_USERS

logger = logging.getLogger("TelegramBotPanel.Auth")


def admin_only(func: Callable) -> Callable:
    """
    Decorator for admin-only access control.
    
    This decorator validates that the user making the request is in the ADMIN_USERS list.
    If the user is not authorized, it sends an access denied message and terminates the handler.
    
    Usage:
        @admin_only
        async def my_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Handler code that only admins can access
            pass
    
    Args:
        func: The async handler function to wrap
        
    Returns:
        Wrapped function with admin authentication
        
    Requirements:
        - AC-8.1: WHEN a non-admin user sends a command THEN the System SHALL respond 
                  with an access denied message
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract update from args - it could be self, update, context or just update, context
        update: Optional[Update] = None
        context: Optional[ContextTypes.DEFAULT_TYPE] = None
        
        # Handle both instance methods (self, update, context) and functions (update, context)
        if len(args) >= 2:
            if isinstance(args[0], Update):
                update = args[0]
                context = args[1] if len(args) > 1 else kwargs.get('context')
            elif isinstance(args[1], Update):
                update = args[1]
                context = args[2] if len(args) > 2 else kwargs.get('context')
        
        if not update:
            logger.error("admin_only decorator: Could not extract Update from arguments")
            return ConversationHandler.END
        
        # Get user ID from update
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
        elif update.message and update.message.from_user:
            user_id = update.message.from_user.id
        elif update.callback_query and update.callback_query.from_user:
            user_id = update.callback_query.from_user.id
        
        if not user_id:
            logger.warning("admin_only decorator: Could not extract user_id from update")
            return ConversationHandler.END
        
        # Check if user is admin
        if not is_admin(user_id):
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            await send_not_authorized(update)
            return ConversationHandler.END
        
        # User is authorized, proceed with handler
        logger.debug(f"Admin user {user_id} authorized for {func.__name__}")
        return await func(*args, **kwargs)
    
    return wrapper


def is_admin(user_id: int) -> bool:
    """
    Check if a user ID is in the admin list.
    
    Args:
        user_id: Telegram user ID to check
        
    Returns:
        True if user is admin, False otherwise
        
    Requirements:
        - AC-8.1: User ID validation against ADMIN_USERS list
    """
    return user_id in ADMIN_USERS


async def send_not_authorized(update: Update) -> None:
    """
    Send access denied message to unauthorized user.
    
    This function sends a Persian-language message informing the user that they
    don't have permission to use the bot.
    
    Args:
        update: Telegram Update object
        
    Requirements:
        - AC-8.1: Access denied message handler
        - AC-6.1: Persian language text
    """
    message = """
⚠️ **دسترسی محدود**

شما دسترسی لازم برای استفاده از این ربات را ندارید.

این ربات فقط برای مدیران سیستم در دسترس است.
"""
    
    try:
        # Try to send via message
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        # Try to send via callback query
        elif update.callback_query:
            await update.callback_query.answer("⚠️ دسترسی محدود", show_alert=True)
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
        # Try to send via effective message
        elif update.effective_message:
            await update.effective_message.reply_text(message, parse_mode='Markdown')
        else:
            logger.error("Could not send not_authorized message - no message context found")
    
    except Exception as e:
        logger.error(f"Error sending not_authorized message: {e}")


def get_admin_list() -> list[int]:
    """
    Get the list of admin user IDs.
    
    Returns:
        List of admin Telegram user IDs
        
    Requirements:
        - AC-8.2: Display admin list
    """
    return ADMIN_USERS.copy()


def format_admin_list() -> str:
    """
    Format the admin list for display.
    
    Returns:
        Formatted Persian text with admin list
        
    Requirements:
        - AC-8.2: Display admin list
        - AC-6.1: Persian language text
    """
    admins_list = "\n".join([f"🔹 {admin_id}" for admin_id in ADMIN_USERS])
    
    message = f"""
👥 **لیست ادمین‌های ربات**

{admins_list}

**تعداد کل:** {len(ADMIN_USERS)} ادمین
"""
    
    return message
