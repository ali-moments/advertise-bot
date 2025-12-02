"""
Channel Manager CLI Module

This module provides the CLI interface for managing channels and their reaction lists.
It allows users to add, edit, delete, and list channels, as well as manage reactions
for each channel.
"""

import asyncio
import logging
from typing import Optional
from rich.console import Console

from cli.config_manager import ConfigManager
from cli.ui_components import UIComponents
from cli.models import ChannelConfig, ReactionConfig
from prompt_toolkit.validation import Validator, ValidationError

logger = logging.getLogger(__name__)


class ChannelIDValidator(Validator):
    """Validator for channel IDs"""
    
    def validate(self, document):
        text = document.text.strip()
        if not text:
            raise ValidationError(message="Channel ID cannot be empty")
        # Channel IDs can be numeric IDs or usernames starting with @
        if not (text.isdigit() or text.startswith('@') or text.startswith('-')):
            raise ValidationError(
                message="Channel ID must be a number, start with @, or start with - for private channels"
            )


class ReactionWeightValidator(Validator):
    """Validator for reaction weights"""
    
    def validate(self, document):
        text = document.text.strip()
        if not text:
            return  # Allow empty for default
        try:
            weight = int(text)
            if weight < 1 or weight > 10:
                raise ValidationError(message="Weight must be between 1 and 10")
        except ValueError:
            raise ValidationError(message="Weight must be a valid number")


