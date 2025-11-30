"""
Example: Blacklist Management

This example demonstrates how to use the blacklist management API to manually
add, remove, view, and clear blacklisted users. The blacklist feature automatically
prevents sending messages to users who have blocked the system.

Features demonstrated:
- Viewing the current blacklist
- Manually adding users to the blacklist
- Manually removing users from the blacklist
- Clearing the entire blacklist
- Understanding automatic blacklist behavior
"""

import asyncio
import logging
from telegram_manager.manager import TelegramSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_view_blacklist():
    """Example: View current blacklist"""
    logger.info("=" * 60)
    logger.info("Example 1: View Blacklist")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    
    # Load sessions (this also loads the blacklist from storage)
    logger.info("Loading sessions and blacklist...")
    await manager.load_sessions_from_db()
    
    # Get blacklist
    result = await manager.get_blacklist()
    
    if result['success']:
        logger.info(f"\n✅ Blacklist retrieved successfully")
        logger.info(f"Total entries: {result['count']}")
        
        if result['entries']:
            logger.info("\nBlacklisted users:")
            for entry in result['entries']:
                import datetime
                timestamp = datetime.datetime.fromtimestamp(entry['timestamp'])
                logger.info(f"  • User: {entry['user_id']}")
                logger.info(f"    Reason: {entry['reason']}")
                logger.info(f"    Added: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                if entry['session_name']:
                    logger.info(f"    Detected by: {entry['session_name']}")
                logger.info("")
        else:
            logger.info("\n📋 Blacklist is empty")
    else:
        logger.error(f"❌ Failed to retrieve blacklist: {result['error']}")
    
    await manager.shutdown()


async def example_add_to_blacklist():
    """Example: Manually add users to blacklist"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Add Users to Blacklist")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    await manager.load_sessions_from_db()
    
    # Users to add
    users_to_add = [
        ('spam_user123', 'spam'),
        ('abusive_user456', 'abusive_behavior'),
        ('test_user789', 'testing'),
    ]
    
    logger.info(f"\nAdding {len(users_to_add)} users to blacklist...")
    
    for user_id, reason in users_to_add:
        result = await manager.add_to_blacklist(user_id, reason=reason)
        
        if result['success']:
            logger.info(f"  ✅ Added {user_id} (reason: {reason})")
        else:
            logger.error(f"  ❌ Failed to add {user_id}: {result['error']}")
    
    # Verify additions
    logger.info("\nVerifying additions...")
    blacklist_result = await manager.get_blacklist()
    if blacklist_result['success']:
        logger.info(f"Blacklist now has {blacklist_result['count']} entries")
    
    await manager.shutdown()


async def example_remove_from_blacklist():
    """Example: Manually remove users from blacklist"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Remove Users from Blacklist")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    await manager.load_sessions_from_db()
    
    # First, add a user to demonstrate removal
    logger.info("Adding a test user to blacklist...")
    add_result = await manager.add_to_blacklist('temp_user999', reason='temporary_test')
    
    if add_result['success']:
        logger.info(f"  ✅ Added temp_user999")
        
        # Now remove it
        logger.info("\nRemoving temp_user999 from blacklist...")
        remove_result = await manager.remove_from_blacklist('temp_user999')
        
        if remove_result['success']:
            logger.info(f"  ✅ {remove_result['message']}")
        else:
            logger.error(f"  ❌ {remove_result['error']}")
    
    # Try to remove a non-existent user
    logger.info("\nTrying to remove a non-existent user...")
    remove_result = await manager.remove_from_blacklist('nonexistent_user')
    
    if not remove_result['success']:
        logger.info(f"  ℹ️ {remove_result['error']}")
    
    await manager.shutdown()


async def example_clear_blacklist():
    """Example: Clear entire blacklist"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Clear Blacklist")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    await manager.load_sessions_from_db()
    
    # Check current size
    blacklist_result = await manager.get_blacklist()
    if blacklist_result['success']:
        logger.info(f"Current blacklist has {blacklist_result['count']} entries")
    
    # Clear blacklist
    logger.info("\nClearing blacklist...")
    clear_result = await manager.clear_blacklist()
    
    if clear_result['success']:
        logger.info(f"  ✅ {clear_result['message']}")
        logger.info(f"  Removed {clear_result['entries_removed']} entries")
    else:
        logger.error(f"  ❌ Failed to clear blacklist: {clear_result['error']}")
    
    # Verify it's empty
    blacklist_result = await manager.get_blacklist()
    if blacklist_result['success']:
        logger.info(f"\nBlacklist now has {blacklist_result['count']} entries")
    
    await manager.shutdown()


async def example_input_validation():
    """Example: Input validation for blacklist operations"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Input Validation")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    await manager.load_sessions_from_db()
    
    # Test invalid user identifiers
    invalid_users = [
        '',           # Empty string
        'ab',         # Too short
        'a' * 100,    # Too long
    ]
    
    logger.info("Testing invalid user identifiers...")
    
    for invalid_user in invalid_users:
        result = await manager.add_to_blacklist(invalid_user)
        
        if not result['success']:
            logger.info(f"  ✅ Correctly rejected '{invalid_user}': {result['error']}")
        else:
            logger.error(f"  ❌ Should have rejected '{invalid_user}'")
    
    # Test valid user identifiers
    valid_users = [
        'validuser123',
        '123456789',
        'user_with_underscore',
    ]
    
    logger.info("\nTesting valid user identifiers...")
    
    for valid_user in valid_users:
        result = await manager.add_to_blacklist(valid_user, reason='validation_test')
        
        if result['success']:
            logger.info(f"  ✅ Correctly accepted '{valid_user}'")
            # Clean up
            await manager.remove_from_blacklist(valid_user)
        else:
            logger.error(f"  ❌ Should have accepted '{valid_user}': {result['error']}")
    
    await manager.shutdown()


