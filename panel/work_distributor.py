"""
Work Distributor - Distributes batch operations across available sessions

This module handles:
- Work distribution across sessions for batch operations
- Dynamic load balancing during execution
- Session availability tracking

Requirements: 12.3 - Work distribution across available sessions
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class WorkItem:
    """Represents a single work item in a batch operation"""
    identifier: str  # Group ID, recipient, etc.
    data: Dict[str, Any] = field(default_factory=dict)  # Additional data for the work item
    assigned_session: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class WorkBatch:
    """Represents a batch of work items assigned to a session"""
    session_name: str
    items: List[WorkItem]
    
    def __len__(self):
        return len(self.items)


class WorkDistributor:
    """
    Distributes work items across available sessions for optimal performance
    
    Supports:
    - Even distribution across sessions
    - Dynamic rebalancing when sessions become unavailable
    - Load-aware distribution
    
    Requirements: 12.3
    """
    
    def __init__(self):
        """Initialize work distributor"""
        self.logger = logging.getLogger("WorkDistributor")
    
    def distribute_work(
        self,
        items: List[str],
        available_sessions: List[str],
        session_loads: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[str]]:
        """
        Distribute work items across available sessions
        
        Args:
            items: List of work item identifiers (groups, recipients, etc.)
            available_sessions: List of available session names
            session_loads: Optional dict of current session loads
            
        Returns:
            Dict mapping session names to lists of work items
            
        Requirements: 12.3
        """
        if not available_sessions:
            self.logger.error("❌ No available sessions for work distribution")
            return {}
        
        if not items:
            self.logger.warning("⚠️ No work items to distribute")
            return {session: [] for session in available_sessions}
        
        # Initialize distribution
        distribution: Dict[str, List[str]] = {
            session: [] for session in available_sessions
        }
        
        # If session loads provided, use load-aware distribution
        if session_loads:
            distribution = self._distribute_load_aware(
                items, available_sessions, session_loads
            )
        else:
            # Use round-robin distribution
            distribution = self._distribute_round_robin(
                items, available_sessions
            )
        
        # Log distribution summary
        self.logger.info(
            f"📊 Distributed {len(items)} items across {len(available_sessions)} sessions",
            extra={
                'total_items': len(items),
                'session_count': len(available_sessions),
                'distribution': {
                    session: len(items_list)
                    for session, items_list in distribution.items()
                }
            }
        )
        
        return distribution
    
    def _distribute_round_robin(
        self,
        items: List[str],
        sessions: List[str]
    ) -> Dict[str, List[str]]:
        """
        Distribute items using round-robin strategy
        
        Args:
            items: List of work items
            sessions: List of session names
            
        Returns:
            Dict mapping sessions to work items
        """
        distribution: Dict[str, List[str]] = {
            session: [] for session in sessions
        }
        
        for idx, item in enumerate(items):
            session = sessions[idx % len(sessions)]
            distribution[session].append(item)
        
        return distribution
    
    def _distribute_load_aware(
        self,
        items: List[str],
        sessions: List[str],
        session_loads: Dict[str, int]
    ) -> Dict[str, List[str]]:
        """
        Distribute items based on current session loads
        
        Assigns more work to sessions with lower loads.
        
        Args:
            items: List of work items
            sessions: List of session names
            session_loads: Current load per session
            
        Returns:
            Dict mapping sessions to work items
        """
        distribution: Dict[str, List[str]] = {
            session: [] for session in sessions
        }
        
        # Sort sessions by load (ascending)
        sorted_sessions = sorted(
            sessions,
            key=lambda s: session_loads.get(s, 0)
        )
        
        # Distribute items, preferring less loaded sessions
        for idx, item in enumerate(items):
            # Use round-robin on sorted sessions
            session = sorted_sessions[idx % len(sorted_sessions)]
            distribution[session].append(item)
        
        return distribution
    
    def redistribute_failed_work(
        self,
        failed_items: List[str],
        failed_session: str,
        available_sessions: List[str],
        session_loads: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[str]]:
        """
        Redistribute work items from a failed session to other sessions
        
        Args:
            failed_items: Items that failed on the original session
            failed_session: Name of the session that failed
            available_sessions: List of currently available sessions
            session_loads: Optional current session loads
            
        Returns:
            Dict mapping sessions to redistributed work items
            
        Requirements: 12.3
        """
        # Remove failed session from available sessions
        available = [s for s in available_sessions if s != failed_session]
        
        if not available:
            self.logger.error(
                f"❌ Cannot redistribute work from {failed_session}: no other sessions available"
            )
            return {}
        
        self.logger.info(
            f"🔄 Redistributing {len(failed_items)} items from {failed_session} "
            f"to {len(available)} available sessions"
        )
        
        # Distribute to remaining sessions
        return self.distribute_work(failed_items, available, session_loads)
    
    def create_work_batches(
        self,
        items: List[str],
        available_sessions: List[str],
        session_loads: Optional[Dict[str, int]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> List[WorkBatch]:
        """
        Create work batches with WorkItem objects
        
        Args:
            items: List of work item identifiers
            available_sessions: List of available session names
            session_loads: Optional current session loads
            additional_data: Optional additional data to attach to work items
            
        Returns:
            List of WorkBatch objects
        """
        distribution = self.distribute_work(items, available_sessions, session_loads)
        
        batches = []
        for session_name, session_items in distribution.items():
            work_items = []
            for item_id in session_items:
                work_item = WorkItem(
                    identifier=item_id,
                    data=additional_data.get(item_id, {}) if additional_data else {},
                    assigned_session=session_name
                )
                work_items.append(work_item)
            
            if work_items:
                batch = WorkBatch(
                    session_name=session_name,
                    items=work_items
                )
                batches.append(batch)
        
        return batches
    
    def balance_distribution(
        self,
        current_distribution: Dict[str, List[str]],
        session_loads: Dict[str, int],
        threshold: float = 0.3
    ) -> Tuple[Dict[str, List[str]], bool]:
        """
        Check if distribution is balanced and rebalance if needed
        
        Args:
            current_distribution: Current work distribution
            session_loads: Current session loads
            threshold: Imbalance threshold (0.3 = 30% difference)
            
        Returns:
            Tuple of (new_distribution, was_rebalanced)
        """
        if not current_distribution or len(current_distribution) < 2:
            return current_distribution, False
        
        # Calculate load per session (current + assigned work)
        total_loads = {}
        for session, items in current_distribution.items():
            current_load = session_loads.get(session, 0)
            total_loads[session] = current_load + len(items)
        
        # Check if rebalancing is needed
        max_load = max(total_loads.values())
        min_load = min(total_loads.values())
        
        if max_load == 0:
            return current_distribution, False
        
        imbalance = (max_load - min_load) / max_load
        
        if imbalance <= threshold:
            # Distribution is balanced
            return current_distribution, False
        
        self.logger.info(
            f"⚖️ Rebalancing distribution (imbalance: {imbalance:.2%})"
        )
        
        # Collect all items
        all_items = []
        for items in current_distribution.values():
            all_items.extend(items)
        
        # Redistribute with load awareness
        new_distribution = self._distribute_load_aware(
            all_items,
            list(current_distribution.keys()),
            session_loads
        )
        
        return new_distribution, True
