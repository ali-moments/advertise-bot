"""
Main CLI application entry point

This module contains the main TelegramCLI class that provides the interactive
command-line interface for the Telegram session manager.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console

from telegram_manager.manager import TelegramSessionManager
from telegram_manager.blacklist import BlocklistManager
from cli.config_manager import ConfigManager
from cli.session_manager import SessionManagerCLI
from cli.channel_manager import ChannelManagerCLI
from cli.message_sender import MessageSenderCLI
from cli.scraper import ScraperCLI
from cli.job_scheduler import JobScheduler, JobSchedulerCLI
from cli.blacklist_manager import BlacklistManagerCLI
from cli.ui_components import UIComponents

# Get the project root directory using absolute path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Prepare log file path
log_dir = PROJECT_ROOT / 'cli'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / 'cli.log'

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False):
    """
    Configure logging with optional console output
    
    Args:
        verbose: If True, log to both file and console. If False, only log to file.
    
    This function sets up logging to always write to a file, but only writes to
    console (stdout) when verbose mode is enabled. This keeps the UI clean during
    normal operation while still maintaining a complete log file.
    
    Additionally, when not in verbose mode, noisy Telethon internal logs are
    suppressed to prevent cluttering the console with channel update messages
    and timestamp warnings.
    """
    handlers = [logging.FileHandler(str(log_file))]
    
    if verbose:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Suppress noisy Telethon logs unless verbose mode is enabled
    if not verbose:
        # Suppress "Got difference for channel" INFO messages
        logging.getLogger('telethon.client.updates').setLevel(logging.ERROR)
        # Suppress "Persistent timestamp outdated" WARNING messages
        logging.getLogger('telethon.client.users').setLevel(logging.ERROR)
        # Suppress other noisy Telethon components
        logging.getLogger('telethon.network').setLevel(logging.ERROR)
        logging.getLogger('telethon.client.telegrambaseclient').setLevel(logging.ERROR)


class TelegramCLI:
    """Main CLI application with interactive menu"""
    
    def __init__(self, config_path: str = 'cli/config.json', verbose: bool = False):
        """
        Initialize CLI with session manager and modules
        
        Args:
            config_path: Path to configuration file
            verbose: Enable verbose console logging
        
        Requirements: 7.1
        """
        # Configure logging based on verbose flag
        configure_logging(verbose)
        
        self.console = Console()
        self.ui = UIComponents(self.console)
        self.config_path = config_path
        self.verbose = verbose
        
        # Core components
        self.session_manager: Optional[TelegramSessionManager] = None
        self.blacklist_manager: Optional[BlocklistManager] = None
        self.config: Optional[ConfigManager] = None
        self.job_scheduler: Optional[JobScheduler] = None
        
        # CLI modules
        self.session_cli: Optional[SessionManagerCLI] = None
        self.channel_cli: Optional[ChannelManagerCLI] = None
        self.message_cli: Optional[MessageSenderCLI] = None
        self.scraper_cli: Optional[ScraperCLI] = None
        self.job_cli: Optional[JobSchedulerCLI] = None
        self.blacklist_cli: Optional[BlacklistManagerCLI] = None
        
        self.running = False
    
    async def preloop(self):
        """
        Load sessions and configuration before starting
        
        Initializes all components and loads sessions from database.
        
        Requirements: 7.1, 7.5, 9.1
        """
        try:
            # Log event loop identity for verification
            loop = asyncio.get_running_loop()
            logger.info(f"CLI preloop using event loop: {id(loop)}")
            
            self.ui.show_info("Initializing Telegram Manager CLI...")
            
            # Initialize configuration manager
            self.config = ConfigManager(self.config_path)
            await self.config.load()
            self.ui.show_success("Configuration loaded")
            
            # Initialize session manager
            self.session_manager = TelegramSessionManager()
            self.ui.show_info("Loading sessions from database...")
            
            # Load sessions
            results = await self.session_manager.load_sessions_from_db()
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            if success_count > 0:
                self.ui.show_success(f"Loaded {success_count}/{total_count} sessions")
            else:
                self.ui.show_warning("No sessions loaded")
            
            # Initialize blacklist manager
            self.blacklist_manager = BlocklistManager()
            await self.blacklist_manager.load()
            self.ui.show_success("Blacklist loaded")
            
            # Initialize job scheduler
            self.job_scheduler = JobScheduler(self.config)
            
            # Register job handlers
            self._register_job_handlers()
            
            # Start job scheduler
            await self.job_scheduler.start()
            self.ui.show_success("Job scheduler started")
            
            # Initialize CLI modules
            self.session_cli = SessionManagerCLI(self.session_manager, self.console)
            self.channel_cli = ChannelManagerCLI(self.config, self.console, self.session_manager)
            self.message_cli = MessageSenderCLI(self.session_manager, self.console)
            self.scraper_cli = ScraperCLI(self.session_manager, self.console)
            self.job_cli = JobSchedulerCLI(self.job_scheduler, self.console)
            self.blacklist_cli = BlacklistManagerCLI(self.blacklist_manager, self.console)
            
            # Auto-start monitoring for configured channels
            await self._auto_start_monitoring()
            
            self.ui.show_success("CLI initialized successfully")
            self.running = True
            
        except Exception as e:
            self.ui.show_error(f"Failed to initialize CLI: {e}")
            logger.error(f"Initialization error: {e}", exc_info=True)
            raise
    
    async def postloop(self):
        """
        Cleanup and save state on exit
        
        Saves configuration, stops scheduler, and disconnects sessions.
        
        Requirements: 7.5, 9.4
        """
        try:
            self.ui.show_info("Shutting down...")
            
            # Stop job scheduler
            if self.job_scheduler:
                await self.job_scheduler.stop()
                self.ui.show_success("Job scheduler stopped")
            
            # Save configuration
            if self.config:
                await self.config.save()
                self.ui.show_success("Configuration saved")
            
            # Blacklist auto-persists on modifications, no explicit save needed
            if self.blacklist_manager:
                self.ui.show_success("Blacklist state maintained")
            
            # Disconnect all sessions
            if self.session_manager and self.session_manager.sessions:
                self.ui.show_info("Disconnecting sessions...")
                for session_name, session in self.session_manager.sessions.items():
                    try:
                        if session.is_connected:
                            await session.disconnect()
                    except Exception as e:
                        logger.error(f"Error disconnecting session {session_name}: {e}")
                
                self.ui.show_success("Sessions disconnected")
            
            self.ui.show_success("Shutdown complete")
            self.running = False
            
        except Exception as e:
            self.ui.show_error(f"Error during shutdown: {e}")
            logger.error(f"Shutdown error: {e}", exc_info=True)
    
    async def _auto_start_monitoring(self):
        """
        Auto-start monitoring for configured channels on startup
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
        try:
            # Get all configured channels
            channels = self.config.get_channels()
            
            if not channels:
                logger.info("No channels configured - skipping auto-start monitoring")
                return
            
            # Filter channels with monitoring enabled
            monitoring_channels = [ch for ch in channels if ch.monitoring_enabled]
            
            if not monitoring_channels:
                logger.info("No channels have monitoring enabled - skipping auto-start monitoring")
                return
            
            self.ui.show_info(f"Auto-starting monitoring for {len(monitoring_channels)} channel(s)...")
            
            # Start monitoring for each session
            for session_name, session in self.session_manager.sessions.items():
                if not session.is_connected:
                    continue
                
                # Build monitoring targets
                monitoring_targets = []
                for channel in monitoring_channels:
                    # Convert reactions to dict format
                    reactions_dict = [
                        {'emoji': r.emoji, 'weight': r.weight}
                        for r in channel.reactions
                    ]
                    
                    target = {
                        'chat_id': channel.channel_id,
                        'reaction_pool': {
                            'reactions': reactions_dict
                        },
                        'cooldown': 1.0  # Default cooldown
                    }
                    monitoring_targets.append(target)
                
                # Start monitoring
                try:
                    success = await session.start_monitoring(monitoring_targets)
                    if success:
                        logger.info(f"Started monitoring on session {session_name} for {len(monitoring_targets)} channels")
                    else:
                        logger.warning(f"Failed to start monitoring on session {session_name}")
                except Exception as e:
                    logger.error(f"Error starting monitoring on session {session_name}: {e}")
            
            self.ui.show_success(f"Monitoring started for {len(monitoring_channels)} channel(s)")
            
        except Exception as e:
            logger.error(f"Error in auto-start monitoring: {e}", exc_info=True)
            self.ui.show_warning(f"Failed to auto-start monitoring: {e}")
    
    def _register_job_handlers(self):
        """Register handlers for different job types"""
        # Register scrape_links handler
        async def scrape_links_handler(job_config):
            """Handler for link scraping jobs"""
            from cli.scraper import ScraperCLI
            scraper = ScraperCLI(self.session_manager, self.console)
            # Execute link scraping with job parameters
            # This would be called by the scheduler
            logger.info(f"Executing link scraping job: {job_config.job_id}")
        
        # Register scrape_members handler
        async def scrape_members_handler(job_config):
            """Handler for member scraping jobs"""
            logger.info(f"Executing member scraping job: {job_config.job_id}")
        
        # Register scrape_messages handler
        async def scrape_messages_handler(job_config):
            """Handler for message scraping jobs"""
            logger.info(f"Executing message scraping job: {job_config.job_id}")
        
        # Register handlers with scheduler
        self.job_scheduler.register_handler('scrape_links', scrape_links_handler)
        self.job_scheduler.register_handler('scrape_members', scrape_members_handler)
        self.job_scheduler.register_handler('scrape_messages', scrape_messages_handler)
    
    def show_main_menu(self):
        """
        Display main menu with all available features
        
        Requirements: 7.1, 7.2
        """
        self.console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
        self.console.print("[bold cyan]   Telegram Manager CLI - Main Menu   [/bold cyan]")
        self.console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
        
        # Display status bar
        status_items = {}
        if self.session_manager and self.session_manager.sessions:
            active_sessions = sum(1 for s in self.session_manager.sessions.values() if s.is_connected)
            status_items['Sessions'] = f"{active_sessions}/{len(self.session_manager.sessions)} active"
        
        if self.config:
            channels = self.config.get_channels()
            status_items['Channels'] = str(len(channels))
            
            jobs = self.config.get_jobs()
            enabled_jobs = sum(1 for j in jobs if j.enabled)
            status_items['Jobs'] = f"{enabled_jobs}/{len(jobs)} enabled"
        
        if status_items:
            self.ui.show_status_bar(status_items)
        
        # Menu options with keyboard shortcuts
        self.console.print("  [bold]1.[/bold] [bold yellow](s)[/bold yellow] Session Management    - Load and manage Telegram sessions")
        self.console.print("  [bold]2.[/bold] [bold yellow](c)[/bold yellow] Channel Management    - Configure channels and reactions")
        self.console.print("  [bold]3.[/bold] [bold yellow](m)[/bold yellow] Send Messages         - Send text, media, or bulk messages")
        self.console.print("  [bold]4.[/bold] [bold yellow](r)[/bold yellow] Scraping Operations   - Scrape members, messages, or links")
        self.console.print("  [bold]5.[/bold] [bold yellow](j)[/bold yellow] Job Scheduler         - Manage scheduled recurring tasks")
        self.console.print("  [bold]6.[/bold] [bold yellow](b)[/bold yellow] Blacklist Management  - Manage blocked users")
        self.console.print("  [bold]7.[/bold] [bold yellow](h)[/bold yellow] Help                  - Show detailed help for all commands")
        self.console.print("  [bold]8.[/bold] [bold yellow](q)[/bold yellow] Exit                  - Save and exit the application")
        self.console.print("\n[dim]Tip: You can use numbers (1-8) or letters (s,c,m,r,j,b,h,q) to select options[/dim]")
        self.console.print()
    
    async def show_help_async(self):
        """
        Display help text for all commands - async version
        
        Requirements: 7.2
        """
        self.console.print("\n[bold cyan]═══ Help - Available Commands ═══[/bold cyan]\n")
        
        help_text = [
            ["1 / s", "Session Management", "List, reload, and view details of Telegram sessions"],
            ["2 / c", "Channel Management", "Add, edit, delete channels and manage reaction lists"],
            ["3 / m", "Send Messages", "Send text messages, media, or bulk messages from CSV"],
            ["4 / r", "Scraping Operations", "Scrape channel members, messages, or extract links"],
            ["5 / j", "Job Scheduler", "Create, edit, delete, and run scheduled jobs"],
            ["6 / b", "Blacklist Management", "Add, remove, check, and clear blacklisted users"],
            ["8 / q", "Exit", "Save configuration and exit the application"]
        ]
        
        self.ui.display_table(
            "Command Help",
            ["Shortcut", "Feature", "Description"],
            help_text
        )
        
        # Show keyboard shortcuts
        self.ui.show_keyboard_shortcuts()
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        await self.ui.prompt_input_async("")
    
    async def do_sessions(self):
        """
        Manage Telegram sessions
        
        Opens the session management submenu.
        
        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.2
        """
        try:
            await self.session_cli.show_menu()
        except Exception as e:
            self.ui.show_error(f"Error in session management: {e}")
            logger.error(f"Session management error: {e}", exc_info=True)
    
    async def do_channels(self):
        """
        Manage channels and reaction lists
        
        Opens the channel management submenu.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 7.2
        """
        try:
            await self.channel_cli.run()
        except Exception as e:
            self.ui.show_error(f"Error in channel management: {e}")
            logger.error(f"Channel management error: {e}", exc_info=True)
    
    async def do_send(self):
        """
        Send messages to recipients
        
        Opens the message sending submenu.
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.2
        """
        try:
            await self.message_cli.run()
        except Exception as e:
            self.ui.show_error(f"Error in message sending: {e}")
            logger.error(f"Message sending error: {e}", exc_info=True)
    
    async def do_scrape(self):
        """
        Scrape data from channels
        
        Opens the scraping operations submenu.
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.2
        """
        try:
            await self.scraper_cli.show_menu()
        except Exception as e:
            self.ui.show_error(f"Error in scraping operations: {e}")
            logger.error(f"Scraping error: {e}", exc_info=True)
    
    async def do_jobs(self):
        """
        Manage scheduled jobs
        
        Opens the job management submenu.
        
        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.2
        """
        try:
            await self.job_cli.show_menu()
        except Exception as e:
            self.ui.show_error(f"Error in job management: {e}")
            logger.error(f"Job management error: {e}", exc_info=True)
    
    async def do_blacklist(self):
        """
        Manage user blacklist
        
        Opens the blacklist management submenu.
        
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2
        """
        try:
            await self.blacklist_cli.show_menu()
        except Exception as e:
            self.ui.show_error(f"Error in blacklist management: {e}")
            logger.error(f"Blacklist management error: {e}", exc_info=True)
    
    async def do_exit(self):
        """
        Exit the CLI panel
        
        Confirms exit and performs cleanup.
        
        Requirements: 7.5
        """
        confirm = await self.ui.prompt_confirm_async(
            "Are you sure you want to exit?",
            default=True
        )
        
        if confirm:
            await self.postloop()
            return True
        return False
    
    async def run(self):
        """
        Main CLI loop
        
        Displays menu, handles user input, and routes to appropriate handlers.
        
        Requirements: 7.1, 7.2, 7.3, 7.4
        """
        # Log event loop identity for verification
        loop = asyncio.get_running_loop()
        logger.info(f"CLI run() using event loop: {id(loop)}")
        
        # Initialize
        await self.preloop()
        
        # Display welcome message
        self.console.print("\n[bold green]Welcome to Telegram Manager CLI![/bold green]")
        self.console.print("[dim]Type a number (1-8) or letter shortcut (s,c,m,r,j,b,h,q), or Ctrl+C to exit[/dim]\n")
        
        # Main loop
        while self.running:
            try:
                # Show main menu
                self.show_main_menu()
                
                # Get user choice - async input to avoid event loop conflicts
                choice = await self.ui.prompt_input_async("Enter your choice")
                choice = choice.lower().strip()
                
                # Map keyboard shortcuts to menu options
                shortcut_map = {
                    's': '1',  # Sessions
                    'c': '2',  # Channels
                    'm': '3',  # Messages
                    'r': '4',  # scRaping
                    'j': '5',  # Jobs
                    'b': '6',  # Blacklist
                    'h': '7',  # Help
                    'q': '8',  # Quit
                    'exit': '8',
                    'quit': '8'
                }
                
                # Convert shortcut to number if applicable
                if choice in shortcut_map:
                    choice = shortcut_map[choice]
                
                # Route to appropriate handler
                if choice == "1":
                    await self.do_sessions()
                
                elif choice == "2":
                    await self.do_channels()
                
                elif choice == "3":
                    await self.do_send()
                
                elif choice == "4":
                    await self.do_scrape()
                
                elif choice == "5":
                    await self.do_jobs()
                
                elif choice == "6":
                    await self.do_blacklist()
                
                elif choice == "7":
                    await self.show_help_async()
                
                elif choice == "8":
                    should_exit = await self.do_exit()
                    if should_exit:
                        break
                
                else:
                    # Invalid input handling
                    self.ui.show_error(
                        f"Invalid choice: '{choice}'. Please enter a number (1-8) or shortcut (s,c,m,r,j,b,h,q)."
                    )
            
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                self.console.print("\n")
                self.ui.show_warning("Interrupted by user")
                should_exit = await self.do_exit()
                if should_exit:
                    break
            
            except EOFError:
                # Handle Ctrl+D gracefully
                self.console.print("\n")
                self.ui.show_info("EOF detected")
                should_exit = await self.do_exit()
                if should_exit:
                    break
            
            except Exception as e:
                # Handle unexpected errors
                self.ui.show_error(f"An unexpected error occurred: {e}")
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                
                # Ask if user wants to continue - async
                continue_running = await self.ui.prompt_confirm_async(
                    "Do you want to continue?",
                    default=True
                )
                
                if not continue_running:
                    await self.postloop()
                    break


async def main():
    """
    Entry point for the CLI application
    
    Creates and runs the TelegramCLI instance.
    """
    try:
        cli = TelegramCLI()
        await cli.run()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the CLI application
    asyncio.run(main())
