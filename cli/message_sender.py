"""
Message Sender CLI Module

This module provides the CLI interface for sending messages to recipients.
It supports text messages, media messages, and bulk sending from CSV files
with real-time progress display and summary reports.
"""

import asyncio
import logging
import os
import time
from typing import Optional, Dict, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from telegram_manager.manager import TelegramSessionManager
from telegram_manager.models import MessageResult, MediaHandler, CSVProcessor, RecipientValidator
from cli.ui_components import UIComponents
from prompt_toolkit.validation import Validator, ValidationError

logger = logging.getLogger(__name__)


class FilePathValidator(Validator):
    """Validator for file paths"""
    
    def validate(self, document):
        text = document.text.strip()
        if not text:
            raise ValidationError(message="File path cannot be empty")
        if not os.path.exists(text):
            raise ValidationError(message=f"File does not exist: {text}")


class DelayValidator(Validator):
    """Validator for delay values"""
    
    def validate(self, document):
        text = document.text.strip()
        if not text:
            return  # Allow empty for default
        try:
            delay = float(text)
            if delay < 0:
                raise ValidationError(message="Delay must be non-negative")
            if delay > 60:
                raise ValidationError(message="Delay must be 60 seconds or less")
        except ValueError:
            raise ValidationError(message="Delay must be a valid number")


