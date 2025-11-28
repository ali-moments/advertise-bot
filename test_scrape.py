"""
Example of using the group member scraping, link extraction, and target checking functionality
"""

import asyncio
from telegram_manager.main import TelegramManagerApp

async def example_scraping():
    """Example of group member scraping and link extraction"""
    
    app = TelegramManagerApp()
    
    if await app.initialize():
        try:
            print("🚀 Telegram Manager Started Successfully!")
            
            # Example 1: Check target types before scraping
            print("\n🔍 Example 1: Checking target types...")
            test_targets = [
                "https://t.me/+0AC3yo0R-j45MTdk",  # Group
                "@some_channel",                    # Channel (should be skipped)
                "@some_user",                       # User (should be skipped)
                "https://t.me/some_group",         # Group
                "invalid_target",                  # Invalid (should be skipped)
            ]
            
            checks = await app.bulk_check_targets(test_targets)
            for target, result in checks.items():
                status = "✅" if result.get('scrapable', False) else "❌"
                print(f"   {status} {target}")
                if result['success']:
                    print(f"      Type: {result.get('type', 'unknown')}")
                    print(f"      Reason: {result.get('reason', '')}")
                else:
                    print(f"      Error: {result.get('error', '')}")
                    print(f"      Reason: {result.get('reason', '')}")
            
            # Example 2: Filter and scrape only scrapable targets
            print("\n🎯 Example 2: Safe scraping with target filtering...")
            safe_result = await app.safe_bulk_scrape_with_filter(
                targets=test_targets,
                join_first=True,
                max_members=1000
            )
            
            print(f"   - Targets checked: {safe_result['total_checked']}")
            print(f"   - Targets scrapable: {safe_result['total_scrapable']}")
            print(f"   - Targets scraped: {safe_result['total_scraped']}")
            
            # Example 3: Extract group links from actual "لینک دونی" channels
            print("\n🔗 Example 3: Extracting group links from link channels...")
            link_channels = [
                "https://t.me/linkdoniwar2",
                "@Linkdoniimm",
            ]
            
            for channel in link_channels:
                print(f"\n   📋 Extracting links from: {channel}")
                link_result = await app.extract_group_links(channel, limit_messages=50)
                if link_result['success']:
                    print(f"   ✅ Found {link_result['telegram_links_count']} group links:")
                    for link in link_result['telegram_links'][:5]:  # Show first 5
                        print(f"      - {link}")
                else:
                    print(f"   ❌ Failed: {link_result['error']}")
                
                # Small delay between channels
                await asyncio.sleep(2)
            
            # Example 4: Complete workflow - Extract links from multiple channels, filter, then scrape
            print("\n🔄 Example 4: Complete workflow - Extract from multiple channels, filter, then scrape...")
            
            # Step 1: Extract links from all channels
            print("   Step 1: Extracting links from all channels...")
            links_result = await app.extract_links_from_channels(link_channels, limit_messages=50)
            
            all_links = []
            for channel, result in links_result.items():
                if result['success']:
                    all_links.extend(result['telegram_links'])
                    print(f"      {channel}: {result['telegram_links_count']} links")
            
            unique_links = list(set(all_links))
            print(f"   ✅ Total unique links found: {len(unique_links)}")
            
            if unique_links:
                # Step 2: Filter only scrapable groups
                print("   Step 2: Filtering scrapable groups...")
                scrapable_links = await app.filter_scrapable_targets(unique_links)
                print(f"   ✅ Scrapable groups: {len(scrapable_links)}/{len(unique_links)}")
                
                # Step 3: Scrape only scrapable groups
                if scrapable_links:
                    print("   Step 3: Scraping scrapable groups...")
                    workflow_result = await app.bulk_scrape_from_link_channels(
                        link_channels=link_channels,
                        join_first=True,
                        limit_messages=50,
                        max_members=1000
                    )
                    
                    print(f"   📊 Workflow Results:")
                    print(f"      - Groups found: {workflow_result['total_groups_found']}")
                    print(f"      - Groups scraped: {workflow_result['total_groups_scraped']}")
            
            # Example 5: Safe bulk scraping with daily limits
            print("\n🛡️ Example 5: Safe bulk scraping with daily limits...")
            test_groups = [
                "https://t.me/+0AC3yo0R-j45MTdk",
            ]
            safe_results = await app.bulk_scrape_groups(
                groups=test_groups,
                join_first=True,
                enforce_daily_limits=True
            )
            
            for group, result in safe_results.items():
                status = "✅" if result.get('success') else "❌"
                error = result.get('error', '')
                print(f"   {status} {group}: {result.get('members_count', 0)} members - {error}")
            
            # Example 6: Get session statistics
            print("\n📊 Example 6: Session Statistics...")
            stats = await app.get_session_stats()
            for session_name, session_stats in stats.items():
                print(f"   {session_name}:")
                print(f"      - Connected: {session_stats['connected']}")
                print(f"      - Monitoring: {session_stats['monitoring']}")
                print(f"      - Active Tasks: {session_stats['active_tasks']}")
                if 'daily_stats' in session_stats:
                    print(f"      - Messages Read Today: {session_stats['daily_stats']['messages_read']}")
                    print(f"      - Groups Scraped Today: {session_stats['daily_stats']['groups_scraped_today']}")
            
        except Exception as e:
            print(f"❌ Error in examples: {e}")
        finally:
            await app.shutdown()
            print("\n👋 Application shutdown complete")

