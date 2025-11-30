"""
Example: Using ReactionPool for monitoring with multiple reactions

This example demonstrates how to configure monitoring with multiple reactions
that are randomly selected with configurable weights.
"""

import asyncio
from telegram_manager.session import TelegramSession
from telegram_manager.models import ReactionPool, ReactionConfig


async def example_reaction_pool_monitoring():
    """Example of monitoring with reaction pool"""
    
    # Create a session
    session = TelegramSession(
        session_file='example.session',
        api_id=12345,
        api_hash='your_api_hash'
    )
    
    # Connect to Telegram
    await session.connect()
    
    # Example 1: Monitoring with multiple reactions (equal weights)
    targets_equal_weights = [{
        'chat_id': '@example_channel',
        'reaction_pool': {
            'reactions': [
                {'emoji': '👍', 'weight': 1},
                {'emoji': '❤️', 'weight': 1},
                {'emoji': '🔥', 'weight': 1},
                {'emoji': '👏', 'weight': 1}
            ]
        },
        'cooldown': 2.0
    }]
    
    # Example 2: Monitoring with weighted reactions
    # This will use ❤️ 50% of the time, 👍 30%, and 🔥 20%
    targets_weighted = [{
        'chat_id': '@another_channel',
        'reaction_pool': {
            'reactions': [
                {'emoji': '❤️', 'weight': 5},  # 50% (5/10)
                {'emoji': '👍', 'weight': 3},  # 30% (3/10)
                {'emoji': '🔥', 'weight': 2}   # 20% (2/10)
            ]
        },
        'cooldown': 2.0
    }]
    
    # Example 3: Backward compatibility - single reaction (old style)
    targets_single_reaction = [{
        'chat_id': '@legacy_channel',
        'reaction': '👍',  # Old-style single reaction
        'cooldown': 2.0
    }]
    
    # Start monitoring with reaction pool
    print("Starting monitoring with reaction pool...")
    await session.start_monitoring(targets_weighted)
    
    # The session will now:
    # 1. Monitor the specified channels
    # 2. For each new message, randomly select a reaction from the pool
    # 3. Use weighted selection (❤️ appears more often than others)
    # 4. Log which reaction was selected
    
    # Keep monitoring for a while
    print("Monitoring active. Press Ctrl+C to stop.")
    try:
        await asyncio.sleep(3600)  # Monitor for 1 hour
    except KeyboardInterrupt:
        print("Stopping monitoring...")
    
    # Stop monitoring and disconnect
    await session.stop_monitoring()
    await session.disconnect()


async def example_programmatic_reaction_pool():
    """Example of creating ReactionPool programmatically"""
    
    # Create a reaction pool with Python objects
    reaction_pool = ReactionPool(reactions=[
        ReactionConfig(emoji='👍', weight=1),
        ReactionConfig(emoji='❤️', weight=2),
        ReactionConfig(emoji='🔥', weight=1)
    ])
    
    # Test the selection
    print("Testing weighted random selection:")
    reactions = [reaction_pool.select_random() for _ in range(20)]
    print(f"Selected reactions: {reactions}")
    
    # Count occurrences
    from collections import Counter
    counts = Counter(reactions)
    print(f"Distribution: {dict(counts)}")
    print("Note: ❤️ should appear roughly twice as often as others")


async def example_updating_reaction_pool():
    """Example of updating reaction pool for an active monitoring target"""
    
    session = TelegramSession(
        session_file='example.session',
        api_id=12345,
        api_hash='your_api_hash'
    )
    
    await session.connect()
    
    # Start with initial reaction pool
    initial_targets = [{
        'chat_id': '@example_channel',
        'reaction_pool': {
            'reactions': [
                {'emoji': '👍', 'weight': 1}
            ]
        },
        'cooldown': 2.0
    }]
    
    await session.start_monitoring(initial_targets)
    print("Monitoring started with 👍 only")
    
    # Wait a bit
    await asyncio.sleep(10)
    
    # Update to use multiple reactions
    updated_targets = [{
        'chat_id': '@example_channel',
        'reaction_pool': {
            'reactions': [
                {'emoji': '👍', 'weight': 1},
                {'emoji': '❤️', 'weight': 2},
                {'emoji': '🔥', 'weight': 1}
            ]
        },
        'cooldown': 2.0
    }]
    
    # Restart monitoring with new pool
    await session.start_monitoring(updated_targets)
    print("Monitoring updated with multiple reactions")
    
    # Continue monitoring
    await asyncio.sleep(30)
    
    await session.stop_monitoring()
    await session.disconnect()


if __name__ == '__main__':
    # Run the examples
    print("Example 1: Basic reaction pool monitoring")
    # asyncio.run(example_reaction_pool_monitoring())
    
    print("\nExample 2: Programmatic reaction pool")
    asyncio.run(example_programmatic_reaction_pool())
    
    print("\nExample 3: Updating reaction pool")
    # asyncio.run(example_updating_reaction_pool())
