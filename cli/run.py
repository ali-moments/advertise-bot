#!/usr/bin/env python3
"""
CLI Entry Point Script

This script serves as the main entry point for the Telegram Manager CLI.
It handles command-line argument parsing and launches the CLI application.

Usage:
    python cli/run.py [options]
    
Options:
    --config PATH    Path to configuration file (default: cli/config.json)
    --help          Show this help message and exit
    --version       Show version information and exit

Requirements: All
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.main import TelegramCLI, logger


VERSION = "1.0.0"


def parse_arguments():
    """
    Parse command-line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Telegram Manager CLI - Interactive command-line interface for managing Telegram sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default configuration
  python cli/run.py
  
  # Start with custom configuration file
  python cli/run.py --config /path/to/config.json
  
  # Show version
  python cli/run.py --version

For more information, see cli/README.md
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='cli/config.json',
        metavar='PATH',
        help='Path to configuration file (default: cli/config.json)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'Telegram Manager CLI v{VERSION}'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose console logging (shows all logs in terminal)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()


async def main():
    """
    Main entry point
    
    Parses arguments and launches the CLI application.
    """
    # Log event loop identity for verification
    loop = asyncio.get_running_loop()
    logger.info(f"Main event loop started: {id(loop)}")
    
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Validate config file path
    config_path = Path(args.config)
    
    # Create config directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Set config path in environment for CLI to use
    os.environ['CLI_CONFIG_PATH'] = str(config_path)
    
    try:
        # Create and run CLI with config path and verbose flag
        cli = TelegramCLI(config_path=str(config_path), verbose=args.verbose)
        
        if args.config != 'cli/config.json':
            logger.info(f"Using configuration file: {config_path}")
        
        await cli.run()
        
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the CLI application
    asyncio.run(main())
