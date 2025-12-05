"""
Batch Result Tracker - Tracks success and failure for batch operations

This module handles:
- Per-item result tracking
- Success/failure statistics
- Detailed error reporting
- Result aggregation

Requirements: 12.4 - Provide detailed results showing which items succeeded and which failed
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ItemStatus(Enum):
    """Status of a batch item"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ItemResult:
    """Result for a single item in a batch operation"""
    identifier: str
    status: ItemStatus
    session_used: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    timestamp: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def success(self) -> bool:
        """Check if item was successful"""
        return self.status == ItemStatus.SUCCESS
    
    @property
    def failed(self) -> bool:
        """Check if item failed"""
        return self.status == ItemStatus.FAILED


@dataclass
class BatchResult:
    """Aggregated results for a batch operation"""
    operation_type: str  # 'scraping', 'sending', etc.
    total_items: int
    successful_items: List[ItemResult] = field(default_factory=list)
    failed_items: List[ItemResult] = field(default_factory=list)
    skipped_items: List[ItemResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()
    
    @property
    def success_count(self) -> int:
        """Number of successful items"""
        return len(self.successful_items)
    
    @property
    def failure_count(self) -> int:
        """Number of failed items"""
        return len(self.failed_items)
    
    @property
    def skipped_count(self) -> int:
        """Number of skipped items"""
        return len(self.skipped_items)
    
    @property
    def completed_count(self) -> int:
        """Number of completed items (success + failed + skipped)"""
        return self.success_count + self.failure_count + self.skipped_count
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage"""
        if self.completed_count == 0:
            return 0.0
        return (self.success_count / self.completed_count) * 100
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Duration of operation in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def get_failed_identifiers(self) -> List[str]:
        """Get list of failed item identifiers"""
        return [item.identifier for item in self.failed_items]
    
    def get_successful_identifiers(self) -> List[str]:
        """Get list of successful item identifiers"""
        return [item.identifier for item in self.successful_items]
    
    def get_errors_by_type(self) -> Dict[str, List[str]]:
        """Group failed items by error type"""
        errors: Dict[str, List[str]] = {}
        for item in self.failed_items:
            error_msg = item.error or "Unknown error"
            if error_msg not in errors:
                errors[error_msg] = []
            errors[error_msg].append(item.identifier)
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'operation_type': self.operation_type,
            'total_items': self.total_items,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'skipped_count': self.skipped_count,
            'success_rate': self.success_rate,
            'duration_seconds': self.duration_seconds,
            'successful_items': [
                {
                    'identifier': item.identifier,
                    'session': item.session_used,
                    'attempts': item.attempts
                }
                for item in self.successful_items
            ],
            'failed_items': [
                {
                    'identifier': item.identifier,
                    'session': item.session_used,
                    'error': item.error,
                    'attempts': item.attempts
                }
                for item in self.failed_items
            ],
            'errors_by_type': self.get_errors_by_type()
        }


class BatchResultTracker:
    """
    Tracks results for batch operations with detailed per-item tracking
    
    Supports:
    - Recording success/failure per item
    - Aggregating statistics
    - Generating detailed reports
    - Continuing on failures
    
    Requirements: 12.4
    """
    
    def __init__(self, operation_type: str, total_items: int):
        """
        Initialize batch result tracker
        
        Args:
            operation_type: Type of operation ('scraping', 'sending', etc.)
            total_items: Total number of items in batch
        """
        self.logger = logging.getLogger("BatchResultTracker")
        self.batch_result = BatchResult(
            operation_type=operation_type,
            total_items=total_items
        )
        self._pending_items: Dict[str, ItemResult] = {}
    
    def start_item(self, identifier: str) -> None:
        """
        Mark an item as started
        
        Args:
            identifier: Item identifier
        """
        if identifier not in self._pending_items:
            self._pending_items[identifier] = ItemResult(
                identifier=identifier,
                status=ItemStatus.PENDING
            )
    
    def record_success(
        self,
        identifier: str,
        session_used: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record successful completion of an item
        
        Args:
            identifier: Item identifier
            session_used: Session that processed the item
            data: Additional data about the result
            
        Requirements: 12.4
        """
        if identifier in self._pending_items:
            item = self._pending_items[identifier]
            item.status = ItemStatus.SUCCESS
            item.session_used = session_used
            item.attempts += 1
            if data:
                item.data.update(data)
            item.timestamp = datetime.now()
            
            self.batch_result.successful_items.append(item)
            del self._pending_items[identifier]
        else:
            # Create new success result
            item = ItemResult(
                identifier=identifier,
                status=ItemStatus.SUCCESS,
                session_used=session_used,
                attempts=1,
                data=data or {}
            )
            self.batch_result.successful_items.append(item)
        
        self.logger.debug(
            f"✅ Item succeeded: {identifier}",
            extra={
                'identifier': identifier,
                'session': session_used,
                'operation_type': self.batch_result.operation_type
            }
        )
    
    def record_failure(
        self,
        identifier: str,
        error: str,
        session_used: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record failure of an item
        
        Args:
            identifier: Item identifier
            error: Error message
            session_used: Session that attempted the item
            data: Additional data about the failure
            
        Requirements: 12.4
        """
        if identifier in self._pending_items:
            item = self._pending_items[identifier]
            item.status = ItemStatus.FAILED
            item.error = error
            item.session_used = session_used
            item.attempts += 1
            if data:
                item.data.update(data)
            item.timestamp = datetime.now()
            
            self.batch_result.failed_items.append(item)
            del self._pending_items[identifier]
        else:
            # Create new failure result
            item = ItemResult(
                identifier=identifier,
                status=ItemStatus.FAILED,
                error=error,
                session_used=session_used,
                attempts=1,
                data=data or {}
            )
            self.batch_result.failed_items.append(item)
        
        self.logger.warning(
            f"❌ Item failed: {identifier} - {error}",
            extra={
                'identifier': identifier,
                'error': error,
                'session': session_used,
                'operation_type': self.batch_result.operation_type
            }
        )
    
    def record_skip(
        self,
        identifier: str,
        reason: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record skipped item
        
        Args:
            identifier: Item identifier
            reason: Reason for skipping
            data: Additional data
        """
        item = ItemResult(
            identifier=identifier,
            status=ItemStatus.SKIPPED,
            error=reason,
            data=data or {}
        )
        self.batch_result.skipped_items.append(item)
        
        if identifier in self._pending_items:
            del self._pending_items[identifier]
        
        self.logger.info(
            f"⏭️ Item skipped: {identifier} - {reason}",
            extra={
                'identifier': identifier,
                'reason': reason,
                'operation_type': self.batch_result.operation_type
            }
        )
    
    def complete(self) -> BatchResult:
        """
        Mark batch as complete and return results
        
        Returns:
            BatchResult with all statistics
            
        Requirements: 12.4
        """
        self.batch_result.end_time = datetime.now()
        
        # Log any remaining pending items as failed
        for identifier, item in self._pending_items.items():
            item.status = ItemStatus.FAILED
            item.error = "Operation incomplete"
            item.timestamp = datetime.now()
            self.batch_result.failed_items.append(item)
        
        self._pending_items.clear()
        
        # Log summary
        self.logger.info(
            f"📊 Batch operation complete: {self.batch_result.operation_type}",
            extra={
                'operation_type': self.batch_result.operation_type,
                'total': self.batch_result.total_items,
                'success': self.batch_result.success_count,
                'failed': self.batch_result.failure_count,
                'skipped': self.batch_result.skipped_count,
                'success_rate': f"{self.batch_result.success_rate:.1f}%",
                'duration': self.batch_result.duration_seconds
            }
        )
        
        return self.batch_result
    
    def get_current_stats(self) -> Dict[str, int]:
        """
        Get current statistics
        
        Returns:
            Dict with current counts
        """
        return {
            'total': self.batch_result.total_items,
            'success': self.batch_result.success_count,
            'failed': self.batch_result.failure_count,
            'skipped': self.batch_result.skipped_count,
            'pending': len(self._pending_items),
            'completed': self.batch_result.completed_count
        }
    
    def should_continue(self, max_failure_rate: float = 0.5) -> bool:
        """
        Check if batch should continue based on failure rate
        
        Args:
            max_failure_rate: Maximum acceptable failure rate (0.0-1.0)
            
        Returns:
            True if batch should continue, False if too many failures
        """
        completed = self.batch_result.completed_count
        if completed == 0:
            return True
        
        failure_rate = self.batch_result.failure_count / completed
        return failure_rate <= max_failure_rate
    
    def get_detailed_report(self) -> str:
        """
        Generate detailed text report
        
        Returns:
            Formatted report string
        """
        result = self.batch_result
        
        report = f"📊 **نتیجه عملیات {result.operation_type}**\n\n"
        report += f"کل: {result.total_items}\n"
        report += f"✅ موفق: {result.success_count}\n"
        report += f"❌ ناموفق: {result.failure_count}\n"
        
        if result.skipped_count > 0:
            report += f"⏭️ رد شده: {result.skipped_count}\n"
        
        report += f"\n📈 نرخ موفقیت: {result.success_rate:.1f}%\n"
        
        if result.duration_seconds:
            report += f"⏱️ مدت زمان: {result.duration_seconds:.1f} ثانیه\n"
        
        # Add error summary if there are failures
        if result.failure_count > 0:
            report += f"\n**خطاها:**\n"
            errors_by_type = result.get_errors_by_type()
            for error, identifiers in errors_by_type.items():
                report += f"• {error}: {len(identifiers)} مورد\n"
        
        return report
