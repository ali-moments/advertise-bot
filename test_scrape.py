"""
Simple example: Scrape group members

This demonstrates how to scrape members from Telegram groups/channels.
"""

import asyncio
from telegram_manager.main import TelegramManagerApp


async def main():
    # Initialize the app
    app = TelegramManagerApp()
    
    print("Initializing Telegram Manager...")
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize. Make sure you have sessions in the database.")
        return
    
    print("✅ Initialized successfully\n")
    
    # Example 1: Scrape a single group
    print("="*60)
    print("Example 1: Scrape a single group")
    print("="*60)
    
    group = "https://t.me/mexciranir"  # Replace with your group
    
    print(f"Scraping members from: {group}")
    result = await app.scrape_group_members(
        group_identifier=group,
        join_first=False,  # Set to True if you need to join first
        max_members=10000  # Increase to get more members
    )
    
    if result['success']:
        print(f"✅ Successfully scraped {result.get('members_count', 0)} members")
        print(f"   Saved to: {result.get('file_path', 'N/A')}")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Example 2: Scrape multiple groups
    print("\n" + "="*60)
    print("Example 2: Scrape multiple groups")
    print("="*60)
    
    groups = [
        "https://t.me/mexciranir",
        # Add more groups here
    ]
    
    print(f"Scraping {len(groups)} groups...")
    results = await app.bulk_scrape_groups(
        groups=groups,
        join_first=False,
        max_members=10000  # Increase to get more members
    )
    
    print("\nResults:")
    for group, result in results.items():
        if result.get('success'):
            print(f"✅ {group}: {result.get('members_count', 0)} members")
        else:
            print(f"❌ {group}: {result.get('error', 'Failed')}")
    
    # Example 3: Check target types
    print("\n" + "="*60)
    print("Example 3: Check if targets are scrapable")
    print("="*60)
    
    targets = [
        "https://t.me/mexciranir",
        "@some_channel",
        # Add more targets to check
    ]
    
    print("Checking targets...")
    checks = await app.bulk_check_targets(targets)
    
    for target, result in checks.items():
        if result.get('scrapable'):
            print(f"✅ {target} - Type: {result.get('type')} (Scrapable)")
        else:
            print(f"❌ {target} - {result.get('reason', 'Not scrapable')}")
    
    # Example 4: Extract links from a channel
    print("\n" + "="*60)
    print("Example 4: Extract group links from a channel")
    print("="*60)
    
    link_channel = "https://t.me/linkdoniwar2"  # A channel that posts group links
    
    print(f"Extracting links from: {link_channel}")
    link_result = await app.extract_group_links(
        target=link_channel,
        limit_messages=50
    )
    
    if link_result['success']:
        links = link_result.get('telegram_links', [])
        print(f"✅ Found {len(links)} Telegram links")
        if links:
            print("   First 5 links:")
            for link in links[:5]:
                print(f"   - {link}")
    else:
        print(f"❌ Failed: {link_result.get('error', 'Unknown error')}")
    
    # Example 5: Get session statistics
    print("\n" + "="*60)
    print("Example 5: Session Statistics")
    print("="*60)
    
    stats = await app.get_session_stats()
    for session_name, session_stats in stats.items():
        print(f"\n{session_name}:")
        print(f"  Connected: {session_stats.get('connected', False)}")
        print(f"  Active Tasks: {session_stats.get('active_tasks', 0)}")
    
    # Cleanup
    await app.shutdown()
    print("\n✅ Done!")


if __name__ == '__main__':
    asyncio.run(main())
