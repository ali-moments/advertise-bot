"""
Example: Bulk Message Sending with Load Balancing and Blacklist Management

This example demonstrates how to use the bulk message sending functionality
to send text and media messages to multiple recipients with automatic load
balancing across sessions. It also shows how the blacklist feature automatically
prevents sending to users who have blocked the system.
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


async def example_text_messages():
    """Example: Send text messages to multiple recipients"""
    logger.info("=" * 60)
    logger.info("Example 1: Bulk Text Message Sending")
    logger.info("=" * 60)
    
    # Initialize manager with load balancing strategy
    manager = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy="least_loaded"  # or "round_robin"
    )
    
    # Load sessions from database
    logger.info("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    logger.info(f"Loaded {sum(load_results.values())} sessions successfully")
    
    if not any(load_results.values()):
        logger.error("No sessions loaded, cannot proceed")
        return
    
    # Define recipients
    recipients = [
        'user123456',      # User ID
        'username1',       # Username
        'another_user',    # Another username
        # Add more recipients as needed
    ]
    
    # Message to send
    message = """
Hello! This is a test message sent via the bulk messaging system.

This message was sent using load-balanced session distribution.
    """.strip()
    
    # Send messages with automatic load balancing
    logger.info(f"Sending messages to {len(recipients)} recipients...")
    results = await manager.send_text_messages_bulk(
        recipients=recipients,
        message=message,
        delay=2.0,  # 2 second delay between sends within each session
        skip_invalid=True  # Skip invalid recipients instead of failing
    )
    
    # Process results
    logger.info("\n" + "=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    
    succeeded = sum(1 for r in results.values() if r.success)
    failed = len(results) - succeeded
    
    logger.info(f"Total: {len(results)}")
    logger.info(f"Succeeded: {succeeded}")
    logger.info(f"Failed: {failed}")
    
    # Show detailed results
    logger.info("\nDetailed Results:")
    for recipient, result in results.items():
        if result.success:
            logger.info(f"  ✅ {recipient} (via {result.session_used})")
        else:
            logger.error(f"  ❌ {recipient}: {result.error}")
    
    # Shutdown
    await manager.shutdown()


async def example_media_messages():
    """Example: Send media messages to multiple recipients"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Bulk Media Message Sending")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy="round_robin"
    )
    
    # Load sessions
    logger.info("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    logger.info(f"Loaded {sum(load_results.values())} sessions successfully")
    
    if not any(load_results.values()):
        logger.error("No sessions loaded, cannot proceed")
        return
    
    # Define recipients
    recipients = [
        'user123456',
        'username1',
        'another_user',
    ]
    
    # Path to media file (replace with actual path)
    image_path = '/path/to/your/image.jpg'
    caption = "Check out this image! 📸"
    
    # Send media messages
    logger.info(f"Sending images to {len(recipients)} recipients...")
    results = await manager.send_media_messages_bulk(
        recipients=recipients,
        media_path=image_path,
        media_type='image',  # 'image', 'video', or 'document'
        caption=caption,
        delay=2.0,
        skip_invalid=True
    )
    
    # Process results
    logger.info("\n" + "=" * 60)
    logger.info("Results Summary")
    logger.info("=" * 60)
    
    succeeded = sum(1 for r in results.values() if r.success)
    failed = len(results) - succeeded
    
    logger.info(f"Total: {len(results)}")
    logger.info(f"Succeeded: {succeeded}")
    logger.info(f"Failed: {failed}")
    
    # Show detailed results
    logger.info("\nDetailed Results:")
    for recipient, result in results.items():
        if result.success:
            logger.info(f"  ✅ {recipient} (via {result.session_used})")
        else:
            logger.error(f"  ❌ {recipient}: {result.error}")
    
    # Shutdown
    await manager.shutdown()


async def example_mixed_recipients():
    """Example: Handle mixed valid and invalid recipients"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Handling Invalid Recipients")
    logger.info("=" * 60)
    
    # Initialize manager
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Load sessions
    logger.info("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    logger.info(f"Loaded {sum(load_results.values())} sessions successfully")
    
    if not any(load_results.values()):
        logger.error("No sessions loaded, cannot proceed")
        return
    
    # Mix of valid and invalid recipients
    recipients = [
        'validuser123',    # Valid
        'inv',             # Invalid (too short)
        'another_valid',   # Valid
        '',                # Invalid (empty)
        '12345678',        # Valid (user ID)
    ]
    
    message = "Test message with mixed recipients"
    
    # Send with skip_invalid=True (default)
    logger.info("Sending with skip_invalid=True...")
    results = await manager.send_text_messages_bulk(
        recipients=recipients,
        message=message,
        delay=1.0,
        skip_invalid=True  # Skip invalid, continue with valid
    )
    
    # Show results
    logger.info("\nResults:")
    for recipient, result in results.items():
        status = "✅" if result.success else "❌"
        logger.info(f"  {status} {recipient}: {result.error or 'Success'}")
    
    # Shutdown
    await manager.shutdown()


async def example_load_balancing_strategies():
    """Example: Compare different load balancing strategies"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Load Balancing Strategies")
    logger.info("=" * 60)
    
    # Test with round-robin
    logger.info("\n--- Testing Round-Robin Strategy ---")
    manager_rr = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy="round_robin"
    )
    
    await manager_rr.load_sessions_from_db()
    
    recipients = [f'user{i}' for i in range(10)]
    message = "Round-robin test"
    
    results_rr = await manager_rr.send_text_messages_bulk(
        recipients=recipients,
        message=message,
        delay=0.5
    )
    
    # Show session distribution
    session_counts = {}
    for result in results_rr.values():
        session = result.session_used
        session_counts[session] = session_counts.get(session, 0) + 1
    
    logger.info("Session distribution (round-robin):")
    for session, count in session_counts.items():
        logger.info(f"  {session}: {count} messages")
    
    await manager_rr.shutdown()
    
    # Test with least-loaded
    logger.info("\n--- Testing Least-Loaded Strategy ---")
    manager_ll = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy="least_loaded"
    )
    
    await manager_ll.load_sessions_from_db()
    
    results_ll = await manager_ll.send_text_messages_bulk(
        recipients=recipients,
        message=message,
        delay=0.5
    )
    
    # Show session distribution
    session_counts = {}
    for result in results_ll.values():
        session = result.session_used
        session_counts[session] = session_counts.get(session, 0) + 1
    
    logger.info("Session distribution (least-loaded):")
    for session, count in session_counts.items():
        logger.info(f"  {session}: {count} messages")
    
    await manager_ll.shutdown()


