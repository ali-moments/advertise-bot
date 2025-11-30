"""
Telegram Manager - Quick Start Guide

This is a simple guide showing the most common use cases.
Replace the placeholder values with your actual data.

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
from telegram_manager.main import TelegramManagerApp

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def main():
    """Main function - choose what you want to do"""
    
    # Step 1: Initialize the app (loads your sessions from database)
    print("🚀 Initializing Telegram Manager...")
    app = TelegramManagerApp()
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize. Check your database and sessions.")
        return
    
    print("✅ Initialized successfully!\n")
    
    try:
        # ============================================================
        # CHOOSE YOUR OPERATION - Uncomment the one you want to use
        # ============================================================
        
        # --- 1. SEND TEXT MESSAGES TO USERS ---
        # await send_text_messages(app)
        
        # --- 2. SEND IMAGES TO USERS ---
        # await send_images(app)
        
        # --- 3. SEND MESSAGES FROM CSV FILE ---
        # await send_from_csv(app)
        
        # --- 4. MONITOR CHANNELS AND AUTO-REACT ---
        # await monitor_channels(app)
        
        # --- 5. SCRAPE GROUP MEMBERS ---
        # await scrape_groups(app)
        
        # --- 6. CHECK SESSION STATUS ---
        await check_status(app)
        
        # --- 7. CONCURRENT MONITORING + SCRAPING ---
        # await concurrent_monitoring_and_scraping(app)
        
        # --- 8. CONCURRENT MONITORING + SENDING ---
        # await concurrent_monitoring_and_sending(app)
        
    finally:
        # Always cleanup when done
        print("\n🛑 Shutting down...")
        await app.shutdown()
        print("✅ Done!")


# ============================================================
# OPERATION EXAMPLES - Simple and clear
# ============================================================

async def send_text_messages(app):
    """Send a text message to multiple users"""
    print("📤 SENDING TEXT MESSAGES\n")
    
    # Your recipients (usernames or user IDs)
    recipients = [
        '@username1',
        '@username2',
        '123456789',  # User ID
    ]
    
    # Your message
    message = "Hello! This is a test message."
    
    # Send it
    result = await app.send_text_to_users(
        recipients=recipients,
        message=message,
        delay=2.0  # Wait 2 seconds between each send
    )
    
    # Check results
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")


async def send_images(app):
    """Send an image with caption to multiple users"""
    print("🖼️ SENDING IMAGES\n")
    
    recipients = [
        '@username1',
        '@username2',
    ]
    
    # Path to your image
    image_path = '/path/to/your/image.jpg'
    caption = "Check out this image!"
    
    result = await app.send_image_to_users(
        recipients=recipients,
        image_path=image_path,
        caption=caption,
        delay=2.0
    )
    
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")


async def send_from_csv(app):
    """Send messages to users listed in a CSV file"""
    print("📋 SENDING FROM CSV FILE\n")
    
    # Your CSV file should have a column with usernames or user IDs
    csv_path = '/path/to/your/users.csv'
    message = "Hello from CSV!"
    
    result = await app.send_from_csv_file(
        csv_path=csv_path,
        message=message,
        batch_size=100,  # Process 100 users at a time
        resumable=True   # Can resume if interrupted
    )
    
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")


async def monitor_channels(app):
    """Monitor channels and automatically react to new messages"""
    print("👀 MONITORING CHANNELS\n")
    
    # Configure which channels to monitor and what reactions to use
    # Note: You need to configure this in your database first
    # This example just shows how to start/stop monitoring
    
    print("Starting monitoring...")
    await app.start_monitoring()
    
    # Let it run for 60 seconds
    print("Monitoring active for 60 seconds...")
    await asyncio.sleep(60)
    
    print("Stopping monitoring...")
    await app.stop_monitoring()
    print("✅ Monitoring stopped")


async def concurrent_monitoring_and_scraping(app):
    """
    Example: Monitor channels while scraping groups concurrently
    
    This demonstrates the concurrent operation model where monitoring
    runs continuously in the background while other operations execute.
    """
    print("🔄 CONCURRENT MONITORING + SCRAPING\n")
    
    # Start monitoring first
    print("Starting monitoring...")
    await app.start_monitoring()
    print("✅ Monitoring is now active in the background\n")
    
    # Now scrape a group while monitoring continues
    print("Scraping group members (monitoring continues in background)...")
    scrape_result = await app.scrape_group_members(
        group_identifier='@your_group',
        max_members=1000
    )
    
    if scrape_result['success']:
        print(f"✅ Scraped {scrape_result['members_count']} members")
        print(f"📁 Saved to: {scrape_result['file_path']}")
    
    # Monitoring is still active!
    print("\n✅ Monitoring continued throughout the scraping operation")
    
    # Stop monitoring when done
    await app.stop_monitoring()
    print("✅ Monitoring stopped")


async def concurrent_monitoring_and_sending(app):
    """
    Example: Monitor channels while sending messages concurrently
    
    Monitoring runs in the background while messages are sent.
    """
    print("🔄 CONCURRENT MONITORING + SENDING\n")
    
    # Start monitoring
    print("Starting monitoring...")
    await app.start_monitoring()
    print("✅ Monitoring is now active in the background\n")
    
    # Send messages while monitoring continues
    print("Sending messages (monitoring continues in background)...")
    recipients = ['@user1', '@user2', '@user3']
    message = "Hello! This message was sent while monitoring was active."
    
    result = await app.send_text_to_users(
        recipients=recipients,
        message=message,
        delay=2.0
    )
    
    print(f"✅ Sent: {result['succeeded']}")
    print(f"❌ Failed: {result['failed']}")
    
    # Monitoring is still active!
    print("\n✅ Monitoring continued throughout the sending operation")
    
    # Stop monitoring
    await app.stop_monitoring()
    print("✅ Monitoring stopped")


async def scrape_groups(app):
    """Scrape members from Telegram groups"""
    print("🔍 SCRAPING GROUP MEMBERS\n")
    
    # Group to scrape (username or invite link)
    group = '@your_group_username'
    # or: group = 'https://t.me/+InviteLinkHere'
    
    result = await app.scrape_group_members(
        group_identifier=group,
        join_first=False,  # Set True to join before scraping
        max_members=10000
    )
    
    if result['success']:
        print(f"✅ Scraped {result['members_count']} members")
        print(f"📁 Saved to: {result['file_path']}")
    else:
        print(f"❌ Failed: {result['error']}")


async def check_status(app):
    """Check the status of your sessions"""
    print("📊 SESSION STATUS\n")
    
    stats = await app.get_session_stats()
    
    for session_name, info in stats.items():
        print(f"\n📱 {session_name}")
        print(f"   Connected: {'✅' if info['connected'] else '❌'}")
        print(f"   Monitoring: {'✅' if info['monitoring'] else '❌'}")
        print(f"   Active tasks: {info['active_tasks']}")


# ============================================================
# ADVANCED EXAMPLES
# ============================================================
# 
# BAN PREVENTION STRATEGY:
# The system automatically prevents risky operation combinations:
# - Scraping and sending NEVER run simultaneously on the same session
# - Monitoring runs independently and can overlap with both
# - This mimics real Telegram app behavior and avoids anti-spam detection
# ============================================================

async def preview_before_sending(app):
    """Preview what will happen before actually sending"""
    print("👁️ PREVIEW MODE\n")
    
    recipients = ['@user1', '@user2', '@user3']
    message = "Test message"
    
    # Preview without sending
    preview = await app.preview_send(
        recipients=recipients,
        message=message
    )
    
    print(f"Will send to: {preview['recipient_count']} users")
    print(f"Estimated time: {preview['estimated_duration']:.1f} seconds")
    print(f"Session distribution: {preview['session_distribution']}")
    
    # If preview looks good, actually send
    # result = await app.send_text_to_users(recipients, message)


async def configure_reaction_pool(app):
    """Configure multiple reactions for a channel"""
    print("🎭 CONFIGURING REACTION POOL\n")
    
    channel = '@your_channel'
    
    # Configure multiple reactions with weights
    # Higher weight = more likely to be selected
    reactions = [
        {'emoji': '👍', 'weight': 5},  # 50% chance
        {'emoji': '❤️', 'weight': 3},  # 30% chance
        {'emoji': '🔥', 'weight': 2},  # 20% chance
    ]
    
    await app.configure_reaction_pool(
        chat_id=channel,
        reactions=reactions,
        cooldown=2.0
    )
    
    print(f"✅ Configured reaction pool for {channel}")


async def bulk_operations(app):
    """Send to many users efficiently"""
    print("⚡ BULK OPERATIONS\n")
    
    # For large lists, the system automatically:
    # - Distributes work across all your sessions
    # - Handles rate limits
    # - Retries failures
    # - Tracks progress
    
    recipients = [f'@user{i}' for i in range(1000)]  # 1000 users
    message = "Bulk message"
    
    result = await app.send_text_to_users(
        recipients=recipients,
        message=message,
        delay=2.0
    )
    
    print(f"✅ Sent: {result['succeeded']}/{len(recipients)}")
    print(f"❌ Failed: {result['failed']}")


# ============================================================
# RUN IT
# ============================================================

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
    
    # Or run a specific operation:
    # asyncio.run(send_text_messages(TelegramManagerApp()))
