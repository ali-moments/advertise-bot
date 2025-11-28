"""
Telegram Manager - Complete Examples and Testing Script

This file demonstrates all features of the Telegram Manager system.
Fill in the 'data' dictionary with real values to test with actual data.
"""

import asyncio
import logging
from telegram_manager.main import TelegramManagerApp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============================================================================
# DATA CONFIGURATION - Fill this with your real data for testing
# ============================================================================

data = {
    # Monitoring targets - channels/groups to monitor and react to
    'monitoring_targets': [
        {
            'chat_id': '@example_channel',  # Replace with actual channel username
            'reaction': '👍',
            'cooldown': 2.0
        },
        # Add more monitoring targets here
    ],
    
    # Message sending targets
    'message_targets': [
        '@user1',  # Replace with actual usernames or chat IDs
        '@user2',
        # Add more targets here
    ],
    
    # Message to send
    'test_message': 'Hello! This is a test message from Telegram Manager.',
    
    # Groups/channels to get members from
    'member_chats': [
        '@example_group',  # Replace with actual group usernames
        # Add more groups here
    ],
    
    # Groups/channels to join
    'chats_to_join': [
        'https://t.me/example_group',  # Replace with actual invite links
        # Add more groups here
    ],
    
    # Groups to scrape members from
    'groups_to_scrape': [
        '@example_group',  # Replace with actual group identifiers
        'https://t.me/+AbCdEfGhIjKlMnOp',  # Private group invite link
        # Add more groups here
    ],
    
    # Link channels (لینک دونی) - channels that share group links
    'link_channels': [
        '@link_sharing_channel',  # Replace with actual link-sharing channels
        # Add more channels here
    ],
    
    # Targets to check type (scrapable or not)
    'targets_to_check': [
        '@example_channel',
        '@example_group',
        'https://t.me/example',
        # Add more targets here
    ],
}

# ============================================================================
# EXAMPLE FUNCTIONS - Demonstrating all features
# ============================================================================

async def example_1_initialize_and_load_sessions():
    """
    Example 1: Initialize the application and load sessions from database
    
    Features demonstrated:
    - Initialize TelegramManagerApp
    - Load sessions from database
    - Get session statistics
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Initialize and Load Sessions")
    print("="*80)
    
    app = TelegramManagerApp()
    
    # Initialize from database
    success = await app.initialize()
    
    if success:
        print("✅ Application initialized successfully")
        
        # Show session stats
        await app.show_stats()
    else:
        print("❌ Failed to initialize application")
    
    return app


async def example_2_monitoring(app: TelegramManagerApp):
    """
    Example 2: Start and stop monitoring on channels/groups
    
    Features demonstrated:
    - Start global monitoring across all sessions
    - Monitor multiple targets with different reactions
    - Stop monitoring
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Monitoring Channels/Groups")
    print("="*80)
    
    if not data['monitoring_targets']:
        print("⚠️  No monitoring targets configured in data dict")
        return
    
    # Start monitoring
    print(f"Starting monitoring on {len(data['monitoring_targets'])} targets...")
    await app.start_monitoring()
    
    # Let it run for a while
    print("Monitoring active for 30 seconds...")
    await asyncio.sleep(30)
    
    # Stop monitoring
    print("Stopping monitoring...")
    await app.stop_monitoring()
    print("✅ Monitoring stopped")


async def example_3_send_bulk_messages(app: TelegramManagerApp):
    """
    Example 3: Send messages to multiple targets
    
    Features demonstrated:
    - Bulk message sending
    - Load balancing across sessions
    - Result tracking
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Send Bulk Messages")
    print("="*80)
    
    if not data['message_targets']:
        print("⚠️  No message targets configured in data dict")
        return
    
    results = await app.send_bulk_messages(
        targets=data['message_targets'],
        message=data['test_message']
    )
    
    print(f"\n📊 Results:")
    for target, result in results.items():
        status = "✅" if result['success'] else "❌"
        print(f"{status} {target}: {result.get('error', 'Success')}")


async def example_4_get_chat_members(app: TelegramManagerApp):
    """
    Example 4: Get member lists from chats
    
    Features demonstrated:
    - Bulk member retrieval
    - Session distribution
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Get Chat Members")
    print("="*80)
    
    if not data['member_chats']:
        print("⚠️  No member chats configured in data dict")
        return
    
    members_data = await app.get_chat_members(
        chats=data['member_chats'],
        limit=100
    )
    
    print(f"\n📊 Results:")
    for chat, members in members_data.items():
        print(f"👥 {chat}: {len(members)} members")


