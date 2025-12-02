#!/usr/bin/env python3
"""
Monitoring Verification Test Script

This script verifies that the monitoring and reaction system is working correctly.
It checks monitoring status, displays statistics, and tests reaction functionality.

Requirements: 1.1, 1.2, 3.1, 6.1, 6.2, 6.3

Usage:
    python test_monitoring.py
"""

import asyncio
import logging
import time
from typing import Dict, Any
from telegram_manager.manager import TelegramSessionManager
from telegram_manager.config import MonitoringTarget
from telegram_manager.models import ReactionPool, ReactionConfig


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MonitoringVerification")


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{title}")
    print("-" * 80)


async def verify_monitoring_status(manager: TelegramSessionManager) -> Dict[str, bool]:
    """
    Verify monitoring status for all sessions
    
    Requirements: 1.1, 1.2
    
    Args:
        manager: TelegramSessionManager instance
        
    Returns:
        Dict mapping session names to monitoring status
    """
    print_section("1. Monitoring Status Verification")
    
    monitoring_status = {}
    
    for session_name, session in manager.sessions.items():
        is_monitoring = session.is_monitoring
        monitoring_status[session_name] = is_monitoring
        
        status_icon = "✅" if is_monitoring else "❌"
        print(f"   {status_icon} {session_name}: {'MONITORING' if is_monitoring else 'NOT MONITORING'}")
    
    # Summary
    active_count = sum(1 for status in monitoring_status.values() if status)
    total_count = len(monitoring_status)
    
    print(f"\n   Summary: {active_count}/{total_count} sessions are actively monitoring")
    
    if active_count == 0:
        print("   ⚠️  WARNING: No sessions are monitoring!")
    elif active_count < total_count:
        print(f"   ⚠️  WARNING: {total_count - active_count} sessions are not monitoring")
    else:
        print("   ✅ All sessions are monitoring")
    
    return monitoring_status


async def display_monitoring_health(manager: TelegramSessionManager):
    """
    Display monitoring health for all sessions
    
    Requirements: 6.1, 6.2, 6.3
    
    Args:
        manager: TelegramSessionManager instance
    """
    print_section("2. Monitoring Health Status")
    
    for session_name, session in manager.sessions.items():
        print(f"\n   Session: {session_name}")
        
        # Get health status
        health = session.get_monitoring_health()
        
        # Display overall status (Requirement 6.1)
        print(f"      Is Monitoring: {health['is_monitoring']}")
        print(f"      Target Count: {health['target_count']}")
        print(f"      Queue Size: {health['queue_size']}")
        
        # Display per-target statistics (Requirements 6.2, 6.3)
        if health['targets']:
            print(f"\n      Targets:")
            for target_id, target_health in health['targets'].items():
                print(f"\n         {target_id}:")
                print(f"            Messages Processed: {target_health['messages_processed']}")
                print(f"            Reactions Sent: {target_health['reactions_sent']}")
                print(f"            Reaction Failures: {target_health['reaction_failures']}")
                print(f"            Cooldown: {target_health['cooldown']}s")
                print(f"            Time Since Last Reaction: {target_health['time_since_last_reaction']:.2f}s")
                
                # Calculate success rate
                total_attempts = target_health['reactions_sent'] + target_health['reaction_failures']
                if total_attempts > 0:
                    success_rate = (target_health['reactions_sent'] / total_attempts) * 100
                    print(f"            Success Rate: {success_rate:.1f}%")
        else:
            print(f"      No targets configured")


async def verify_event_handler_registration(manager: TelegramSessionManager):
    """
    Verify event handler registration for all sessions
    
    Requirement: 3.1
    
    Args:
        manager: TelegramSessionManager instance
    """
    print_section("3. Event Handler Registration Verification")
    
    for session_name, session in manager.sessions.items():
        has_handler = session._event_handler is not None
        handler_icon = "✅" if has_handler else "❌"
        
        print(f"   {handler_icon} {session_name}: Event handler {'REGISTERED' if has_handler else 'NOT REGISTERED'}")
        
        if has_handler:
            print(f"      Handler ID: {id(session._event_handler)}")
            print(f"      Target Count: {len(session.monitoring_targets)}")


async def test_cooldown_configuration(manager: TelegramSessionManager):
    """
    Test cooldown configuration for all monitoring targets
    
    Args:
        manager: TelegramSessionManager instance
    """
    print_section("4. Cooldown Configuration Test")
    
    all_correct = True
    
    for session_name, session in manager.sessions.items():
        print(f"\n   Session: {session_name}")
        
        if not session.monitoring_targets:
            print(f"      No targets configured")
            continue
        
        for target_id, target in session.monitoring_targets.items():
            cooldown = target.cooldown
            cooldown_icon = "✅" if cooldown == 1.0 else "⚠️"
            
            print(f"      {cooldown_icon} {target_id}: Cooldown = {cooldown}s")
            
            if cooldown != 1.0:
                print(f"         WARNING: Expected 1.0s, got {cooldown}s")
                all_correct = False
    
    if all_correct:
        print("\n   ✅ All targets have correct 1.0s cooldown")
    else:
        print("\n   ⚠️  Some targets have incorrect cooldown configuration")


