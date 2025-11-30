"""
State Management Example

Demonstrates how to use the StateManager for managing user sessions,
operation progress, and monitoring configurations.

Requirements: AC-6.3, AC-6.4
"""

import asyncio
import time
from panel.state_manager import StateManager


async def example_user_session():
    """Example: Managing user sessions during conversations"""
    print("\n=== User Session Management Example ===\n")
    
    state_manager = StateManager()
    
    # Simulate user starting a scraping operation
    user_id = 123456
    
    # Create session
    print(f"Creating session for user {user_id}...")
    session = state_manager.create_user_session(
        user_id=user_id,
        operation='scraping',
        step='select_type',
        data={'started_from': 'menu'}
    )
    print(f"✓ Session created: {session.operation} - {session.step}")
    
    # User selects bulk scraping
    print("\nUser selects bulk scraping...")
    state_manager.update_user_session(
        user_id=user_id,
        step='get_links',
        data={'scrape_type': 'bulk'}
    )
    session = state_manager.get_user_session(user_id)
    print(f"✓ Session updated: step={session.step}, type={session.get_data('scrape_type')}")
    
    # User provides links
    print("\nUser provides group links...")
    links = ['@group1', '@group2', '@group3']
    state_manager.update_user_session(
        user_id=user_id,
        step='confirm',
        data={'targets': links}
    )
    session = state_manager.get_user_session(user_id)
    print(f"✓ Session updated: {len(session.get_data('targets'))} targets")
    
    # User confirms
    print("\nUser confirms operation...")
    state_manager.update_user_session(
        user_id=user_id,
        step='execute'
    )
    
    # Operation completes
    print("\nOperation completes, cleaning up session...")
    state_manager.delete_user_session(user_id)
    print("✓ Session deleted")
    
    # Verify deletion
    session = state_manager.get_user_session(user_id)
    print(f"✓ Session exists: {session is not None}")


async def example_operation_progress():
    """Example: Tracking operation progress"""
    print("\n=== Operation Progress Tracking Example ===\n")
    
    state_manager = StateManager()
    
    # Create progress tracker for bulk scraping
    operation_id = f'scrape_{int(time.time())}'
    total_groups = 10
    
    print(f"Creating progress tracker for {total_groups} groups...")
    progress = state_manager.create_operation_progress(
        operation_id=operation_id,
        operation_type='scraping',
        total=total_groups,
        user_id=123456,
        message_id=789
    )
    print(f"✓ Progress tracker created: {operation_id}")
    
    # Simulate scraping with progress updates
    print("\nSimulating scraping operation...")
    for i in range(total_groups):
        await asyncio.sleep(0.2)  # Simulate work
        
        # Randomly succeed or fail
        if i % 3 == 0:
            progress.increment_failed()
            print(f"  Group {i+1}: Failed")
        else:
            progress.increment_completed()
            print(f"  Group {i+1}: Success")
        
        # Show progress
        print(f"  Progress: {progress.progress_percent:.1f}% "
              f"({progress.completed} success, {progress.failed} failed, "
              f"{progress.remaining} remaining)")
        
        if progress.estimated_remaining_seconds:
            print(f"  Estimated time remaining: {progress.estimated_remaining_seconds:.1f}s")
    
    # Mark as completed
    print("\nMarking operation as completed...")
    progress.mark_completed({
        'total_members': progress.completed * 50,
        'groups_scraped': progress.completed
    })
    print(f"✓ Operation completed with {progress.success_rate:.1f}% success rate")
    print(f"✓ Result data: {progress.result_data}")
    
    # Clean up
    state_manager.delete_operation_progress(operation_id)
    print("✓ Progress tracker deleted")


