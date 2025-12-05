"""
Telegram Bot Control Panel - Quick Start Examples

This file shows examples of using the Telegram Bot Control Panel.

IMPORTANT: The bot provides a Persian-language Telegram interface for managing
all these operations. You don't need to use this Python API directly unless
you're integrating with external systems.

RECOMMENDED USAGE:
==================
1. Start the bot: python panel/bot.py
2. Open Telegram and send /start to your bot
3. Use the Persian interface to perform all operations

This file is for developers who want to:
- Integrate with external systems
- Automate operations programmatically
- Understand the underlying API

CONCURRENT OPERATION MODEL:
===========================
The system supports concurrent operations that mimic real Telegram app behavior:

✅ ALLOWED CONCURRENT OPERATIONS:
- Monitoring + Scraping (monitoring runs in background while scraping)
- Monitoring + Sending (monitoring runs in background while sending)

❌ PREVENTED CONCURRENT OPERATIONS (Ban Prevention):
- Scraping + Sending (these are serialized via operation queue)

This ensures your sessions behave naturally and avoid triggering Telegram's
anti-spam detection while maximizing efficiency.
"""

import asyncio
import logging
from telegram_manager.manager import TelegramSessionManager

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def main():
    """
    Main function - choose what you want to do
    
    NOTE: For normal usage, use the Telegram bot interface instead!
    Start the bot with: python panel/bot.py
    Then send /start to your bot in Telegram.
    
    This Python API is for programmatic/automated usage only.
    """
    
    # Step 1: Initialize the session manager (loads your sessions from database)
    print("🚀 Initializing Telegram Session Manager...")
    print("💡 TIP: For normal usage, use the bot interface: python panel/bot.py\n")
    
    manager = TelegramSessionManager()
    
    # Load sessions from database
    result = await manager.load_sessions_from_db()
    
    if not result['success']:
        print("❌ Failed to load sessions. Check your database.")
        return
    
    print(f"✅ Loaded {result['loaded']} sessions successfully!\n")
    
    try:
        # ============================================================
        # CHOOSE YOUR OPERATION - Uncomment the one you want to use
        # ============================================================
        
        # --- 1. SEND TEXT MESSAGES TO USERS ---
        # await send_text_messages(manager)
        
        # --- 2. SEND IMAGES TO USERS ---
        # await send_images(manager)
        
        # --- 3. SCRAPE GROUP MEMBERS ---
        # await scrape_groups(manager)
        
        # --- 4. CHECK SESSION STATUS ---
        await check_status(manager)
        
        # --- 5. BULK SCRAPING ---
        # await bulk_scraping(manager)
        
        # --- 6. BULK SENDING ---
        # await bulk_sending(manager)
        
    finally:
        # Always cleanup when done
        print("\n🛑 Shutting down...")
        await manager.shutdown()
        print("✅ Done!")


# ============================================================
# OPERATION EXAMPLES - Simple and clear
# ============================================================

async def send_text_messages(manager):
    """
    Send a text message to multiple users
    
    NOTE: Use the bot interface for easier usage!
    Bot: /start → ارسال پیام → پیام متنی
    """
    print("📤 SENDING TEXT MESSAGES\n")
    
    # Your recipients (usernames or user IDs)
    recipients = [
        '@username1',
        '@username2',
        '123456789',  # User ID
    ]
    
    # Your message
    message = "Hello! This is a test message."
    
    # Send it using bulk_send_messages
    result = await manager.bulk_send_messages(
        recipients=recipients,
        message=message,
        delay=2.0  # Wait 2 seconds between each send
    )
    
    # Check results
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")
    print(f"📊 Total: {result['total']}")


async def send_images(manager):
    """
    Send an image with caption to multiple users
    
    NOTE: Use the bot interface for easier usage!
    Bot: /start → ارسال پیام → پیام تصویری
    """
    print("🖼️ SENDING IMAGES\n")
    
    recipients = [
        '@username1',
        '@username2',
    ]
    
    # Path to your image
    image_path = '/path/to/your/image.jpg'
    caption = "Check out this image!"
    
    # Send image using bulk_send_messages with media
    result = await manager.bulk_send_messages(
        recipients=recipients,
        message=caption,
        media_path=image_path,
        delay=2.0
    )
    
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")
    print(f"📊 Total: {result['total']}")


