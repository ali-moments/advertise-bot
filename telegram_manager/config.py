"""
Configuration settings and data classes
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import json

@dataclass
class SessionConfig:
    """Configuration for a single Telegram session"""
    name: str
    session_file: str
    api_id: int
    api_hash: str
    db_data: Any = None

@dataclass
class MonitoringTarget:
    """Configuration for monitoring a chat"""
    chat_id: str
    reaction: str = "👍"
    cooldown: float = 2.0
    last_reaction_time: float = 0

    def to_dict(self):
        return {
            'chat_id': self.chat_id,
            'reaction': self.reaction,
            'cooldown': self.cooldown
        }

@dataclass
class AppConfig:
    """Main application configuration"""
    sessions: List[SessionConfig]
    monitoring_targets: List[Dict]
    max_concurrent_operations: int = 3
    default_delay: float = 2.0

    @classmethod
    def from_file(cls, config_path: str):
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        sessions = [SessionConfig(**session) for session in data.get('sessions', [])]
        
        return cls(
            sessions=sessions,
            monitoring_targets=data.get('monitoring_targets', []),
            max_concurrent_operations=data.get('max_concurrent_operations', 3),
            default_delay=data.get('default_delay', 2.0)
        )

    def to_file(self, config_path: str):
        """Save configuration to JSON file"""
        data = {
            'sessions': [asdict(session) for session in self.sessions],
            'monitoring_targets': self.monitoring_targets,
            'max_concurrent_operations': self.max_concurrent_operations,
            'default_delay': self.default_delay
        }
        
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)