async def example_monitoring_config():
    """Example: Managing monitoring configurations"""
    print("\n=== Monitoring Configuration Example ===\n")
    
    state_manager = StateManager()
    
    # Add channel to monitoring
    chat_id = '@channel1'
    print(f"Adding channel {chat_id} to monitoring...")
    
    config = state_manager.create_monitoring_config(
        chat_id=chat_id,
        reactions=[
            {'emoji': '👍', 'weight': 5},
            {'emoji': '❤️', 'weight': 3}
        ],
        cooldown=2.0,
        enabled=True
    )
    print(f"✓ Monitoring config created")
    print(f"  Reactions: {config.reactions}")
    print(f"  Cooldown: {config.cooldown}s")
    
    # Add another reaction
    print("\nAdding 🔥 reaction...")
    config.add_reaction('🔥', 2)
    print(f"✓ Reaction added: {config.reactions}")
    
    # Update existing reaction
    print("\nUpdating 👍 weight to 10...")
    config.add_reaction('👍', 10)
    print(f"✓ Reaction updated: {config.get_reaction_weight('👍')}")
    
    # Simulate monitoring activity
    print("\nSimulating monitoring activity...")
    for i in range(5):
        config.increment_messages_processed()
        if i % 2 == 0:
            config.increment_reactions_sent()
    
    print(f"✓ Stats: {config.stats}")
    
    # Add more channels
    print("\nAdding more channels...")
    state_manager.create_monitoring_config('@channel2', enabled=True)
    state_manager.create_monitoring_config('@channel3', enabled=False)
    
    # Get enabled channels
    enabled = state_manager.get_enabled_monitoring_configs()
    print(f"✓ Enabled channels: {len(enabled)}")
    for cfg in enabled:
        print(f"  - {cfg.chat_id}: {cfg.stats['reactions_sent']} reactions sent")
    
    # Clean up
    state_manager.delete_monitoring_config('@channel1')
    state_manager.delete_monitoring_config('@channel2')
    state_manager.delete_monitoring_config('@channel3')
    print("\n✓ Monitoring configs deleted")


async def example_concurrent_operations():
    """Example: Managing multiple concurrent operations"""
    print("\n=== Concurrent Operations Example ===\n")
    
    state_manager = StateManager()
    
    # Create multiple user sessions
    print("Creating sessions for 3 users...")
    for user_id in [111, 222, 333]:
        state_manager.create_user_session(
            user_id=user_id,
            operation='scraping' if user_id % 2 == 0 else 'sending',
            step='execute'
        )
    print(f"✓ Created {len(state_manager.user_sessions)} sessions")
    
    # Create multiple operations
    print("\nCreating operations for 3 users...")
    for i, user_id in enumerate([111, 222, 333]):
        state_manager.create_operation_progress(
            operation_id=f'op_{user_id}',
            operation_type='scraping' if i % 2 == 0 else 'sending',
            total=100,
            user_id=user_id
        )
    print(f"✓ Created {len(state_manager.operation_progress)} operations")
    
    # Simulate concurrent progress
    print("\nSimulating concurrent progress...")
    for _ in range(5):
        for op_id in ['op_111', 'op_222', 'op_333']:
            state_manager.update_operation_progress(
                operation_id=op_id,
                increment_completed=True
            )
        await asyncio.sleep(0.1)
    
    # Get statistics
    print("\nGetting statistics...")
    stats = state_manager.get_stats()
    print(f"✓ User sessions: {stats['user_sessions']}")
    print(f"✓ Total operations: {stats['total_operations']}")
    print(f"✓ Active operations: {stats['active_operations']}")
    print(f"✓ Operations by type: {stats['operations_by_type']}")
    print(f"✓ Sessions by operation: {stats['sessions_by_operation']}")
    
    # Get user-specific operations
    print("\nGetting operations for user 111...")
    user_ops = state_manager.get_user_operations(111)
    print(f"✓ User 111 has {len(user_ops)} operations")
    for op in user_ops:
        print(f"  - {op.operation_id}: {op.completed}/{op.total} completed")
    
    # Clean up
    print("\nCleaning up...")
    state_manager.clear_all_user_sessions()
    for op_id in ['op_111', 'op_222', 'op_333']:
        state_manager.delete_operation_progress(op_id)
    print("✓ All cleaned up")


