"""
Example: Reaction Pool Management

This example demonstrates how to configure and manage reaction pools for monitoring targets.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_manager.main import TelegramManagerApp


async def main():
    """Main example function"""
    
    # Initialize the app
    app = TelegramManagerApp()
    
    print("🚀 Initializing Telegram Manager...")
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize application")
        return
    
    print(f"✅ Initialized with {len(app.manager.sessions)} sessions\n")
    
    # Example 1: Configure a new reaction pool
    print("=" * 60)
    print("Example 1: Configure Reaction Pool")
    print("=" * 60)
    
    chat_id = "@example_channel"
    reactions = [
        {'emoji': '👍', 'weight': 2},  # 2x more likely
        {'emoji': '❤️', 'weight': 1},
        {'emoji': '🔥', 'weight': 1},
        {'emoji': '👏', 'weight': 1}
    ]
    
    result = await app.configure_reaction_pool(
        chat_id=chat_id,
        reactions=reactions,
        cooldown=2.0
    )
    
    print(f"Configure result: {result}\n")
    
    # Example 2: Update an existing reaction pool
    print("=" * 60)
    print("Example 2: Update Reaction Pool")
    print("=" * 60)
    
    new_reactions = [
        {'emoji': '😊', 'weight': 1},
        {'emoji': '🎉', 'weight': 1},
        {'emoji': '💯', 'weight': 3}  # 3x more likely
    ]
    
    result = await app.update_reaction_pool(
        chat_id=chat_id,
        reactions=new_reactions
    )
    
    print(f"Update result: {result}\n")
    
    # Example 3: Get all reaction pools
    print("=" * 60)
    print("Example 3: Get All Reaction Pools")
    print("=" * 60)
    
    pools = await app.get_reaction_pools()
    
    print(f"Found {len(pools)} configured reaction pools:")
    for chat_id, config in pools.items():
        print(f"\n  Chat: {chat_id}")
        print(f"  Cooldown: {config['cooldown']}s")
        print(f"  Reactions:")
        for reaction in config['reactions']:
            print(f"    - {reaction['emoji']} (weight: {reaction['weight']})")
    
    print()
    
    # Example 4: Migrate single reaction to pool
    print("=" * 60)
    print("Example 4: Migrate Single Reactions to Pools")
    print("=" * 60)
    
    # First, let's add a target with single reaction for demonstration
    app.monitoring_targets.append({
        'chat_id': '@old_channel',
        'reaction': '👍',
        'cooldown': 2.0
    })
    
    print("Added legacy target with single reaction: @old_channel -> 👍")
    
    # Now migrate it
    result = app.migrate_single_reaction_to_pool()
    
    print(f"\nMigration result:")
    print(f"  Migrated: {result['migrated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {len(result['errors'])}")
    
    if result['errors']:
        for error in result['errors']:
            print(f"    - {error}")
    
    # Show the migrated configuration
    pools = await app.get_reaction_pools()
    if '@old_channel' in pools:
        print(f"\n  Migrated @old_channel configuration:")
        print(f"    Reactions: {pools['@old_channel']['reactions']}")
    
    print()
    
    # Example 5: Error handling - invalid reactions
    print("=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)
    
    # Try to configure with empty reaction list
    result = await app.configure_reaction_pool(
        chat_id="@test_channel",
        reactions=[],
        cooldown=2.0
    )
    print(f"Empty reactions result: {result}")
    
    # Try to configure with invalid weight
    result = await app.configure_reaction_pool(
        chat_id="@test_channel",
        reactions=[{'emoji': '👍', 'weight': 0}],  # Invalid: weight must be >= 1
        cooldown=2.0
    )
    print(f"Invalid weight result: {result}")
    
    # Try to update non-existent target
    result = await app.update_reaction_pool(
        chat_id="@nonexistent_channel",
        reactions=[{'emoji': '👍', 'weight': 1}]
    )
    print(f"Non-existent target result: {result}")
    
    print()
    
    # Cleanup
    print("=" * 60)
    print("Shutting down...")
    print("=" * 60)
    await app.shutdown()
    print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
