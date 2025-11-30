"""
Example: Preview message sending operations

This example demonstrates how to use the preview_send method to:
1. Validate recipients and media files without sending
2. See how recipients will be distributed across sessions
3. Estimate how long the operation will take

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

import asyncio
from telegram_manager.main import TelegramManagerApp


async def preview_text_message():
    """Preview a text message send operation"""
    print("\n" + "="*60)
    print("Example 1: Preview Text Message Send")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Load sessions
        print("\n📱 Loading sessions...")
        await app.load_sessions_from_db()
        
        # Define recipients
        recipients = [
            'user1',
            'user2',
            'user3',
            'user4',
            'user5'
        ]
        
        # Preview the send operation
        print(f"\n🔍 Previewing send to {len(recipients)} recipients...")
        preview = await app.manager.preview_send(
            recipients=recipients,
            message="Hello! This is a test message.",
            delay=2.0
        )
        
        # Display preview results
        print("\n📊 Preview Results:")
        print(f"  Total recipients: {preview.recipient_count}")
        print(f"  Validation: {'✅ PASSED' if preview.validation_result.valid else '❌ FAILED'}")
        
        if not preview.validation_result.valid:
            print("\n  Validation Errors:")
            for error in preview.validation_result.errors:
                print(f"    - {error.field}: {error.message}")
        
        print(f"\n  Session Distribution:")
        for session_name, count in preview.session_distribution.items():
            print(f"    - {session_name}: {count} recipients")
        
        print(f"\n  Estimated Duration: {preview.estimated_duration:.1f} seconds")
        
        # Ask user if they want to proceed
        if preview.validation_result.valid:
            print("\n✅ Preview successful! You can now proceed with the actual send.")
        else:
            print("\n❌ Preview failed. Please fix validation errors before sending.")
        
    finally:
        await app.shutdown()


async def preview_image_message():
    """Preview an image message send operation"""
    print("\n" + "="*60)
    print("Example 2: Preview Image Message Send")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Load sessions
        print("\n📱 Loading sessions...")
        await app.load_sessions_from_db()
        
        # Define recipients
        recipients = ['user1', 'user2', 'user3']
        
        # Preview with a valid image path (replace with actual path)
        image_path = '/path/to/image.jpg'
        
        print(f"\n🔍 Previewing image send to {len(recipients)} recipients...")
        preview = await app.manager.preview_send(
            recipients=recipients,
            media_path=image_path,
            media_type='image',
            delay=3.0
        )
        
        # Display preview results
        print("\n📊 Preview Results:")
        print(f"  Total recipients: {preview.recipient_count}")
        print(f"  Validation: {'✅ PASSED' if preview.validation_result.valid else '❌ FAILED'}")
        
        if not preview.validation_result.valid:
            print("\n  Validation Errors:")
            for error in preview.validation_result.errors:
                print(f"    - {error.field}: {error.message}")
        else:
            print(f"\n  Session Distribution:")
            for session_name, count in preview.session_distribution.items():
                print(f"    - {session_name}: {count} recipients")
            
            print(f"\n  Estimated Duration: {preview.estimated_duration:.1f} seconds")
        
    finally:
        await app.shutdown()


async def preview_with_invalid_data():
    """Preview with invalid data to see validation errors"""
    print("\n" + "="*60)
    print("Example 3: Preview with Invalid Data")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Load sessions
        print("\n📱 Loading sessions...")
        await app.load_sessions_from_db()
        
        # Test 1: Empty recipient list
        print("\n🔍 Test 1: Empty recipient list")
        preview = await app.manager.preview_send(
            recipients=[],
            message="Test message",
            delay=2.0
        )
        print(f"  Validation: {'✅ PASSED' if preview.validation_result.valid else '❌ FAILED'}")
        if not preview.validation_result.valid:
            for error in preview.validation_result.errors:
                print(f"    - {error.message}")
        
        # Test 2: Non-existent media file
        print("\n🔍 Test 2: Non-existent media file")
        preview = await app.manager.preview_send(
            recipients=['user1', 'user2'],
            media_path='/nonexistent/file.jpg',
            media_type='image',
            delay=2.0
        )
        print(f"  Validation: {'✅ PASSED' if preview.validation_result.valid else '❌ FAILED'}")
        if not preview.validation_result.valid:
            for error in preview.validation_result.errors:
                print(f"    - {error.message}")
        
    finally:
        await app.shutdown()


async def compare_preview_with_actual():
    """Compare preview estimates with actual send times"""
    print("\n" + "="*60)
    print("Example 4: Compare Preview with Actual Send")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Load sessions
        print("\n📱 Loading sessions...")
        await app.load_sessions_from_db()
        
        recipients = ['user1', 'user2', 'user3']
        message = "Test message"
        delay = 2.0
        
        # Get preview
        print(f"\n🔍 Getting preview...")
        preview = await app.manager.preview_send(
            recipients=recipients,
            message=message,
            delay=delay
        )
        
        print(f"\n📊 Preview Estimates:")
        print(f"  Recipients: {preview.recipient_count}")
        print(f"  Session Distribution: {preview.session_distribution}")
        print(f"  Estimated Duration: {preview.estimated_duration:.1f} seconds")
        
        # Note: Actual send would be done here if this were a real scenario
        # For demonstration purposes, we're just showing the preview
        print("\n💡 In a real scenario, you would:")
        print("  1. Review the preview")
        print("  2. Confirm the distribution looks good")
        print("  3. Proceed with actual send using send_text_messages_bulk()")
        
    finally:
        await app.shutdown()


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("Preview Functionality Examples")
    print("="*60)
    
    # Run examples
    await preview_text_message()
    
    # Uncomment to run other examples:
    # await preview_image_message()
    # await preview_with_invalid_data()
    # await compare_preview_with_actual()


if __name__ == '__main__':
    asyncio.run(main())
