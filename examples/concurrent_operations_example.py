"""
Concurrent Operations Example

Demonstrates how monitoring, scraping, and sending work together simultaneously.

KEY FEATURES:
- Monitoring runs continuously in background
- Monitoring + Scraping can run at same time ✅
- Monitoring + Sending can run at same time ✅
- Scraping + Sending NEVER run together (ban prevention) ✅
"""

import asyncio
import logging
from telegram_manager.main import TelegramManagerApp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def main():
    """Demonstrate concurrent operations"""
    
    print("=" * 70)
    print("🎯 CONCURRENT OPERATIONS DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Initialize app
    print("📱 Initializing Telegram Manager...")
    app = TelegramManagerApp()
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize")
        return
    
    print("✅ Initialized successfully!\n")
    
    try:
        # ============================================================
        # STEP 1: Start Monitoring (Runs in Background)
        # ============================================================
        print("=" * 70)
        print("STEP 1: Starting Monitoring")
        print("=" * 70)
        print()
        
        # Configure monitoring targets
        # Note: You need to configure these in your config or database
        # This is just an example showing the API
        print("🎯 Monitoring will run continuously in background...")
        print("   - Listens for new messages")
        print("   - Reacts with configured reactions")
        print("   - Does NOT block other operations")
        print()
        
        # Uncomment if you have monitoring configured:
        # await app.start_monitoring()
        # print("✅ Monitoring started!\n")
        
        # ============================================================
        # STEP 2: Scrape Groups (While Monitoring is Active)
        # ============================================================
        print("=" * 70)
        print("STEP 2: Scraping Groups (Concurrent with Monitoring)")
        print("=" * 70)
        print()
        
        print("🔍 Scraping groups while monitoring continues...")
        print("   ✅ Monitoring + Scraping = ALLOWED (concurrent)")
        print()
        
        # Example: Scrape a group
        # Uncomment to test with real group:
        # result = await app.scrape_group_members(
        #     group_identifier='@your_group',
        #     join_first=False,
        #     max_members=100
        # )
        # 
        # if result['success']:
        #     print(f"✅ Scraped {result['members_count']} members")
        #     print(f"📁 Saved to: {result['file_path']}")
        # print()
        
        # ============================================================
        # STEP 3: Send Messages (While Monitoring is Active)
        # ============================================================
        print("=" * 70)
        print("STEP 3: Sending Messages (Concurrent with Monitoring)")
        print("=" * 70)
        print()
        
        print("📤 Sending messages while monitoring continues...")
        print("   ✅ Monitoring + Sending = ALLOWED (concurrent)")
        print()
        
        # Example: Send messages
        # Uncomment to test with real recipients:
        # recipients = ['@user1', '@user2', '@user3']
        # result = await app.send_text_to_users(
        #     recipients=recipients,
        #     message="Hello! This is a test message.",
        #     delay=2.0
        # )
        # 
        # print(f"✅ Sent to {result.succeeded} users")
        # print(f"❌ Failed: {result.failed}")
        # print()
        
        # ============================================================
        # STEP 4: Demonstrate Ban Prevention
        # ============================================================
        print("=" * 70)
        print("STEP 4: Ban Prevention (Scraping + Sending)")
        print("=" * 70)
        print()
        
        print("🚫 Scraping + Sending = NOT ALLOWED (ban prevention)")
        print("   - If scraping is active, sending will be queued")
        print("   - If sending is active, scraping will be queued")
        print("   - They NEVER run at the same time on same session")
        print()
        
        print("Example scenario:")
        print("  1. Start scraping operation (takes 30 seconds)")
        print("  2. Try to send messages (will wait in queue)")
        print("  3. After scraping completes, sending starts")
        print("  4. Result: No ban risk! ✅")
        print()
        
        # ============================================================
        # STEP 5: Check Session Status
        # ============================================================
        print("=" * 70)
        print("STEP 5: Session Status")
        print("=" * 70)
        print()
        
        stats = await app.get_session_stats()
        
        print("📊 Session Status:")
        for session_name, info in stats.items():
            print(f"\n  📱 {session_name}")
            print(f"     Connected: {'✅' if info['connected'] else '❌'}")
            print(f"     Monitoring: {'✅' if info['monitoring'] else '❌'}")
            print(f"     Active tasks: {info['active_tasks']}")
            print(f"     Queue depth: {info.get('queue_depth', 0)}")
        print()
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print("=" * 70)
        print("✅ SUMMARY: Concurrent Operations Architecture")
        print("=" * 70)
        print()
        print("What's Working:")
        print("  ✅ Monitoring runs continuously in background")
        print("  ✅ Monitoring + Scraping work together")
        print("  ✅ Monitoring + Sending work together")
        print("  ✅ Scraping + Sending are serialized (ban prevention)")
        print()
        print("How It Works:")
        print("  🔹 Monitoring: Independent background task")
        print("  🔹 Scraping/Sending: Share operation_lock (one at a time)")
        print("  🔹 Result: Like a real Telegram app!")
        print()
        print("Ban Prevention:")
        print("  🚫 Scraping + Sending NEVER run together")
        print("  ✅ Prevents triggering Telegram's anti-spam detection")
        print("  ✅ Safe for long-term use")
        print()
        
    finally:
        # Cleanup
        print("🛑 Shutting down...")
        await app.shutdown()
        print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
