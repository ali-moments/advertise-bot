"""
LoadBalancer class - Session selection strategies for load distribution
"""

import logging
from typing import Dict, Optional
from enum import Enum


class LoadBalancingStrategy(Enum):
    """Load balancing strategy options"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"


class LoadBalancer:
    """
    Manages session selection using configurable load balancing strategies
    
    Supports two strategies:
    - Round-robin: Distributes operations evenly across sessions in rotation
    - Least-loaded: Selects the session with minimum active operations
    
    For least-loaded strategy, ties are broken using round-robin.
    """
    
    def __init__(self, strategy: str = "round_robin"):
        """
        Initialize load balancer
        
        Args:
            strategy: Load balancing strategy ('round_robin' or 'least_loaded')
        """
        self.strategy = strategy
        self.round_robin_index = 0
        self.logger = logging.getLogger("LoadBalancer")
        
        # Validate strategy
        valid_strategies = [s.value for s in LoadBalancingStrategy]
        if strategy not in valid_strategies:
            self.logger.warning(
                f"Invalid strategy '{strategy}', defaulting to 'round_robin'. "
                f"Valid strategies: {valid_strategies}"
            )
            self.strategy = LoadBalancingStrategy.ROUND_ROBIN.value
    
    def set_strategy(self, strategy: str):
        """
        Change the load balancing strategy at runtime
        
        Args:
            strategy: New strategy ('round_robin' or 'least_loaded')
        """
        valid_strategies = [s.value for s in LoadBalancingStrategy]
        if strategy not in valid_strategies:
            self.logger.warning(
                f"Invalid strategy '{strategy}', keeping current strategy '{self.strategy}'. "
                f"Valid strategies: {valid_strategies}"
            )
            return
        
        old_strategy = self.strategy
        self.strategy = strategy
        self.logger.info(f"Load balancing strategy changed from '{old_strategy}' to '{strategy}'")
    
    def get_strategy(self) -> str:
        """
        Get the current load balancing strategy
        
        Returns:
            Current strategy name
        """
        return self.strategy
    
    def select_session(
        self,
        sessions: Dict,
        session_loads: Dict[str, int]
    ) -> Optional[str]:
        """
        Select a session based on the configured strategy
        
        Args:
            sessions: Dict mapping session names to TelegramSession objects
            session_loads: Dict mapping session names to active operation counts
            
        Returns:
            Selected session name or None if no sessions available
        """
        if not sessions:
            return None
        
        if self.strategy == LoadBalancingStrategy.LEAST_LOADED.value:
            return self._select_least_loaded(sessions, session_loads)
        else:
            # Default to round-robin
            return self._select_round_robin(sessions)
    
    def _select_round_robin(self, sessions: Dict) -> Optional[str]:
        """
        Select next available session using round-robin strategy
        
        Args:
            sessions: Dict mapping session names to TelegramSession objects
            
        Returns:
            Session name or None if no connected sessions available
        """
        if not sessions:
            return None
        
        session_names = list(sessions.keys())
        attempts = 0
        
        # Try to find a connected session
        while attempts < len(session_names):
            # Get next session in round-robin order
            session_name = session_names[self.round_robin_index % len(session_names)]
            self.round_robin_index += 1
            
            # Check if session is connected
            session = sessions[session_name]
            if session.is_connected:
                # Enhanced logging for load balancing decisions (Requirement 13.4)
                self.logger.debug(
                    f"🔄 Round-robin selected: {session_name}",
                    extra={
                        'load_balancing_strategy': 'round_robin',
                        'selected_session': session_name,
                        'round_robin_index': self.round_robin_index - 1,
                        'total_sessions': len(session_names),
                        'attempts': attempts + 1
                    }
                )
                return session_name
            
            attempts += 1
        
        # No connected sessions found
        self.logger.warning("⚠️ No connected sessions available for round-robin selection")
        return None
    
    def _select_least_loaded(
        self,
        sessions: Dict,
        session_loads: Dict[str, int]
    ) -> Optional[str]:
        """
        Select session with minimum active operations
        Break ties using round-robin
        
        Args:
            sessions: Dict mapping session names to TelegramSession objects
            session_loads: Dict mapping session names to active operation counts
            
        Returns:
            Session name or None if no connected sessions available
        """
        if not sessions:
            return None
        
        # Find connected sessions with their loads
        connected_sessions = []
        for session_name, session in sessions.items():
            if session.is_connected:
                load = session_loads.get(session_name, 0)
                connected_sessions.append((session_name, load))
        
        if not connected_sessions:
            self.logger.warning("⚠️ No connected sessions available for least-loaded selection")
            return None
        
        # Find minimum load
        min_load = min(load for _, load in connected_sessions)
        
        # Get all sessions with minimum load
        least_loaded = [name for name, load in connected_sessions if load == min_load]
        
        # If multiple sessions have same load, use round-robin to break tie
        if len(least_loaded) > 1:
            selected = least_loaded[self.round_robin_index % len(least_loaded)]
            self.round_robin_index += 1
            # Enhanced logging for load balancing decisions (Requirement 13.4)
            self.logger.debug(
                f"⚖️ Least-loaded selected (tie-break): {selected} (load: {min_load})",
                extra={
                    'load_balancing_strategy': 'least_loaded',
                    'selected_session': selected,
                    'session_load': min_load,
                    'tied_sessions': len(least_loaded),
                    'tie_break_method': 'round_robin',
                    'all_session_loads': {name: load for name, load in connected_sessions}
                }
            )
        else:
            selected = least_loaded[0]
            # Enhanced logging for load balancing decisions (Requirement 13.4)
            self.logger.debug(
                f"⚖️ Least-loaded selected: {selected} (load: {min_load})",
                extra={
                    'load_balancing_strategy': 'least_loaded',
                    'selected_session': selected,
                    'session_load': min_load,
                    'all_session_loads': {name: load for name, load in connected_sessions}
                }
            )
        
        return selected