async def example_automatic_blacklisting():
    """Example: Understanding automatic blacklist behavior"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 6: Automatic Blacklisting")
    logger.info("=" * 60)
    
    logger.info("""
How Automatic Blacklisting Works:
==================================

1. DETECTION:
   - When a message delivery fails, the system tracks the failure
   - After 2 consecutive failures to the same user, the system checks if it's a block
   
2. ERROR CLASSIFICATION:
   - Block errors: USER_PRIVACY_RESTRICTED, USER_IS_BLOCKED, PEER_ID_INVALID
   - Temporary errors: FLOOD_WAIT, TIMEOUT, CONNECTION, NETWORK
   - Unknown errors are treated as temporary (to avoid false positives)
   
3. AUTOMATIC ADDITION:
   - If the 2nd failure is classified as a block error, the user is added to blacklist
   - The entry is immediately persisted to storage
   - A log entry is created with timestamp and session information
   
4. FUTURE SENDS:
   - Before attempting any message delivery, the system checks the blacklist
   - If the user is blacklisted, delivery is skipped entirely
   - No session resources are used for blacklisted users
   
5. PERSISTENCE:
   - The blacklist is stored in 'sessions/blacklist.json'
   - It persists across system restarts
   - Failure counts are reset on system restart (fresh start)
   
6. MANUAL MANAGEMENT:
   - You can manually add users (e.g., for spam prevention)
   - You can remove users (e.g., if they unblock you)
   - You can view all entries with metadata
   - You can clear the entire blacklist if needed

Example Scenario:
-----------------
1. Send message to user123 → Fails (network error) → Failure count = 1
2. Send message to user123 → Fails (USER_IS_BLOCKED) → Failure count = 2
3. System detects block error on 2nd failure → Adds user123 to blacklist
4. Future sends to user123 → Skipped (blacklisted)
5. Send message to user456 → Success → Failure count for user456 = 0

Note: Successful delivery resets the failure count for that user.
    """)


async def example_complete_workflow():
    """Example: Complete blacklist management workflow"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 7: Complete Workflow")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager()
    await manager.load_sessions_from_db()
    
    # Step 1: View current blacklist
    logger.info("\n--- Step 1: View Current Blacklist ---")
    result = await manager.get_blacklist()
    logger.info(f"Current entries: {result['count']}")
    
    # Step 2: Add some users
    logger.info("\n--- Step 2: Add Users ---")
    await manager.add_to_blacklist('spam_user1', reason='spam')
    await manager.add_to_blacklist('spam_user2', reason='spam')
    logger.info("Added 2 users")
    
    # Step 3: View updated blacklist
    logger.info("\n--- Step 3: View Updated Blacklist ---")
    result = await manager.get_blacklist()
    logger.info(f"Current entries: {result['count']}")
    for entry in result['entries']:
        logger.info(f"  - {entry['user_id']} ({entry['reason']})")
    
    # Step 4: Send messages (blacklisted users will be skipped)
    logger.info("\n--- Step 4: Send Messages ---")
    recipients = ['spam_user1', 'valid_user1', 'spam_user2', 'valid_user2']
    
    # Note: This would actually send messages if sessions are connected
    # For this example, we'll just show what would happen
    logger.info("Recipients: " + ", ".join(recipients))
    logger.info("Expected behavior:")
    logger.info("  - spam_user1: SKIPPED (blacklisted)")
    logger.info("  - valid_user1: SENT")
    logger.info("  - spam_user2: SKIPPED (blacklisted)")
    logger.info("  - valid_user2: SENT")
    
    # Step 5: Remove a user
    logger.info("\n--- Step 5: Remove User ---")
    await manager.remove_from_blacklist('spam_user1')
    logger.info("Removed spam_user1")
    
    # Step 6: View final blacklist
    logger.info("\n--- Step 6: View Final Blacklist ---")
    result = await manager.get_blacklist()
    logger.info(f"Current entries: {result['count']}")
    for entry in result['entries']:
        logger.info(f"  - {entry['user_id']} ({entry['reason']})")
    
    # Step 7: Clean up (optional)
    logger.info("\n--- Step 7: Clean Up ---")
    await manager.clear_blacklist()
    logger.info("Blacklist cleared")
    
    await manager.shutdown()


async def main():
    """Run all examples"""
    try:
        # Run examples in sequence
        await example_view_blacklist()
        
        # Uncomment to run other examples:
        # await example_add_to_blacklist()
        # await example_remove_from_blacklist()
        # await example_clear_blacklist()
        # await example_input_validation()
        # await example_automatic_blacklisting()
        # await example_complete_workflow()
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == '__main__':
    asyncio.run(main())