async def example_cleanup():
    """Example: Automatic cleanup of expired sessions"""
    print("\n=== Automatic Cleanup Example ===\n")
    
    state_manager = StateManager(session_timeout=2, cleanup_interval=1)
    
    # Create some sessions
    print("Creating sessions...")
    state_manager.create_user_session(111, 'scraping', 'step1')
    state_manager.create_user_session(222, 'sending', 'step1')
    print(f"✓ Created {len(state_manager.user_sessions)} sessions")
    
    # Create some operations
    print("\nCreating operations...")
    state_manager.create_operation_progress('op1', 'scraping', 100)
    state_manager.create_operation_progress('op2', 'sending', 50)
    
    # Mark one as completed
    progress = state_manager.get_operation_progress('op1')
    progress.mark_completed()
    progress.started_at = time.time() - 3700  # Make it old
    
    print(f"✓ Created {len(state_manager.operation_progress)} operations")
    
    # Wait for sessions to expire
    print("\nWaiting for sessions to expire (3 seconds)...")
    await asyncio.sleep(3)
    
    # Manual cleanup
    print("\nRunning manual cleanup...")
    expired_sessions = await state_manager.cleanup_expired_sessions()
    completed_ops = await state_manager.cleanup_completed_operations(max_age=3600)
    
    print(f"✓ Cleaned up {expired_sessions} expired sessions")
    print(f"✓ Cleaned up {completed_ops} completed operations")
    print(f"✓ Remaining sessions: {len(state_manager.user_sessions)}")
    print(f"✓ Remaining operations: {len(state_manager.operation_progress)}")


async def example_real_world_scenario():
    """Example: Real-world bulk scraping scenario"""
    print("\n=== Real-World Bulk Scraping Scenario ===\n")
    
    state_manager = StateManager()
    user_id = 123456
    
    # Step 1: User starts conversation
    print("Step 1: User starts scraping conversation")
    session = state_manager.create_user_session(
        user_id=user_id,
        operation='scraping',
        step='select_type'
    )
    print(f"✓ Session created")
    
    # Step 2: User selects bulk scraping
    print("\nStep 2: User selects bulk scraping")
    state_manager.update_user_session(
        user_id=user_id,
        step='get_links',
        data={'scrape_type': 'bulk'}
    )
    print(f"✓ Session updated")
    
    # Step 3: User provides links
    print("\nStep 3: User provides group links")
    links = ['@group1', '@group2', '@group3', '@group4', '@group5']
    state_manager.update_user_session(
        user_id=user_id,
        step='confirm',
        data={'targets': links}
    )
    print(f"✓ {len(links)} targets added")
    
    # Step 4: User confirms
    print("\nStep 4: User confirms operation")
    session = state_manager.get_user_session(user_id)
    targets = session.get_data('targets')
    
    # Create progress tracker
    operation_id = f'scrape_{user_id}_{int(time.time())}'
    progress = state_manager.create_operation_progress(
        operation_id=operation_id,
        operation_type='scraping',
        total=len(targets),
        user_id=user_id
    )
    print(f"✓ Progress tracker created")
    
    # Step 5: Execute scraping
    print("\nStep 5: Executing bulk scraping")
    for i, target in enumerate(targets):
        await asyncio.sleep(0.3)  # Simulate scraping
        
        # Simulate success/failure
        if i == 2:  # Simulate one failure
            progress.increment_failed()
            print(f"  {target}: ❌ Failed")
        else:
            progress.increment_completed()
            print(f"  {target}: ✓ Success ({progress.completed * 50} members)")
        
        # Show progress
        print(f"    Progress: {progress.progress_percent:.1f}% "
              f"(Success rate: {progress.success_rate:.1f}%)")
    
    # Step 6: Complete operation
    print("\nStep 6: Operation completed")
    progress.mark_completed({
        'total_members': progress.completed * 50,
        'groups_scraped': progress.completed,
        'groups_failed': progress.failed
    })
    
    print(f"✓ Scraping completed:")
    print(f"  - Groups scraped: {progress.completed}/{progress.total}")
    print(f"  - Total members: {progress.result_data['total_members']}")
    print(f"  - Success rate: {progress.success_rate:.1f}%")
    print(f"  - Time taken: {progress.elapsed_seconds:.1f}s")
    
    # Step 7: Clean up
    print("\nStep 7: Cleaning up")
    state_manager.delete_user_session(user_id)
    state_manager.delete_operation_progress(operation_id)
    print("✓ Session and progress tracker deleted")


async def main():
    """Run all examples"""
    print("=" * 60)
    print("State Management Examples")
    print("=" * 60)
    
    await example_user_session()
    await example_operation_progress()
    await example_monitoring_config()
    await example_concurrent_operations()
    await example_cleanup()
    await example_real_world_scenario()
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
