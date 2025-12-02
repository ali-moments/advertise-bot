"""
Scraper CLI Module

This module provides a CLI interface for scraping operations including
member scraping, message scraping, and link extraction with statistics.
"""

import asyncio
import json
import csv
import os
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
from rich.console import Console
from telegram_manager.manager import TelegramSessionManager
from cli.ui_components import UIComponents
from cli.models import LinkScrapingResult


class ScraperCLI:
    """CLI interface for scraping operations"""
    
    def __init__(self, session_manager: TelegramSessionManager, console: Optional[Console] = None):
        """
        Initialize Scraper CLI
        
        Args:
            session_manager: TelegramSessionManager instance
            console: Optional Rich Console instance
        """
        self.session_manager = session_manager
        self.console = console or Console()
        self.ui = UIComponents(self.console)
    
    async def scrape_members(self):
        """
        Scrape channel members with interactive prompts
        
        Prompts for channel identifier, max members, and output format.
        Displays progress and saves results to file.
        
        Requirements: 4.1, 4.2, 4.3, 4.4
        """
        self.console.print("\n[bold cyan]═══ Scrape Channel Members ═══[/bold cyan]\n")
        
        # Check if sessions are available
        if not self.session_manager.sessions:
            self.ui.show_error("No sessions available. Please load sessions first.")
            return
        
        # Prompt for channel identifier
        channel = await self.ui.prompt_input_async(
            "Enter channel username, ID, or invite link",
            default=None
        )
        
        if not channel:
            self.ui.show_warning("Channel identifier is required")
            return
        
        # Prompt for max members
        max_members_str = await self.ui.prompt_input_async(
            "Maximum members to scrape",
            default="10000"
        )
        
        try:
            max_members = int(max_members_str)
            if max_members <= 0:
                self.ui.show_error("Max members must be positive")
                return
        except ValueError:
            self.ui.show_error("Invalid number for max members")
            return
        
        # Prompt for fallback option
        fallback = await self.ui.prompt_confirm_async(
            "Fallback to message-based scraping if member list unavailable?",
            default=True
        )
        
        # Prompt for output format
        output_format = await self.ui.prompt_choice_async(
            "Select output format:",
            ["CSV", "JSON"],
            default="CSV"
        )
        
        # Start scraping with progress display
        self.ui.show_info(f"Starting member scrape for {channel}...")
        
        with self.ui.create_progress_bar(100, "Scraping members") as progress:
            task = progress.add_task("Scraping...", total=100)
            
            # Update progress
            progress.update(task, advance=20, description="Connecting to channel...")
            
            try:
                # Execute scraping operation
                result = await self.session_manager.scrape_group_members_random_session(
                    group_identifier=channel,
                    max_members=max_members,
                    fallback_to_messages=fallback,
                    message_days_back=10
                )
                
                progress.update(task, advance=60, description="Processing results...")
                
                if result.get('success'):
                    # Get the file path from result
                    file_path = result.get('file_path')
                    member_count = result.get('member_count', 0)
                    session_used = result.get('session_used', 'unknown')
                    
                    progress.update(task, advance=20, description="Complete!")
                    
                    # Show success message
                    self.ui.show_success(
                        f"Successfully scraped {member_count} members from {channel}"
                    )
                    self.console.print(f"[bold]Session used:[/bold] {session_used}")
                    self.console.print(f"[bold]Output file:[/bold] {file_path}")
                    
                    # If user wants different format, convert it
                    if file_path and output_format.upper() != file_path.split('.')[-1].upper():
                        converted_path = await self._convert_file_format(
                            file_path,
                            output_format.lower()
                        )
                        if converted_path:
                            self.console.print(f"[bold]Converted to:[/bold] {converted_path}")
                else:
                    progress.update(task, advance=80, description="Failed!")
                    error = result.get('error', 'Unknown error')
                    self.ui.show_error(f"Failed to scrape members: {error}")
                    
            except Exception as e:
                progress.update(task, advance=100, description="Error!")
                self.ui.show_error(f"Error during scraping: {e}")
    
    async def scrape_messages(self):
        """
        Scrape channel messages with date range prompts
        
        Prompts for channel, date range, and output format.
        Displays progress and saves results to file.
        
        Requirements: 4.1, 4.2, 4.3, 4.4
        """
        self.console.print("\n[bold cyan]═══ Scrape Channel Messages ═══[/bold cyan]\n")
        
        # Check if sessions are available
        if not self.session_manager.sessions:
            self.ui.show_error("No sessions available. Please load sessions first.")
            return
        
        # Prompt for channel identifier
        channel = await self.ui.prompt_input_async(
            "Enter channel username, ID, or invite link",
            default=None
        )
        
        if not channel:
            self.ui.show_warning("Channel identifier is required")
            return
        
        # Prompt for days back
        days_back_str = await self.ui.prompt_input_async(
            "How many days back to scrape messages?",
            default="7"
        )
        
        try:
            days_back = int(days_back_str)
            if days_back <= 0:
                self.ui.show_error("Days back must be positive")
                return
        except ValueError:
            self.ui.show_error("Invalid number for days back")
            return
        
        # Prompt for message limit
        limit_str = await self.ui.prompt_input_async(
            "Maximum messages to scrape (0 for unlimited)",
            default="1000"
        )
        
        try:
            limit = int(limit_str)
            if limit < 0:
                self.ui.show_error("Limit must be non-negative")
                return
        except ValueError:
            self.ui.show_error("Invalid number for limit")
            return
        
        # Prompt for output format
        output_format = await self.ui.prompt_choice_async(
            "Select output format:",
            ["JSON", "CSV"],
            default="JSON"
        )
        
        # Start scraping with progress display
        self.ui.show_info(f"Starting message scrape for {channel}...")
        
        with self.ui.create_progress_bar(100, "Scraping messages") as progress:
            task = progress.add_task("Scraping...", total=100)
            
            # Update progress
            progress.update(task, advance=20, description="Connecting to channel...")
            
            try:
                # Get a session to use
                session_name = self.session_manager._get_available_session()
                if not session_name:
                    self.ui.show_error("No available sessions")
                    return
                
                session = self.session_manager.sessions[session_name]
                
                progress.update(task, advance=20, description="Fetching messages...")
                
                # Get the entity
                entity = await session.client.get_entity(channel)
                
                # Calculate offset date
                offset_date = datetime.now() - timedelta(days=days_back)
                
                # Scrape messages
                messages = []
                message_limit = limit if limit > 0 else None
                
                async for message in session.client.iter_messages(
                    entity,
                    offset_date=offset_date,
                    limit=message_limit
                ):
                    messages.append({
                        'id': message.id,
                        'date': message.date.isoformat() if message.date else None,
                        'text': message.text or '',
                        'sender_id': message.sender_id,
                        'views': message.views,
                        'forwards': message.forwards,
                        'replies': message.replies.replies if message.replies else 0,
                        'has_media': message.media is not None
                    })
                    
                    # Update progress periodically
                    if len(messages) % 100 == 0:
                        progress.update(task, advance=0.5, description=f"Scraped {len(messages)} messages...")
                
                progress.update(task, advance=40, description="Saving results...")
                
                # Save results
                output_dir = "data"
                os.makedirs(output_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                channel_name = channel.replace('@', '').replace('/', '_')
                
                if output_format.lower() == 'json':
                    output_file = os.path.join(
                        output_dir,
                        f"messages_{channel_name}_{timestamp}.json"
                    )
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'channel': channel,
                            'scraped_at': datetime.now().isoformat(),
                            'days_back': days_back,
                            'message_count': len(messages),
                            'messages': messages
                        }, f, indent=2, ensure_ascii=False)
                else:
                    output_file = os.path.join(
                        output_dir,
                        f"messages_{channel_name}_{timestamp}.csv"
                    )
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        if messages:
                            writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                            writer.writeheader()
                            writer.writerows(messages)
                
                progress.update(task, advance=20, description="Complete!")
                
                # Show success message
                self.ui.show_success(
                    f"Successfully scraped {len(messages)} messages from {channel}"
                )
                self.console.print(f"[bold]Session used:[/bold] {session_name}")
                self.console.print(f"[bold]Output file:[/bold] {output_file}")
                
            except Exception as e:
                progress.update(task, advance=100, description="Error!")
                self.ui.show_error(f"Error during scraping: {e}")
    
    async def scrape_links(self):
        """
        Scrape links from channel messages with extraction and categorization
        
        Extracts all URLs from messages, categorizes by domain and type,
        and generates statistics.
        
        Requirements: 4.1, 4.3, 4.4, 4.5, 10.2, 10.3, 10.4
        """
        self.console.print("\n[bold cyan]═══ Scrape Links from Channel ═══[/bold cyan]\n")
        
        # Check if sessions are available
        if not self.session_manager.sessions:
            self.ui.show_error("No sessions available. Please load sessions first.")
            return
        
        # Prompt for channel identifier
        channel = await self.ui.prompt_input_async(
            "Enter channel username, ID, or invite link",
            default=None
        )
        
        if not channel:
            self.ui.show_warning("Channel identifier is required")
            return
        
        # Prompt for days back
        days_back_str = await self.ui.prompt_input_async(
            "How many days back to scrape links?",
            default="1"
        )
        
        try:
            days_back = int(days_back_str)
            if days_back <= 0:
                self.ui.show_error("Days back must be positive")
                return
        except ValueError:
            self.ui.show_error("Invalid number for days back")
            return
        
        # Start scraping with progress display
        self.ui.show_info(f"Starting link scrape for {channel}...")
        
        with self.ui.create_progress_bar(100, "Scraping links") as progress:
            task = progress.add_task("Scraping...", total=100)
            
            # Update progress
            progress.update(task, advance=10, description="Connecting to channel...")
            
            try:
                # Get a session to use
                session_name = self.session_manager._get_available_session()
                if not session_name:
                    self.ui.show_error("No available sessions")
                    return
                
                session = self.session_manager.sessions[session_name]
                
                progress.update(task, advance=10, description="Fetching messages...")
                
                # Get the entity
                entity = await session.client.get_entity(channel)
                
                # Calculate offset date
                offset_date = datetime.now() - timedelta(days=days_back)
                
                # Scrape messages and extract links
                links = []
                total_messages = 0
                
                # URL regex pattern
                url_pattern = re.compile(
                    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                )
                
                async for message in session.client.iter_messages(
                    entity,
                    offset_date=offset_date
                ):
                    total_messages += 1
                    
                    # Extract links from message text
                    if message.text:
                        urls = url_pattern.findall(message.text)
                        for url in urls:
                            links.append({
                                'url': url,
                                'message_id': message.id,
                                'message_date': message.date.isoformat() if message.date else None,
                                'domain': self._extract_domain(url),
                                'type': self._get_url_type(url)
                            })
                    
                    # Update progress periodically
                    if total_messages % 50 == 0:
                        progress.update(
                            task,
                            advance=0.5,
                            description=f"Processed {total_messages} messages, found {len(links)} links..."
                        )
                
                progress.update(task, advance=50, description="Calculating statistics...")
                
                # Calculate statistics
                links_by_domain = {}
                links_by_type = {}
                
                for link in links:
                    domain = link['domain']
                    link_type = link['type']
                    
                    links_by_domain[domain] = links_by_domain.get(domain, 0) + 1
                    links_by_type[link_type] = links_by_type.get(link_type, 0) + 1
                
                unique_domains = len(links_by_domain)
                
                progress.update(task, advance=20, description="Saving results...")
                
                # Save results
                output_dir = "data/links"
                os.makedirs(output_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                channel_name = channel.replace('@', '').replace('/', '_')
                output_file = os.path.join(
                    output_dir,
                    f"links_{channel_name}_{timestamp}.json"
                )
                
                # Create result object
                result = LinkScrapingResult(
                    channel_id=channel,
                    total_messages=total_messages,
                    total_links=len(links),
                    unique_domains=unique_domains,
                    links_by_domain=links_by_domain,
                    links_by_type=links_by_type,
                    timestamp=datetime.now().timestamp(),
                    output_file=output_file
                )
                
                # Save to JSON
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'channel_id': result.channel_id,
                        'channel_name': channel,
                        'scrape_timestamp': datetime.fromtimestamp(result.timestamp).isoformat(),
                        'total_messages': result.total_messages,
                        'total_links': result.total_links,
                        'unique_domains': result.unique_domains,
                        'links_by_domain': result.links_by_domain,
                        'links_by_type': result.links_by_type,
                        'links': links
                    }, f, indent=2, ensure_ascii=False)
                
                progress.update(task, advance=20, description="Complete!")
                
                # Show success message with statistics
                self.ui.show_success(
                    f"Successfully scraped links from {channel}"
                )
                self.console.print(f"[bold]Session used:[/bold] {session_name}")
                self.console.print(f"[bold]Output file:[/bold] {output_file}")
                
                # Display statistics
                self._display_link_statistics(result)
                
            except Exception as e:
                progress.update(task, advance=100, description="Error!")
                self.ui.show_error(f"Error during link scraping: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL
        
        Args:
            url: URL string
            
        Returns:
            Domain name
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or 'unknown'
        except Exception:
            return 'unknown'
    
    def _get_url_type(self, url: str) -> str:
        """
        Get URL type (http, https, telegram, etc.)
        
        Args:
            url: URL string
            
        Returns:
            URL type
        """
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            
            # Check for Telegram URLs first
            if 't.me' in url or 'telegram' in url:
                return 'telegram'
            elif scheme in ['http', 'https']:
                return scheme
            else:
                return scheme or 'unknown'
        except Exception:
            return 'unknown'
    
    def _display_link_statistics(self, result: LinkScrapingResult):
        """
        Display link scraping statistics in formatted tables
        
        Args:
            result: LinkScrapingResult object
        """
        self.console.print("\n[bold cyan]═══ Link Statistics ═══[/bold cyan]\n")
        
        # Overall statistics
        self.console.print(f"[bold]Total Messages:[/bold] {result.total_messages}")
        self.console.print(f"[bold]Total Links:[/bold] {result.total_links}")
        self.console.print(f"[bold]Unique Domains:[/bold] {result.unique_domains}")
        
        # Links by type
        if result.links_by_type:
            self.console.print("\n[bold]Links by Type:[/bold]")
            type_rows = [
                [link_type, count]
                for link_type, count in sorted(
                    result.links_by_type.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]
            self.ui.display_table(
                "Link Types",
                ["Type", "Count"],
                type_rows
            )
        
        # Top domains
        if result.links_by_domain:
            self.console.print("\n[bold]Top 10 Domains:[/bold]")
            domain_rows = [
                [domain, count]
                for domain, count in sorted(
                    result.links_by_domain.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ]
            self.ui.display_table(
                "Top Domains",
                ["Domain", "Count"],
                domain_rows
            )
    
    async def _convert_file_format(self, input_file: str, target_format: str) -> Optional[str]:
        """
        Convert file from one format to another
        
        Args:
            input_file: Path to input file
            target_format: Target format ('csv' or 'json')
            
        Returns:
            Path to converted file or None if conversion failed
        """
        try:
            # Determine input format
            input_format = input_file.split('.')[-1].lower()
            
            if input_format == target_format:
                return input_file
            
            # Generate output filename
            output_file = input_file.rsplit('.', 1)[0] + f'.{target_format}'
            
            if input_format == 'csv' and target_format == 'json':
                # CSV to JSON
                with open(input_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return output_file
            
            elif input_format == 'json' and target_format == 'csv':
                # JSON to CSV
                with open(input_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, dict) and 'members' in data:
                    rows = data['members']
                elif isinstance(data, list):
                    rows = data
                else:
                    return None
                
                if not rows:
                    return None
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                
                return output_file
            
            return None
            
        except Exception as e:
            self.ui.show_error(f"Failed to convert file format: {e}")
            return None
    
    async def show_menu(self):
        """
        Display scraping menu and handle user selection
        
        Requirements: 7.2, 7.3
        """
        while True:
            self.console.print("\n[bold cyan]═══ Scraping Operations ═══[/bold cyan]\n")
            
            choices = [
                "Scrape Members",
                "Scrape Messages",
                "Scrape Links",
                "Back to Main Menu"
            ]
            
            try:
                choice = await self.ui.prompt_choice_async("Select an option:", choices)
                
                if choice == "Scrape Members":
                    await self.scrape_members()
                
                elif choice == "Scrape Messages":
                    await self.scrape_messages()
                
                elif choice == "Scrape Links":
                    await self.scrape_links()
                
                elif choice == "Back to Main Menu":
                    break
                
            except KeyboardInterrupt:
                self.console.print("\n")
                break
            except Exception as e:
                self.ui.show_error(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
