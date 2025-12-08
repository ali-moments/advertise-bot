"""
Telegram Manager Constants using Environment Variables
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API Configuration
API_ID = int(os.getenv('API_ID', 'YOUR_API_ID_HERE'))
API_HASH = os.getenv('API_HASH', 'YOUR_API_HASH_HERE')

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
MONITORING_COOLDOWN = float(os.getenv('MONITORING_COOLDOWN', '1.0'))
MESSAGE_SCRAPING_DAYS = int(os.getenv('MESSAGE_SCRAPING_DAYS', '10'))

# Blacklist Configuration
BLACKLIST_ENABLED = os.getenv('BLACKLIST_ENABLED', 'true').lower() == 'true'
BLACKLIST_STORAGE_PATH = os.getenv('BLACKLIST_STORAGE_PATH', 'sessions/blacklist.json')
BLACKLIST_FAILURE_THRESHOLD = int(os.getenv('BLACKLIST_FAILURE_THRESHOLD', '2'))
BLACKLIST_AUTO_ADD = os.getenv('BLACKLIST_AUTO_ADD', 'true').lower() == 'true'

# Validation
if not API_HASH or API_HASH == 'YOUR_API_HASH_HERE':
    raise ValueError("API_HASH must be set in .env file")

