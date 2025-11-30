"""
Example: Resumable Operations with Progress Tracking

This example demonstrates how to use resumable operations with checkpoint-based
progress tracking for large bulk sending operations that can be interrupted and resumed.

Requirements: 25.1, 25.2, 25.3, 25.4, 25.5
"""

import asyncio
import logging
from telegram_manager.main import TelegramManagerApp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_basic_resumable_send():
    """
    Example 1: Basic resumable send operation
    
    This demonstrates how to start a resumable operation that creates checkpoints
    and can be resumed if interrupted.
    """
    print("\n" + "="*60)
    print("Example 1: Basic Resumable Send")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        # Define a unique operation ID for this send
        # This ID is used to track progress and resume if interrupted
        operation_id = "bulk_send_2024_example_1"
        
        # Prepare recipients (in real scenario, this would be a large list)
        recipients = [f'user{i}' for i in range(100)]
        message = "Hello! This is a resumable bulk message."
        
        print(f"\n📤 Starting resumable send operation...")
        print(f"   Operation ID: {operation_id}")
        print(f"   Recipients: {len(recipients)}")
        print(f"   Resumable: Yes")
        
        # Send with resumable=True
        # This will create a checkpoint file that tracks progress
        result = await app.send_text_to_users(
            recipients=recipients,
            message=message,
            delay=1.0,
            skip_invalid=True,
            priority="normal"
        )
        
        # Note: For CSV-based sends, use send_from_csv_file with resumable=True
        # result = await app.send_from_csv_file(
        #     csv_path='recipients.csv',
        #     message=message,
        #     batch_size=1000,
        #     delay=2.0,
        #     resumable=True,
        #     operation_id=operation_id
        # )
        
        print(f"\n✅ Operation completed!")
        print(f"   Total: {len(result)}")
        print(f"   Succeeded: {sum(1 for r in result.values() if r.success)}")
        print(f"   Failed: {sum(1 for r in result.values() if not r.success)}")
        
    finally:
        await app.shutdown()


async def example_resume_interrupted_operation():
    """
    Example 2: Resume an interrupted operation
    
    This demonstrates how to resume an operation that was previously interrupted.
    The operation will skip recipients that were already processed successfully.
    """
    print("\n" + "="*60)
    print("Example 2: Resume Interrupted Operation")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        # Use the SAME operation ID as the interrupted operation
        operation_id = "bulk_send_2024_example_1"
        
        print(f"\n🔄 Attempting to resume operation...")
        print(f"   Operation ID: {operation_id}")
        print(f"   The system will check for existing checkpoint file")
        print(f"   and skip already-processed recipients")
        
        # When you call send_from_csv_file with the same operation_id,
        # it will automatically detect the checkpoint and resume
        result = await app.send_from_csv_file(
            csv_path='recipients.csv',
            message="Resumed message",
            batch_size=1000,
            delay=2.0,
            resumable=True,
            operation_id=operation_id  # Same ID = resume
        )
        
        print(f"\n✅ Resume completed!")
        print(f"   Total: {result.total}")
        print(f"   Succeeded: {result.succeeded}")
        print(f"   Failed: {result.failed}")
        print(f"   Duration: {result.duration:.2f}s")
        
    except FileNotFoundError:
        print("\n⚠️ CSV file not found - this is just an example")
        print("   In a real scenario, provide a valid CSV file path")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await app.shutdown()


async def example_progress_monitoring():
    """
    Example 3: Monitor progress during a long-running operation
    
    This demonstrates how progress tracking works during a resumable operation.
    """
    print("\n" + "="*60)
    print("Example 3: Progress Monitoring")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        operation_id = "bulk_send_2024_example_3"
        
        print(f"\n📊 Progress tracking information:")
        print(f"   - Checkpoint files are stored in .checkpoints/ directory")
        print(f"   - Each checkpoint contains:")
        print(f"     * Operation ID")
        print(f"     * Total recipients")
        print(f"     * Completed recipients (list)")
        print(f"     * Failed recipients (list)")
        print(f"     * Start time")
        print(f"   - Checkpoints are updated after each batch")
        print(f"   - Checkpoints are automatically cleaned up on completion")
        
        # In a real scenario, you would start the operation
        # and monitor the checkpoint file for progress
        
        print(f"\n💡 To monitor progress in real-time:")
        print(f"   1. Start a resumable operation")
        print(f"   2. Check .checkpoints/{operation_id}.json")
        print(f"   3. The file shows completed/failed recipients")
        print(f"   4. Calculate progress: completed / total * 100%")
        
    finally:
        await app.shutdown()


