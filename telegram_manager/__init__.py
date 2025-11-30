"""
Telegram Session Manager
A robust system for managing multiple Telegram sessions with monitoring capabilities.
"""

__version__ = "1.0.0"
__author__ = "Ali-moments"

from .session import TelegramSession, MonitoringTarget
from .manager import TelegramSessionManager
from .load_balancer import LoadBalancer, LoadBalancingStrategy
from .models import (
    MessageResult,
    BulkSendResult,
    ValidationError,
    ValidationResult,
    SendPreview,
    RecipientValidator
)

__all__ = [
    'TelegramSession',
    'MonitoringTarget',
    'TelegramSessionManager',
    'LoadBalancer',
    'LoadBalancingStrategy',
    'MessageResult',
    'BulkSendResult',
    'ValidationError',
    'ValidationResult',
    'SendPreview',
    'RecipientValidator'
]