"""
Telegram Manager Constants using Environment Variables
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API Configuration
APP_ID = int(os.getenv('APP_ID', 'YOUR_APP_ID_HERE'))
APP_HASH = os.getenv('APP_HASH', 'YOUR_APP_HASH_HERE')

# Database and Sessions
DB_PATH = os.getenv('DB_PATH', 'sessions/data.db')
SESSION_COUNT = int(os.getenv('SESSION_COUNT', '3'))
SESSIONS_DIR = os.getenv('SESSIONS_DIR', 'sessions')

# Operation Limits
MAX_CONCURRENT_OPERATIONS = int(os.getenv('MAX_CONCURRENT_OPERATIONS', '3'))
MAX_CONCURRENT_SCRAPES = int(os.getenv('MAX_CONCURRENT_SCRAPES', '5'))
DAILY_MESSAGES_LIMIT = int(os.getenv('DAILY_MESSAGES_LIMIT', '500'))
DAILY_GROUPS_LIMIT = int(os.getenv('DAILY_GROUPS_LIMIT', '10'))

# Monitoring Settings
MONITORING_COOLDOWN = float(os.getenv('MONITORING_COOLDOWN', '2.0'))
MESSAGE_SCRAPING_DAYS = int(os.getenv('MESSAGE_SCRAPING_DAYS', '10'))

# Validation
if not APP_HASH or APP_HASH == 'YOUR_APP_HASH_HERE':
    raise ValueError("APP_HASH must be set in .env file")

