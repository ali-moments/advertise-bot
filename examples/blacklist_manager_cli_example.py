"""
Example usage of Blacklist Manager CLI

This example demonstrates how to use the BlacklistManagerCLI to manage
the user blacklist through an interactive command-line interface.
"""

import asyncio
from telegram_manager.blacklist import BlocklistManager
from cli.blacklist_manager import BlacklistManagerCLI


async def main():
    """Main example function"""
    
    # Initialize blacklist manager
    blacklist_manager = BlocklistManager(storage_path='sessions/blacklist.json')
    await blacklist_manager.load()
    
    # Create CLI interface
    cli = BlacklistManagerCLI(blacklist_manager)
    
    # Show the interactive menu
    cli.show_menu()


if __name__ == '__main__':
    asyncio.run(main())
