"""
Configuration Handler - Manages bot configuration through UI

This module provides configuration management functionality including:
- Display current configuration
- Modify configuration settings
- Reset configuration to defaults
- Log configuration changes

Requirements: 16.1, 16.2, 16.3, 16.4
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from .auth import admin_only
from .keyboard_builder import KeyboardBuilder
from .message_formatter import MessageFormatter
from .persian_text import (
    BTN_BACK, BTN_MAIN_MENU, BTN_CONFIRM, BTN_CANCEL,
    ERROR_INVALID_INPUT, OPERATION_CANCELLED
)
from .error_handler import BotErrorHandler, ErrorContext


# Conversation states
SHOW_CONFIG, SELECT_SETTING, GET_NEW_VALUE, CONFIRM_CHANGE, CONFIRM_RESET = range(5)


@dataclass
class ConfigSetting:
    """Represents a configurable setting"""
    key: str
    name_persian: str
    description: str
    current_value: Any
    default_value: Any
    value_type: str  # 'int', 'float', 'bool', 'string', 'list'
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    
    def validate(self, value: Any) -> tuple[bool, str]:
        """
        Validate a new value for this setting
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Type conversion
            if self.value_type == 'int':
                value = int(value)
            elif self.value_type == 'float':
                value = float(value)
            elif self.value_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'بله')
                else:
                    value = bool(value)
            elif self.value_type == 'list':
                if isinstance(value, str):
                    value = [v.strip() for v in value.split(',')]
            
            # Range validation
            if self.min_value is not None and isinstance(value, (int, float)):
                if value < self.min_value:
                    return False, f"مقدار باید حداقل {self.min_value} باشد"
            
            if self.max_value is not None and isinstance(value, (int, float)):
                if value > self.max_value:
                    return False, f"مقدار باید حداکثر {self.max_value} باشد"
            
            # Allowed values validation
            if self.allowed_values is not None:
                if value not in self.allowed_values:
                    allowed_str = ', '.join(str(v) for v in self.allowed_values)
                    return False, f"مقدار باید یکی از موارد زیر باشد: {allowed_str}"
            
            return True, ""
            
        except (ValueError, TypeError) as e:
            return False, f"فرمت نامعتبر: {str(e)}"