async def scrape_groups(manager):
    """
    Scrape members from Telegram groups
    
    NOTE: Use the bot interface for easier usage!
    Bot: /start → استخراج اعضا → استخراج تک گروه
    """
    print("🔍 SCRAPING GROUP MEMBERS\n")
    
    # Group to scrape (username or invite link)
    group = '@your_group_username'
    # or: group = 'https://t.me/+InviteLinkHere'
    
    result = await manager.scrape_group_members_random_session(
        group_identifier=group,
        join_first=False,  # Set True to join before scraping
        max_members=10000
    )
    
    if result['success']:
        print(f"✅ Scraped {result['members_count']} members")
        print(f"📁 Saved to: {result.get('file_path', 'N/A')}")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")


async def check_status(manager):
    """
    Check the status of your sessions
    
    NOTE: Use the bot interface for real-time status!
    Bot: /status or /start → وضعیت سیستم
    """
    print("📊 SESSION STATUS\n")
    
    stats = manager.get_session_stats()
    
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Connected: {stats['connected_sessions']}")
    print(f"Disconnected: {stats['disconnected_sessions']}")
    print(f"Active operations: {stats.get('active_operations', 0)}")
    
    print("\nSession details:")
    for session_name, session in manager.sessions.items():
        status = await session.get_status()
        print(f"\n📱 {session_name}")
        print(f"   Connected: {'✅' if status['connected'] else '❌'}")
        print(f"   Phone: {status.get('phone', 'N/A')}")


async def bulk_scraping(manager):
    """
    Scrape multiple groups at once
    
    NOTE: Use the bot interface for easier usage!
    Bot: /start → استخراج اعضا → استخراج چند گروه
    """
    print("🔄 BULK SCRAPING\n")
    
    # List of groups to scrape
    groups = [
        '@group1',
        '@group2',
        '@group3',
    ]
    
    result = await manager.bulk_scrape_groups(
        groups=groups,
        join_first=False,
        max_members=10000
    )
    
    print(f"✅ Succeeded: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")
    print(f"📊 Total: {result['total']}")
    
    # Results are saved to data/ directory
    print(f"\n📁 Results saved to: data/")


async def bulk_sending(manager):
    """
    Send messages to many users efficiently
    
    NOTE: Use the bot interface for easier usage!
    Bot: /start → ارسال پیام → پیام متنی
    """
    print("⚡ BULK SENDING\n")
    
    # For large lists, the system automatically:
    # - Distributes work across all your sessions
    # - Handles rate limits
    # - Retries failures
    # - Tracks progress
    
    recipients = [f'@user{i}' for i in range(100)]  # 100 users
    message = "Bulk message"
    
    result = await manager.bulk_send_messages(
        recipients=recipients,
        message=message,
        delay=2.0
    )
    
    print(f"✅ Sent: {result['succeeded']}/{result['total']}")
    print(f"❌ Failed: {result['failed']}")
    print(f"⏱️ Duration: {result.get('duration', 0):.1f} seconds")


# ============================================================
# IMPORTANT NOTES
# ============================================================
# 
# 🤖 RECOMMENDED: Use the Telegram Bot Interface
# ================================================
# The easiest way to use this system is through the bot:
# 
# 1. Start the bot:
#    python panel/bot.py
# 
# 2. Open Telegram and send /start to your bot
# 
# 3. Use the Persian interface to:
#    - استخراج اعضا (Scrape members)
#    - ارسال پیام (Send messages)
#    - مانیتورینگ (Monitor channels)
#    - مدیریت سشن‌ها (Manage sessions)
#    - وضعیت سیستم (System status)
# 
# 💻 Python API Usage
# ===================
# Use this Python API only if you need to:
# - Integrate with external systems
# - Automate operations programmatically
# - Build custom workflows
# 
# 🚫 BAN PREVENTION STRATEGY
# ==========================
# The system automatically prevents risky operation combinations:
# - Scraping and sending NEVER run simultaneously on the same session
# - This mimics real Telegram app behavior and avoids anti-spam detection
# 
# ============================================================


# ============================================================
# RUN IT
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Telegram Bot Control Panel - Python API Examples")
    print("=" * 60)
    print()
    print("⚠️  IMPORTANT: For normal usage, use the bot interface!")
    print()
    print("   Start the bot:")
    print("   $ python panel/bot.py")
    print()
    print("   Then send /start to your bot in Telegram")
    print()
    print("=" * 60)
    print()
    
    # Run the main function
    asyncio.run(main())
