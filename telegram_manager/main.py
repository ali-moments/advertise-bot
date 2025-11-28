"""
Main application and usage examples
"""

import json
import random
import asyncio
import logging
from typing import List, Dict

from .config import AppConfig, SessionConfig
from .manager import TelegramSessionManager

from .constants import APP_ID, APP_HASH, DB_PATH, SESSION_COUNT

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TelegramManagerApp:
    """
    Main application class for managing Telegram sessions
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Optional[AppConfig] = None
        self.manager: Optional[TelegramSessionManager] = None
        self.logger = logging.getLogger("TelegramManagerApp")

    async def initialize(self):
        """Initialize the application from database"""
        try:
            # Load constants
            from .constants import APP_ID, APP_HASH, DB_PATH
            
            self.logger.info(f"📁 Using APP_ID: {APP_ID}")
            
            # Initialize session manager
            self.manager = TelegramSessionManager(
                max_concurrent_operations=getattr(self.config, 'max_concurrent_operations', 3) if self.config else 3
            )
            
            # Load sessions from database
            load_results = await self.manager.load_sessions_from_db()
            
            # Log how many sessions are being loaded
            self.logger.info(f"📊 Loading {len(load_results)} sessions (SESSION_COUNT={SESSION_COUNT})")
            
            successful_sessions = sum(1 for success in load_results.values() if success)
            self.logger.info(f"✅ Successfully loaded {successful_sessions}/{len(load_results)} sessions from database")
            
            # Load monitoring targets from config file if exists, otherwise use empty list
            if self.config:
                self.monitoring_targets = self.config.monitoring_targets
            else:
                self.monitoring_targets = []
                self.logger.info("⚠️ No config file found, using empty monitoring targets")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize application: {e}")
            return False

    async def start_monitoring(self):
        """Start monitoring on all sessions"""
        if not self.manager or not self.config:
            self.logger.error("❌ Application not initialized")
            return False
        
        if not self.config.monitoring_targets:
            self.logger.warning("⚠️ No monitoring targets configured")
            return False
        
        await self.manager.start_global_monitoring(self.config.monitoring_targets)
        return True

    async def stop_monitoring(self):
        """Stop monitoring on all sessions"""
        if self.manager:
            await self.manager.stop_global_monitoring()

    async def send_bulk_messages(self, targets: List[str], message: str):
        """Send bulk messages to multiple targets"""
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return {}
        
        self.logger.info(f"📤 Sending message to {len(targets)} targets")
        results = await self.manager.bulk_send_messages(
            targets=targets,
            message=message,
            delay=self.config.default_delay if self.config else 2.0
        )
        
        success_count = sum(1 for result in results.values() if result['success'])
        self.logger.info(f"✅ Successfully sent {success_count}/{len(targets)} messages")
        
        return results

    async def get_chat_members(self, chats: List[str], limit: int = 100):
        """Get members from multiple chats"""
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return {}
        
        self.logger.info(f"👥 Getting members from {len(chats)} chats")
        members_data = await self.manager.bulk_get_members(chats, limit=limit)
        
        for chat, members in members_data.items():
            self.logger.info(f"📊 {chat}: {len(members)} members")
        
        return members_data

    async def join_multiple_chats(self, chats: List[str]):
        """Join multiple chats"""
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return {}
        
        self.logger.info(f"🔗 Joining {len(chats)} chats")
        results = await self.manager.join_chats(chats)
        
        success_count = sum(1 for success in results.values() if success)
        self.logger.info(f"✅ Successfully joined {success_count}/{len(chats)} chats")
        
        return results

    async def show_stats(self):
        """Display session statistics"""
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return
        
        stats = await self.manager.get_session_stats()
        print("\n📊 Session Statistics:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    async def shutdown(self):
        """Shutdown the application"""
        if self.manager:
            await self.manager.shutdown()
        self.logger.info("👋 Application shutdown complete")
    
    async def scrape_group_members(self, group_identifier: str, join_first: bool = False, max_members: int = 10000) -> Dict:
        """
        Scrape members from a group using random session
        
        Args:
            group_identifier: Group username, invite link, or ID
            join_first: Whether to join group first
            max_members: Maximum members to scrape
            
        Returns:
            Dict with scrape results
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return {'success': False, 'error': 'Application not initialized'}
        
        self.logger.info(f"🔍 Scraping members from {group_identifier}")
        
        if join_first:
            result = await self.manager.join_and_scrape_group_random_session(group_identifier, max_members)
        else:
            result = await self.manager.scrape_group_members_random_session(group_identifier, max_members)
        
        if result['success']:
            self.logger.info(f"✅ Successfully scraped {result.get('members_count', 0)} members -> {result['file_path']}")
        else:
            self.logger.error(f"❌ Failed to scrape {group_identifier}: {result.get('error', 'Unknown error')}")
        
        return result

    async def bulk_scrape_groups(self, groups: List[str], join_first: bool = False, max_members: int = 10000) -> Dict[str, Dict]:
        """
        Scrape multiple groups using different sessions
        
        Args:
            groups: List of group identifiers
            join_first: Whether to join groups first
            max_members: Maximum members per group
            
        Returns:
            Dict mapping groups to scrape results
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            return {}
        
        self.logger.info(f"🔍 Bulk scraping {len(groups)} groups")
        
        results = await self.manager.bulk_scrape_groups(groups, join_first, max_members)
        
        # Log summary
        success_count = sum(1 for result in results.values() if result.get('success', False))
        self.logger.info(f"📊 Bulk scrape completed: {success_count}/{len(groups)} successful")
        
        return results

    async def extract_group_links(self, target: str, limit_messages: int = 100) -> Dict:
        """
        Extract group/channel links from a 'لینک دونی' type channel
        """
        if not self.manager.sessions:
            return {
                'success': False,
                'error': 'No active sessions available',
                'source_channel': target,
                'telegram_links': []
            }
        
        # Get a random session
        session_names = list(self.manager.sessions.keys())
        random_session_name = random.choice(session_names)
        session = self.manager.sessions[random_session_name]
        
        self.logger.info(f"🎲 Using session '{random_session_name}' to extract links from {target}")
        
        try:
            result = await session.extract_group_links(target, limit_messages)
            result['session_used'] = random_session_name
            return result
        except Exception as e:
            self.logger.error(f"❌ Error extracting links with session {random_session_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'source_channel': target,
                'telegram_links': [],
                'session_used': random_session_name
            }

    async def extract_links_from_channels(self, channels: List[str], limit_messages: int = 100) -> Dict[str, Dict]:
        """
        Extract group links from multiple 'لینک دونی' channels
        """
        return await self.manager.extract_links_from_channels(channels, limit_messages)

    async def bulk_scrape_from_link_channels(self, link_channels: List[str], join_first: bool = False, 
                                           limit_messages: int = 100, max_members: int = 10000) -> Dict:
        """
        Complete workflow: Extract links from 'لینک دونی' channels, then scrape all found groups
        """
        return await self.manager.bulk_scrape_from_link_channels(
            link_channels, join_first, limit_messages, max_members
        )

    async def bulk_scrape_groups(self, groups: List[str], join_first: bool = False, 
                               max_members: int = 10000, enforce_daily_limits: bool = True) -> Dict[str, Dict]:
        """
        Scrape multiple groups with optional daily limits enforcement
        """
        return await self.manager.bulk_scrape_groups(groups, join_first, max_members, enforce_daily_limits)

    async def get_session_stats(self) -> Dict:
        """
        Get statistics for all sessions including daily usage
        """
        stats = await self.manager.get_session_stats()
        
        # Add daily stats to the response
        for session_name, session in self.manager.sessions.items():
            if session_name in stats:
                stats[session_name]['daily_stats'] = {
                    'messages_read': session.daily_stats['messages_read'],
                    'groups_scraped_today': session.daily_stats['groups_scraped_today'],
                    'max_messages_per_day': session.daily_limits['max_messages_per_day'],
                    'max_groups_per_day': session.daily_limits['max_groups_per_day']
                }
        
        return stats
    
    async def check_target_type(self, target: str) -> Dict:
        """Check if target is scrapable"""
        return await self.manager.check_target_type(target)

    async def bulk_check_targets(self, targets: List[str]) -> Dict[str, Dict]:
        """Check multiple targets"""
        return await self.manager.bulk_check_targets(targets)

    async def filter_scrapable_targets(self, targets: List[str]) -> List[str]:
        """Filter to only scrapable groups"""
        return await self.manager.filter_scrapable_targets(targets)

    async def safe_bulk_scrape_with_filter(self, targets: List[str], join_first: bool = False, 
                                        max_members: int = 10000) -> Dict[str, Dict]:
        """Complete safe scraping workflow"""
        return await self.manager.safe_bulk_scrape_with_filter(targets, join_first, max_members)