async def detect_health_issues(manager: TelegramSessionManager):
    """
    Detect potential health issues in the monitoring system
    
    Args:
        manager: TelegramSessionManager instance
    """
    print_section("5. Health Issue Detection")
    
    issues_found = False
    
    for session_name, session in manager.sessions.items():
        health = session.get_monitoring_health()
        
        # Check if monitoring is active but no targets
        if health['is_monitoring'] and health['target_count'] == 0:
            print(f"   ⚠️  {session_name}: Monitoring active but no targets configured")
            issues_found = True
        
        # Check for high failure rates
        for target_id, target_health in health['targets'].items():
            total_attempts = target_health['reactions_sent'] + target_health['reaction_failures']
            if total_attempts > 10:  # Only check if we have enough data
                failure_rate = (target_health['reaction_failures'] / total_attempts) * 100
                if failure_rate > 20:  # More than 20% failure rate
                    print(f"   ⚠️  {session_name} - {target_id}: High failure rate ({failure_rate:.1f}%)")
                    issues_found = True
        
        # Check for large queue backlog
        if health['queue_size'] > 50:
            print(f"   ⚠️  {session_name}: Large reaction queue backlog ({health['queue_size']} pending)")
            issues_found = True
        
        # Check for stale targets (no reactions in a long time)
        for target_id, target_health in health['targets'].items():
            if target_health['messages_processed'] > 0 and target_health['time_since_last_reaction'] > 300:  # 5 minutes
                print(f"   ⚠️  {session_name} - {target_id}: No reactions in {target_health['time_since_last_reaction']:.0f}s")
                issues_found = True
    
    if not issues_found:
        print("   ✅ No health issues detected - monitoring system is healthy!")


async def display_summary(manager: TelegramSessionManager, monitoring_status: Dict[str, bool]):
    """
    Display summary of monitoring verification
    
    Args:
        manager: TelegramSessionManager instance
        monitoring_status: Dict mapping session names to monitoring status
    """
    print_section("6. Summary")
    
    total_sessions = len(manager.sessions)
    monitoring_sessions = sum(1 for status in monitoring_status.values() if status)
    
    # Count total targets and reactions
    total_targets = 0
    total_messages = 0
    total_reactions = 0
    total_failures = 0
    total_queue_size = 0
    
    for session in manager.sessions.values():
        health = session.get_monitoring_health()
        total_targets += health['target_count']
        total_queue_size += health['queue_size']
        
        for target_health in health['targets'].values():
            total_messages += target_health['messages_processed']
            total_reactions += target_health['reactions_sent']
            total_failures += target_health['reaction_failures']
    
    print(f"\n   Sessions:")
    print(f"      Total: {total_sessions}")
    print(f"      Monitoring: {monitoring_sessions}")
    print(f"      Not Monitoring: {total_sessions - monitoring_sessions}")
    
    print(f"\n   Targets:")
    print(f"      Total Targets: {total_targets}")
    print(f"      Total Queue Size: {total_queue_size}")
    
    print(f"\n   Statistics:")
    print(f"      Messages Processed: {total_messages}")
    print(f"      Reactions Sent: {total_reactions}")
    print(f"      Reaction Failures: {total_failures}")
    
    if total_messages > 0:
        reaction_rate = (total_reactions / total_messages) * 100
        print(f"      Reaction Rate: {reaction_rate:.1f}%")
    
    if total_reactions + total_failures > 0:
        success_rate = (total_reactions / (total_reactions + total_failures)) * 100
        print(f"      Success Rate: {success_rate:.1f}%")
    
    # Overall health assessment
    print(f"\n   Overall Health:")
    if monitoring_sessions == total_sessions and total_failures == 0:
        print(f"      ✅ EXCELLENT - All sessions monitoring with no failures")
    elif monitoring_sessions == total_sessions:
        print(f"      ✅ GOOD - All sessions monitoring")
    elif monitoring_sessions > 0:
        print(f"      ⚠️  FAIR - Some sessions not monitoring")
    else:
        print(f"      ❌ POOR - No sessions monitoring")


async def main():
    """Main verification function"""
    print_header("Monitoring System Verification")
    
    print("\nInitializing session manager...")
    
    # Create session manager
    manager = TelegramSessionManager()
    
    # Load sessions from database
    print("Loading sessions from database...")
    load_results = await manager.load_sessions_from_db()
    
    if not load_results:
        print("❌ Failed to load any sessions")
        return
    
    loaded_count = sum(1 for success in load_results.values() if success)
    print(f"✅ Loaded {loaded_count}/{len(load_results)} sessions successfully")
    
    # Wait a moment for sessions to stabilize
    await asyncio.sleep(2)
    
    # Run verification steps
    monitoring_status = await verify_monitoring_status(manager)
    await display_monitoring_health(manager)
    await verify_event_handler_registration(manager)
    await test_cooldown_configuration(manager)
    await detect_health_issues(manager)
    await display_summary(manager, monitoring_status)
    
    print_header("Verification Complete")
    
    # Cleanup
    print("\nCleaning up...")
    for session in manager.sessions.values():
        await session.disconnect()
    
    print("✅ Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