class ConfigurationHandler:
    """
    Handle configuration management operations
    
    Features:
    - Display current configuration
    - Modify individual settings
    - Reset to defaults
    - Log all changes
    
    Requirements:
        - AC-16.1: Display configuration
        - AC-16.2: Modify settings
        - AC-16.3: Reset configuration
        - AC-16.4: Log changes
    """
    
    def __init__(self, error_handler: Optional[BotErrorHandler] = None):
        """
        Initialize configuration handler
        
        Args:
            error_handler: Error handler instance
        """
        self.logger = logging.getLogger("ConfigurationHandler")
        self.error_handler = error_handler or BotErrorHandler()
        
        # Configuration file path
        self.config_file = os.path.join(os.path.dirname(__file__), 'bot_config.json')
        self.log_file = os.path.join(os.path.dirname(__file__), 'config_changes.log')
        
        # Load current configuration
        self.config = self._load_config()
        
        # Define configurable settings
        self.settings = self._define_settings()
        
        self.logger.info("ConfigurationHandler initialized")
    
    def _define_settings(self) -> Dict[str, ConfigSetting]:
        """
        Define all configurable settings
        
        Returns:
            Dictionary of setting key to ConfigSetting
            
        Requirements: AC-16.1
        """
        return {
            'page_size': ConfigSetting(
                key='page_size',
                name_persian='تعداد آیتم در هر صفحه',
                description='تعداد آیتم‌هایی که در لیست‌های صفحه‌بندی شده نمایش داده می‌شود',
                current_value=self.config.get('page_size', 5),
                default_value=5,
                value_type='int',
                min_value=1,
                max_value=20
            ),
            'max_groups_per_bulk': ConfigSetting(
                key='max_groups_per_bulk',
                name_persian='حداکثر گروه در اسکرپ چندگانه',
                description='حداکثر تعداد گروه‌هایی که می‌توان در یک عملیات اسکرپ چندگانه پردازش کرد',
                current_value=self.config.get('max_groups_per_bulk', 10),
                default_value=10,
                value_type='int',
                min_value=1,
                max_value=50
            ),
            'max_concurrent_scrapes': ConfigSetting(
                key='max_concurrent_scrapes',
                name_persian='حداکثر اسکرپ همزمان',
                description='حداکثر تعداد عملیات اسکرپ که می‌توانند به صورت همزمان اجرا شوند',
                current_value=self.config.get('max_concurrent_scrapes', 3),
                default_value=3,
                value_type='int',
                min_value=1,
                max_value=10
            ),
            'request_timeout': ConfigSetting(
                key='request_timeout',
                name_persian='زمان انتظار درخواست (ثانیه)',
                description='حداکثر زمان انتظار برای پاسخ درخواست‌ها',
                current_value=self.config.get('request_timeout', 30),
                default_value=30,
                value_type='int',
                min_value=10,
                max_value=120
            ),
            'session_timeout': ConfigSetting(
                key='session_timeout',
                name_persian='زمان انقضای سشن (ثانیه)',
                description='مدت زمانی که سشن کاربر بدون فعالیت باقی می‌ماند',
                current_value=self.config.get('session_timeout', 3600),
                default_value=3600,
                value_type='int',
                min_value=300,
                max_value=7200
            ),
            'cleanup_interval': ConfigSetting(
                key='cleanup_interval',
                name_persian='فاصله پاکسازی (ثانیه)',
                description='فاصله زمانی بین عملیات پاکسازی خودکار',
                current_value=self.config.get('cleanup_interval', 300),
                default_value=300,
                value_type='int',
                min_value=60,
                max_value=3600
            ),
            'log_level': ConfigSetting(
                key='log_level',
                name_persian='سطح لاگ',
                description='سطح جزئیات لاگ‌های سیستم',
                current_value=self.config.get('log_level', 'INFO'),
                default_value='INFO',
                value_type='string',
                allowed_values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            ),
            'enable_notifications': ConfigSetting(
                key='enable_notifications',
                name_persian='فعال‌سازی اعلان‌ها',
                description='ارسال اعلان برای رویدادهای مهم',
                current_value=self.config.get('enable_notifications', True),
                default_value=True,
                value_type='bool'
            ),
            'progress_update_interval': ConfigSetting(
                key='progress_update_interval',
                name_persian='فاصله بروزرسانی پیشرفت (ثانیه)',
                description='حداقل فاصله زمانی بین بروزرسانی‌های پیشرفت',
                current_value=self.config.get('progress_update_interval', 2.0),
                default_value=2.0,
                value_type='float',
                min_value=0.5,
                max_value=10.0
            )
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file
        
        Returns:
            Configuration dictionary
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_file}")
                return config
            except Exception as e:
                self.logger.error(f"Failed to load configuration: {e}")
                return {}
        else:
            self.logger.info("No configuration file found, using defaults")
            return {}
    
    def _save_config(self) -> bool:
        """
        Save configuration to file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    def _log_change(self, admin_id: int, setting_key: str, old_value: Any, new_value: Any):
        """
        Log configuration change
        
        Args:
            admin_id: ID of admin who made the change
            setting_key: Key of the setting that was changed
            old_value: Previous value
            new_value: New value
            
        Requirements: AC-16.4
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'admin_id': admin_id,
            'setting': setting_key,
            'old_value': old_value,
            'new_value': new_value
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            self.logger.info(
                f"Config change logged: {setting_key} changed from {old_value} to {new_value} by admin {admin_id}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log configuration change: {e}")
    
    def format_config_display(self) -> str:
        """
        Format current configuration for display
        
        Returns:
            Formatted configuration string
            
        Requirements: AC-16.1
        """
        result = "⚙️ **تنظیمات سیستم**\n\n"
        result += "**تنظیمات فعلی:**\n\n"
        
        for setting in self.settings.values():
            # Format value based on type
            if setting.value_type == 'bool':
                value_str = "✅ فعال" if setting.current_value else "❌ غیرفعال"
            else:
                value_str = str(setting.current_value)
            
            result += f"🔹 **{setting.name_persian}**\n"
            result += f"   مقدار فعلی: `{value_str}`\n"
            result += f"   مقدار پیش‌فرض: `{setting.default_value}`\n"
            result += f"   توضیحات: {setting.description}\n\n"
        
        result += "برای تغییر تنظیمات از دکمه‌های زیر استفاده کنید."
        
        return result
    
    def build_settings_keyboard(self) -> InlineKeyboardMarkup:
        """
        Build keyboard for settings selection
        
        Returns:
            InlineKeyboardMarkup with setting buttons
        """
        keyboard = []
        
        # Add button for each setting
        for setting in self.settings.values():
            keyboard.append([
                InlineKeyboardButton(
                    setting.name_persian,
                    callback_data=f"config:edit:{setting.key}"
                )
            ])
        
        # Add reset and back buttons
        keyboard.append([
            InlineKeyboardButton("🔄 بازگردانی به پیش‌فرض", callback_data="config:reset")
        ])
        keyboard.append([
            InlineKeyboardButton(BTN_BACK, callback_data="nav:main"),
            InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_conversation_handler(self) -> ConversationHandler:
        """
        Get conversation handler for configuration management
        
        Returns:
            ConversationHandler instance
        """
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.show_config, pattern='^menu:settings$'),
                CallbackQueryHandler(self.show_config, pattern='^config:show$')
            ],
            states={
                SHOW_CONFIG: [
                    CallbackQueryHandler(self.select_setting, pattern='^config:edit:'),
                    CallbackQueryHandler(self.confirm_reset, pattern='^config:reset$'),
                    CallbackQueryHandler(self.handle_back, pattern='^nav:')
                ],
                SELECT_SETTING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_new_value),
                    CallbackQueryHandler(self.handle_cancel, pattern='^action:cancel$')
                ],
                GET_NEW_VALUE: [
                    CallbackQueryHandler(self.apply_change, pattern='^config:confirm:'),
                    CallbackQueryHandler(self.handle_cancel, pattern='^action:cancel$')
                ],
                CONFIRM_RESET: [
                    CallbackQueryHandler(self.reset_config, pattern='^config:reset:confirm$'),
                    CallbackQueryHandler(self.show_config, pattern='^config:reset:cancel$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.handle_cancel, pattern='^action:cancel$'),
                CallbackQueryHandler(self.handle_back, pattern='^nav:main$')
            ],
            name="configuration_handler",
            persistent=False
        )
    
    @admin_only
    async def show_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show current configuration
        
        Requirements: AC-16.1
        """
        query = update.callback_query
        if query:
            await query.answer()
        
        # Reload settings to get current values
        self.settings = self._define_settings()
        
        message_text = self.format_config_display()
        keyboard = self.build_settings_keyboard()
        
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
        
        return SHOW_CONFIG
    
    @admin_only
    async def select_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Handle setting selection for editing
        
        Requirements: AC-16.2
        """
        query = update.callback_query
        await query.answer()
        
        # Extract setting key from callback data
        setting_key = query.data.split(':')[2]
        
        if setting_key not in self.settings:
            await query.edit_message_text(
                text=f"❌ تنظیم نامعتبر: {setting_key}",
                reply_markup=KeyboardBuilder.back_main()
            )
            return SHOW_CONFIG
        
        setting = self.settings[setting_key]
        context.user_data['editing_setting'] = setting_key
        
        # Build prompt message
        prompt = f"⚙️ **ویرایش تنظیم**\n\n"
        prompt += f"**{setting.name_persian}**\n"
        prompt += f"{setting.description}\n\n"
        prompt += f"**مقدار فعلی:** `{setting.current_value}`\n"
        prompt += f"**مقدار پیش‌فرض:** `{setting.default_value}`\n\n"
        
        # Add constraints info
        if setting.min_value is not None or setting.max_value is not None:
            prompt += f"**محدوده مجاز:** "
            if setting.min_value is not None:
                prompt += f"حداقل {setting.min_value}"
            if setting.max_value is not None:
                if setting.min_value is not None:
                    prompt += f" - "
                prompt += f"حداکثر {setting.max_value}"
            prompt += "\n\n"
        
        if setting.allowed_values:
            allowed_str = ', '.join(f"`{v}`" for v in setting.allowed_values)
            prompt += f"**مقادیر مجاز:** {allowed_str}\n\n"
        
        prompt += "لطفاً مقدار جدید را وارد کنید:"
        
        keyboard = [[InlineKeyboardButton(BTN_CANCEL, callback_data="action:cancel")]]
        
        await query.edit_message_text(
            text=prompt,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SELECT_SETTING
    
    @admin_only
    async def get_new_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Get and validate new value from user
        
        Requirements: AC-16.2
        """
        setting_key = context.user_data.get('editing_setting')
        if not setting_key or setting_key not in self.settings:
            await update.message.reply_text(
                text=ERROR_INVALID_INPUT,
                reply_markup=KeyboardBuilder.back_main()
            )
            return SHOW_CONFIG
        
        setting = self.settings[setting_key]
        new_value = update.message.text.strip()
        
        # Validate new value
        is_valid, error_msg = setting.validate(new_value)
        
        if not is_valid:
            await update.message.reply_text(
                text=f"❌ **خطا در اعتبارسنجی**\n\n{error_msg}\n\nلطفاً مقدار معتبر وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(BTN_CANCEL, callback_data="action:cancel")
                ]]),
                parse_mode='Markdown'
            )
            return SELECT_SETTING
        
        # Convert value to proper type
        if setting.value_type == 'int':
            new_value = int(new_value)
        elif setting.value_type == 'float':
            new_value = float(new_value)
        elif setting.value_type == 'bool':
            new_value = new_value.lower() in ('true', '1', 'yes', 'بله')
        elif setting.value_type == 'list':
            new_value = [v.strip() for v in new_value.split(',')]
        
        # Store new value for confirmation
        context.user_data['new_value'] = new_value
        
        # Show confirmation
        confirm_text = f"✅ **تأیید تغییر**\n\n"
        confirm_text += f"**تنظیم:** {setting.name_persian}\n"
        confirm_text += f"**مقدار فعلی:** `{setting.current_value}`\n"
        confirm_text += f"**مقدار جدید:** `{new_value}`\n\n"
        confirm_text += "آیا از اعمال این تغییر اطمینان دارید؟"
        
        keyboard = [
            [
                InlineKeyboardButton(BTN_CONFIRM, callback_data=f"config:confirm:{setting_key}"),
                InlineKeyboardButton(BTN_CANCEL, callback_data="action:cancel")
            ]
        ]
        
        await update.message.reply_text(
            text=confirm_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return GET_NEW_VALUE
    
    @admin_only
    async def apply_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Apply configuration change
        
        Requirements: AC-16.2, AC-16.4
        """
        query = update.callback_query
        await query.answer()
        
        setting_key = query.data.split(':')[2]
        new_value = context.user_data.get('new_value')
        
        if not setting_key or setting_key not in self.settings:
            await query.edit_message_text(
                text=ERROR_INVALID_INPUT,
                reply_markup=KeyboardBuilder.back_main()
            )
            return SHOW_CONFIG
        
        setting = self.settings[setting_key]
        old_value = setting.current_value
        
        # Update configuration
        self.config[setting_key] = new_value
        setting.current_value = new_value
        
        # Save to file
        if self._save_config():
            # Log the change
            admin_id = update.effective_user.id
            self._log_change(admin_id, setting_key, old_value, new_value)
            
            success_text = f"✅ **تغییر اعمال شد**\n\n"
            success_text += f"**تنظیم:** {setting.name_persian}\n"
            success_text += f"**مقدار قبلی:** `{old_value}`\n"
            success_text += f"**مقدار جدید:** `{new_value}`\n\n"
            success_text += "تغییرات بلافاصله اعمال شد."
            
            await query.edit_message_text(
                text=success_text,
                reply_markup=KeyboardBuilder.back_main(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                text="❌ خطا در ذخیره تنظیمات. لطفاً دوباره تلاش کنید.",
                reply_markup=KeyboardBuilder.back_main()
            )
        
        # Clear user data
        context.user_data.pop('editing_setting', None)
        context.user_data.pop('new_value', None)
        
        return SHOW_CONFIG
    
    @admin_only
    async def confirm_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Show reset confirmation dialog
        
        Requirements: AC-16.3
        """
        query = update.callback_query
        await query.answer()
        
        confirm_text = "⚠️ **بازگردانی به تنظیمات پیش‌فرض**\n\n"
        confirm_text += "آیا از بازگردانی تمام تنظیمات به مقادیر پیش‌فرض اطمینان دارید؟\n\n"
        confirm_text += "**توجه:** این عملیات قابل بازگشت نیست."
        
        keyboard = [
            [
                InlineKeyboardButton("✅ بله، بازگردانی کن", callback_data="config:reset:confirm"),
                InlineKeyboardButton("❌ انصراف", callback_data="config:reset:cancel")
            ]
        ]
        
        await query.edit_message_text(
            text=confirm_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return CONFIRM_RESET
    
    @admin_only
    async def reset_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Reset configuration to defaults
        
        Requirements: AC-16.3, AC-16.4
        """
        query = update.callback_query
        await query.answer()
        
        admin_id = update.effective_user.id
        
        # Store old config for logging
        old_config = self.config.copy()
        
        # Reset to defaults
        self.config = {}
        for setting in self.settings.values():
            self.config[setting.key] = setting.default_value
            setting.current_value = setting.default_value
        
        # Save to file
        if self._save_config():
            # Log the reset
            self._log_change(admin_id, 'ALL_SETTINGS', old_config, self.config)
            
            success_text = "✅ **تنظیمات بازگردانی شد**\n\n"
            success_text += "تمام تنظیمات به مقادیر پیش‌فرض بازگردانی شدند.\n\n"
            success_text += "تغییرات بلافاصله اعمال شد."
            
            await query.edit_message_text(
                text=success_text,
                reply_markup=KeyboardBuilder.back_main(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                text="❌ خطا در بازگردانی تنظیمات. لطفاً دوباره تلاش کنید.",
                reply_markup=KeyboardBuilder.back_main()
            )
        
        return SHOW_CONFIG
    
    @admin_only
    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle cancel action"""
        query = update.callback_query
        await query.answer()
        
        # Clear user data
        context.user_data.pop('editing_setting', None)
        context.user_data.pop('new_value', None)
        
        await query.edit_message_text(
            text=OPERATION_CANCELLED,
            reply_markup=KeyboardBuilder.back_main()
        )
        
        return ConversationHandler.END
    
    @admin_only
    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle back navigation"""
        query = update.callback_query
        await query.answer()
        
        # Clear user data
        context.user_data.pop('editing_setting', None)
        context.user_data.pop('new_value', None)
        
        return ConversationHandler.END
    
    def get_setting_value(self, key: str) -> Any:
        """
        Get current value of a setting
        
        Args:
            key: Setting key
            
        Returns:
            Current value or None if not found
        """
        return self.config.get(key)
    
    def update_setting(self, key: str, value: Any, admin_id: int) -> bool:
        """
        Programmatically update a setting
        
        Args:
            key: Setting key
            value: New value
            admin_id: ID of admin making the change
            
        Returns:
            True if successful, False otherwise
        """
        if key not in self.settings:
            return False
        
        setting = self.settings[key]
        is_valid, _ = setting.validate(value)
        
        if not is_valid:
            return False
        
        old_value = setting.current_value
        self.config[key] = value
        setting.current_value = value
        
        if self._save_config():
            self._log_change(admin_id, key, old_value, value)
            return True
        
        return False