class ChannelManagerCLI:
    """CLI interface for channel and reaction list management"""
    
    def __init__(self, config: ConfigManager, console: Optional[Console] = None, session_manager=None):
        """
        Initialize channel manager CLI
        
        Args:
            config: ConfigManager instance for persistence
            console: Optional Console instance for output
            session_manager: Optional TelegramSessionManager for auto-join functionality
        """
        self.config = config
        self.console = console or Console()
        self.ui = UIComponents(self.console)
        self.session_manager = session_manager
    
    async def list_channels(self, show_detailed_join_status: bool = False):
        """
        Display all configured channels in a formatted table
        
        Args:
            show_detailed_join_status: If True, show per-session join status for each channel
        """
        channels = self.config.get_channels()
        
        if not channels:
            self.ui.show_info("No channels configured yet.")
            return
        
        # Prepare table data
        rows = []
        for channel in channels:
            # Format reactions as emoji list with weights
            reactions_str = ", ".join([
                f"{r.emoji}({r.weight})" for r in channel.reactions
            ]) if channel.reactions else "None"
            
            # Format status
            status_parts = []
            if channel.scraping_enabled:
                status_parts.append("Scraping")
            if channel.monitoring_enabled:
                status_parts.append("Monitoring")
            status = ", ".join(status_parts) if status_parts else "Inactive"
            
            # Get join status if session manager is available
            join_status_str = await self._show_join_status(channel.channel_id)
            
            # Get monitoring statistics if session manager is available (Requirement 4.3)
            stats_str = await self._show_monitoring_statistics(channel.channel_id)
            
            rows.append([
                channel.channel_id,
                channel.get_display_name(),
                channel.channel_username or "N/A",
                reactions_str,
                status,
                join_status_str,
                stats_str
            ])
        
        # Display table
        self.ui.display_table(
            title="Configured Channels",
            columns=["Channel ID", "Name", "Username", "Reactions", "Status", "Join Status", "Statistics"],
            rows=rows
        )
        
        # Show detailed join status if requested
        if show_detailed_join_status and self.session_manager:
            self.console.print("\n[bold cyan]Detailed Join Status:[/bold cyan]")
            for channel in channels:
                await self._show_detailed_join_status(channel.channel_id, channel.get_display_name())
    
    async def add_channel(self):
        """Add a new channel with interactive prompts and validation"""
        self.console.print("\n[bold cyan]Add New Channel[/bold cyan]")
        self.ui.print_separator()
        
        try:
            # Prompt for channel ID (note: validation removed for async compatibility)
            channel_id = await self.ui.prompt_input_async(
                "Enter channel ID (numeric ID, @username, or -100...)"
            )
            
            # Validate channel ID
            if not channel_id:
                self.ui.show_error("Channel ID cannot be empty")
                return
            if not (channel_id.isdigit() or channel_id.startswith('@') or channel_id.startswith('-')):
                self.ui.show_error("Channel ID must be a number, start with @, or start with - for private channels")
                return
            
            # Check if channel already exists
            if self.config.get_channel(channel_id):
                self.ui.show_error(f"Channel {channel_id} already exists!")
                return
            
            # Prompt for channel name (optional)
            channel_name = await self.ui.prompt_input_async(
                "Enter channel name (optional, press Enter to use channel ID)"
            )
            if not channel_name:
                channel_name = None
            
            # Prompt for channel username (optional)
            channel_username = await self.ui.prompt_input_async(
                "Enter channel username (optional, press Enter to skip)"
            )
            if not channel_username:
                channel_username = None
            
            # Prompt for scraping enabled
            scraping_enabled = await self.ui.prompt_confirm_async(
                "Enable scraping for this channel?",
                default=True
            )
            
            # Prompt for monitoring enabled
            monitoring_enabled = await self.ui.prompt_confirm_async(
                "Enable monitoring for this channel?",
                default=False
            )
            
            # Create channel config with default reactions
            default_reactions = [
                ReactionConfig(emoji='❤️', weight=1),
                ReactionConfig(emoji='👍', weight=1)
            ]
            
            channel = ChannelConfig(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_username=channel_username,
                reactions=default_reactions,
                scraping_enabled=scraping_enabled,
                monitoring_enabled=monitoring_enabled
            )
            
            # Add channel with auto-join if session manager is available
            if self.session_manager:
                self.ui.show_info("Adding channel and joining with all sessions...")
                join_results = await self.config.add_channel_with_join(channel, self.session_manager)
                
                if join_results:
                    # Display join results to user
                    self.ui.show_success(f"Channel '{channel.get_display_name()}' added successfully!")
                    self._display_join_results(join_results)
                    
                    # Ask if user wants to add reactions now
                    add_reactions = await self.ui.prompt_confirm_async(
                        "Would you like to add reactions now?",
                        default=True
                    )
                    
                    if add_reactions:
                        await self.manage_reactions(channel_id)
                else:
                    self.ui.show_error("Failed to add channel")
            else:
                # Fallback to regular add without auto-join
                success = await self.config.add_channel(channel)
                
                if success:
                    self.ui.show_success(f"Channel '{channel.get_display_name()}' added successfully!")
                    self.ui.show_warning("Session manager not available - auto-join skipped")
                    
                    # Ask if user wants to add reactions now
                    add_reactions = await self.ui.prompt_confirm_async(
                        "Would you like to add reactions now?",
                        default=True
                    )
                    
                    if add_reactions:
                        await self.manage_reactions(channel_id)
                else:
                    self.ui.show_error("Failed to add channel")
        
        except KeyboardInterrupt:
            self.ui.show_warning("\nChannel addition cancelled")
        except Exception as e:
            self.ui.show_error(f"Error adding channel: {e}")
            logger.error(f"Error in add_channel: {e}", exc_info=True)
    
    async def edit_channel(self, channel_id: Optional[str] = None):
        """
        Edit channel configuration with current values displayed
        
        Args:
            channel_id: Optional channel ID to edit. If not provided, prompts user to select.
        """
        # If no channel_id provided, let user select one
        if not channel_id:
            channels = self.config.get_channels()
            if not channels:
                self.ui.show_info("No channels configured yet.")
                return
            
            # Display channels and let user choose
            await self.list_channels()
            channel_id = await self.ui.prompt_input_async("\nEnter channel ID to edit")
        
        # Get channel
        channel = self.config.get_channel(channel_id)
        if not channel:
            self.ui.show_error(f"Channel {channel_id} not found")
            return
        
        self.console.print(f"\n[bold cyan]Edit Channel: {channel.get_display_name()}[/bold cyan]")
        self.ui.print_separator()
        
        try:
            # Display current values and prompt for new ones
            self.console.print(f"Current name: [yellow]{channel.get_display_name()}[/yellow]")
            new_name = await self.ui.prompt_input_async(
                "Enter new name (press Enter to keep current, or leave empty to use channel ID)",
                default=channel.channel_name or ""
            )
            if not new_name:
                new_name = None
            
            self.console.print(f"Current username: [yellow]{channel.channel_username or 'None'}[/yellow]")
            new_username = await self.ui.prompt_input_async(
                "Enter new username (press Enter to keep current)",
                default=channel.channel_username or ""
            )
            if not new_username:
                new_username = None
            
            self.console.print(f"Current scraping enabled: [yellow]{channel.scraping_enabled}[/yellow]")
            new_scraping = await self.ui.prompt_confirm_async(
                "Enable scraping?",
                default=channel.scraping_enabled
            )
            
            self.console.print(f"Current monitoring enabled: [yellow]{channel.monitoring_enabled}[/yellow]")
            new_monitoring = await self.ui.prompt_confirm_async(
                "Enable monitoring?",
                default=channel.monitoring_enabled
            )
            
            # Update channel
            channel.channel_name = new_name
            channel.channel_username = new_username
            channel.scraping_enabled = new_scraping
            channel.monitoring_enabled = new_monitoring
            
            # Save changes
            success = await self.config.update_channel(channel)
            
            if success:
                self.ui.show_success(f"Channel '{channel.get_display_name()}' updated successfully!")
            else:
                self.ui.show_error("Failed to update channel")
        
        except KeyboardInterrupt:
            self.ui.show_warning("\nChannel edit cancelled")
        except Exception as e:
            self.ui.show_error(f"Error editing channel: {e}")
            logger.error(f"Error in edit_channel: {e}", exc_info=True)
    
    async def delete_channel(self, channel_id: Optional[str] = None):
        """
        Delete a channel with confirmation prompt
        
        Args:
            channel_id: Optional channel ID to delete. If not provided, prompts user to select.
        """
        # If no channel_id provided, let user select one
        if not channel_id:
            channels = self.config.get_channels()
            if not channels:
                self.ui.show_info("No channels configured yet.")
                return
            
            # Display channels and let user choose
            await self.list_channels()
            channel_id = await self.ui.prompt_input_async("\nEnter channel ID to delete")
        
        # Get channel
        channel = self.config.get_channel(channel_id)
        if not channel:
            self.ui.show_error(f"Channel {channel_id} not found")
            return
        
        # Confirm deletion
        self.console.print(f"\n[bold red]Delete Channel: {channel.get_display_name()}[/bold red]")
        self.ui.show_warning(f"This will permanently delete channel '{channel.get_display_name()}'")
        
        confirmed = await self.ui.prompt_confirm_async(
            "Are you sure you want to delete this channel?",
            default=False
        )
        
        if not confirmed:
            self.ui.show_info("Deletion cancelled")
            return
        
        try:
            # Delete channel
            success = await self.config.remove_channel(channel_id)
            
            if success:
                self.ui.show_success(f"Channel '{channel.get_display_name()}' deleted successfully!")
            else:
                self.ui.show_error("Failed to delete channel")
        
        except Exception as e:
            self.ui.show_error(f"Error deleting channel: {e}")
            logger.error(f"Error in delete_channel: {e}", exc_info=True)
    
    async def manage_reactions(self, channel_id: Optional[str] = None):
        """
        Manage reaction list for a channel (add/remove/weight reactions)
        
        Args:
            channel_id: Optional channel ID. If not provided, prompts user to select.
        """
        # If no channel_id provided, let user select one
        if not channel_id:
            channels = self.config.get_channels()
            if not channels:
                self.ui.show_info("No channels configured yet.")
                return
            
            # Display channels and let user choose
            await self.list_channels()
            channel_id = await self.ui.prompt_input_async("\nEnter channel ID to manage reactions")
        
        # Get channel
        channel = self.config.get_channel(channel_id)
        if not channel:
            self.ui.show_error(f"Channel {channel_id} not found")
            return
        
        while True:
            self.console.print(f"\n[bold cyan]Manage Reactions: {channel.get_display_name()}[/bold cyan]")
            self.ui.print_separator()
            
            # Display current reactions
            if channel.reactions:
                self.console.print("\n[bold]Current Reactions:[/bold]")
                for i, reaction in enumerate(channel.reactions, 1):
                    self.console.print(f"  {i}. {reaction.emoji} (weight: {reaction.weight})")
            else:
                self.console.print("\n[yellow]No reactions configured[/yellow]")
            
            # Show menu
            self.console.print("\n[bold]Options:[/bold]")
            self.console.print("  1. Add reaction")
            self.console.print("  2. Remove reaction")
            self.console.print("  3. Change reaction weight")
            self.console.print("  4. Back to channel menu")
            
            try:
                choice = await self.ui.prompt_input_async("\nEnter choice (1-4)")
                
                if choice == "1":
                    await self._add_reaction(channel)
                elif choice == "2":
                    await self._remove_reaction(channel)
                elif choice == "3":
                    await self._change_reaction_weight(channel)
                elif choice == "4":
                    break
                else:
                    self.ui.show_error("Invalid choice. Please enter 1-4.")
            
            except KeyboardInterrupt:
                self.ui.show_warning("\nReturning to channel menu")
                break
            except Exception as e:
                self.ui.show_error(f"Error: {e}")
                logger.error(f"Error in manage_reactions: {e}", exc_info=True)
    
    async def _add_reaction(self, channel: ChannelConfig):
        """Add a reaction to a channel"""
        try:
            emoji = await self.ui.prompt_input_async("Enter emoji reaction")
            if not emoji:
                self.ui.show_error("Emoji cannot be empty")
                return
            
            # Check if reaction already exists
            if any(r.emoji == emoji for r in channel.reactions):
                self.ui.show_error(f"Reaction {emoji} already exists for this channel")
                return
            
            weight_str = await self.ui.prompt_input_async(
                "Enter weight (1-10)",
                default="1"
            )
            
            # Validate weight
            try:
                weight = int(weight_str) if weight_str else 1
                if weight < 1 or weight > 10:
                    self.ui.show_error("Weight must be between 1 and 10")
                    return
            except ValueError:
                self.ui.show_error("Weight must be a valid number")
                return
            
            # Add reaction
            channel.reactions.append(ReactionConfig(emoji=emoji, weight=weight))
            
            # Save changes
            success = await self.config.update_channel(channel)
            
            if success:
                self.ui.show_success(f"Reaction {emoji} added successfully!")
            else:
                self.ui.show_error("Failed to add reaction")
        
        except Exception as e:
            self.ui.show_error(f"Error adding reaction: {e}")
            logger.error(f"Error in _add_reaction: {e}", exc_info=True)
    
    async def _remove_reaction(self, channel: ChannelConfig):
        """Remove a reaction from a channel"""
        if not channel.reactions:
            self.ui.show_info("No reactions to remove")
            return
        
        try:
            # Display reactions with numbers
            self.console.print("\n[bold]Select reaction to remove:[/bold]")
            for i, reaction in enumerate(channel.reactions, 1):
                self.console.print(f"  {i}. {reaction.emoji} (weight: {reaction.weight})")
            
            choice = await self.ui.prompt_input_async(f"Enter number (1-{len(channel.reactions)})")
            
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(channel.reactions):
                    self.ui.show_error("Invalid selection")
                    return
                
                removed_reaction = channel.reactions.pop(index)
                
                # Save changes
                success = await self.config.update_channel(channel)
                
                if success:
                    self.ui.show_success(f"Reaction {removed_reaction.emoji} removed successfully!")
                else:
                    self.ui.show_error("Failed to remove reaction")
            
            except ValueError:
                self.ui.show_error("Please enter a valid number")
        
        except Exception as e:
            self.ui.show_error(f"Error removing reaction: {e}")
            logger.error(f"Error in _remove_reaction: {e}", exc_info=True)
    
    async def _show_join_status(self, channel_id: str) -> str:
        """
        Get join status summary for a channel
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            Formatted string like "3/5 joined" or "N/A" if session manager unavailable
            
        Requirements: 4.1
        """
        if not self.session_manager:
            return "N/A"
        
        try:
            # Get join status from session manager
            status_dict = await self.session_manager.get_channel_join_status(channel_id)
            
            if not status_dict:
                return "0/0"
            
            # Count joined sessions
            joined_count = sum(1 for status in status_dict.values() if status.get('joined', False))
            total_count = len(status_dict)
            
            # Format with color
            if joined_count == 0:
                return f"[red]{joined_count}/{total_count}[/red]"
            elif joined_count == total_count:
                return f"[green]{joined_count}/{total_count}[/green]"
            else:
                return f"[yellow]{joined_count}/{total_count}[/yellow]"
        
        except Exception as e:
            logger.error(f"Error getting join status for {channel_id}: {e}")
            return "Error"
    
    async def _show_monitoring_statistics(self, channel_id: str) -> str:
        """
        Get monitoring statistics summary for a channel
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            Formatted string like "R:10 M:50" (Reactions:10, Messages:50) or "N/A" if unavailable
            
        Requirements: 4.3
        """
        if not self.session_manager:
            return "N/A"
        
        try:
            # Get monitoring statistics from session manager
            stats = self.session_manager.get_monitoring_statistics(channel_id)
            
            if not stats or stats.get('active_sessions', 0) == 0:
                return "-"
            
            reactions_sent = stats.get('total_reactions_sent', 0)
            messages_processed = stats.get('total_messages_processed', 0)
            
            # Format as "R:X M:Y"
            return f"R:{reactions_sent} M:{messages_processed}"
        
        except Exception as e:
            logger.error(f"Error getting monitoring statistics for {channel_id}: {e}")
            return "Error"
    
    async def _show_detailed_join_status(self, channel_id: str, channel_name: str):
        """
        Display detailed per-session join status for a channel
        
        Args:
            channel_id: Channel identifier
            channel_name: Channel display name
            
        Requirements: 4.1, 4.2
        """
        if not self.session_manager:
            self.ui.show_warning("Session manager not available")
            return
        
        try:
            # Get join status from session manager
            status_dict = await self.session_manager.get_channel_join_status(channel_id)
            
            if not status_dict:
                self.ui.show_info(f"No sessions available for channel '{channel_name}'")
                return
            
            # Prepare table data
            rows = []
            for session_name, status in status_dict.items():
                joined = status.get('joined', False)
                error = status.get('error')
                
                # Format status with color
                if joined:
                    status_str = "[green]✓ Joined[/green]"
                    error_str = "-"
                else:
                    status_str = "[red]✗ Not Joined[/red]"
                    error_str = error if error else "Unknown"
                
                rows.append([session_name, status_str, error_str])
            
            # Display table
            self.ui.display_table(
                title=f"Join Status for '{channel_name}' ({channel_id})",
                columns=["Session", "Status", "Error/Reason"],
                rows=rows
            )
        
        except Exception as e:
            self.ui.show_error(f"Error getting detailed join status: {e}")
            logger.error(f"Error in _show_detailed_join_status for {channel_id}: {e}", exc_info=True)
    
    def _display_join_results(self, join_results: dict):
        """
        Display join results in a formatted table
        
        Args:
            join_results: Dict mapping session names to join success status
        """
        if not join_results:
            self.ui.show_warning("No join results to display")
            return
        
        # Prepare table data
        rows = []
        for session_name, success in join_results.items():
            status = "[green]✓ Joined[/green]" if success else "[red]✗ Failed[/red]"
            rows.append([session_name, status])
        
        # Display table
        self.ui.display_table(
            title="Channel Join Results",
            columns=["Session", "Status"],
            rows=rows
        )
        
        # Display summary
        succeeded = sum(1 for success in join_results.values() if success)
        failed = len(join_results) - succeeded
        
        if succeeded == len(join_results):
            self.ui.show_success(f"All {succeeded} sessions joined successfully!")
        elif succeeded > 0:
            self.ui.show_warning(f"{succeeded} sessions joined, {failed} failed")
        else:
            self.ui.show_error(f"All {failed} sessions failed to join")
    
    async def _change_reaction_weight(self, channel: ChannelConfig):
        """Change the weight of a reaction"""
        if not channel.reactions:
            self.ui.show_info("No reactions to modify")
            return
        
        try:
            # Display reactions with numbers
            self.console.print("\n[bold]Select reaction to modify:[/bold]")
            for i, reaction in enumerate(channel.reactions, 1):
                self.console.print(f"  {i}. {reaction.emoji} (weight: {reaction.weight})")
            
            choice = await self.ui.prompt_input_async(f"Enter number (1-{len(channel.reactions)})")
            
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(channel.reactions):
                    self.ui.show_error("Invalid selection")
                    return
                
                reaction = channel.reactions[index]
                self.console.print(f"\nCurrent weight for {reaction.emoji}: [yellow]{reaction.weight}[/yellow]")
                
                new_weight_str = await self.ui.prompt_input_async(
                    "Enter new weight (1-10)",
                    default=str(reaction.weight)
                )
                
                # Validate weight
                try:
                    new_weight = int(new_weight_str) if new_weight_str else reaction.weight
                    if new_weight < 1 or new_weight > 10:
                        self.ui.show_error("Weight must be between 1 and 10")
                        return
                except ValueError:
                    self.ui.show_error("Weight must be a valid number")
                    return
                
                reaction.weight = new_weight
                
                # Save changes
                success = await self.config.update_channel(channel)
                
                if success:
                    self.ui.show_success(f"Weight for {reaction.emoji} updated to {new_weight}!")
                else:
                    self.ui.show_error("Failed to update weight")
            
            except ValueError:
                self.ui.show_error("Please enter a valid number")
        
        except Exception as e:
            self.ui.show_error(f"Error changing reaction weight: {e}")
            logger.error(f"Error in _change_reaction_weight: {e}", exc_info=True)
    
    async def show_detailed_statistics(self, channel_id: Optional[str] = None):
        """
        Display detailed monitoring statistics for a channel
        
        Args:
            channel_id: Optional channel ID. If not provided, prompts user to select.
            
        Requirements: 4.3
        """
        # If no channel_id provided, let user select one
        if not channel_id:
            channels = self.config.get_channels()
            if not channels:
                self.ui.show_info("No channels configured yet.")
                return
            
            # Display channels and let user choose
            await self.list_channels()
            channel_id = await self.ui.prompt_input_async("\nEnter channel ID to view statistics")
        
        # Get channel
        channel = self.config.get_channel(channel_id)
        if not channel:
            self.ui.show_error(f"Channel {channel_id} not found")
            return
        
        if not self.session_manager:
            self.ui.show_warning("Session manager not available - cannot retrieve statistics")
            return
        
        try:
            # Get aggregated statistics
            stats = self.session_manager.get_monitoring_statistics(channel_id)
            
            self.console.print(f"\n[bold cyan]Monitoring Statistics: {channel.get_display_name()}[/bold cyan]")
            self.ui.print_separator()
            
            if stats.get('active_sessions', 0) == 0:
                self.ui.show_info("No active monitoring sessions for this channel")
                return
            
            # Display aggregated statistics
            self.console.print(f"[bold]Active Sessions:[/bold] {stats.get('active_sessions', 0)}")
            self.console.print(f"[bold]Total Reactions Sent:[/bold] {stats.get('total_reactions_sent', 0)}")
            self.console.print(f"[bold]Total Messages Processed:[/bold] {stats.get('total_messages_processed', 0)}")
            self.console.print(f"[bold]Total Reaction Failures:[/bold] {stats.get('total_reaction_failures', 0)}")
            
            # Calculate success rate if there were attempts
            total_attempts = stats.get('total_reactions_sent', 0) + stats.get('total_reaction_failures', 0)
            if total_attempts > 0:
                success_rate = (stats.get('total_reactions_sent', 0) / total_attempts) * 100
                self.console.print(f"[bold]Success Rate:[/bold] {success_rate:.1f}%")
            
            # Show per-session breakdown
            show_breakdown = await self.ui.prompt_confirm_async(
                "\nShow per-session breakdown?",
                default=False
            )
            
            if show_breakdown:
                self.console.print("\n[bold cyan]Per-Session Statistics:[/bold cyan]")
                rows = []
                
                for session_name, session in self.session_manager.sessions.items():
                    if session.is_connected:
                        session_stats = session.get_monitoring_statistics(channel_id)
                        if session_stats.get('monitoring_active', False):
                            rows.append([
                                session_name,
                                session_stats.get('reactions_sent', 0),
                                session_stats.get('messages_processed', 0),
                                session_stats.get('reaction_failures', 0)
                            ])
                
                if rows:
                    self.ui.display_table(
                        title=f"Session Statistics for {channel.get_display_name()}",
                        columns=["Session", "Reactions Sent", "Messages Processed", "Failures"],
                        rows=rows
                    )
                else:
                    self.ui.show_info("No session-level statistics available")
        
        except Exception as e:
            self.ui.show_error(f"Error retrieving statistics: {e}")
            logger.error(f"Error in show_detailed_statistics for {channel_id}: {e}", exc_info=True)
    
    def show_menu(self):
        """Display channel management menu"""
        self.console.print("\n[bold cyan]Channel Management[/bold cyan]")
        self.ui.print_separator()
        self.console.print("  1. List channels")
        self.console.print("  2. List channels with detailed join status")
        self.console.print("  3. Add channel")
        self.console.print("  4. Edit channel")
        self.console.print("  5. Delete channel")
        self.console.print("  6. Manage reactions")
        self.console.print("  7. View detailed statistics")
        self.console.print("  8. Back to main menu")
        self.console.print()
    
    async def run(self):
        """Run the channel manager interactive menu"""
        while True:
            try:
                self.show_menu()
                choice = await self.ui.prompt_input_async("Enter choice (1-8)")
                
                if choice == "1":
                    await self.list_channels()
                elif choice == "2":
                    await self.list_channels(show_detailed_join_status=True)
                elif choice == "3":
                    await self.add_channel()
                elif choice == "4":
                    await self.edit_channel()
                elif choice == "5":
                    await self.delete_channel()
                elif choice == "6":
                    await self.manage_reactions()
                elif choice == "7":
                    await self.show_detailed_statistics()
                elif choice == "8":
                    break
                else:
                    self.ui.show_error("Invalid choice. Please enter 1-8.")
            
            except KeyboardInterrupt:
                self.ui.show_warning("\nReturning to main menu")
                break
            except Exception as e:
                self.ui.show_error(f"Error: {e}")
                logger.error(f"Error in channel manager menu: {e}", exc_info=True)


# Example usage
async def main():
    """Example usage of ChannelManagerCLI"""
    config = ConfigManager('cli/config.json')
    await config.load()
    
    manager = ChannelManagerCLI(config)
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
