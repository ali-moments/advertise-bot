"""
Example: Using TelegramManagerApp message sending methods

This example demonstrates how to use the high-level app API for sending messages,
images, documents, and videos to users.
"""

import asyncio
from telegram_manager.main import TelegramManagerApp


async def main():
    # Initialize the app
    app = TelegramManagerApp()
    
    # Initialize from database
    success = await app.initialize()
    if not success:
        print("❌ Failed to initialize app")
        return
    
    print("✅ App initialized successfully")
    
    # Example 1: Send text messages to users
    print("\n" + "="*60)
    print("Example 1: Sending text messages")
    print("="*60)
    
    recipients = ['user1', 'user2', 'user3']
    message = "Hello! This is a test message from the Telegram Manager."
    
    # Preview the send operation first
    preview = await app.preview_send(recipients, message=message)
    
    if preview.validation_result.valid:
        print(f"✅ Preview valid:")
        print(f"   - Recipients: {preview.recipient_count}")
        print(f"   - Session distribution: {preview.session_distribution}")
        print(f"   - Estimated duration: {preview.estimated_duration:.2f}s")
        
        # Uncomment to actually send:
        # results = await app.send_text_to_users(recipients, message)
        # success_count = sum(1 for r in results.values() if r.success)
        # print(f"✅ Sent {success_count}/{len(recipients)} messages")
    else:
        print(f"❌ Preview validation failed:")
        for error in preview.validation_result.errors:
            print(f"   - {error.field}: {error.message}")
    
    # Example 2: Send images with captions
    print("\n" + "="*60)
    print("Example 2: Sending images with captions")
    print("="*60)
    
    image_path = "/path/to/image.jpg"
    caption = "Check out this amazing image!"
    
    # Preview the image send
    preview = await app.preview_send(
        recipients,
        media_path=image_path,
        media_type='image'
    )
    
    if preview.validation_result.valid:
        print(f"✅ Image send preview valid")
        
        # Uncomment to actually send:
        # results = await app.send_image_to_users(recipients, image_path, caption)
        # success_count = sum(1 for r in results.values() if r.success)
        # print(f"✅ Sent {success_count}/{len(recipients)} images")
    else:
        print(f"❌ Image validation failed:")
        for error in preview.validation_result.errors:
            print(f"   - {error.field}: {error.message}")
    
    # Example 3: Send documents
    print("\n" + "="*60)
    print("Example 3: Sending documents")
    print("="*60)
    
    document_path = "/path/to/document.pdf"
    caption = "Important document attached"
    
    # Uncomment to send:
    # results = await app.send_document_to_users(
    #     recipients,
    #     document_path,
    #     caption,
    #     delay=3.0  # Custom delay
    # )
    # success_count = sum(1 for r in results.values() if r.success)
    # print(f"✅ Sent {success_count}/{len(recipients)} documents")
    
    print("ℹ️  Document sending example (commented out)")
    
    # Example 4: Send videos
    print("\n" + "="*60)
    print("Example 4: Sending videos")
    print("="*60)
    
    video_path = "/path/to/video.mp4"
    caption = "Watch this video!"
    
    # Uncomment to send:
    # results = await app.send_video_to_users(
    #     recipients,
    #     video_path,
    #     caption
    # )
    # success_count = sum(1 for r in results.values() if r.success)
    # print(f"✅ Sent {success_count}/{len(recipients)} videos")
    
    print("ℹ️  Video sending example (commented out)")
    
    # Example 5: Send from CSV file
    print("\n" + "="*60)
    print("Example 5: Sending from CSV file")
    print("="*60)
    
    csv_path = "/path/to/recipients.csv"
    message = "Bulk message from CSV"
    
    # Uncomment to send:
    # result = await app.send_from_csv_file(
    #     csv_path,
    #     message,
    #     batch_size=500,
    #     delay=2.0,
    #     resumable=True
    # )
    # print(f"✅ CSV send completed:")
    # print(f"   - Total: {result.total}")
    # print(f"   - Succeeded: {result.succeeded}")
    # print(f"   - Failed: {result.failed}")
    # print(f"   - Duration: {result.duration:.2f}s")
    
    print("ℹ️  CSV sending example (commented out)")
    
    # Example 6: Custom delay and skip_invalid options
    print("\n" + "="*60)
    print("Example 6: Custom options")
    print("="*60)
    
    mixed_recipients = ['valid_user', 'invalid@@@', 'another_user']
    
    # With skip_invalid=True (default), invalid recipients are skipped
    # Uncomment to send:
    # results = await app.send_text_to_users(
    #     mixed_recipients,
    #     "Test message",
    #     delay=5.0,  # 5 second delay between sends
    #     skip_invalid=True  # Skip invalid recipients
    # )
    
    # With skip_invalid=False, operation fails if any recipient is invalid
    # results = await app.send_text_to_users(
    #     mixed_recipients,
    #     "Test message",
    #     skip_invalid=False  # Fail on invalid recipients
    # )
    
    print("ℹ️  Custom options example (commented out)")
    
    # Shutdown
    await app.shutdown()
    print("\n✅ App shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
