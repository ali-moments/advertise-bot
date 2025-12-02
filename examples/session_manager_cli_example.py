"""
Example usage of Session Manager CLI

This example demonstrates how to use the SessionManagerCLI to manage
Telegram sessions through a command-line interface.
"""

import asyncio
from telegram_manager.manager import TelegramSessionManager
from cli.session_manager import SessionManagerCLI


async def main():
    """Main example function"""
    
    # Initialize session manager
    print("Initializing Telegram Session Manager...")
    manager = TelegramSessionManager(
        max_concurrent_operations=3,
        load_balancing_strategy="round_robin"
    )
    
    # Load sessions from database
    print("Loading sessions from database...")
    results = await manager.load_sessions_from_db()
    
    if not results:
        print("No sessions loaded. Please add sessions to the database first.")
        return
    
    print(f"Loaded {sum(results.values())}/{len(results)} sessions successfully\n")
    
    # Create CLI interface
    cli = SessionManagerCLI(manager)
    
    # Example 1: List all sessions
    print("=" * 60)
    print("Example 1: Listing all sessions")
    print("=" * 60)
    await cli.list_sessions()
    
    # Example 2: Show details for first session
    if manager.sessions:
        print("\n" + "=" * 60)
        print("Example 2: Showing session details")
        print("=" * 60)
        first_session = list(manager.sessions.keys())[0]
        await cli.show_session_details(first_session)
    
    # Example 3: Reload sessions
    print("\n" + "=" * 60)
    print("Example 3: Reloading sessions")
    print("=" * 60)
    await cli.reload_sessions()
    
    # Cleanup
    print("\nCleaning up...")
    await manager.disconnect_all()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())

