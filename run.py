"""
Telegram Bot Control Panel - Main Entry Point

This is the main entry point for running the bot.
Use this file to start the bot instead of running panel/bot.py directly.
"""

import asyncio
import logging
from telegram_manager.manager import TelegramSessionManager
from panel.bot import TelegramBotPanel

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point"""
    logger.info("🚀 Starting Telegram Bot Control Panel...")
    
    # Initialize session manager
    logger.info("Initializing session manager...")
    session_manager = TelegramSessionManager()
    
    # Load sessions from database
    # Returns Dict[str, bool] mapping session names to load success status
    loaded_sessions = await session_manager.load_sessions_from_db()
    
    if loaded_sessions:
        successful_sessions = sum(1 for success in loaded_sessions.values() if success)
        logger.info(f"✅ Loaded {successful_sessions}/{len(loaded_sessions)} sessions successfully")
        
        try:
            # Initialize bot panel
            bot_panel = TelegramBotPanel(session_manager)
            
            logger.info("Starting bot panel...")
            await bot_panel.run()
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Received shutdown signal...")
        except Exception as e:
            logger.error(f"❌ Application error: {e}", exc_info=True)
        finally:
            logger.info("Shutting down session manager...")
            await session_manager.shutdown()
            logger.info("✅ Shutdown complete")
    else:
        logger.error("❌ Failed to load any sessions from database")
        logger.error("Check that sessions exist in the database and session files are present")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
