"""
Example demonstrating load balancing strategies in TelegramSessionManager

This example shows:
1. Creating a manager with a specific load balancing strategy
2. Changing the strategy at runtime
3. How different strategies select sessions
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_manager import TelegramSessionManager, LoadBalancingStrategy


async def main():
    print("=" * 60)
    print("Load Balancing Strategy Example")
    print("=" * 60)
    
    # Create manager with round-robin strategy (default)
    print("\n1. Creating manager with default round-robin strategy...")
    manager = TelegramSessionManager(max_concurrent_operations=10)
    print(f"   Current strategy: {manager.get_load_balancing_strategy()}")
    
    # Change to least-loaded strategy
    print("\n2. Changing to least-loaded strategy...")
    manager.set_load_balancing_strategy("least_loaded")
    print(f"   Current strategy: {manager.get_load_balancing_strategy()}")
    
    # Change back to round-robin
    print("\n3. Changing back to round-robin strategy...")
    manager.set_load_balancing_strategy("round_robin")
    print(f"   Current strategy: {manager.get_load_balancing_strategy()}")
    
    # Try invalid strategy (should be ignored)
    print("\n4. Trying to set invalid strategy...")
    manager.set_load_balancing_strategy("invalid_strategy")
    print(f"   Current strategy (unchanged): {manager.get_load_balancing_strategy()}")
    
    # Create manager with specific strategy at initialization
    print("\n5. Creating manager with least-loaded strategy at initialization...")
    manager2 = TelegramSessionManager(
        max_concurrent_operations=10,
        load_balancing_strategy="least_loaded"
    )
    print(f"   Current strategy: {manager2.get_load_balancing_strategy()}")
    
    print("\n" + "=" * 60)
    print("Strategy Options:")
    print("  - round_robin: Distributes operations evenly in rotation")
    print("  - least_loaded: Selects session with minimum active operations")
    print("  - For least_loaded, ties are broken using round-robin")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
