"""
Database handler for session data
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from .config import SessionConfig

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("DatabaseManager")

    def get_all_accounts(self) -> List[Dict]:
        """
        Get all accounts from database
        
        Returns:
            List of account dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM accounts")
            rows = cursor.fetchall()
            
            accounts = []
            for row in rows:
                accounts.append(dict(row))
            
            conn.close()
            self.logger.info(f"📊 Loaded {len(accounts)} accounts from database")
            return accounts
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load accounts from database: {e}")
            return []

    def convert_to_session_configs(self, accounts: List[Dict], app_id: int, app_hash: str) -> List[SessionConfig]:
        """
        Convert database accounts to SessionConfig objects
        
        Args:
            accounts: List of account dictionaries from database
            app_id: Telegram API ID
            app_hash: Telegram API Hash
            
        Returns:
            List of SessionConfig objects
        """
        session_configs = []
        
        for account in accounts:
            # Use phone number as session name
            session_name = account['number']
            
            # Session file path: sessions/+12345678910.session
            session_file = f"sessions/{account['number']}.session"
            
            session_config = SessionConfig(
                name=session_name,
                session_file=session_file,
                api_id=app_id,
                api_hash=app_hash
            )
            session_configs.append(session_config)
            
            # Store additional account data for later use if needed
            session_config.db_data = account
            
        return session_configs