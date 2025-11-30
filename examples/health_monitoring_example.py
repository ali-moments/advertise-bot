"""
Example: Automatic Session Health Monitoring

This example demonstrates how SessionHealthMonitor is automatically integrated
into TelegramSessionManager to provide automatic session health monitoring,
disconnection detection, and reconnection handling.

Task 18: Integrate SessionHealthMonitor into TelegramSessionManager
Requirements: 16.1, 16.2, 16.4
"""

import asyncio
import logging
from telegram_manager.main import TelegramManagerApp

# Setup logging to see health monitoring events
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """
    Demonstrate automatic health monitoring integration
    """
    print("=" * 80)
    print("Session Health Monitoring Integration Example")
    print("=" * 80)
    
    # Initialize the application
    app = TelegramManagerApp()
    
    print("\n1. Initializing application and loading sessions...")
    print("   (Health monitoring will start automatically)")
    
    success = await app.initialize()
    
    if not success:
        print("❌ Failed to initialize application")
        return
    
    print(f"✅ Application initialized with {len(app.manager.sessions)} sessions")
    
    # Check health monitoring status
    print("\n2. Checking health monitoring status...")
    
    if app.manager.health_monitor.is_monitoring:
        print("✅ Health monitoring is ACTIVE")
        print(f"   - Monitoring {len(app.manager.health_monitor.sessions)} sessions")
        print(f"   - Check interval: {app.manager.health_monitor.CHECK_INTERVAL}s")
        print(f"   - Max reconnection attempts: {app.manager.health_monitor.MAX_RECONNECT_ATTEMPTS}")
    else:
        print("❌ Health monitoring is NOT active")
    
    # Display health status for all sessions
    print("\n3. Session health status:")
    
    health_statuses = app.manager.health_monitor.get_all_health_statuses()
    
    for session_name, status in health_statuses.items():
        health_icon = "✅" if status.is_healthy else "❌"
        print(f"   {health_icon} {session_name}:")
        print(f"      - Healthy: {status.is_healthy}")
        print(f"      - Last check: {status.last_check_time:.2f}")
        print(f"      - Consecutive failures: {status.consecutive_failures}")
        if status.last_error:
            print(f"      - Last error: {status.last_error}")
    
    # Display available vs failed sessions
    print("\n4. Session availability:")
    
    available_sessions = app.manager.health_monitor.get_available_sessions()
    failed_sessions = app.manager.health_monitor.get_failed_sessions()
    
    print(f"   ✅ Available sessions: {len(available_sessions)}")
    for session_name in available_sessions:
        print(f"      - {session_name}")
    
    if failed_sessions:
        print(f"   ❌ Failed sessions: {len(failed_sessions)}")
        for session_name in failed_sessions:
            print(f"      - {session_name}")
    else:
        print(f"   ✅ No failed sessions")
    
    # Wait a bit to allow health checks to run
    print("\n5. Waiting 35 seconds to observe health check cycle...")
    print("   (Health checks run every 30 seconds)")
    
    await asyncio.sleep(35)
    
    # Check health status again
    print("\n6. Session health status after health check cycle:")
    
    health_statuses = app.manager.health_monitor.get_all_health_statuses()
    
    for session_name, status in health_statuses.items():
        health_icon = "✅" if status.is_healthy else "❌"
        print(f"   {health_icon} {session_name}:")
        print(f"      - Healthy: {status.is_healthy}")
        print(f"      - Last check: {status.last_check_time:.2f}")
        print(f"      - Consecutive failures: {status.consecutive_failures}")
    
    # Demonstrate graceful shutdown
    print("\n7. Shutting down application...")
    print("   (Health monitoring will stop automatically)")
    
    await app.shutdown()
    
    # Verify health monitoring stopped
    if not app.manager.health_monitor.is_monitoring:
        print("✅ Health monitoring stopped successfully")
    else:
        print("⚠️ Health monitoring still active")
    
    print("\n" + "=" * 80)
    print("Example completed!")
    print("=" * 80)
    
    print("\nKey Features Demonstrated:")
    print("  ✅ Automatic health monitoring startup on session load")
    print("  ✅ Periodic health checks (every 30 seconds)")
    print("  ✅ Session health status tracking")
    print("  ✅ Failed session detection and exclusion")
    print("  ✅ Automatic health monitoring shutdown")
    print("\nBenefits:")
    print("  • No manual intervention required")
    print("  • Automatic session reconnection on disconnection")
    print("  • Failed sessions excluded from load balancing")
    print("  • Comprehensive health event logging")
    print("  • Clean resource cleanup on shutdown")


if __name__ == "__main__":
    asyncio.run(main())
