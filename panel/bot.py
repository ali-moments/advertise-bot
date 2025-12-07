"""
Telegram Bot Control Panel - Main Bot Class

This module provides the main bot application that integrates all handlers
and provides the primary interface for administrators to manage the Telegram
session management system.

Requirements: All requirements (main integration point)
"""

import asyncio
import logging
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

from telegram_manager.manager import TelegramSessionManager
from .config import BOT_TOKEN, ADMIN_USERS
from .auth import admin_only, format_admin_list
from .state_manager import StateManager
from .error_handler import BotErrorHandler, ErrorContext
from .logging_config import get_logger
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .navigation import get_navigation_manager
from .rate_limiter import RateLimiter
from .persian_text import (
    MAIN_MENU_WELCOME,
    HELP_MENU,
    BTN_MAIN_MENU
)

# Import all handlers
from .scraping_handler import ScrapingHandler
from .sending_handler import SendingHandler
from .monitoring_handler import MonitoringHandler
from .session_handler import SessionHandler
from .system_status_handler import SystemStatusHandler
from .operation_history_handler import OperationHistoryHandler
from .config_handler import ConfigurationHandler


class TelegramBotPanel:
    """
    Main Telegram Bot Control Panel Application
    
    This class integrates all handlers and provides the primary interface
    for administrators to manage the Telegram session management system.
    
    Features:
    - Admin authentication
    - Command handlers (/start, /status, /admins, /help)
    - Callback query routing
    - Navigation system
    - Global error handling
    - Integration with all feature handlers
    
    Requirements:
        - AC-6.6: Navigation system
        - AC-8.1: Admin authentication
        - AC-8.2: Admin list display
        - AC-9.1, AC-9.2, AC-9.3, AC-9.4: Error handling
        - AC-18.1: Help system
    """
    
    def __init__(self, session_manager: TelegramSessionManager):
        """
        Initialize the Telegram Bot Panel
        
        Args:
            session_manager: TelegramSessionManager instance for backend operations
        """
        self.session_manager = session_manager
        self.logger = get_logger("TelegramBotPanel")
        
        # Initialize state manager
        self.state_manager = StateManager()
        
        # Initialize error handler
        self.error_handler = BotErrorHandler(logger_name="TelegramBotPanel")
        
        # Initialize navigation manager
        self.navigation_manager = get_navigation_manager()
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter()
        
        # Initialize all feature handlers
        self.scraping_handler = ScrapingHandler(
            session_manager=session_manager,
            state_manager=self.state_manager,
            error_handler=self.error_handler
        )
        
        self.sending_handler = SendingHandler(
            session_manager=session_manager,
            state_manager=self.state_manager,
            error_handler=self.error_handler
        )
        
        self.monitoring_handler = MonitoringHandler(
            session_manager=session_manager,
            state_manager=self.state_manager,
            error_handler=self.error_handler
        )
        
        self.session_handler = SessionHandler(
            session_manager=session_manager,
            state_manager=self.state_manager,
            error_handler=self.error_handler
        )
        
        self.system_status_handler = SystemStatusHandler(
            session_manager=session_manager
        )
        
        self.operation_history_handler = OperationHistoryHandler(
            state_manager=self.state_manager
        )
        
        self.config_handler = ConfigurationHandler(
            error_handler=self.error_handler
        )
        
        # Application instance (will be created in setup)
        self.application: Optional[Application] = None
        
        self.logger.info("TelegramBotPanel initialized")
    
    async def setup(self) -> Application:
        """
        Set up the bot application with all handlers
        
        Returns:
            Configured Application instance
        """
        self.logger.info("Setting up bot application...")
        
        # Build application
        self.application = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .build()
        )
        
        # Set up handlers
        self._setup_command_handlers()
        self._setup_conversation_handlers()
        self._setup_callback_handlers()
        self._setup_error_handler()
        
        # Set bot commands for UI
        await self._set_bot_commands()
        
        # Start cleanup tasks
        await self.state_manager.start_cleanup_task()
        await self.operation_history_handler.start_cleanup_task()
        
        self.logger.info("Bot application setup complete")
        return self.application
    
    def _setup_command_handlers(self):
        """
        Set up command handlers for the bot
        
        Commands:
        - /start: Show main menu
        - /status: Show system status
        - /admins: Show admin list
        - /help: Show help menu
        
        Requirements: AC-8.2, AC-18.1
        """
        self.logger.info("Setting up command handlers...")
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("admins", self.admins_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        self.logger.info("Command handlers registered")
    
    def _setup_conversation_handlers(self):
        """
        Set up conversation handlers for all features
        
        Registers conversation handlers from:
        - ScrapingHandler
        - SendingHandler
        - MonitoringHandler
        - SessionHandler
        - SystemStatusHandler
        - OperationHistoryHandler
        """
        self.logger.info("Setting up conversation handlers...")
        
        # Add conversation handlers from each feature handler
        self.application.add_handler(self.scraping_handler.get_conversation_handler())
        self.application.add_handler(self.sending_handler.get_conversation_handler())
        self.application.add_handler(self.monitoring_handler.get_conversation_handler())
        self.application.add_handler(self.session_handler.get_conversation_handler())
        self.application.add_handler(self.system_status_handler.get_conversation_handler())
        self.application.add_handler(self.operation_history_handler.get_conversation_handler())
        self.application.add_handler(self.config_handler.get_conversation_handler())
        
        self.logger.info("Conversation handlers registered")
    
    def _setup_callback_handlers(self):
        """
        Set up callback query handlers for navigation and actions
        
        Handles:
        - Navigation callbacks (nav:*)
        - Action callbacks (action:*)
        - Menu callbacks (menu:*)
        
        Requirements: AC-6.2, AC-6.6
        """
        self.logger.info("Setting up callback handlers...")
        
        # Navigation handlers
        self.application.add_handler(
            CallbackQueryHandler(self.handle_main_menu, pattern='^nav:main$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_back, pattern='^nav:back$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_cancel, pattern='^action:cancel$')
        )
        
        # Menu handlers (fallback for direct menu access)
        self.application.add_handler(
            CallbackQueryHandler(self.show_scraping_menu, pattern='^menu:scraping$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.show_sending_menu, pattern='^menu:sending$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.show_monitoring_menu, pattern='^menu:monitoring$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.show_sessions_menu, pattern='^menu:sessions$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.show_settings_menu, pattern='^menu:settings$')
        )
        
        # Help handlers
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_main, pattern='^help:main$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_scraping, pattern='^help:scraping$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_sending, pattern='^help:sending$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_monitoring, pattern='^help:monitoring$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_sessions, pattern='^help:sessions$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_status, pattern='^help:status$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_history, pattern='^help:history$')
        )
        self.application.add_handler(
            CallbackQueryHandler(self.handle_help_config, pattern='^help:config$')
        )
        
        # Catch-all for unknown callbacks
        self.application.add_handler(
            CallbackQueryHandler(self.handle_unknown_callback)
        )
        
        self.logger.info("Callback handlers registered")
    
    def _setup_error_handler(self):
        """
        Set up global error handler
        
        Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4
        """
        self.logger.info("Setting up error handler...")
        
        self.application.add_error_handler(self.global_error_handler)
        
        self.logger.info("Error handler registered")
    
    async def _set_bot_commands(self):
        """
        Set bot commands for Telegram UI
        
        This makes commands visible in the Telegram command menu
        """
        commands = [
            BotCommand("start", "شروع و نمایش منوی اصلی"),
            BotCommand("status", "نمایش وضعیت سیستم"),
            BotCommand("admins", "نمایش لیست ادمین‌ها"),
            BotCommand("help", "راهنمای استفاده از ربات"),
        ]
        
        try:
            await self.application.bot.set_my_commands(commands)
            self.logger.info("Bot commands set successfully")
        except Exception as e:
            self.logger.error(f"Failed to set bot commands: {e}")
    
    # Command Handlers
    
    @admin_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /start command - Show main menu
        
        Requirements: AC-6.1, AC-6.2, AC-8.1, AC-10.1
        """
        user_id = update.effective_user.id
        
        # Rate limiting
        allowed = await self.rate_limiter.acquire(user_id, 'command', wait=True)
        if not allowed:
            await update.message.reply_text(
                "⚠️ تعداد درخواست‌های شما زیاد است. لطفاً کمی صبر کنید."
            )
            return
        
        self.logger.info(f"User {user_id} started bot")
        
        # Clear navigation state
        self.navigation_manager.clear_state(user_id)
        
        # Show main menu
        keyboard = KeyboardBuilder.main_menu()
        
        await update.message.reply_text(
            MAIN_MENU_WELCOME,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /status command - Show system status
        
        Requirements: AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.5, AC-5.6, AC-8.1, AC-10.1
        """
        user_id = update.effective_user.id
        
        # Rate limiting
        allowed = await self.rate_limiter.acquire(user_id, 'command', wait=True)
        if not allowed:
            await update.message.reply_text(
                "⚠️ تعداد درخواست‌های شما زیاد است. لطفاً کمی صبر کنید."
            )
            return
        
        self.logger.info(f"User {user_id} requested system status")
        
        # Delegate to system status handler
        await self.system_status_handler.show_system_status(update, context)
    
    @admin_only
    async def admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /admins command - Show admin list
        
        Requirements: AC-8.2, AC-8.1
        """
        user_id = update.effective_user.id
        self.logger.info(f"User {user_id} requested admin list")
        
        # Get formatted admin list
        admin_list_text = format_admin_list()
        
        # Show with back to main menu button
        keyboard = KeyboardBuilder.back_to_main()
        
        await update.message.reply_text(
            admin_list_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /help command - Show comprehensive help menu with navigation
        
        Requirements: AC-18.1, AC-18.2, AC-8.1
        """
        user_id = update.effective_user.id
        self.logger.info(f"User {user_id} requested help")
        
        # Show help text with navigation to feature-specific help
        keyboard = KeyboardBuilder.help_menu()
        
        await update.message.reply_text(
            HELP_MENU,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # Help Navigation Handlers
    
    @admin_only
    async def handle_help_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle navigation back to main help menu
        
        Requirements: AC-18.1, AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} navigating to main help")
        
        keyboard = KeyboardBuilder.help_menu()
        
        await query.edit_message_text(
            HELP_MENU,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_scraping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show scraping operations help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing scraping help")
        
        from .persian_text import HELP_SCRAPING
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_SCRAPING,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_sending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show message sending help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing sending help")
        
        from .persian_text import HELP_SENDING
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_SENDING,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show monitoring help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing monitoring help")
        
        from .persian_text import HELP_MONITORING
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_MONITORING,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show session management help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing sessions help")
        
        from .persian_text import HELP_SESSIONS
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_SESSIONS,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show system status help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing status help")
        
        from .persian_text import HELP_SYSTEM_STATUS
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_SYSTEM_STATUS,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show operation history help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing history help")
        
        from .persian_text import HELP_OPERATION_HISTORY
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_OPERATION_HISTORY,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_help_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show configuration help
        
        Requirements: AC-18.2
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} viewing config help")
        
        from .persian_text import HELP_CONFIGURATION
        keyboard = KeyboardBuilder.help_feature_back()
        
        await query.edit_message_text(
            HELP_CONFIGURATION,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # Navigation Handlers
    
    @admin_only
    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle navigation to main menu
        
        Requirements: AC-6.6, AC-10.2
        """
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Rate limiting for button clicks
        allowed = await self.rate_limiter.acquire(user_id, 'button', wait=False)
        if not allowed:
            await query.answer("⚠️ لطفاً کمی صبر کنید", show_alert=True)
            return
        
        await query.answer()
        
        self.logger.debug(f"User {user_id} navigating to main menu")
        
        # Clear navigation state
        self.navigation_manager.clear_state(user_id)
        
        # Show main menu
        keyboard = KeyboardBuilder.main_menu()
        
        await query.edit_message_text(
            MAIN_MENU_WELCOME,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    @admin_only
    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle back button navigation
        
        Requirements: AC-6.6
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        self.logger.debug(f"User {user_id} pressed back button")
        
        # Pop navigation and get previous target
        previous_target = self.navigation_manager.pop_navigation(user_id)
        
        if previous_target:
            # Navigate to previous target
            # Create a new callback query with the previous target
            query.data = previous_target
            await self.route_callback(update, context)
        else:
            # No history, go to main menu
            await self.handle_main_menu(update, context)
    
    @admin_only
    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle cancel button - return to main menu
        
        Requirements: AC-6.6
        """
        query = update.callback_query
        await query.answer("❌ عملیات لغو شد")
        
        user_id = update.effective_user.id
        self.logger.info(f"User {user_id} cancelled operation")
        
        # Clear user session
        self.state_manager.delete_user_session(user_id)
        
        # Return to main menu
        await self.handle_main_menu(update, context)
        
        return ConversationHandler.END
    
    # Menu Handlers
    
    @admin_only
    async def show_scraping_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show scraping menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Delegate to scraping handler
        await self.scraping_handler.show_scrape_menu(update, context)
    
    @admin_only
    async def show_sending_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show sending menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Delegate to sending handler
        await self.sending_handler.show_send_menu(update, context)
    
    @admin_only
    async def show_monitoring_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show monitoring menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Delegate to monitoring handler
        await self.monitoring_handler.show_monitoring_menu(update, context)
    
    @admin_only
    async def show_sessions_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show sessions menu"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Delegate to session handler
        await self.session_handler.show_session_menu(update, context)
    
    @admin_only
    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show settings menu - delegates to ConfigurationHandler
        
        Requirements: AC-16.1
        """
        # Delegate to configuration handler
        await self.config_handler.show_config(update, context)
    
    @admin_only
    async def handle_unknown_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle unknown callback queries gracefully
        
        Requirements: AC-6.2
        """
        query = update.callback_query
        await query.answer("⚠️ دستور نامعتبر")
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        self.logger.warning(f"Unknown callback from user {user_id}: {callback_data}")
        
        # Show error message with option to return to main menu
        text = """
⚠️ **دستور نامعتبر**

دستور درخواستی شناخته نشده است.

لطفاً از منوی اصلی استفاده کنید.
"""
        
        keyboard = KeyboardBuilder.back_to_main()
        
        try:
            await query.edit_message_text(
                text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            self.logger.error(f"Failed to edit message for unknown callback: {e}")
    
    async def route_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Route callback queries to appropriate handlers
        
        This is a helper method for programmatic callback routing
        """
        query = update.callback_query
        callback_data = query.data
        
        # Route based on callback prefix
        if callback_data.startswith('nav:main'):
            await self.handle_main_menu(update, context)
        elif callback_data.startswith('menu:scraping'):
            await self.show_scraping_menu(update, context)
        elif callback_data.startswith('menu:sending'):
            await self.show_sending_menu(update, context)
        elif callback_data.startswith('menu:monitoring'):
            await self.show_monitoring_menu(update, context)
        elif callback_data.startswith('menu:sessions'):
            await self.show_sessions_menu(update, context)
        elif callback_data.startswith('menu:settings'):
            await self.show_settings_menu(update, context)
        else:
            await self.handle_unknown_callback(update, context)
    
    # Error Handler
    
    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """
        Global error handler for all bot errors
        
        Requirements: AC-9.1, AC-9.2, AC-9.3, AC-9.4
        """
        # Get error
        error = context.error
        
        # Log error
        self.logger.error(f"Global error handler caught: {error}", exc_info=error)
        
        # Get user ID if available
        user_id = None
        if isinstance(update, Update):
            if update.effective_user:
                user_id = update.effective_user.id
        
        # Create error context
        error_context = ErrorContext(
            user_id=user_id,
            operation="global",
            details={"update": str(update) if update else "No update"}
        )
        
        # Handle error using error handler
        if isinstance(update, Update):
            await self.error_handler.handle_error(
                error=error,
                update=update,
                context=context,
                error_context=error_context
            )
        else:
            # Log only if update is not available
            self.error_handler.log_error(error, error_context.__dict__)
    
    # Application Lifecycle
    
    async def run(self):
        """
        Run the bot application
        
        This method starts the bot and runs it until stopped.
        """
        self.logger.info("Starting Telegram Bot Panel...")
        
        # Set up application
        await self.setup()
        
        # Initialize and start the application
        await self.application.initialize()
        await self.application.start()
        
        # Start polling
        self.logger.info("Bot is now running. Press Ctrl+C to stop.")
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep running until interrupted
        try:
            # Run forever
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
    
    async def shutdown(self):
        """
        Gracefully shutdown the bot application
        """
        self.logger.info("Shutting down Telegram Bot Panel...")
        
        # Stop cleanup tasks
        await self.state_manager.stop_cleanup_task()
        await self.operation_history_handler.stop_cleanup_task()
        
        # Stop application
        if self.application:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        self.logger.info("Bot shutdown complete")


async def main():
    """
    Main entry point for the bot application
    """
    # Initialize session manager (placeholder - should be passed from main app)
    from telegram_manager.manager import TelegramSessionManager
    session_manager = TelegramSessionManager()
    
    # Create and run bot
    bot = TelegramBotPanel(session_manager)
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
