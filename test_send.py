"""
Simple example: Send messages to a list of users

This is a straightforward example showing how to send text messages
to multiple users using the Telegram Manager.
"""

import asyncio
from telegram_manager.main import TelegramManagerApp


async def main():
    # Initialize the app
    app = TelegramManagerApp()
    
    # Load sessions from database
    print("Initializing Telegram Manager...")
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize. Make sure you have sessions in the database.")
        return
    
    print("✅ Initialized successfully\n")
    
    # Define your list of users
    # You can use usernames (without @) or user IDs
    users = [
        'amirkingofcrypto',
        'momento_hastam', 
        # Add more users here
    ]
    
    # Your message
    message = """
-99999pip
جبران میکنم
"""
    
    # Send the message to all users
    print(f"Sending message to {len(users)} users...")
    print(f"Message: {message[:50]}...\n")
    
    results = await app.send_text_to_users(
        recipients=users,
        message=message,
        delay=2.0,  # Wait 2 seconds between each send
        skip_invalid=True  # Skip invalid usernames instead of failing
    )
    
    # Show results
    print("\n" + "="*60)
    print("Results:")
    print("="*60)
    
    success_count = 0
    failed_count = 0
    
    for user, result in results.items():
        if result.success:
            print(f"✅ {user} - Sent successfully via {result.session_used}")
            success_count += 1
        else:
            print(f"❌ {user} - Failed: {result.error}")
            failed_count += 1
    
    print("\n" + "="*60)
    print(f"Summary: {success_count} succeeded, {failed_count} failed")
    print("="*60)
    
    # Cleanup
    await app.shutdown()
    print("\n✅ Done!")


if __name__ == '__main__':
    asyncio.run(main())
