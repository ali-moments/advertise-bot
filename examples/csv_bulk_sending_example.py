"""
Example: CSV-based bulk message sending

This example demonstrates how to send messages to recipients from a CSV file
with batch processing, progress tracking, and resumable operations.
"""

import asyncio
import logging
from telegram_manager.manager import TelegramSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    """Main example function"""
    
    # Initialize session manager
    manager = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy='least_loaded'
    )
    
    # Load sessions from database
    print("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    
    if not load_results:
        print("❌ No sessions loaded. Please add sessions to the database first.")
        return
    
    print(f"✅ Loaded {len(load_results)} sessions")
    
    # Example 1: Basic CSV sending
    print("\n" + "="*60)
    print("Example 1: Basic CSV Sending")
    print("="*60)
    
    csv_path = 'data/recipients.csv'  # Your CSV file path
    message = """
Hello! This is a test message sent via the Telegram bulk sender.

This message was sent using CSV-based bulk sending with:
- Automatic batch processing
- Load balancing across multiple sessions
- Progress tracking
- Error handling

Thank you!
"""
    
    try:
        result = await manager.send_from_csv(
            csv_path=csv_path,
            message=message,
            batch_size=100,  # Process 100 recipients per batch
            delay=2.0,  # 2 second delay between sends
            resumable=False  # Disable resumable for this example
        )
        
        print(f"\n✅ Sending complete!")
        print(f"   Total: {result.total}")
        print(f"   Succeeded: {result.succeeded}")
        print(f"   Failed: {result.failed}")
        print(f"   Duration: {result.duration:.1f}s")
        print(f"   Operation ID: {result.operation_id}")
        
        # Show some sample results
        print(f"\n📊 Sample results:")
        for i, (recipient, msg_result) in enumerate(list(result.results.items())[:5]):
            status = "✅" if msg_result.success else "❌"
            print(f"   {status} {recipient}: {msg_result.session_used}")
            if msg_result.error:
                print(f"      Error: {msg_result.error}")
        
        if len(result.results) > 5:
            print(f"   ... and {len(result.results) - 5} more")
    
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_path}")
        print("   Please create a CSV file with recipient identifiers.")
        print("   Format: One column with usernames or user IDs")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 2: Resumable CSV sending with large file
    print("\n" + "="*60)
    print("Example 2: Resumable CSV Sending (Large File)")
    print("="*60)
    
    large_csv_path = 'data/large_recipients.csv'  # Your large CSV file
    operation_id = 'bulk_send_2024_01'  # Unique operation ID
    
    print(f"This example demonstrates resumable operations.")
    print(f"If the operation is interrupted, you can resume it by running")
    print(f"the same command with the same operation_id.")
    
    try:
        result = await manager.send_from_csv(
            csv_path=large_csv_path,
            message=message,
            batch_size=1000,  # Larger batch size for efficiency
            delay=2.0,
            resumable=True,  # Enable resumable operations
            operation_id=operation_id  # Specify operation ID for resuming
        )
        
        print(f"\n✅ Sending complete!")
        print(f"   Total: {result.total}")
        print(f"   Succeeded: {result.succeeded}")
        print(f"   Failed: {result.failed}")
        print(f"   Duration: {result.duration:.1f}s")
        
    except FileNotFoundError:
        print(f"ℹ️  Large CSV file not found: {large_csv_path}")
        print("   This is optional - only needed for large file testing")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 3: CSV sending with custom batch size
    print("\n" + "="*60)
    print("Example 3: Custom Batch Size")
    print("="*60)
    
    print("Batch size affects memory usage and progress granularity:")
    print("  - Small batch (100): More frequent progress updates, higher overhead")
    print("  - Medium batch (1000): Balanced approach (recommended)")
    print("  - Large batch (10000): Less overhead, but less frequent updates")
    
    # Shutdown
    print("\n" + "="*60)
    print("Shutting down...")
    print("="*60)
    await manager.shutdown()
    print("✅ Shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
