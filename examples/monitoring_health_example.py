"""
Example demonstrating the get_monitoring_health() method

This example shows how to use the monitoring health check functionality
to get comprehensive status information about the monitoring system.
"""
import asyncio
import time
from telegram_manager.session import TelegramSession
from telegram_manager.config import MonitoringTarget
from telegram_manager.models import ReactionPool, ReactionConfig


async def demonstrate_monitoring_health():
    """Demonstrate the monitoring health check functionality"""
    
    # Create a session (in real usage, you would connect to Telegram)
    session = TelegramSession(
        session_file="demo.session",
        api_id=12345,
        api_hash="demo_hash"
    )
    
    print("=" * 60)
    print("Monitoring Health Check Demonstration")
    print("=" * 60)
    
    # Example 1: Check health when not monitoring
    print("\n1. Health check when NOT monitoring:")
    print("-" * 60)
    health = session.get_monitoring_health()
    print(f"   Is Monitoring: {health['is_monitoring']}")
    print(f"   Target Count: {health['target_count']}")
    print(f"   Queue Size: {health['queue_size']}")
    print(f"   Targets: {health['targets']}")
    
    # Example 2: Simulate active monitoring with targets
    print("\n2. Health check with ACTIVE monitoring:")
    print("-" * 60)
    
    # Simulate monitoring state
    session.is_monitoring = True
    
    # Create monitoring targets with statistics
    reaction_pool1 = ReactionPool(reactions=[
        ReactionConfig(emoji='👍', weight=5),
        ReactionConfig(emoji='❤️', weight=3),
        ReactionConfig(emoji='🔥', weight=2)
    ])
    
    target1 = MonitoringTarget(
        chat_id='@tech_news',
        reaction_pool=reaction_pool1,
        cooldown=1.0
    )
    target1.messages_processed = 42
    target1.reactions_sent = 38
    target1.reaction_failures = 4
    target1.last_reaction_time = time.time() - 5.0  # 5 seconds ago
    
    reaction_pool2 = ReactionPool(reactions=[
        ReactionConfig(emoji='😊', weight=10)
    ])
    
    target2 = MonitoringTarget(
        chat_id='@crypto_updates',
        reaction_pool=reaction_pool2,
        cooldown=2.0
    )
    target2.messages_processed = 128
    target2.reactions_sent = 120
    target2.reaction_failures = 8
    target2.last_reaction_time = time.time() - 12.0  # 12 seconds ago
    
    session.monitoring_targets = {
        '@tech_news': target1,
        '@crypto_updates': target2
    }
    
    # Simulate some queued reactions
    from collections import deque
    session.reaction_queue = deque(maxlen=100)
    for _ in range(7):
        session.reaction_queue.append({'mock': 'reaction'})
    
    # Get health status
    health = session.get_monitoring_health()
    
    print(f"   Is Monitoring: {health['is_monitoring']}")
    print(f"   Target Count: {health['target_count']}")
    print(f"   Queue Size: {health['queue_size']}")
    print(f"\n   Per-Target Details:")
    
    for target_id, target_health in health['targets'].items():
        print(f"\n   Target: {target_id}")
        print(f"      Messages Processed: {target_health['messages_processed']}")
        print(f"      Reactions Sent: {target_health['reactions_sent']}")
        print(f"      Reaction Failures: {target_health['reaction_failures']}")
        print(f"      Cooldown: {target_health['cooldown']}s")
        print(f"      Time Since Last Reaction: {target_health['time_since_last_reaction']:.2f}s")
        print(f"      Last Reaction Time: {target_health['last_reaction_time']:.2f}")
    
    # Example 3: Calculate success rate from health data
    print("\n3. Calculating metrics from health data:")
    print("-" * 60)
    
    for target_id, target_health in health['targets'].items():
        total_attempts = target_health['reactions_sent'] + target_health['reaction_failures']
        if total_attempts > 0:
            success_rate = (target_health['reactions_sent'] / total_attempts) * 100
            print(f"   {target_id}:")
            print(f"      Success Rate: {success_rate:.1f}%")
            print(f"      Processing Rate: {target_health['reactions_sent']}/{target_health['messages_processed']} messages")
    
    # Example 4: Detect potential issues
    print("\n4. Health issue detection:")
    print("-" * 60)
    
    issues_found = False
    
    # Check if monitoring is active but no targets
    if health['is_monitoring'] and health['target_count'] == 0:
        print("   ⚠️  WARNING: Monitoring is active but no targets configured")
        issues_found = True
    
    # Check for high failure rates
    for target_id, target_health in health['targets'].items():
        total_attempts = target_health['reactions_sent'] + target_health['reaction_failures']
        if total_attempts > 10:  # Only check if we have enough data
            failure_rate = (target_health['reaction_failures'] / total_attempts) * 100
            if failure_rate > 20:  # More than 20% failure rate
                print(f"   ⚠️  WARNING: High failure rate for {target_id}: {failure_rate:.1f}%")
                issues_found = True
    
    # Check for large queue backlog
    if health['queue_size'] > 50:
        print(f"   ⚠️  WARNING: Large reaction queue backlog: {health['queue_size']} pending")
        issues_found = True
    
    # Check for stale targets (no reactions in a long time)
    for target_id, target_health in health['targets'].items():
        if target_health['time_since_last_reaction'] > 300:  # 5 minutes
            print(f"   ⚠️  WARNING: No reactions sent to {target_id} in {target_health['time_since_last_reaction']:.0f}s")
            issues_found = True
    
    if not issues_found:
        print("   ✅ No issues detected - monitoring system is healthy!")
    
    print("\n" + "=" * 60)
    print("Demonstration complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_monitoring_health())
