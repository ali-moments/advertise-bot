"""
Main application and usage examples
"""

import json
import random
import asyncio
import logging
from typing import List, Dict, Optional

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
        
        # Add daily stats and queue depth to the response
        for session_name, session in self.manager.sessions.items():
            if session_name in stats:
                stats[session_name]['daily_stats'] = {
                    'messages_read': session.daily_stats['messages_read'],
                    'groups_scraped_today': session.daily_stats['groups_scraped_today'],
                    'max_messages_per_day': session.daily_limits['max_messages_per_day'],
                    'max_groups_per_day': session.daily_limits['max_groups_per_day']
                }
                stats[session_name]['queue_depth'] = session.get_queue_depth()
        
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

    async def send_text_to_users(
        self,
        recipients: List[str],
        message: str,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send text messages to multiple users with load balancing
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            message: Text message to send
            delay: Delay between sends within each session (seconds, default 2.0)
            skip_invalid: Whether to skip invalid recipients or fail early (default True)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 1.1, 21.1, 21.2
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='Application not initialized'
                )
                for recipient in recipients
            }
        
        try:
            self.logger.info(f"📤 Sending text message to {len(recipients)} recipients (priority: {priority})")
            results = await self.manager.send_text_messages_bulk(
                recipients=recipients,
                message=message,
                delay=delay,
                skip_invalid=skip_invalid,
                priority=priority
            )
            
            success_count = sum(1 for result in results.values() if result.success)
            self.logger.info(f"✅ Successfully sent {success_count}/{len(recipients)} text messages")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send text messages: {e}")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=str(e)
                )
                for recipient in recipients
            }

    async def send_image_to_users(
        self,
        recipients: List[str],
        image_path: str,
        caption: str = None,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send images with optional captions to multiple users with load balancing
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            image_path: Path to image file or URL
            caption: Optional caption for the image
            delay: Delay between sends within each session (seconds, default 2.0)
            skip_invalid: Whether to skip invalid recipients or fail early (default True)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 2.1, 18.1, 21.1, 21.2
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='Application not initialized'
                )
                for recipient in recipients
            }
        
        try:
            self.logger.info(f"📤 Sending image to {len(recipients)} recipients (priority: {priority})")
            results = await self.manager.send_media_messages_bulk(
                recipients=recipients,
                media_path=image_path,
                media_type='image',
                caption=caption,
                delay=delay,
                skip_invalid=skip_invalid,
                priority=priority
            )
            
            success_count = sum(1 for result in results.values() if result.success)
            self.logger.info(f"✅ Successfully sent {success_count}/{len(recipients)} images")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send images: {e}")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=str(e)
                )
                for recipient in recipients
            }

    async def send_document_to_users(
        self,
        recipients: List[str],
        document_path: str,
        caption: str = None,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send documents with optional captions to multiple users with load balancing
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            document_path: Path to document file
            caption: Optional caption for the document
            delay: Delay between sends within each session (seconds, default 2.0)
            skip_invalid: Whether to skip invalid recipients or fail early (default True)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 18.1, 18.2, 21.1, 21.2
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='Application not initialized'
                )
                for recipient in recipients
            }
        
        try:
            self.logger.info(f"📤 Sending document to {len(recipients)} recipients (priority: {priority})")
            results = await self.manager.send_media_messages_bulk(
                recipients=recipients,
                media_path=document_path,
                media_type='document',
                caption=caption,
                delay=delay,
                skip_invalid=skip_invalid,
                priority=priority
            )
            
            success_count = sum(1 for result in results.values() if result.success)
            self.logger.info(f"✅ Successfully sent {success_count}/{len(recipients)} documents")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send documents: {e}")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=str(e)
                )
                for recipient in recipients
            }

    async def send_video_to_users(
        self,
        recipients: List[str],
        video_path: str,
        caption: str = None,
        delay: float = 2.0,
        skip_invalid: bool = True,
        priority: str = "normal"
    ) -> Dict[str, 'MessageResult']:
        """
        Send videos with optional captions to multiple users with load balancing
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            video_path: Path to video file
            caption: Optional caption for the video
            delay: Delay between sends within each session (seconds, default 2.0)
            skip_invalid: Whether to skip invalid recipients or fail early (default True)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            Dict mapping recipient identifiers to MessageResult objects
            
        Requirements: 18.1, 18.2, 21.1, 21.2
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error='Application not initialized'
                )
                for recipient in recipients
            }
        
        try:
            self.logger.info(f"📤 Sending video to {len(recipients)} recipients (priority: {priority})")
            results = await self.manager.send_media_messages_bulk(
                recipients=recipients,
                media_path=video_path,
                media_type='video',
                caption=caption,
                delay=delay,
                skip_invalid=skip_invalid,
                priority=priority
            )
            
            success_count = sum(1 for result in results.values() if result.success)
            self.logger.info(f"✅ Successfully sent {success_count}/{len(recipients)} videos")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send videos: {e}")
            from .models import MessageResult
            return {
                recipient: MessageResult(
                    recipient=recipient,
                    success=False,
                    session_used='',
                    error=str(e)
                )
                for recipient in recipients
            }

    async def send_from_csv_file(
        self,
        csv_path: str,
        message: str,
        batch_size: int = 1000,
        delay: float = 2.0,
        resumable: bool = True,
        operation_id: str = None,
        priority: str = "normal"
    ) -> 'BulkSendResult':
        """
        Send messages to recipients from a CSV file with batch processing and progress tracking
        
        Args:
            csv_path: Path to CSV file containing recipient identifiers
            message: Text message to send
            batch_size: Number of recipients to process per batch (default 1000)
            delay: Delay between sends within each session (seconds, default 2.0)
            resumable: Whether to enable checkpoint-based resumption (default True)
            operation_id: Optional operation ID for resuming (auto-generated if not provided)
            priority: Operation priority ('high', 'normal', or 'low') (default 'normal')
            
        Returns:
            BulkSendResult with complete operation results
            
        Requirements: 12.1, 21.1, 21.2
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import BulkSendResult
            return BulkSendResult(
                total=0,
                succeeded=0,
                failed=0,
                results={},
                duration=0.0,
                operation_id=operation_id or 'failed'
            )
        
        try:
            self.logger.info(f"📤 Sending messages from CSV file: {csv_path} (priority: {priority})")
            result = await self.manager.send_from_csv(
                csv_path=csv_path,
                message=message,
                batch_size=batch_size,
                delay=delay,
                resumable=resumable,
                operation_id=operation_id,
                priority=priority
            )
            
            self.logger.info(
                f"✅ CSV send completed: {result.succeeded}/{result.total} successful "
                f"in {result.duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send from CSV: {e}")
            from .models import BulkSendResult
            return BulkSendResult(
                total=0,
                succeeded=0,
                failed=0,
                results={},
                duration=0.0,
                operation_id=operation_id or 'failed'
            )

    async def preview_send(
        self,
        recipients: List[str],
        message: str = None,
        media_path: str = None,
        media_type: str = None,
        delay: float = 2.0
    ) -> 'SendPreview':
        """
        Preview a message sending operation without actually sending
        
        Validates all inputs and calculates session distribution and estimated duration
        without sending any messages.
        
        Args:
            recipients: List of recipient identifiers (usernames or user IDs)
            message: Text message (for text sends)
            media_path: Path to media file (for media sends)
            media_type: Type of media ('image', 'video', 'document')
            delay: Delay between sends within each session (seconds, default 2.0)
            
        Returns:
            SendPreview with validation results, distribution plan, and time estimate
            
        Requirements: 15.1
        """
        if not self.manager:
            self.logger.error("❌ Application not initialized")
            from .models import SendPreview, ValidationResult, ValidationError
            return SendPreview(
                recipients=recipients,
                recipient_count=len(recipients),
                session_distribution={},
                estimated_duration=0.0,
                validation_result=ValidationResult(
                    valid=False,
                    errors=[ValidationError(
                        field='application',
                        value=None,
                        rule='initialization',
                        message='Application not initialized'
                    )]
                )
            )
        
        try:
            self.logger.info(f"🔍 Previewing send operation for {len(recipients)} recipients")
            preview = await self.manager.preview_send(
                recipients=recipients,
                message=message,
                media_path=media_path,
                media_type=media_type,
                delay=delay
            )
            
            if preview.validation_result.valid:
                self.logger.info(
                    f"✅ Preview valid: {preview.recipient_count} recipients, "
                    f"estimated {preview.estimated_duration:.2f}s"
                )
            else:
                self.logger.warning(
                    f"⚠️ Preview validation failed: {len(preview.validation_result.errors)} errors"
                )
            
            return preview
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate preview: {e}")
            from .models import SendPreview, ValidationResult, ValidationError
            return SendPreview(
                recipients=recipients,
                recipient_count=len(recipients),
                session_distribution={},
                estimated_duration=0.0,
                validation_result=ValidationResult(
                    valid=False,
                    errors=[ValidationError(
                        field='preview',
                        value=None,
                        rule='execution',
                        message=str(e)
                    )]
                )
            )

    async def configure_reaction_pool(
        self,
        chat_id: str,
        reactions: List[Dict[str, any]],
        cooldown: float = 2.0
    ) -> Dict[str, any]:
        """
        Configure a reaction pool for a monitoring target
        
        Args:
            chat_id: Chat identifier to configure
            reactions: List of reaction configs with 'emoji' and optional 'weight' keys
                      Example: [{'emoji': '👍', 'weight': 2}, {'emoji': '❤️', 'weight': 1}]
            cooldown: Cooldown period between reactions (seconds, default 2.0)
            
        Returns:
            Dict with 'success' status and 'message' or 'error'
            
        Requirements: 7.1
        """
        try:
            self.logger.info(f"⚙️ Configuring reaction pool for chat {chat_id}")
            
            # Validate reactions list
            if not reactions:
                return {
                    'success': False,
                    'error': 'Reaction list cannot be empty'
                }
            
            # Create ReactionConfig objects
            from .models import ReactionConfig, ReactionPool
            reaction_configs = []
            for i, reaction in enumerate(reactions):
                if 'emoji' not in reaction:
                    return {
                        'success': False,
                        'error': f'Reaction at index {i} missing required "emoji" field'
                    }
                
                emoji = reaction['emoji']
                weight = reaction.get('weight', 1)
                
                try:
                    reaction_configs.append(ReactionConfig(emoji=emoji, weight=weight))
                except ValueError as e:
                    return {
                        'success': False,
                        'error': f'Invalid reaction at index {i}: {str(e)}'
                    }
            
            # Create and validate reaction pool
            try:
                reaction_pool = ReactionPool(reactions=reaction_configs)
            except ValueError as e:
                return {
                    'success': False,
                    'error': f'Invalid reaction pool: {str(e)}'
                }
            
            # Create monitoring target
            from .config import MonitoringTarget
            monitoring_target = MonitoringTarget(
                chat_id=chat_id,
                reaction_pool=reaction_pool,
                cooldown=cooldown
            )
            
            # Store in monitoring targets
            # Find existing target or create new one
            target_found = False
            for i, target in enumerate(self.monitoring_targets):
                if target.get('chat_id') == chat_id or (isinstance(target, MonitoringTarget) and target.chat_id == chat_id):
                    # Update existing target
                    self.monitoring_targets[i] = monitoring_target.to_dict()
                    target_found = True
                    break
            
            if not target_found:
                # Add new target
                self.monitoring_targets.append(monitoring_target.to_dict())
            
            self.logger.info(
                f"✅ Configured reaction pool for {chat_id} with {len(reaction_configs)} reactions"
            )
            
            return {
                'success': True,
                'message': f'Successfully configured reaction pool for {chat_id}',
                'chat_id': chat_id,
                'reaction_count': len(reaction_configs)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to configure reaction pool: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def update_reaction_pool(
        self,
        chat_id: str,
        reactions: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Update an existing reaction pool for a monitoring target
        
        Args:
            chat_id: Chat identifier to update
            reactions: New list of reaction configs with 'emoji' and optional 'weight' keys
            
        Returns:
            Dict with 'success' status and 'message' or 'error'
            
        Requirements: 9.1, 9.2
        """
        try:
            self.logger.info(f"🔄 Updating reaction pool for chat {chat_id}")
            
            # Find existing target
            target_index = None
            old_reactions = None
            for i, target in enumerate(self.monitoring_targets):
                target_chat_id = target.get('chat_id') if isinstance(target, dict) else target.chat_id
                if target_chat_id == chat_id:
                    target_index = i
                    # Get old reactions for logging
                    if isinstance(target, dict) and 'reaction_pool' in target:
                        old_reactions = target['reaction_pool']['reactions']
                    elif hasattr(target, 'reaction_pool') and target.reaction_pool:
                        old_reactions = [
                            {'emoji': r.emoji, 'weight': r.weight}
                            for r in target.reaction_pool.reactions
                        ]
                    break
            
            if target_index is None:
                return {
                    'success': False,
                    'error': f'No monitoring target found for chat {chat_id}'
                }
            
            # Validate new reactions
            if not reactions:
                return {
                    'success': False,
                    'error': 'Reaction list cannot be empty'
                }
            
            # Create ReactionConfig objects
            from .models import ReactionConfig, ReactionPool
            reaction_configs = []
            for i, reaction in enumerate(reactions):
                if 'emoji' not in reaction:
                    return {
                        'success': False,
                        'error': f'Reaction at index {i} missing required "emoji" field'
                    }
                
                emoji = reaction['emoji']
                weight = reaction.get('weight', 1)
                
                try:
                    reaction_configs.append(ReactionConfig(emoji=emoji, weight=weight))
                except ValueError as e:
                    # Validation failed, keep existing pool unchanged
                    return {
                        'success': False,
                        'error': f'Invalid reaction at index {i}: {str(e)}'
                    }
            
            # Create and validate new reaction pool
            try:
                new_reaction_pool = ReactionPool(reactions=reaction_configs)
            except ValueError as e:
                # Validation failed, keep existing pool unchanged
                return {
                    'success': False,
                    'error': f'Invalid reaction pool: {str(e)}'
                }
            
            # Get existing target to preserve other settings
            existing_target = self.monitoring_targets[target_index]
            cooldown = existing_target.get('cooldown', 2.0) if isinstance(existing_target, dict) else existing_target.cooldown
            
            # Create updated monitoring target
            from .config import MonitoringTarget
            updated_target = MonitoringTarget(
                chat_id=chat_id,
                reaction_pool=new_reaction_pool,
                cooldown=cooldown
            )
            
            # Update in monitoring targets
            self.monitoring_targets[target_index] = updated_target.to_dict()
            
            # If monitoring is active, update the session's monitoring targets
            if self.manager and self.manager.sessions:
                for session in self.manager.sessions.values():
                    if session.is_monitoring and chat_id in session.monitoring_targets:
                        session.monitoring_targets[chat_id].reaction_pool = new_reaction_pool
            
            # Enhanced logging for reaction pool updates with structured logging (Requirement 9.5)
            new_reactions_list = [{'emoji': r.emoji, 'weight': r.weight} for r in reaction_configs]
            self.logger.info(
                f"✅ Updated reaction pool for {chat_id}: "
                f"old={old_reactions}, new={new_reactions_list}",
                extra={
                    'operation_type': 'reaction_pool_update',
                    'chat_id': chat_id,
                    'old_reactions': old_reactions,
                    'new_reactions': new_reactions_list,
                    'old_reaction_count': len(old_reactions) if old_reactions else 0,
                    'new_reaction_count': len(reaction_configs),
                    'monitoring_active': self.manager and any(s.is_monitoring for s in self.manager.sessions.values()) if self.manager else False
                }
            )
            
            return {
                'success': True,
                'message': f'Successfully updated reaction pool for {chat_id}',
                'chat_id': chat_id,
                'old_reactions': old_reactions,
                'new_reactions': [{'emoji': r.emoji, 'weight': r.weight} for r in reaction_configs]
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update reaction pool: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_reaction_pools(self) -> Dict[str, Dict[str, any]]:
        """
        Get all reaction pool configurations for monitoring targets
        
        Returns:
            Dict mapping chat IDs to their reaction pool configurations
            Format: {
                'chat_id': {
                    'reactions': [{'emoji': '👍', 'weight': 1}, ...],
                    'cooldown': 2.0
                }
            }
            
        Requirements: 10.1
        """
        try:
            self.logger.info("📋 Retrieving reaction pool configurations")
            
            result = {}
            
            for target in self.monitoring_targets:
                if isinstance(target, dict):
                    chat_id = target.get('chat_id')
                    if 'reaction_pool' in target:
                        result[chat_id] = {
                            'reactions': target['reaction_pool']['reactions'],
                            'cooldown': target.get('cooldown', 2.0)
                        }
                    elif 'reaction' in target:
                        # Single reaction - display as single-item pool
                        result[chat_id] = {
                            'reactions': [{'emoji': target['reaction'], 'weight': 1}],
                            'cooldown': target.get('cooldown', 2.0)
                        }
                else:
                    # MonitoringTarget object
                    chat_id = target.chat_id
                    if target.reaction_pool:
                        result[chat_id] = {
                            'reactions': [
                                {'emoji': r.emoji, 'weight': r.weight}
                                for r in target.reaction_pool.reactions
                            ],
                            'cooldown': target.cooldown
                        }
                    elif target.reaction:
                        # Single reaction - display as single-item pool
                        result[chat_id] = {
                            'reactions': [{'emoji': target.reaction, 'weight': 1}],
                            'cooldown': target.cooldown
                        }
            
            self.logger.info(f"✅ Retrieved {len(result)} reaction pool configurations")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get reaction pools: {e}")
            return {}

    def migrate_single_reaction_to_pool(
        self,
        chat_id: str = None
    ) -> Dict[str, any]:
        """
        Migrate single reaction configuration to reaction pool format
        
        This utility helps migrate from the old single-reaction format to the new
        reaction pool format. If chat_id is provided, migrates only that target.
        Otherwise, migrates all targets with single reactions.
        
        Args:
            chat_id: Optional chat ID to migrate (if None, migrates all)
            
        Returns:
            Dict with migration results
            
        Requirements: 7.1
        """
        try:
            self.logger.info(f"🔄 Migrating single reactions to pools for {chat_id or 'all targets'}")
            
            migrated_count = 0
            skipped_count = 0
            errors = []
            
            from .models import ReactionConfig, ReactionPool
            from .config import MonitoringTarget
            
            for i, target in enumerate(self.monitoring_targets):
                # Get chat ID from target
                if isinstance(target, dict):
                    target_chat_id = target.get('chat_id')
                else:
                    target_chat_id = target.chat_id
                
                # Skip if specific chat_id requested and this isn't it
                if chat_id and target_chat_id != chat_id:
                    continue
                
                # Check if already has reaction pool
                has_pool = False
                if isinstance(target, dict):
                    has_pool = 'reaction_pool' in target
                else:
                    has_pool = target.reaction_pool is not None
                
                if has_pool:
                    skipped_count += 1
                    continue
                
                # Get single reaction
                single_reaction = None
                if isinstance(target, dict):
                    single_reaction = target.get('reaction')
                else:
                    single_reaction = target.reaction
                
                if not single_reaction:
                    skipped_count += 1
                    continue
                
                # Create reaction pool from single reaction
                try:
                    reaction_pool = ReactionPool(
                        reactions=[ReactionConfig(emoji=single_reaction, weight=1)]
                    )
                    
                    # Get cooldown
                    cooldown = target.get('cooldown', 2.0) if isinstance(target, dict) else target.cooldown
                    
                    # Create updated monitoring target
                    updated_target = MonitoringTarget(
                        chat_id=target_chat_id,
                        reaction_pool=reaction_pool,
                        cooldown=cooldown
                    )
                    
                    # Update in list
                    self.monitoring_targets[i] = updated_target.to_dict()
                    migrated_count += 1
                    
                    self.logger.info(f"✅ Migrated {target_chat_id}: '{single_reaction}' -> pool")
                    
                except Exception as e:
                    errors.append({
                        'chat_id': target_chat_id,
                        'error': str(e)
                    })
            
            result = {
                'success': len(errors) == 0,
                'migrated': migrated_count,
                'skipped': skipped_count,
                'errors': errors
            }
            
            if migrated_count > 0:
                self.logger.info(f"✅ Migration complete: {migrated_count} migrated, {skipped_count} skipped")
            else:
                self.logger.info(f"ℹ️ No targets to migrate ({skipped_count} already using pools)")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to migrate reactions: {e}")
            return {
                'success': False,
                'migrated': 0,
                'skipped': 0,
                'errors': [{'error': str(e)}]
            }