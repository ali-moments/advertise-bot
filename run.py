import asyncio
import logging
from telegram_manager.main import TelegramManagerApp
from panel.bot import TelegramBotPanel
from telegram_manager.constants import print_telegram_config
from panel.config import print_panel_config

async def main():
    """Main application entry point"""
    # Print configurations for debugging
    print_telegram_config()
    print_panel_config()
    
    # Initialize session manager
    session_manager = TelegramManagerApp()
    
    if await session_manager.initialize():
        try:
            # Initialize bot panel
            bot_panel = TelegramBotPanel(session_manager)
            
            print("🚀 Starting Telegram Bot Panel...")
            await bot_panel.run()
            
        except Exception as e:
            logging.error(f"Application error: {e}")
        finally:
            await session_manager.shutdown()
    else:
        logging.error("❌ Failed to initialize session manager")

if __name__ == "__main__":
    asyncio.run(main())