async def example_5_join_chats(app: TelegramManagerApp):
    """
    Example 5: Join multiple chats/groups
    
    Features demonstrated:
    - Bulk chat joining
    - Handle invite links
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: Join Multiple Chats")
    print("="*80)
    
    if not data['chats_to_join']:
        print("⚠️  No chats to join configured in data dict")
        return
    
    results = await app.join_multiple_chats(data['chats_to_join'])
    
    print(f"\n📊 Results:")
    for chat, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {chat}")


async def example_6_scrape_group_members(app: TelegramManagerApp):
    """
    Example 6: Scrape members from a single group
    
    Features demonstrated:
    - Member scraping with fallback to message-based scraping
    - Load-balanced session selection
    - CSV export
    """
    print("\n" + "="*80)
    print("EXAMPLE 6: Scrape Group Members")
    print("="*80)
    
    if not data['groups_to_scrape']:
        print("⚠️  No groups to scrape configured in data dict")
        return
    
    group = data['groups_to_scrape'][0]
    
    result = await app.scrape_group_members(
        group_identifier=group,
        join_first=False,  # Set to True to join before scraping
        max_members=10000
    )
    
    if result['success']:
        print(f"✅ Scraped {result.get('members_count', 0)} members")
        print(f"📁 Saved to: {result['file_path']}")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")


async def example_7_bulk_scrape_groups(app: TelegramManagerApp):
    """
    Example 7: Scrape multiple groups with load balancing
    
    Features demonstrated:
    - Bulk group scraping
    - Load balancing across sessions
    - Daily limit enforcement
    - Retry logic
    """
    print("\n" + "="*80)
    print("EXAMPLE 7: Bulk Scrape Multiple Groups")
    print("="*80)
    
    if not data['groups_to_scrape']:
        print("⚠️  No groups to scrape configured in data dict")
        return
    
    results = await app.bulk_scrape_groups(
        groups=data['groups_to_scrape'],
        join_first=False,
        max_members=10000
    )
    
    print(f"\n📊 Results:")
    for group, result in results.items():
        if result.get('success'):
            print(f"✅ {group}: {result.get('members_count', 0)} members -> {result['file_path']}")
        else:
            print(f"❌ {group}: {result.get('error', 'Unknown error')}")


async def example_8_extract_group_links(app: TelegramManagerApp):
    """
    Example 8: Extract group links from link-sharing channels
    
    Features demonstrated:
    - Extract Telegram links from messages
    - Parse different link formats
    """
    print("\n" + "="*80)
    print("EXAMPLE 8: Extract Group Links from Channels")
    print("="*80)
    
    if not data['link_channels']:
        print("⚠️  No link channels configured in data dict")
        return
    
    channel = data['link_channels'][0]
    
    result = await app.extract_group_links(
        target=channel,
        limit_messages=100
    )
    
    if result['success']:
        print(f"✅ Found {len(result['telegram_links'])} links")
        print(f"📋 Links: {result['telegram_links'][:5]}...")  # Show first 5
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")


async def example_9_extract_and_scrape_workflow(app: TelegramManagerApp):
    """
    Example 9: Complete workflow - Extract links then scrape all found groups
    
    Features demonstrated:
    - Multi-step workflow
    - Link extraction from multiple channels
    - Automatic scraping of discovered groups
    - Deduplication
    """
    print("\n" + "="*80)
    print("EXAMPLE 9: Extract Links and Scrape Workflow")
    print("="*80)
    
    if not data['link_channels']:
        print("⚠️  No link channels configured in data dict")
        return
    
    result = await app.bulk_scrape_from_link_channels(
        link_channels=data['link_channels'],
        join_first=True,  # Join groups before scraping
        limit_messages=100,
        max_members=10000
    )
    
    print(f"\n📊 Workflow Results:")
    print(f"🔗 Groups found: {result['total_groups_found']}")
    print(f"✅ Groups scraped: {result['total_groups_scraped']}")
    
    # Show scraping results
    for group, scrape_result in result['scraping_results'].items():
        if scrape_result.get('success'):
            print(f"  ✅ {group}: {scrape_result.get('members_count', 0)} members")


async def example_10_check_target_types(app: TelegramManagerApp):
    """
    Example 10: Check if targets are scrapable
    
    Features demonstrated:
    - Target type checking
    - Identify channels vs groups
    - Filter scrapable targets
    """
    print("\n" + "="*80)
    print("EXAMPLE 10: Check Target Types")
    print("="*80)
    
    if not data['targets_to_check']:
        print("⚠️  No targets to check configured in data dict")
        return
    
    results = await app.bulk_check_targets(data['targets_to_check'])
    
    print(f"\n📊 Target Check Results:")
    for target, result in results.items():
        if result.get('success'):
            scrapable = "✅ Scrapable" if result.get('scrapable') else "❌ Not scrapable"
            target_type = result.get('target_type', 'unknown')
            print(f"{scrapable} - {target} ({target_type})")
        else:
            print(f"❌ {target}: {result.get('error', 'Unknown error')}")


async def example_11_safe_scrape_with_filter(app: TelegramManagerApp):
    """
    Example 11: Safe scraping workflow with automatic filtering
    
    Features demonstrated:
    - Automatic target type checking
    - Filter out non-scrapable targets
    - Only scrape valid groups
    """
    print("\n" + "="*80)
    print("EXAMPLE 11: Safe Scrape with Filtering")
    print("="*80)
    
    if not data['targets_to_check']:
        print("⚠️  No targets configured in data dict")
        return
    
    result = await app.safe_bulk_scrape_with_filter(
        targets=data['targets_to_check'],
        join_first=False,
        max_members=10000
    )
    
    print(f"\n📊 Safe Scrape Results:")
    print(f"🔍 Targets checked: {result['total_checked']}")
    print(f"✅ Scrapable targets: {result['total_scrapable']}")
    print(f"📥 Successfully scraped: {result['total_scraped']}")


async def example_12_session_statistics(app: TelegramManagerApp):
    """
    Example 12: Get detailed session statistics
    
    Features demonstrated:
    - Session status monitoring
    - Daily usage tracking
    - Load balancing metrics
    """
    print("\n" + "="*80)
    print("EXAMPLE 12: Session Statistics")
    print("="*80)
    
    stats = await app.get_session_stats()
    
    print(f"\n📊 Session Statistics:")
    for session_name, session_stats in stats.items():
        print(f"\n📱 Session: {session_name}")
        print(f"  Connected: {session_stats.get('connected', False)}")
        print(f"  Monitoring: {session_stats.get('monitoring', False)}")
        print(f"  Active tasks: {session_stats.get('active_tasks', 0)}")
        
        if 'daily_stats' in session_stats:
            daily = session_stats['daily_stats']
            print(f"  Daily messages read: {daily['messages_read']}/{daily['max_messages_per_day']}")
            print(f"  Daily groups scraped: {daily['groups_scraped_today']}/{daily['max_groups_per_day']}")


async def example_13_manager_metrics(app: TelegramManagerApp):
    """
    Example 13: Get manager-level metrics
    
    Features demonstrated:
    - Operation metrics tracking
    - Active operation counts
    - Global task tracking
    """
    print("\n" + "="*80)
    print("EXAMPLE 13: Manager Metrics")
    print("="*80)
    
    if not app.manager:
        print("❌ Manager not initialized")
        return
    
    # Get operation metrics
    metrics = await app.manager.get_operation_metrics()
    print(f"\n📊 Operation Metrics:")
    for op_type, count in metrics.items():
        print(f"  {op_type}: {count} active")
    
    # Get scrape count
    scrape_count = app.manager.get_active_scrape_count()
    print(f"\n🔍 Active scrape operations: {scrape_count}")
    
    # Get global task count
    task_count = await app.manager.get_global_task_count()
    print(f"📋 Global task count: {task_count}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def run_all_examples():
    """
    Run all examples in sequence
    
    Note: Comment out examples you don't want to run
    """
    print("\n" + "="*80)
    print("TELEGRAM MANAGER - COMPLETE EXAMPLES")
    print("="*80)
    
    # Initialize
    app = await example_1_initialize_and_load_sessions()
    
    if not app or not app.manager:
        print("❌ Failed to initialize, stopping examples")
        return
    
    try:
        # Run examples (comment out the ones you don't want to run)
        
        # await example_2_monitoring(app)
        # await example_3_send_bulk_messages(app)
        # await example_4_get_chat_members(app)
        # await example_5_join_chats(app)
        # await example_6_scrape_group_members(app)
        # await example_7_bulk_scrape_groups(app)
        # await example_8_extract_group_links(app)
        # await example_9_extract_and_scrape_workflow(app)
        # await example_10_check_target_types(app)
        # await example_11_safe_scrape_with_filter(app)
        await example_12_session_statistics(app)
        await example_13_manager_metrics(app)
        
    finally:
        # Cleanup
        print("\n" + "="*80)
        print("CLEANUP")
        print("="*80)
        await app.shutdown()
        print("✅ Application shutdown complete")


async def run_single_example(example_number: int):
    """
    Run a single example by number
    
    Args:
        example_number: Number of the example to run (1-13)
    """
    app = await example_1_initialize_and_load_sessions()
    
    if not app or not app.manager:
        print("❌ Failed to initialize")
        return
    
    try:
        examples = {
            2: example_2_monitoring,
            3: example_3_send_bulk_messages,
            4: example_4_get_chat_members,
            5: example_5_join_chats,
            6: example_6_scrape_group_members,
            7: example_7_bulk_scrape_groups,
            8: example_8_extract_group_links,
            9: example_9_extract_and_scrape_workflow,
            10: example_10_check_target_types,
            11: example_11_safe_scrape_with_filter,
            12: example_12_session_statistics,
            13: example_13_manager_metrics,
        }
        
        if example_number in examples:
            await examples[example_number](app)
        else:
            print(f"❌ Example {example_number} not found")
    
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())
    
    # Or run a single example:
    # asyncio.run(run_single_example(12))
