"""
Example usage of Scraper CLI Module

This example demonstrates how to use the ScraperCLI class to scrape
members, messages, and links from Telegram channels.
"""

import asyncio
from telegram_manager.manager import TelegramSessionManager
from cli.scraper import ScraperCLI


async def main():
    """Main example function"""
    
    # Initialize session manager
    session_manager = TelegramSessionManager()
    
    # Load sessions from database
    print("Loading sessions...")
    results = await session_manager.load_sessions_from_db()
    
    if not any(results.values()):
        print("❌ No sessions loaded successfully")
        return
    
    print(f"✅ Loaded {sum(results.values())} sessions")
    
    # Create scraper CLI instance
    scraper = ScraperCLI(session_manager)
    
    # Example 1: Show the scraper menu (interactive)
    # Uncomment to run interactively
    # scraper.show_menu()
    
    # Example 2: Programmatic scraping (for automation)
    print("\n" + "="*50)
    print("Example: Scraping members programmatically")
    print("="*50)
    
    # Note: In actual usage, you would call these methods directly
    # or use the interactive menu via show_menu()
    
    # The scraper provides three main operations:
    # 1. scrape_members() - Scrape channel members
    # 2. scrape_messages() - Scrape channel messages
    # 3. scrape_links() - Extract and analyze links from messages
    
    print("\nScraper CLI is ready!")
    print("Use scraper.show_menu() for interactive mode")
    print("Or call methods directly for automation:")
    print("  - await scraper.scrape_members()")
    print("  - await scraper.scrape_messages()")
    print("  - await scraper.scrape_links()")
    
    # Cleanup
    await session_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