async def test_link_extraction_only():
    """Test only the link extraction functionality"""
    app = TelegramManagerApp()
    
    if await app.initialize():
        try:
            print("🔗 Testing Link Extraction Only...")
            
            # Test with multiple link channels
            link_channels = [
                "https://t.me/linkdoniwar2",
                "@Linkdoniimm",
            ]
            
            for channel in link_channels:
                print(f"\n📋 Extracting links from: {channel}")
                result = await app.extract_group_links(channel, limit_messages=30)
                
                if result['success']:
                    print(f"✅ Found {result['telegram_links_count']} Telegram links")
                    if result['telegram_links']:
                        print("   Top links found:")
                        for link in result['telegram_links'][:10]:  # Show first 10
                            print(f"   - {link}")
                else:
                    print(f"❌ Failed: {result['error']}")
                    
                # Small delay between channels
                await asyncio.sleep(2)
                
        finally:
            await app.shutdown()

async def test_target_checking_only():
    """Test only the target checking functionality"""
    app = TelegramManagerApp()
    
    if await app.initialize():
        try:
            print("🔍 Testing Target Checking Only...")
            
            # Test various target types
            test_targets = [
                "https://t.me/linkdoniwar2",           # Channel
                "@Linkdoniimm",                        # Channel
                "https://t.me/+0AC3yo0R-j45MTdk",      # Group
                "https://t.me/telegram",               # Official channel
                "@some_nonexistent_channel",           # Invalid
            ]
            
            print("   Checking target types...")
            checks = await app.bulk_check_targets(test_targets)
            
            for target, result in checks.items():
                status = "✅" if result.get('scrapable', False) else "❌"
                print(f"   {status} {target}")
                
                if result.get('success', False):
                    print(f"      Type: {result.get('type', 'unknown')}")
                    print(f"      Reason: {result.get('reason', '')}")
                    if result.get('type') in ['channel', 'group', 'supergroup', 'megagroup']:
                        print(f"      Title: {result.get('title', 'N/A')}")
                        print(f"      Participants: {result.get('participants_count', 'N/A')}")
                else:
                    print(f"      Error: {result.get('error', 'Unknown error')}")
                    print(f"      Reason: {result.get('reason', 'Check failed')}")
            
            print(f"\n   Filtering scrapable targets...")
            scrapable = await app.filter_scrapable_targets(test_targets)
            print(f"   ✅ Scrapable targets: {scrapable}")
                
        finally:
            await app.shutdown()

if __name__ == "__main__":
    # Run the main scraping example
    # asyncio.run(example_scraping())
    
    # Uncomment to run only link extraction test
    asyncio.run(test_link_extraction_only())
    
    # Uncomment to run only target checking test
    # asyncio.run(test_target_checking_only())