class MessageSenderCLI:
    """CLI interface for message sending operations"""
    
    def __init__(self, session_manager: TelegramSessionManager, console: Optional[Console] = None):
        """
        Initialize message sender CLI
        
        Args:
            session_manager: TelegramSessionManager instance
            console: Optional Console instance for output
        """
        self.session_manager = session_manager
        self.console = console or Console()
        self.ui = UIComponents(self.console)
    
    async def send_text_message(self):
        """Send text message with interactive prompts"""
        self.console.print("\n[bold cyan]Send Text Message[/bold cyan]")
        self.ui.print_separator()
        
        try:
            # Prompt for recipients
            self.console.print("\n[bold]Enter recipients:[/bold]")
            self.console.print("  - Enter usernames (e.g., @username) or user IDs")
            self.console.print("  - Separate multiple recipients with commas")
            self.console.print("  - Example: @user1, @user2, 123456789")
            
            recipients_input = await self.ui.prompt_input_async("\nRecipients")
            if not recipients_input:
                self.ui.show_error("Recipients cannot be empty")
                return
            
            # Parse recipients (split by comma and strip whitespace)
            recipients = [r.strip() for r in recipients_input.split(',') if r.strip()]
            
            if not recipients:
                self.ui.show_error("No valid recipients provided")
                return
            
            # Validate recipients
            validation_result = RecipientValidator.validate_recipients(recipients)
            if not validation_result.valid:
                self.ui.show_error("Invalid recipients:")
                for error in validation_result.errors:
                    self.console.print(f"  - {error.message}", style="red")
                
                # Ask if user wants to skip invalid recipients
                skip_invalid = await self.ui.prompt_confirm_async(
                    "Skip invalid recipients and continue?",
                    default=True
                )
                
                if not skip_invalid:
                    self.ui.show_info("Send operation cancelled")
                    return
            else:
                skip_invalid = False
            
            # Prompt for message
            self.console.print("\n[bold]Enter message text:[/bold]")
            self.console.print("  - Type your message (press Enter twice to finish)")
            self.console.print("  - Or type 'file:' followed by path to load from markdown file")
            self.console.print("  - Example: file:message.md")
            
            # Import aioconsole for async input
            import aioconsole
            
            message_lines = []
            empty_line_count = 0
            while True:
                line = await aioconsole.ainput()
                if not line:
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        break
                    message_lines.append(line)
                else:
                    empty_line_count = 0
                    message_lines.append(line)
            
            # Remove trailing empty lines
            while message_lines and not message_lines[-1]:
                message_lines.pop()
            
            message = '\n'.join(message_lines)
            
            # Check if user wants to load from file
            if message.strip().startswith('file:'):
                file_path = message.strip()[5:].strip()
                if not os.path.exists(file_path):
                    self.ui.show_error(f"File not found: {file_path}")
                    return
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        message = f.read()
                    self.ui.show_success(f"Loaded message from {file_path} ({len(message)} characters)")
                except Exception as e:
                    self.ui.show_error(f"Error reading file: {e}")
                    return
            
            if not message.strip():
                self.ui.show_error("Message cannot be empty")
                return
            
            # Prompt for delay
            delay_str = await self.ui.prompt_input_async(
                "Delay between sends (seconds)",
                default="2.0"
            )
            
            # Validate delay
            try:
                delay = float(delay_str) if delay_str else 2.0
                if delay < 0 or delay > 60:
                    self.ui.show_error("Delay must be between 0 and 60 seconds")
                    return
            except ValueError:
                self.ui.show_error("Delay must be a valid number")
                return
            
            # Confirm send
            self.console.print("\n[bold yellow]Send Summary:[/bold yellow]")
            self.console.print(f"  Recipients: {len(recipients)}")
            self.console.print(f"  Message length: {len(message)} characters")
            self.console.print(f"  Delay: {delay} seconds")
            
            confirmed = await self.ui.prompt_confirm_async(
                "\nProceed with sending?",
                default=True
            )
            
            if not confirmed:
                self.ui.show_info("Send operation cancelled")
                return
            
            # Send messages with progress display
            self.console.print("\n[bold green]Sending messages...[/bold green]")
            
            start_time = time.time()
            results = await self._send_with_progress(
                recipients,
                message,
                delay,
                skip_invalid,
                send_type="text"
            )
            duration = time.time() - start_time
            
            # Display summary
            self.show_summary(results, duration)
        
        except KeyboardInterrupt:
            self.ui.show_warning("\nSend operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Error sending message: {e}")
            logger.error(f"Error in send_text_message: {e}", exc_info=True)
    
    async def send_media_message(self):
        """Send media message with interactive prompts"""
        self.console.print("\n[bold cyan]Send Media Message[/bold cyan]")
        self.ui.print_separator()
        
        try:
            # Prompt for recipients
            self.console.print("\n[bold]Enter recipients:[/bold]")
            self.console.print("  - Enter usernames (e.g., @username) or user IDs")
            self.console.print("  - Separate multiple recipients with commas")
            
            recipients_input = await self.ui.prompt_input_async("\nRecipients")
            if not recipients_input:
                self.ui.show_error("Recipients cannot be empty")
                return
            
            # Parse recipients
            recipients = [r.strip() for r in recipients_input.split(',') if r.strip()]
            
            if not recipients:
                self.ui.show_error("No valid recipients provided")
                return
            
            # Validate recipients
            validation_result = RecipientValidator.validate_recipients(recipients)
            if not validation_result.valid:
                self.ui.show_error("Invalid recipients:")
                for error in validation_result.errors:
                    self.console.print(f"  - {error.message}", style="red")
                
                skip_invalid = await self.ui.prompt_confirm_async(
                    "Skip invalid recipients and continue?",
                    default=True
                )
                
                if not skip_invalid:
                    self.ui.show_info("Send operation cancelled")
                    return
            else:
                skip_invalid = False
            
            # Prompt for media file path with validation
            media_path = await self.ui.prompt_input_async(
                "Enter media file path"
            )
            
            # Validate file path
            if not media_path or not os.path.exists(media_path):
                self.ui.show_error(f"File does not exist: {media_path}")
                return
            
            # Prompt for media type
            media_type = await self.ui.prompt_choice_async(
                "Select media type",
                choices=["image", "video", "document"],
                default="image"
            )
            
            # Validate media format
            format_validation = MediaHandler.validate_format(media_path, media_type)
            if not format_validation.valid:
                self.ui.show_error("Invalid media format:")
                for error in format_validation.errors:
                    self.console.print(f"  - {error.message}", style="red")
                return
            
            # Validate media size
            size_validation = MediaHandler.validate_size(media_path, media_type)
            if not size_validation.valid:
                self.ui.show_error("Invalid media size:")
                for error in size_validation.errors:
                    self.console.print(f"  - {error.message}", style="red")
                return
            
            # Prompt for caption (optional)
            self.console.print("\n[bold]Enter caption (optional):[/bold]")
            self.console.print("  - Press Enter to skip")
            caption = await self.ui.prompt_input_async("Caption")
            if not caption:
                caption = None
            
            # Prompt for delay
            delay_str = await self.ui.prompt_input_async(
                "Delay between sends (seconds)",
                default="2.0"
            )
            
            # Validate delay
            try:
                delay = float(delay_str) if delay_str else 2.0
                if delay < 0 or delay > 60:
                    self.ui.show_error("Delay must be between 0 and 60 seconds")
                    return
            except ValueError:
                self.ui.show_error("Delay must be a valid number")
                return
            
            # Confirm send
            file_size = os.path.getsize(media_path)
            file_size_mb = file_size / (1024 * 1024)
            
            self.console.print("\n[bold yellow]Send Summary:[/bold yellow]")
            self.console.print(f"  Recipients: {len(recipients)}")
            self.console.print(f"  Media type: {media_type}")
            self.console.print(f"  File: {os.path.basename(media_path)}")
            self.console.print(f"  File size: {file_size_mb:.2f} MB")
            if caption:
                self.console.print(f"  Caption: {caption[:50]}{'...' if len(caption) > 50 else ''}")
            self.console.print(f"  Delay: {delay} seconds")
            
            confirmed = await self.ui.prompt_confirm_async(
                "\nProceed with sending?",
                default=True
            )
            
            if not confirmed:
                self.ui.show_info("Send operation cancelled")
                return
            
            # Send media messages with progress display
            self.console.print("\n[bold green]Sending media messages...[/bold green]")
            
            start_time = time.time()
            results = await self._send_media_with_progress(
                recipients,
                media_path,
                media_type,
                caption,
                delay,
                skip_invalid
            )
            duration = time.time() - start_time
            
            # Display summary
            self.show_summary(results, duration)
        
        except KeyboardInterrupt:
            self.ui.show_warning("\nSend operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Error sending media message: {e}")
            logger.error(f"Error in send_media_message: {e}", exc_info=True)
    
    async def send_bulk_from_csv(self):
        """Send bulk messages from CSV file with CSV file processing"""
        self.console.print("\n[bold cyan]Send Bulk Messages from CSV[/bold cyan]")
        self.ui.print_separator()
        
        try:
            # Prompt for CSV file path
            csv_path = await self.ui.prompt_input_async(
                "Enter CSV file path"
            )
            
            # Validate file path
            if not csv_path or not os.path.exists(csv_path):
                self.ui.show_error(f"File does not exist: {csv_path}")
                return
            
            # Check if file is CSV
            if not csv_path.lower().endswith('.csv'):
                self.ui.show_error("File must be a CSV file")
                return
            
            # Parse CSV to get recipients
            self.console.print("\n[bold]Parsing CSV file...[/bold]")
            
            recipients = []
            async for batch in CSVProcessor.parse_csv(csv_path):
                recipients.extend(batch)
            
            if not recipients:
                self.ui.show_error("No recipients found in CSV file")
                return
            
            self.ui.show_success(f"Found {len(recipients)} recipients in CSV file")
            
            # Validate recipients
            valid_recipients, invalid_recipients = RecipientValidator.filter_valid_recipients(recipients)
            
            if invalid_recipients:
                self.ui.show_warning(f"Found {len(invalid_recipients)} invalid recipients")
                self.console.print(f"  Valid: {len(valid_recipients)}")
                self.console.print(f"  Invalid: {len(invalid_recipients)}")
                
                if len(valid_recipients) == 0:
                    self.ui.show_error("No valid recipients found")
                    return
                
                skip_invalid = await self.ui.prompt_confirm_async(
                    "Skip invalid recipients and continue?",
                    default=True
                )
                
                if not skip_invalid:
                    self.ui.show_info("Send operation cancelled")
                    return
                
                recipients = valid_recipients
            
            # Prompt for message type
            message_type = await self.ui.prompt_choice_async(
                "Select message type",
                choices=["text", "media"],
                default="text"
            )
            
            if message_type == "text":
                # Prompt for message text
                self.console.print("\n[bold]Enter message text:[/bold]")
                self.console.print("  - Type your message (press Enter twice to finish)")
                
                message_lines = []
                empty_line_count = 0
                while True:
                    line = input()
                    if not line:
                        empty_line_count += 1
                        if empty_line_count >= 2:
                            break
                        message_lines.append(line)
                    else:
                        empty_line_count = 0
                        message_lines.append(line)
                
                # Remove trailing empty lines
                while message_lines and not message_lines[-1]:
                    message_lines.pop()
                
                message = '\n'.join(message_lines)
                
                if not message.strip():
                    self.ui.show_error("Message cannot be empty")
                    return
                
                media_path = None
                media_type_val = None
                caption = None
            else:
                # Prompt for media file
                media_path = await self.ui.prompt_input_async(
                    "Enter media file path"
                )
                
                # Validate file path
                if not media_path or not os.path.exists(media_path):
                    self.ui.show_error(f"File does not exist: {media_path}")
                    return
                
                media_type_val = await self.ui.prompt_choice_async(
                    "Select media type",
                    choices=["image", "video", "document"],
                    default="image"
                )
                
                # Validate media
                format_validation = MediaHandler.validate_format(media_path, media_type_val)
                if not format_validation.valid:
                    self.ui.show_error("Invalid media format:")
                    for error in format_validation.errors:
                        self.console.print(f"  - {error.message}", style="red")
                    return
                
                size_validation = MediaHandler.validate_size(media_path, media_type_val)
                if not size_validation.valid:
                    self.ui.show_error("Invalid media size:")
                    for error in size_validation.errors:
                        self.console.print(f"  - {error.message}", style="red")
                    return
                
                # Prompt for caption
                self.console.print("\n[bold]Enter caption (optional):[/bold]")
                caption = await self.ui.prompt_input_async("Caption")
                if not caption:
                    caption = None
                
                message = None
            
            # Prompt for delay
            delay_str = await self.ui.prompt_input_async(
                "Delay between sends (seconds)",
                default="2.0"
            )
            
            # Validate delay
            try:
                delay = float(delay_str) if delay_str else 2.0
                if delay < 0 or delay > 60:
                    self.ui.show_error("Delay must be between 0 and 60 seconds")
                    return
            except ValueError:
                self.ui.show_error("Delay must be a valid number")
                return
            
            # Confirm send
            self.console.print("\n[bold yellow]Send Summary:[/bold yellow]")
            self.console.print(f"  Recipients: {len(recipients)}")
            self.console.print(f"  Message type: {message_type}")
            if message_type == "text":
                self.console.print(f"  Message length: {len(message)} characters")
            else:
                self.console.print(f"  Media type: {media_type_val}")
                self.console.print(f"  File: {os.path.basename(media_path)}")
            self.console.print(f"  Delay: {delay} seconds")
            self.console.print(f"  Estimated duration: {len(recipients) * delay / 60:.1f} minutes")
            
            confirmed = await self.ui.prompt_confirm_async(
                "\nProceed with bulk sending?",
                default=True
            )
            
            if not confirmed:
                self.ui.show_info("Send operation cancelled")
                return
            
            # Send messages with progress display
            self.console.print("\n[bold green]Sending bulk messages...[/bold green]")
            
            start_time = time.time()
            
            if message_type == "text":
                results = await self._send_with_progress(
                    recipients,
                    message,
                    delay,
                    skip_invalid=True,
                    send_type="text"
                )
            else:
                results = await self._send_media_with_progress(
                    recipients,
                    media_path,
                    media_type_val,
                    caption,
                    delay,
                    skip_invalid=True
                )
            
            duration = time.time() - start_time
            
            # Display summary
            self.show_summary(results, duration)
        
        except KeyboardInterrupt:
            self.ui.show_warning("\nBulk send operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Error in bulk send: {e}")
            logger.error(f"Error in send_bulk_from_csv: {e}", exc_info=True)
    
    async def _send_with_progress(
        self,
        recipients: List[str],
        message: str,
        delay: float,
        skip_invalid: bool,
        send_type: str
    ) -> Dict[str, MessageResult]:
        """
        Send text messages with real-time progress display
        
        Args:
            recipients: List of recipient identifiers
            message: Message text to send
            delay: Delay between sends
            skip_invalid: Whether to skip invalid recipients
            send_type: Type of send operation (for display)
            
        Returns:
            Dict mapping recipients to MessageResult objects
        """
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("• Success: {task.fields[success]}"),
            TextColumn("• Failed: {task.fields[failed]}"),
            console=self.console
        ) as progress:
            task = progress.add_task(
                f"Sending {send_type} messages",
                total=len(recipients),
                success=0,
                failed=0
            )
            
            # Send messages using session manager
            results = await self.session_manager.send_text_messages_bulk(
                recipients=recipients,
                message=message,
                delay=delay,
                skip_invalid=skip_invalid
            )
            
            # Update progress as results come in
            success_count = sum(1 for r in results.values() if r.success)
            failed_count = len(results) - success_count
            
            progress.update(
                task,
                completed=len(results),
                success=success_count,
                failed=failed_count
            )
        
        return results
    
    async def _send_media_with_progress(
        self,
        recipients: List[str],
        media_path: str,
        media_type: str,
        caption: Optional[str],
        delay: float,
        skip_invalid: bool
    ) -> Dict[str, MessageResult]:
        """
        Send media messages with real-time progress display
        
        Args:
            recipients: List of recipient identifiers
            media_path: Path to media file
            media_type: Type of media
            caption: Optional caption
            delay: Delay between sends
            skip_invalid: Whether to skip invalid recipients
            
        Returns:
            Dict mapping recipients to MessageResult objects
        """
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("• Success: {task.fields[success]}"),
            TextColumn("• Failed: {task.fields[failed]}"),
            console=self.console
        ) as progress:
            task = progress.add_task(
                f"Sending {media_type} messages",
                total=len(recipients),
                success=0,
                failed=0
            )
            
            # Send media messages using session manager
            results = await self.session_manager.send_media_messages_bulk(
                recipients=recipients,
                media_path=media_path,
                media_type=media_type,
                caption=caption,
                delay=delay,
                skip_invalid=skip_invalid
            )
            
            # Update progress as results come in
            success_count = sum(1 for r in results.values() if r.success)
            failed_count = len(results) - success_count
            
            progress.update(
                task,
                completed=len(results),
                success=success_count,
                failed=failed_count
            )
        
        return results
    
    def show_progress(self, current: int, total: int, results: Dict):
        """
        Display real-time sending progress
        
        Args:
            current: Current number of messages sent
            total: Total number of messages to send
            results: Dict of results so far
        """
        success = sum(1 for r in results.values() if r.success)
        failed = current - success
        percentage = (current / total * 100) if total > 0 else 0
        
        self.console.print(
            f"Progress: {current}/{total} ({percentage:.1f}%) | "
            f"Success: {success} | Failed: {failed}",
            end='\r'
        )
    
    def show_summary(self, results: Dict[str, MessageResult], duration: float):
        """
        Display send operation summary with statistics
        
        Args:
            results: Dict mapping recipients to MessageResult objects
            duration: Duration of the operation in seconds
        """
        self.console.print("\n")
        self.ui.print_separator()
        self.console.print("\n[bold cyan]Send Operation Summary[/bold cyan]\n")
        
        # Calculate statistics
        total = len(results)
        succeeded = sum(1 for r in results.values() if r.success)
        failed = total - succeeded
        success_rate = (succeeded / total * 100) if total > 0 else 0
        
        # Count blacklisted
        blacklisted = sum(1 for r in results.values() if hasattr(r, 'blacklisted') and r.blacklisted)
        
        # Display statistics
        self.console.print(f"[bold]Total Recipients:[/bold] {total}")
        self.console.print(f"[bold green]Succeeded:[/bold green] {succeeded}")
        self.console.print(f"[bold red]Failed:[/bold red] {failed}")
        if blacklisted > 0:
            self.console.print(f"[bold yellow]Blacklisted (skipped):[/bold yellow] {blacklisted}")
        self.console.print(f"[bold]Success Rate:[/bold] {success_rate:.1f}%")
        self.console.print(f"[bold]Duration:[/bold] {duration:.1f} seconds")
        
        # Display failed recipients if any
        if failed > 0:
            self.console.print("\n[bold red]Failed Recipients:[/bold red]")
            failed_results = [(r, res) for r, res in results.items() if not res.success]
            
            # Limit display to first 10 failures
            display_count = min(10, len(failed_results))
            for recipient, result in failed_results[:display_count]:
                error_msg = result.error or "Unknown error"
                self.console.print(f"  - {recipient}: {error_msg}")
            
            if len(failed_results) > display_count:
                self.console.print(f"  ... and {len(failed_results) - display_count} more")
        
        self.console.print()
        self.ui.print_separator()
    
    def show_menu(self):
        """Display message sending menu"""
        self.console.print("\n[bold cyan]Message Sending[/bold cyan]")
        self.ui.print_separator()
        self.console.print("  1. Send text message")
        self.console.print("  2. Send media message")
        self.console.print("  3. Send bulk from CSV")
        self.console.print("  4. Back to main menu")
        self.console.print()
    
    async def run(self):
        """Run the message sender interactive menu"""
        while True:
            try:
                self.show_menu()
                choice = await self.ui.prompt_input_async("Enter choice (1-4)")
                
                if choice == "1":
                    await self.send_text_message()
                elif choice == "2":
                    await self.send_media_message()
                elif choice == "3":
                    await self.send_bulk_from_csv()
                elif choice == "4":
                    break
                else:
                    self.ui.show_error("Invalid choice. Please enter 1-4.")
            
            except KeyboardInterrupt:
                self.ui.show_warning("\nReturning to main menu")
                break
            except Exception as e:
                self.ui.show_error(f"Error: {e}")
                logger.error(f"Error in message sender menu: {e}", exc_info=True)


# Example usage
async def main():
    """Example usage of MessageSenderCLI"""
    from telegram_manager.manager import TelegramSessionManager
    
    # Initialize session manager
    session_manager = TelegramSessionManager()
    await session_manager.load_sessions_from_db()
    
    # Create message sender CLI
    sender = MessageSenderCLI(session_manager)
    await sender.run()


if __name__ == "__main__":
    asyncio.run(main())
