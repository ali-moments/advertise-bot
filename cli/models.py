"""
Data models for CLI Panel

This module contains dataclasses for CLI-specific data structures including
channel configurations, job configurations, and scraping results.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time


@dataclass
class ReactionConfig:
    """Configuration for a single reaction"""
    emoji: str
    weight: int = 1


@dataclass
class ChannelConfig:
    """Configuration for a monitored channel"""
    channel_id: str
    channel_name: Optional[str] = None
    channel_username: Optional[str] = None
    reactions: List[ReactionConfig] = field(default_factory=list)
    scraping_enabled: bool = True
    monitoring_enabled: bool = False
    created_at: float = field(default_factory=time.time)
    
    def get_display_name(self) -> str:
        """Get display name (name or identifier fallback)"""
        return self.channel_name or self.channel_id


@dataclass
class JobConfig:
    """Configuration for a scheduled job"""
    job_id: str
    job_type: str  # 'scrape_members', 'scrape_messages', 'scrape_links', 'send_messages'
    schedule_interval: int  # Interval in hours
    target_channel: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class Job:
    """Represents a scheduled job"""
    config: JobConfig
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    status: str = 'pending'  # 'pending', 'running', 'completed', 'failed'
    error: Optional[str] = None


@dataclass
class LinkScrapingResult:
    """Result of link scraping operation"""
    channel_id: str
    total_messages: int
    total_links: int
    unique_domains: int
    links_by_domain: Dict[str, int]
    links_by_type: Dict[str, int]  # 'http', 'https', 'telegram', etc.
    timestamp: float
    output_file: str
