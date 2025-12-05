"""
Statistics Manager for Telegram Bot Panel

This module provides comprehensive statistics calculation and persistence
for all operation types: scraping, sending, monitoring, and session-level metrics.

Requirements: AC-17.1, AC-17.2, AC-17.3, AC-17.4
"""

import json
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class ScrapingStatistics:
    """
    Statistics for scraping operations
    
    Requirements: AC-17.1
    """
    total_members_scraped: int = 0
    total_groups_processed: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    last_scrape_time: Optional[float] = None
    
    # Daily statistics
    daily_members_scraped: int = 0
    daily_groups_processed: int = 0
    daily_reset_time: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_groups_processed == 0:
            return 0.0
        return (self.successful_scrapes / self.total_groups_processed) * 100
    
    def add_scrape_result(self, members_count: int, success: bool) -> None:
        """Add a scrape result to statistics"""
        self.total_groups_processed += 1
        self.daily_groups_processed += 1
        
        if success:
            self.successful_scrapes += 1
            self.total_members_scraped += members_count
            self.daily_members_scraped += members_count
        else:
            self.failed_scrapes += 1
        
        self.last_scrape_time = time.time()

    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.daily_members_scraped = 0
        self.daily_groups_processed = 0
        self.daily_reset_time = time.time()


@dataclass
class SendingStatistics:
    """
    Statistics for sending operations
    
    Requirements: AC-17.2
    """
    total_messages_sent: int = 0
    successful_sends: int = 0
    failed_sends: int = 0
    last_send_time: Optional[float] = None
    
    # Failure categorization
    failure_reasons: Dict[str, int] = field(default_factory=dict)
    
    # Daily statistics
    daily_messages_sent: int = 0
    daily_successful_sends: int = 0
    daily_reset_time: float = field(default_factory=time.time)
    
    @property
    def delivery_rate(self) -> float:
        """Calculate delivery rate percentage"""
        if self.total_messages_sent == 0:
            return 0.0
        return (self.successful_sends / self.total_messages_sent) * 100
    
    def add_send_result(self, success: bool, failure_reason: Optional[str] = None) -> None:
        """Add a send result to statistics"""
        self.total_messages_sent += 1
        self.daily_messages_sent += 1
        
        if success:
            self.successful_sends += 1
            self.daily_successful_sends += 1
        else:
            self.failed_sends += 1
            if failure_reason:
                self.failure_reasons[failure_reason] = self.failure_reasons.get(failure_reason, 0) + 1
        
        self.last_send_time = time.time()
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.daily_messages_sent = 0
        self.daily_successful_sends = 0
        self.daily_reset_time = time.time()
    
    def get_top_failure_reasons(self, limit: int = 5) -> List[tuple]:
        """Get top failure reasons sorted by count"""
        sorted_reasons = sorted(
            self.failure_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_reasons[:limit]



@dataclass
class MonitoringStatistics:
    """
    Statistics for monitoring operations
    
    Requirements: AC-17.3
    """
    # Per-channel statistics
    channel_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Global statistics
    total_reactions_sent: int = 0
    total_messages_processed: int = 0
    monitoring_start_time: Optional[float] = None
    total_uptime_seconds: float = 0.0
    
    # Daily statistics
    daily_reactions_sent: int = 0
    daily_messages_processed: int = 0
    daily_reset_time: float = field(default_factory=time.time)
    
    def add_channel_reaction(self, channel_id: str, emoji: str) -> None:
        """Add a reaction sent to a channel"""
        if channel_id not in self.channel_stats:
            self.channel_stats[channel_id] = {
                'reactions_sent': 0,
                'messages_processed': 0,
                'reactions_by_emoji': {},
                'last_reaction_time': None
            }
        
        self.channel_stats[channel_id]['reactions_sent'] += 1
        self.channel_stats[channel_id]['last_reaction_time'] = time.time()
        
        # Track by emoji
        emoji_stats = self.channel_stats[channel_id]['reactions_by_emoji']
        emoji_stats[emoji] = emoji_stats.get(emoji, 0) + 1
        
        # Update global stats
        self.total_reactions_sent += 1
        self.daily_reactions_sent += 1
    
    def add_channel_message_processed(self, channel_id: str) -> None:
        """Add a message processed for a channel"""
        if channel_id not in self.channel_stats:
            self.channel_stats[channel_id] = {
                'reactions_sent': 0,
                'messages_processed': 0,
                'reactions_by_emoji': {},
                'last_reaction_time': None
            }
        
        self.channel_stats[channel_id]['messages_processed'] += 1
        
        # Update global stats
        self.total_messages_processed += 1
        self.daily_messages_processed += 1
    
    def get_channel_engagement_rate(self, channel_id: str) -> float:
        """Calculate engagement rate for a channel"""
        if channel_id not in self.channel_stats:
            return 0.0
        
        stats = self.channel_stats[channel_id]
        messages = stats['messages_processed']
        
        if messages == 0:
            return 0.0
        
        return (stats['reactions_sent'] / messages) * 100
    
    def start_monitoring(self) -> None:
        """Mark monitoring as started"""
        if self.monitoring_start_time is None:
            self.monitoring_start_time = time.time()
    
    def stop_monitoring(self) -> None:
        """Mark monitoring as stopped and update uptime"""
        if self.monitoring_start_time is not None:
            self.total_uptime_seconds += time.time() - self.monitoring_start_time
            self.monitoring_start_time = None
    
    def get_current_uptime_seconds(self) -> float:
        """Get current uptime in seconds"""
        uptime = self.total_uptime_seconds
        if self.monitoring_start_time is not None:
            uptime += time.time() - self.monitoring_start_time
        return uptime
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.daily_reactions_sent = 0
        self.daily_messages_processed = 0
        self.daily_reset_time = time.time()



@dataclass
class SessionStatistics:
    """
    Statistics for a single session
    
    Requirements: AC-17.4
    """
    session_name: str
    phone: str = "نامشخص"
    
    # Usage metrics
    messages_read: int = 0
    groups_scraped: int = 0
    messages_sent: int = 0
    reactions_sent: int = 0
    
    # Daily limits tracking
    daily_message_limit: int = 500
    daily_scrape_limit: int = 10
    daily_send_limit: int = 200
    
    # Historical data (last 7 days)
    historical_usage: List[Dict[str, Any]] = field(default_factory=list)
    
    # Daily reset
    daily_reset_time: float = field(default_factory=time.time)
    
    @property
    def message_limit_usage_percent(self) -> float:
        """Calculate message limit usage percentage"""
        if self.daily_message_limit == 0:
            return 0.0
        return (self.messages_read / self.daily_message_limit) * 100
    
    @property
    def scrape_limit_usage_percent(self) -> float:
        """Calculate scrape limit usage percentage"""
        if self.daily_scrape_limit == 0:
            return 0.0
        return (self.groups_scraped / self.daily_scrape_limit) * 100
    
    @property
    def send_limit_usage_percent(self) -> float:
        """Calculate send limit usage percentage"""
        if self.daily_send_limit == 0:
            return 0.0
        return (self.messages_sent / self.daily_send_limit) * 100
    
    def add_message_read(self, count: int = 1) -> None:
        """Add messages read"""
        self.messages_read += count
    
    def add_group_scraped(self, count: int = 1) -> None:
        """Add groups scraped"""
        self.groups_scraped += count
    
    def add_message_sent(self, count: int = 1) -> None:
        """Add messages sent"""
        self.messages_sent += count
    
    def add_reaction_sent(self, count: int = 1) -> None:
        """Add reactions sent"""
        self.reactions_sent += count
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics and save to history"""
        # Save current day to history
        self.historical_usage.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'messages_read': self.messages_read,
            'groups_scraped': self.groups_scraped,
            'messages_sent': self.messages_sent,
            'reactions_sent': self.reactions_sent,
            'timestamp': time.time()
        })
        
        # Keep only last 7 days
        if len(self.historical_usage) > 7:
            self.historical_usage = self.historical_usage[-7:]
        
        # Reset counters
        self.messages_read = 0
        self.groups_scraped = 0
        self.messages_sent = 0
        self.reactions_sent = 0
        self.daily_reset_time = time.time()
    
    def get_historical_trend(self, metric: str) -> List[int]:
        """Get historical trend for a metric"""
        return [day.get(metric, 0) for day in self.historical_usage]



class StatisticsManager:
    """
    Centralized statistics management for the bot panel
    
    Manages statistics for:
    - Scraping operations (AC-17.1)
    - Sending operations (AC-17.2)
    - Monitoring operations (AC-17.3)
    - Session-level metrics (AC-17.4)
    
    Provides persistence and automatic daily reset functionality.
    """
    
    def __init__(self, storage_path: str = "data/statistics.json"):
        """
        Initialize statistics manager
        
        Args:
            storage_path: Path to statistics storage file
        """
        self.logger = logging.getLogger("StatisticsManager")
        self.storage_path = Path(storage_path)
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Statistics objects
        self.scraping_stats = ScrapingStatistics()
        self.sending_stats = SendingStatistics()
        self.monitoring_stats = MonitoringStatistics()
        self.session_stats: Dict[str, SessionStatistics] = {}
        
        # Load persisted statistics
        self.load_statistics()
        
        # Check if daily reset is needed
        self._check_daily_reset()
        
        self.logger.info("StatisticsManager initialized")
    
    # Scraping Statistics (AC-17.1)
    
    def record_scrape_result(
        self,
        session_name: str,
        members_count: int,
        success: bool
    ) -> None:
        """
        Record a scraping operation result
        
        Args:
            session_name: Name of session that performed scrape
            members_count: Number of members scraped
            success: Whether scrape was successful
            
        Requirements: AC-17.1
        """
        # Update global scraping stats
        self.scraping_stats.add_scrape_result(members_count, success)
        
        # Update session stats
        if success:
            self._ensure_session_stats(session_name)
            self.session_stats[session_name].add_group_scraped()
            self.session_stats[session_name].add_message_read(members_count)
        
        # Persist changes
        self.save_statistics()
        
        self.logger.debug(
            f"Recorded scrape result: session={session_name}, "
            f"members={members_count}, success={success}"
        )
    
    def get_scraping_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive scraping statistics
        
        Returns:
            Dict with scraping statistics
            
        Requirements: AC-17.1
        """
        return {
            'total_members_scraped': self.scraping_stats.total_members_scraped,
            'total_groups_processed': self.scraping_stats.total_groups_processed,
            'successful_scrapes': self.scraping_stats.successful_scrapes,
            'failed_scrapes': self.scraping_stats.failed_scrapes,
            'success_rate': self.scraping_stats.success_rate,
            'daily_members_scraped': self.scraping_stats.daily_members_scraped,
            'daily_groups_processed': self.scraping_stats.daily_groups_processed,
            'last_scrape_time': self.scraping_stats.last_scrape_time
        }

    
    # Sending Statistics (AC-17.2)
    
    def record_send_result(
        self,
        session_name: str,
        success: bool,
        failure_reason: Optional[str] = None
    ) -> None:
        """
        Record a message sending result
        
        Args:
            session_name: Name of session that sent message
            success: Whether send was successful
            failure_reason: Reason for failure if applicable
            
        Requirements: AC-17.2
        """
        # Update global sending stats
        self.sending_stats.add_send_result(success, failure_reason)
        
        # Update session stats
        if success:
            self._ensure_session_stats(session_name)
            self.session_stats[session_name].add_message_sent()
        
        # Persist changes
        self.save_statistics()
        
        self.logger.debug(
            f"Recorded send result: session={session_name}, "
            f"success={success}, reason={failure_reason}"
        )
    
    def get_sending_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive sending statistics
        
        Returns:
            Dict with sending statistics
            
        Requirements: AC-17.2
        """
        return {
            'total_messages_sent': self.sending_stats.total_messages_sent,
            'successful_sends': self.sending_stats.successful_sends,
            'failed_sends': self.sending_stats.failed_sends,
            'delivery_rate': self.sending_stats.delivery_rate,
            'daily_messages_sent': self.sending_stats.daily_messages_sent,
            'daily_successful_sends': self.sending_stats.daily_successful_sends,
            'top_failure_reasons': self.sending_stats.get_top_failure_reasons(),
            'last_send_time': self.sending_stats.last_send_time
        }
    
    # Monitoring Statistics (AC-17.3)
    
    def record_reaction_sent(
        self,
        session_name: str,
        channel_id: str,
        emoji: str
    ) -> None:
        """
        Record a reaction sent to a channel
        
        Args:
            session_name: Name of session that sent reaction
            channel_id: Channel identifier
            emoji: Emoji used for reaction
            
        Requirements: AC-17.3
        """
        # Update monitoring stats
        self.monitoring_stats.add_channel_reaction(channel_id, emoji)
        
        # Update session stats
        self._ensure_session_stats(session_name)
        self.session_stats[session_name].add_reaction_sent()
        
        # Persist changes
        self.save_statistics()
        
        self.logger.debug(
            f"Recorded reaction: session={session_name}, "
            f"channel={channel_id}, emoji={emoji}"
        )
    
    def record_message_processed(self, channel_id: str) -> None:
        """
        Record a message processed for monitoring
        
        Args:
            channel_id: Channel identifier
            
        Requirements: AC-17.3
        """
        self.monitoring_stats.add_channel_message_processed(channel_id)
        self.save_statistics()
    
    def start_monitoring(self) -> None:
        """Mark monitoring as started"""
        self.monitoring_stats.start_monitoring()
        self.save_statistics()
    
    def stop_monitoring(self) -> None:
        """Mark monitoring as stopped"""
        self.monitoring_stats.stop_monitoring()
        self.save_statistics()
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring statistics
        
        Returns:
            Dict with monitoring statistics
            
        Requirements: AC-17.3
        """
        # Calculate per-channel stats
        channel_details = []
        for channel_id, stats in self.monitoring_stats.channel_stats.items():
            channel_details.append({
                'channel_id': channel_id,
                'reactions_sent': stats['reactions_sent'],
                'messages_processed': stats['messages_processed'],
                'engagement_rate': self.monitoring_stats.get_channel_engagement_rate(channel_id),
                'reactions_by_emoji': stats['reactions_by_emoji'],
                'last_reaction_time': stats['last_reaction_time']
            })
        
        return {
            'total_reactions_sent': self.monitoring_stats.total_reactions_sent,
            'total_messages_processed': self.monitoring_stats.total_messages_processed,
            'daily_reactions_sent': self.monitoring_stats.daily_reactions_sent,
            'daily_messages_processed': self.monitoring_stats.daily_messages_processed,
            'uptime_seconds': self.monitoring_stats.get_current_uptime_seconds(),
            'channel_details': channel_details
        }

    
    # Session Statistics (AC-17.4)
    
    def get_session_statistics(self, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific session
        
        Args:
            session_name: Name of session
            
        Returns:
            Dict with session statistics or None if not found
            
        Requirements: AC-17.4
        """
        if session_name not in self.session_stats:
            return None
        
        stats = self.session_stats[session_name]
        
        return {
            'session_name': stats.session_name,
            'phone': stats.phone,
            'messages_read': stats.messages_read,
            'groups_scraped': stats.groups_scraped,
            'messages_sent': stats.messages_sent,
            'reactions_sent': stats.reactions_sent,
            'daily_message_limit': stats.daily_message_limit,
            'daily_scrape_limit': stats.daily_scrape_limit,
            'daily_send_limit': stats.daily_send_limit,
            'message_limit_usage_percent': stats.message_limit_usage_percent,
            'scrape_limit_usage_percent': stats.scrape_limit_usage_percent,
            'send_limit_usage_percent': stats.send_limit_usage_percent,
            'historical_usage': stats.historical_usage
        }
    
    def get_all_session_statistics(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all sessions
        
        Returns:
            List of session statistics dicts
            
        Requirements: AC-17.4
        """
        return [
            self.get_session_statistics(session_name)
            for session_name in self.session_stats.keys()
        ]
    
    def update_session_phone(self, session_name: str, phone: str) -> None:
        """Update phone number for a session"""
        self._ensure_session_stats(session_name)
        self.session_stats[session_name].phone = phone
        self.save_statistics()
    
    # Persistence
    
    def save_statistics(self) -> None:
        """Save statistics to disk"""
        try:
            data = {
                'scraping': asdict(self.scraping_stats),
                'sending': asdict(self.sending_stats),
                'monitoring': asdict(self.monitoring_stats),
                'sessions': {
                    name: asdict(stats)
                    for name, stats in self.session_stats.items()
                },
                'last_saved': time.time()
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("Statistics saved to disk")
        
        except Exception as e:
            self.logger.error(f"Error saving statistics: {e}")
    
    def load_statistics(self) -> None:
        """Load statistics from disk"""
        try:
            if not self.storage_path.exists():
                self.logger.info("No existing statistics file found")
                return
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load scraping stats
            if 'scraping' in data:
                self.scraping_stats = ScrapingStatistics(**data['scraping'])
            
            # Load sending stats
            if 'sending' in data:
                self.sending_stats = SendingStatistics(**data['sending'])
            
            # Load monitoring stats
            if 'monitoring' in data:
                self.monitoring_stats = MonitoringStatistics(**data['monitoring'])
            
            # Load session stats
            if 'sessions' in data:
                for session_name, session_data in data['sessions'].items():
                    self.session_stats[session_name] = SessionStatistics(**session_data)
            
            self.logger.info("Statistics loaded from disk")
        
        except Exception as e:
            self.logger.error(f"Error loading statistics: {e}")
    
    # Daily Reset
    
    def _check_daily_reset(self) -> None:
        """Check if daily reset is needed and perform it"""
        current_time = time.time()
        
        # Check scraping stats
        if self._should_reset_daily(self.scraping_stats.daily_reset_time):
            self.scraping_stats.reset_daily_stats()
            self.logger.info("Reset daily scraping statistics")
        
        # Check sending stats
        if self._should_reset_daily(self.sending_stats.daily_reset_time):
            self.sending_stats.reset_daily_stats()
            self.logger.info("Reset daily sending statistics")
        
        # Check monitoring stats
        if self._should_reset_daily(self.monitoring_stats.daily_reset_time):
            self.monitoring_stats.reset_daily_stats()
            self.logger.info("Reset daily monitoring statistics")
        
        # Check session stats
        for session_name, stats in self.session_stats.items():
            if self._should_reset_daily(stats.daily_reset_time):
                stats.reset_daily_stats()
                self.logger.info(f"Reset daily statistics for session {session_name}")
        
        # Save after reset
        self.save_statistics()
    
    def _should_reset_daily(self, last_reset_time: float) -> bool:
        """Check if daily reset is needed"""
        last_reset_date = datetime.fromtimestamp(last_reset_time).date()
        current_date = datetime.now().date()
        return current_date > last_reset_date
    
    def _ensure_session_stats(self, session_name: str) -> None:
        """Ensure session statistics object exists"""
        if session_name not in self.session_stats:
            self.session_stats[session_name] = SessionStatistics(
                session_name=session_name
            )
    
    # Utility Methods
    
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """
        Get all statistics in one call
        
        Returns:
            Dict with all statistics
        """
        return {
            'scraping': self.get_scraping_statistics(),
            'sending': self.get_sending_statistics(),
            'monitoring': self.get_monitoring_statistics(),
            'sessions': self.get_all_session_statistics()
        }
    
    def reset_all_statistics(self) -> None:
        """Reset all statistics (use with caution)"""
        self.scraping_stats = ScrapingStatistics()
        self.sending_stats = SendingStatistics()
        self.monitoring_stats = MonitoringStatistics()
        self.session_stats.clear()
        self.save_statistics()
        self.logger.warning("All statistics have been reset")