async def example_checkpoint_cleanup():
    """
    Example 4: Checkpoint cleanup behavior
    
    This demonstrates how checkpoints are automatically cleaned up
    when operations complete successfully.
    """
    print("\n" + "="*60)
    print("Example 4: Checkpoint Cleanup")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        print(f"\n🧹 Checkpoint cleanup behavior:")
        print(f"   - When operation completes successfully:")
        print(f"     * Checkpoint file is automatically deleted")
        print(f"     * This prevents stale checkpoints from accumulating")
        print(f"   - When operation is interrupted:")
        print(f"     * Checkpoint file remains for resumption")
        print(f"     * Contains all progress up to interruption point")
        print(f"   - When operation fails:")
        print(f"     * Checkpoint file remains for debugging")
        print(f"     * Can be manually deleted or used for retry")
        
        print(f"\n💡 Manual checkpoint management:")
        print(f"   - Checkpoint files: .checkpoints/<operation_id>.json")
        print(f"   - To start fresh: delete the checkpoint file")
        print(f"   - To resume: keep the checkpoint file and use same operation_id")
        
    finally:
        await app.shutdown()


async def example_batch_processing_with_checkpoints():
    """
    Example 5: Batch processing with checkpoint updates
    
    This demonstrates how checkpoints are updated after each batch
    during large CSV-based operations.
    """
    print("\n" + "="*60)
    print("Example 5: Batch Processing with Checkpoints")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        operation_id = "bulk_send_2024_example_5"
        
        print(f"\n📦 Batch processing with checkpoints:")
        print(f"   - Large CSV files are processed in batches")
        print(f"   - Default batch size: 1000 recipients")
        print(f"   - After each batch:")
        print(f"     * Checkpoint file is updated")
        print(f"     * Progress is saved to disk")
        print(f"     * Memory is released")
        print(f"   - If interrupted:")
        print(f"     * Resume from last completed batch")
        print(f"     * No duplicate sends to completed recipients")
        
        print(f"\n💡 Batch size recommendations:")
        print(f"   - Small batches (100): More frequent checkpoints, slower")
        print(f"   - Medium batches (1000): Balanced (recommended)")
        print(f"   - Large batches (10000): Faster, but less frequent checkpoints")
        
        # Example with custom batch size
        print(f"\n📤 Example with custom batch size:")
        print(f"   result = await app.send_from_csv_file(")
        print(f"       csv_path='large_recipients.csv',")
        print(f"       message='Bulk message',")
        print(f"       batch_size=500,  # Custom batch size")
        print(f"       delay=2.0,")
        print(f"       resumable=True,")
        print(f"       operation_id='{operation_id}'")
        print(f"   )")
        
    finally:
        await app.shutdown()


async def example_error_handling_with_resume():
    """
    Example 6: Error handling and resumption
    
    This demonstrates how to handle errors and resume operations
    after fixing issues.
    """
    print("\n" + "="*60)
    print("Example 6: Error Handling with Resume")
    print("="*60)
    
    app = TelegramManagerApp()
    
    try:
        # Initialize app
        print("\n📱 Initializing app...")
        await app.initialize()
        
        print(f"\n🔧 Error handling strategies:")
        print(f"   1. Transient errors (network issues):")
        print(f"      - Automatically retried with exponential backoff")
        print(f"      - Progress is saved before retry")
        print(f"      - Operation continues after retry")
        print(f"   2. Permanent errors (invalid recipient):")
        print(f"      - Marked as failed in checkpoint")
        print(f"      - Operation continues with next recipient")
        print(f"      - Failed recipients listed in final result")
        print(f"   3. Critical errors (session disconnected):")
        print(f"      - Operation is interrupted")
        print(f"      - Checkpoint saved with current progress")
        print(f"      - Can be resumed after fixing issue")
        
        print(f"\n💡 Resumption after errors:")
        print(f"   1. Check the error in logs")
        print(f"   2. Fix the underlying issue (e.g., reconnect session)")
        print(f"   3. Resume with same operation_id")
        print(f"   4. System skips completed recipients")
        print(f"   5. Retries failed recipients (if transient)")
        
        print(f"\n📊 Failed recipient handling:")
        print(f"   - Failed recipients are tracked in checkpoint")
        print(f"   - Final result includes all failures with error messages")
        print(f"   - You can extract failed recipients for manual review")
        print(f"   - Example:")
        print(f"       failed = [r for r, res in result.results.items() if not res.success]")
        print(f"       print(f'Failed recipients: {{failed}}')")
        
    finally:
        await app.shutdown()


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("Resumable Operations Examples")
    print("="*60)
    print("\nThese examples demonstrate checkpoint-based resumable operations")
    print("for large bulk sending tasks that can be interrupted and resumed.")
    
    # Run examples
    await example_basic_resumable_send()
    
    # Uncomment to run other examples:
    # await example_resume_interrupted_operation()
    # await example_progress_monitoring()
    # await example_checkpoint_cleanup()
    # await example_batch_processing_with_checkpoints()
    # await example_error_handling_with_resume()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