async def example_blacklist_integration():
    """Example: Automatic blacklist integration during bulk sending"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Blacklist Integration")
    logger.info("=" * 60)
    
    # Initialize manager with blacklist enabled (default)
    manager = TelegramSessionManager(max_concurrent_operations=3)
    
    # Load sessions
    logger.info("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    logger.info(f"Loaded {sum(load_results.values())} sessions successfully")
    
    if not any(load_results.values()):
        logger.error("No sessions loaded, cannot proceed")
        return
    
    # Define recipients (some may be blacklisted)
    recipients = [
        'user123456',
        'blocked_user1',  # This user might be blacklisted
        'another_user',
        'blocked_user2',  # This user might be blacklisted
    ]
    
    message = "Test message with blacklist checking"
    
    # Check current blacklist status
    logger.info("\n--- Checking Blacklist Status ---")
    blacklist_result = await manager.get_blacklist()
    if blacklist_result['success']:
        logger.info(f"Current blacklist has {blacklist_result['count']} entries")
        for entry in blacklist_result['entries']:
            logger.info(f"  - {entry['user_id']} (added: {entry['timestamp']}, reason: {entry['reason']})")
    
    # Send messages - blacklisted users will be automatically skipped
    logger.info("\n--- Sending Messages ---")
    logger.info("The system will automatically skip any blacklisted users...")
    results = await manager.send_text_messages_bulk(
        recipients=recipients,
        message=message,
        delay=1.0
    )
    
    # Show results with blacklist information
    logger.info("\n--- Results ---")
    for recipient, result in results.items():
        if result.blacklisted:
            logger.info(f"  ⏭️ {recipient}: SKIPPED (blacklisted)")
        elif result.success:
            logger.info(f"  ✅ {recipient}: SUCCESS (via {result.session_used})")
        else:
            logger.info(f"  ❌ {recipient}: FAILED ({result.error})")
    
    # Note: If a user blocks us during sending, after 2 consecutive failures,
    # they will be automatically added to the blacklist and future sends will be skipped
    
    logger.info("\n--- Blacklist Feature Notes ---")
    logger.info("• Users are automatically blacklisted after 2 consecutive delivery failures")
    logger.info("• Blacklisted users are skipped before attempting delivery")
    logger.info("• The blacklist persists across system restarts")
    logger.info("• You can manually manage the blacklist using the API (see blacklist_management_example.py)")
    
    # Shutdown
    await manager.shutdown()


async def main():
    """Run all examples"""
    try:
        # Run examples
        await example_text_messages()
        
        # Uncomment to run other examples:
        # await example_media_messages()
        # await example_mixed_recipients()
        # await example_load_balancing_strategies()
        # await example_blacklist_integration()
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == '__main__':
    asyncio.run(main())
