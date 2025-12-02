"""
Configuration Manager for CLI Panel

This module provides persistent configuration storage for the CLI panel,
including channel configurations, job definitions, and user preferences.
"""

import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from cli.models import ChannelConfig, JobConfig, ReactionConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages CLI configuration and persistence"""
    
    def __init__(self, config_path: str = 'cli/config.json'):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {
            'version': '1.0',
            'channels': [],
            'jobs': [],
            'preferences': {
                'default_delay': 2.0,
                'auto_save': True,
                'show_progress': True
            }
        }
        self._ensure_config_directory()
    
    def _ensure_config_directory(self):
        """Ensure the configuration directory exists"""
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
    
    async def load(self) -> bool:
        """
        Load configuration from file
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Validate and merge with defaults
                    self.config['version'] = loaded_config.get('version', '1.0')
                    self.config['channels'] = loaded_config.get('channels', [])
                    self.config['jobs'] = loaded_config.get('jobs', [])
                    self.config['preferences'] = {
                        **self.config['preferences'],
                        **loaded_config.get('preferences', {})
                    }
                logger.info(f"Configuration loaded from {self.config_path}")
                return True
            else:
                logger.info(f"No configuration file found at {self.config_path}, using defaults")
                return False
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted configuration file: {e}")
            logger.warning("Using default configuration")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    async def save(self) -> bool:
        """
        Save configuration to file
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self._ensure_config_directory()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get(self, key: str, default=None) -> Any:
        """
        Get configuration value
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    
    async def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value and persist
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            value: Value to set
            
        Returns:
            True if saved successfully, False otherwise
        """
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        
        # Auto-save if enabled
        if self.config['preferences'].get('auto_save', True):
            return await self.save()
        return True
    
    # Channel Management Methods
    
    def get_channels(self) -> List[ChannelConfig]:
        """
        Get all configured channels
        
        Returns:
            List of ChannelConfig objects
        """
        channels = []
        for channel_data in self.config.get('channels', []):
            try:
                # Convert reaction dicts to ReactionConfig objects
                reactions = [
                    ReactionConfig(emoji=r['emoji'], weight=r.get('weight', 1))
                    for r in channel_data.get('reactions', [])
                ]
                
                channel = ChannelConfig(
                    channel_id=channel_data['channel_id'],
                    channel_name=channel_data.get('channel_name'),
                    channel_username=channel_data.get('channel_username'),
                    reactions=reactions,
                    scraping_enabled=channel_data.get('scraping_enabled', True),
                    monitoring_enabled=channel_data.get('monitoring_enabled', False),
                    created_at=channel_data.get('created_at', 0.0)
                )
                channels.append(channel)
            except (KeyError, TypeError) as e:
                logger.error(f"Error parsing channel configuration: {e}")
                continue
        return channels
    
    def get_channel(self, channel_id: str) -> Optional[ChannelConfig]:
        """
        Get a specific channel by ID (case-insensitive)
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            ChannelConfig object or None if not found
        """
        channels = self.get_channels()
        channel_id_lower = channel_id.lower()
        for channel in channels:
            if channel.channel_id.lower() == channel_id_lower:
                return channel
        return None
    
    async def add_channel(self, channel: ChannelConfig) -> bool:
        """
        Add a channel configuration
        
        Args:
            channel: ChannelConfig object to add
            
        Returns:
            True if added successfully, False otherwise
        """
        # Check if channel already exists
        if self.get_channel(channel.channel_id):
            logger.warning(f"Channel {channel.channel_id} already exists")
            return False
        
        # Convert to dict for JSON serialization
        channel_dict = {
            'channel_id': channel.channel_id,
            'channel_name': channel.channel_name,
            'channel_username': channel.channel_username,
            'reactions': [
                {'emoji': r.emoji, 'weight': r.weight}
                for r in channel.reactions
            ],
            'scraping_enabled': channel.scraping_enabled,
            'monitoring_enabled': channel.monitoring_enabled,
            'created_at': channel.created_at
        }
        
        self.config['channels'].append(channel_dict)
        
        # Auto-save if enabled
        if self.config['preferences'].get('auto_save', True):
            return await self.save()
        return True
    
    async def update_channel(self, channel: ChannelConfig) -> bool:
        """
        Update an existing channel configuration
        
        Args:
            channel: ChannelConfig object with updated values
            
        Returns:
            True if updated successfully, False otherwise
        """
        for i, channel_data in enumerate(self.config['channels']):
            if channel_data['channel_id'] == channel.channel_id:
                # Update the channel
                self.config['channels'][i] = {
                    'channel_id': channel.channel_id,
                    'channel_name': channel.channel_name,
                    'channel_username': channel.channel_username,
                    'reactions': [
                        {'emoji': r.emoji, 'weight': r.weight}
                        for r in channel.reactions
                    ],
                    'scraping_enabled': channel.scraping_enabled,
                    'monitoring_enabled': channel.monitoring_enabled,
                    'created_at': channel.created_at
                }
                
                # Auto-save if enabled
                if self.config['preferences'].get('auto_save', True):
                    return await self.save()
                return True
        
        logger.warning(f"Channel {channel.channel_id} not found for update")
        return False
    
    async def remove_channel(self, channel_id: str) -> bool:
        """
        Remove a channel configuration
        
        Args:
            channel_id: Channel identifier to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        initial_count = len(self.config['channels'])
        self.config['channels'] = [
            c for c in self.config['channels']
            if c['channel_id'] != channel_id
        ]
        
        if len(self.config['channels']) < initial_count:
            # Auto-save if enabled
            if self.config['preferences'].get('auto_save', True):
                return await self.save()
            return True
        
        logger.warning(f"Channel {channel_id} not found for removal")
        return False
    
    # Job Management Methods
    
    def get_jobs(self) -> List[JobConfig]:
        """
        Get all configured jobs
        
        Returns:
            List of JobConfig objects
        """
        jobs = []
        for job_data in self.config.get('jobs', []):
            try:
                job = JobConfig(
                    job_id=job_data['job_id'],
                    job_type=job_data['job_type'],
                    schedule_interval=job_data['schedule_interval'],
                    target_channel=job_data.get('target_channel'),
                    parameters=job_data.get('parameters', {}),
                    enabled=job_data.get('enabled', True),
                    created_at=job_data.get('created_at', 0.0)
                )
                jobs.append(job)
            except (KeyError, TypeError) as e:
                logger.error(f"Error parsing job configuration: {e}")
                continue
        return jobs
    
    def get_job(self, job_id: str) -> Optional[JobConfig]:
        """
        Get a specific job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobConfig object or None if not found
        """
        jobs = self.get_jobs()
        for job in jobs:
            if job.job_id == job_id:
                return job
        return None
    
    async def add_job(self, job: JobConfig) -> bool:
        """
        Add a job configuration
        
        Args:
            job: JobConfig object to add
            
        Returns:
            True if added successfully, False otherwise
        """
        # Check if job already exists
        if self.get_job(job.job_id):
            logger.warning(f"Job {job.job_id} already exists")
            return False
        
        # Convert to dict for JSON serialization
        job_dict = {
            'job_id': job.job_id,
            'job_type': job.job_type,
            'schedule_interval': job.schedule_interval,
            'target_channel': job.target_channel,
            'parameters': job.parameters,
            'enabled': job.enabled,
            'created_at': job.created_at
        }
        
        self.config['jobs'].append(job_dict)
        
        # Auto-save if enabled
        if self.config['preferences'].get('auto_save', True):
            return await self.save()
        return True
    
    async def update_job(self, job: JobConfig) -> bool:
        """
        Update an existing job configuration
        
        Args:
            job: JobConfig object with updated values
            
        Returns:
            True if updated successfully, False otherwise
        """
        for i, job_data in enumerate(self.config['jobs']):
            if job_data['job_id'] == job.job_id:
                # Update the job
                self.config['jobs'][i] = {
                    'job_id': job.job_id,
                    'job_type': job.job_type,
                    'schedule_interval': job.schedule_interval,
                    'target_channel': job.target_channel,
                    'parameters': job.parameters,
                    'enabled': job.enabled,
                    'created_at': job.created_at
                }
                
                # Auto-save if enabled
                if self.config['preferences'].get('auto_save', True):
                    return await self.save()
                return True
        
        logger.warning(f"Job {job.job_id} not found for update")
        return False
    
    async def remove_job(self, job_id: str) -> bool:
        """
        Remove a job configuration
        
        Args:
            job_id: Job identifier to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        initial_count = len(self.config['jobs'])
        self.config['jobs'] = [
            j for j in self.config['jobs']
            if j['job_id'] != job_id
        ]
        
        if len(self.config['jobs']) < initial_count:
            # Auto-save if enabled
            if self.config['preferences'].get('auto_save', True):
                return await self.save()
            return True
        
        logger.warning(f"Job {job_id} not found for removal")
        return False
    
    # Preferences Management Methods
    
    def get_preference(self, key: str, default=None) -> Any:
        """
        Get a preference value
        
        Args:
            key: Preference key
            default: Default value if not found
            
        Returns:
            Preference value or default
        """
        return self.config['preferences'].get(key, default)
    
    async def set_preference(self, key: str, value: Any) -> bool:
        """
        Set a preference value
        
        Args:
            key: Preference key
            value: Preference value
            
        Returns:
            True if saved successfully, False otherwise
        """
        self.config['preferences'][key] = value
        
        # Auto-save if enabled
        if self.config['preferences'].get('auto_save', True):
            return await self.save()
        return True
    
    def get_all_preferences(self) -> Dict[str, Any]:
        """
        Get all preferences
        
        Returns:
            Dictionary of all preferences
        """
        return self.config['preferences'].copy()
    
    async def add_channel_with_join(self, channel: ChannelConfig, session_manager) -> Dict[str, bool]:
        """
        Add a channel configuration and trigger auto-join with all sessions
        
        This method combines channel addition with automatic joining across all
        active sessions, providing immediate feedback on join success.
        
        Args:
            channel: ChannelConfig object to add
            session_manager: TelegramSessionManager instance for joining
            
        Returns:
            Dict mapping session names to join success status
            Empty dict if channel addition failed
            
        Requirements: 2.1, 2.2, 2.3
        """
        # First add the channel to configuration
        add_success = await self.add_channel(channel)
        
        if not add_success:
            logger.warning(f"Failed to add channel {channel.channel_id}, skipping auto-join")
            return {}
        
        # Trigger auto-join with all sessions
        join_results = await self.trigger_auto_join(channel.channel_id, session_manager)
        
        return join_results
    
    async def trigger_auto_join(self, channel_id: str, session_manager) -> Dict[str, bool]:
        """
        Trigger auto-join for a channel across all sessions
        
        This method calls the session manager's join_channel_all_sessions method
        to attempt joining the channel with all active sessions.
        
        Args:
            channel_id: Channel identifier to join
            session_manager: TelegramSessionManager instance for joining
            
        Returns:
            Dict mapping session names to join success status (True/False)
            
        Requirements: 2.1, 2.2, 2.3
        """
        logger.info(f"Triggering auto-join for channel {channel_id}")
        
        # Call session manager to join with all sessions
        join_results = await session_manager.join_channel_all_sessions(channel_id)
        
        # Log summary
        succeeded = sum(1 for success in join_results.values() if success)
        failed = len(join_results) - succeeded
        logger.info(
            f"Auto-join complete for {channel_id}: "
            f"{succeeded} succeeded, {failed} failed out of {len(join_results)} sessions"
        )
        
        return join_results
