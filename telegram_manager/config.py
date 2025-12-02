"""
Configuration settings and data classes
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Union
import json
from telegram_manager.models import ReactionPool, ReactionConfig

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
    reaction_pool: Optional[ReactionPool] = None
    reaction: Optional[str] = None  # Deprecated, kept for backward compatibility
    cooldown: float = 1.0
    last_reaction_time: float = 0
    # Statistics tracking (Requirement 4.3)
    reactions_sent: int = 0
    messages_processed: int = 0
    reaction_failures: int = 0

    def __post_init__(self):
        """Initialize reaction pool from single reaction if needed"""
        # If reaction_pool is not set but reaction is, create a pool from single reaction
        if self.reaction_pool is None and self.reaction is not None:
            self.reaction_pool = ReactionPool(
                reactions=[ReactionConfig(emoji=self.reaction, weight=1)]
            )
        # If neither is set, use default
        elif self.reaction_pool is None and self.reaction is None:
            self.reaction = "👍"
            self.reaction_pool = ReactionPool(
                reactions=[ReactionConfig(emoji="👍", weight=1)]
            )
    
    def get_next_reaction(self) -> str:
        """
        Get next reaction from pool using weighted selection
        
        Returns:
            Selected emoji string
        """
        if self.reaction_pool is None:
            # Fallback to single reaction if pool is not set
            return self.reaction if self.reaction else "👍"
        return self.reaction_pool.select_random()

    def to_dict(self):
        """Convert to dictionary for serialization"""
        result = {
            'chat_id': self.chat_id,
            'cooldown': self.cooldown
        }
        
        # Serialize reaction pool
        if self.reaction_pool is not None:
            result['reaction_pool'] = {
                'reactions': [
                    {'emoji': r.emoji, 'weight': r.weight}
                    for r in self.reaction_pool.reactions
                ]
            }
        # Include single reaction for backward compatibility
        elif self.reaction is not None:
            result['reaction'] = self.reaction
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MonitoringTarget':
        """
        Create MonitoringTarget from dictionary with backward compatibility
        
        Args:
            data: Dictionary containing monitoring target configuration
            
        Returns:
            MonitoringTarget instance
        """
        chat_id = data['chat_id']
        cooldown = data.get('cooldown', 1.0)
        
        # Check if reaction_pool is present
        if 'reaction_pool' in data:
            reactions = [
                ReactionConfig(emoji=r['emoji'], weight=r.get('weight', 1))
                for r in data['reaction_pool']['reactions']
            ]
            reaction_pool = ReactionPool(reactions=reactions)
            return cls(
                chat_id=chat_id,
                reaction_pool=reaction_pool,
                cooldown=cooldown
            )
        # Backward compatibility: single reaction
        elif 'reaction' in data:
            return cls(
                chat_id=chat_id,
                reaction=data['reaction'],
                cooldown=cooldown
            )
        # Default
        else:
            return cls(
                chat_id=chat_id,
                cooldown=cooldown
            )

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