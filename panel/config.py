"""
Bot Panel Configuration using Environment Variables

This module loads and validates all configuration settings from environment variables.
It provides centralized configuration management for the bot panel.

Requirements: 8.1, 8.3, 9.4 - Configuration management and logging setup
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Admin users (Telegram user IDs)
ADMIN_USERS_STR = os.getenv('ADMIN_USERS', '')
ADMIN_USERS = [int(user_id.strip()) for user_id in ADMIN_USERS_STR.split(',') if user_id.strip()]

# UI Settings
PAGE_SIZE = int(os.getenv('PAGE_SIZE', '5'))
MAX_GROUPS_PER_BULK = int(os.getenv('MAX_GROUPS_PER_BULK', '10'))

# Operation Limits for Bot
BOT_MAX_CONCURRENT_SCRAPES = int(os.getenv('BOT_MAX_CONCURRENT_SCRAPES', '3'))
BOT_REQUEST_TIMEOUT = int(os.getenv('BOT_REQUEST_TIMEOUT', '30'))

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.getenv('LOG_FILE', 'panel/bot_panel.log')
LOG_TO_CONSOLE = os.getenv('LOG_TO_CONSOLE', 'true').lower() in ('true', '1', 'yes')

# Session Management
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))  # 1 hour default
CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', '300'))  # 5 minutes default

# Validation
if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    raise ValueError("BOT_TOKEN must be set in .env file")

if not ADMIN_USERS:
    raise ValueError("ADMIN_USERS must be set in .env file")

# Validate log level
VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
if LOG_LEVEL not in VALID_LOG_LEVELS:
    raise ValueError(f"LOG_LEVEL must be one of {VALID_LOG_LEVELS}, got: {LOG_LEVEL}")
